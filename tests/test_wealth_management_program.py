import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from wealth_management_program import (
    build_daily_program,
    generate_report,
    load_program_config,
    rank_features,
)


class WealthManagementProgramTests(unittest.TestCase):
    def test_generates_combined_program_for_matching_repos(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            bauer = root / "Bauer-Strategy"
            bauer.mkdir()
            (bauer / ".git").mkdir()
            (bauer / "README.md").write_text(
                "\n".join(
                    [
                        "# Bauer Strategy",
                        "- Risk allocation engine",
                        "- Real-time trading signal alerting",
                    ]
                ),
                encoding="utf-8",
            )

            raynman = root / "Raynman-Precision-Tech"
            raynman.mkdir()
            (raynman / ".git").mkdir()
            (raynman / "README.md").write_text(
                "\n".join(
                    [
                        "# Raynman Precision",
                        "- Portfolio analysis automation",
                        "- Execution strategy optimizer",
                    ]
                ),
                encoding="utf-8",
            )

            ignored = root / "OtherRepo"
            ignored.mkdir()
            (ignored / ".git").mkdir()
            (ignored / "README.md").write_text("- unrelated note", encoding="utf-8")

            report = generate_report(root, ["Bauer", "Raynman"])

            self.assertIn("- Bauer-Strategy", report)
            self.assertIn("- Raynman-Precision-Tech", report)
            self.assertNotIn("- OtherRepo", report)
            self.assertIn("## Consolidated Feature Set", report)
            self.assertIn("## Ensemble Ranking Diagnostics", report)
            self.assertIn("## Extraction Quality Backtest", report)
            self.assertIn("### Pre-Market Planning", report)
            self.assertIn("### Market-Hours Monitoring", report)
            self.assertIn("### Post-Market Review", report)

    def test_build_daily_program_categorizes_features(self) -> None:
        daily_program = build_daily_program(
            [
                "Risk allocation monitor",
                "Live trading signal alert",
                "Weekly analysis automation summary",
                "Risk-aware execution strategy",
            ]
        )

        self.assertIn("Risk allocation monitor", daily_program["Pre-Market Planning"])
        self.assertIn("Live trading signal alert", daily_program["Market-Hours Monitoring"])
        self.assertIn("Weekly analysis automation summary", daily_program["Post-Market Review"])
        self.assertIn("Risk-aware execution strategy", daily_program["Pre-Market Planning"])
        self.assertIn("Risk-aware execution strategy", daily_program["Market-Hours Monitoring"])

    def test_config_precedence_env_over_user_file(self) -> None:
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "max_features_per_section": 5,
                        "min_feature_length": 8,
                        "ranking_weights": {"keyword_hits": 2.0},
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {
                    "WMP_MAX_FEATURES_PER_SECTION": "2",
                    "WMP_WEIGHT_KEYWORD_HITS": "3.0",
                },
                clear=False,
            ):
                config = load_program_config(config_path)

            self.assertEqual(config.max_features_per_section, 2)
            self.assertEqual(config.min_feature_length, 8)
            self.assertEqual(config.ranking_weights.keyword_hits, 3.0)

    def test_rank_features_prioritizes_keyword_rich_feature(self) -> None:
        ranked = rank_features(
            [
                "Weekly analysis note",
                "Risk allocation trading execution signal alert",
            ]
        )
        self.assertEqual(ranked[0].feature, "Risk allocation trading execution signal alert")
        self.assertGreater(ranked[0].score, ranked[1].score)


if __name__ == "__main__":
    unittest.main()
