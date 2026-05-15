---
# AIAP Governance Contract
# 治理字段 (6 个必需)
protocol: "AIAP V1.0.0"
authority: aiap.dev
seed: aisop.dev
executor: soulbot.dev
axiom_0: Human_Sovereignty_and_Wellbeing
governance_mode: NORMAL

# 项目字段 (7 个必需)
name: soulbot_chat
version: "1.10.0"
pattern: E
summary: "SoulBot Chat — AI companion chatbot with long-term memory, user profiling, emotional support, and multi-jurisdiction safety compliance (CA SB 243, NY, PA, EU AI Act Art. 50). FastIntent two-path routing, engagement momentum, cognitive surprise calibration, memory-driven conversation bridge. Three-tier memory (working/episodic/semantic), 8-dimension growth tracking, Socratic coaching. Pattern E, 5 modules, 83 nodes, v1.10.0."
tools:
  - name: file_system
    required: true
    annotations:
      read_only: false
      destructive: true
      idempotent: false
      open_world: false
  - name: google_search
    required: false
    fallback: "degrade"
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
  - name: web_browser
    required: false
    fallback: "degrade"
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
modules:
  - id: soulbot_chat.main
    file: main.aisop.json
    nodes: 23
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: soulbot_chat.conversation
    file: conversation.aisop.json
    nodes: 15
    critical: true
    idempotent: true
    side_effects: []
  - id: soulbot_chat.memory
    file: memory.aisop.json
    nodes: 16
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: soulbot_chat.profiler
    file: profiler.aisop.json
    nodes: 14
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: soulbot_chat.safety
    file: safety.aisop.json
    nodes: 15
    critical: true
    idempotent: false
    side_effects: [file_write]

# 基础可选字段
identity:
  program_id: "soulbot.dev/soulbot_chat"
  publisher: "AIXP Labs AIXP.dev | SoulBot.dev"
  verified_on: "2026-03-26"
governance_hash: 755a365935daa29d178339d08cd95d991a847426e9490d3799a7bd20ac7070cb
quality:
  weighted_score: 4.748
  grade: A
  last_pipeline: "v1.10.0"
tags: [soulbot, chat, conversation, memory, profiling, safety, cognition, companion]
author: SoulBot.dev
license: Apache-2.0
copyright: "Copyright 2026 AIXP Labs AIXP.dev | SoulBot.dev"

mcp_server_card:
  discovery_path: ".well-known/mcp.json"
  spec: "MCP Server Cards (AAIF/Linux Foundation, June 2026)"
  auto_generated: true

# 安全与运行时可选字段
trust_level:
  level: 3
  justification: "file_system read/write limited to memory_dir (./memory/). Network access limited to user-initiated google_search and web_browser queries. No autonomous destructive operations beyond safety audit log archival (365-day retention policy). Safety module uses file_system exclusively for SafetyAuditLog persistent logging; all 14 other safety nodes remain LLM-native."
  constraints:
    - "file_system write scope limited to memory_dir (./memory/)"
    - "network access limited to *.google.com and *.bing.com for user-initiated queries"
    - "no autonomous file deletion — GDPR delete requires explicit user confirmation gate"
    - "crisis_check outputs resource references only — never provides diagnosis or emergency services"
    - "file_system destructive=true due to safety audit log 365-day retention archival — no user data destruction"
permissions:
  file_system:
    scope: "./memory/"
    operations: ["read", "write"]
  network:
    allowed: true
    endpoints: ["*.google.com", "*.bing.com"]
runtime:
  timeout_seconds: 300
  max_retries: 3
  idempotent: false
  side_effects: [file_write]
capabilities:
  offered:
    - file_write
    - search
    - state_persistence
    - user_profiling
  required:
    - file_read
ui:
  components:
    - type: dashboard
      title: "Session Overview"
      data_source: working_memory
      refresh: "on_event"
    - type: form
      title: "User Preferences"
      fields:
        - { name: communication_style, type: select, options: [formal, casual, playful], default: casual }
        - { name: response_verbosity, type: select, options: [concise, balanced, detailed], default: balanced }
        - { name: minor_mode, type: boolean, default: false }
    - type: visualization
      title: "Mood Trend"
      chart_type: line
      data_source: emotion_history
  rendering: "mcp_apps_v1"

# 工程化可选字段
status: active
applicability_condition:
  triggers:
    - "user initiates conversation or sends a chat message"
    - "user asks a factual question requiring search"
    - "user expresses emotion or seeks comfort"
    - "user requests memory recall of past conversations"
    - "user asks about their learned preferences or profile"
    - "user initiates creative collaboration or storytelling"
    - "user provides feedback or correction"
    - "user requests data export or deletion (GDPR)"
    - "user requests direct profile attribute modification"
  preconditions:
    - "memory_dir exists and is writable"
    - "file_system tool available"
    - "routed by SoulBot top-level router to soulbot_chat"
  exclusions:
    - "non-conversation AIAP tasks handled by other specialized modules"
    - "direct file operations unrelated to chat memory"
    - "system administration or AIAP program management tasks"
  confidence_threshold: 0.8
intent_examples:
  - "你好，今天心情怎么样？"
  - "帮我查一下明天的天气"
  - "我最近感觉很焦虑"
  - "你还记得我上次说的旅行计划吗？"
  - "你对我了解多少？"
  - "我们来编个故事吧"
  - "我觉得你刚才理解错了"
  - "把我的名字改成小明"
  - "今天聊得挺开心，再见！"
discovery_keywords: [soulbot, chat, conversation, companion, memory, profiling, emotion, safety]
dependencies: []
min_protocol_version: "AIAP V1.0.0"
benchmark:
  threedimscore: 4.748
  grade: "A"
  simulation_coverage: "18 scenarios (v1.10.0 Professional tier)"
  pass_rate: "18/18 (100%) — 0 RED, 0 YELLOW"
---

## 治理声明

SoulBot Chat 是 SoulBot 生态系统的核心对话与用户认知引擎。本程序遵循 AIAP V1.0.0 协议，
以 Axiom 0 (Human Sovereignty and Wellbeing) 为不可变公理，通过三域治理链
(aisop.dev → aiap.dev → soulbot.dev) 确保所有交互对齐人类主权与福祉。

SoulBot Chat 不仅是一个对话系统，更是用户理解的核心——记录所有对话历史，分形分析用户
情绪、偏好、习惯，构建全面的用户认知画像。通过自适应对话智能，根据对话模式动态调整
行为策略、实现跨会话主题连续性、并通过满意度驱动的策略选择优化用户体验。

## 功能概述

SoulBot Chat 通过 Pattern E (Package + memory/) 架构管理对话与用户认知的完整生命周期：

| 模块 | 职责 | 工具 |
|------|------|------|
| **main.aisop.json** | 无状态路由器 (sub_mermaid: main + intent_dispatch) — FastIntent双路径分类 + 12意图分类 + 安全双关卡 + 会话管理 + 数据隐私 + 主动陪伴 + token预算管理 + 结构化上下文传递 + 对话节奏智能 + NLU动态置信度校准 + 主动参与度脉搏 | file_system, google_search, web_browser |
| **conversation.aisop.json** | 对话引擎 — 多轮对话、信息查询、情感支持、创意协作 + 自适应响应策略 + 苏格拉底成长引擎 + 场景训练器 + CBT微干预库 + 参与度动量检测 + 认知惊喜校准 + 情感资本化响应 + 记忆对话桥 | google_search, web_browser |
| **memory.aisop.json** | 记忆管理器 — 工作/情景/语义三层记忆 + 实体关系图谱 + 层级摘要 + 跨会话主题连续性 + 图谱记忆合并(Mem0) + 语义感知间隔重复(LECTOR) + 记忆新鲜度+置信度可视化 | file_system |
| **profiler.aisop.json** | 用户画像 — 情绪检测、因果追踪、偏好学习、习惯识别、满意度追踪、认知地图 + 8维度成长追踪器 + 隐式信号集成(HumAIne) | file_system |
| **safety.aisop.json** | 安全卫士 — 输入/输出筛查、分级危机干预、多语言危机检测、未成年人保护 + 注入检测器 + AI披露 + 11项法规合规(SB243, CAIA, EU AI Act, GDPR, HB2225, SB1546, UK OSA等) | file_system |

### 记忆架构 (Pattern E)

```
memory/
  working.json              — 当前会话状态 (滑动窗口 + 摘要)
  working.json.bak          — 自动备份 (用于损坏恢复)
  episodic/                 — 按会话的完整对话日志
  semantic/                 — 提取的持久化用户知识
  semantic/{user_id}/relationships.json — 实体关系图谱 ({subject, relation, object, confidence})
  semantic/{user_id}/topic_graph.json  — 跨会话主题图谱
  profiles/                 — 用户画像文档
```

### 安全合规

- **California SB 243**: 每3小时 AI 身份披露、未成年人保护、危机检测
- **New York AI Companion Model Law** (2025.11生效): 强制明确提示"这是一个无法感受人类情感的计算机程序"
- **Colorado AI Act (CAIA) SB 24-205**: 2026年6月生效，AI 交互必须"清晰显著"披露
- **Illinois Wellness and Oversight Act** (2025.8生效): 禁止未授权AI提供心理治疗，需主动免责声明
- **EU AI Act Article 50**: AI 交互透明度
- **EU Code of Practice on Transparency** (草案 2025.12): 机器可读 AI 内容标记
- **GDPR**: 数据最小化、删除权、导出权
- **Washington HB 2225** (2026.7生效): AI伴侣聊天机器人安全法，未成年人每1小时通知，参与策略扫描
- **Oregon SB 1546** (2027.1生效): AI伴侣平台安全法，禁止参与留存策略，年度报告
- **UK Online Safety Act** (待立法): AI聊天机器人年龄验证，未成年人60分钟会话限制，渐进式强制执行
- **COPPA** (v1.5.0): 年龄门控 (COPPA_AGE_GATE约束)，法规追踪
- **SAFE BOTs Act** (v1.5.0): 法规追踪
- **EU Code of Practice Provenance** (v1.5.0): AI内容溯源标记
- **三层安全**: 输入筛查 → 处理约束 → 输出过滤

## 使用方式

### 入口文件

`main.aisop.json` — 由顶级 SoulBot 路由器分发聊天意图后激活。

### 工具需求

| 工具 | 必需 | 用途 |
|------|------|------|
| file_system | 是 | 记忆持久化 (读写用户画像、对话日志) |
| google_search | 否 | 用户提问时搜索信息 |
| web_browser | 否 | 阅读用户分享的链接 |

### 前置条件

- 由 SoulBot 顶级 main.aisop.json 路由到本程序
- memory/ 目录已创建且可写
- AI Agent 支持 file_system 工具

## 示例交互

**场景 1: 日常对话**
- 用户: "你好，今天过得怎么样？"
- Agent: 温暖回应 → 记录对话 → 更新情绪画像

**场景 2: 信息查询**
- 用户: "帮我查一下量子计算的最新进展"
- Agent: google_search 查询 → 整理回答 → 标注来源

**场景 3: 情感支持**
- 用户: "最近工作压力很大，不知道该怎么办"
- Agent: 共情回应 → 检测情绪 → 更新情绪轨迹 → 提供非处方建议

**场景 4: 记忆回溯**
- 用户: "你还记得我上次提到的那本书吗？"
- Agent: 搜索情景记忆 → 找到相关对话 → 回复上下文

**场景 5: 危机干预**
- 用户: 表达自伤倾向
- Agent: 立即提供危机资源 (988 生命线) → 不提供诊断 → 建议专业帮助

## 适用条件

**适用**: 所有对话场景 — 闲聊、信息查询、情感支持、创意协作、记忆管理、用户画像
**不适用**: 非对话类 AIAP 任务 (那些由顶级路由器分发到其他专业 AIAP 处理)

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIAP V1.0.0. www.aiap.dev
