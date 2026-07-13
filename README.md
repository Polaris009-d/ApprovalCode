# ApprovalCode

> 企业级 6-Agent 智能合同审批平台 — 规则引擎优先 + Phase 编排

## 架构概览

```
用户上传合同 PDF
      |
      v
Phase 0: Investigation Agent (合同解析 + 权利义务矩阵)
Phase 1: Risk Pattern Agent (规则引擎优先: 13个关键词模式扫描)
Phase 2: Legal Citation Agent (风险 -> 法条映射 + 第一性原理解释)
Phase 3: Evidence Agent (结构化证据: 原文+坐标+置信度+建议)
Phase 4: Risk Decision Agent (多维评分 + 强制升级)
      |
      v
审批报告 (LOW/MEDIUM/HIGH/CRITICAL)
```

## 快速启动



### 启动后端

```bash
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 启动前端

```bash
cd frontend
npx vite --port 3000
```

打开 http://localhost:3000

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload/ocr` | 上传合同 OCR 识别 |
| POST | `/approval/start` | 发起审批 (SSE 流式) |
| POST | `/approval/{id}/approve` | 审批通过 |
| POST | `/approval/{id}/reject` | 驳回修改 |
| GET | `/history` | 审查记录列表 |
| GET | `/legal-kb` | 法律知识库 (CRUD) |
| GET | `/tools` | 工具列表 + 调用统计 |
| GET | `/agents/status` | Agent 状态 |
| GET | `/health` | 健康检查 |

## Agent 体系

| Agent | 工具 | 说明 |
|-------|------|------|
| Master | dispatch_subagent, generate_report | Phase 编排 |
| Investigation | build_obligation_matrix | 合同解析 + 权利义务矩阵 |
| Risk Pattern | scan_risk_patterns | 规则引擎: 13 关键词模式 |
| Legal Citation | search_law | 风险 -> 法条映射 (PostgreSQL) |
| Evidence | generate_evidence | 结构化证据生成 |
| Risk Decision | risk_score | 多维评分 + 强制升级 |

## 风险模式库

| 模式 | 等级 | 关键词示例 |
|------|------|------------|
| PAYMENT_INDEFINITE_EXTENSION | CRITICAL | 无限期顺延、内部流程不算违约 |
| BUYER_NON_PAYMENT_EXEMPTION | CRITICAL | 不付款不算违约、暂缓支付 |
| INVOICE_BEFORE_PAYMENT_TRAP | CRITICAL | 先开全额发票否则拒绝付款 |
| UNILATERAL_ACCEPTANCE_ORAL | CRITICAL | 验收标准口头说了算 |
| UNILATERAL_TERMINATION_NO_COMPENSATION | CRITICAL | 无理由解除不赔偿 |
| EXCESSIVE_LATE_PENALTY | HIGH | 晚X分钟扣X%货款 |
| SUPER_LONG_PAYMENT_TERM | HIGH | X天审核+X工作日支付 |
| ... | ... | ... |

## 强制升级规则

| 条件 | 评分 |
|------|------|
| >=5 CRITICAL | 强制 95 分 (CRITICAL) |
| >=3 CRITICAL | 强制 80 分 (HIGH) |
| >=1 CRITICAL | 强制 55 分 (MEDIUM) |
| 风险>0 | 需要人工复核 |

## 项目结构

```
ApprovalCode/
├── docs/
│   ├── APPROVAL_PLATFORM_ARCHITECTURE.md  # 架构文档
│   └── RESUME_PROJECT.md                  # 项目简历
├── backend/
│   ├── .env                               # 环境配置
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                        # FastAPI 入口 (20 API)
│   │   ├── config.py
│   │   ├── agents/
│   │   │   ├── base_agent.py              # ReAct 基类
│   │   │   ├── master_agent.py            # Phase 编排
│   │   │   ├── sub_agents.py              # 5 个子 Agent
│   │   │   └── reasoning_engine.py        # LLM 推理引擎
│   │   ├── tools/
│   │   │   ├── base_tool.py
│   │   │   ├── registry.py                # 20 工具注册
│   │   │   └── builtin/
│   │   │       ├── ocr.py                 # Baidu OCR
│   │   │       ├── compliance.py          # 法条检索
│   │   │       ├── risk.py                # 评分工具
│   │   │       ├── reasoning.py           # 论证 + 辩论
│   │   │       ├── risk_patterns.py       # 风险模式库
│   │   │       └── field_extract.py
│   │   ├── memory/
│   │   │   ├── short_term.py              # Redis
│   │   │   ├── long_term.py               # PostgreSQL
│   │   │   └── legal_kb.py                # 法律知识库
│   │   ├── security/rule_engine.py
│   │   ├── models/schemas.py              # Pydantic 模型
│   │   └── observability/audit.py
│   └── uploads/
├── frontend/
│   ├── src/
│   │   ├── App.vue                        # 主布局 + 侧边栏
│   │   ├── router.js                      # 5 页面路由
│   │   └── views/
│   │       ├── Dashboard.vue              # 工作台
│   │       ├── ReviewPage.vue             # 智能审查 (3 Step)
│   │       ├── PendingReviews.vue         # 待审批列表
│   │       ├── History.vue                # 审查记录 + 详情
│   │       ├── LegalKBPage.vue            # 法律知识库管理
│   │       └── AgentMonitor.vue           # Agent 监控 (实时)
│   └── package.json
└── README.md
```
