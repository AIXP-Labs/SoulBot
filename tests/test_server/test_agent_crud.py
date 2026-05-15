"""Tests for Agent CRUD endpoints (GET /templates, POST /agents/create, DELETE /agents/{name})."""

import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from soulbot.server.api_server import create_app


@pytest.fixture
def agents_dir(tmp_path: Path):
    """Create a minimal agents directory with one pre-existing agent."""
    agent_dir = tmp_path / "existing_agent"
    agent_dir.mkdir()
    (agent_dir / "agent.py").write_text(
        'from soulbot.agents import LlmAgent\n'
        'root_agent = LlmAgent(name="existing_agent", model="test")\n',
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def client(agents_dir: Path):
    app = create_app(agents_dir=agents_dir)
    return TestClient(app)


class TestGetTemplates:
    def test_returns_list(self, client: TestClient):
        resp = client.get("/templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert isinstance(templates, list)
        names = [t["name"] for t in templates]
        assert "basic" in names

    def test_template_has_fields(self, client: TestClient):
        resp = client.get("/templates")
        for tpl in resp.json():
            assert "name" in tpl
            assert "description" in tpl


class TestCreateAgent:
    def test_create_basic(self, client: TestClient):
        resp = client.post("/agents/create", json={"name": "test_bot", "template": "basic"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test_bot"
        assert data["status"] == "created"
        # Verify agent is now in the list
        apps = client.get("/list-apps").json()
        assert "test_bot" in apps

    def test_create_invalid_template(self, client: TestClient):
        resp = client.post("/agents/create", json={"name": "my_agent", "template": "normal"})
        assert resp.status_code == 400

    def test_invalid_name_starts_with_number(self, client: TestClient):
        resp = client.post("/agents/create", json={"name": "1agent"})
        assert resp.status_code == 400

    def test_invalid_name_special_chars(self, client: TestClient):
        resp = client.post("/agents/create", json={"name": "my-agent"})
        assert resp.status_code == 400

    def test_invalid_name_empty(self, client: TestClient):
        resp = client.post("/agents/create", json={"name": ""})
        assert resp.status_code == 400

    def test_invalid_name_path_traversal(self, client: TestClient):
        resp = client.post("/agents/create", json={"name": "../hack"})
        assert resp.status_code == 400

    def test_invalid_template(self, client: TestClient):
        resp = client.post("/agents/create", json={"name": "test_bot", "template": "nonexistent"})
        assert resp.status_code == 400

    def test_duplicate_name(self, client: TestClient):
        # Create first
        resp1 = client.post("/agents/create", json={"name": "dup_test"})
        assert resp1.status_code == 200
        # Create duplicate
        resp2 = client.post("/agents/create", json={"name": "dup_test"})
        assert resp2.status_code == 409

    def test_existing_agent_conflict(self, client: TestClient):
        resp = client.post("/agents/create", json={"name": "existing_agent"})
        assert resp.status_code == 409


class TestDeleteAgent:
    def test_delete_existing(self, client: TestClient):
        # Create then delete
        client.post("/agents/create", json={"name": "to_delete"})
        resp = client.delete("/agents/to_delete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        # Verify removed from list
        apps = client.get("/list-apps").json()
        assert "to_delete" not in apps

    def test_delete_not_found(self, client: TestClient):
        resp = client.delete("/agents/nonexistent")
        assert resp.status_code == 404

    def test_delete_invalid_name(self, client: TestClient):
        resp = client.delete("/agents/Bad-Name!")
        assert resp.status_code == 400


class TestHotReload:
    def test_created_agent_accessible(self, client: TestClient):
        """Created agent should be immediately accessible via /apps/{name}."""
        client.post("/agents/create", json={"name": "hot_agent"})
        resp = client.get("/apps/hot_agent")
        assert resp.status_code == 200
        info = resp.json()
        assert info["name"] == "hot_agent"

    def test_deleted_agent_inaccessible(self, client: TestClient):
        """Deleted agent should no longer be accessible."""
        client.post("/agents/create", json={"name": "temp_agent"})
        client.delete("/agents/temp_agent")
        resp = client.get("/apps/temp_agent")
        assert resp.status_code == 404


class TestListAisops:
    def test_no_aisop_dir(self, client: TestClient):
        """Agent without aiap/ directory returns empty list."""
        resp = client.get("/agents/existing_agent/aisops")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_not_found_agent(self, client: TestClient):
        resp = client.get("/agents/nonexistent/aisops")
        assert resp.status_code == 404

    def test_with_aisop_files(self, client: TestClient, agents_dir: Path):
        """Agent with aisop files returns parsed summaries."""
        import json
        # Create aisop directory with a test file
        aisop_dir = agents_dir / "existing_agent" / "aiap"
        aisop_dir.mkdir(parents=True)
        aisop_file = aisop_dir / "main.aisop.json"
        aisop_file.write_text(json.dumps([
            {
                "role": "system",
                "content": {
                    "protocol": "AISOP V1.0.0",
                    "name": "Test AISOP",
                    "version": "1.0.0",
                    "summary": "A test aisop file",
                    "tools": ["shell", "file_system"],
                }
            },
            {"role": "user", "content": {"instruction": "test"}}
        ]), encoding="utf-8")

        resp = client.get("/agents/existing_agent/aisops")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test AISOP"
        assert data[0]["version"] == "1.0.0"
        assert data[0]["summary"] == "A test aisop file"
        assert data[0]["protocol"] == "AISOP V1.0.0"
        assert data[0]["tools"] == ["shell", "file_system"]
        assert data[0]["group"] is None

    def test_grouped_aisop_files(self, client: TestClient, agents_dir: Path):
        """Nested subfolder AIOSPs should have group set."""
        import json
        sub_dir = agents_dir / "existing_agent" / "aiap" / "my_group"
        sub_dir.mkdir(parents=True)
        (sub_dir / "detail.aisop.json").write_text(json.dumps([
            {"role": "system", "content": {"name": "Detail", "version": "0.1"}},
            {"role": "user", "content": {}}
        ]), encoding="utf-8")

        resp = client.get("/agents/existing_agent/aisops")
        assert resp.status_code == 200
        grouped = [a for a in resp.json() if a["group"] == "my_group"]
        assert len(grouped) == 1
        assert grouped[0]["name"] == "Detail"


class TestDeleteAisop:
    def _setup_aisop(self, agents_dir: Path, filename: str = "detail.aisop.json",
                     group: str | None = None):
        """Helper to create an AISOP file."""
        import json
        if group:
            d = agents_dir / "existing_agent" / "aiap" / group
        else:
            d = agents_dir / "existing_agent" / "aiap"
        d.mkdir(parents=True, exist_ok=True)
        f = d / filename
        f.write_text(json.dumps([
            {"role": "system", "content": {"name": "Test", "version": "1.0"}},
            {"role": "user", "content": {}}
        ]), encoding="utf-8")
        return f

    def test_delete_non_main(self, client: TestClient, agents_dir: Path):
        self._setup_aisop(agents_dir, "detail.aisop.json")
        resp = client.post("/agents/existing_agent/aisops/delete",
                           json={"path": "aiap/detail.aisop.json"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        # Verify file removed
        assert not (agents_dir / "existing_agent" / "aiap" / "detail.aisop.json").exists()

    def test_delete_main_blocked(self, client: TestClient, agents_dir: Path):
        self._setup_aisop(agents_dir, "main.aisop.json")
        resp = client.post("/agents/existing_agent/aisops/delete",
                           json={"path": "aiap/main.aisop.json"})
        assert resp.status_code == 400
        assert "main.aisop.json" in resp.json()["detail"]

    def test_delete_grouped_main_blocked(self, client: TestClient, agents_dir: Path):
        self._setup_aisop(agents_dir, "main.aisop.json", group="sub_group")
        resp = client.post("/agents/existing_agent/aisops/delete",
                           json={"path": "aiap/sub_group/main.aisop.json"})
        assert resp.status_code == 400

    def test_delete_group_folder(self, client: TestClient, agents_dir: Path):
        """Delete an entire group folder."""
        self._setup_aisop(agents_dir, "main.aisop.json", group="sub_group")
        self._setup_aisop(agents_dir, "detail.aisop.json", group="sub_group")
        resp = client.post("/agents/existing_agent/aisops/delete",
                           json={"path": "aiap/sub_group"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
        # Verify folder removed
        assert not (agents_dir / "existing_agent" / "aiap" / "sub_group").exists()

    def test_delete_group_not_found(self, client: TestClient, agents_dir: Path):
        (agents_dir / "existing_agent" / "aiap").mkdir(parents=True, exist_ok=True)
        resp = client.post("/agents/existing_agent/aisops/delete",
                           json={"path": "aiap/nonexistent_group"})
        assert resp.status_code == 404

    def test_delete_invalid_path(self, client: TestClient):
        resp = client.post("/agents/existing_agent/aisops/delete",
                           json={"path": "not_aiap/file.json"})
        assert resp.status_code == 400

    def test_delete_path_traversal(self, client: TestClient):
        resp = client.post("/agents/existing_agent/aisops/delete",
                           json={"path": "aiap/../../../etc/passwd.aisop.json"})
        assert resp.status_code == 400

    def test_delete_not_found_file(self, client: TestClient, agents_dir: Path):
        (agents_dir / "existing_agent" / "aiap").mkdir(parents=True, exist_ok=True)
        resp = client.post("/agents/existing_agent/aisops/delete",
                           json={"path": "aiap/nonexistent.aisop.json"})
        assert resp.status_code == 404

    def test_delete_not_found_agent(self, client: TestClient):
        resp = client.post("/agents/nonexistent/aisops/delete",
                           json={"path": "aiap/detail.aisop.json"})
        assert resp.status_code == 404


class TestAisopLibrary:
    def test_no_library_dir(self, client: TestClient):
        """No aiap_store directory returns empty list."""
        resp = client.get("/aisop-library")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_with_library_packages(self, client: TestClient, agents_dir: Path):
        """Library with AISOP packages returns parsed summaries."""
        import json
        lib_dir = agents_dir / "aiap_store"
        pkg_dir = lib_dir / "stock_tracker_aisop"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "main.aisop.json").write_text(json.dumps([
            {
                "role": "system",
                "content": {
                    "protocol": "AISOP V1.0.0",
                    "name": "Stock Tracker",
                    "version": "1.0.0",
                    "summary": "Track stock prices",
                    "tools": ["google_search"],
                }
            },
            {"role": "user", "content": {"instruction": "test"}}
        ]), encoding="utf-8")

        resp = client.get("/aisop-library")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Stock Tracker"
        assert data[0]["group"] == "stock_tracker_aisop"
        assert data[0]["tools"] == ["google_search"]

    def test_multiple_packages(self, client: TestClient, agents_dir: Path):
        """Multiple library packages are all returned."""
        import json
        lib_dir = agents_dir / "aiap_store"
        for pkg in ["pkg_a_aisop", "pkg_b_aisop"]:
            d = lib_dir / pkg
            d.mkdir(parents=True, exist_ok=True)
            (d / "main.aisop.json").write_text(json.dumps([
                {"role": "system", "content": {"name": pkg, "version": "1.0"}},
                {"role": "user", "content": {}}
            ]), encoding="utf-8")

        resp = client.get("/aisop-library")
        assert resp.status_code == 200
        groups = {a["group"] for a in resp.json()}
        assert "pkg_a_aisop" in groups
        assert "pkg_b_aisop" in groups


class TestAddFromLibrary:
    def _setup_lib_pkg(self, agents_dir: Path, pkg: str = "stock_aisop"):
        import json
        d = agents_dir / "aiap_store" / pkg
        d.mkdir(parents=True, exist_ok=True)
        (d / "main.aisop.json").write_text(json.dumps([
            {"role": "system", "content": {"name": pkg, "version": "1.0"}},
            {"role": "user", "content": {}}
        ]), encoding="utf-8")

    def test_add_success(self, client: TestClient, agents_dir: Path):
        self._setup_lib_pkg(agents_dir)
        resp = client.post("/agents/existing_agent/aisops/add-from-library",
                           json={"group": "stock_aisop"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "added"
        # Verify copied
        assert (agents_dir / "existing_agent" / "aiap" / "stock_aisop" / "main.aisop.json").is_file()

    def test_add_shows_in_agent_aisops(self, client: TestClient, agents_dir: Path):
        self._setup_lib_pkg(agents_dir)
        client.post("/agents/existing_agent/aisops/add-from-library",
                     json={"group": "stock_aisop"})
        resp = client.get("/agents/existing_agent/aisops")
        assert resp.status_code == 200
        groups = {a["group"] for a in resp.json()}
        assert "stock_aisop" in groups

    def test_add_duplicate(self, client: TestClient, agents_dir: Path):
        self._setup_lib_pkg(agents_dir)
        client.post("/agents/existing_agent/aisops/add-from-library",
                     json={"group": "stock_aisop"})
        resp = client.post("/agents/existing_agent/aisops/add-from-library",
                           json={"group": "stock_aisop"})
        assert resp.status_code == 409

    def test_add_not_found_pkg(self, client: TestClient, agents_dir: Path):
        resp = client.post("/agents/existing_agent/aisops/add-from-library",
                           json={"group": "nonexistent_aisop"})
        assert resp.status_code == 404

    def test_add_not_found_agent(self, client: TestClient):
        resp = client.post("/agents/nonexistent/aisops/add-from-library",
                           json={"group": "stock_aisop"})
        assert resp.status_code == 404

    def test_add_path_traversal(self, client: TestClient):
        resp = client.post("/agents/existing_agent/aisops/add-from-library",
                           json={"group": "../etc"})
        assert resp.status_code == 400
