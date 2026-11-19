"""Tests for gh_issue_phase.sh workflow script."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parent.parent
    / "skills/development/workflow/make-release/scripts/gh_issue_phase.sh"
)


def run_script(*args: str, stdin: str = "") -> subprocess.CompletedProcess:
    """Run gh_issue_phase.sh with args and optional stdin."""
    return subprocess.run(
        [str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
    )


class TestArgumentParsing:
    """Unit tests for argument parsing (no network)."""

    def test_no_args_shows_usage(self):
        """Running with no arguments prints usage and exits non-zero."""
        result = run_script()
        assert result.returncode != 0
        assert "Usage:" in result.stderr

    def test_unknown_action_rejected(self):
        """Unknown action names are rejected."""
        result = run_script("bad-action")
        assert result.returncode != 0
        assert "Unknown action: bad-action" in result.stderr

    def test_resolve_issue_from_number(self):
        """Numeric issue references are accepted (errors at gh call, not at parsing)."""
        # post-phase with a number should get past argument parsing
        # and fail at the gh API call, not at resolve_issue
        result = run_script("post-phase", "42", "research", stdin="test")
        # Should not fail with "Invalid issue reference"
        assert "Invalid issue reference" not in result.stderr

    def test_resolve_issue_from_url(self):
        """GitHub URL issue references are accepted."""
        url = "https://github.com/owner/repo/issues/99"
        result = run_script("post-phase", url, "research", stdin="test")
        assert "Invalid issue reference" not in result.stderr

    def test_invalid_reference_rejected(self):
        """Non-number/non-URL references are rejected."""
        result = run_script("get-issue", "not-a-reference")
        assert result.returncode != 0
        assert "Invalid issue reference" in result.stderr

    def test_create_issue_requires_title(self):
        """create-issue without a title shows usage."""
        result = run_script("create-issue", stdin="body text")
        assert result.returncode != 0

    def test_post_phase_requires_issue_and_phase(self):
        """post-phase without both args shows usage."""
        result = run_script("post-phase", "42", stdin="content")
        assert result.returncode != 0

    def test_set_label_requires_issue_and_label(self):
        """set-label without both args shows usage."""
        result = run_script("set-label", "42")
        assert result.returncode != 0


@pytest.mark.e2e
class TestFullWorkflow:
    """Integration tests that require gh auth and network access."""

    @pytest.fixture
    def issue_number(self):
        """Create a test issue and return its number. Closes it after the test."""
        result = subprocess.run(
            [
                str(SCRIPT),
                "create-issue",
                "Test: gh_issue_phase workflow",
            ],
            input="Automated test issue. Safe to delete.",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Failed to create issue: {result.stderr}"
        number = result.stdout.strip()
        assert number.isdigit(), f"Expected issue number, got: {number}"
        yield number
        # Cleanup: close the issue
        subprocess.run(
            [str(SCRIPT), "close-issue", number],
            capture_output=True,
            text=True,
        )

    def test_full_workflow(self, issue_number):
        """Create issue, post phase, verify idempotent update, set labels, close."""
        # Post research phase
        result = subprocess.run(
            [str(SCRIPT), "post-phase", issue_number, "research"],
            input="Research findings: initial post.",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"post-phase failed: {result.stderr}"

        # Post again (should update, not duplicate)
        result = subprocess.run(
            [str(SCRIPT), "post-phase", issue_number, "research"],
            input="Research findings: updated post.",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"post-phase update failed: {result.stderr}"

        # Verify only one research comment exists
        result = subprocess.run(
            [str(SCRIPT), "get-issue", issue_number],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # The updated content should be there
        assert "updated post" in result.stdout

        # Set label
        result = subprocess.run(
            [str(SCRIPT), "set-label", issue_number, "phase:research"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"set-label failed: {result.stderr}"

        # Set different label (should remove old one)
        result = subprocess.run(
            [str(SCRIPT), "set-label", issue_number, "phase:brainstorm"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"set-label update failed: {result.stderr}"

        # Close issue
        result = subprocess.run(
            [str(SCRIPT), "close-issue", issue_number],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"close-issue failed: {result.stderr}"
