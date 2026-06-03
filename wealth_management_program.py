#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

FEATURE_KEYWORDS = (
    "feature",
    "trading",
    "strategy",
    "signal",
    "risk",
    "portfolio",
    "allocation",
    "alert",
    "analysis",
    "automation",
    "prediction",
    "execution",
)
MAX_FEATURES_PER_SECTION = 10


def appears_to_be_code_or_path(text: str) -> bool:
    return "```" in text or "/" in text or "\\" in text


def find_git_repositories(scan_root: Path, repo_name_contains: list[str]) -> list[Path]:
    repos: list[Path] = []
    filters = [value.lower() for value in repo_name_contains]
    for child in sorted(scan_root.iterdir()):
        if not child.is_dir():
            continue
        if not (child / ".git").exists():
            continue
        if filters and not any(value in child.name.lower() for value in filters):
            continue
        repos.append(child)
    return repos


def extract_candidate_features(text: str) -> list[str]:
    features: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if not re.match(r"^\s*([\-\*]|\d+[.)])\s+", line):
            continue
        normalized = re.sub(r"^[\-\*\d\.\)\s]+", "", stripped).strip()
        if len(normalized) < 5:
            continue
        if appears_to_be_code_or_path(normalized):
            continue
        lowered = normalized.lower()
        if not any(keyword in lowered for keyword in FEATURE_KEYWORDS):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        features.append(normalized)
    return features


def collect_repo_features(repo_path: Path) -> list[str]:
    features: list[str] = []
    readme_files = sorted(repo_path.glob("README*.md"))
    for readme in readme_files:
        try:
            content = readme.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        features.extend(extract_candidate_features(content))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in features:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def build_daily_program(features: list[str]) -> dict[str, list[str]]:
    pre_market: list[str] = []
    market_hours: list[str] = []
    post_market: list[str] = []
    for feature in features:
        lowered = feature.lower()
        if "risk" in lowered or "allocation" in lowered or "portfolio" in lowered:
            pre_market.append(feature)
        elif "execution" in lowered or "signal" in lowered or "alert" in lowered or "trading" in lowered:
            market_hours.append(feature)
        else:
            post_market.append(feature)
    return {
        "Pre-Market Planning": pre_market[:MAX_FEATURES_PER_SECTION],
        "Market-Hours Monitoring": market_hours[:MAX_FEATURES_PER_SECTION],
        "Post-Market Review": post_market[:MAX_FEATURES_PER_SECTION],
    }


def generate_report(scan_root: Path, repo_name_contains: list[str]) -> str:
    repos = find_git_repositories(scan_root, repo_name_contains)
    repo_features: dict[str, list[str]] = {}
    for repo in repos:
        repo_features[repo.name] = collect_repo_features(repo)

    consolidated: list[str] = []
    seen: set[str] = set()
    for features in repo_features.values():
        for feature in features:
            lowered = feature.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            consolidated.append(feature)

    daily_program = build_daily_program(consolidated)

    lines: list[str] = ["# Final Wealth Management Program", ""]
    lines.append("## Repositories Scanned")
    if repo_features:
        lines.extend(f"- {repo}" for repo in repo_features.keys())
    else:
        lines.append("- No matching repositories found")
    lines.append("")

    lines.append("## Extracted Features by Repository")
    if not repo_features:
        lines.append("- No repository features available")
    else:
        for repo, features in repo_features.items():
            lines.append(f"### {repo}")
            if features:
                lines.extend(f"- {feature}" for feature in features)
            else:
                lines.append("- No qualifying features detected in README files")
    lines.append("")

    lines.append("## Consolidated Feature Set")
    if consolidated:
        lines.extend(f"- {feature}" for feature in consolidated)
    else:
        lines.append("- No consolidated features available")
    lines.append("")

    lines.append("## Daily Operating Program")
    for section, items in daily_program.items():
        lines.append(f"### {section}")
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- Use discretionary review until additional features are extracted")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan local Git repositories and generate a combined wealth management "
            "program report from extracted README features."
        )
    )
    parser.add_argument(
        "--scan-root",
        type=Path,
        default=Path.cwd().parent,
        help="Root directory containing repositories to scan",
    )
    parser.add_argument(
        "--repo-name-contains",
        action="append",
        default=[],
        help="Optional repository name filter (can be repeated)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd() / "final_wealth_management_program.md",
        help="Output Markdown file path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = generate_report(args.scan_root, args.repo_name_contains)
    args.output.write_text(report, encoding="utf-8")
    print(f"Report generated: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
