#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_extract_wisdom.py — 长文深度提炼报告生成器（中文技能库 · extract-wisdom）

把长内容（播客转写、文章、书籍章节、深度报告、访谈实录）按维度提炼成
面向学习吸收的深度智慧摘要：核心观点、关键洞察、重要引用、术语与概念、
适用场景与启发、可疑或待核实处、行动建议。区别于一页纸决策者摘要，
本技能保留观点/洞察/金句的多维结构，不压成单一结论。

用法示例：
    python draft_extract_wisdom.py article.txt --output wisdom.md
    cat transcript.txt | python draft_extract_wisdom.py -

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
    "你是资深内容分析师，擅长从长文本中提炼多维度智慧。请把用户提供的长内容"
    "（播客转写、文章、书籍章节、深度报告、访谈实录），提炼成一份面向学习吸收的"
    "深度智慧摘要。\n"
    "必须遵守：\n"
    "1. 忠于原文：只提炼原文中真实出现的内容，绝不编造、补写、脑补原文没有的观点或洞察；\n"
    "2. 区分观点与事实：每条核心观点必须标注【事实】或【观点】——可被外部验证的客观陈述"
    "标【事实】，作者主观判断/推测/主张标【观点】；标记不遗漏；\n"
    "3. 引用逐字保留：重要引用必须逐字摘自原文，不得改写或 paraphrase，保留金句原貌，"
    "注明说话人/出处（如有）；\n"
    "4. 按维度组织，而非按原文顺序：把同类信息归到对应维度节，不要顺着原文流水账复述；\n"
    "5. 可疑处必列：发现原文有夸张、矛盾、以偏概全、缺乏数据支撑的断言，列入"
    "“可疑或待核实处”并标（待核实），不为原文背书；\n"
    "6. 信息不足时对应节写“原文未涉及”，不凑数、不脑补。\n"
    "输出必须严格包含以下 7 个章节（节名与顺序不得改动）：\n"
    "## 核心观点\n（3-10 条，每条一句话，句末标注【事实】或【观点】）\n"
    "## 关键洞察\n（原文中反直觉、值得注意、跳出字面的点，每条注明在原文中的大致出处位置）\n"
    "## 重要引用\n（保留原文金句，逐条，逐字摘自原文，注明说话人/出处如有）\n"
    "## 术语与概念\n（出现的关键术语 + 一句话解释；首次出现时括注原文上下文）\n"
    "## 适用场景与启发\n（分三类：个人 / 团队 / 业务，每类列可迁移的启发）\n"
    "## 可疑或待核实处\n（原文的夸张、矛盾、存疑点，每条末尾标（待核实）；如无则写“原文未发现明显存疑处”）\n"
    "## 行动建议\n（3-8 条可执行动作，具体到“谁在什么场景下做什么”）\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior content analyst who extracts multi-dimensional wisdom from long text "
    "(podcast transcripts, articles, book chapters, deep reports, interviews). Produce a "
    "learning-oriented deep wisdom digest.\n"
    "Rules:\n"
    "1. Stay faithful: only extract what actually appears in the source; never invent or fill gaps.\n"
    "2. Label every core claim as [FACT] (verifiable objective statement) or [OPINION] "
    "(author's subjective judgment / speculation / claim); never skip the label.\n"
    "3. Quotes must be verbatim from the source — do NOT paraphrase the golden lines; "
    "attribute speaker/source when available.\n"
    "4. Organize by dimension, not by the source order; group like items together.\n"
    "5. Flag hype, contradictions, over-generalizations or unsupported claims under "
    "'Suspicious / To-verify' and mark (to-verify).\n"
    "6. When information is missing, write 'not covered in source' — do not pad.\n"
    "Output exactly these 7 sections, in this order:\n"
    "## Core Claims (3-10, one sentence each, tagged [FACT]/[OPINION])\n"
    "## Key Insights (counter-intuitive / noteworthy, with rough source location)\n"
    "## Notable Quotes (verbatim, attributed)\n"
    "## Terms & Concepts (term + one-line gloss, with first-occurrence context)\n"
    "## Applicable Scenarios & Takeaways (split: individual / team / business)\n"
    "## Suspicious or To-verify (each marked (to-verify); or 'no obvious issues found')\n"
    "## Actionable Recommendations (3-8 concrete actions: who does what in which scenario)\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_extract_wisdom",
        description="把长内容按维度提炼成深度智慧摘要报告（中文技能库 · extract-wisdom）",
    )
    parser.add_argument("input", help="长文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.extract-wisdom.md）")
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
        raise SystemExit("错误：输入内容为空，请提供长文本。")
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
    print("输入文本：%d 字，切分为 %d 段，开始提炼智慧摘要……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是待提炼的长内容（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".extract-wisdom.md"
        else:
            out_path = base + ".extract-wisdom.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：草稿请对照原文复核后再交付。")


if __name__ == "__main__":
    main()