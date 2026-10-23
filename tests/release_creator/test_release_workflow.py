"""The tagged release must satisfy the pinned reusable workflow interface."""

lazy from pathlib import Path

lazy import yaml


def test_build_uses_required_inputs_of_pinned_validator() -> None:
    workflow = yaml.safe_load((Path(__file__).resolve().parents[2] / ".github/workflows/release.yaml").read_text())
    build = workflow["jobs"]["build"]
    assert build["uses"].endswith("@801969505384f96d16882e224e98a74bffd09d21")
    assert {"changelog", "artifact-base-url"} <= build["with"].keys()
    assert build["with"]["local-tool-source"] is True


def test_verify_pypi_uses_tagged_tool_source() -> None:
    workflow = yaml.safe_load((Path(__file__).resolve().parents[2] / ".github/workflows/release.yaml").read_text())
    verify = workflow["jobs"]["verify-pypi"]
    action = next(step for step in verify["steps"] if "reconcile-pypi-artifacts@" in step.get("uses", ""))
    assert action["with"]["local-tool-source"] == "true"
