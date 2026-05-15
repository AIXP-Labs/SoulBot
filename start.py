"""SoulBot One-Click Launcher.

pip install -e .

Usage:
    python start.py                          # Default: web UI + examples/simple
    python start.py --agents-dir my_agents   # Custom agents directory
    python start.py --port 3000              # Custom port
    python start.py --host 0.0.0.0           # Listen on all interfaces
    python start.py --bot-only agent_dir     # Telegram bot only
    python start.py --run agent_dir          # Terminal interactive mode
    python start.py --check                  # Check environment only

No pip install needed — auto-detects and installs on first run.
"""

import shutil
import subprocess
import sys
import os

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_AGENTS_DIR = "examples/simple"
DEFAULT_AGENT_PATH = "examples/simple/SoulBot_Agent"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2026

# LLM CLI tools and their check commands
LLM_TOOLS = [
    ("Claude Code", "claude", "npm install -g @anthropic-ai/claude-code"),
    ("Gemini CLI", "gemini", "npm install -g @google/gemini-cli"),
    ("OpenCode", "opencode", "npm install -g opencode"),
]


# ---------------------------------------------------------------------------
# Environment checks
# ---------------------------------------------------------------------------

def _check_python() -> bool:
    """Check Python version >= 3.11."""
    if sys.version_info >= (3, 11):
        print(f"  [OK] Python {sys.version.split()[0]}")
        return True
    print(f"  [!!] Python {sys.version.split()[0]} — requires 3.11+")
    return False


def _check_soulbot() -> bool:
    """Check if soulbot is importable."""
    try:
        import soulbot  # noqa: F401
        print(f"  [OK] SoulBot installed")
        return True
    except ImportError:
        print(f"  [--] SoulBot not installed")
        return False


def _check_llm_tools() -> list[str]:
    """Check available LLM CLI tools. Returns list of available tool names."""
    available = []
    for name, cmd, install in LLM_TOOLS:
        if shutil.which(cmd):
            print(f"  [OK] {name} ({cmd})")
            available.append(name)
        else:
            print(f"  [--] {name} — install: {install}")
    return available


def _check_agents_dir(agents_dir: str) -> bool:
    """Check if agents directory exists and contains agents."""
    if not os.path.isdir(agents_dir):
        print(f"  [!!] Agents directory not found: {agents_dir}")
        return False
    agents = [d for d in os.listdir(agents_dir)
              if os.path.isdir(os.path.join(agents_dir, d))
              and os.path.isfile(os.path.join(agents_dir, d, "agent.py"))]
    if agents:
        print(f"  [OK] Agents directory: {agents_dir} ({len(agents)} agent(s): {', '.join(agents)})")
    else:
        print(f"  [!!] No agents found in: {agents_dir}")
    return bool(agents)


def _run_checks(config: dict) -> dict:
    """Run all environment checks. Returns results dict."""
    print()
    print("=" * 55)
    print("  SoulBot Environment Check")
    print("=" * 55)
    print()

    results = {
        "python": _check_python(),
        "soulbot": _check_soulbot(),
        "llm_tools": _check_llm_tools(),
    }

    agents_dir = config.get("agents_dir", DEFAULT_AGENTS_DIR)
    results["agents"] = _check_agents_dir(agents_dir)

    print()

    if not results["python"]:
        print("  Python 3.11+ is required.")
    elif not results["llm_tools"]:
        print("  No LLM CLI tool found. Install at least one:")
        for name, _, install in LLM_TOOLS:
            print(f"    {install}")
    elif not results["soulbot"]:
        print("  Run: pip install -e .")
    else:
        print("  All checks passed!")

    print()
    return results


# ---------------------------------------------------------------------------
# Auto-install
# ---------------------------------------------------------------------------

def _check_and_install() -> bool:
    """Return True if soulbot is importable. Auto-install if not."""
    try:
        import soulbot  # noqa: F401
        return True
    except ImportError:
        pass

    print()
    print("=" * 55)
    print("  SoulBot is not installed.")
    print("=" * 55)
    print()

    try:
        answer = input("  Install now? (pip install -e .) [Y/n]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Aborted.")
        return False

    if answer.lower() not in ("", "y", "yes"):
        print("  Aborted. Install manually: pip install -e .")
        return False

    print("\n  Installing SoulBot...\n")
    ret = subprocess.call([sys.executable, "-m", "pip", "install", "-e", "."])
    if ret != 0:
        print("\n  Installation failed. Please fix errors above and retry.")
        return False

    print("\n  Installation successful!\n")
    return True


# ---------------------------------------------------------------------------
# Argument parsing (lightweight, no external dependencies)
# ---------------------------------------------------------------------------

def _parse_args():
    """Parse command-line arguments without external dependencies."""
    args = sys.argv[1:]

    config = {
        "mode": "web",           # "web", "bot", "run", "check"
        "agents_dir": None,
        "agent_path": None,
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
    }

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--bot-only":
            config["mode"] = "bot"
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                config["agent_path"] = args[i + 1]
                i += 1
        elif arg == "--run":
            config["mode"] = "run"
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                config["agent_path"] = args[i + 1]
                i += 1
        elif arg == "--check":
            config["mode"] = "check"
        elif arg == "--agents-dir" and i + 1 < len(args):
            config["agents_dir"] = args[i + 1]
            i += 1
        elif arg == "--host" and i + 1 < len(args):
            config["host"] = args[i + 1]
            i += 1
        elif arg == "--port" and i + 1 < len(args):
            try:
                config["port"] = int(args[i + 1])
            except ValueError:
                print(f"Error: invalid port number: {args[i + 1]}")
                sys.exit(1)
            i += 1
        elif arg in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        else:
            print(f"Unknown argument: {arg}")
            print("Run: python start.py --help")
            sys.exit(1)
        i += 1

    # Defaults
    if config["agents_dir"] is None and config["mode"] == "web":
        config["agents_dir"] = DEFAULT_AGENTS_DIR
    if config["agent_path"] is None and config["mode"] in ("bot", "run"):
        config["agent_path"] = DEFAULT_AGENT_PATH

    return config


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

def _launch(config: dict):
    """Build and execute the soulbot CLI command."""
    mode = config["mode"]

    if mode == "bot":
        cmd = [sys.executable, "-m", "soulbot", "telegram", config["agent_path"]]
    elif mode == "run":
        cmd = [sys.executable, "-m", "soulbot", "run", config["agent_path"]]
    else:
        cmd = [
            sys.executable, "-m", "soulbot", "web",
            "--agents-dir", config["agents_dir"],
            "--host", config["host"],
            "--port", str(config["port"]),
        ]

    # Validate path exists
    check_path = config["agent_path"] if mode in ("bot", "run") else config["agents_dir"]
    if not os.path.exists(check_path):
        print(f"Error: path not found: {check_path}")
        sys.exit(1)

    print()
    print("=" * 55)
    print(f"  SoulBot Starting...")
    print(f"  Mode: {mode.upper()}")
    if mode == "web":
        print(f"  Agents: {config['agents_dir']}")
        print(f"  URL: http://{config['host']}:{config['port']}")
    else:
        print(f"  Agent: {config['agent_path']}")
    print("-" * 55)
    print(f"  Tip: python start.py --help for more options")
    print("=" * 55)
    print()

    try:
        sys.exit(subprocess.call(cmd))
    except KeyboardInterrupt:
        print("\nSoulBot stopped.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Change to script directory (so relative paths work)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    config = _parse_args()

    # Check-only mode
    if config["mode"] == "check":
        _run_checks(config)
        sys.exit(0)

    if not _check_and_install():
        sys.exit(1)

    _launch(config)


if __name__ == "__main__":
    main()
