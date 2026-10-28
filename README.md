# Verifying Package Claims in LLM-Generated Code

**Final Year NLP Project**

> *Make package validity an externally verified runtime contract, not a self-reported model belief.*

## Problem

Code-generating LLMs frequently hallucinate package names — recommending or importing
dependencies that don't exist on PyPI. An attacker can register these plausible missing
names, turning a benign recommendation into a supply-chain attack vector. The anchor study
(Spracklen et al., USENIX Security 2025) found **19.7%** of recommended packages were
hallucinated across 16 models and 576,000 generations.

## Research Question

> Holding model, prompt, decoding, and regeneration budget fixed, does executable external
> package verification reduce invalid dependency references more than RAG, LLM self-detection,
> and prose-only guidance — without an unacceptable valid-package refusal cost?

## Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| **M1** | Literature survey and reproducibility audit |  Done |
| **M2** | API-based baseline reproduction (C0, C2) | Done |
| **M3** | Verify-Skill agent harness (C3, C4) | Planned |
| **M4** | Ablation study and final analysis | Planned |

## Project Structure

```
NLP_Project/
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── setup.py                    # Package installation
├── .gitignore                  # Git ignore rules
│
├── src/                        # Source code
│   ├── __init__.py
│   ├── reproduce_m2_baseline.py  # M2 API-based reproduction script
│   ├── extraction/             # Package claim extraction (AST, regex, elicitation)
│   │   └── __init__.py
│   ├── verification/           # Registry lookup & deterministic verification gate
│   │   └── __init__.py
│   ├── harness/                # C0–C4 agent harness orchestration
│   │   └── __init__.py
│   ├── skills/                 # SKILL.md and skill-related logic
│   │   └── __init__.py
│   └── utils/                  # Shared utilities (API client, normalization, etc.)
│       └── __init__.py
│
├── data/                       # Data (not committed to git; see .gitignore)
│   ├── raw/                    # Upstream anchor repo data (SO_LY, LLM_LY, etc.)
│   ├── processed/              # Sampled/cleaned prompt subsets
│   └── registry_snapshots/     # Versioned PyPI snapshots & stdlib lists
│
├── configs/                    # Experiment configuration files
│   └── example_config.json     # Template run configuration
│
├── experiments/                # Per-experiment scripts and configs
│   ├── m2_baseline/            # M2 baseline runs
│   ├── m3_harness/             # M3 verify-skill implementation
│   └── m4_ablations/           # M4 ablation experiments (A1–A8)
│
├── results/                    # Experiment outputs (not committed; see .gitignore)
│   ├── tables/                 # Summary CSVs and markdown tables
│   ├── figures/                # Generated plots and charts
│   └── logs/                   # Run logs and verification manifests
│
├── reports/                    # Written deliverables
│   ├── latex/                  # LaTeX source for reports
│   │   └── M1_M2_Report.tex
│   └── slides/                 # Presentation decks
│
├── tests/                      # Unit and integration tests
│
├── notebooks/                  # Jupyter notebooks for exploration/analysis
│
├── scripts/                    # One-off helper scripts (data prep, plotting, etc.)
│
└── docs/                       # Documentation and references
    └── M1_M2_SUBMISSION.md     # Full M1/M2 submission document
```

## Experimental Conditions

| Condition | Intervention | What it tests |
|-----------|-------------|---------------|
| **C0** | Vanilla code generation | Base prevalence |
| **C1** | Static RAG from anchor repo | Retrieved package descriptions |
| **C2** | LLM self-detection/refinement | Model judging its own names |
| **C3** | SKILL.md prose only (no enforcement) | Instruction-following effect |
| **C4** | SKILL.md + deterministic verifier + gate | Executable external enforcement |

## Quick Start

```bash
# 1. Clone and set up
git clone <repo-url>
cd NLP_Project
pip install -r requirements.txt

# 2. Clone the anchor repository
git clone https://github.com/Spracks/PackageHallucination data/raw/PackageHallucination

# 3. Set API key and run M2 baseline
export OPENAI_API_KEY='...'
python src/reproduce_m2_baseline.py \
  --repo-root data/raw/PackageHallucination \
  --base-url https://openrouter.ai/api/v1 \
  --models small=provider/small-8b-instruct large=provider/large-70b-instruct
```

## References

1. Spracklen et al. "We Have a Package for You!" USENIX Security 2025. [Paper](https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf)
2. Liu et al. "Beyond Functional Correctness: Exploring Hallucinations in LLM-Generated Code." [arXiv:2404.00971](https://arxiv.org/abs/2404.00971)
3. Li et al. "SkillsBench." [arXiv:2602.12670](https://arxiv.org/abs/2602.12670)
4. Han et al. "SWE-Skills-Bench." [arXiv:2603.15401](https://arxiv.org/abs/2603.15401)
5. Pan et al. "Natural-Language Agent Harnesses." [arXiv:2603.25723](https://arxiv.org/abs/2603.25723)
6. Gou et al. "CRITIC." ICLR 2024. [arXiv:2305.11738](https://arxiv.org/abs/2305.11738)
