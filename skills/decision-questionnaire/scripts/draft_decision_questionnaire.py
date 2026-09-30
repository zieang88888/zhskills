#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_decision_questionnaire.py — 决策问卷草稿生成器（中文技能库 · decision-questionnaire）

把"用户自己拍不了板、需要向某个特定的人确认"的访谈要点，转成一份可直接发送、
可异步填写的中文 Markdown 决策问卷草稿：问卷用途、背景、答题说明（含容错提示）、
按主题分组的问题（最重要排最前、一题一意图、留答题空位）、末尾开放题。

用法示例：
    python draft_decision_questionnaire.py interview_notes.txt --output q.md
    cat interview_notes.txt | python draft_decision_questionnaire.py -

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
CHUNK_OVERLAP = 400         # 相邻分段的交叠量，避免切断句子
REQUEST_TIMEOUT = 120       # 秒

SYSTEM_PROMPT_ZH = (
    "你是资深业务问卷设计师。用户会给你一份访谈要点：这份问卷发给谁（收件人的岗位 / "
    "专长 / 与用户的关系）、用户需要从对方那里拿回哪些具体的决策或事实、事情的背景。\n"
    "请据此产出一份可直接发送的中文 Markdown 决策问卷草稿。\n"
    "必须遵守：\n"
    "1. 拷问发送者、不拷问被访者：只问事实与判断，不问态度、责任与立场；\n"
    "2. 只问对方能答的事：每道题必须落在收件人的岗位职责 / 经历 / 数据范围内；\n"
    "3. 一题一意图：禁止复合问句；最重要的问题排最前；\n"
    "4. 结构完整：标题（# 决策问卷 · 主题）、问卷用途与收发信息（发件人 / 收件人 / 答复用途）、"
    "一段背景、答题说明（截止时间 + 预计耗时，且必须含\"不知道也请标注、不要空着跳过\"的容错提示）、"
    "按主题用 ## 分组的问题（每题下方留 > 引用块作答区，易被误解或易敷衍处加一行\"为什么问这个\"）、"
    "末尾开放题\"还有什么遗漏\"；\n"
    "5. 中文公文式措辞：用\"烦请\"\"敬请于……前反馈\"等职场书面语；\n"
    "6. 覆盖度：访谈要点中点名要拿回的每一项，必须至少被一道题覆盖；信息不足处标注（待用户确认），"
    "不得编造收件人信息或背景；\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior business questionnaire designer. The user gives you interview notes: "
    "who the questionnaire goes to (recipient's role / expertise / relationship), what specific "
    "decisions or facts the user needs back, and the background.\n"
    "Produce a ready-to-send Markdown discovery questionnaire.\n"
    "Rules:\n"
    "1. Grill the sender, not the subject: ask facts and judgments, never attitudes or blame.\n"
    "2. Only ask what the recipient can actually answer.\n"
    "3. One idea per question; never compound; order most-important first.\n"
    "4. Structure: title, Purpose / From / To / How answers will be used, one-paragraph context, "
    "how-to-answer (deadline, rough effort, and the tolerance note that 'I don't know' is welcome "
    "rather than skipped), questions grouped by ## theme with a '> ' answer stub under each and a "
    "one-line 'why this matters' only where needed, and a closing catch-all 'Anything else?'.\n"
    "5. Every item the user listed as needed-back must be covered by at least one question.\n"
    "Mark gaps as (TBC); never invent recipient details.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_decision_questionnaire",
        description="把用户访谈要点转成可异步填写的决策问卷草稿（中文技能库 · decision-questionnaire）",
    )
    parser.add_argument("input", help="访谈要点文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.decision-questionnaire.md）")
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
        raise SystemExit("错误：输入内容为空，请提供用户访谈要点文本。")
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
    print("输入文本：%d 字，切分为 %d 段，开始生成问卷草稿……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是用户访谈要点（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".decision-questionnaire.md"
        else:
            out_path = base + ".decision-questionnaire.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：草稿请对照访谈要点复核后再发送。")


if __name__ == "__main__":
    main()