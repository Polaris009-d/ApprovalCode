"""
ApprovalCode — FastAPI 入口
企业级多 Agent 智能审批平台 API
"""
import asyncio, json, os, base64, httpx
from datetime import datetime
from contextlib import asynccontextmanager


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import settings
from .models.schemas import ApprovalTask, ApprovalReport
from .agents.master_agent import MasterAgent
from .agents.reasoning_engine import ReasoningEngine
from .tools.registry import registry
from .tools.builtin.field_extract import ExtractFieldsTool
from .tools.builtin.compliance import SearchLawTool, CiteClauseTool, CrossValidateTool
from .tools.builtin.risk_patterns import ScanRiskPatternsTool, BuildObligationMatrixTool, GenerateEvidenceTool
from .tools.builtin.ocr import ocr_contract, BaiduOCRTool
from .tools.builtin.reasoning import (InvestigateFactsTool, ConstructArgumentTool,
    AdversarialReviewTool, NegotiateTool, FinancialAnalysisTool,
    PlaintiffAgentTool, DefendantAgentTool, JudgeAgentTool)
from .tools.builtin.risk import RiskScoreTool, SuspendNodeTool, ApproveNodeTool, GenerateReportTool
from .security.rule_engine import RuleEngine
from .memory.short_term import ShortTermMemory
from .memory.long_term import LongTermMemory
from .memory.legal_kb import legal_kb, LegalKBCreate
from .observability.audit import AuditLogger


# ═══════════════ 全局服务 ═══════════════

master_agent: Optional[MasterAgent] = None
memory: Optional[ShortTermMemory] = None
long_memory: Optional[LongTermMemory] = None
rule_engine: Optional[RuleEngine] = None
audit: Optional[AuditLogger] = None

# 运行时统计
_task_stats = {"processed": 0, "suspended": 0, "total_latency": 0.0, "auto_passed": 0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global master_agent, memory, long_memory, rule_engine, audit

    memory = ShortTermMemory()
    long_memory = LongTermMemory()
    rule_engine = RuleEngine()
    audit = AuditLogger()
    reasoner = ReasoningEngine()

    registry.register(ExtractFieldsTool())
    registry.register(BaiduOCRTool())
    registry.register(InvestigateFactsTool())
    registry.register(ConstructArgumentTool())
    registry.register(AdversarialReviewTool())
    registry.register(NegotiateTool())
    registry.register(FinancialAnalysisTool())
    registry.register(PlaintiffAgentTool())
    registry.register(DefendantAgentTool())
    registry.register(JudgeAgentTool())
    registry.register(ScanRiskPatternsTool())
    registry.register(BuildObligationMatrixTool())
    registry.register(GenerateEvidenceTool())
    registry.register(CrossValidateTool())
    registry.register(SearchLawTool())
    registry.register(CiteClauseTool())
    registry.register(RiskScoreTool())
    registry.register(SuspendNodeTool())
    registry.register(ApproveNodeTool())
    registry.register(GenerateReportTool())

    master_agent = MasterAgent(
        tools=registry, memory=memory, rule_engine=rule_engine,
        audit=audit, reasoning=reasoner,
    )

    print(f"[ApprovalCode] Started. Tools: {registry.get_available_tools()}")
    kb_stats = await legal_kb.stats()
    print(f"[ApprovalCode] Legal KB: {kb_stats['total']} clauses loaded from PostgreSQL")
    yield
    print("[ApprovalCode] Shutting down")


app = FastAPI(
    title="ApprovalCode",
    description="企业级多 Agent 智能审批平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ═══════════════ Health ═══════════════

@app.get("/health")
async def health():
    kb_stats = await legal_kb.stats()
    # 从 DB 查真实统计数据
    pending = approved = rejected = 0
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            pending = await conn.fetchval("SELECT COUNT(*) FROM approval_reports WHERE status='pending'") or 0
            approved = await conn.fetchval("SELECT COUNT(*) FROM approval_reports WHERE status='approved'") or 0
            rejected = await conn.fetchval("SELECT COUNT(*) FROM approval_reports WHERE status='rejected'") or 0
    except: pass
    total = pending + approved + rejected
    auto_rate = round(approved / max(total, 1) * 100, 1)
    avg_lat = 0
    latest_latency = 0
    try:
        async with pool.acquire() as conn:
            avg_lat = await conn.fetchval("SELECT COALESCE(AVG((report_data->>'total_latency_ms')::float),0) FROM approval_reports") or 0
            latest = await conn.fetchrow("SELECT report_data->>'total_latency_ms' as lt FROM approval_reports ORDER BY created_at DESC LIMIT 1")
            if latest and latest['lt']: latest_latency = round(float(latest['lt']) / 1000, 1)
    except: pass
    return {
        "status": "ok", "app": settings.APP_NAME,
        "tools": registry.get_available_tools(),
        "agent": master_agent.agent_id if master_agent else None,
        "tasks_pending": pending,
        "tasks_approved": approved,
        "tasks_rejected": rejected,
        "tasks_total": total,
        "auto_rate": auto_rate,
        "avg_latency": round(avg_lat / 1000, 2),
        "latest_latency": latest_latency,
        "legal_kb_total": kb_stats["total"],
    }


# ═══════════════ 法律知识库 API ═══════════════

@app.get("/legal-kb")
async def get_legal_clauses(contract_type: str = "", keyword: str = ""):
    clauses = await legal_kb.get_all(contract_type=contract_type or None, keyword=keyword or None)
    return {"clauses": [c.model_dump() for c in clauses], "total": len(clauses)}


@app.get("/legal-kb/stats")
async def get_legal_stats():
    return await legal_kb.stats()


@app.post("/legal-kb")
async def add_legal_clause(item: LegalKBCreate):
    try:
        clause = await legal_kb.add(item)
        return clause.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.put("/legal-kb/{clause_id}")
async def update_legal_clause(clause_id: str, item: LegalKBCreate):
    result = await legal_kb.update(clause_id, item)
    if result is None:
        raise HTTPException(status_code=404, detail="法条不存在")
    return result.model_dump()


@app.delete("/legal-kb/{clause_id}")
async def delete_legal_clause(clause_id: str):
    ok = await legal_kb.delete(clause_id)
    if not ok:
        raise HTTPException(status_code=404, detail="法条不存在")
    return {"ok": True}


# ═══════════════ 文件上传 + 多模态 OCR ═══════════════

@app.post("/upload/ocr")
async def upload_and_ocr(file: UploadFile = File(...), contract_type: str = Form("purchase")):
    """上传合同并 OCR 提取字段"""
    allowed = {'.pdf', '.jpg', '.jpeg', '.png'}
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"不支持的文件格式: {ext}")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "文件不能超过 20MB")

    # 保存到临时文件
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, file.filename or "contract.pdf")
    with open(filepath, "wb") as f:
        f.write(content)

    # 调用多模态 OCR
    ocr_data = await _ocr_contract(filepath, contract_type, content, ext)
    return {
        "filename": file.filename, "filepath": filepath,
        "fields": ocr_data.get("fields", {}),
        "positions": ocr_data.get("positions", []),
        "image_base64": ocr_data.get("image_base64", ""),
        "full_text": ocr_data.get("full_text", ""),
    }


async def _ocr_contract(filepath: str, contract_type: str, content: bytes, ext: str) -> dict:
    """
    合同字段提取 — PDF 文本提取 / 百度 OCR + DeepSeek。
    返回: {fields, positions(段落级), image_base64, full_text}
    """
    # 图片预览: PDF 转 PNG 首页，图片直接用
    if ext == '.pdf':
        img_bytes = _pdf_first_page_image(content)
        image_b64 = base64.b64encode(img_bytes).decode() if img_bytes else base64.b64encode(content).decode()
    else:
        image_b64 = base64.b64encode(content).decode()

    full_text = ""
    ocr_positions = []

    # Step 1: 提取文字 — PDF 直接读文本，图片用百度 OCR
    if ext == '.pdf':
        full_text, ocr_positions = _extract_pdf_text(content)
        if not full_text:
            # PDF 是扫描件 — 转图片后 OCR
            images = _pdf_to_images(content)
            for img_bytes in images:
                img_result = await ocr_contract(img_bytes, '.png')
                if isinstance(img_result, dict):
                    ft = img_result.get("full_text", "")
                    if ft:
                        full_text += ft + "\n"
                        ocr_positions.extend(img_result.get("positions", []))
    else:
        ocr_result = await ocr_contract(content, ext)
        if isinstance(ocr_result, dict):
            full_text = ocr_result.get("full_text", "")
            ocr_positions = ocr_result.get("positions", [])

    if not full_text:
        return {"fields": _rule_based_extract(contract_type), "positions": [], "image_base64": image_b64, "full_text": ""}

    # Step 2: DeepSeek 提取结构化字段
    fields = _rule_based_extract(contract_type)
    if settings.LLM_API_KEY:
        prompt = f"""你是一个合同信息提取助手。从以下 OCR 文字中提取字段，返回严格JSON。

{{
  "party_a": "甲方/委托方/买方公司全称",
  "party_b": "乙方/服务方/供应方公司全称",
  "amount": "合同总金额(含数字和单位)",
  "date": "签订日期(YYYY-MM-DD)",
  "payment_period": "付款方式/周期",
  "subject": "服务内容/标的物摘要",
  "contract_type": "合同类型(仅返回: purchase/service/lease/labor)"
}}

规则: 每个字段必填，找不到填""。金额去逗号留单位。日期统一YYYY-MM-DD。
contract_type根据合同内容判断: 采购合同=purchase, 服务合同=service, 租赁合同=lease, 劳动合同=labor。
只返回JSON，禁止任何解释。

OCR文字:
{full_text}"""
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    f"{settings.LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"},
                    json={"model": settings.LLM_MODEL, "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 800, "temperature": 0},
                )
                if resp.status_code == 200:
                    raw = resp.json()["choices"][0]["message"]["content"]
                    fields = _parse_deepseek_json(raw)
                    print(f"[OCR] DeepSeek extracted: {json.dumps(fields, ensure_ascii=False)}")
        except Exception as e:
            print(f"[OCR] DeepSeek error: {e}")

    # Step 3: 段落级位置匹配（整行匹配，不用前缀截断）
    field_positions = _match_fields_to_positions(fields, ocr_positions, full_text)
    print(f"[OCR] Position matches: {len(field_positions)}/{len(fields)} fields")

    return {"fields": fields, "positions": field_positions, "image_base64": image_b64, "full_text": full_text}


def _parse_deepseek_json(raw: str) -> dict:
    """解析 DeepSeek 返回的 JSON，多级容错"""
    text = raw.strip()
    # 去掉 markdown 包裹
    for tag in ["```json", "```"]:
        if tag in text:
            text = text.split(tag, 1)[-1]
            if text.endswith("```"):
                text = text[:-3]
            break
    text = text.strip()
    # 尝试解析
    for attempt in range(3):
        try:
            parsed = json.loads(text)
            return {k: str(v).strip() if v else "" for k, v in parsed.items()}
        except json.JSONDecodeError:
            # 尝试修复: 找到最后一个完整的花括号对
            if attempt == 0:
                idx = text.rfind('}')
                if idx > 0:
                    text = text[:idx+1]
            elif attempt == 1:
                # 尝试添加缺失的结尾花括号
                if text.startswith('{') and not text.endswith('}'):
                    text = text + '}'
    # 全失败
    print(f"[OCR] JSON parse failed for: {raw[:300]}")
    return {}


def _match_fields_to_positions(fields: dict, positions: list, full_text: str) -> list:
    """
    将字段值匹配到 OCR 位置坐标。
    策略:
    1. 精确匹配: 字段值整体在某行文字中
    2. 关键字符匹配: 提取字段值的前几个有意义字符匹配
    3. 关键词邻近匹配: 根据"甲方""乙方""金额"等关键词找邻近区域
    """
    result = []
    field_keywords = {
        "party_a": ["甲方", "委托方", "买方"],
        "party_b": ["乙方", "服务方", "供应方"],
        "amount": ["金额", "合同金额", "人民币", "大写"],
        "date": ["签订日期", "日期", "签署日期"],
        "payment_period": ["付款周期", "付款方式", "支付"],
        "subject": ["服务内容", "标的", "服务范围"],
    }

    for key, val in fields.items():
        if not val or not val.strip():
            continue

        # 策略1: 值整体出现在某行
        found = False
        for pos in positions:
            ptext = pos.get("text", "")
            if val in ptext or (len(val) > 4 and val[:6] in ptext):
                result.append({"field": key, "value": val,
                               "top": pos["top"], "left": pos["left"],
                               "width": pos["width"], "height": pos["height"],
                               "text": ptext})
                found = True
                break

        # 策略2: 关键词邻近 — 找关键词所在行，取该行的坐标
        if not found:
            for kw in field_keywords.get(key, []):
                for pos in positions:
                    if kw in pos.get("text", ""):
                        # 扩展到邻近行形成标注区域
                        result.append({"field": key, "value": val,
                                       "top": pos["top"], "left": pos["left"],
                                       "width": max(pos["width"], 200),
                                       "height": max(pos["height"], 24),
                                       "text": f"{kw}: {val}"})
                        found = True
                        break
                if found:
                    break

        # 策略3: 值的前3个字符
        if not found and len(val) >= 3:
            prefix = val[:3]
            for pos in positions:
                if prefix in pos.get("text", ""):
                    result.append({"field": key, "value": val,
                                   "top": pos["top"], "left": pos["left"],
                                   "width": pos["width"], "height": pos["height"],
                                   "text": pos.get("text", "")})
                    break

    return result


def _rule_based_extract(contract_type: str) -> dict:
    """无 API key 时的规则提取"""
    templates = {
        "purchase": {"party_a": "", "party_b": "", "amount": "", "date": "", "payment_period": "30天", "subject": "", "contract_type": "purchase"},
        "service": {"party_a": "", "party_b": "", "amount": "", "date": "", "payment_period": "按里程碑", "subject": "", "contract_type": "service"},
        "lease": {"party_a": "", "party_b": "", "amount": "", "date": "", "payment_period": "月付", "subject": "", "contract_type": "lease"},
        "labor": {"party_a": "", "party_b": "", "amount": "", "date": "", "payment_period": "月薪", "subject": "", "contract_type": "labor"},
    }
    return templates.get(contract_type, templates["purchase"])


# ═══════════════ 审批 API ═══════════════

@app.post("/approval/start")
async def start_approval(
    file: Optional[UploadFile] = File(None),
    contract_type: str = Form("purchase"),
    user_input: str = Form("{}"),
    stream: bool = Form(True),
):
    """发起审批任务 — 支持文件上传 + SSE 流式输出"""
    user_data = json.loads(user_input) if isinstance(user_input, str) else user_input

    contract_files = []
    if file:
        upload_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, file.filename or "contract.pdf")
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        contract_files.append(filepath)

        # 先 OCR
        ext = os.path.splitext(file.filename or '')[1].lower()
        ocr_data = await _ocr_contract(filepath, contract_type, content, ext)
        user_data["_ocr_data"] = ocr_data
        user_data["_ocr_fields"] = ocr_data.get("fields", {})

    task = ApprovalTask(
        contract_type=contract_type,
        contract_files=contract_files,
        user_input=user_data,
        stream=stream,
    )

    if stream:
        return StreamingResponse(_stream_approval(task), media_type="text/event-stream")
    else:
        report = await master_agent.execute(task, {})
        return report[0].model_dump()


async def _stream_approval(task: ApprovalTask):
    context = {"task": task, "start_time": __import__("time").perf_counter()}
    yield f"data: {json.dumps({'type': 'start', 'task_id': task.task_id})}\n\n"

    try:
        result = await master_agent.execute(task, context)
        report, traces = result
        _task_stats["processed"] += 1
        _task_stats["total_latency"] += (__import__("time").perf_counter() - context["start_time"]) * 1000
        rl = report.risk_level if hasattr(report, 'risk_level') else report.get('risk_level', 'LOW') if isinstance(report, dict) else 'LOW'
        needs_review = report.status == "needs_review" if hasattr(report, 'status') else (rl not in ("LOW",) or (float(report.risk_score if hasattr(report, 'risk_score') else report.get('risk_score', 0) if isinstance(report, dict) else 0)) > 0)

        # 保存到 PostgreSQL
        try:
            import asyncpg as apg
            rd = report.model_dump(mode='json') if hasattr(report, 'model_dump') else report
            # 附上 OCR 数据 + 用户表单字段
            task_obj = context.get("task") if isinstance(context, dict) else None
            ocr_data = {}
            if task_obj and hasattr(task_obj, 'user_input'):
                ocr_data = task_obj.user_input.get("_ocr_data", {})
                for k in ('amount','party_a','party_b','date','payment_period','contract_type'):
                    rd['form_' + k] = str(task_obj.user_input.get(k, ''))
            if isinstance(ocr_data, dict):
                rd["_ocr_fields"] = ocr_data.get("fields", {})
                rd["_ocr_positions"] = ocr_data.get("positions", [])
                rd["_ocr_image"] = ocr_data.get("image_base64", "")
            pool = await _get_pool()
            async with pool.acquire() as conn:
                print(f"[DB] Saving report {task.task_id}...")
                await conn.execute('''
                    INSERT INTO approval_reports (task_id, contract_type, status, risk_score, risk_level, citations_count, mismatch_count, review_summary, report_data)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)
                    ON CONFLICT (task_id) DO UPDATE SET status=$3, risk_score=$4, risk_level=$5, updated_at=NOW()
                ''', task.task_id, task.contract_type, 'pending' if needs_review else 'approved',
                   float(rd.get('risk_score', 0) if isinstance(rd, dict) else 0),
                   str(rd.get('risk_level', 'LOW') if isinstance(rd, dict) else 'LOW'),
                   len(rd.get('citations', []) if isinstance(rd, (dict, list)) else ([rd.get('citations')] if rd.get('citations') else [])),
                   len(rd.get('mismatch_fields', []) if isinstance(rd, (dict, list)) else []),
                   str(rd.get('review_summary', '') if isinstance(rd, dict) else '')[:500],
                   json.dumps(rd, default=str) if isinstance(rd, dict) else json.dumps({}))
        except Exception as e:
            import traceback
            print(f"[DB] Failed to save report: {e}")
            traceback.print_exc()
        if rl != "HIGH":
            _task_stats["auto_passed"] += 1
        else:
            _task_stats["suspended"] += 1
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        return

    for step in traces:
        sd = step.model_dump(mode='json') if hasattr(step, 'model_dump') else step
        yield f"data: {json.dumps({'type': 'step', 'data': sd}, default=str)}\n\n"
        await asyncio.sleep(0.01)

    report_data = report.model_dump(mode='json') if hasattr(report, 'model_dump') else report
    # 附上 OCR 位置数据和图片
    task_obj = context.get("task") if isinstance(context, dict) else None
    ocr_data = {}
    if task_obj and hasattr(task_obj, 'user_input'):
        ocr_data = task_obj.user_input.get("_ocr_data", {})
    if isinstance(ocr_data, dict):
        report_data["_ocr_positions"] = ocr_data.get("positions", [])
        report_data["_ocr_image"] = ocr_data.get("image_base64", "")
        report_data["_ocr_fields"] = ocr_data.get("fields", {})
    else:
        report_data["_ocr_positions"] = []
        report_data["_ocr_image"] = ""
        report_data["_ocr_fields"] = {}
    yield f"data: {json.dumps({'type': 'report', 'data': report_data}, default=str)}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.get("/approval/status/{task_id}")
async def approval_status(task_id: str):
    if not master_agent: raise HTTPException(503, "Agent not initialized")
    return {"task_id": task_id, "agent_state": master_agent.state.model_dump()}


@app.get("/approval/timeline/{task_id}")
async def approval_timeline(task_id: str):
    if not audit: raise HTTPException(503)
    return audit.get_timeline(task_id)


@app.get("/tools")
async def list_tools():
    schemas = registry.get_schemas()
    stats = registry._stats
    result = []
    for s in schemas:
        name = s["name"]
        st = stats.get(name, {})
        calls = st.get("calls", 0)
        success = st.get("success", 0)
        total_lat = st.get("total_latency", 0.0)
        result.append({
            "name": name, "description": s["description"],
            "calls": calls,
            "success_rate": round(success / max(calls, 1) * 100, 1),
            "avg_latency": round(total_lat / max(calls, 1), 1),
        })
    return result


_db_pool = None

async def _get_pool():
    global _db_pool
    if _db_pool is None:
        import asyncpg
        dsn = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        _db_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    return _db_pool


@app.get("/history")
async def approval_history(limit: int = 20, contract_type: str = "", status: str = ""):
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            query = "SELECT * FROM approval_reports WHERE 1=1"
            params = []
            if contract_type:
                query += f" AND contract_type = ${len(params)+1}"
                params.append(contract_type)
            if status:
                query += f" AND status = ${len(params)+1}"
                params.append(status)
            query += f" ORDER BY created_at DESC LIMIT {int(limit)}"
            rows = await conn.fetch(query, *params)
            reports = []
            for r in rows:
                d = dict(r)
                if isinstance(d.get('report_data'), str):
                    try: d['report_data'] = json.loads(d['report_data'])
                    except: pass
                d['created_at'] = d['created_at'].isoformat() if d.get('created_at') else ''
                d['updated_at'] = d['updated_at'].isoformat() if d.get('updated_at') else ''
                reports.append(d)
            return {"reports": reports, "total": len(reports)}
    except Exception as e:
        return {"reports": [], "total": 0, "error": str(e)}


@app.post("/approval/{task_id}/approve")
async def approve_task(task_id: str):
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE approval_reports SET status='approved', updated_at=NOW() WHERE task_id=$1", task_id)
        return {"ok": True, "task_id": task_id, "status": "approved"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/approval/{task_id}/reject")
async def reject_task(task_id: str):
    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE approval_reports SET status='rejected', updated_at=NOW() WHERE task_id=$1", task_id)
        return {"ok": True, "task_id": task_id, "status": "rejected"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/agents/status")
async def agent_status():
    if not audit: return {"agents": {}}
    return {"agents": audit.get_agent_statuses()}


# ═══════════════ PDF 处理 ═══════════════

def _extract_pdf_text(content: bytes) -> tuple:
    """从 PDF 提取文字 + 生成段落位置"""
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        full_text = ""
        positions = []
        y_offset = 0
        for page in doc:
            blocks = page.get_text("blocks")  # (x0,y0,x1,y1,text,block_no,block_type)
            for b in blocks:
                if b[6] == 0:  # text block
                    text = b[4].strip()
                    if text:
                        full_text += text + "\n"
                        positions.append({
                            "text": text,
                            "top": y_offset + b[1],
                            "left": b[0],
                            "width": b[2] - b[0],
                            "height": b[3] - b[1],
                        })
            y_offset += page.rect.height
        doc.close()
        return full_text.strip(), positions
    except Exception as e:
        print(f"[PDF] Text extraction failed: {e}")
        return "", []


def _pdf_first_page_image(content: bytes) -> bytes:
    """PDF 首页转 PNG，用于前端 img 预览"""
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        if doc.page_count > 0:
            pix = doc[0].get_pixmap(dpi=150)
            result = pix.tobytes("png")
            doc.close()
            return result
        doc.close()
    except Exception:
        pass
    return b""


def _pdf_to_images(content: bytes) -> list:
    """将 PDF 页转为 PNG 图片列表（用于扫描件 OCR）"""
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            images.append(pix.tobytes("png"))
        doc.close()
        return images
    except Exception as e:
        print(f"[PDF] Image conversion failed: {e}")
        return []


# ═══════════════ Auth helpers ═══════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
