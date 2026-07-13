# ApprovalCode 最终架构设计

> 参考: Claude Code Agent Architecture
> 核心原则: 规则引擎优先，LLM 做语义解释

## 1. Agent 架构

```
Master Agent (Phase 编排)
  |
  Phase 0: Investigation Agent (合同解析 + 义务矩阵)
  |   build_obligation_matrix -> DeepSeek 构建权利义务矩阵
  |
  Phase 1: Risk Pattern Agent (规则引擎优先)
  |   scan_risk_patterns -> 13 关键词模式确定性扫描 + LLM 语义补充
  |
  Phase 2: Legal Citation Agent (法条映射)
  |   search_law -> PostgreSQL 含第一性原理 + 法条关系图
  |
  Phase 3: Evidence Agent (证据生成)
  |   generate_evidence -> 原文 + OCR坐标 + 置信度 + 建议
  |
  Phase 4: Risk Decision Agent (多维评分 + 强制升级)
      risk_score -> 金额 + 模式命中 + 敏感条款
```

## 2. 风险模式库

| 模式ID | 等级 | 说明 |
|--------|------|------|
| PAYMENT_INDEFINITE_EXTENSION | CRITICAL | 无限期顺延付款且免责 |
| BUYER_NON_PAYMENT_EXEMPTION | CRITICAL | 甲方不付款不算违约 |
| INVOICE_BEFORE_PAYMENT_TRAP | CRITICAL | 先票后款资金占用陷阱 |
| UNILATERAL_ACCEPTANCE_ORAL | CRITICAL | 验收标准口头决定 |
| UNILATERAL_TERMINATION | CRITICAL | 无理由解除不赔偿 |
| EXCESSIVE_LATE_PENALTY | HIGH | 延期处罚畸高 |
| SUPER_LONG_PAYMENT_TERM | HIGH | 超长付款周期 |
| QUALITY_UNLIMITED_LIABILITY | HIGH | 质量责任无限延长 |
| LIABILITY_AFTER_DELIVERY | HIGH | 交付后责任倒挂 |
| DISPUTE_UNFAIR_FORUM | HIGH | 争议地点不公 |
| ... | ... | ... |

## 3. 强制升级规则

- >=5 CRITICAL -> 强制 95 分 (CRITICAL)
- >=3 CRITICAL -> 强制 80 分 (HIGH)
- >=1 CRITICAL -> 强制 55 分 (MEDIUM)
- 风险 > 0 -> 需要人工复核 (status=pending)

## 4. 评分公式

```
总分 = 金额因子(0-40) + 模式命中(0-60) + 敏感条款(0-20)
```

法条引用不参与评分，仅作为审查报告中的法律依据展示。

## 5. 法律知识库

PostgreSQL 存储，14 条法条：

- clause_id, title, content
- first_principles (每条法条的根本原理)
- relationships (法条间关系: supplements/conflicts/overrides)
- precedent_weight (判例权重 1-5)

## 6. 工具注册

20 个工具，调用次数/成功率/平均耗时实时统计，内存计数 + API 暴露。

## 7. 前端页面

| 页面 | 路由 | 说明 |
|------|------|------|
| 工作台 | / | 统计卡片 + 待审批 + 最近通过 |
| 智能审查 | /review | 3-Step: 上传OCR -> 审查进度 -> 结果+审批 |
| 待审批 | /pending | 需要人工复核的任务 |
| 审查记录 | /history | 全部记录 + 详情弹窗 |
| 法律库 | /legal-kb | CRUD + 第一性原理展示 |
| Agent监控 | /agents | 6 Agent + 20 工具实时统计 |
