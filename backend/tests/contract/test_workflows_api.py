"""T057 [US7] workflow CRUD and YAML/JSON round-trip contract tests."""

from __future__ import annotations

from copy import deepcopy


def test_workflow_create_update_export_import_json_round_trip(client):
    created = client.post(
        "/api/workflows",
        json={"name": "Editable loop", "template": "four_role_loop"},
    )
    assert created.status_code == 201, created.text
    workflow = created.json()

    fetched = client.get(f"/api/workflows/{workflow['id']}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json() == workflow

    edited = deepcopy(workflow)
    edited["name"] = "Edited loop"
    execution = next(node for node in edited["nodes"] if node["id"] == "execution")
    execution["config"].update(
        {
            "instructions": "Implement the approved plan.",
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "tools": ["shell", "filesystem"],
            "retry_limit": 2,
            "timeout_s": 300,
            "success_path": "validator",
            "failure_path": "planning",
        }
    )

    updated = client.put(f"/api/workflows/{workflow['id']}", json=edited)
    assert updated.status_code == 200, updated.text
    assert updated.json() == edited

    exported = client.post(f"/api/workflows/{workflow['id']}/export?format=json")
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("application/json")

    imported = client.post(
        "/api/workflows/import",
        json={"format": "json", "content": exported.text},
    )
    assert imported.status_code == 201, imported.text
    assert imported.json() == edited


def test_builtin_ui_workflow_can_be_fetched_and_saved_without_prior_creation(client):
    fetched = client.get("/api/workflows/default-four-role-loop")
    assert fetched.status_code == 200, fetched.text
    workflow = fetched.json()

    workflow["name"] = "Saved from the UI"
    saved = client.put("/api/workflows/default-four-role-loop", json=workflow)

    assert saved.status_code == 200, saved.text
    assert saved.json()["name"] == "Saved from the UI"


def test_workflow_yaml_export_import_reconstructs_identical_graph(client, workflow_id):
    original = client.get(f"/api/workflows/{workflow_id}")
    assert original.status_code == 200, original.text

    exported = client.post(f"/api/workflows/{workflow_id}/export?format=yaml")
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("application/yaml")
    assert "nodes:" in exported.text
    assert "edges:" in exported.text

    imported = client.post(
        "/api/workflows/import",
        json={"format": "yaml", "content": exported.text},
    )
    assert imported.status_code == 201, imported.text
    assert imported.json() == original.json()


def test_workflow_update_rejects_mismatched_id(client, workflow_id):
    workflow = client.get(f"/api/workflows/{workflow_id}").json()
    workflow["id"] = "different-id"

    response = client.put(f"/api/workflows/{workflow_id}", json=workflow)

    assert response.status_code == 409, response.text
    assert "error" in response.json()


def test_workflow_import_rejects_invalid_configuration(client):
    response = client.post(
        "/api/workflows/import",
        json={"format": "yaml", "content": "name: missing-required-fields"},
    )

    assert response.status_code == 422, response.text
    assert "error" in response.json()


def test_workflow_import_rejects_malformed_yaml(client):
    response = client.post(
        "/api/workflows/import",
        json={"format": "yaml", "content": "nodes: ["},
    )

    assert response.status_code == 422, response.text
    assert "error" in response.json()
