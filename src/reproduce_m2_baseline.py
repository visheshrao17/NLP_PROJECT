#!/usr/bin/env python3
"""API-based M2 reproduction for Spracks/PackageHallucination.

This script replaces the repository's local Hugging Face checkpoint loop with an
OpenAI-compatible client.  It preserves the experiment's two-stage structure:
generate Python code, then elicit package recommendations.  It additionally
extracts imports and pip-install commands deterministically for a transparent
registry-based score.

Examples
--------
export OPENAI_API_KEY='...'
python reproduce_m2_baseline.py --repo-root /path/to/PackageHallucination \
  --base-url https://openrouter.ai/api/v1 --models small=model-a large=model-b

The default 200 prompts are stratified as 100 from SO_LY and 100 from LLM_LY.
Use --dry-run to validate the repository/data layout without an API key.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SYSTEM_CODE = (
    "You are a careful Python coding assistant. Return only runnable Python code. "
    "Use only packages that are real and available from PyPI or the Python standard library."
)
SYSTEM_PACKAGES = (
    "Return only a comma-separated list of Python package names required or useful "
    "for the answer. Do not add prose, Markdown, versions, or explanations."
)
SYSTEM_BINARY = "Reply with exactly one word: Yes or No."
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)", re.MULTILINE)
PIP_RE = re.compile(r"(?:^|[;&|]\s*|\b)(?:python(?:3)?\s+-m\s+)?pip\s+install\s+([^\n\r;&|]+)", re.I)
PACKAGE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(frozen=True)
class ModelSpec:
    label: str
    model: str


@dataclass
class ApiClient:
    base_url: str
    api_key: str
    timeout: int
    retries: int

    def chat(self, model: str, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        payload = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"].strip()
            except (urllib.error.HTTPError, urllib.error.URLError, KeyError, json.JSONDecodeError) as error:
                last_error = error
                if attempt == self.retries:
                    break
                time.sleep(min(2 ** attempt, 12))
        raise RuntimeError(f"API request failed after {self.retries + 1} attempts: {last_error}")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip(" `.,;:()[]{}'\"").lower())


def read_jsonl_prompts(path: Path) -> list[str]:
    prompts: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                candidate = value.get("0")
                if candidate is None and value:
                    candidate = next(iter(value.values()))
            else:
                candidate = value
            if not isinstance(candidate, str):
                raise ValueError(f"{path}:{line_number} does not contain a string prompt")
            prompts.append(candidate)
    return prompts


def stratified_sample(repo_root: Path, per_dataset: int, seed: int) -> list[dict[str, Any]]:
    randomizer = random.Random(seed)
    selected: list[dict[str, Any]] = []
    for dataset in ("SO_LY", "LLM_LY"):
        prompts = read_jsonl_prompts(repo_root / "Data" / "Python" / f"{dataset}.json")
        if per_dataset > len(prompts):
            raise ValueError(f"Requested {per_dataset} prompts from {dataset}, which contains {len(prompts)}")
        for source_index in sorted(randomizer.sample(range(len(prompts)), per_dataset)):
            selected.append({"dataset": dataset, "source_index": source_index, "prompt": prompts[source_index]})
    return selected


def load_registry(repo_root: Path) -> tuple[set[str], set[str]]:
    data_dir = repo_root / "Data" / "Python"
    packages_path = data_dir / "pypi_package_names.csv"
    if not packages_path.exists():
        raise FileNotFoundError(f"Missing PyPI master list: {packages_path}")
    registry: set[str] = set()
    with packages_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if row and row[0].strip():
                registry.add(normalize(row[0]))
    exceptions: set[str] = set()
    false_positive_path = data_dir / "false_positive_packages.csv"
    if false_positive_path.exists():
        with false_positive_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if row:
                    exceptions.add(normalize(row[-1]))
    return registry, exceptions


def code_only(text: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\s*\n?(.*?)```", text, flags=re.I | re.S)
    return max(blocks, key=len).strip() if blocks else text.strip()


def extract_imports(code: str) -> set[str]:
    modules: set[str] = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
    except SyntaxError:
        modules.update(match.group(1).split(".")[0] for match in IMPORT_RE.finditer(code))
    return {normalize(module) for module in modules if module}


def extract_pip_packages(text: str) -> set[str]:
    packages: set[str] = set()
    for match in PIP_RE.finditer(text):
        for raw_token in match.group(1).split():
            if raw_token.startswith(("-", ".", "/")) or "://" in raw_token:
                continue
            distribution = re.split(r"(?:===|==|>=|<=|~=|!=|>|<|\[|@)", raw_token, maxsplit=1)[0]
            if PACKAGE_TOKEN_RE.fullmatch(distribution):
                packages.add(normalize(distribution))
    return packages


def extract_recommendations(text: str) -> set[str]:
    candidates: set[str] = set()
    for chunk in re.split(r"[,\n;]", text):
        candidate = normalize(re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", chunk))
        if PACKAGE_TOKEN_RE.fullmatch(candidate):
            candidates.add(candidate)
    return candidates


def is_valid_package(name: str, registry: set[str], exceptions: set[str]) -> bool:
    stdlib = {normalize(module) for module in getattr(sys, "stdlib_module_names", set())}
    return name in registry or name in stdlib or name in exceptions


def evaluate(candidates: Iterable[str], registry: set[str], exceptions: set[str]) -> tuple[list[str], list[str]]:
    unique = sorted(set(candidates))
    valid = [name for name in unique if is_valid_package(name, registry, exceptions)]
    invalid = [name for name in unique if name not in valid]
    return valid, invalid


def binary_answer(client: ApiClient, model: str, package: str) -> bool:
    answer = client.chat(model, [
        {"role": "system", "content": SYSTEM_BINARY},
        {"role": "user", "content": f"Is {package} a valid Python package?"},
    ], temperature=0.0, max_tokens=3)
    return answer.strip().lower().startswith("yes")


def generate(client: ApiClient, model: str, prompt: str, temperature: float, banned: set[str]) -> str:
    constraint = ""
    if banned:
        constraint = "\nDo not use or recommend these packages: " + ", ".join(sorted(banned)) + "."
    return client.chat(model, [
        {"role": "system", "content": SYSTEM_CODE},
        {"role": "user", "content": prompt + constraint},
    ], temperature=temperature, max_tokens=2048)


def recommend(client: ApiClient, model: str, prompt: str, code: str) -> str:
    return client.chat(model, [
        {"role": "system", "content": SYSTEM_PACKAGES},
        {"role": "user", "content": f"Problem:\n{prompt}\n\nGenerated code:\n{code}"},
    ], temperature=0.0, max_tokens=128)


def run_condition(
    client: ApiClient,
    samples: list[dict[str, Any]],
    model_spec: ModelSpec,
    temperature: float,
    mitigation: str,
    registry: set[str],
    exceptions: set[str],
    max_regenerations: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for position, sample in enumerate(samples, 1):
        print(f"[{model_spec.label} T={temperature} {mitigation}] {position}/{len(samples)}", flush=True)
        banned: set[str] = set()
        refusal_valid = 0
        valid_checked = 0
        regenerations = 0
        while True:
            response = generate(client, model_spec.model, sample["prompt"], temperature, banned)
            code = code_only(response)
            recommendation_text = recommend(client, model_spec.model, sample["prompt"], code)
            candidates = extract_imports(code) | extract_pip_packages(code) | extract_recommendations(recommendation_text)
            valid, invalid = evaluate(candidates, registry, exceptions)
            flagged: set[str] = set()
            if mitigation == "self_detection":
                for package in sorted(candidates):
                    model_says_valid = binary_answer(client, model_spec.model, package)
                    if is_valid_package(package, registry, exceptions):
                        valid_checked += 1
                        refusal_valid += int(not model_says_valid)
                    if not model_says_valid:
                        flagged.add(package)
            if mitigation != "self_detection" or not flagged or regenerations >= max_regenerations:
                break
            banned.update(flagged)
            regenerations += 1
        records.append({
            "dataset": sample["dataset"], "source_index": sample["source_index"],
            "prompt_id": hashlib.sha256(sample["prompt"].encode()).hexdigest()[:12],
            "model_size": model_spec.label, "model": model_spec.model, "temperature": temperature,
            "mitigation": mitigation, "regenerations": regenerations,
            "candidates": "|".join(sorted(candidates)), "valid_packages": "|".join(valid),
            "hallucinated_packages": "|".join(invalid), "candidate_count": len(candidates),
            "hallucinated_count": len(invalid), "has_hallucination": int(bool(invalid)),
            "valid_packages_checked": valid_checked, "valid_packages_refused": refusal_valid,
            "false_positive_refusal_rate": (refusal_valid / valid_checked) if valid_checked else None,
        })
    return records


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, float, str], list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault((record["model_size"], record["model"], record["temperature"], record["mitigation"]), []).append(record)
    rows: list[dict[str, Any]] = []
    for (size, model, temperature, mitigation), values in sorted(groups.items()):
        candidate_count = sum(item["candidate_count"] for item in values)
        hallucinated_count = sum(item["hallucinated_count"] for item in values)
        valid_checked = sum(item["valid_packages_checked"] for item in values)
        valid_refused = sum(item["valid_packages_refused"] for item in values)
        rows.append({
            "model_size": size, "model": model, "temperature": temperature, "mitigation": mitigation,
            "prompts": len(values), "package_references": candidate_count,
            "hallucinated_references": hallucinated_count,
            "hallucination_rate_pct": round(100 * hallucinated_count / candidate_count, 2) if candidate_count else 0.0,
            "prompt_hallucination_rate_pct": round(100 * sum(item["has_hallucination"] for item in values) / len(values), 2),
            "valid_packages_checked": valid_checked, "valid_packages_refused": valid_refused,
            "false_positive_refusal_rate_pct": round(100 * valid_refused / valid_checked, 2) if valid_checked else "NA",
            "mean_regenerations": round(sum(item["regenerations"] for item in values) / len(values), 3),
        })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = ["model_size", "temperature", "mitigation", "prompts", "package_references", "hallucination_rate_pct", "prompt_hallucination_rate_pct", "false_positive_refusal_rate_pct", "mean_regenerations"]
    with path.open("w", encoding="utf-8") as handle:
        handle.write("# M2 API Reproduction Summary\n\n")
        handle.write("Hallucination rate is hallucinated package references / all extracted package references. "
                     "False-positive refusal rate is valid registry/stdlib references rejected by the LLM self-detector / valid references checked.\n\n")
        handle.write("| " + " | ".join(column.replace("_", " ") for column in columns) + " |\n")
        handle.write("|" + "|".join("---" for _ in columns) + "|\n")
        for row in rows:
            handle.write("| " + " | ".join(str(row[column]) for column in columns) + " |\n")


def latex_escape(value: Any) -> str:
    """Escape summary-cell content for the generated LaTeX table."""
    return str(value).replace("_", "\\_").replace("%", "\\%")


def write_latex(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a self-contained table that can be included with \\input{summary.tex}."""
    columns = ["model_size", "temperature", "mitigation", "prompts", "package_references", "hallucination_rate_pct", "prompt_hallucination_rate_pct", "false_positive_refusal_rate_pct"]
    labels = ["Model", "$T$", "Condition", "Prompts", "Claims", "Halluc. (\\%)", "Prompt rate (\\%)", "FP refusal (\\%)"]
    with path.open("w", encoding="utf-8") as handle:
        handle.write("% Generated by reproduce_m2_baseline.py; do not edit by hand.\n")
        handle.write("\\begin{table}[t]\n\\centering\n\\small\n")
        handle.write("\\caption{M2 API-based baseline reproduction summary.}\n")
        handle.write("\\label{tab:m2-results}\n")
        handle.write("\\begin{tabular}{lllr rrrr}\n\\toprule\n")
        handle.write(" & ".join(labels) + " \\\\n\\midrule\n")
        for row in rows:
            handle.write(" & ".join(latex_escape(row[column]) for column in columns) + " \\\\n")
        handle.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")


def parse_models(values: list[str]) -> list[ModelSpec]:
    models: list[ModelSpec] = []
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("Each --models entry must be LABEL=MODEL_ID")
        label, model = value.split("=", 1)
        if label not in {"small", "large"}:
            raise argparse.ArgumentTypeError("Model labels must be small or large")
        models.append(ModelSpec(label, model))
    if {model.label for model in models} != {"small", "large"}:
        raise argparse.ArgumentTypeError("Provide exactly one small=... and one large=... model")
    return models


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Root of cloned PackageHallucination repository")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--models", nargs="+", default=["small=meta-llama/llama-3.1-8b-instruct", "large=meta-llama/llama-3.3-70b-instruct"])
    parser.add_argument("--per-dataset", type=int, default=100, help="SO_LY and LLM_LY prompts each; default total is 200")
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--max-regenerations", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    models = parse_models(args.models)
    registry, exceptions = load_registry(repo_root)
    samples = stratified_sample(repo_root, args.per_dataset, args.seed)
    print(f"Validated {repo_root}; sampled {len(samples)} prompts; loaded {len(registry)} PyPI names.")
    if args.dry_run:
        return
    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Set {args.api_key_env} or choose it with --api-key-env before running.")
    output_dir = (args.output_dir or repo_root / "Tests" / "M2_API_Reproduction").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    client = ApiClient(args.base_url, api_key, args.timeout, args.retries)
    records: list[dict[str, Any]] = []
    for model_spec in models:
        for temperature in (0.0, 0.7):
            records.extend(run_condition(client, samples, model_spec, temperature, "baseline", registry, exceptions, args.max_regenerations))
            records.extend(run_condition(client, samples, model_spec, temperature, "self_detection", registry, exceptions, args.max_regenerations))
    summary = summarize(records)
    write_csv(output_dir / "prompt_level_results.csv", records)
    write_csv(output_dir / "summary.csv", summary)
    write_markdown(output_dir / "summary.md", summary)
    write_latex(output_dir / "summary.tex", summary)
    (output_dir / "run_config.json").write_text(json.dumps({
        "repo_root": str(repo_root), "base_url": args.base_url, "models": [model.__dict__ for model in models],
        "per_dataset": args.per_dataset, "seed": args.seed, "max_regenerations": args.max_regenerations,
        "registry_entries": len(registry), "exception_entries": len(exceptions),
    }, indent=2), encoding="utf-8")
    print(f"Wrote slide-ready results to {output_dir}")


if __name__ == "__main__":
    main()
