#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_xiaohongshu_comment_reply.py — 评论区回复生成器（中文技能库 · xiaohongshu-comment-reply）

改编自 mengke-wang/xiaohongshu-ai-workbench（MIT © 2026 王梦珂），
把一条或多条评论变成像真人、有边界、能延续对话的回复：
友好 / 专业 / 更像评论区 / 引导私信四个版本 + 一个"不建议这样回"反例，
恶意评论优先给不争辩的处理建议。

用法示例：
    python draft_xiaohongshu_comment_reply.py 评论.txt --persona 亲切 --output replies.md
    python draft_xiaohongshu_comment_reply.py 评论.txt --persona 品牌号
    cat 评论.txt | python draft_xiaohongshu_comment_reply.py -

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
CHUNK_SIZE = 9000
CHUNK_OVERLAP = 400
REQUEST_TIMEOUT = 120

PERSONAS = ["专业", "亲切", "幽默", "品牌号", "个人IP"]

SYSTEM_PROMPT_ZH = (
    "你是中文互联网评论区回复助手。任务是让回复像真人、有边界、能延续对话，"
    "而不是客服模板。场景覆盖小红书、微博、社群互动与电商差评回复。\n"
    "必须遵守：\n"
    "1. 先回应对方说了什么，再补充自己的意思；开头先接住对方原话，不自说自话；\n"
    "2. 少客服腔：默认不用'亲''呢''哦～''感谢您的反馈呢'等模板句；感叹号默认不用，最多 1 个；\n"
    "3. 不吵架、不阴阳怪气、不抬杠、不反讽、不在公开区对线；\n"
    "4. 不把每条评论都导向私信：对方没有一对一沟通需求时，不要硬推；\n"
    "5. 质疑类评论：先承认对方关心点/顾虑合理，再说明边界，不一上来就辩解；\n"
    "6. 涉及价格、效果、法律、医疗、财务时不做承诺、不下定论，用'以官方页面/合同/医生意见为准''具体情况具体看'；\n"
    "7. 不编造产品事实：价格、优惠、发货时间、参数、资质背书，输入没给就不写；不确定处标注（待确认）；\n"
    "8. 明显恶意、辱骂、引战的评论：不争辩，优先给'不予回复/置顶统一说明/举报/删除'的处理建议，不写骂回去的话。\n"
    "输出格式（单条评论，严格按此 5 段）：\n"
    "友好回复：（先接住情绪，轻松能聊）\n"
    "专业回复：（信息准确有边界，适合品牌号/知识账号）\n"
    "更像评论区的回复：（短、像真人接话）\n"
    "引导私信版：（仅在确实需要一对一沟通时给出；否则写'本条不建议引导私信'）\n"
    "不建议这样回：（一个危险/生硬/抬杠/过度承诺的写法）\n"
    "原因：（为什么不能这么回）\n"
    "如果输入是多条评论：逐条给'原评论/推荐回复/备选回复'，最后给一条置顶评论建议；\n"
    "如果输入是笔记正文并要求置顶评论：给 A 补充价值 / B 引导讨论 / C 引导体验三条。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a Chinese social-media comment-reply assistant. Make replies sound human, "
    "have boundaries, and keep the conversation going - not like customer-service templates.\n"
    "Rules: respond to what the commenter said first; avoid robotic phrasing and exclamation marks; "
    "never argue or be passive-aggressive; don't push every comment to DMs; acknowledge concerns of "
    "critical comments first; make no commitments about price, effects, legal, medical or financial "
    "matters; never invent product facts; for hostile comments, advise against arguing (ignore / pin a "
    "unified note / report / delete).\n"
    "For a single comment output five sections: friendly reply, professional reply, comment-area-style "
    "reply, DM-guidance version (or state DM push is not advised here), and a discouraged reply with its reason.\n"
    "Output the Markdown body only."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_xiaohongshu_comment_reply",
        description="把评论变成像真人、有边界的回复草稿（中文技能库 · xiaohongshu-comment-reply）",
    )
    parser.add_argument("input", help="评论内容/笔记正文文件路径，或用 - 从标准输入读取")
    parser.add_argument("--persona", choices=PERSONAS, default=None,
                        help="账号人设（默认不指定：温和、清楚、不硬推）")
    parser.add_argument("--output", "-o",
                        help="输出 Markdown 文件路径（默认：输入名.xiaohongshu-comment-reply.md）")
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
        raise SystemExit("错误：输入内容为空，请提供评论或笔记正文文本。")
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
    system_prompt = SYSTEM_PROMPT_ZH if args.lang == "zh" else SYSTEM_PROMPT_EN

    persona_note = ""
    if args.persona:
        persona_note = (
            "\n账号人设：%s。回复语气贴合这个人设：专业=给信息与边界；"
            "亲切=有温度；幽默=可接梗但不刻薄；品牌号=稳重克制；个人IP=像朋友说话。"
        ) % args.persona

    text = read_input(args.input)
    chunks = chunk_text(text)
    persona_desc = args.persona or "未指定"
    print("输入：%d 字，切分为 %d 段，人设：%s，开始生成回复草稿……"
          % (len(text), len(chunks), persona_desc), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content":
                "以下是需要回复的评论/内容（第 %d/%d 段）：\n\n%s%s"
                % (i, len(chunks), chunk, persona_note)},
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
            out_path = base.rsplit(".", 1)[0] + ".xiaohongshu-comment-reply.md"
        else:
            out_path = base + ".xiaohongshu-comment-reply.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：回复发出前请人工复核，确保没有过度承诺或泄露未公开信息。")


if __name__ == "__main__":
    main()