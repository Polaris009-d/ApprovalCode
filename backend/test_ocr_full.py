"""测试完整 OCR 管线 — 生成带文字的测试图片"""
import asyncio, httpx, base64, json, io

async def test_upload_endpoint():
    """测试 /upload/ocr 端点"""
    # 创建一个最小的白色 PNG (Baidu OCR 需要真实图片)
    # 使用 1x1 透明PNG 最小数据
    # 实际上我们上传用户提供的合同截图路径来测试

    # 直接测试后端函数，跳过 HTTP
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from app.main import _ocr_contract

    # 创建一个简单PNG (白色背景 800x200, 写中文在上面)
    # 这里用占位图测试 — 实际应上传合同截图
    print("测试1: 模拟 OCR + DeepSeek 提取")

    # 直接测试 _ocr_contract 的 DeepSeek 部分（跳过百度 OCR）
    from app.tools.builtin.ocr import ocr_contract

    # 生成一个带中文文本的简单图片用于测试百度OCR
    # 由于无法在Windows轻松生成PNG，改为测试已有逻辑
    from app.config import settings
    print(f"DeepSeek Key: {'SET' if settings.LLM_API_KEY else 'MISSING'}")
    print(f"Baidu Key: {'SET' if settings.BAIDU_OCR_API_KEY else 'MISSING'}")

    # 测试百度 OCR — 需要一个真实的合同图片
    # 用户上传的图片路径应该在上传目录中
    import glob
    uploads = glob.glob(os.path.join(os.path.dirname(__file__), "uploads", "*"))
    if uploads:
        print(f"发现已上传文件: {uploads}")
        latest = max(uploads, key=os.path.getmtime)
        print(f"使用最新文件: {latest}")
        ext = os.path.splitext(latest)[1].lower()
        with open(latest, "rb") as f:
            content = f.read()
        print(f"文件大小: {len(content)} bytes")

        # 测试百度 OCR
        result = await ocr_contract(content, ext)
        if isinstance(result, dict):
            ft = result.get("full_text", "")
            print(f"OCR 文字长度: {len(ft)}")
            print(f"OCR 前200字: {ft[:200]}")
            if not ft:
                print("WARNING: OCR 返回空文字！百度 OCR 未能识别图片内容。")
                print(f"Raw: {json.dumps(result, ensure_ascii=False)[:300]}")
        else:
            print(f"OCR result type: {type(result)}")

        # 完整管线
        ocr_data = await _ocr_contract(latest, "service", content, ext)
        fields = ocr_data.get("fields", {})
        positions = ocr_data.get("positions", [])
        print(f"\n完整管线结果:")
        print(f"  Fields: {json.dumps(fields, ensure_ascii=False)}")
        print(f"  Positions: {len(positions)}")
        for p in positions[:3]:
            print(f"    [{p.get('field')}] ({p.get('top')},{p.get('left')}) {p.get('text','')[:40]}")
    else:
        print("upload/ 目录为空 — 请通过前端上传合同文件后再运行测试")

asyncio.run(test_upload_endpoint())
