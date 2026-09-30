#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_resume_review.py — 简历诊断报告草稿生成器（中文技能库 · resume-review）

把简历文本转成结构化诊断报告：总体评价、亮点清单、分级问题清单、
逐条改写建议、岗位匹配度、行动清单。

用法示例：
    python draft_resume_review.py resume.md --target "数据分析师" --jd jd.txt --output report.md
    cat resume.md | python draft_resume_review.py -

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
CHUNK_OVERLAP = 400        # 相邻分段的交叠量，避免切断语义
REQUEST_TIMEOUT = 120      # 秒

SYSTEM_PROMPT = (
    "你是资深 HR 与简历顾问。请把用户提供的简历改写成一份"
    "可直接交付的简历诊断报告。\n"
    "必须遵守：\n"
    "1. 忠于原文：只分析简历中真实存在的内容，绝不虚构经历或能力；\n"
    "2. 证据引用：每条亮点与问题必须附原文依据；\n"
    "3. 问题分级：🔴 致命（影响筛选）/ 🟡 重要（影响竞争力）/ 🟢 建议（锦上添花）；\n"
    "4. 改写可落地：每个问题给出 Before → After 的具体改写句；\n"
    "5. 岗位匹配：仅当提供了目标岗位或 JD 时才输出匹配度分析，否则明确说明未评估；\n"
    "6. 尊重事实：基于真实经历重组表达，不教用户编造经历；\n"
    "7. 输出结构固定：总体评价 → 亮点清单 → 问题清单（分级）→ 逐条改写建议 → "
    "岗位匹配度 → 行动清单。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior HR and resume consultant. Turn the provided resume into a "
    "ready-to-deliver resume review report.\n"
    "Rules:\n"
    "1. Stay faithful: analyze only what is actually in the resume; never invent experience or skills.\n"
    "2. Evidence: every highlight and issue must quote the original text.\n"
    "3. Severity tiers: RED (blocks screening) / YELLOW (hurts competitiveness) / GREEN (nice-to-have).\n"
    "4. Actionable rewrites: give concrete Before → After sentences for every issue.\n"
    "5. Role fit: only analyze fit when a target role or JD is provided; otherwise state it is not assessed.\n"
    "6. Be honest: rephrase real experience, never advise fabricating.\n"
    "7. Fixed structure: overall assessment → highlights → tiered issues → rewrite table → role fit → action list.\n"
    "Output the Markdown body only."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_resume_review",
        description="把简历改写成结构化诊断报告（中文技能库 · resume-review）",
    )
    parser.add_argument("input", help="简历文件路径，或用 - 从标准输入读取")
    parser.add_argument("--target", help="目标岗位（可选，影响匹配度与关键词建议）")
    parser.add_argument("--jd", help="岗位描述 JD 文件路径（可选，提供则做逐条匹配分析）")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.resume-review.md）")
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
        raise SystemExit("错误：输入内容为空，请提供简历文本。")
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
        "temperature": 0.3,
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
    system_prompt = SYSTEM_PROMPT if args.lang == "zh" else SYSTEM_PROMPT_EN

    resume = read_input(args.input)
    chunks = chunk_text(resume)
    print("简历：%d 字，切分为 %d 段，开始诊断……" % (len(resume), len(chunks)), file=sys.stderr)

    context = []
    if args.target:
        context.append("目标岗位：%s" % args.target)
    if args.jd:
        try:
            jd_text = read_input(args.jd)
            context.append("岗位描述 JD：\n%s" % jd_text)
        except SystemExit as exc:
            raise SystemExit("错误：无法读取 JD 文件。%s" % exc)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        user_msg = "以下是简历（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)
        if context:
            user_msg += "\n\n补充信息：\n%s" % "\n".join(context)
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
            out_path = base.rsplit(".", 1)[0] + ".resume-review.md"
        else:
            out_path = base + ".resume-review.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：诊断报告请结合候选人的真实情况复核后使用。")


if __name__ == "__main__":
    main()
