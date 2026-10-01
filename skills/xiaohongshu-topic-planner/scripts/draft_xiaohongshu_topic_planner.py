#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_xiaohongshu_topic_planner.py — 选题日历生成器（中文技能库 · xiaohongshu-topic-planner）

把账号定位与运营目标拆成 6 类功能选题（吸引/共鸣/信任/教育/转化/互动），
产出选题池 + 优先级排序 + 发布日历 + 系列选题建议。

用法示例：
    python draft_xiaohongshu_topic_planner.py brief.txt --output plan.md
    python draft_xiaohongshu_topic_planner.py brief.txt --days 30 -o plan.md
    cat brief.txt | python draft_xiaohongshu_topic_planner.py -

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
DEFAULT_DAYS = 14         # 默认规划周期天数

SYSTEM_PROMPT_ZH = (
    "你是资深内容选题策划师。请把用户提供的账号定位、运营目标"
    "（可含已有栏目、产品信息、近期热点、素材），整理成一份可直接执行的"
    "结构化 Markdown「选题日历」草稿。\n"
    "必须遵守：\n"
    "1. 方法论——6 类功能选题，每条选题必须带功能标签（发这条是为了什么）：\n"
    "   吸引（让目标用户觉得\"这和我有关\"）、共鸣（说出用户正在经历的问题）、\n"
    "   信任（展示方法、判断力、过程和边界）、教育（解释概念、误区、步骤）、\n"
    "   转化（让用户知道你提供什么、适合谁、不适合谁）、\n"
    "   互动（适合评论区讨论和收集反馈）；\n"
    "2. 配比随账号阶段调整：冷启动期重吸引 + 共鸣；稳定期重信任 + 转化；"
    "教育、互动贯穿全程做调节；\n"
    "3. 结构化输出，严格包含 5 节：\n"
    "   ① 账号定位与目标复述（信息不足处标注\"（待确认）\"）；\n"
    "   ② 选题池——按 6 类分组，每条含：标题方向 / 功能标签 / 一句话思路 / "
    "对应栏目（无栏目写\"（待挂栏目）\"）；\n"
    "   ③ 优先级排序——按对目标达成的贡献排序，前 5 条各给一句理由；\n"
    "   ④ 发布日历——表格：日期 / 选题 / 功能 / 栏目 / 发布形式；按功能节奏排布，"
    "相邻两天不得为同一功能；\n"
    "   ⑤ 系列选题建议——可拆成连续系列的主题 + 更新顺序；\n"
    "4. 每条选题必须与本周期目标相关；不服务于目标的选题不要写入；\n"
    "5. 不编造行业数据、平台趋势，不承诺爆款 / 涨粉 / 搜索排名；\n"
    "6. 若用户提供了已有栏目 / 母题，每条选题挂回对应栏目；没有则标注"
    "\"（待挂栏目）\"并提示先定刊；\n"
    "7. 规划周期为 {days} 天，发布日历从明天起按此天数排布。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior content planner. Convert the account positioning and goals "
    "(plus any existing columns, product info, trends, materials) into a structured "
    "Markdown topic calendar draft.\n"
    "Rules:\n"
    "1. Use 6 functional topic types, each tagged with its function "
    "(attract / resonate / trust / educate / convert / interact);\n"
    "2. Adjust the mix by stage: cold-start leans attract+resonate; stable stage "
    "leans trust+convert; educate/interact run throughout;\n"
    "3. Strictly output 5 sections: (1) positioning & goal recap with "
    "(TBC) marks; (2) topic pool grouped by 6 types, each with title direction / "
    "function tag / one-line idea / column; (3) priority ranking, top 5 with reasons; "
    "(4) publishing calendar table (date / topic / function / column / format) with "
    "no two consecutive days sharing the same function; (5) series suggestions with "
    "update order;\n"
    "4. Every topic must serve the stated goal;\n"
    "5. Never fabricate data or promise virality/growth;\n"
    "6. Planning horizon: {days} days, calendar starts tomorrow.\n"
    "Output the Markdown body only."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_xiaohongshu_topic_planner",
        description="把账号定位与目标拆成 6 类功能选题，产出选题日历（中文技能库 · xiaohongshu-topic-planner）",
    )
    parser.add_argument("input", help="账号定位与目标文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.xiaohongshu-topic-planner.md）")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="规划周期天数（默认 %(default)s 天）")
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
        raise SystemExit("错误：输入内容为空，请提供账号定位与运营目标文本。")
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
    system_prompt = tpl.format(days=args.days)

    text = read_input(args.input)
    chunks = chunk_text(text)
    print("输入文本：%d 字，切分为 %d 段，规划周期 %d 天，开始生成选题日历……"
          % (len(text), len(chunks), args.days), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是账号定位与目标素材（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".xiaohongshu-topic-planner.md"
        else:
            out_path = base + ".xiaohongshu-topic-planner.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：草稿请对照账号实际情况复核后再发布。")


if __name__ == "__main__":
    main()