from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "dashboard" / "AGENTS.md"


class DashboardAgentContractTest(unittest.TestCase):
    def test_low_context_contract_stays_bounded_and_actionable(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")

        self.assertLessEqual(
            len(text),
            3000,
            "dashboard/AGENTS.md must stay short enough for low-context agents",
        )

        required = (
            "config/public-links.json",
            "collectors/public_links.py",
            "../api/dashboard-live.js",
            "../docs/dashboard/live-overlay.js",
            "../vercel.json",
            "python scripts/validate_dashboard_contract.py",
            "uvx pre-commit run --all-files --hook-stage pre-commit",
            "uvx pre-commit run --all-files --hook-stage pre-push",
            "exact PR head",
            "Verify Dashboard Release",
            "UNVERIFIED",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
