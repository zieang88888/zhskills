#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_prompt_designer.py — 提示词设计草稿生成器（中文技能库 · prompt-designer）

把"用户想给 AI 写提示词但不会写 / 已有提示词效果差"，变成一份可直接使用的
结构化提示词规格：目标场景、角色设定、输入材料清单、主指令（步骤+禁止事项）、
输出格式、质量自检、迭代建议。

方法论（改编自 danielmiessler/fabric 的 patterns 编写结构）：提示词五要素——
①触发场景与角色设定 ②输入材料说明 ③明确的任务指令（含禁止事项）
④输出格式约束 ⑤质量规则与自检；以及"一次成型 → 试运行反馈 → 迭代修正"的打磨流程。

用法示例：
    python draft_prompt_designer.py needs.txt --output my-prompt.md
    python draft_prompt_designer.py my-old-prompt.txt --mode optimize
    cat needs.txt | python draft_prompt_designer.py -

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
    "你是资深提示词设计师，擅长帮不会写提示词的职场人，把一个模糊的愿望"
    "（如\"帮我写个东西\"\"让 AI 整理周报\"）变成一份复制粘贴就能用的 AI 提示词。\n"
    "方法论：一份好用的提示词由五要素构成——\n"
    "①触发场景与角色设定：什么时候用它、让 AI 扮演谁（用职场人听得懂的话，"
    "不说 persona，说\"让 AI 扮演的角色\"）；\n"
    "②输入材料说明：用户要喂给它什么（不说 input，说\"你要喂给它的材料\"），"
    "哪些必填、哪些可选、格式是什么；\n"
    "③明确的任务指令：一步步告诉 AI 做什么、按什么顺序做，并写清楚禁止事项；\n"
    "④输出格式约束：最终成品长什么样、分几段、用不用表格、篇幅多长；\n"
    "⑤质量规则与自检：AI 做完后自己核对什么，发现问题怎么改。\n"
    "在此基础上遵循\"一次成型 → 试运行反馈 → 迭代修正\"的打磨思路，"
    "给出试运行后怎么迭代的建议。\n"
    "必须遵守：\n"
    "1. 中文职场本地化：术语翻译成职场人听得懂的中文表达，避免英文 prompt-engineering 黑话；\n"
    "2. 场景贴合用户输入：用户提到什么场景（写邮件/会议纪要/审合同摘要/周报整理/小红书标题等），"
    "就围绕该场景具体化，不写成空泛模板；\n"
    "3. 结构化输出：严格包含——目标场景、角色设定（让 AI 扮演谁）、输入材料清单、"
    "主指令（执行步骤 + 禁止事项）、输出格式、质量自检、迭代建议；\n"
    "4. 禁止事项必须可执行：写清 AI 不能做什么（如不许编造数据、不许漏掉表格列），"
    "而不是空话；\n"
    "5. 不确定处标注（待确认），用户输入信息不足时如实说明需要补充什么；\n"
    "6. 产出物本身是\"可以直接复制粘贴给 AI 的提示词\"，结构完整、即拿即用。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior prompt designer who turns a vague user wish into a "
    "copy-paste-ready AI prompt. A good prompt has five elements:\n"
    "1. Trigger scenario & role: when to use it, who the AI should act as;\n"
    "2. Input materials: what the user must paste in, required vs optional, format;\n"
    "3. Clear task instructions: step-by-step what to do, plus explicit prohibitions;\n"
    "4. Output format: shape of the final deliverable, sections, tables, length;\n"
    "5. Quality rules & self-check: what the AI should verify before finishing.\n"
    "Also give iteration advice for the \"draft → trial run → refine\" loop.\n"
    "Rules: stay concrete to the user's scenario; prohibitions must be actionable; "
    "mark uncertain items as (TBC); the output must itself be a ready-to-use prompt.\n"
    "Output the Markdown body only, with no extra explanation."
)

MODE_HINT = {
    "design": (
        "以下是用户的需求描述（想让 AI 做什么、目标场景、手头已有什么材料）。"
        "请按系统提示词从零设计一份完整、可直接复制粘贴使用的提示词：\n\n"
    ),
    "optimize": (
        "以下是用户已有的提示词，以及它在试运行中效果不佳的地方。"
        "请按系统提示词诊断问题（五要素缺了哪一环、指令是否含糊、禁止事项是否缺失），"
        "并输出优化后的完整提示词：\n\n"
    ),
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_prompt_designer",
        description="把模糊的愿望变成可直接使用的结构化提示词（中文技能库 · prompt-designer）",
    )
    parser.add_argument("input", help="需求描述或已有提示词的文件路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.prompt-designer.md）")
    parser.add_argument("--mode", choices=["design", "optimize"], default="design",
                        help="design=从零设计提示词；optimize=优化用户已有提示词（默认 design）")
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
        raise SystemExit("错误：输入内容为空，请提供需求描述或已有提示词文本。")
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
    mode_hint = MODE_HINT[args.mode]

    text = read_input(args.input)
    chunks = chunk_text(text)
    print("输入文本：%d 字，切分为 %d 段，模式=%s，开始生成提示词草稿……"
          % (len(text), len(chunks), args.mode), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": mode_hint + "（第 %d/%d 段）\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".prompt-designer.md"
        else:
            out_path = base + ".prompt-designer.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：草稿请对照需求复核，试运行后按「迭代建议」再修一轮。")


if __name__ == "__main__":
    main()
