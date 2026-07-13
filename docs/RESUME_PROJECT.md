#  企业级多Agent智能合同审批平台

## 项目信息

- 项目时间: 2025.11 - 2026.07
- 角色: 独立开发
- 技术栈: FastAPI, Redis, PostgreSQL, Vue2, SSE, DeepSeek V4 Pro, Baidu OCR, PyMuPDF, Pydantic

## 项目描述

为解决传统合同审批人工周期长、法务成本高的问题，参考 Claude Code subagent 架构，设计并实现基于 6-Agent 协作的智能合同审批系统。系统可在 30 秒内完成全文 OCR、风险模式扫描、法律法条映射和综合风险评估，对高风险条款自动标红预警并强制人工复核。

## 核心技术亮点

### 1. 6-Agent Phase 编排架构

参考 Claude Code 的 subagent 体系，6 个专职 Agent 按确定性 Phase 编排，每个 Agent 内部遵循 ReAct 循环：

- Master Agent: Phase 状态机调度，确定性编排
- Investigation Agent: 合同全文解析 + 权利义务矩阵构建 (DeepSeek)
- Risk Pattern Agent: 规则引擎优先，13 个关键词模式确定性扫描 + LLM 语义补充
- Legal Citation Agent: 已发现风险映射到法条 + 第一性原理解释 (PostgreSQL)
- Evidence Agent: 风险转为结构化证据（原文+OCR位置+置信度+修改建议）
- Risk Decision Agent: 多维评分 + 强制升级规则

### 2. 风险模式库 - 规则引擎优先

不靠法律辩论发现风险，而是确定性规则先扫出所有风险信号：

- 13 个 CRITICAL/HIGH 风险模式：无限期付款、甲方免责、先票后款陷阱、单方口头验收、无理由解约、畸高违约金、责任倒挂等
- 规则命中确定性扫描，LLM 语义补充，置信度 >= 0.95
- 强制升级规则：>=5 CRITICAL 强制 95 分，>=3 强制 80 分，>=1 强制 55 分
- 实测：一份含 10+ 霸王条款的采购合同，识别 5 CRITICAL + 7 HIGH，评分 95

### 3. 法律知识库 - PostgreSQL + 第一性原理

14 条法条存储于 PostgreSQL，每条含第一性原理（如"违约责任核心在于填平而非惩罚"）、法条关系图（supplements/conflicts/overrides/basis_for）、判例权重(1-5)。前端可增删改查。

### 4. 合同 OCR - 百度云 + DeepSeek V4 Pro

Baidu OCR 高精度版提取全文 + 段落级坐标。PyMuPDF 直接提取 PDF 文本，扫描件转 PNG 后 OCR。DeepSeek 从 OCR 文字提取 7 个结构化字段（含合同类型自动判断）。OCR 坐标映射到合同图片，蓝色标注一致字段，红色标注不一致字段。

### 5. 全链路可观测

20 个注册工具，每次调用实时计数。SSE 实时推送 6 Agent 推理进度。前端时间轴步骤级回放，每条风险含原文证据 + 置信度 + OCR 坐标。

### 6. 评分体系

三维评分：金额因子(0-40) + 风险模式命中(0-60) + 敏感条款(0-20)。强制升级：CRITICAL>=5 强制 95 分。风险>0 即需人工复核，状态为 pending。

## 核心数据

| 指标 | 数值 |
|------|------|
| Agent 数量 | 6（Master + Investigation + Risk Pattern + Legal Citation + Evidence + Risk Decision） |
| 工具数量 | 20 个 |
| 法律知识库 | 14 条法条（含第一性原理 + 法条关系 + 判例权重） |
| 风险模式库 | 13 个关键词模式（6 CRITICAL + 7 HIGH） |
| 前端页面 | 5 页面（工作台 + 智能审查 + 待审批 + 审查记录 + 法律库管理 + Agent 监控） |
| 技术架构 | FastAPI + Vue2 + Redis + PostgreSQL + SSE 流式 |
