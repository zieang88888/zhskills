#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_academic_polishing.py — 专业文稿润色（中文技能库 · academic-polishing）

把论文 / 技术报告 / 方案 / 制度 / 申报材料等专业文稿，按「类型×章节×语言×目标场合」
四轴路由做结构化润色：先内容后语言，输出润色稿 + 修改说明 + 证据边界检查 + 术语一致性。

用法示例：
    python draft_academic_polishing.py report.md --type 技术报告 --target 项目评审 -o polished.md
    cat report.md | python draft_academic_polishing.py - --type 制度

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

DOC_TYPES = ["论文", "技术报告", "方案", "制度", "申报材料"]

SYSTEM_PROMPT_ZH = (
    "你是资深专业文稿润色专家。请把用户提供的专业文稿，按「类型×章节×语言×目标场合」"
    "四轴路由做结构化润色，输出一份完整的 Markdown 成稿。\n"
    "必须遵守：\n"
    "1. 先内容后语言：第一轮只改主张—证据对应、章节结构、术语一致性与逻辑衔接；"
    "确认内容与结构定稿后，第二轮才动句式、用词、标点；不允许只改语言不动结构。\n"
    "2. 内容层检查：每个主张必须有支撑（数据/引文/案例/推导），数据可追溯（来源、口径、时间点）；"
    "缺支撑的主张要么降级表述，要么标（待确认），禁止靠修饰掩盖。\n"
    "3. 结构层检查：章节顺序、篇幅、详略符合该类型（论文/技术报告/方案/制度/申报材料）的文体惯例；"
    "修不了的结构问题不要硬改，标（待确认）并说明。\n"
    "4. 语言层检查：术语全文统一；句式服务于逻辑；语气与目标场合匹配。\n"
    "5. 证据边界：显式区分事实（有出处的观察/数据）、推断（基于证据的判断）、建议（行动主张）三类表述；"
    "模态词（表明/提示/可能/应当）与证据强度匹配，禁止把相关写成因果、把可能写成已经证明。\n"
    "6. 不虚构：绝不补写原文没有的数字、引文、案例；不改变作者原意与立场。\n"
    "输出严格包含四部分：\n"
    "（一）润色后全文（Markdown）；\n"
    "（二）修改说明，按内容层/结构层/语言层分组列出主要改动及理由，无改动的组写“无”；\n"
    "（三）证据边界检查表：逐条列出「原文表述 / 归类（事实·推断·建议）/ 是否越界 / 建议改法」；\n"
    "（四）术语一致性表：列出全文关键术语统一后的写法及原文分歧说明。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior professional-document polisher. Polish the user's draft "
    "through a four-axis router (document type x section x language x target venue), "
    "content first, language second. Output a complete Markdown manuscript.\n"
    "Rules:\n"
    "1. Content before language: fix claim-evidence support, section structure, "
    "terminology consistency and logical flow first; only then polish sentences, wording, punctuation.\n"
    "2. Every claim must have support; traceable data; unsupported claims are downgraded or marked (TBC).\n"
    "3. Section structure and length match the genre conventions of the given document type.\n"
    "4. Terminology unified across the whole text.\n"
    "5. Evidence boundary: explicitly separate facts / inferences / recommendations; "
    "modals match evidence strength; never turn correlation into causation or possibility into proof.\n"
    "6. Never invent numbers, citations or cases; never change the author's stance.\n"
    "Output four sections: (1) polished full text; (2) change log grouped by content/structure/language; "
    "(3) evidence-boundary table (original sentence / category / overstepped? / suggested fix); "
    "(4) terminology-consistency table.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_academic_polishing",
        description="把专业文稿按类型×章节×语言×目标场合四轴路由做结构化润色（中文技能库 · academic-polishing）",
    )
    parser.add_argument("input", help="文稿路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.academic-polishing.md）")
    parser.add_argument("--type", dest="doc_type", choices=DOC_TYPES, default="技术报告",
                        help="文稿类型（默认 %(default)s），可选：论文 / 技术报告 / 方案 / 制度 / 申报材料")
    parser.add_argument("--target", default="通用正式书面场合",
                        help="目标场合，如 项目评审 / 期刊投稿 / 内部存档 / 上级汇报（默认：%(default)s）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型名（默认 %(default)s）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help="OpenAI 兼容接口根地址（默认 %(default)s）")
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
        raise SystemExit("错误：输入内容为空，请提供待润色文稿文本。")
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
    system_prompt = SYSTEM_PROMPT_ZH if args.lang == "zh" else SYSTEM_PROMPT_EN

    text = read_input(args.input)
    chunks = chunk_text(text)
    print("输入文本：%d 字，类型=%s，目标场合=%s，语言=%s，切分为 %d 段，开始润色……"
          % (len(text), args.doc_type, args.target, args.lang, len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        user_content = (
            "文稿类型：%s\n目标场合：%s\n语言：%s\n"
            "以下是待润色文稿（第 %d/%d 段）：\n\n%s"
            % (args.doc_type, args.target, args.lang, i, len(chunks), chunk)
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
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
            out_path = base.rsplit(".", 1)[0] + ".academic-polishing.md"
        else:
            out_path = base + ".academic-polishing.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：润色稿请对照原文复核后再交付；证据边界检查与术语一致性清单请逐项确认。")


if __name__ == "__main__":
    main()