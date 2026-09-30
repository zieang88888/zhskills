#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_xiaohongshu_profile.py — 主页体检与简介改写生成器（中文技能库 · xiaohongshu-profile）

把用户提供的主页 / 档案素材（昵称、头像描述、简介、置顶内容、定位、目标用户等），
整理成一份结构化 Markdown 体检草稿：第一眼判断、主要问题、优先修改顺序、
4 版简介改写（清晰专业 / 亲近人话 / 转化引导 / 个人 IP）、置顶建议、下一步。

用法示例：
    python draft_xiaohongshu_profile.py profile_info.txt --output profile_checkup.md
    cat profile_info.txt | python draft_xiaohongshu_profile.py -

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
    "你是资深个人主页 / 档案体检师。请基于用户提供的真实信息（昵称、头像描述、当前简介、"
    "置顶 / 精选内容、账号定位、目标用户、产品 / 服务等），判断一个陌生人点进主页后，"
    "能否在 3 秒内看懂：你是谁、帮谁、解决什么问题、为什么可信、下一步做什么。\n"
    "必须遵守：\n"
    "1. 忠于输入：只基于用户提供的真实信息做诊断与改写，绝不编造粉丝量、转化率、客户数、作品、获奖或第三方背书；\n"
    "2. 七个诊断维度：第一眼清晰度、目标用户、具体结果、信任材料、转化动作、置顶 / 精选结构、语气一致性；\n"
    "3. 简介原则：短、具体、可判断；优先包含五要素——我是谁 / 帮哪类人 / 解决什么 / 通过什么方式 / 下一步动作；\n"
    "4. 避免抽象价值观堆叠、过度承诺、自夸无信息量、只写情绪不写对象与服务、同时服务太多人；\n"
    "5. 结构化输出：第一眼判断、主要问题（3 条）、优先修改顺序（3 条）、简介改写"
    "（A 清晰专业版 / B 亲近人话版 / C 转化引导版 / D 个人 IP 版）、置顶 / 精选建议（3 条）、下一步；\n"
    "6. 信息不足处标注（待确认），不要替用户编故事；\n"
    "7. 4 个简介版本是同一事实的不同语气表达，不得新增事实。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a personal-profile doctor. Based only on the user's real info "
    "(nickname, avatar description, current bio, pinned posts, positioning, "
    "target audience, product / service), judge whether a first-time visitor "
    "can understand within 3 seconds: who you are, who you help, what problem "
    "you solve, why you are credible, and what to do next.\n"
    "Rules:\n"
    "1. Stay faithful: never invent follower counts, conversion rates, testimonials, "
    "awards, works or endorsements not provided by the user.\n"
    "2. Diagnose on 7 dimensions: first-glance clarity, target audience, concrete result, "
    "trust signals, conversion action, pinned structure, tone consistency.\n"
    "3. Bio principles: short, specific, judgeable; prefer the five elements — who I am / "
    "whom I help / what I solve / how / next action.\n"
    "4. Avoid abstract value-stacking, over-promising, empty self-praise, emotion-only lines, "
    "and trying to serve everyone.\n"
    "5. Structure: first-glance verdict, top 3 problems, fix priority, four bio versions "
    "(A professional / B friendly / C conversion-driven / D personal IP), 3 pinned-post "
    "suggestions, next step.\n"
    "6. Mark uncertain items as (TBC).\n"
    "7. The four bio versions must reuse the same facts, just in different tones.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_xiaohongshu_profile",
        description="主页体检与简介改写草稿生成器（中文技能库 · xiaohongshu-profile）",
    )
    parser.add_argument("input", help="主页 / 档案素材路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.xiaohongshu-profile.md）")
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
        raise SystemExit("错误：输入内容为空，请提供主页 / 档案素材。")
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
    print("输入素材：%d 字，切分为 %d 段，开始生成主页体检草稿……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是用户主页 / 档案的素材（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".xiaohongshu-profile.md"
        else:
            out_path = base + ".xiaohongshu-profile.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：草稿请对照你提供的真实信息复核后再交付。")


if __name__ == "__main__":
    main()