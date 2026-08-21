import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "dashboard" / "schema" / "repository-operations.schema.json"
FIXTURE_PATH = ROOT / "dashboard" / "fixtures" / "repository-operations.valid.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_repository_operations_schema_uses_json_schema_2020_12():
    schema = _load(SCHEMA_PATH)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "generatedAt",
        "sourceRevision",
        "runId",
        "repositories",
    }


def test_repository_operations_fixture_preserves_observed_facts_without_secrets():
    fixture = _load(FIXTURE_PATH)
    repository = fixture["repositories"][0]
    main_branch, candidate_branch = repository["branches"]

    assert repository["classification"]["source"] == "repository-topic"
    assert main_branch["isDefault"] is True
    assert main_branch["deletionCandidate"] is False
    assert main_branch["deleted"] is False
    assert candidate_branch["deletionCandidate"] is True
    assert candidate_branch["deletionConfirmed"] is False
    assert candidate_branch["deleted"] is False

    serialized = json.dumps(fixture).lower()
    for forbidden in ("token", "secret", "credential", "transcript"):
        assert forbidden not in serialized


def test_branch_contract_prevents_default_or_protected_branch_deletion():
    schema = _load(SCHEMA_PATH)
    branch_schema = schema["$defs"]["branch"]

    default_rule, protected_rule = branch_schema["allOf"]
    assert default_rule["then"]["properties"]["deleted"] == {"const": False}
    assert default_rule["then"]["properties"]["deletionCandidate"] == {"const": False}
    assert protected_rule["then"]["properties"]["deleted"] == {"const": False}
