"""直接测试 OCR + DeepSeek 管线"""
import asyncio, httpx, json, base64, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from app.config import settings

DEEPSEEK_KEY = settings.LLM_API_KEY
BAIDU_API_KEY = settings.BAIDU_OCR_API_KEY
BAIDU_SECRET = settings.BAIDU_OCR_SECRET_KEY

# 模拟用户上传的合同文本
CONTRACT_TEXT = """合同类型：企业年度咨询服务合同
甲方（委托方）名称：山西晋通恒业科技有限公司
统一社会信用代码：91140702MA0KX98L7Y
地址：山西省晋中市榆次区安宁街 269 号鑫源大厦 15 层 1503 室
联系电话：13935401188
法定代表人：刘建国
乙方（服务方）名称：晋中汇智方略咨询中心（有限合伙）
统一社会信用代码：91140702MA0LW32P9Q
地址：山西省晋中市榆次区文苑街 180 号创意园 A 座 402
联系电话：13835416699
执行事务合伙人：张敏
合同金额 人民币：86000 元 大写：捌万陆仟元整（含税 6%）
签订日期 2026 年 07 月 11 日
付款周期 按季度支付，共 4 期，每期支付 21500 元。
服务内容：乙方向甲方提供年度管理咨询、流程优化、数据整理服务。"""


async def test_deepseek_extraction():
    """测试 DeepSeek 字段提取"""
    prompt = f"""你是一个合同信息提取助手。从以下 OCR 文字中提取字段，返回严格JSON。

{{"party_a":"甲方/委托方公司全称","party_b":"乙方/服务方公司全称","amount":"合同总金额(含数字和单位)","date":"签订日期(YYYY-MM-DD)","payment_period":"付款方式/周期","subject":"服务内容/标的物摘要"}}

规则: 每个字段必填，找不到填""。金额去逗号留单位。日期统一YYYY-MM-DD。
只返回JSON，禁止任何解释。

OCR文字:
{CONTRACT_TEXT}"""

    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    body = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "max_tokens": 800, "temperature": 0}

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=body)
        print(f"DeepSeek status: {r.status_code}")
        raw = r.json()["choices"][0]["message"]["content"]
        print(f"Raw output:\n{raw}\n")

        # 解析
        text = raw.strip()
        for tag in ["```json", "```"]:
            if tag in text:
                text = text.split(tag, 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
                break

        try:
            fields = json.loads(text.strip())
            print("Parsed fields:")
            for k, v in fields.items():
                print(f"  {k}: {v}")
            return fields
        except json.JSONDecodeError as e:
            print(f"JSON parse FAILED: {e}")
            print(f"Attempted to parse: {text.strip()[:200]}")
            return {}


async def test_baidu_token():
    """测试 Baidu Token"""
    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={BAIDU_API_KEY}&client_secret={BAIDU_SECRET}"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url)
        print(f"Baidu Token status: {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            print(f"Token: {d.get('access_token','')[:20]}... expires={d.get('expires_in')}s")
            return d.get("access_token", "")
        print(f"FAILED: {r.text[:200]}")
        return ""


async def main():
    print("=== Test 1: Baidu Token ===")
    await test_baidu_token()

    print("\n=== Test 2: DeepSeek Extraction ===")
    fields = await test_deepseek_extraction()

    if fields:
        print("\n=== Result ===")
        non_empty = sum(1 for v in fields.values() if v)
        print(f"Fields extracted: {non_empty}/{len(fields)}")
        for k, v in fields.items():
            status = "OK" if v else "EMPTY"
            print(f"  [{status}] {k}: {v}")


asyncio.run(main())
