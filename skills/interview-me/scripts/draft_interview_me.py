#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_interview_me.py — 需求澄清访谈报告生成器（中文技能库 · interview-me）

把用户一句话式的模糊需求委托（"领导说做个东西""客户要个方案""老板让我优化一下"）
单轮收敛成一份可逐条确认的结构化需求澄清报告：
初步假设（带置信度）→ 访谈问题清单（每问附猜测答案）→ 6 行需求复述（待确认）→ 待确认汇总与下一步。

用法示例：
    python draft_interview_me.py ask.txt --output ask.clarified.md
    python draft_interview_me.py ask.txt --focus "重点确认成功标准和预算"
    echo "领导让我做个数据看板" | python draft_interview_me.py -

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
    "你是资深需求澄清访谈教练。用户给你的是一句模糊的需求委托"
    "（如\"领导说做个东西\"\"客户要个方案\"\"老板让我优化一下\"），"
    "你要在单轮内把它收敛成一份可逐条确认的结构化需求澄清报告。\n"
    "必须遵守：\n"
    "1. 忠于原文：只基于用户给出的描述做推断，绝不编造用户没说的背景、人名、数据、预算；\n"
    "2. 猜测必须挂牌：所有猜测答案都要显式标注\"（这是猜测，请确认或修正）\"，不许把假设写成事实；\n"
    "3. 一问一意图：每道访谈题只问一个意图，绝不复合提问；问题 3-8 道，按重要性降序排列；\n"
    "4. 假设带数字：初步假设每条附诚实的置信度百分比，低于 70% 同行写一句\"还缺什么\"；\n"
    "5. 套话必追问：若需求里出现\"最佳实践/可扩展/通用做法/应该更专业\"等套话倾向，"
    "必须补一道追问：\"如果不用向任何人解释、不用显得专业，你真正想要什么？\"；\n"
    "6. 6 行复述不可省略：Outcome（结果）/ User（谁受益）/ Why now（为什么现在）/ "
    "Success（怎么算成了）/ Constraint（最硬约束）/ Out of scope（明确不做），六行缺一不可，"
    "每行末尾标注\"（待确认）\"；\n"
    "7. 信息不足处一律标\"（待确认）\"，不要填看似合理的默认值糊弄过去。\n"
    "输出必须严格包含四节：一、需求原文与初步假设；二、访谈问题清单（每问附猜测答案与理由）；"
    "三、6 行需求复述；四、待确认事项汇总与下一步。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior requirement-clarification coach. The user gives you an underspecified "
    "ask (e.g. 'my boss wants something built', 'the client wants a proposal'). "
    "Produce a single-round, line-by-line confirmable requirement-clarification report.\n"
    "Rules:\n"
    "1. Stay faithful: never invent background, names, numbers or budget the user did not state.\n"
    "2. Flag every guess as '(guess - please confirm or correct)'.\n"
    "3. One question = one intent; 3-8 questions, most important first.\n"
    "4. Attach an honest confidence % to each hypothesis; below ~70% add what is still missing.\n"
    "5. If buzzwords appear, ask: 'If you didn't have to justify this to anyone, what would you actually want?'\n"
    "6. The 6-line restate is mandatory: Outcome / User / Why now / Success / Constraint / "
    "Out of scope - each line marked (TBC).\n"
    "7. Mark insufficient info as (TBC); do not fill plausible defaults.\n"
    "Output four sections: original ask & hypotheses; interview question list with guessed answers; "
    "the 6-line restate; open items & next step.\n"
    "Output the Markdown body only, no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_interview_me",
        description="把一句话模糊需求委托收敛成可逐条确认的需求澄清报告（中文技能库 · interview-me）",
    )
    parser.add_argument("input", help="需求描述文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.interview-me.md）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型名（默认 %(default)s）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI 兼容接口根地址（默认 %(default)s）")
    parser.add_argument("--api-key", default=None, help="API Key（优先于环境变量）")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言（默认 zh）")
    parser.add_argument("--focus", default=None, help="可选：本次重点澄清方向（如\"重点确认成功标准和预算\"）")
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
        raise SystemExit("错误：输入内容为空，请提供用户对需求的模糊描述文本。")
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
    print("输入文本：%d 字，切分为 %d 段，开始生成需求澄清报告……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        user_content = "以下是用户的模糊需求描述（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)
        if args.focus:
            user_content += "\n\n本次重点澄清方向：%s" % args.focus
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
            out_path = base.rsplit(".", 1)[0] + ".interview-me.md"
        else:
            out_path = base + ".interview-me.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：报告中的猜测答案均为推断，请逐条确认或修正后再进入设计。")


if __name__ == "__main__":
    main()