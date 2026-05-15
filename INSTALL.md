# SoulBot CLI 安装与发布指南

> 本文档说明如何将 SoulBot 从"源码运行"升级为"一行命令安装启动"，
> 以及如何发布到 PyPI 让任何人 `pip install soulbot` 即可使用。

---

## 一、现状

项目已具备完整的 CLI 打包配置：

```
pyproject.toml          # 构建配置 + 入口点声明
src/soulbot/cli.py      # CLI 主入口 (click)
src/soulbot/__main__.py # python -m soulbot 支持
```

`pyproject.toml` 中的关键配置：

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
soulbot = "soulbot.cli:main"     # ← 这一行声明了 CLI 入口

[tool.hatch.build.targets.wheel]
packages = ["src/soulbot"]       # ← 源码在 src/ 下
```

`[project.scripts]` 等价于 Node.js 的 `package.json → "bin"`。
安装后系统会在 PATH 中创建 `soulbot` 可执行文件，指向 `soulbot.cli:main`。

---

## 二、本地开发安装

### 2.1 editable 模式（推荐开发时使用）

```bash
cd /path/to/SoulBot

# 基础安装
pip install -e .

# 带开发依赖
pip install -e ".[dev]"

# 全部可选依赖
pip install -e ".[dev,telegram,sqlite]"
```

安装后即可全局使用 `soulbot` 命令：

```bash
soulbot --help
soulbot create my_agent
soulbot run my_agent
soulbot web --agents-dir examples/simple
soulbot telegram examples/simple/SoulBot_Agent
```

**editable 模式的好处**：修改 `src/soulbot/` 下的代码后，无需重新安装，`soulbot` 命令立即生效。

### 2.2 普通安装（测试发布包）

```bash
pip install .
```

这会将代码复制到 `site-packages`，修改源码不会自动生效。

### 2.3 卸载

```bash
pip uninstall soulbot
```

---

## 三、两种运行方式对比

安装后有两种等价的运行方式：

| 方式 | 命令 | 说明 |
|------|------|------|
| CLI 入口 | `soulbot web --agents-dir .` | 需要 `pip install` 后才可用 |
| 模块运行 | `python -m soulbot web --agents-dir .` | 无需安装，直接从源码运行 |

两者调用同一个入口函数 `soulbot.cli:main`，功能完全一致。

---

## 四、从 GitHub 安装（无需发布 PyPI）

开发阶段让别人试用，直接从 GitHub 仓库安装即可：

```bash
# pip 安装（需要仓库 URL）
pip install git+https://github.com/AIXP-Labs/SoulBot.git
soulbot web --agents-dir .

# 指定分支
pip install git+https://github.com/AIXP-Labs/SoulBot.git@main

# 指定 tag
pip install git+https://github.com/AIXP-Labs/SoulBot.git@v1.0.0
```

> 将 `AIXP-Labs/SoulBot` 替换为实际的 GitHub 仓库路径。

---

## 五、uvx 一键运行（Python 的 npx）

[uv](https://docs.astral.sh/uv/) 是新一代 Python 包管理器（Ruff 团队出品），
其中 `uvx` 命令等价于 Node.js 的 `npx`——**一条命令完成下载+安装+运行**。

### 5.1 安装 uv

```bash
# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 5.2 一键运行（不需要预先安装）

```bash
# 从 PyPI（发布后）
uvx soulbot web --agents-dir .

# 从 GitHub（开发阶段，无需 PyPI）
uvx --from git+https://github.com/AIXP-Labs/SoulBot.git soulbot web --agents-dir .

# 指定分支
uvx --from git+https://github.com/AIXP-Labs/SoulBot.git@main soulbot web --agents-dir .
```

`uvx` 会自动创建临时隔离环境、安装依赖、运行命令，用完即丢。

### 5.3 对比：Node.js vs Python 一键运行

| Node.js | Python (uv) | 效果 |
|---------|-------------|------|
| `npx openclaw` | `uvx soulbot web --agents-dir .` | 临时下载 + 运行 |
| `npx create-react-app my-app` | `uvx soulbot create my_agent` | 临时下载 + 运行 |
| `npm install -g openclaw` | `uv tool install soulbot` | 永久安装到 PATH |

---

## 六、pipx 隔离安装

[pipx](https://pipx.pypa.io/) 功能类似 `uv tool install`，为 CLI 工具创建独立虚拟环境：

```bash
# 安装 pipx（如果没有）
pip install pipx

# 从本地源码安装
pipx install .

# 从 GitHub 安装
pipx install git+https://github.com/AIXP-Labs/SoulBot.git

# 从 PyPI 安装（发布后）
pipx install soulbot

# 一键运行（不永久安装，类似 uvx）
pipx run soulbot web --agents-dir .

# 卸载
pipx uninstall soulbot
```

---

## 七、发布到 PyPI

发布后任何人都可以 `pip install soulbot` 一行安装。

### 7.1 前置准备

```bash
# 安装构建工具
pip install build twine

# 注册 PyPI 账号
# https://pypi.org/account/register/
```

### 7.2 构建

```bash
cd /path/to/SoulBot
python -m build
```

产物在 `dist/` 目录：
```
dist/
├── soulbot-1.0.0-py3-none-any.whl    # wheel（推荐）
└── soulbot-1.0.0.tar.gz              # sdist
```

### 7.3 发布到 TestPyPI（先测试）

```bash
twine upload --repository testpypi dist/*

# 从 TestPyPI 安装验证
pip install --index-url https://test.pypi.org/simple/ soulbot
```

### 7.4 发布到正式 PyPI

```bash
twine upload dist/*
```

发布后的安装方式：

```bash
# 任何人都可以
pip install soulbot
soulbot --help
```

### 7.5 版本更新

修改 `pyproject.toml` 中的版本号：

```toml
[project]
version = "0.3.0"
```

然后重新构建发布：

```bash
python -m build && twine upload dist/*
```

---

## 八、与主流项目的对比

| 项目 | 语言 | 安装命令 | 一键运行 | CLI 命令 |
|------|------|----------|----------|----------|
| **SoulBot** | Python | `pip install soulbot` | `uvx soulbot` | `soulbot` |
| OpenClaw | Node.js | `npm install -g openclaw` | `npx openclaw` | `openclaw` |
| Claude Code | Node.js | `npm install -g @anthropic-ai/claude-code` | `npx @anthropic-ai/claude-code` | `claude` |
| Ruff | Python/Rust | `pip install ruff` | `uvx ruff` | `ruff` |
| Black | Python | `pip install black` | `uvx black` | `black` |
| Poetry | Python | `pipx install poetry` | `pipx run poetry` | `poetry` |

机制完全一致，SoulBot 已经具备同等能力。

### 安装方式速查

| 阶段 | 安装方式 | 需要 PyPI？ |
|------|----------|-------------|
| 本地开发 | `pip install -e .` | 不需要 |
| 让别人试用 | `pip install git+https://github.com/...` | 不需要 |
| 让别人一键试用 | `uvx --from git+https://github.com/... soulbot` | 不需要 |
| 正式发布 | `pip install soulbot` / `uvx soulbot` | 需要 |

---

## 九、项目打包配置清单

| 文件 | 作用 | 状态 |
|------|------|------|
| `pyproject.toml` | 构建系统 + 元数据 + CLI 入口 + 依赖 | 已配置 |
| `src/soulbot/__init__.py` | 包标识 | 已存在 |
| `src/soulbot/__main__.py` | `python -m soulbot` 支持 | 已存在 |
| `src/soulbot/cli.py` | CLI 入口函数 `main()` | 已存在 |
| `[project.scripts]` | `soulbot = "soulbot.cli:main"` | 已声明 |
| `[tool.hatch.build.targets.wheel]` | `packages = ["src/soulbot"]` | 已声明 |

所有配置已就绪，`pip install -e .` 即可激活。

---

## 十、常见问题

### Q: `soulbot` 命令找不到？

```bash
# 检查是否安装
pip show soulbot

# 检查 Scripts 目录是否在 PATH 中
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"

# Windows 下可能需要重启终端，或手动加 PATH
```

### Q: 改了代码但 `soulbot` 没变化？

确认使用 editable 模式安装：
```bash
pip install -e .
```
普通 `pip install .` 会复制代码，修改不会生效。

### Q: 想同时开发和使用？

editable 模式就是为此设计的。`pip install -e .` 后，
`soulbot` 命令直接指向 `src/soulbot/` 源码，改代码立即生效。

### Q: `pip install -e .` 和 `python -m soulbot` 什么区别？

`python -m soulbot` 不需要安装，直接从当前目录的 `src/soulbot/__main__.py` 运行。
`pip install -e .` 后 `soulbot` 命令从任何目录都能运行，且会创建 PATH 中的可执行文件。

两者调用完全相同的代码。
