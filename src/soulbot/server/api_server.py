"""FastAPI API Server for SoulBot agents.

Provides HTTP endpoints for running agents, managing sessions,
and serving the dev web UI.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# CRITICAL: import at module top, not inside handlers.
# sse_starlette monkey-patches uvicorn's Server.handle_exit on import
# (sse_starlette/sse.py:52-53) so SSE streams can cooperate with Ctrl+C.
# If imported lazily (first request), the patch runs AFTER uvicorn has
# already bound its signal handler to the original handle_exit — the
# patch never takes effect → Ctrl+C hangs on open SSE connections.
from sse_starlette.sse import EventSourceResponse

from ..agents.base_agent import BaseAgent
from ..runners import Runner
from ..sessions import InMemorySessionService
from ..sessions.base_session_service import BaseSessionService
from .agent_loader import AgentLoader

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RunAgentRequest(BaseModel):
    app_name: str
    user_id: str
    session_id: str
    new_message: Optional[dict] = None  # {"role": "user", "parts": [{"text": "..."}]}
    streaming: bool = False


class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = None
    state: Optional[dict] = None
    title: Optional[str] = None


class CreateAgentRequest(BaseModel):
    name: str
    template: str = "basic"


class DeleteAisopRequest(BaseModel):
    path: str


class AddFromLibraryRequest(BaseModel):
    group: str


class AddAispFromLibraryRequest(BaseModel):
    skill: str


class EnvUpdateRequest(BaseModel):
    content: str


class DownloadFromStoreRequest(BaseModel):
    program: str
    repo: str = ""
    overwrite: bool = False


class InstallFromStoreRequest(BaseModel):
    program: str
    agent_name: str
    repo: str = ""
    overwrite: bool = False


class DownloadAispRequest(BaseModel):
    skill: str
    repo: str = ""
    overwrite: bool = False


class InstallAispRequest(BaseModel):
    skill: str
    agent_name: str
    repo: str = ""
    overwrite: bool = False


class AddRepoRequest(BaseModel):
    repo: str


class RemoveRepoRequest(BaseModel):
    repo: str


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    *,
    agents_dir: str | Path | None = None,
    agents: dict[str, BaseAgent] | None = None,
    session_service: BaseSessionService | None = None,
    schedule_service: object | None = None,
    message_service: object | None = None,
    heartbeat_store: object | None = None,
    cli_name: str | None = None,
    dev_ui: bool = True,
    bus: object | None = None,
    cmd_executor: object | None = None,
    cron: object | None = None,
) -> FastAPI:
    """Create a FastAPI application wired with agent runners.

    Args:
        agents_dir: Directory to discover agents from.
        agents: Pre-built dict of {name: agent}.  Mutually exclusive with *agents_dir*.
        session_service: Session backend (defaults to DatabaseSessionService).
        schedule_service: Optional ScheduleService for schedule query endpoints.
        cli_name: CLI identity for session grouping (Doc 21).
        dev_ui: Whether to mount the dev web UI at ``/dev-ui``.
    """
    app = FastAPI(title="SoulBot API Server", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Start the cron scheduler on FastAPI startup. CronScheduler.start()
    # is idempotent (cron.py:143), so if a Telegram bridge also calls it
    # via its on_startup hook, nothing breaks.
    if cron is not None:
        @app.on_event("startup")
        async def _start_cron():
            await cron.start()  # type: ignore[attr-defined]

    # ---- Shared state ---------------------------------------------------
    if session_service is None:
        from ..sessions.constants import resolve_db_path
        from ..sessions.database_session_service import DatabaseSessionService
        session_service = DatabaseSessionService(resolve_db_path())
    svc = session_service

    # Resolve cli_name for runner app_name (Doc 21)
    _cli_name = cli_name

    # Save for agent CRUD endpoints
    _agents_dir: Path | None = Path(agents_dir).resolve() if agents_dir else None
    _loader: AgentLoader | None = None

    runners: dict[str, Runner] = {}

    # ---- AIAP Store repos & cache ----------------------------------------
    DEFAULT_REPO = "AIXP-Labs/AIAP-AISP-Store"
    CACHE_TTL = 300  # 5 minutes
    # Per-repo cache: {repo: {"data": [...], "expires": float}}
    _store_cache: dict[str, dict] = {}

    def _repos_file() -> Path | None:
        if _agents_dir is None:
            return None
        return _agents_dir / "aiap_store_repos.json"

    def _load_repos() -> list[str]:
        """Load repo list from persistent file."""
        f = _repos_file()
        if f and f.is_file():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    repos = [r for r in data if isinstance(r, str) and "/" in r]
                    if DEFAULT_REPO not in repos:
                        repos.insert(0, DEFAULT_REPO)
                    return repos
            except (json.JSONDecodeError, OSError):
                pass
        return [DEFAULT_REPO]

    def _save_repos(repos: list[str]) -> None:
        f = _repos_file()
        if f:
            f.write_text(json.dumps(repos, ensure_ascii=False, indent=2), encoding="utf-8")

    def _github_urls(repo: str, store_dir: str = "aiap_store") -> tuple[str, str, str]:
        """Return (store_api, raw_base, github_tree) for a repo's store dir.

        store_dir defaults to 'aiap_store' so existing AIAP callers are
        unchanged; pass 'aisp_store' for the AISP skill store.
        """
        api_base = f"https://api.github.com/repos/{repo}/contents"
        store_api = f"{api_base}/{store_dir}"
        raw_base = f"https://raw.githubusercontent.com/{repo}/main/{store_dir}"
        return store_api, raw_base, repo

    # Collect all agents FIRST so every Runner gets the full registry
    # for peer-discovery via agents_registry (message.send to_agent list).
    _loaded_agents: dict[str, BaseAgent] = {}
    if agents:
        _loaded_agents.update(agents)
    elif agents_dir:
        import logging
        _log = logging.getLogger(__name__)
        _loader = AgentLoader(agents_dir)
        for name in _loader.list_agents():
            try:
                _loaded_agents[name] = _loader.load_agent(name)
            except (AttributeError, TypeError) as exc:
                _log.warning("Skipping '%s': %s", name, exc)
                continue

    for name, agent in _loaded_agents.items():
        runners[name] = Runner(
            agent=agent, app_name=_cli_name or name, session_service=svc,
            bus=bus, cmd_executor=cmd_executor,
            agents_registry=_loaded_agents,
        )

    # ---- System endpoints -----------------------------------------------

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/version")
    async def version():
        return {"version": "0.1.0"}

    @app.get("/list-apps")
    async def list_apps():
        return list(runners.keys())

    @app.get("/cli-info")
    async def cli_info():
        """Return CLI name for frontend session management (Doc 21)."""
        return {"cli_name": _cli_name or ""}

    # ---- Agent info ------------------------------------------------------

    @app.get("/apps/{app_name}")
    async def get_app_info(app_name: str):
        runner = _get_runner(app_name)
        agent = runner.agent
        return {
            "name": agent.name,
            "description": agent.description or "",
            "sub_agents": [a.name for a in (agent.sub_agents or [])],
        }

    # ---- Agent CRUD (template system) ------------------------------------

    @app.get("/templates")
    async def get_templates():
        from ..templates import list_templates
        return list_templates()

    @app.post("/agents/create")
    async def create_agent(req: CreateAgentRequest):
        if _agents_dir is None:
            raise HTTPException(400, "Agent creation requires agents_dir mode")
        from ..templates import scaffold_agent, AGENT_NAME_RE
        if not AGENT_NAME_RE.match(req.name):
            raise HTTPException(
                400,
                f"Invalid agent name '{req.name}': must match [a-z][a-z0-9_]{{0,49}}",
            )
        if req.name in runners:
            raise HTTPException(409, f"Agent '{req.name}' already exists")
        try:
            target = scaffold_agent(req.name, req.template, _agents_dir)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        except FileExistsError as exc:
            raise HTTPException(409, str(exc))
        except Exception as exc:
            raise HTTPException(500, f"Failed to create agent: {exc}")
        # Hot reload: load new agent into runners
        try:
            loader = _loader or AgentLoader(_agents_dir)
            agent = loader.load_agent(req.name)
            # Register in the shared registry so existing runners' peer
            # discovery sees the new agent immediately.
            _loaded_agents[req.name] = agent
            runners[req.name] = Runner(
                agent=agent, app_name=_cli_name or req.name, session_service=svc,
                agents_registry=_loaded_agents,
            )
        except Exception as exc:
            shutil.rmtree(target, ignore_errors=True)
            raise HTTPException(500, f"Agent created but failed to load: {exc}")
        return {"name": req.name, "status": "created"}

    @app.delete("/agents/{agent_name}")
    async def delete_agent(agent_name: str):
        if _agents_dir is None:
            raise HTTPException(400, "Agent deletion requires agents_dir mode")
        from ..templates import AGENT_NAME_RE
        if not AGENT_NAME_RE.match(agent_name):
            raise HTTPException(400, "Invalid agent name")
        if agent_name not in runners:
            raise HTTPException(404, f"Agent '{agent_name}' not found")
        runners.pop(agent_name)
        # Clean sys.modules cache
        keys_to_remove = [
            k for k in sys.modules
            if agent_name in k and k.startswith("_adk_agents_")
        ]
        for k in keys_to_remove:
            sys.modules.pop(k, None)
        # Remove agent directory
        agent_dir = _agents_dir / agent_name
        if agent_dir.is_dir():
            shutil.rmtree(agent_dir, ignore_errors=True)
        # Clear loader cache
        if _loader and agent_name in _loader._agent_envs:
            del _loader._agent_envs[agent_name]
        return {"name": agent_name, "status": "deleted"}

    _ENV_MAX_BYTES = 10_000

    @app.get("/agents/{agent_name}/env")
    async def get_agent_env(agent_name: str):
        """Read .env file for the named agent."""
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        from ..templates import AGENT_NAME_RE
        if not AGENT_NAME_RE.match(agent_name):
            raise HTTPException(400, "Invalid agent name")
        if agent_name not in runners:
            raise HTTPException(404, f"Agent '{agent_name}' not found")
        env_file = (_agents_dir / agent_name / ".env").resolve()
        # Path traversal guard: env_file must be inside agent_dir
        agent_dir_resolved = (_agents_dir / agent_name).resolve()
        try:
            env_file.relative_to(agent_dir_resolved)
        except ValueError:
            raise HTTPException(400, "Invalid env path")
        if not env_file.is_file():
            return {"content": "", "exists": False}
        try:
            content = env_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(500, f"Failed to read .env: {exc}")
        return {"content": content, "exists": True}

    @app.put("/agents/{agent_name}/env")
    async def update_agent_env(agent_name: str, req: EnvUpdateRequest):
        """Atomically write .env file for the named agent."""
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        from ..templates import AGENT_NAME_RE
        if not AGENT_NAME_RE.match(agent_name):
            raise HTTPException(400, "Invalid agent name")
        if agent_name not in runners:
            raise HTTPException(404, f"Agent '{agent_name}' not found")
        if len(req.content.encode("utf-8")) > _ENV_MAX_BYTES:
            raise HTTPException(
                413,
                f".env content exceeds {_ENV_MAX_BYTES} bytes",
            )
        agent_dir_resolved = (_agents_dir / agent_name).resolve()
        env_file = (agent_dir_resolved / ".env").resolve()
        try:
            env_file.relative_to(agent_dir_resolved)
        except ValueError:
            raise HTTPException(400, "Invalid env path")
        # Atomic write: .tmp + rename
        tmp = env_file.with_suffix(".env.tmp")
        try:
            tmp.write_text(req.content, encoding="utf-8")
            tmp.replace(env_file)
        except OSError as exc:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise HTTPException(500, f"Failed to write .env: {exc}")
        return {
            "name": agent_name,
            "status": "saved",
            "bytes": len(req.content.encode("utf-8")),
            "note": "Call POST /agents/{name}/reload to apply without restart",
        }

    @app.post("/agents/{agent_name}/reload")
    async def reload_agent(agent_name: str):
        """Hot-reload an agent: re-read .env, re-import module, rebuild Runner.

        Isolation: only this agent's module + Runner is replaced. Other agents
        keep their existing instances and their in-progress runs are not
        disrupted (old Runner reference held by active coroutines stays valid;
        only NEW requests use the new Runner).

        Caveat: ``os.environ`` is process-global, so any env var read at
        runtime by shared code (e.g. ``CACHE_NUM`` in prepare_cache) becomes
        this agent's value until another reload overwrites it — same behavior
        as a full SoulBot restart.
        """
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        from ..templates import AGENT_NAME_RE
        if not AGENT_NAME_RE.match(agent_name):
            raise HTTPException(400, "Invalid agent name")
        if agent_name not in runners:
            raise HTTPException(404, f"Agent '{agent_name}' not found")
        if _loader is None:
            raise HTTPException(500, "AgentLoader not initialized")

        # Invalidate AgentLoader's per-agent env cache so .env is re-parsed
        # from disk on the next load_agent() call.
        if hasattr(_loader, "_agent_envs") and agent_name in _loader._agent_envs:
            del _loader._agent_envs[agent_name]

        # Clear cached agent module(s) from sys.modules — load_agent will
        # re-import from disk after this, picking up any agent.py edits too.
        keys_to_remove = [
            k for k in sys.modules
            if agent_name in k and k.startswith("_adk_agents_")
        ]
        for k in keys_to_remove:
            sys.modules.pop(k, None)

        try:
            # load_agent() internally re-applies the agent's merged .env to
            # os.environ before importing, so the new module sees fresh values.
            new_agent = _loader.load_agent(agent_name)
        except Exception as exc:
            raise HTTPException(500, f"Reload failed during import: {exc}")

        # Mutate the SHARED registry dict in place so every existing Runner's
        # agents_registry (which holds the same dict by reference) now sees
        # the new agent — important for inter-agent message.send dispatch.
        _loaded_agents[agent_name] = new_agent

        # Replace this agent's Runner. In-flight requests captured the OLD
        # runner reference locally (Python closure semantics), so they keep
        # using the old agent instance until they finish. Only NEW requests
        # arriving after this point use the new Runner.
        runners[agent_name] = Runner(
            agent=new_agent,
            app_name=_cli_name or agent_name,
            session_service=svc,
            bus=bus,
            cmd_executor=cmd_executor,
            agents_registry=_loaded_agents,
        )

        return {
            "name": agent_name,
            "status": "reloaded",
            "model": getattr(new_agent, "model", ""),
        }

    @app.get("/agents/{agent_name}/aisops")
    async def list_agent_aisops(agent_name: str):
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        if agent_name not in runners:
            raise HTTPException(404, f"Agent '{agent_name}' not found")
        aisop_dir = _agents_dir / agent_name / "aiap"
        if not aisop_dir.is_dir():
            return []
        return _scan_aisops(aisop_dir)

    @app.post("/agents/{agent_name}/aisops/delete")
    async def delete_agent_aisop(agent_name: str, req: DeleteAisopRequest):
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        if agent_name not in runners:
            raise HTTPException(404, f"Agent '{agent_name}' not found")
        p = req.path.replace("\\", "/")
        if not p.startswith("aiap/"):
            raise HTTPException(400, "Invalid path")
        if ".." in p:
            raise HTTPException(400, "Path traversal not allowed")
        # Resolve and verify within agent directory
        target = (_agents_dir / agent_name / p).resolve()
        agent_dir = (_agents_dir / agent_name).resolve()
        if not str(target).startswith(str(agent_dir)):
            raise HTTPException(400, "Path outside agent directory")
        # Case 1: Delete a single file
        if p.endswith(".aisop.json"):
            if p.split("/")[-1] == "main.aisop.json":
                raise HTTPException(400, "Cannot delete main.aisop.json (entry point)")
            if not target.is_file():
                raise HTTPException(404, f"AISOP file not found: {req.path}")
            target.unlink()
            return {"path": req.path, "status": "deleted"}
        # Case 2: Delete an entire group folder (e.g. "aiap/code_creator_aiap")
        if not target.is_dir():
            raise HTTPException(404, f"AISOP group not found: {req.path}")
        shutil.rmtree(target, ignore_errors=True)
        return {"path": req.path, "status": "deleted"}

    @app.get("/aisop-library")
    async def list_aiap_store():
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        lib_dir = _agents_dir / "aiap_store"
        if not lib_dir.is_dir():
            return []
        return _scan_aisops(lib_dir)

    @app.post("/agents/{agent_name}/aisops/add-from-library")
    async def add_aisop_from_library(agent_name: str, req: AddFromLibraryRequest):
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        if agent_name not in runners:
            raise HTTPException(404, f"Agent '{agent_name}' not found")
        if ".." in req.group or "/" in req.group or "\\" in req.group:
            raise HTTPException(400, "Invalid group name")
        src = _agents_dir / "aiap_store" / req.group
        if not src.is_dir():
            raise HTTPException(404, f"Library package '{req.group}' not found")
        dest = _agents_dir / agent_name / "aiap" / req.group
        if dest.exists():
            raise HTTPException(409, f"'{req.group}' already exists in this agent")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)
        return {"group": req.group, "status": "added"}

    # ---- AISP skills (mirrors the aisops endpoints above; doc 06) --------
    # The registry cache (aisp/aisp_list.json) is deliberately NOT touched
    # here: agent.py's _get_aisp_registry hash-gate self-heals it on the
    # agent's next turn (truth model: folders are the source of truth).

    @app.get("/agents/{agent_name}/aisps")
    async def list_agent_aisps(agent_name: str):
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        if agent_name not in runners:
            raise HTTPException(404, f"Agent '{agent_name}' not found")
        aisp_dir = _agents_dir / agent_name / "aisp"
        if not aisp_dir.is_dir():
            return []
        return _scan_aisps(aisp_dir)

    @app.post("/agents/{agent_name}/aisps/delete")
    async def delete_agent_aisp(agent_name: str, req: DeleteAisopRequest):
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        if agent_name not in runners:
            raise HTTPException(404, f"Agent '{agent_name}' not found")
        p = req.path.replace("\\", "/")
        if not p.startswith("aisp/"):
            raise HTTPException(400, "Invalid path")
        if ".." in p:
            raise HTTPException(400, "Path traversal not allowed")
        # An AISP skill is an atomic single-folder unit: only whole *_aisp
        # directories may be removed (stricter than the aisops variant —
        # aisp_list.py / _shared/ / README.md are never deletable here).
        if not p.rstrip("/").endswith("_aisp"):
            raise HTTPException(400, "Only whole *_aisp skill folders can be deleted")
        target = (_agents_dir / agent_name / p).resolve()
        agent_dir = (_agents_dir / agent_name).resolve()
        if not str(target).startswith(str(agent_dir)):
            raise HTTPException(400, "Path outside agent directory")
        if not target.is_dir():
            raise HTTPException(404, f"AISP skill not found: {req.path}")
        shutil.rmtree(target, ignore_errors=True)
        return {"path": req.path, "status": "deleted"}

    @app.get("/aisp-library")
    async def list_aisp_store():
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        lib_dir = _agents_dir / "aisp_store"
        if not lib_dir.is_dir():
            return []
        return _scan_aisps(lib_dir)

    @app.post("/agents/{agent_name}/aisps/add-from-library")
    async def add_aisp_from_library(agent_name: str, req: AddAispFromLibraryRequest):
        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        if agent_name not in runners:
            raise HTTPException(404, f"Agent '{agent_name}' not found")
        if ".." in req.skill or "/" in req.skill or "\\" in req.skill:
            raise HTTPException(400, "Invalid skill name")
        if not req.skill.endswith("_aisp"):
            raise HTTPException(400, "Skill name must end with '_aisp'")
        src = _agents_dir / "aisp_store" / req.skill
        if not src.is_dir():
            raise HTTPException(404, f"Library skill '{req.skill}' not found")
        dest = _agents_dir / agent_name / "aisp" / req.skill
        if dest.exists():
            raise HTTPException(409, f"'{req.skill}' already exists in this agent")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)
        return {"skill": req.skill, "status": "added"}

    # ---- AIAP Store repo management --------------------------------------

    @app.get("/aiap-store/repos")
    async def list_store_repos():
        return _load_repos()

    @app.post("/aiap-store/repos/add")
    async def add_store_repo(req: AddRepoRequest):
        repo = req.repo.strip()
        if "/" not in repo or len(repo.split("/")) != 2:
            raise HTTPException(400, "Invalid format. Use 'owner/repo'")
        repos = _load_repos()
        if repo in repos:
            raise HTTPException(409, f"'{repo}' already exists")
        repos.append(repo)
        _save_repos(repos)
        return {"repo": repo, "status": "added"}

    @app.post("/aiap-store/repos/remove")
    async def remove_store_repo(req: RemoveRepoRequest):
        repo = req.repo.strip()
        if repo == DEFAULT_REPO:
            raise HTTPException(400, "Cannot remove the default repository")
        repos = _load_repos()
        if repo not in repos:
            raise HTTPException(404, f"'{repo}' not found")
        repos.remove(repo)
        _save_repos(repos)
        _store_cache.pop(repo, None)
        return {"repo": repo, "status": "removed"}

    # ---- AIAP Store endpoints -------------------------------------------

    @app.get("/aiap-store/programs")
    async def list_store_programs(repo: str = ""):
        """List available AIAP programs from a GitHub repo."""
        import logging
        _log = logging.getLogger(__name__)

        target_repo = repo or DEFAULT_REPO
        cache_key = target_repo
        store_api, raw_base, gh_repo = _github_urls(target_repo)

        now = time.time()
        cached = _store_cache.get(cache_key)
        if cached and cached["data"] is not None and now < cached["expires"]:
            return cached["data"]

        try:
            r = urllib.request.Request(
                store_api,
                headers={"Accept": "application/vnd.github.v3+json",
                         "User-Agent": "SoulBot/1.0"},
            )
            with urllib.request.urlopen(r, timeout=10) as resp:
                contents = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            _log.warning("Failed to fetch AIAP Store listing: %s", exc)
            raise HTTPException(502, f"Failed to reach GitHub API: {exc}")

        store_dir = "aiap_store"
        programs = []
        for item in contents:
            if item.get("type") != "dir":
                continue
            name = item["name"]
            if not name.endswith("_aiap"):
                continue
            meta = _fetch_aiap_metadata(name, raw_base, gh_repo, store_dir, _log)
            meta["local_version"] = _local_version("aiap_store", name)
            programs.append(meta)

        _store_cache[cache_key] = {"data": programs, "expires": now + CACHE_TTL}
        return programs

    def _fetch_aiap_metadata(program_name: str, raw_base: str, gh_repo: str, store_dir: str, _log) -> dict:
        """Fetch and parse AIAP.md YAML frontmatter for a program."""
        import yaml

        meta = {
            # id = directory name (what download/install need); name below may
            # be overwritten by the AIAP.md frontmatter display name.
            "id": program_name,
            "name": program_name,
            "version": "",
            "pattern": "",
            "summary": "",
            "tools": [],
            "quality_grade": "",
            "quality_score": 0.0,
            "trust_level": "",
            "module_count": 0,
            "github_url": f"https://github.com/{gh_repo}/tree/main/{store_dir}/{program_name}",
        }

        try:
            url = f"{raw_base}/{program_name}/AIAP.md"
            r = urllib.request.Request(
                url, headers={"User-Agent": "SoulBot/1.0"}
            )
            with urllib.request.urlopen(r, timeout=10) as resp:
                content = resp.read().decode()
        except (urllib.error.URLError, urllib.error.HTTPError):
            _log.debug("No AIAP.md found for %s", program_name)
            return meta

        # Parse YAML frontmatter (between --- delimiters)
        try:
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    data = yaml.safe_load(parts[1])
                    if isinstance(data, dict):
                        meta["name"] = data.get("name", program_name)
                        meta["version"] = str(data.get("version", ""))
                        meta["pattern"] = str(data.get("pattern", ""))
                        meta["summary"] = str(data.get("summary", ""))

                        # trust_level.level → "T3"
                        tl = data.get("trust_level")
                        if isinstance(tl, dict) and "level" in tl:
                            meta["trust_level"] = f"T{tl['level']}"
                        elif isinstance(tl, (int, str)):
                            meta["trust_level"] = f"T{tl}"

                        # quality.grade / quality.weighted_score
                        quality = data.get("quality")
                        if isinstance(quality, dict):
                            meta["quality_grade"] = str(quality.get("grade", ""))
                            try:
                                meta["quality_score"] = float(quality.get("weighted_score", 0))
                            except (ValueError, TypeError):
                                pass

                        # tools[] → extract name from each
                        tools = data.get("tools")
                        if isinstance(tools, list):
                            meta["tools"] = [
                                t["name"] for t in tools
                                if isinstance(t, dict) and "name" in t
                            ]

                        # modules[] → count
                        modules = data.get("modules")
                        if isinstance(modules, list):
                            meta["module_count"] = len(modules)
        except Exception as exc:
            _log.debug("Failed to parse AIAP.md YAML for %s: %s", program_name, exc)

        return meta

    @app.post("/aiap-store/download")
    async def download_from_store(req: DownloadFromStoreRequest):
        """Download an AIAP program from GitHub to local aiap_store/ library."""
        import logging
        _log = logging.getLogger(__name__)

        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")

        if ".." in req.program or "/" in req.program or "\\" in req.program:
            raise HTTPException(400, "Invalid program name")
        if not req.program.endswith("_aiap"):
            raise HTTPException(400, "Program name must end with '_aiap'")

        target_repo = req.repo or DEFAULT_REPO
        store_api, _, _ = _github_urls(target_repo)

        dest = _agents_dir / "aiap_store" / req.program
        if dest.exists() and not req.overwrite:
            raise HTTPException(409, {
                "message": f"'{req.program}' already exists in local library",
                "local_version": _local_version("aiap_store", req.program),
            })

        try:
            files_count = _download_dir_safe(
                f"{store_api}/{req.program}", dest, req.overwrite, _log
            )
        except HTTPException:
            raise
        except Exception as exc:
            _log.error("Failed to download %s: %s", req.program, exc)
            raise HTTPException(502, f"Failed to download from GitHub: {exc}")

        return {
            "program": req.program,
            "files_downloaded": files_count,
            "status": "updated" if req.overwrite else "downloaded",
        }

    @app.post("/aiap-store/install")
    async def install_from_store(req: InstallFromStoreRequest):
        """Download an AIAP program from GitHub and install to agent's aiap dir."""
        import logging
        _log = logging.getLogger(__name__)

        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        if req.agent_name not in runners:
            raise HTTPException(404, f"Agent '{req.agent_name}' not found")

        if ".." in req.program or "/" in req.program or "\\" in req.program:
            raise HTTPException(400, "Invalid program name")
        if not req.program.endswith("_aiap"):
            raise HTTPException(400, "Program name must end with '_aiap'")

        target_repo = req.repo or DEFAULT_REPO
        store_api, _, _ = _github_urls(target_repo)

        dest = _agents_dir / req.agent_name / "aiap" / req.program
        if dest.exists() and not req.overwrite:
            raise HTTPException(409, {
                "message": f"'{req.program}' already exists in agent '{req.agent_name}'",
                "local_version": _local_version(f"{req.agent_name}/aiap", req.program),
            })

        try:
            files_count = _download_dir_safe(
                f"{store_api}/{req.program}", dest, req.overwrite, _log
            )
        except HTTPException:
            raise
        except Exception as exc:
            _log.error("Failed to install %s: %s", req.program, exc)
            raise HTTPException(502, f"Failed to download from GitHub: {exc}")

        return {
            "program": req.program,
            "agent": req.agent_name,
            "files_installed": files_count,
            "status": "updated" if req.overwrite else "installed",
        }

    # ---- AISP Store endpoints (GitHub remote; doc 07) -------------------
    # Mirror the aiap-store endpoints but target the repo's aisp_store/ dir
    # and *_aisp skills. Repo list (/aiap-store/repos) is shared — one repo
    # can host both aiap_store/ and aisp_store/.

    @app.get("/aisp-store/skills")
    async def list_store_skills(repo: str = ""):
        """List available AISP skills from a GitHub repo's aisp_store/."""
        import logging
        _log = logging.getLogger(__name__)

        target_repo = repo or DEFAULT_REPO
        cache_key = f"{target_repo}:aisp"
        store_api, raw_base, gh_repo = _github_urls(target_repo, "aisp_store")

        now = time.time()
        cached = _store_cache.get(cache_key)
        if cached and cached["data"] is not None and now < cached["expires"]:
            return cached["data"]

        try:
            r = urllib.request.Request(
                store_api,
                headers={"Accept": "application/vnd.github.v3+json",
                         "User-Agent": "SoulBot/1.0"},
            )
            with urllib.request.urlopen(r, timeout=10) as resp:
                contents = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            _log.warning("Failed to fetch AISP Store listing: %s", exc)
            raise HTTPException(502, f"Failed to reach GitHub API: {exc}")

        skills = []
        for item in contents:
            if item.get("type") != "dir":
                continue
            name = item["name"]
            if not name.endswith("_aisp"):
                continue
            meta = _fetch_aisp_metadata(name, raw_base, gh_repo, _log)
            meta["local_version"] = _local_version("aisp_store", name)
            skills.append(meta)

        _store_cache[cache_key] = {"data": skills, "expires": now + CACHE_TTL}
        return skills

    def _fetch_aisp_metadata(skill_name: str, raw_base: str, gh_repo: str, _log) -> dict:
        """Fetch and parse a skill's aisp.aisop.json (JSON, not YAML)."""
        meta = {
            "id": skill_name,
            "name": skill_name,
            "version": "",
            "summary": "",
            "protocol": "",
            "risk_level": "",
            "when_to_use": [],
            "github_url": f"https://github.com/{gh_repo}/tree/main/aisp_store/{skill_name}",
        }
        try:
            url = f"{raw_base}/{skill_name}/aisp.aisop.json"
            r = urllib.request.Request(url, headers={"User-Agent": "SoulBot/1.0"})
            with urllib.request.urlopen(r, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            _log.debug("No aisp.aisop.json for %s", skill_name)
            return meta

        try:
            sys_content = data[0]["content"] if isinstance(data, list) and data else {}
            meta["name"] = sys_content.get("name", skill_name)
            meta["version"] = str(sys_content.get("version", ""))
            meta["summary"] = str(sys_content.get("summary", ""))
            meta["protocol"] = str(sys_content.get("protocol", ""))
            if isinstance(data, list) and len(data) > 1:
                contract = data[1].get("content", {}).get("aisp_contract", {}) or {}
                meta["risk_level"] = str(contract.get("risk_level", ""))
                wtu = (contract.get("invocation", {}) or {}).get("when_to_use", [])
                if isinstance(wtu, list):
                    meta["when_to_use"] = wtu
        except Exception as exc:
            _log.debug("Failed to parse aisp.aisop.json for %s: %s", skill_name, exc)
        return meta

    @app.post("/aisp-store/download")
    async def download_aisp_from_store(req: DownloadAispRequest):
        """Download an AISP skill from GitHub to local aisp_store/ library."""
        import logging
        _log = logging.getLogger(__name__)

        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        if ".." in req.skill or "/" in req.skill or "\\" in req.skill:
            raise HTTPException(400, "Invalid skill name")
        if not req.skill.endswith("_aisp"):
            raise HTTPException(400, "Skill name must end with '_aisp'")

        store_api, _, _ = _github_urls(req.repo or DEFAULT_REPO, "aisp_store")
        dest = _agents_dir / "aisp_store" / req.skill
        if dest.exists() and not req.overwrite:
            raise HTTPException(409, {
                "message": f"'{req.skill}' already exists in local library",
                "local_version": _local_version("aisp_store", req.skill),
            })

        try:
            files_count = _download_dir_safe(f"{store_api}/{req.skill}", dest, req.overwrite, _log)
        except HTTPException:
            raise
        except Exception as exc:
            _log.error("Failed to download %s: %s", req.skill, exc)
            raise HTTPException(502, f"Failed to download from GitHub: {exc}")

        return {"skill": req.skill, "files_downloaded": files_count,
                "status": "updated" if req.overwrite else "downloaded"}

    @app.post("/aisp-store/install")
    async def install_aisp_from_store(req: InstallAispRequest):
        """Download an AISP skill from GitHub and install to agent's aisp/ dir."""
        import logging
        _log = logging.getLogger(__name__)

        if _agents_dir is None:
            raise HTTPException(400, "Requires agents_dir mode")
        if req.agent_name not in runners:
            raise HTTPException(404, f"Agent '{req.agent_name}' not found")
        if ".." in req.skill or "/" in req.skill or "\\" in req.skill:
            raise HTTPException(400, "Invalid skill name")
        if not req.skill.endswith("_aisp"):
            raise HTTPException(400, "Skill name must end with '_aisp'")

        store_api, _, _ = _github_urls(req.repo or DEFAULT_REPO, "aisp_store")
        dest = _agents_dir / req.agent_name / "aisp" / req.skill
        if dest.exists() and not req.overwrite:
            raise HTTPException(409, {
                "message": f"'{req.skill}' already exists in agent '{req.agent_name}'",
                "local_version": _local_version(f"{req.agent_name}/aisp", req.skill),
            })

        try:
            files_count = _download_dir_safe(f"{store_api}/{req.skill}", dest, req.overwrite, _log)
        except HTTPException:
            raise
        except Exception as exc:
            _log.error("Failed to install %s: %s", req.skill, exc)
            raise HTTPException(502, f"Failed to download from GitHub: {exc}")

        return {"skill": req.skill, "agent": req.agent_name,
                "files_installed": files_count, "status": "updated" if req.overwrite else "installed"}

    def _local_version(store_dir: str, pkg_id: str) -> str:
        """Version of a package already in the local store library ('' if none).

        AIAP: agent_card.json version (falls back to AIAP.md frontmatter).
        AISP: aisp.aisop.json [0].content.version.
        """
        if _agents_dir is None:
            return ""
        d = _agents_dir / store_dir / pkg_id
        if not d.is_dir():
            return ""
        try:
            if pkg_id.endswith("_aisp"):
                data = json.loads((d / "aisp.aisop.json").read_text(encoding="utf-8-sig"))
                return str(data[0]["content"].get("version", "")) if data else ""
            card = d / "agent_card.json"
            if card.is_file():
                return str(json.loads(card.read_text(encoding="utf-8-sig")).get("version", ""))
        except (OSError, json.JSONDecodeError, KeyError, IndexError):
            pass
        return ""

    def _download_dir_safe(api_url: str, dest: Path, overwrite: bool, _log) -> int:
        """Download a GitHub dir to *dest*. If dest exists and overwrite=True,
        download to a temp sibling first and atomically swap only on success —
        so a failed download never destroys the existing local copy.

        On success, invalidates the store-listing cache so the next
        /programs or /skills call re-scans and reports the fresh
        local_version (else the button stays 'Download' for 5 min TTL).
        """
        if not dest.exists():
            count = _download_github_dir(api_url, dest, _log)
            _store_cache.clear()
            return count
        # overwrite: temp-then-swap
        tmp = dest.parent / f".{dest.name}.tmp-download"
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        try:
            count = _download_github_dir(api_url, tmp, _log)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        shutil.rmtree(dest, ignore_errors=True)
        tmp.rename(dest)
        _store_cache.clear()
        return count

    def _download_github_dir(api_url: str, dest: Path, _log) -> int:
        """Recursively download a directory from GitHub API."""
        req = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "SoulBot/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            items = json.loads(resp.read().decode())

        dest.mkdir(parents=True, exist_ok=True)
        count = 0

        for item in items:
            name = item["name"]
            if item["type"] == "file":
                download_url = item.get("download_url")
                if not download_url:
                    continue
                file_req = urllib.request.Request(
                    download_url,
                    headers={"User-Agent": "SoulBot/1.0"},
                )
                with urllib.request.urlopen(file_req, timeout=15) as file_resp:
                    file_content = file_resp.read()
                (dest / name).write_bytes(file_content)
                count += 1
                _log.debug("Downloaded: %s", dest / name)
            elif item["type"] == "dir":
                sub_url = item.get("url", f"{api_url}/{name}")
                count += _download_github_dir(sub_url, dest / name, _log)

        return count

    # ---- Session CRUD ---------------------------------------------------

    @app.post("/apps/{app_name}/users/{user_id}/sessions")
    async def create_session(app_name: str, user_id: str, req: CreateSessionRequest):
        _get_runner(app_name)  # validate app exists
        # Use cli_name as the real app_name for DB (Doc 21)
        real_app = _cli_name or app_name
        session = await svc.create_session(
            real_app, user_id,
            agent_name=app_name,
            session_id=req.session_id,
            state=req.state,
            title=req.title,
        )
        return _session_summary(session)

    @app.get("/apps/{app_name}/users/{user_id}/sessions")
    async def list_sessions(app_name: str, user_id: str):
        _get_runner(app_name)
        real_app = _cli_name or app_name
        sessions = await svc.list_sessions(real_app, user_id, agent_name=app_name)
        return [_session_summary(s) for s in sessions]

    @app.get("/apps/{app_name}/users/{user_id}/sessions/{session_id}")
    async def get_session(app_name: str, user_id: str, session_id: str):
        _get_runner(app_name)
        real_app = _cli_name or app_name
        session = await svc.get_session(real_app, user_id, session_id)
        if session is None:
            raise HTTPException(404, f"Session '{session_id}' not found")
        return _session_detail(session)

    @app.delete("/apps/{app_name}/users/{user_id}/sessions/{session_id}")
    async def delete_session(app_name: str, user_id: str, session_id: str):
        _get_runner(app_name)
        real_app = _cli_name or app_name
        await svc.delete_session(real_app, user_id, session_id)
        return {"status": "deleted"}

    # ---- Execution endpoints --------------------------------------------

    @app.post("/run")
    async def run_agent(req: RunAgentRequest):
        runner = _get_runner(req.app_name)
        message = _extract_message(req)

        events = []
        async for event in runner.run(
            user_id=req.user_id,
            session_id=req.session_id,
            message=message,
        ):
            if not event.partial:
                events.append(json.loads(event.model_dump_json()))
        return events

    @app.post("/run_sse")
    async def run_agent_sse(req: RunAgentRequest):
        from ..agents.invocation_context import RunConfig

        runner = _get_runner(req.app_name)
        message = _extract_message(req)

        async def event_generator():
            async for event in runner.run(
                user_id=req.user_id,
                session_id=req.session_id,
                message=message,
                run_config=RunConfig(streaming=True),
            ):
                yield {"data": event.model_dump_json()}

        return EventSourceResponse(event_generator())

    # ---- Session event stream -------------------------------------------
    # Long-lived SSE for out-of-band AI responses (scheduled fires,
    # heartbeat broadcasts, agent-to-agent calls). Reuses runner.run()'s
    # existing AGENT_RESPONSE bus event — every AI reply (both user-
    # triggered and schedule-triggered) publishes the same event type, so
    # this endpoint delivers both through a single session-scoped channel.
    if bus is not None:
        from ..bus.events import AGENT_RESPONSE

        @app.get("/sessions/{session_id}/events/stream")
        async def session_events_stream(session_id: str):
            import asyncio

            queue: asyncio.Queue = asyncio.Queue()

            async def on_agent_response(event):
                # Forward out-of-band fires only:
                #   - "scheduled" (schedule fires, heartbeat broadcasts)
                #   - "message"   (agent-to-agent callback arrivals, Doc 08)
                # User-triggered responses are already delivered to the
                # browser via /run_sse on the same request — forwarding
                # them here would cause duplicates.
                if event.data.get("session_id") != session_id:
                    return
                if event.data.get("trigger_type") not in ("scheduled", "message"):
                    return
                await queue.put({
                    "agent": event.data.get("agent", ""),
                    "text": event.data.get("text", ""),
                    "trigger_type": event.data.get("trigger_type", ""),
                    "timestamp": event.timestamp,
                })

            bus.subscribe(AGENT_RESPONSE, on_agent_response)

            async def gen():
                try:
                    while True:
                        try:
                            # Wake up every 5s so cancellation (Ctrl+C,
                            # server shutdown, client disconnect) can
                            # unwind the coroutine. Bare `await queue.get()`
                            # blocks indefinitely and on Windows the
                            # ProactorEventLoop doesn't reliably propagate
                            # SIGINT through the blocked wait.
                            data = await asyncio.wait_for(queue.get(), timeout=5.0)
                            yield {"data": json.dumps(data, ensure_ascii=False)}
                        except asyncio.TimeoutError:
                            # No event this window — loop back; the next
                            # wait_for call is a cancellation checkpoint.
                            continue
                except asyncio.CancelledError:
                    # Normal shutdown / client disconnect path. Swallow
                    # so uvicorn doesn't log "ASGI callable returned
                    # without completing response" — we intentionally
                    # exit without sending a terminal frame because
                    # sse-starlette's task_group is being torn down.
                    pass
                finally:
                    bus.unsubscribe(AGENT_RESPONSE, on_agent_response)

            return EventSourceResponse(gen(), ping=15)

    # ---- Schedule endpoints (Doc 17.5) -----------------------------------

    if schedule_service is not None:
        @app.get("/schedule/list")
        async def schedule_list(status: Optional[str] = None):
            return schedule_service.list(status=status)

        @app.get("/schedule/{entry_id}")
        async def schedule_get(entry_id: str):
            try:
                return schedule_service.get(id=entry_id)
            except ValueError as exc:
                raise HTTPException(404, str(exc))

        @app.post("/schedule/{entry_id}/cancel")
        async def schedule_cancel(entry_id: str):
            # Heartbeat seeds are part of the agent's declared lifecycle
            # and must not be cancellable from the web UI. Users who truly
            # want to disable heartbeat must remove `heartbeat=` in agent.py.
            if entry_id.startswith("hb_"):
                raise HTTPException(
                    403,
                    "Heartbeat seeds cannot be cancelled via the web UI. "
                    "To disable heartbeat, remove the `heartbeat=` parameter "
                    "in the agent's agent.py.",
                )
            try:
                return schedule_service.cancel(id=entry_id)
            except ValueError as exc:
                raise HTTPException(404, str(exc))

    # ---- Agent Message endpoints (Doc 08) --------------------------------

    if message_service is not None:
        _MSG_VALID_STATUSES = frozenset({
            "pending", "processing", "delivered", "failed", "cancelled",
        })
        import re as _re
        _MSG_ID_RE = _re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

        def _validate_message_id(entry_id: str) -> None:
            if not _MSG_ID_RE.match(entry_id):
                raise HTTPException(
                    400,
                    "Invalid message id: must be 1-64 chars of [A-Za-z0-9_.-]",
                )

        @app.get("/message/list")
        async def message_list(
            status: Optional[str] = None,
            from_agent: Optional[str] = None,
            to_agent: Optional[str] = None,
            parent_id: Optional[str] = None,
            limit: int = Query(default=100, ge=1, le=1000),
        ):
            if status is not None and status not in _MSG_VALID_STATUSES:
                raise HTTPException(
                    400,
                    f"Invalid status '{status}'. Allowed: "
                    f"{sorted(_MSG_VALID_STATUSES)}",
                )
            return message_service.list(
                status=status,
                from_agent=from_agent,
                to_agent=to_agent,
                parent_id=parent_id,
                limit=limit,
            )

        @app.get("/message/{entry_id}")
        async def message_get(entry_id: str):
            _validate_message_id(entry_id)
            entry = message_service.get(id=entry_id)
            if not entry:
                raise HTTPException(404, f"Message {entry_id} not found")
            return entry

        @app.post("/message/{entry_id}/cancel")
        async def message_cancel(entry_id: str):
            _validate_message_id(entry_id)
            return await message_service.cancel(id=entry_id)

        @app.get("/message/health")
        async def message_health():
            store = getattr(message_service, "_store", None)
            if store is None:
                return {"status": "no_store"}
            return {
                "status": "ok",
                "pending": store.count(status="pending"),
                "processing": store.count(status="processing"),
                "delivered": store.count(status="delivered"),
                "failed": store.count(status="failed"),
                "cancelled": store.count(status="cancelled"),
                "total": store.count(),
                "in_flight_tasks": len(getattr(message_service, "_tasks", {})),
            }

        @app.on_event("startup")
        async def _restore_messages():
            try:
                count = await message_service.restore()
                if count:
                    import logging
                    logging.getLogger(__name__).info(
                        "Restored %d pending agent message(s) on startup", count
                    )
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Failed to restore pending messages: %s", exc
                )

        @app.on_event("shutdown")
        async def _close_messages():
            try:
                await message_service.close(timeout=5.0)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Failed to close message service cleanly: %s", exc
                )

    # ---- Heartbeat endpoints (Doc 12) ------------------------------------

    if heartbeat_store is not None:
        @app.get("/heartbeat/history")
        async def heartbeat_history(
            agent: Optional[str] = None,
            limit: int = Query(default=50, ge=1, le=1000),
            offset: int = Query(default=0, ge=0),
        ):
            return heartbeat_store.query(agent_name=agent, limit=limit, offset=offset)

        @app.get("/heartbeat/count")
        async def heartbeat_count(agent: Optional[str] = None):
            return {"count": heartbeat_store.count(agent_name=agent)}

    # ---- Observability endpoints (Doc 12 v2.7 + Doc 16 Plan B) ---------
    # Read OTel spans from {agents_dir}/data/_spans.jsonl (or SOULBOT_SPANS_FILE
    # env var override). Lazily import tools.pipeline_viewer to keep startup
    # cost zero when nobody hits these endpoints.

    def _resolve_spans_file() -> Path | None:
        spans_path = os.environ.get("SOULBOT_SPANS_FILE")
        if spans_path:
            return Path(spans_path)
        if _agents_dir is not None:
            return _agents_dir / "data" / "_spans.jsonl"
        return None

    def _parse_ts_ns(t):
        """Span timestamp → nanoseconds. Accepts numeric ns or ISO 8601 string.

        _spans.jsonl mixes two formats:
        - Numeric ns (OTel SDK native export)
        - ISO 8601 string with Z suffix (pipeline.node tools + SoulBot exporter)
        """
        if t is None:
            return None
        if isinstance(t, (int, float)):
            return float(t)
        if isinstance(t, str):
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
                return dt.timestamp() * 1e9
            except ValueError:
                return None
        return None

    def _aggregate_traces(spans: list[dict]) -> list[dict]:
        """Group spans by trace_id, compute summary per trace."""
        groups: dict[str, list[dict]] = {}
        for s in spans:
            tid = (s.get("context") or {}).get("trace_id") or "unknown"
            groups.setdefault(tid, []).append(s)

        traces: list[dict] = []
        for tid, group in groups.items():
            # Root span = one without parent_id (or the earliest if all have)
            roots = [s for s in group if not s.get("parent_id")]
            root = roots[0] if roots else min(group, key=lambda x: x.get("start_time") or 0)

            durations_ns = []
            for s in group:
                start = _parse_ts_ns(s.get("start_time"))
                end = _parse_ts_ns(s.get("end_time"))
                if start is not None and end is not None:
                    durations_ns.append(end - start)

            agents = sorted({
                (s.get("attributes") or {}).get("gen_ai.agent.name", "")
                for s in group
                if (s.get("attributes") or {}).get("gen_ai.agent.name")
            })
            models = sorted({
                (s.get("attributes") or {}).get("gen_ai.request.model", "")
                for s in group
                if (s.get("attributes") or {}).get("gen_ai.request.model")
            })
            has_error = any(
                ((s.get("status") or {}).get("status_code") == "ERROR")
                for s in group
            )
            traces.append({
                "trace_id": tid,
                "root_name": root.get("name", "?"),
                "start_time": root.get("start_time"),
                "duration_ms": (max(durations_ns) / 1e6) if durations_ns else 0.0,
                "span_count": len(group),
                "has_error": has_error,
                "agents": agents,
                "models": models,
            })
        # Sort by start_time desc (newest first)
        traces.sort(key=lambda t: t.get("start_time") or 0, reverse=True)
        return traces

    @app.get("/observability/health")
    async def observability_health():
        spans_file = _resolve_spans_file()
        if spans_file is None:
            return {
                "spans_file": None,
                "exists": False,
                "reason": "no agents_dir and no SOULBOT_SPANS_FILE env",
            }
        if not spans_file.exists():
            return {
                "spans_file": str(spans_file),
                "exists": False,
                "reason": "file not yet created — start chatting to generate spans",
            }
        size = spans_file.stat().st_size
        try:
            from tools.pipeline_viewer import parse_spans_jsonl
            spans = parse_spans_jsonl(spans_file)
            trace_ids = {(s.get("context") or {}).get("trace_id") for s in spans}
            trace_count = len(trace_ids - {None})
        except Exception as exc:
            return {
                "spans_file": str(spans_file),
                "exists": True,
                "size_bytes": size,
                "trace_count": 0,
                "parse_error": str(exc),
            }
        return {
            "spans_file": str(spans_file),
            "exists": True,
            "size_bytes": size,
            "span_count": len(spans),
            "trace_count": trace_count,
        }

    @app.get("/observability/traces")
    async def observability_traces(limit: int = 100, status: str = ""):
        """List trace summaries (newest first).

        Args:
            limit: max number of traces to return
            status: filter by status — "OK" / "ERROR" / "" (all)
        """
        spans_file = _resolve_spans_file()
        if spans_file is None or not spans_file.exists():
            return []
        from tools.pipeline_viewer import parse_spans_jsonl
        spans = parse_spans_jsonl(spans_file)
        traces = _aggregate_traces(spans)
        if status == "ERROR":
            traces = [t for t in traces if t["has_error"]]
        elif status == "OK":
            traces = [t for t in traces if not t["has_error"]]
        return traces[:limit]

    @app.get("/observability/spans/{trace_id}")
    async def observability_spans_by_trace(trace_id: str):
        """Return all spans of a single trace, sorted by start_time."""
        spans_file = _resolve_spans_file()
        if spans_file is None or not spans_file.exists():
            raise HTTPException(404, "spans file not available")
        from tools.pipeline_viewer import parse_spans_jsonl
        all_spans = parse_spans_jsonl(spans_file)
        matched = [
            s for s in all_spans
            if (s.get("context") or {}).get("trace_id") == trace_id
        ]
        if not matched:
            raise HTTPException(404, f"trace_id '{trace_id}' not found")
        # Sort by start_time
        matched.sort(key=lambda s: s.get("start_time") or 0)
        return matched

    # ---- Dev Web UI -----------------------------------------------------

    if dev_ui and STATIC_DIR.is_dir():
        @app.get("/")
        async def redirect_to_dev_ui():
            return RedirectResponse("/dev-ui/")

        app.mount(
            "/dev-ui",
            StaticFiles(directory=str(STATIC_DIR), html=True),
            name="dev-ui",
        )

    # ---- Helpers --------------------------------------------------------

    def _get_runner(app_name: str) -> Runner:
        if app_name not in runners:
            raise HTTPException(404, f"App '{app_name}' not found")
        return runners[app_name]

    return app


def _extract_message(req: RunAgentRequest) -> str:
    """Extract plain text from the request message."""
    if req.new_message:
        parts = req.new_message.get("parts", [])
        texts = [p.get("text", "") for p in parts if p.get("text")]
        if texts:
            return " ".join(texts)
    return ""


def _session_summary(session) -> dict:
    return {
        "id": session.id,
        "app_name": session.app_name,
        "user_id": session.user_id,
        "agent_name": session.agent_name,
        "last_agent": session.last_agent,
        "title": session.title,
        "created_at": session.created_at,
        "last_update_time": session.last_update_time,
    }


def _session_detail(session) -> dict:
    return {
        "id": session.id,
        "app_name": session.app_name,
        "user_id": session.user_id,
        "agent_name": session.agent_name,
        "last_agent": session.last_agent,
        "title": session.title,
        "created_at": session.created_at,
        "state": dict(session.state),
        "events": [json.loads(e.model_dump_json()) for e in session.events],
        "last_update_time": session.last_update_time,
    }


def _scan_aisps(root: Path) -> list[dict]:
    """Scan a directory for AISP skills (*_aisp/aisp.aisop.json, one level).

    Lenient like _scan_aisops (malformed file -> warn + skip) — the UI listing
    favours availability; strict conformance stays with aisp_list.py (the
    spec-normative registry generator). ``_shared/`` carries no aisp.aisop.json
    and is naturally excluded.
    """
    import logging
    _log = logging.getLogger(__name__)
    results: list[dict] = []
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        if not (d.is_dir() and d.name.endswith("_aisp")):
            continue
        f = d / "aisp.aisop.json"
        if not f.is_file():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
            sys_content = data[0]["content"] if isinstance(data, list) and data else {}
            contract = {}
            if isinstance(data, list) and len(data) > 1:
                contract = data[1].get("content", {}).get("aisp_contract", {}) or {}
        except Exception as exc:
            _log.warning("Skipping AISP %s: %s", f, exc)
            continue
        results.append({
            "id": d.name,
            "path": f"{root.name}/{d.name}",
            "name": sys_content.get("name", d.name),
            "version": sys_content.get("version", ""),
            "summary": sys_content.get("summary", ""),
            "protocol": sys_content.get("protocol", ""),
            "risk_level": contract.get("risk_level", ""),
            "when_to_use": (contract.get("invocation", {}) or {}).get("when_to_use", []),
        })
    return results


def _scan_aisops(aisop_dir: Path, pattern: str = "*.aisop.json") -> list[dict]:
    """Scan a directory for AISOP files and extract summaries.

    Skips dot-prefixed subdirectories (``.version_history``,
    ``.execution_cache``, ``.pipeline_cache`` …) since these contain
    historical/cache snapshots that should not appear in the AIAP listing
    and may contain stale or partially-written files. Reads with
    ``utf-8-sig`` so BOM-prefixed files (common when AISOP is hand-edited
    on Windows) decode cleanly.
    """
    import logging
    _log = logging.getLogger(__name__)
    results: list[dict] = []

    for f in sorted(aisop_dir.rglob(pattern)):
        rel = f.relative_to(aisop_dir.parent)
        # Skip any path containing a dot-prefixed component (hidden / cache dirs)
        if any(part.startswith(".") for part in rel.parts):
            continue
        # Determine group: if file is nested in a subfolder under aisop/
        parts = rel.parts  # e.g. ("aiap", "sub_group", "main.aisop.json")
        group = parts[1] if len(parts) > 2 else None

        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
            sys_content = data[0]["content"] if isinstance(data, list) and data else {}
        except Exception as exc:
            _log.warning("Skipping AISOP %s: %s", f, exc)
            continue

        # Normalize tools to a flat list of names. The engine's tools
        # declaration evolved from ["shell", ...] (strings) to
        # [{"name": "shell", "annotations": {...}}, ...] (objects); the UI
        # expects string[]. Accept BOTH shapes so the list never breaks.
        raw_tools = sys_content.get("tools", []) or []
        tools = [
            t.get("name", "") if isinstance(t, dict) else str(t)
            for t in raw_tools
        ]

        results.append({
            "path": str(rel).replace("\\", "/"),
            "group": group,
            "name": sys_content.get("name", f.stem),
            "version": sys_content.get("version", ""),
            "summary": sys_content.get("summary", ""),
            "protocol": sys_content.get("protocol", ""),
            "tools": tools,
        })

    return results
