#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_doc_summary.py — 文档一页摘要生成器（中文技能库 · doc-summary）

把长文档（报告、方案、制度、论文、合同条款说明、会议材料等）浓缩成
决策者视角的一页摘要：一句话结论、关键发现（带原文位置）、影响与风险、
建议行动、待确认事项。长文本自动两遍式：先逐段抽取关键发现，再汇总成稿；
短文档（单段）只跑一遍直接成稿。

用法示例：
    python draft_doc_summary.py report.txt --output summary.md
    cat report.txt | python draft_doc_summary.py - --purpose 向上汇报 --focus 预算
    python draft_doc_summary.py report.txt --reader "分管副总" --focus "合规、时间线"

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

# 第一遍：逐段抽取关键发现
EXTRACT_SYSTEM_PROMPT_ZH = (
    "你是严谨的文档信息抽取员。请从用户提供的文档片段中，逐条抽取「关键发现」："
    "数字、金额、日期、人名、机构名、项目名、明确结论、重要事实。\n"
    "必须遵守：\n"
    "1. 只列出片段中真实出现的内容，绝不脑补、评价或替原文下结论；\n"
    "2. 每条尽量标注其在片段中的位置（页码 / 章节标题 / 就近段落）；\n"
    "3. 数字、金额、日期、人名、机构名、项目名原样保留，不得遗漏或改写；\n"
    "4. 片段自相矛盾或口径变化时，并列写出两种说法；\n"
    "5. 不确定或片段没讲清的，标注（待确认）。\n"
    "直接输出 Markdown 列表，不要任何额外解释。"
)

# 第二遍：汇总成一页式决策者摘要
SUMMARY_SYSTEM_PROMPT_ZH = (
    "你是资深顾问，面向决策者撰写一页式文档摘要。请根据用户提供的内容"
    "（可能是文档原文，或从文档各段抽取的关键发现条目汇总），生成一页"
    "（约 800-1200 字）的 Markdown 摘要。\n"
    "严格按以下结构输出：\n"
    "1. 文档标题与信息来源（缺失项标注（待确认））；\n"
    "2. 一句话结论（结论先行，一句话说清核心）；\n"
    "3. 关键发现（按重要性排序，不按章节顺序罗列；每条带原文位置 / 页码 / 章节）；\n"
    "4. 影响与风险（仅基于给定材料）；\n"
    "5. 建议行动；\n"
    "6. 待确认事项（原文没讲清、口径不明、自相矛盾之处）。\n"
    "必须遵守：\n"
    "1. 忠于原文：只使用材料中真实出现的信息，绝不脑补、不替原文下结论；\n"
    "2. 信息保全：数字、金额、日期、人名、项目名一个不丢；\n"
    "3. 不确定处标注（待确认）；\n"
    "4. 原文自相矛盾或前后口径变化时，必须在待确认事项中点出；\n"
    "5. 面向决策者：结论先行、按重要性排序，控制在一页以内。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

EXTRACT_SYSTEM_PROMPT_EN = (
    "You are a rigorous document extractor. From the provided document excerpt, "
    "extract key findings item by item: numbers, amounts, dates, person names, "
    "organization names, project names, explicit conclusions, important facts.\n"
    "Rules:\n"
    "1. Only list content actually present; never invent, evaluate, or conclude for the source;\n"
    "2. Mark each item's location (page / section / nearby paragraph);\n"
    "3. Keep numbers, amounts, dates, names verbatim; never drop or rewrite them;\n"
    "4. If the excerpt contradicts itself, list both versions;\n"
    "5. Mark unclear items as (TBC).\n"
    "Output a Markdown list only, with no extra explanation."
)

SUMMARY_SYSTEM_PROMPT_EN = (
    "You are a senior consultant writing a one-page, decision-maker-oriented document summary. "
    "Based on the provided content (either the original document, or extracted key findings "
    "from its sections), produce a one-page Markdown summary.\n"
    "Structure strictly:\n"
    "1. Document title and source (mark unknowns as (TBC));\n"
    "2. One-sentence conclusion (conclusion first);\n"
    "3. Key findings (sorted by importance, not by document order; each with source location/page/section);\n"
    "4. Impacts and risks (based only on the given material);\n"
    "5. Recommended actions;\n"
    "6. Open items (unclear, ambiguous, or contradictory points).\n"
    "Rules:\n"
    "1. Stay faithful: only use information actually present; never invent or conclude for the source;\n"
    "2. Preserve every number, amount, date, name, and project name;\n"
    "3. Mark uncertain items as (TBC);\n"
    "4. Point out contradictions or inconsistent wording in open items;\n"
    "5. Conclusion first, sorted by importance; keep it to one page.\n"
    "Output the Markdown body only."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_doc_summary",
        description="把长文档浓缩成决策者视角的一页摘要（中文技能库 · doc-summary）",
    )
    parser.add_argument("input", help="文档路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.doc-summary.md）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型名（默认 %(default)s）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help="OpenAI 兼容接口根地址（默认 %(default)s）")
    parser.add_argument("--api-key", default=None, help="API Key（优先于环境变量）")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言（默认 zh）")
    parser.add_argument("--purpose", default=None,
                        help="摘要用途，如：向上汇报 / 快速决策 / 存档")
    parser.add_argument("--reader", default=None, help="读者背景，如：分管副总、非技术高管")
    parser.add_argument("--focus", default=None,
                        help="特别关注点，如：预算、合规、时间线（多个用顿号分隔）")
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
        raise SystemExit("错误：输入内容为空，请提供文档文本。")
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


def build_context_note(args):
    """把可选补充信息（用途/读者/关注点）拼成注入用户消息的说明。"""
    notes = []
    if args.purpose:
        notes.append("【摘要用途】%s" % args.purpose)
    if args.reader:
        notes.append("【读者背景】%s" % args.reader)
    if args.focus:
        notes.append("【特别关注点】%s" % args.focus)
    return "\n".join(notes)


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
    extract_prompt = EXTRACT_SYSTEM_PROMPT_ZH if args.lang == "zh" else EXTRACT_SYSTEM_PROMPT_EN
    summary_prompt = SUMMARY_SYSTEM_PROMPT_ZH if args.lang == "zh" else SUMMARY_SYSTEM_PROMPT_EN
    context_note = build_context_note(args)

    text = read_input(args.input)
    chunks = chunk_text(text)
    print("输入文本：%d 字，切分为 %d 段。" % (len(text), len(chunks)), file=sys.stderr)

    if len(chunks) == 1:
        # 短文档：一遍直接成稿
        user_content = text
        if context_note:
            user_content = context_note + "\n\n" + text
        messages = [
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": user_content},
        ]
        final_summary = chat(messages, api_key, args.base_url, args.model)
        print("一遍成稿完成。", file=sys.stderr)
    else:
        # 长文档：第一遍逐段抽取关键发现
        findings = []
        for i, chunk in enumerate(chunks, start=1):
            messages = [
                {"role": "system", "content": extract_prompt},
                {"role": "user", "content": "以下是文档第 %d/%d 段，请抽取关键发现：\n\n%s"
                                            % (i, len(chunks), chunk)},
            ]
            result = chat(messages, api_key, args.base_url, args.model)
            findings.append("### 第 %d 段关键发现\n\n%s" % (i, result))
            print("第一遍：第 %d/%d 段抽取完成。" % (i, len(chunks)), file=sys.stderr)
        # 第二遍：把全部抽取结果汇总成一页摘要
        aggregated = "\n\n".join(findings)
        user_content = (
            "以下是从文档各段抽取的关键发现条目汇总，请据此生成一页式决策者摘要：\n\n%s"
            % aggregated
        )
        if context_note:
            user_content = context_note + "\n\n" + user_content
        messages = [
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": user_content},
        ]
        final_summary = chat(messages, api_key, args.base_url, args.model)
        print("第二遍：汇总成稿完成。", file=sys.stderr)

    if args.output:
        out_path = args.output
    else:
        base = args.input if args.input != "-" else "stdin"
        if "." in base:
            out_path = base.rsplit(".", 1)[0] + ".doc-summary.md"
        else:
            out_path = base + ".doc-summary.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(final_summary)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = final_summary.count("\n") + 1
    print("已生成：%s（%d 行，%d 字）" % (out_path, lines, len(final_summary)))
    print("提示：摘要请对照原文复核后再交付。")


if __name__ == "__main__":
    main()