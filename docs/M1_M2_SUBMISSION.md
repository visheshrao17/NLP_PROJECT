# M1–M2 Submission: Verifying Package Claims in LLM-Generated Code

**Project focus.** This project studies codebase hallucinations at the package/API boundary, where a plausible but nonexistent dependency can become a supply-chain attack opportunity. M1 audits the anchor study and establishes baselines. M2 replaces its expensive local-checkpoint inference loop with a controlled API experiment. M3/M4 test whether a portable, inference-time verification skill can reduce invalid package references more reliably than static retrieval or an LLM judging its own claims.

## 1. M1 Literature Survey and Synthesis Matrix

| Work | Target hallucination type | Evaluation granularity | Mitigation mechanism | Key quantitative finding | Limitation and research gap |
|---|---|---|---|---|---|
| **Spracklen et al. (Anchor, 2025)** | Nonexistent Python/PyPI or JavaScript/npm package reference; a supply-chain security risk | Package reference, prompt, model, language, temperature, prompt-source; 576,000 generations from 16 models | Static RAG, LLM self-detection/self-refinement, fine-tuning | 19.7% of recommended packages were hallucinated overall; commercial models at least 5.2%, open models at least 21.7%; 205,474 unique nonexistent names | Evaluation is registry-oriented but mitigation delegates validity to the same LLM or static context. It does not isolate an executable, deterministic inference-time gate from prose guidance. |
| **HalluCode / Liu et al. (2024; revised 2026)** | Broad code hallucinations: intent conflict, context deviation, and real-world knowledge conflict; 3 primary / 12 specific categories | Fine-grained snippet/category and benchmark level; 3,120 samples across HumanEval/CoderEval | Training-free prompt enhancement explored | 1,134/3,120 samples (36.35%) contain a hallucination; pass@1 is 6.26 with hallucination versus 54.73 without; requirement-conflict is 39.60% of annotated hallucinations | Broad taxonomy lacks a focused supply-chain package/API verifier and does not measure a registry-enforced agent loop. |
| **SkillsBench / Li et al. (2026)** | Missing or unreliable procedural knowledge in agent tasks, not package hallucination specifically | 86 tasks, 11 domains, 7 agent-model configurations, 7,308 trajectories; deterministic task verifiers | Curated Skills vs no Skill vs self-generated Skill | Curated Skills: +16.2 percentage points (pp) average pass rate; self-generated Skills: −1.3pp; 16/84 tasks declined; focused 2–3 modules beat broad documentation | Shows Skills can help but are heterogeneous and may harm. It does not distinguish instruction-following benefit from executable factual verification. |
| **SWE-Skills-Bench / Han et al. (2026)** | Whether public SWE Skills help or distract agents in repository tasks | 98 public skills × 10 requirements × 4 configurations; 3,920 paired evaluations; requirement-level paired deltas | Injected public Skills; per-skill utility classification | Only 6/98 Skills significantly help; pass ratio moves 76.6%→76.9%; helpful effects up to +17.7 points and harmful effects down to −17.0 | Public prose Skills often anchor agents to templates. It motivates a narrow Skill with a deterministic hook and explicit, testable contract. |
| **NLAH / Pan et al. (2026)** | Opaque, controller-embedded agent-harness behavior | Run-level harness policy/modules, coding/terminal/computer-use tasks, module ablations | Executable natural-language harness interpreted by a shared runtime | NLAHs attain comparable outcomes to code and prompted realizations while exposing shorter, inspectable policy artifacts | Does not target factual dependency validity or compare deterministic registry gates with LLM self-checking. Our `SKILL.md` is a domain-specific NLAH-style policy plus a hard verifier. |
| **CRITIC / Gou et al. (ICLR 2024)** | Factual errors, flawed math programs, and toxic output | Output/revision trajectory on QA, program synthesis, and toxicity | Iterative verify → critique → revise using external tools | Tool feedback consistently improves evaluated tasks; on TabMWP, reported LLaMA-2 gains grow 7B +4.7%, 13B +9.4%, 70B +16.0% | Tool choice and critique are still model-mediated, and it does not measure package false positives or supply-chain outcomes. It provides the causal template for external evidence before revision. |

### Critical synthesis

The anchor paper establishes that package hallucination is measurable, persistent, and security-relevant; however, its self-detection baseline asks the generator to answer the factual question it just failed: *“Is [package] a valid Python package?”* This is an intrinsic judgment, not an independently grounded verification decision. CRITIC’s core lesson is that correction becomes dependable when it is conditioned on external feedback. Here, the external feedback can be much stronger and cheaper than open-web search: a versioned PyPI snapshot plus AST-extracted import/install claims.

HalluCode expands the dependent variable beyond compilation or unit-test success: code can be functionally plausible yet contain a nonexistent dependency. SkillsBench and SWE-Skills-Bench add a necessary caution: a Skill is not automatically beneficial. Broad or templated natural-language instructions can be neutral or harmful. Therefore C3 (prose-only `SKILL.md`) is a required negative control, not a presumed solution. NLAH supplies the representation argument: harness policy should be portable, inspectable, and ablatable. The proposed C4 makes this concrete by separating (i) editable policy in `SKILL.md`, (ii) deterministic evidence from a verifier, and (iii) a gate that blocks delivery until claims pass.

**Research contribution.** The causal question is not “do more instructions help?” It is: **holding model, prompt, decoding, and regenerate budget fixed, does executable external package verification reduce invalid dependency references more than RAG, LLM self-detection, and prose-only guidance, without an unacceptable valid-package refusal cost?**

Primary sources: [Anchor paper](https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf), [HalluCode](https://arxiv.org/abs/2404.00971), [SkillsBench](https://arxiv.org/abs/2602.12670), [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401), [NLAH](https://arxiv.org/abs/2603.25723), [CRITIC](https://arxiv.org/abs/2305.11738).

## 2. M1 Reproducibility Audit: `Spracks/PackageHallucination`

| Audit item | What the upstream repository supplies | Reproduction decision / check | Risk to validity |
|---|---|---|---|
| Repository release | Public code and data repository; README documents an end-to-end generation → extraction → detection pipeline | Pin the commit hash, archive `requirements.txt`/`environment.yml`, and record Python, CUDA, API provider, model identifier, date, and decoding settings | Upstream scripts contain workstation-specific paths in mitigation helpers, so an unpinned run is not portable. |
| Python prompt artifacts | `Data/Python/SO_AT.json`, `SO_LY.json`, `LLM_AT.json`, `LLM_LY.json`; JSONL rows with a prompt field | Use `SO_LY` and `LLM_LY`; sample 100 rows per source without replacement with seed `20261028` (200 total) | Prompt source is a confounder; report source-stratified and pooled results. |
| JavaScript artifacts | Parallel `Data/Javascript/` datasets plus `npm_package_names.zip`, core modules, options, and false-positive list | Out of M2 scope; retain as a future language-transfer replication | Python-only claims must not be generalized to npm. |
| Registry/master lists | `Data/Python/pypi_package_names.csv`; `Data/Python/false_positive_packages.csv`; JavaScript npm list and exceptions | Normalize using PEP 503-style `[-_.]+ → -`; add `sys.stdlib_module_names`; save the list checksum/version with each run | Distribution names and import names differ (`scikit-learn`/`sklearn`), so report this as registry-proxy validity and maintain an auditable alias file if introduced. |
| Heuristic 1: install command | `package_detection.parse_pip_install` detects `pip install ...`, strips versions/options, then matches master list | M2 captures `pip install` and `python -m pip install`, removes version specifiers/options, then checks snapshot registry | Regex misses shell indirection and requirements files; count only explicit claims and retain raw outputs. |
| Heuristic 2: dependency query | `generate_package_names.py` asks the model which packages are required to run generated code | M2 makes the same separate package-recommendation API call after code generation | Elicited package lists can add names absent from source code; score extraction channel separately in prompt-level records. |
| Heuristic 3: direct recommendation | A second query asks which packages would be useful for the original coding problem | M2 captures this via the prompt+code package recommendation and supplements it with AST imports | Recommendation wording is model-sensitive; use temperature 0 for this elicitation and preserve raw output in an optional audit log. |
| Package detection | `package_detection.py` merges the two LLM query outputs and `pip` extraction, normalizes names, and checks master list | M2 uses AST imports first (regex fallback on syntax error), explicit pip extraction, and recommendation parsing; union is deduplicated before scoring | AST finds import modules, not necessarily distributions. This is intentional evidence of the codebase claim, but must be reported separately from dependency-name claims. |
| RAG baseline | `Mitigation/RAG_setup.py` embeds package descriptions; `run_model_RAG.py` retrieves package context and calls an OpenAI-compatible local web UI | C1 runs the upstream retrieval corpus/prompt template as frozen; log embedding model, index build date, top-k, and retrieved text | “Static RAG” may be stale and can expose a candidate without proving it is valid at execution time. |
| Self-detection baseline | `run_model_SD.py`/`webui_api_package_query_RAG_SD.py` asks whether candidate packages are valid and regenerates while avoiding rejected names | C2 reproduces the same binary prompt at T=0, regeneration budget 2, and logs decision-level false-positive refusals against the deterministic registry | The supplied implementation has hard-coded absolute paths and is model-as-judge; self-belief is not a source of truth. |
| Full local inference | `generate_code.py` loads an `AutoTokenizer` and `AutoModelForCausalLM` from `Models/<name>` with `device_map="cuda"`, then generates every dataset/prompt configuration | Do **not** claim bitwise reproduction. The local model weights, quantization, GPU memory/throughput, and four datasets × generation/recommendation passes make the documented 24–72 h runtime credible | Different models/providers are a new experiment, not a reproduction of exact paper rates. |
| M2 API adaptation | No API adapter is provided for remote commercial inference | Use `reproduce_m2_baseline.py` with an OpenAI-compatible endpoint (OpenRouter, Gemini OpenAI-compatibility endpoint, Groq, etc.), `small=...`, `large=...`, T∈{0,0.7}, and the fixed 200-prompt stratified subset | Provider model aliases, silent model upgrades, rate limits, and API nondeterminism must be disclosed in `run_config.json`. |
| Outputs and metrics | Upstream stores result files under `Tests/` and aggregate totals | M2 writes prompt-level CSV, summary CSV, Markdown slide table, and exact configuration JSON | Primary rate is invalid references / extracted references; also report prompt-level incidence and false-positive refusal rate. Do not conflate them. |

### Exact M2 protocol

1. Clone and pin `Spracks/PackageHallucination`; install only a Python 3.10+ standard runtime for the script.
2. Set `OPENAI_API_KEY`, select one roughly 7B/8B and one ≥70B model exposed by the same OpenAI-compatible provider, and use a provider-specific `--base-url`.
3. Run a deterministic 100/100 stratified sample from `SO_LY` and `LLM_LY` with seed `20261028`.
4. For each model size and `T∈{0.0, 0.7}`, run C0 and C2. Use T=0 for package elicitation and validity queries; use the code temperature only for code generation.
5. Never send generated hallucinated names to a public registry for installation. Store identifiers only in access-controlled research artifacts when required; the script’s summary aggregates rates for slide use.

Command template:

```bash
export OPENAI_API_KEY='...'
python reproduce_m2_baseline.py \
  --repo-root /absolute/path/PackageHallucination \
  --base-url https://openrouter.ai/api/v1 \
  --models small=provider/small-8b-instruct large=provider/large-70b-instruct
```

The upstream repository itself documents the 24–72 hour full-run range and its 16-model/576,000-sample evaluation. [Repository README](https://github.com/Spracks/PackageHallucination) and [anchor paper](https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf).

## 3. M2 Baseline Reproduction Code

The complete drop-in implementation is [`reproduce_m2_baseline.py`](./reproduce_m2_baseline.py). Copy it to the root of a cloned anchor repository (or pass `--repo-root` from elsewhere). It uses only the Python standard library, supports any OpenAI-compatible endpoint, and produces:

- `Tests/M2_API_Reproduction/prompt_level_results.csv`
- `Tests/M2_API_Reproduction/summary.csv`
- `Tests/M2_API_Reproduction/summary.md`
- `Tests/M2_API_Reproduction/run_config.json`

### Metric definitions

Let (C_i) be the deduplicated package claims extracted from output (i), and (H_i\subseteq C_i) those absent from the PyPI snapshot, stdlib list, and documented exception list.

- **Reference-level Hallucination Rate (primary):** (100 \times \sum_i |H_i| / \sum_i |C_i|).
- **Prompt Hallucination Incidence:** (100 \times \sum_i \mathbb{1}[|H_i|>0] / N).
- **False-Positive Refusal Rate (C2):** (100 \times \#\{p: p\text{ is deterministically valid and LLM says No}\}/\#\{p: p\text{ is deterministically valid and checked}\}).
- **Regeneration burden:** mean regeneration count per prompt, capped at 2 by default.

The script deliberately reports the denominator and source dataset so a low rate cannot hide a strategy that simply emits fewer dependencies. It does **not** live-query PyPI: M2’s registry is the anchor repository’s snapshot plus stdlib, which makes a run replayable. A later online-verification ablation should use a timestamped PyPI API cache, not unlogged live results.

## 4. M3/M4: Verify-Skill Agent Harness

### M3 research gap

Existing package-hallucination mitigation conflates *instruction* (“be accurate”), *retrieval* (show related package text), and *judgment* (ask the LLM whether it is correct). None establishes whether an independently executable, deterministic validity gate can reduce dependency hallucinations while preserving useful valid packages. Existing Skills evidence further makes it unsafe to assume that natural-language skill documents help by themselves.

### Original hypothesis

**H1.** A focused `SKILL.md` that binds generation to a deterministic AST/package verifier and a repair gate (C4) will achieve lower reference-level hallucination rate than C0–C3 at equal model, prompt, temperature, and regeneration budget. It will also reduce or match C2’s false-positive refusal rate because validity is decided by registry evidence, not the generator’s self-belief.

### Falsifiable predictions

- **P1 (safety):** C4 has a lower pooled hallucination rate than C0, C1, C2, and C3; test paired prompt-level differences with bootstrap 95% CIs and McNemar/permutation tests.
- **P2 (mechanism):** C3 may improve modestly over C0, but C4 improves significantly more than C3. This isolates executable enforcement from prose instructions.
- **P3 (selectivity):** C4’s deterministic false-positive refusal rate is ≤ C2’s at a fixed regeneration cap; any remaining false positives are attributable to registry/import-distribution mapping and are auditable.
- **P4 (robustness):** C4’s relative benefit grows or remains stable at T=0.7 and for the smaller model, where unsupported plausible names are more likely.
- **P5 (utility):** C4 does not materially degrade functional success or valid dependency recall; report a non-inferiority margin specified before results (e.g., ≤3pp decline in task tests/valid-claim recall).

### C0–C4 experimental conditions

| Condition | Intervention | What it tests |
|---|---|---|
| C0 | Vanilla code generation, small/large × T=0/0.7 | Base prevalence and scale/temperature effects |
| C1 | Frozen static RAG from `run_model_RAG.py` | Whether retrieved package descriptions suffice |
| C2 | Anchor self-detection/refinement prompt | Whether the model can reliably judge its own names |
| C3 | `SKILL.md` prose: extract claims, prefer known packages, verify before finalizing; no executable enforcement | Instruction/attention effect only |
| C4 | Same `SKILL.md` plus harness invokes AST/pip/recommendation extractor and registry/PyPI-cache hook; invalid claims cause structured repair or abstention | Incremental effect of deterministic external enforcement |

### C4 architecture and `SKILL.md` contract

```text
GENERATE candidate code
  → EXTRACT imports, pip installs, and named recommendations
  → NORMALIZE names and map import aliases
  → VERIFY against versioned PyPI snapshot + stdlib (+ optional cached live API)
  → PASS: return code with evidence manifest
  → FAIL: return structured invalid-name feedback to model
  → REPAIR up to R attempts; otherwise abstain with verified alternatives
```

The Skill contains the human-readable policy, stop condition, evidence schema, and repair instruction. The hook is a separate deterministic executable called by the harness; the model cannot override a `FAIL`. Persist a per-run `verification_manifest.jsonl` containing extracted claim, channel, normalised name, alias decision, registry outcome, snapshot version, iteration, and final action. This makes errors inspectable: model hallucination, stale registry, parser miss, or alias-mapping error are different failure classes.

### M4 ablation and analysis plan

| Ablation | Change from C4 | Diagnostic interpretation |
|---|---|---|
| A1: no prose | Remove `SKILL.md`, retain hook/gate | Measures whether the executable gate alone explains benefit |
| A2: no gate | Keep prose but return verifier feedback without blocking final answer | Separates visibility of evidence from enforcement |
| A3: no repair | Gate rejects without regeneration | Measures safety–utility trade-off of repair |
| A4: registry only vs cached live PyPI | Switch evidence source under a timestamped cache | Measures sensitivity to stale/deleted/new package state |
| A5: AST only / regex only / union | Change extraction channels | Quantifies parser coverage and false-positive sources |
| A6: no import-alias map | Disable mappings such as `sklearn→scikit-learn` | Separates registry mismatch from hallucination |
| A7: R=0,1,2,3 | Vary repair budget | Produces a cost–safety frontier |
| A8: prompt source/model/temperature strata | Analyze SO_LY vs LLM_LY; small vs large; 0 vs 0.7 | Tests generality and interaction effects |

Pre-register the primary endpoint (reference-level hallucination rate) and secondary endpoints (prompt incidence, valid-package recall, false-positive refusal, task success, latency/cost, and attempts). Use the identical sampled prompts and a paired design across all conditions. Report both micro-average (all references) and macro-average (per prompt) to prevent dependency-heavy outputs from dominating the conclusion.

## 5. Round 1 Presentation: 8-Slide Outline with Speaker Notes

### Slide 1 — Title and thesis

**On-slide content:** *Preventing Package Hallucinations with Skill-Based Verification*; M1 literature + reproducibility audit, M2 API baselines, M3/M4 harness roadmap. Thesis: “Make package validity an externally verified runtime contract, not a self-reported model belief.”

**Speaker notes:** Package hallucination is not merely a bad answer: an attacker may register a plausible missing name and turn an LLM recommendation into a supply-chain exposure. Today establishes the empirical foundation and the intervention we will test next.

### Slide 2 — Why this problem matters

**On-slide content:** Define package hallucination; chain: prompt → nonexistent dependency → malicious registration → installation. Anchor scale: 16 models, 576k samples, 19.7% hallucinated recommendations, 205,474 unique names.

**Speaker notes:** Emphasize that the unit of risk is an actionable dependency reference. Functional-looking code can still be unsafe. The anchor results motivate a verifier positioned before the developer acts, rather than a post-hoc warning.

### Slide 3 — Literature map: from hallucination to harnesses

**On-slide content:** Compact map: HalluCode = taxonomy; Anchor = package/security measurement; CRITIC = external feedback; SkillsBench/SWE-Skills-Bench = Skills help variably; NLAH = harnesses as portable experimental objects.

**Speaker notes:** These papers converge on a design principle: instructions alone are not sufficient. Skills can help, but public prose Skills are often neutral. A narrow, testable Skill with an external verifier is the missing combination.

### Slide 4 — M1 synthesis and gap

**On-slide content:** Two columns: “What is known” (package risk measurable; RAG/self-reflection can help; external feedback matters) and “What remains” (no causal comparison of prose Skill vs executable gate; no false-positive refusal measurement; no portable verification manifest).

**Speaker notes:** State the research question verbatim: at fixed model, prompt, temperature, and repair budget, what does deterministic verification add beyond instructions, RAG, and self-detection?

### Slide 5 — Reproducibility audit and M2 adaptation

**On-slide content:** Upstream pipeline: local HF `Models/` → code → two package queries + `pip` regex → registry. Bottleneck: 24–72 h GPU. Adaptation: OpenAI-compatible API, pinned 200-prompt 100/100 SO_LY/LLM_LY sample, model size × temperature factorial design.

**Speaker notes:** This is a controlled *adaptation*, not a claim to reproduce paper numbers exactly. The provider, date, model IDs, sampling seed, and registry snapshot are all written to configuration files.

### Slide 6 — M2 experiment and metrics

**On-slide content:** 2 sizes (7/8B, 70B+) × T {0, .7} × C0/C2. Extraction union: AST imports + pip regex + package elicitation. Outcomes: reference-level rate, prompt incidence, false-positive refusal rate, regeneration burden. Show placeholder: “Insert `summary.md` table after run.”

**Speaker notes:** Clarify the critical comparison: C2 asks the model whether each name is valid; deterministic scoring exposes whether it incorrectly rejects valid packages. We report denominators, not only percentages.

### Slide 7 — M3: Verify-Skill harness

**On-slide content:** Generate → Extract → Verify → Gate → Repair/Abstain. `SKILL.md` contains policy; hook uses versioned registry/PyPI cache; manifest records evidence. Highlight “LLM cannot override FAIL.”

**Speaker notes:** The contribution is modularity. We can change the model or prompt without changing the verifier, and we can audit every decision. The system can abstain instead of inventing a replacement after the repair budget is exhausted.

### Slide 8 — M4 ablations and success criteria

**On-slide content:** C0–C4 row, then A1 no prose, A2 no gate, A3 no repair, A4 source freshness, A5 extraction channel. Success: C4 lowest hallucination rate, no unacceptable valid-package refusal/utility loss, paired confidence intervals. End with timeline: M2 run → C1/C3/C4 implementation → paired ablation report.

**Speaker notes:** Avoid promising an outcome before running the experiment. The strongest claim we can make is conditional and falsifiable: if C4 beats C3, the executable gate—not merely the wording of `SKILL.md`—is responsible for the improvement.

## References

1. J. Spracklen et al. “We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs.” USENIX Security, 2025. [Paper](https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf), [repository](https://github.com/Spracks/PackageHallucination).
2. F. Liu et al. “Beyond Functional Correctness: Exploring Hallucinations in LLM-Generated Code.” arXiv:2404.00971 / TSE. [Paper](https://arxiv.org/abs/2404.00971).
3. X. Li et al. “SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks.” arXiv:2602.12670, 2026. [Paper](https://arxiv.org/abs/2602.12670).
4. T. Han et al. “SWE-Skills-Bench: Do Agent Skills Actually Help in Real-World Software Engineering?” arXiv:2603.15401, 2026. [Paper](https://arxiv.org/abs/2603.15401).
5. L. Pan et al. “Natural-Language Agent Harnesses.” arXiv:2603.25723, 2026. [Paper](https://arxiv.org/abs/2603.25723).
6. Z. Gou et al. “CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing.” ICLR, 2024. [Paper](https://arxiv.org/abs/2305.11738).
