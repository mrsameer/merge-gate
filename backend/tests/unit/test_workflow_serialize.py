"""T061 [US7] deterministic workflow YAML/JSON serialization tests."""

from mergegate.orchestrator.default_workflow import build_default_workflow
from mergegate.orchestrator.serialize import deserialize_workflow, serialize_workflow


def test_json_round_trip_preserves_the_complete_workflow():
    workflow = build_default_workflow("wf-roundtrip", name="Round trip")

    content = serialize_workflow(workflow, "json")
    reconstructed = deserialize_workflow(content, "json")

    assert reconstructed == workflow
    assert content.endswith("\n")


def test_yaml_round_trip_preserves_the_complete_workflow():
    workflow = build_default_workflow("wf-roundtrip", name="Round trip")

    content = serialize_workflow(workflow, "yaml")
    reconstructed = deserialize_workflow(content, "yaml")

    assert reconstructed == workflow
    assert "nodes:" in content
    assert "edges:" in content


def test_serialization_rejects_an_unknown_format():
    workflow = build_default_workflow("wf-roundtrip")

    try:
        serialize_workflow(workflow, "toml")
    except ValueError as exc:
        assert "toml" in str(exc)
    else:
        raise AssertionError("unknown serialization formats must be rejected")
