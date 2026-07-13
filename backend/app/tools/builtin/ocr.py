"""
Baidu OCR 工具 — 合同多模态识别
使用百度云通用文字识别（高精度含位置版）
"""
import base64
import json
import httpx
from typing import Any, Dict
from pydantic import BaseModel, Field
from ..base_tool import BaseTool
from ...models.schemas import ToolCall
from ...config import settings


class BaiduOCRInput(BaseModel):
    filepath: str = Field(description="合同文件本地路径")
    file_content: str = Field(default="", description="文件 Base64 编码")
    file_ext: str = Field(default=".png", description="文件扩展名")


class BaiduOCRTool(BaseTool):
    name = "baidu_ocr"
    description = "使用百度云 OCR 从合同图片/扫描件中提取文字内容（带位置信息）"
    input_schema = BaiduOCRInput

    async def _run(self, validated: BaiduOCRInput, call: ToolCall, **kwargs) -> Dict[str, Any]:
        image_b64 = validated.file_content
        if not image_b64 and validated.filepath:
            with open(validated.filepath, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()

        access_token = await _get_baidu_token()
        if not access_token:
            return {"error": "Baidu OCR token 获取失败", "words": []}

        url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/accurate?access_token={access_token}"
        payload = {
            "image": image_b64,
            "detect_direction": "true",
            "paragraph": "true",
            "probability": "false",
            "language_type": "CHN_ENG",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
            if resp.status_code != 200:
                return {"error": f"Baidu OCR failed: {resp.status_code}", "words": [], "positions": []}

            data = resp.json()
            words = data.get("words_result", [])

            # 收集两种位置: 词级别 + 段落级别
            positions = []
            for w in words:
                loc = w.get("location", {})
                positions.append({
                    "text": w["words"],
                    "top": loc.get("top", 0),
                    "left": loc.get("left", 0),
                    "width": loc.get("width", 0),
                    "height": loc.get("height", 0),
                })

            # 段落合并: 将同一 paragraph 的 words 合并为一个区域
            para_positions = _merge_paragraphs(words)

            # 优先用段落位置，词位置作为 fallback
            use_positions = para_positions if para_positions else positions

            lines = [w["words"] for w in words]
            return {
                "words": lines,
                "full_text": "\n".join(lines),
                "count": len(lines),
                "positions": use_positions,
                "raw": data,
            }


# ═══════════════ Token 管理 ═══════════════

_token_cache: Dict[str, Any] = {}


async def _get_baidu_token() -> str:
    """获取 Baidu OCR access_token (缓存)"""
    import time
    if _token_cache.get("expires_at", 0) > time.time():
        return _token_cache["token"]

    api_key = settings.BAIDU_OCR_API_KEY
    secret = settings.BAIDU_OCR_SECRET_KEY
    if not api_key or not secret:
        return ""

    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url)
        if resp.status_code == 200:
            data = resp.json()
            _token_cache["token"] = data.get("access_token", "")
            _token_cache["expires_at"] = time.time() + data.get("expires_in", 2592000) - 60
            return _token_cache["token"]
    return ""


def _merge_paragraphs(words: list) -> list:
    """将 OCR 返回的 words 按 Y 坐标聚类为段落级区域"""
    if not words:
        return []
    LINE_THRESHOLD = 15  # Y 坐标差异 < 15px 视为同一行
    lines = []
    current_line = []
    current_y = None

    for w in sorted(words, key=lambda w: (w.get("location", {}).get("top", 0), w.get("location", {}).get("left", 0))):
        loc = w.get("location", {})
        y = loc.get("top", 0)
        if current_y is None or abs(y - current_y) < LINE_THRESHOLD:
            current_line.append(w)
        else:
            if current_line:
                lines.append(current_line)
            current_line = [w]
        current_y = y
    if current_line:
        lines.append(current_line)

    para_positions = []
    for line_words in lines:
        texts = [w["words"] for w in line_words]
        full = "".join(texts)
        locs = [w.get("location", {}) for w in line_words]
        min_top = min(l["top"] for l in locs)
        min_left = min(l["left"] for l in locs)
        max_right = max(l["left"] + l["width"] for l in locs)
        max_bottom = max(l["top"] + l["height"] for l in locs)
        para_positions.append({
            "text": full,
            "top": min_top,
            "left": min_left,
            "width": max_right - min_left,
            "height": max_bottom - min_top,
        })
    return para_positions


async def ocr_contract(file_content: bytes, file_ext: str) -> Dict[str, Any]:
    """便捷函数：OCR 识别合同"""
    tool = BaiduOCRTool()
    image_b64 = base64.b64encode(file_content).decode()
    call = ToolCall(tool_name="baidu_ocr", arguments={
        "filepath": "", "file_content": image_b64, "file_ext": file_ext,
    }, agent_id="ocr_pipeline")
    result = await tool.execute(call)
    return result.data if result.success else {"error": result.error, "words": []}
