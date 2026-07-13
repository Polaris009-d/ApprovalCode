"""完整审批流程测试 — 捕获所有异常"""
import sys, os, traceback, asyncio
sys.path.insert(0, os.path.dirname(__file__))

async def test():
    from app.models.schemas import ApprovalTask
    from app.agents.master_agent import MasterAgent
    from app.agents.reasoning_engine import ReasoningEngine
    from app.tools.registry import registry
    from app.tools.builtin.field_extract import ExtractFieldsTool
    from app.tools.builtin.compliance import SearchLawTool, CiteClauseTool, CrossValidateTool
    from app.tools.builtin.risk import RiskScoreTool, SuspendNodeTool, ApproveNodeTool, GenerateReportTool
    from app.tools.builtin.ocr import BaiduOCRTool
    from app.security.rule_engine import RuleEngine
    from app.memory.short_term import ShortTermMemory
    from app.observability.audit import AuditLogger

    # Register tools
    for t in [ExtractFieldsTool(), BaiduOCRTool(), CrossValidateTool(),
              SearchLawTool(), CiteClauseTool(), RiskScoreTool(),
              SuspendNodeTool(), ApproveNodeTool(), GenerateReportTool()]:
        try: registry.register(t)
        except: pass

    agent = MasterAgent(registry, ShortTermMemory(), RuleEngine(), AuditLogger(), ReasoningEngine())

    # Simulate user upload with pre-extracted OCR data
    ocr_data = {
        "fields": {
            "party_a": "山西晋通恒业科技有限公司",
            "party_b": "晋中汇智方略咨询中心（有限合伙）",
            "amount": "86000元",
            "date": "2026-07-11",
            "payment_period": "按季度支付，共4期，每期支付21500元",
            "subject": "年度管理咨询、流程优化、数据整理服务"
        },
        "positions": [],
        "image_base64": "",
        "full_text": "合同测试文本"
    }

    task = ApprovalTask(
        contract_type="service",
        contract_files=[],
        user_input={
            "amount": "86000",
            "party_a": "山西晋通恒业科技有限公司",
            "_ocr_data": ocr_data,
            "_ocr_fields": ocr_data["fields"],
        }
    )

    context = {"task": task, "start_time": __import__("time").perf_counter()}

    print("Starting approval pipeline...")
    try:
        result = await agent.execute(task, context)
        report, traces = result
        print(f"SUCCESS: type={type(report).__name__}, traces={len(traces)}")
        if hasattr(report, 'model_dump'):
            import json
            print(json.dumps(report.model_dump(mode='json'), ensure_ascii=False, indent=2)[:2000])
        else:
            print(f"Report (dict): {str(report)[:500]}")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        traceback.print_exc()

asyncio.run(test())
