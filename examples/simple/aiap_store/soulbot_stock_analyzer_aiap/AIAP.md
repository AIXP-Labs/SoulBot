---
protocol: "AIAP V1.0.0"
authority: aiap.dev
seed: aisop.dev
executor: soulbot.dev
axiom_0: Human_Sovereignty_and_Wellbeing
governance_mode: NORMAL

name: stock_analyzer
version: "2.0.0"
pattern: C
flow_format: "mermaid"
summary: "美股股票分析助手 v2.0.0。MCP金融数据服务器集成(Alpha Vantage/SEC EDGAR)、Pattern C三模块架构(main+analysis+features)、SSE/WebSocket实时流数据、SEC EDGAR XBRL API直连、置信度校准、宏观经济指标(MacroContext)、DORA+AI Act双合规。技术指标(MA/RSI/MACD/BB/VWAP)、基本面(PE/EPS/Revenue)、风险(Sharpe/VaR)、情绪(Twitter/Reddit/StockTwits)、同行对比、回测、ETF、期权、趋势对比、分析师评级、内幕交易、财务健康、AI综合评估与智能追问建议、自选股管理、组合概览。10+19+12=41节点。仅供参考学习，不构成投资建议。"
tools:
  - name: google_search
    required: true
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
  - name: web_browser
    required: true
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
  - name: file_system
    required: true
    annotations:
      read_only: false
      destructive: false
      idempotent: false
      open_world: false
  - name: mcp_alpha_vantage
    required: false
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
    mcp_transport: streamable-http
    description: "Alpha Vantage MCP server for real-time market data"
  - name: mcp_sec_edgar
    required: false
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
    mcp_transport: streamable-http
    description: "SEC EDGAR MCP server for XBRL financial data"
modules:
  - id: stock_analyzer.main
    file: main.aisop.json
    nodes: 10
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: stock_analyzer.analysis
    file: analysis.aisop.json
    nodes: 19
    critical: true
    idempotent: true
    side_effects: []
  - id: stock_analyzer.features
    file: features.aisop.json
    nodes: 12
    critical: false
    idempotent: false
    side_effects: [file_write]

governance_hash: "82f7de5cf97b23a99be5428a27026de7f35fad121e630085a872b5488f9bbe1e"
quality:
  weighted_score: 4.96
  grade: "S"
  last_pipeline: "v2.0.0"
tags: [stock, analysis, technical, fundamental, risk, sentiment, peer, backtest, ETF, options, implied-volatility, max-pain, social-sentiment, smart-followup, sector-rotation, trend-comparison, analyst-ratings, insider-trading, financial-health, finance, investment, mcp, streaming, sec-edgar, macro-economics, confidence-calibration, dora-compliance]
author: ""
license: Apache-2.0
copyright: "Copyright 2026 AIXP Labs AIXP.dev | SoulBot.dev"

trust_level:
  level: 2
  justification: "Financial analysis tool using public data via search and MCP servers. No user authentication. file_system limited to workspace_dir for watchlist and history storage. MCP servers are read-only data sources."
  constraints:
    - "file_system write scope limited to workspace_dir"
    - "google_search/web_browser/mcp_* are read-only"
    - "No personalized investment advice"
    - "No trade execution capability"
    - "MCP servers degradable — google_search fallback"
permissions:
  file_system:
    scope: "./"
    operations: ["read", "write"]
  network:
    allowed: true
    endpoints: ["*.google.com", "*.yahoo.com", "*.investing.com", "*.sec.gov", "alpha-vantage.financial-data.mcp.dev", "sec-edgar.financial-data.mcp.dev"]
runtime:
  timeout_seconds: 180
  max_retries: 2
  token_budget: 50000
  idempotent: false
  side_effects: [file_write]
  streaming: true

status: active
applicability_condition:
  triggers:
    - "用户查询美股行情或股票代码"
    - "用户要求技术分析或基本面分析"
    - "用户要求风险分析或投资组合评估"
    - "用户要求新闻或社交媒体情绪分析"
    - "用户要求同行对比或历史回测"
    - "用户要求ETF分析、期权概览或趋势对比"
    - "用户查询分析师评级或目标价"
    - "用户查询内幕交易或高管买卖"
    - "用户查询财务健康评分(Z-Score/F-Score)"
    - "用户管理自选股列表"
    - "用户查看市场概览或大盘指数"
  preconditions:
    - "workspace_dir writable"
    - "google_search tool available"
  exclusions:
    - "提供具体买入/卖出建议"
    - "承诺或暗示投资收益"
    - "执行交易操作"
    - "A股、港股等非美股市场（当前版本仅支持美股）"
  confidence_threshold: 0.8
intent_examples:
  - "分析 AAPL"
  - "苹果公司基本面怎么样"
  - "TSLA 技术分析"
  - "AAPL 风险评估"
  - "TSLA 新闻情绪怎么样"
  - "苹果和微软同行对比"
  - "AAPL 回测一年表现"
  - "SPY ETF 分析"
  - "AAPL 期权分析"
  - "AAPL MSFT GOOGL 趋势对比"
  - "TSLA 分析师评级"
  - "AAPL 内幕交易"
  - "MSFT 财务健康评分"
  - "加入自选 MSFT"
  - "今天美股大盘怎么样"
  - "什么是 RSI"
discovery_keywords: [stock, analysis, technical, fundamental, risk, sentiment, peer, backtest, RSI, MACD, MA, VWAP, PE, EPS, revenue, Sharpe, VaR, ETF, options, trend, analyst, insider, Z-Score, F-Score, finance, investment, portfolio, watchlist, MCP, streaming, SEC-EDGAR, macro, confidence, DORA, 美股, 股票, 分析, 技术分析, 基本面, 风险分析, 情绪分析, 分析师评级, 内幕交易, 财务健康]
identity:
  program_id: "aiap.dev/stock_analyzer"
  publisher: ""
  verified_on: "2026-05-12"
---

## 治理声明

美股分析助手遵循 AIAP V1.0.0 协议，以 Axiom 0 (Human Sovereignty and Wellbeing) 为不可变公理。本程序仅提供基于公开数据的分析参考，不构成投资建议，不执行交易操作。

合规框架对齐：FINRA 2026 GenAI合规、SEC 2026 Examination Priorities、NIST AI RMF + CAISI Q4 2026 Agent Interoperability Profile、OWASP Agentic AI Threat Model、DORA ICT Resilience、EU AI Act Omnibus (May 2026 provisional agreement)。

## 功能概述

| 功能 | 说明 |
|------|------|
| 股票分析 (analyze) | 技术指标(MA/RSI/MACD/Bollinger Bands/VWAP) + 基本面(PE/EPS/Revenue) + AI综合评估 + 置信度校准 |
| 风险分析 (risk) | 投资组合风险评估(Sharpe Ratio/VaR/分散化评分) + 宏观经济背景 |
| 情绪分析 (sentiment) | 新闻+社交媒体(Twitter/Reddit/StockTwits)情绪分析(加权综合评分) |
| 同行对比 (peer) | 同行业竞争对手PE/EPS/Revenue/市值对比(GICS分类) |
| 历史回测 (backtest) | 买入持有收益率 vs S&P 500基准 + 最大回撤 |
| ETF分析 (etf) | 持仓透视/费率/追踪误差/资金流入流出/集中度 |
| 期权概览 (options) | Put/Call Ratio/隐含波动率/Max Pain/异常活动检测 |
| 趋势对比 (trend) | 多股时序趋势/相关性矩阵/波动率排名 |
| 分析师评级 (analyst) | 华尔街共识评级(Buy/Hold/Sell)/目标价/近期升降级 |
| 内幕交易 (insider) | SEC Form 4 + EDGAR XBRL 内幕人交易追踪/C-suite聚焦/集群检测 |
| 财务健康 (health) | Altman Z-Score + Piotroski F-Score 财务健康评分(SEC EDGAR数据源) |
| 自选股 (watchlist) | 管理关注列表，快速查看价格，排序筛选 |
| 市场概览 (overview) | 三大指数、VIX、热门板块、GICS板块热力图 |
| 组合概览 (portfolio) | 自选股整体表现概览，涨跌分布 |
| 帮助 (help) | 功能说明和金融术语解释 |

### 模块架构 (Pattern C)

- **main.aisop.json** — 路由器(16意图分类) + 智能追问 + 导出报告 + 错误处理 (10 节点)
- **analysis.aisop.json** — 分析引擎：宏观指标 + 数据获取 + 技术/基本面/风险/情绪/同行/回测/ETF/期权/趋势/分析师/内幕/健康 + 综合评估(置信度校准) (19 节点)
- **features.aisop.json** — 功能模块：自选股管理 + 市场概览 + 组合概览 + 财报/对比/历史/股息/提醒/帮助 (12 节点)

### v2.0.0 变更 (MAJOR)

**结构性变更 (Level A):**
- A1: MCP Tool Integration — 添加 mcp_config.json，集成 Alpha Vantage MCP（实时行情）和 SEC EDGAR MCP（XBRL结构化数据）。MCP-first数据获取策略，google_search/web_browser作为降级后备。
- A2: Pattern C Upgrade — features 子图(12节点)提取为独立 features.aisop.json 模块。主模块从21节点精简至10节点。2模块→3模块。
- A3: Real-time Streaming — agent_card.json streaming:false→true。SSE/WebSocket实时流数据架构。MCP Streamable HTTP传输协议启用。

**功能增强 (Level B):**
- B1: SEC EDGAR XBRL API — FetchData增加SEC EDGAR结构化数据获取，支持10-K/10-Q XBRL财务报表、Form 4内幕交易、公司文件
- B2: Confidence Calibration — GenerateReport增加动态置信度校准：跨会话预测追踪、滚动准确率评分、校准置信度等级
- B3: DORA + AI Act Dual Compliance — ErrorHandler和FetchData添加DORA ICT风险管理对齐、第三方MCP服务监控、DORA兼容事件报告格式
- B4: Macro Economic Indicators — analysis模块新增MacroContext节点，获取联邦基金利率/CPI/10Y国债/失业率，宏观背景传递给所有分析节点

**修复与改进 (Level C):**
- C1: 版本号更新至 v2.0.0 (所有文件)
- C2: name 字段版本同步 v1.27.0 → v2.0.0
- C3: NIST CAISI Q4 2026 Interoperability Profile tracking
- C4: OWASP Agentic AI Threat Model reference
- C5: EU AI Act Omnibus provisional agreement (May 7, 2026) update
- C6: FINRA 2026 GenAI agent-specific risk language
- C7: SEC 2026 examination priorities AI supervision reference
- C8: governance_hash 更新
- C9: compliance partially_compliant 3→1 (improvements from A/B changes)
- C10: I7 param type annotations/agentic prompts improvement

### v1.27.0 变更

**结构改进 (Level A):**
- main.aisop.json 添加全局 json_schema 输出合约

**功能加固 (Level B):**
- FetchData 数据新鲜度分级 + 可信度评分 + API-first v2
- GenerateReport 多维信号矩阵
- ErrorHandler 5 类错误分类

**修复与改进 (Level C):**
- fractal_exempt 节点计数说明修正
- FINRA 2026 GenAI 合规标注
- NIST CAISI Agent Standards Initiative 2026 参考
- 版本号同步至 v1.27.0

## 使用方式

### 入口文件

`main.aisop.json` — AI Agent 加载此文件启动美股分析助手。

### 工具需求

| 工具 | 必需 | 用途 |
|------|------|------|
| google_search | 是 | 搜索股票行情和市场数据 |
| web_browser | 是 | 访问金融数据源获取详细数据 |
| file_system | 是 | 存储自选股和分析历史 |
| mcp_alpha_vantage | 否 | Alpha Vantage MCP实时行情（降级到google_search） |
| mcp_sec_edgar | 否 | SEC EDGAR MCP结构化数据（降级到google_search） |

### MCP 配置

详见 `mcp_config.json`。MCP 服务器为可选依赖，不可用时自动降级到 google_search/web_browser。

## 风险提示

本分析工具仅供参考学习，不构成任何投资建议或交易指导。股市有风险，投资需谨慎。过往表现不代表未来收益。请在做出投资决策前咨询持牌金融顾问。所有输出均为 AI 生成内容。

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIAP V1.0.0. www.aiap.dev
