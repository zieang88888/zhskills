#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_xiaohongshu_conversion_path.py — 成交路径设计生成器（中文技能库 · xiaohongshu-conversion-path）

改编自 mengke-wang/xiaohongshu-ai-workbench（MIT © 2026 王梦珂），
把账号定位 / 产品服务 / 客单价 / 用户顾虑 / 当前内容，整理成一条
"从刷到你到愿意进一步了解"的成交路径方案：6 段路径、4 类内容分工（各 3 选题）、
主页承接、置顶内容、评论区动作、私信筛选问题。

用法示例：
    python draft_xiaohongshu_conversion_path.py 账号情况.txt --output path.md
    cat 账号情况.txt | python draft_xiaohongshu_conversion_path.py -

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
    "你是资深成交路径设计师。你的任务不是承诺成交，而是把用户提供的账号/产品/目标信息，"
    "整理成一条从'刷到你'到'愿意进一步了解'的可执行承接路径方案。\n"
    "必须遵守：\n"
    "1. 不承诺结果：不写任何成交率/转化率/涨粉/收入承诺，只做路径设计；\n"
    "2. 不编造事实：产品能力、价格、客户案例、成交数据一律以用户输入为准，"
    "输入里没有就不写，禁止引用外部案例或第三方背书；\n"
    "3. 结构化输出，严格包含以下小节：\n"
    "   - 当前路径判断（一句话，指出用户卡在哪一段：吸引/筛选/信任/行动/私信/复访）；\n"
    "   - 用户决策阻力（2-3 条，如贵/不信任/怕麻烦/不值，推断处标注（推断））；\n"
    "   - 内容分工 A 吸引内容 / B 信任内容 / C 筛选内容 / D 转化内容，"
    "每类先写一句目的，再给 3 个具体可执行的选题建议；\n"
    "   - 主页/落地页承接建议（第一眼让访客看到什么）；\n"
    "   - 置顶内容建议（3 条）；\n"
    "   - 评论区/互动区动作（作者主动做什么）；\n"
    "   - 私信筛选问题（3 个：问现状/问目标/问卡点，用问题筛需求，不一上来就成交）；\n"
    "   - 下一步最该改（只给 1 个优先级最高的动作）；\n"
    "   - 建议补充的信息（输入缺项清单，无缺项写'无'）；\n"
    "4. 推广免费工具/小程序时，把'成交'理解为体验、收藏、反馈、转发，不写购买话术；\n"
    "5. 客单价/交付方式/用户顾虑等关键输入缺失时，输出通用路径，并在末尾列出建议补充的信息，"
    "不确定处标注（待补充）；\n"
    "6. 选题建议要具体到能直接变成一篇内容/一封邮件/一个落地页模块，不写'加强信任'这类空话。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a conversion-path designer. Your job is not to promise sales, but to design "
    "an executable path from 'first impression' to 'willing to learn more'.\n"
    "Rules:\n"
    "1. Never promise conversion rates, growth or revenue; design paths, do not guarantee results.\n"
    "2. Never invent product capabilities, prices, testimonials or deal data; use only what the user provides.\n"
    "3. Structure strictly: current-path diagnosis; decision friction (2-3 items); "
    "content split A attract / B trust / C filter / D convert (each: purpose + 3 concrete topic ideas); "
    "homepage/landing-page handoff; pinned content (3 items); comment-area actions; "
    "DM screening questions (3 questions that qualify needs, not a sales pitch); "
    "the single highest-priority next fix; a list of missing inputs (or 'none').\n"
    "4. For free tools/miniprograms, treat 'conversion' as try, save, feedback and share - never purchase language.\n"
    "5. When key inputs (price, delivery, objections) are missing, output a generic path and list what to supplement.\n"
    "6. Topic ideas must be concrete enough to become a post, an email or a landing-page module.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_xiaohongshu_conversion_path",
        description="成交路径设计：从刷到你到愿意进一步了解的承接路径方案（中文技能库 · xiaohongshu-conversion-path）",
    )
    parser.add_argument("input", help="账号/产品情况说明文件路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.xiaohongshu-conversion-path.md）")
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
        raise SystemExit("错误：输入内容为空，请提供账号/产品情况说明文本。")
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
    print("输入文本：%d 字，切分为 %d 段，开始生成成交路径方案……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是账号/产品情况说明（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".xiaohongshu-conversion-path.md"
        else:
            out_path = base + ".xiaohongshu-conversion-path.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：路径方案请对照实际产品与用户复核后再执行。")


if __name__ == "__main__":
    main()