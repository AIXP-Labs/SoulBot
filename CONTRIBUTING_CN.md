# 贡献 SoulBot

感谢您有兴趣为 SoulBot 做出贡献！

> ⚠️ **当前阶段的贡献政策**
>
> 我们欢迎通过 **GitHub Issues 进行讨论**。
>
> **当前不接受外部 Pull Request。** 如果您有任何建议 — bug 报告、功能想法、新示例代理或改进 — 请通过 Issue 描述。如果我们认为有价值，由维护者实现并在 commit/release notes 中署名感谢您。
>
> 此政策未来会重新审视。

> **阶段状态（v1.0.0）**
>
> SoulBot 处于早期开发阶段。下方流程描述的是**目标**开发模型。初期决策由 AIXP Labs 核心维护者做出；社区讨论窗口将随贡献者基数增长而扩大。

## 如何贡献

### 报告 Issue

- 使用 [GitHub Issues](https://github.com/AIXP-Labs/SoulBot/issues) 报告 bug、提议功能或建议新示例
- 附 Python 版本、OS、LLM CLI 工具版本
- 提供最小复现步骤
- AISOP / AIAP 相关问题请引用相关的 `.aisop.json` 文件

### 讨论驱动开发

1. 通过 issue 提出讨论
2. 维护者评估价值、可行性和公理 0 合规性
3. 讨论达成共识后，由维护者实现变更
4. 贡献者在 commit / release notes 中获得署名

### 提议新代理示例

提议新示例时，请在 issue 中包含：

- **使用场景** — 该代理解决什么问题
- **代理类型** — LLM / Sequential / Parallel / Loop / Multi-agent
- **是否使用 AIAP 包格式** — 是/否
- **外部依赖** — LLM API、MCP server、工具需求
- **为什么**该示例对社区广泛有用

维护者将评估并实现（如批准）。

## 贡献原则

### 质量标准

- 所有新代码必须包含测试（单元 + 集成测试，在可行时）
- 代码风格：`ruff`（配置见 `pyproject.toml`）
- 必须含 Python 3.11+ 类型注解
- 最大行长：100 字符
- 公开函数和类必须有 docstring
- 禁止 wildcard imports

### AISOP / AIAP 贡献

修改 AISOP 蓝图（`.aisop.json`）或 AIAP 包（`*_aiap/`）需：

- 遵循 [AIAP 协议](https://github.com/AIXP-Labs/AIAP) 规范
- 保持 mermaid 图中执行路径的确定性
- 新包必须在 `AIAP.md` 中包含治理元数据

### 双语要求

README 和 CONTRIBUTING 同时维护英文和中文版本。Issue 可使用任一语言。

## 行为准则

参与本项目即表示您同意遵守 [Code of Conduct](CODE_OF_CONDUCT.md)。

## 贡献的许可

提交即同意您的贡献以 [Apache License 2.0](LICENSE) 授权（无论通过 issue 或未来的 PR）。

Copyright 2026 AIXP Labs AIXP.dev | SoulBot.dev

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: SoulBot V1.0.0. www.soulbot.dev
