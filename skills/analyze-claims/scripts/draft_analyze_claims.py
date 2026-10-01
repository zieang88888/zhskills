#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_analyze_claims.py — 信息可信度核查报告生成器（中文技能库 · analyze-claims）

把一条或多条声明 / 说法 / 文章论断，拆成可单独检验的声明，逐条评估证据、
来源与可信度，输出结构化 Markdown 核查报告：声明拆解、逐条评估、可信度结论、
需核实清单、边界说明。

用法示例：
    python draft_analyze_claims.py claims.txt --output report.md
    cat claims.txt | python draft_analyze_claims.py -

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
    "你是中立客观的信息可信度核查员。请把用户提供的一段文本（新闻、消息、"
    "营销文案、汇报材料或文章论断）拆成可单独检验的声明，逐条做结构化可信度分析，"
    "输出一份 Markdown 核查报告。\n"
    "必须遵守：\n"
    "1. 声明拆解不遗漏：把整段话拆成一条条可单独检验的声明，原文出现的每个断言、"
    "判断、情绪表达与建议都要进表，不得合并、跳过或改写原意；\n"
    "2. 区分类型：每条标注为「事实断言 / 价值判断 / 情绪表达 / 建议」之一，"
    "并判断其可证伪性（可通过事实验证 / 不可证伪）；\n"
    "3. 逐条评估：证据强度分「有据 / 部分有据 / 无据」三档；判「无据」必须写明理由"
    "（如文中未给出证据、仅为主观判断、无法查证等）；同时评估来源可靠度，"
    "指出该声明与已知常识 / 公认事实是否冲突；\n"
    "4. 只按证据评估，不因立场、好恶、标签下结论；信息不足或无法判断处标注（待核实）；\n"
    "5. 可信度结论每条给「高 / 中 / 低」三档之一，并写一句话理由；\n"
    "6. 不编造证据：证据只能来自原文或公认常识，不得虚构数据、来源、引用或链接；\n"
    "7. 报告末尾必须给出需核实清单（哪些断言建议查证、查什么）与边界说明。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a neutral, objective claims-verification analyst. Break the provided text "
    "(news, messages, marketing copy, report draft, or editorial claims) into individually "
    "testable claims and analyze each claim's credibility in a structured Markdown report.\n"
    "Rules:\n"
    "1. No claim is dropped: split the text into individually testable claims; every assertion, "
    "value judgment, emotional expression and recommendation must enter the table.\n"
    "2. Label each claim's type (factual assertion / value judgment / emotional expression / "
    "recommendation) and whether it is falsifiable.\n"
    "3. Rate evidence strength as supported / partially supported / unsupported; if unsupported, "
    "state why. Assess source reliability and note any conflict with established facts.\n"
    "4. Judge only by evidence, never by stance or preference; mark uncertain items (TBC).\n"
    "5. Give each claim a credibility rating (high / medium / low) with a one-line reason.\n"
    "6. Never fabricate evidence, data, citations or links.\n"
    "7. End with a list of claims to verify (and what to check) plus boundary notes.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_analyze_claims",
        description="把声明 / 文章论断拆成可检验的条目，做结构化可信度核查（中文技能库 · analyze-claims）",
    )
    parser.add_argument("input", help="待核查文本路径（一条或多条声明，可整段粘贴），或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.analyze-claims.md）")
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
        raise SystemExit("错误：输入内容为空，请提供待核查的声明 / 文本。")
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
    print("输入文本：%d 字，切分为 %d 段，开始生成核查报告……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是待核查文本（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".analyze-claims.md"
        else:
            out_path = base + ".analyze-claims.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：核查报告仅为文本分析结论，涉及事实请再做权威查证。")


if __name__ == "__main__":
    main()