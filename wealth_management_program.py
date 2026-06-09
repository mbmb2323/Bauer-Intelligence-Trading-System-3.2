#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_FEATURE_KEYWORDS = (
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
DEFAULT_PRE_MARKET_KEYWORDS = ("risk", "allocation", "portfolio")
DEFAULT_MARKET_HOURS_KEYWORDS = ("execution", "signal", "alert", "trading")


@dataclass(frozen=True)
class RankingWeights:
    keyword_hits: float = 1.0
    category_hits: float = 0.75
    length_bonus: float = 0.25


@dataclass(frozen=True)
class ProgramConfig:
    feature_keywords: tuple[str, ...] = DEFAULT_FEATURE_KEYWORDS
    pre_market_keywords: tuple[str, ...] = DEFAULT_PRE_MARKET_KEYWORDS
    market_hours_keywords: tuple[str, ...] = DEFAULT_MARKET_HOURS_KEYWORDS
    max_features_per_section: int = 10
    min_feature_length: int = 5
    include_quality_metrics: bool = True
    ranking_weights: RankingWeights = RankingWeights()


@dataclass(frozen=True)
class FeatureScore:
    feature: str
    score: float
    keyword_hits: int
    category_hits: int
    length_bonus: float


def _split_csv_env(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    parts = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    return parts or None


def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered in {"1", "true", "yes", "y", "on"}


def _load_user_config(config_path: Path | None) -> dict[str, Any]:
    if config_path is None or not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def load_program_config(config_path: Path | None = None) -> ProgramConfig:
    defaults: dict[str, Any] = {
        "feature_keywords": DEFAULT_FEATURE_KEYWORDS,
        "pre_market_keywords": DEFAULT_PRE_MARKET_KEYWORDS,
        "market_hours_keywords": DEFAULT_MARKET_HOURS_KEYWORDS,
        "max_features_per_section": 10,
        "min_feature_length": 5,
        "include_quality_metrics": True,
        "ranking_weights": {
            "keyword_hits": 1.0,
            "category_hits": 0.75,
            "length_bonus": 0.25,
        },
    }

    user = _load_user_config(config_path)

    merged: dict[str, Any] = defaults.copy()
    for key in (
        "feature_keywords",
        "pre_market_keywords",
        "market_hours_keywords",
        "max_features_per_section",
        "min_feature_length",
        "include_quality_metrics",
    ):
        if key in user:
            merged[key] = user[key]

    user_weights = user.get("ranking_weights")
    if isinstance(user_weights, dict):
        merged["ranking_weights"] = {**merged["ranking_weights"], **user_weights}

    env_feature_keywords = _split_csv_env(os.getenv("WMP_FEATURE_KEYWORDS"))
    env_pre_market_keywords = _split_csv_env(os.getenv("WMP_PRE_MARKET_KEYWORDS"))
    env_market_hours_keywords = _split_csv_env(os.getenv("WMP_MARKET_HOURS_KEYWORDS"))
    if env_feature_keywords is not None:
        merged["feature_keywords"] = env_feature_keywords
    if env_pre_market_keywords is not None:
        merged["pre_market_keywords"] = env_pre_market_keywords
    if env_market_hours_keywords is not None:
        merged["market_hours_keywords"] = env_market_hours_keywords

    if os.getenv("WMP_MAX_FEATURES_PER_SECTION") is not None:
        try:
            merged["max_features_per_section"] = int(os.getenv("WMP_MAX_FEATURES_PER_SECTION", "10"))
        except ValueError:
            pass

    if os.getenv("WMP_MIN_FEATURE_LENGTH") is not None:
        try:
            merged["min_feature_length"] = int(os.getenv("WMP_MIN_FEATURE_LENGTH", "5"))
        except ValueError:
            pass

    if os.getenv("WMP_INCLUDE_QUALITY_METRICS") is not None:
        merged["include_quality_metrics"] = _parse_bool(os.getenv("WMP_INCLUDE_QUALITY_METRICS", "true"))

    weight_overrides = {
        "keyword_hits": os.getenv("WMP_WEIGHT_KEYWORD_HITS"),
        "category_hits": os.getenv("WMP_WEIGHT_CATEGORY_HITS"),
        "length_bonus": os.getenv("WMP_WEIGHT_LENGTH_BONUS"),
    }
    for key, value in weight_overrides.items():
        if value is None:
            continue
        try:
            merged["ranking_weights"][key] = float(value)
        except ValueError:
            continue

    feature_keywords = tuple(str(item).strip().lower() for item in merged["feature_keywords"] if str(item).strip())
    pre_market_keywords = tuple(str(item).strip().lower() for item in merged["pre_market_keywords"] if str(item).strip())
    market_hours_keywords = tuple(str(item).strip().lower() for item in merged["market_hours_keywords"] if str(item).strip())

    max_features_per_section = merged["max_features_per_section"]
    min_feature_length = merged["min_feature_length"]

    if not isinstance(max_features_per_section, int) or max_features_per_section <= 0:
        max_features_per_section = 10
    if not isinstance(min_feature_length, int) or min_feature_length < 1:
        min_feature_length = 5

    include_quality_metrics = bool(merged["include_quality_metrics"])

    ranking_weights_dict = merged["ranking_weights"]
    ranking_weights = RankingWeights(
        keyword_hits=float(ranking_weights_dict.get("keyword_hits", 1.0)),
        category_hits=float(ranking_weights_dict.get("category_hits", 0.75)),
        length_bonus=float(ranking_weights_dict.get("length_bonus", 0.25)),
    )

    return ProgramConfig(
        feature_keywords=feature_keywords or DEFAULT_FEATURE_KEYWORDS,
        pre_market_keywords=pre_market_keywords or DEFAULT_PRE_MARKET_KEYWORDS,
        market_hours_keywords=market_hours_keywords or DEFAULT_MARKET_HOURS_KEYWORDS,
        max_features_per_section=max_features_per_section,
        min_feature_length=min_feature_length,
        include_quality_metrics=include_quality_metrics,
        ranking_weights=ranking_weights,
    )


def contains_code_block_or_path_separator(text: str) -> bool:
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


def _normalize_list_item(line: str) -> str:
    stripped = line.strip()
    return re.sub(r"^[\-\*\d\.\)\s]+", "", stripped).strip()


def _is_markdown_list_item(line: str) -> bool:
    return bool(re.match(r"^\s*([\-\*]|\d+[.)])\s+", line))


def extract_candidate_features(text: str, config: ProgramConfig | None = None) -> list[str]:
    cfg = config or load_program_config()
    features: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or not _is_markdown_list_item(line):
            continue
        normalized = _normalize_list_item(line)
        if len(normalized) < cfg.min_feature_length:
            continue
        if contains_code_block_or_path_separator(normalized):
            continue
        lowered = normalized.lower()
        if not any(keyword in lowered for keyword in cfg.feature_keywords):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        features.append(normalized)
    return features


def collect_repo_features(repo_path: Path, config: ProgramConfig | None = None) -> list[str]:
    cfg = config or load_program_config()
    features: list[str] = []
    readme_files = sorted(repo_path.glob("README*.md"))
    for readme in readme_files:
        try:
            content = readme.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        features.extend(extract_candidate_features(content, cfg))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in features:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def rank_features(features: list[str], config: ProgramConfig | None = None) -> list[FeatureScore]:
    cfg = config or load_program_config()
    ranked: list[FeatureScore] = []
    for feature in features:
        lowered = feature.lower()
        keyword_hits = sum(1 for keyword in cfg.feature_keywords if keyword in lowered)
        category_hits = sum(1 for keyword in cfg.pre_market_keywords if keyword in lowered) + sum(
            1 for keyword in cfg.market_hours_keywords if keyword in lowered
        )
        length_bonus = min(len(feature) / 80.0, 1.0)
        score = (
            keyword_hits * cfg.ranking_weights.keyword_hits
            + category_hits * cfg.ranking_weights.category_hits
            + length_bonus * cfg.ranking_weights.length_bonus
        )
        ranked.append(
            FeatureScore(
                feature=feature,
                score=score,
                keyword_hits=keyword_hits,
                category_hits=category_hits,
                length_bonus=length_bonus,
            )
        )
    return sorted(ranked, key=lambda item: (-item.score, item.feature.lower()))


def build_daily_program(features: list[str], config: ProgramConfig | None = None) -> dict[str, list[str]]:
    cfg = config or load_program_config()
    pre_market: list[str] = []
    market_hours: list[str] = []
    post_market: list[str] = []
    for feature in features:
        lowered = feature.lower()
        pre_market_match = any(keyword in lowered for keyword in cfg.pre_market_keywords)
        market_hours_match = any(keyword in lowered for keyword in cfg.market_hours_keywords)
        if pre_market_match:
            pre_market.append(feature)
        if market_hours_match:
            market_hours.append(feature)
        if not pre_market_match and not market_hours_match:
            post_market.append(feature)
    return {
        "Pre-Market Planning": pre_market[: cfg.max_features_per_section],
        "Market-Hours Monitoring": market_hours[: cfg.max_features_per_section],
        "Post-Market Review": post_market[: cfg.max_features_per_section],
    }


def evaluate_extraction_quality(
    consolidated: list[str],
    daily_program: dict[str, list[str]],
    ranked_features: list[FeatureScore],
) -> dict[str, float]:
    total_features = len(consolidated)
    categorized_features: set[str] = set()
    for values in daily_program.values():
        categorized_features.update(value.lower() for value in values)

    coverage = (len(categorized_features) / total_features) if total_features else 0.0
    avg_score = (sum(item.score for item in ranked_features) / total_features) if total_features else 0.0
    top_score = ranked_features[0].score if ranked_features else 0.0
    bottom_score = ranked_features[-1].score if ranked_features else 0.0

    return {
        "total_features": float(total_features),
        "categorized_coverage": coverage,
        "average_ensemble_score": avg_score,
        "top_ensemble_score": top_score,
        "bottom_ensemble_score": bottom_score,
    }


def _consolidate_features(repo_features: dict[str, list[str]]) -> list[str]:
    consolidated: list[str] = []
    seen: set[str] = set()
    for features in repo_features.values():
        for feature in features:
            lowered = feature.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            consolidated.append(feature)
    return consolidated


def generate_report(scan_root: Path, repo_name_contains: list[str], config: ProgramConfig | None = None) -> str:
    cfg = config or load_program_config()
    repos = find_git_repositories(scan_root, repo_name_contains)
    repo_features: dict[str, list[str]] = {}
    for repo in repos:
        repo_features[repo.name] = collect_repo_features(repo, cfg)

    consolidated = _consolidate_features(repo_features)
    ranked_features = rank_features(consolidated, cfg)
    daily_program = build_daily_program([item.feature for item in ranked_features], cfg)
    quality = evaluate_extraction_quality(consolidated, daily_program, ranked_features)

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

    lines.append("## Ensemble Ranking Diagnostics")
    if ranked_features:
        for item in ranked_features[: cfg.max_features_per_section]:
            lines.append(
                "- "
                f"{item.feature} "
                f"(score={item.score:.2f}, keywords={item.keyword_hits}, categories={item.category_hits}, length_bonus={item.length_bonus:.2f})"
            )
    else:
        lines.append("- No ranking diagnostics available")
    lines.append("")

    lines.append("## Daily Operating Program")
    for section, items in daily_program.items():
        lines.append(f"### {section}")
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- Use discretionary review until additional features are extracted")
    lines.append("")

    if cfg.include_quality_metrics:
        lines.append("## Extraction Quality Backtest")
        lines.append(f"- Total Features: {int(quality['total_features'])}")
        lines.append(f"- Categorized Coverage: {quality['categorized_coverage']:.2%}")
        lines.append(f"- Average Ensemble Score: {quality['average_ensemble_score']:.2f}")
        lines.append(f"- Top Ensemble Score: {quality['top_ensemble_score']:.2f}")
        lines.append(f"- Bottom Ensemble Score: {quality['bottom_ensemble_score']:.2f}")
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
        default=Path.cwd(),
        help="Root directory containing repositories to scan",
    )
    parser.add_argument(
        "--repo-name-contains",
        action="append",
        default=[],
        help="Optional repository name filter (can be repeated)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional JSON config file (precedence: env > file > defaults)",
    )
    parser.add_argument(
        "--no-quality-metrics",
        action="store_true",
        help="Disable extraction quality backtest section in report output",
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
    config = load_program_config(args.config)
    if args.no_quality_metrics:
        config = ProgramConfig(
            feature_keywords=config.feature_keywords,
            pre_market_keywords=config.pre_market_keywords,
            market_hours_keywords=config.market_hours_keywords,
            max_features_per_section=config.max_features_per_section,
            min_feature_length=config.min_feature_length,
            include_quality_metrics=False,
            ranking_weights=config.ranking_weights,
        )
    report = generate_report(args.scan_root, args.repo_name_contains, config)
    args.output.write_text(report, encoding="utf-8")
    print(f"Report generated: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
