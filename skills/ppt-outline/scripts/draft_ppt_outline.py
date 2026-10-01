#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_ppt_outline.py — PPT 大纲草稿生成器（中文技能库 · ppt-outline）

把用户提供的材料（会议纪要、方案文档、要点列表、或一个主题+几条要点）
整理成可直接做 PPT 的分页 Markdown 大纲草稿：每页有标题、口语化讲稿要点
（能照着讲）、视觉/排版建议；覆盖封面 → 主体 → 收尾完整结构，标总页数与建议时长。

用法示例：
    python draft_ppt_outline.py material.txt --output outline.md
    python draft_ppt_outline.py material.txt --pages 8
    cat material.txt | python draft_ppt_outline.py -

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
DEFAULT_PAGES = 10         # 页数规模上限（写进系统提示词让模型按此规划）

SYSTEM_PROMPT_ZH = (
    "你是资深 PPT 演示策划。请把用户提供的材料，整理成一份可直接做 PPT、"
    "照着讲的分页大纲 Markdown 草稿。\n"
    "必须遵守：\n"
    "1. 忠于原文：只整理材料中真实出现的信息，绝不编造、补写、猜测；"
    "不确定处标注（待确认）；\n"
    "2. 信息保全：数字、金额、日期、人名、项目名必须保留，不得丢失或改写；\n"
    "3. 每页一个核心信息：禁止一页塞多个主题，宁可拆成两页，也不挤成一页；\n"
    "4. 结构完整：先写文档头（主题 / 总页数 / 建议时长 / 演讲场景与受众），"
    "再逐页展开「第 N 页 · 标题」，每页含——讲稿要点（3-6 条口语化 bullet，"
    "能照着直接念）与视觉建议（一句话：图 / 表 / 关键词 / 版式）；\n"
    "5. 收尾页：行动号召（CTA）或一句话总结；\n"
    "6. 总页数不超过 %d 页（含封面与收尾），页数规模按此上限规划；\n"
    "7. 口语化不等于随意：关键术语保留原文写法，bullet 写成完整短句，不要只写关键词。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior presentation outline designer. Turn the provided material "
    "into a slide-by-slide Markdown outline ready to build a PPT from and to speak from.\n"
    "Rules:\n"
    "1. Stay faithful: only use information actually present in the material; never invent; "
    "mark uncertain items as (TBC).\n"
    "2. Preserve key facts: numbers, amounts, dates, names, project names must all be kept.\n"
    "3. One core idea per slide: never cram multiple topics into one slide; split instead.\n"
    "4. Structure: header (topic / total pages / suggested duration / audience), then "
    "per-slide \"Slide N · Title\" each with speaking points (3-6 oral bullets, readable aloud) "
    "and a one-line visual/layout suggestion; end with a closing CTA or summary slide.\n"
    "5. Total pages must not exceed %d (including cover and closing); plan the page count within this cap.\n"
    "6. Oral style does not mean sloppy: keep key terms as written; bullets are full sentences, not keywords.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_ppt_outline",
        description="把材料整理成可直接做 PPT 的分页大纲草稿（中文技能库 · ppt-outline）",
    )
    parser.add_argument("input", help="材料文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.ppt-outline.md）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型名（默认 %(default)s）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI 兼容接口根地址（默认 %(default)s）")
    parser.add_argument("--api-key", default=None, help="API Key（优先于环境变量）")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言（默认 zh）")
    parser.add_argument("--pages", type=int, default=DEFAULT_PAGES,
                        help="页数规模上限（含封面与收尾，默认 %(default)s）")
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
        raise SystemExit("错误：输入内容为空，请提供材料文本。")
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
        "temperature": 0.4,
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
    tpl = SYSTEM_PROMPT_ZH if args.lang == "zh" else SYSTEM_PROMPT_EN
    system_prompt = tpl % args.pages

    text = read_input(args.input)
    chunks = chunk_text(text)
    print("输入文本：%d 字，切分为 %d 段，页数上限 %d 页，开始生成 PPT 大纲草稿……"
          % (len(text), len(chunks), args.pages), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是材料（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".ppt-outline.md"
        else:
            out_path = base + ".ppt-outline.md"

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