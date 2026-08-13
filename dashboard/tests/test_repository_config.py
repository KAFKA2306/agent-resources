import json
import unittest
from pathlib import Path

from dashboard.collectors.repositories import validate_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "repositories.json"
FIXTURE_PATH = ROOT / "fixtures" / "repositories.config.example.json"


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


class RepositoryConfigTest(unittest.TestCase):
    def test_repository_config_is_owner_only(self):
        config = load_json(CONFIG_PATH)
        fixture = load_json(FIXTURE_PATH)
        self.assertEqual(set(config), {"owner"})
        self.assertEqual(set(fixture), {"owner"})
        validate_config(config)
        validate_config(fixture)

    def test_manual_repository_exclusion_is_forbidden(self):
        config = load_json(FIXTURE_PATH)
        config["exclude"] = ["some-repository"]
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_manual_group_override_is_forbidden(self):
        config = load_json(FIXTURE_PATH)
        config["groupOverrides"] = {"some-repository": "core"}
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_archived_inclusion_switch_is_forbidden(self):
        config = load_json(FIXTURE_PATH)
        config["includeArchived"] = True
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_ui_keys_are_forbidden(self):
        config = load_json(FIXTURE_PATH)
        config["color"] = "red"
        with self.assertRaises(ValueError):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
