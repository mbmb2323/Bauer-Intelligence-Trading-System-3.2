# Bauer Intelligence Trading System 3.2

A Python CLI tool that scans local Git repositories, extracts wealth-management and trading-related features from their README files, and generates a consolidated daily operating program as a Markdown report.

---

## Overview

`wealth_management_program.py` searches a root directory for local Git repositories (optionally filtered by name), reads each repository's `README.md` files, and extracts bullet-point items that reference trading, risk, strategy, and related concepts. It consolidates those features across all matching repositories and produces a structured report organized into a three-phase daily routine.

---

## Requirements

- Python 3.8 or later
- Standard library only — no third-party dependencies

---

## Usage

```bash
python wealth_management_program.py \
  [--scan-root DIR] \
  [--repo-name-contains FILTER] ... \
  [--config FILE.json] \
  [--no-quality-metrics] \
  [--output FILE]
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `--scan-root DIR` | Current working directory | Root directory to search for Git repositories |
| `--repo-name-contains FILTER` | *(none — all repos matched)* | Filter repos whose names contain this string (case-insensitive). Can be repeated to allow multiple filters. |
| `--config FILE.json` | *(none)* | Optional JSON configuration file. |
| `--no-quality-metrics` | `false` | Disable quality backtest metrics section in output. |
| `--output FILE` | `./final_wealth_management_program.md` | Output Markdown file path |

### Example

```bash
python wealth_management_program.py \
  --scan-root /path/to/your/repos \
  --repo-name-contains Bauer \
  --repo-name-contains Raynman \
  --output ./final_wealth_management_program.md
```

This scans all subdirectories of `/path/to/your/repos` that contain a `.git` folder and whose names include `Bauer` or `Raynman` (case-insensitive). The report is written to `./final_wealth_management_program.md`.

---

## Output Format

The generated Markdown file contains six sections:

1. **Repositories Scanned** — a list of matched repository names.
2. **Extracted Features by Repository** — bullet-point features pulled from each repository's `README.md` files.
3. **Consolidated Feature Set** — a deduplicated union of all per-repository features.
4. **Ensemble Ranking Diagnostics** — ranked feature list with score and component breakdown.
5. **Daily Operating Program** — features organized into three time-of-day sections (up to 10 items each):
   - **Pre-Market Planning** — items containing: `risk`, `allocation`, or `portfolio`
   - **Market-Hours Monitoring** — items containing: `execution`, `signal`, `alert`, or `trading`
   - **Post-Market Review** — remaining items not matched by either category above
6. **Extraction Quality Backtest** *(optional)* — score and coverage metrics for extraction/ranking reliability.

> Note: A single feature can appear in both Pre-Market Planning and Market-Hours Monitoring if it matches keywords from both categories.

---

## Feature Extraction Logic

Features are extracted from bullet points in README files (lines beginning with `-`, `*`, or a numbered list marker such as `1.` or `1)`). A line is included as a feature only when **all** of the following are true:

- The text (after stripping the list marker) is at least **5 characters** long.
- It does **not** contain code-block markers (`` ``` ``) or file path separators (`/`, `\`).
- It contains at least one of these keywords (case-insensitive):
  `feature`, `trading`, `strategy`, `signal`, `risk`, `portfolio`, `allocation`, `alert`, `analysis`, `automation`, `prediction`, `execution`

Duplicate lines (compared case-insensitively) are discarded within and across repositories.

---

## Configuration Precedence

Configuration is loaded in deterministic order:

1. **Defaults** (built-in)
2. **User config file** passed via `--config`
3. **Environment variables** (highest precedence)

Supported environment overrides include:

- `WMP_FEATURE_KEYWORDS`
- `WMP_PRE_MARKET_KEYWORDS`
- `WMP_MARKET_HOURS_KEYWORDS`
- `WMP_MAX_FEATURES_PER_SECTION`
- `WMP_MIN_FEATURE_LENGTH`
- `WMP_INCLUDE_QUALITY_METRICS`
- `WMP_WEIGHT_KEYWORD_HITS`
- `WMP_WEIGHT_CATEGORY_HITS`
- `WMP_WEIGHT_LENGTH_BONUS`

Keyword environment values use comma-separated lists.

---

## Running the Tests

Using `pytest`:
```bash
python -m pytest tests/
```

Using the standard library:
```bash
python -m unittest discover -s tests -v
```

The test suite (`tests/test_wealth_management_program.py`) covers:

- **Combined report generation** — verifies that only repositories matching the name filter are included, and that the output contains all expected sections.
- **Daily program categorization** — verifies that features are correctly assigned to Pre-Market Planning, Market-Hours Monitoring, and Post-Market Review based on their keywords.

---

## Project Structure

```
.
├── wealth_management_program.py   # Main CLI script
├── tests/
│   └── test_wealth_management_program.py  # Unit tests
└── README.md
```
