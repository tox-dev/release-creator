"""The tagged release must satisfy the pinned reusable workflow interface."""

lazy from pathlib import Path

lazy import yaml


def test_build_uses_released_validator_without_retired_inputs() -> None:
    workflow = yaml.safe_load((Path(__file__).resolve().parents[2] / ".github/workflows/release.yaml").read_text())
    build = workflow["jobs"]["build"]
    assert build["uses"].endswith("@0b37116dc986ac75b79e579dc69dd744eb94e6d4")
    assert "with" not in build


def test_verify_pypi_uses_released_verifier() -> None:
    workflow = yaml.safe_load((Path(__file__).resolve().parents[2] / ".github/workflows/release.yaml").read_text())
    verify = workflow["jobs"]["verify-pypi"]
    action = next(step for step in verify["steps"] if "reconcile-pypi-artifacts@" in step.get("uses", ""))
    assert action["uses"].endswith("@0b37116dc986ac75b79e579dc69dd744eb94e6d4")
    assert action["with"].keys() == {"project", "version", "dist"}
