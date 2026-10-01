#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_data_storytelling.py — 数据叙事报告草稿生成器（中文技能库 · data-storytelling）

把一堆零散的数据/指标/分析结果，组织成一份有叙事结构的汇报报告：
先定一句话核心信息，再从问题-解决方案/趋势/对比三种框架里选一个，
按框架组织数据支撑与洞察，最后落到建议与不确定性声明。

用法示例：
    python draft_data_storytelling.py metrics.txt --output report.md
    python draft_data_storytelling.py metrics.txt --framework 趋势
    cat metrics.txt | python draft_data_storytelling.py -

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
FRAMEWORKS = ["问题-解决方案", "趋势", "对比"]

SYSTEM_PROMPT_ZH = (
    "你是资深数据叙事顾问，擅长把零散的数据/指标组织成能推动决策的汇报报告。"
    "请把用户提供的数据清单与汇报背景，整理成一份可直接交付的结构化 Markdown 数据叙事报告。\n"
    "必须遵守：\n"
    "1. 只用用户提供的数据，绝不编造数字；需要举例或外推时，明确标注「（估算，需验证）」；\n"
    "2. 核心信息一句话，必须能从给定数据直接推出，写成「主语+动作+结果」的结论句；\n"
    "3. 故事框架三选一：问题-解决方案 / 趋势 / 对比，并写一句为什么选它；用户若通过 --framework 指定，必须尊重指定；\n"
    "4. 数据支撑每条写成「结论式小标题 + 原始数字 + 变化 + 含义」，一条数据一个小标题，禁止「XX 分析」这类空标题；\n"
    "5. 叙事结构按所选框架组织成起承转合，并在数据与结论之间给出过渡话术示例；\n"
    "6. 洞察与建议 3-5 条，每条严格按「数据 → 洞察 → 建议」三段写，建议必须可执行；\n"
    "7. 不确定性必须显式表达：用「约 / 可能 / 需进一步验证」，禁止「必然/一定/绝对」式断言；区间估算写上下界；\n"
    "8. 报告固定包含 7 节：核心信息、故事框架选择、数据支撑、叙事结构、洞察与建议、不确定性声明、Do & Don't 自查；\n"
    "9. 不做数据瀑布：砍掉所有不支撑核心信息的数字；不为展示牺牲真实。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior data-storytelling consultant. Turn the user's data list and "
    "reporting context into a structured, deliverable Markdown data-storytelling report.\n"
    "Rules:\n"
    "1. Use only the data provided; never invent numbers. Mark any extrapolation as (estimate, to verify).\n"
    "2. Lead with a one-line core message, phrased as 'subject + action + result' and directly derivable from the data.\n"
    "3. Pick exactly one story framework (Problem-Solution / Trend / Comparison) and justify it; honor the user's --framework choice if given.\n"
    "4. Each data point gets a conclusion-style subheading plus raw number / change / implication; no vague headings like 'XX analysis'.\n"
    "5. Structure the narrative arc around the chosen framework, with transition phrases between data and conclusions.\n"
    "6. Give 3-5 insights, each as data -> insight -> recommendation; recommendations must be actionable.\n"
    "7. Express uncertainty explicitly ('about / may / needs further validation'); no absolute claims; give ranges for estimates.\n"
    "8. Output strictly 7 sections: core message, framework choice, data support, narrative structure, "
    "insights & recommendations, uncertainty statement, Do & Don't self-check.\n"
    "9. No data dump; cut numbers that don't support the core message; never sacrifice truth for presentation.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_data_storytelling",
        description="把数据/指标清单整理成有叙事结构的数据汇报报告（中文技能库 · data-storytelling）",
    )
    parser.add_argument("input", help="数据清单与汇报背景文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.data-storytelling.md）")
    parser.add_argument("--framework", choices=FRAMEWORKS, default=None,
                        help="指定故事框架：问题-解决方案 / 趋势 / 对比（不传则由模型根据数据形态自动选择）")
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
        raise SystemExit("错误：输入内容为空，请提供数据/指标清单与汇报背景文本。")
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
    print("输入文本：%d 字，切分为 %d 段，开始生成数据叙事报告……" % (len(text), len(chunks)), file=sys.stderr)

    framework_note = ""
    if args.framework:
        framework_note = (
            "\n用户指定故事框架：%s（必须采用，并在「故事框架选择」一节说明这是用户指定）。\n"
            % args.framework
        )

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        user_content = (
            "以下是数据/指标清单与汇报背景（第 %d/%d 段）：\n\n%s%s"
            % (i, len(chunks), framework_note, chunk)
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
            out_path = base.rsplit(".", 1)[0] + ".data-storytelling.md"
        else:
            out_path = base + ".data-storytelling.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：草稿请对照原始数据复核后再交付。")


if __name__ == "__main__":
    main()