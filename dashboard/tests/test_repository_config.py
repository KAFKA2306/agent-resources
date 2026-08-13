import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "repositories.json"
FIXTURE_PATH = ROOT / "fixtures" / "repositories.config.example.json"
ALLOWED_KEYS = {"owner", "exclude", "groupOverrides", "includeArchived"}
FORBIDDEN_UI_KEYS = {"x", "y", "color", "character", "characterName", "coordinates"}


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_config(config):
    if set(config) - ALLOWED_KEYS:
        raise ValueError("unknown config keys")
    if not isinstance(config.get("owner"), str) or not config["owner"]:
        raise ValueError("owner must be a non-empty string")
    if not isinstance(config.get("exclude"), list) or not all(
        isinstance(name, str) and name for name in config["exclude"]
    ):
        raise ValueError("exclude must be a list of repository names")
    if len(config["exclude"]) != len(set(config["exclude"])):
        raise ValueError("exclude entries must be unique")
    overrides = config.get("groupOverrides")
    if not isinstance(overrides, dict) or not all(
        isinstance(name, str) and name and isinstance(group, str) and group
        for name, group in overrides.items()
    ):
        raise ValueError("groupOverrides must map repository names to groups")
    if not isinstance(config.get("includeArchived"), bool):
        raise ValueError("includeArchived must be boolean")
    if FORBIDDEN_UI_KEYS.intersection(config):
        raise ValueError("UI-only keys are forbidden")


def is_public_candidate(repo, config):
    if repo.get("owner") != config["owner"]:
        return False
    if repo.get("visibility") != "public":
        return False
    if repo.get("name") in config["exclude"]:
        return False
    if repo.get("archived") and not config["includeArchived"]:
        return False
    return True


class RepositoryConfigTest(unittest.TestCase):
    def test_repository_config_is_minimal_and_valid(self):
        validate_config(load_json(CONFIG_PATH))
        validate_config(load_json(FIXTURE_PATH))

    def test_private_repository_is_never_a_public_candidate(self):
        config = load_json(FIXTURE_PATH)
        private_repo = {
            "owner": config["owner"],
            "name": "private-even-if-not-excluded",
            "visibility": "private",
            "archived": False,
        }
        self.assertFalse(is_public_candidate(private_repo, config))

    def test_public_active_repository_is_candidate(self):
        config = load_json(FIXTURE_PATH)
        public_repo = {
            "owner": config["owner"],
            "name": "public-active",
            "visibility": "public",
            "archived": False,
        }
        self.assertTrue(is_public_candidate(public_repo, config))

    def test_excluded_public_repository_is_not_candidate(self):
        config = load_json(FIXTURE_PATH)
        excluded_repo = {
            "owner": config["owner"],
            "name": "excluded-public",
            "visibility": "public",
            "archived": False,
        }
        self.assertFalse(is_public_candidate(excluded_repo, config))

    def test_archived_repository_policy_is_explicit(self):
        config = load_json(FIXTURE_PATH)
        archived_repo = {
            "owner": config["owner"],
            "name": "archived-public",
            "visibility": "public",
            "archived": True,
        }
        self.assertFalse(config["includeArchived"])
        self.assertFalse(is_public_candidate(archived_repo, config))

    def test_ui_keys_are_rejected(self):
        config = load_json(FIXTURE_PATH)
        config["color"] = "red"
        with self.assertRaises(ValueError):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
