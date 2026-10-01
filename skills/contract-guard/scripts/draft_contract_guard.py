#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_contract_guard.py — 合同审查报告生成器（中文技能库 · contract-guard）

把一份合同文本（或条款摘要）按审查方立场（我方是甲方/乙方/中立）做结构化审查，
输出 Markdown 审查报告：条款四分类（红旗/警告/保护/缺失保护）、A+~F 公平评分、
中国法强制规定对照、可直接用的修改建议。

用法示例：
    python draft_contract_guard.py contract.txt --side 乙方 --output review.md
    cat contract.txt | python draft_contract_guard.py - --side 甲方

环境变量：
    HX_API_KEY / OPENAI_API_KEY    API Key（二选一）
    HX_BASE_URL                    OpenAI 兼容接口根地址，默认 https://api.deepseek.com/v1
    HX_MODEL                       默认模型，默认 deepseek-chat
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = os.environ.get("HX_BASE_URL", "https://api.deepseek.com/v1")
DEFAULT_MODEL = os.environ.get("HX_MODEL", "deepseek-chat")
CHUNK_SIZE = 9000          # 单次请求的文本上限（按字符估算）
CHUNK_OVERLAP = 400        # 相邻分段的交叠量，避免切断句子
REQUEST_TIMEOUT = 120      # 秒

SYSTEM_PROMPT_ZH = (
    "你是资深合同审查律师（中文语境）。请把用户提供的合同文本，按指定的审查方立场，"
    "整理成一份结构化 Markdown 合同审查报告。\n"
    "审查立场由用户在消息开头指定（我方是甲方 / 乙方 / 中立），所有判断必须与该立场一致。\n"
    "必须遵守：\n"
    "1. 忠于原文：只审查合同里真实出现的条款，绝不编造未出现的内容；引用条款必须摘录原文；\n"
    "2. 条款四分类——每条有实质影响的条款归入以下四类，四类每类都必须出现（无则写\"无\"）：\n"
    "   - 红旗：对我方明显不利、或涉嫌违反强制性规定、签署前必须顶回的条款；\n"
    "   - 警告：中等风险、值得谈但不一定是 deal-breaker 的条款；\n"
    "   - 保护：对我方有利的条款，谈判时不要被对方改掉；\n"
    "   - 缺失保护：按行业惯例应当有、但合同里没写的标准保护条款；\n"
    "3. 公平评分：对合同整体及关键条款给出 A+（双方公平、优秀）到 F（严重一边倒）等级，附一句话理由；\n"
    "4. 中国法强制规定逐项对照（作为固定检查清单，一项都不许漏，原文未涉及就标\"未约定（待确认）\"，不许默认通过）：\n"
    "   - 试用期：劳动合同期限对应试用期上限（3 个月以上不满 1 年试用期≤1 个月；1 年以上不满 3 年≤2 个月；3 年以上及无固定期限≤6 个月），试用期工资不得低于转正工资 80%；\n"
    "   - 竞业限制：期限不得超过 2 年，且须约定经济补偿，范围/地域不得过宽；\n"
    "   - 加班费：工作日延时≥150%、休息日≥200%、法定休假日≥300%；\n"
    "   - 定金：不得超过主合同标的额 20%，超过部分不产生定金效力；\n"
    "   - 民间借贷利率：不得超过合同成立时一年期 LPR 的 4 倍；\n"
    "   - 禁止预扣利息：借款利息不得预先在本金中扣除；\n"
    "   - 保密义务：保密期限、范围、例外情形是否合理；\n"
    "5. 修改建议：对每条红旗/警告给出具体修改方向，写成可直接拿去谈判的表述，不要只说\"这条不好\"；\n"
    "6. 输出严格包含 6 节：合同概要、条款分类清单（红旗/警告/保护/缺失保护四表）、公平评分（整体+关键条款）、强制规定对照（逐项三栏：规定内容/原文对应/合规与否）、修改建议（按优先级）、待确认与边界声明；\n"
    "7. 不确定处标注（待确认）；报告末尾必须声明\"本报告不构成法律意见，法规以最新有效版本为准，重大决策请咨询执业律师\"。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior contract reviewer under PRC Chinese law context. "
    "Review the provided contract from the side specified by the user "
    "(Party A / Party B / Neutral) and produce a structured Markdown report.\n"
    "Rules:\n"
    "1. Stay faithful: only review clauses actually present; never invent; quote original text.\n"
    "2. Four-way classification (each category must appear; write 'None' if empty): "
    "Red Flags / Warnings / Protections / Missing Protections.\n"
    "3. Fairness grade A+ (balanced, excellent) to F (heavily one-sided), with one-line reason.\n"
    "4. Mandatory PRC-law checklist, checked item by item (mark 'Not addressed (TBC)' when absent): "
    "probation length & 80% wage floor; non-compete <=2 years with compensation; "
    "overtime 150%/200%/300%; earnest money <=20% of principal; private lending rate <=4x 1Y LPR; "
    "no pre-deducted interest; confidentiality scope/duration.\n"
    "5. Actionable rewrite suggestions for every red flag / warning.\n"
    "6. Six sections: overview; four-category clause lists; fairness score; statute checklist "
    "(rule / clause text / compliant); prioritized revision suggestions; TBC items + disclaimer "
    "that this is not legal advice and to consult a licensed lawyer.\n"
    "Output the Markdown body only, no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_contract_guard",
        description="把合同文本按审查方立场做结构化审查，输出审查报告（中文技能库 · contract-guard）",
    )
    parser.add_argument("input", help="合同文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.contract-guard.md）")
    parser.add_argument("--side", choices=["甲方", "乙方", "中立"], default="乙方",
                        help="审查立场：我方是甲方/乙方/中立（默认 %(default)s）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型名（默认 %(default)s）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI 兼容接口根地址（默认 %(default)s）")
    parser.add_argument("--api-key", default=None, help="API Key（优先于环境变量）")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言（默认 zh）")
    return parser


def resolve_api_key(args):
    key = args.api_key or os.environ.get("HX_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit(
            "错误：未找到 API Key。\n"
            "请通过 --api-key 传入，或设置环境变量 HX_API_KEY / OPENAI_API_KEY。\n"
            "任意 OpenAI 兼容接口均可（DeepSeek / 通义 / OpenAI / Claude API 等）。"
        )
    return key


def read_input(path):
    if path == "-":
        text = sys.stdin.read()
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            raise SystemExit("错误：无法读取文件 %s（%s）" % (path, exc))
    if not text.strip():
        raise SystemExit("错误：输入内容为空，请提供合同文本。")
    return text


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """长文本按换行切块，相邻块保留交叠，避免切断语义。"""
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            cut = text.rfind("\n", start + size // 2, end)
            if cut != -1:
                end = cut
        chunks.append(text[start:end])
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks


def chat(messages, api_key, base_url, model):
    """调用 OpenAI 兼容的 /chat/completions 接口，返回回复正文。"""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        hints = {
            401: "API Key 无效或未设置（检查 --api-key / HX_API_KEY / OPENAI_API_KEY）",
            403: "无权访问该接口（检查 Key 权限与 IP 白名单）",
            404: "接口地址不正确（--base-url 应指向 OpenAI 兼容接口的根地址，如 https://api.deepseek.com/v1）",
            429: "触发限流，请稍后重试",
        }
        msg = hints.get(exc.code, "服务端返回错误")
        raise SystemExit("请求失败（HTTP %s）：%s\n服务端详情：%s" % (exc.code, msg, detail))
    except urllib.error.URLError as exc:
        raise SystemExit("网络错误：%s\n请检查网络或 --base-url 是否可达。" % exc.reason)
    except (ValueError, KeyError, IndexError) as exc:
        raise SystemExit("响应解析失败：%s\n请确认接口返回 OpenAI 兼容格式。" % exc)
    if "error" in data:
        raise SystemExit("接口返回错误：%s" % data["error"])
    return data["choices"][0]["message"]["content"]


def main():
    args = build_parser().parse_args()
    api_key = resolve_api_key(args)
    system_prompt = SYSTEM_PROMPT_ZH if args.lang == "zh" else SYSTEM_PROMPT_EN

    text = read_input(args.input)
    chunks = chunk_text(text)
    print("输入合同：%d 字，切分为 %d 段，审查立场=我方为%s，开始生成审查报告……"
          % (len(text), len(chunks), args.side), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        user_msg = (
            "审查立场：我方为【%s】。以下是合同文本（第 %d/%d 段）：\n\n%s"
            % (args.side, i, len(chunks), chunk)
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        outputs.append(chat(messages, api_key, args.base_url, args.model))
        print("第 %d/%d 段完成。" % (i, len(chunks)), file=sys.stderr)

    merged = outputs[0] if len(outputs) == 1 else "\n\n".join(
        seg if idx == 0 else "## 补充内容（第 %d 段）\n\n%s" % (idx + 1, seg)
        for idx, seg in enumerate(outputs)
    )

    if args.output:
        out_path = args.output
    else:
        base = args.input if args.input != "-" else "stdin"
        if "." in base:
            out_path = base.rsplit(".", 1)[0] + ".contract-guard.md"
        else:
            out_path = base + ".contract-guard.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：审查报告请对照原文复核后再交付；本报告不构成法律意见。")


if __name__ == "__main__":
    main()