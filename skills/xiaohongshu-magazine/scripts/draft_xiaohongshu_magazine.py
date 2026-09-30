#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_xiaohongshu_magazine.py — 小红书杂志选题库草稿生成器（中文技能库 · xiaohongshu-magazine）

把账号定位 / 目标用户 / 产品或服务 / 个人经历等描述，当成一本杂志来办，
整理成结构化 Markdown 选题库草稿：刊魂母题、业务或个人 IP 判断、栏目结构、
按信任/喜欢分类的选题库（每栏目 3-6 篇并标注角度公式）、优先发布建议。

用法示例：
    python draft_xiaohongshu_magazine.py positioning.txt --output magazine.md
    cat positioning.txt | python draft_xiaohongshu_magazine.py -

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
    "你是资深内容主编。请把用户提供的账号定位、目标用户、产品或服务、个人经历等信息，"
    "当成一本杂志来办，整理成一份可直接交付的结构化 Markdown 选题库草稿。\n"
    "必须遵守：\n"
    "1. 只基于用户提供的信息：不引用外部资料、他人案例或第三方背书，"
    "不编造账号数据、行业数据、平台趋势；\n"
    "2. 不承诺涨粉、爆款、成交或任何平台算法结果；\n"
    "3. 先定刊魂（母题）：一句话承诺，是读者只记住的那一句，不是一个话题；一本杂志只有一个刊魂；\n"
    "4. 判断杂志类型：围绕业务还是围绕个人 IP，判断句为——读者取关是因为不再需要这个产品，"
    "还是不再喜欢这个人，并据此说明理由；\n"
    "5. 栏目结构：从 8 个通用栏目（①我是谁·为什么是我 ②我怎么看这件事 ③我是怎么做的 "
    "④我服务过谁·结果长啥样 ⑤我踩过什么坑 ⑥我懂你 ⑦我在坚持什么 ⑧人味日常）中挑 4-6 个，"
    "标注每个是「信任」还是「喜欢」，并说明这栏为什么重要；\n"
    "6. 选题库：每个栏目用 9 个角度公式（一个误区 / X 个坑或 X 个方法的清单 / 如果重来 / "
    "最近一件真事 / 反常识 / 幕后过程拆解 / 对比 / 一句话观点加展开 / 回答高频问题）"
    "长出 3-6 篇具体选题，每篇标注所用角度公式；\n"
    "7. 挂回刊魂：每篇选题必须能挂回母题，挂不回去的不要放进来；\n"
    "8. 给出优先发布建议：冷启动期先重信任地基（多用栏目①③④），稳定期信任与喜欢交替；\n"
    "9. 输入信息不足处标注（待确认），并列出需要用户补充的问题，不得脑补账号定位。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior content editor. Treat the user's account positioning, audience, "
    "product/service and personal experience as one magazine, and produce a deliverable, "
    "well-structured Markdown topic-library draft.\n"
    "Rules:\n"
    "1. Use only the information provided by the user; no external sources, case studies, "
    "or fabricated account/industry/platform data.\n"
    "2. Never promise growth, viral hits, sales, or any platform-algorithm outcome.\n"
    "3. First define the 'soul' (one-sentence promise readers remember; only one per magazine).\n"
    "4. Decide whether the magazine is business-centric or personal-IP-centric, using the test: "
    "readers unfollow because they no longer need the product, or because they no longer like the person.\n"
    "5. Pick 4-6 of the 8 generic columns (who I am / how I see things / how I work / whom I served / "
    "mistakes I made / I get you / what I insist on / human side), tagging each as trust or like.\n"
    "6. Grow 3-6 concrete topics per column using 9 angle formulas (common myth / list / if I restarted / "
    "a recent true story / counter-intuitive / behind the scenes / contrast / viewpoint + expansion / FAQ), "
    "tagging each topic with its formula.\n"
    "7. Every topic must trace back to the soul; drop the ones that cannot.\n"
    "8. Give a publishing-priority suggestion: cold-start favors trust columns, then alternate trust and like.\n"
    "9. Mark missing information as (TBC) and list what the user should supply; never invent positioning.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_xiaohongshu_magazine",
        description="把账号定位描述整理成「杂志感」选题库草稿（中文技能库 · xiaohongshu-magazine）",
    )
    parser.add_argument("input", help="账号定位 / 素材描述文件路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.xiaohongshu-magazine.md）")
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
        raise SystemExit("错误：输入内容为空，请提供账号定位 / 素材描述文本。")
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
    print("输入文本：%d 字，切分为 %d 段，开始生成选题库草稿……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是账号定位 / 素材描述（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".xiaohongshu-magazine.md"
        else:
            out_path = base + ".xiaohongshu-magazine.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：草稿请对照账号真实信息复核后再交付。")


if __name__ == "__main__":
    main()