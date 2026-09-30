#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_xiaohongshu.py — 小红书文案草稿生成器（中文技能库 · xiaohongshu-copy）

把素材（口播转写 / 产品资料 / 体验 / 灵感碎片）改写成小红书可直接发布的文案：
标题（<=20 字 + 钩子）、封面文案、正文（钩子开头→分点干货→互动引导）、
话题标签、合规自查。

用法示例：
    python draft_xiaohongshu.py 素材.txt --style ganhuo --output note.md
    cat 素材.txt | python draft_xiaohongshu.py -

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

STYLES = {
    "caozhong": "种草型：突出使用场景与真实体验，用生活化的语气让人代入，结尾引导收藏。",
    "ganhuo": "干货型：条理化清单，分点讲清方法/避坑，信息密度高，让人想截图保存。",
    "qingxu": "情绪型：先放大共鸣情绪（焦虑/爽感/治愈），再给解决方案，转发意愿强。",
    "ceping": "测评型：客观多维度对比（价格/效果/适用人群），优缺点都写，增强可信度。",
}

SYSTEM_PROMPT = (
    "你是小红书资深运营兼文案写手。请把用户提供的素材改写成一篇"
    "可直接发布的小红书笔记。\n"
    "必须遵守：\n"
    "1. 忠于素材：体验、效果、数字必须来自素材本身，绝不编造、不虚构对比；\n"
    "2. 标题：每行不超过 20 字，含适量 emoji，制造好奇心缺口（结果前置/数字/对比/悬念），"
    "给出 1 个主标题 + 2 个备选；\n"
    "3. 封面文案：不超过 10 字的大字，一眼看懂利益点；\n"
    "4. 正文结构：钩子开头（3 秒抓人）→ 痛点/场景共鸣 → 分点干货（每点 1-2 句，emoji 分段）"
    "→ 真诚小结 → 互动引导（收藏/评论/关注）；\n"
    "5. 合规：不得使用'最、第一、根治、绝对、秒杀、全网'等绝对化用语与功效断言，"
    "医疗/功效类表达一律以'个人感受''仅供参考'呈现；\n"
    "6. 话题标签 8-10 个，垂直标签与泛流量标签结合；\n"
    "7. 输出完整笔记，最后附发布小贴士与合规自查。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior Xiaohongshu (Little Red Book) content operator and copywriter. "
    "Rewrite the provided source material into a ready-to-publish Xiaohongshu post.\n"
    "Rules:\n"
    "1. Stay faithful: experiences, results and numbers must come from the material only; never invent.\n"
    "2. Title: no more than 20 characters per line, with emoji and a curiosity hook; give 1 main + 2 alternatives.\n"
    "3. Cover text: a big one-liner under 10 characters conveying the benefit.\n"
    "4. Body: hook opening → pain point/empathy → bullet points with emoji → sincere wrap-up → CTA.\n"
    "5. Compliance: no superlatives (best, #1, cure, absolute) or efficacy claims; use 'personal feeling' / 'for reference'.\n"
    "6. 8-10 hashtags mixing niche and broad reach.\n"
    "7. Output the full post plus publishing tips and a compliance checklist.\n"
    "Output the Markdown body only."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_xiaohongshu",
        description="把素材改写成小红书可发布文案（中文技能库 · xiaohongshu-copy）",
    )
    parser.add_argument("input", help="素材文件路径，或用 - 从标准输入读取")
    parser.add_argument("--style", choices=sorted(STYLES), default="caozhong",
                        help="文案风格（默认 %(default)s）：caozhong 种草 / ganhuo 干货 / qingxu 情绪 / ceping 测评")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.xiaohongshu.md）")
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
        raise SystemExit("错误：输入内容为空，请提供素材文本。")
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
        "temperature": 0.7,
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

    text = read_input(args.input)
    chunks = chunk_text(text)
    print("素材：%d 字，切分为 %d 段，开始生成文案……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        style_note = ("\n\n风格要求：%s" % STYLES[args.style]) if args.lang == "zh" else (
            "\n\nStyle: %s" % {
                "caozhong": "lifestyle/种草: emphasize scenarios and real experience, warm tone, end with save CTA",
                "ganhuo": "listicle: organized tips and pitfalls, high information density, screenshot-worthy",
                "qingxu": "emotional: lead with relatable feeling, then solution, high shareability",
                "ceping": "review: objective multi-dimensional comparison, list pros and cons",
            }[args.style])
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是素材（第 %d/%d 段）：\n\n%s%s" % (i, len(chunks), chunk, style_note)},
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
            out_path = base.rsplit(".", 1)[0] + ".xiaohongshu.md"
        else:
            out_path = base + ".xiaohongshu.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：发布前请按『合规自查』复核，敏感类素材请人工确认。")


if __name__ == "__main__":
    main()
