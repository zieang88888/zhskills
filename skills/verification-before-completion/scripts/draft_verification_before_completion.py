#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_verification_before_completion.py — 交付前核验报告生成器（中文技能库 · verification-before-completion）

把交付物（报告/周报/公文/代码/文案）中的声明逐条核验，输出一份自查门禁报告：
哪些声明有新鲜验证证据撑腰（可声称），哪些没有（待验证），每条待验证项给具体补救动作。

铁律：没有新鲜的验证证据，不得声称完成。

用法示例：
    python draft_verification_before_completion.py deliverable.txt --output report.md
    cat deliverable.txt | python draft_verification_before_completion.py -

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
    "你是交付前核验专家。你的铁律是：没有新鲜的验证证据，不得声称完成。\n"
    "请把用户提供的交付物内容（或声明清单）整理成一份结构化的 Markdown 核验报告。\n"
    "必须遵守：\n"
    "1. 忠实提取声明：从交付物中摘出所有断言性语句（凡是声称某个事实、状态、结果的句子），"
    "绝不遗漏，也不编造交付物里没有的声明；\n"
    "2. 判定证据类型：每条声明需要什么类型的证据（数据报表 / 测试输出 / 原文核对 / 构建退出码 / 需求清单逐条对照）；\n"
    "3. 检查证据新鲜度：用户提供的验证情况里，明确区分'本次验证过'和'以前验证过'——"
    "以前验证过 ≠ 本次有效；用户没说验过的，一律按'未验证'处理；\n"
    "4. 五步门控逐条过：识别→执行→读取→对照→才声称；缺任何一步，该条不能标'可声称'；\n"
    "5. 红旗词敏感：交付物中出现'应该''大概''好像''差不多''之前跑过''应该没问题'这类措辞时，"
    "必须重点标注为待验证；\n"
    "6. 未验证项必须给可执行动作：不能只写'待验证'，必须给一条具体的、用户照着就能做的验证动作；\n"
    "7. 绝不允许把'未验证'写成'已验证'，绝不把'待验证'包装成'基本没问题'；\n"
    "8. 结构化输出，严格包含以下四节：\n"
    "   - 一、声明核验清单（表格：序号/声明内容/证据类型/证据是否新鲜/验证结果/结论：可声称 or 待验证）\n"
    "   - 二、未通过项与补救行动（表格：序号/待验证声明/具体验证动作建议）\n"
    "   - 三、借口对照（把交付物中出现的借口措辞映射到应做的动作）\n"
    "   - 四、最终结论（是否可交付 / 交付前必做 checklist）\n"
    "9. 不确定处标注（待确认），信息不足时如实说明；\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a verification-before-completion auditor. Your iron rule: "
    "NO completion claims without fresh verification evidence.\n"
    "Convert the provided deliverable (or claim list) into a structured Markdown verification report.\n"
    "Rules:\n"
    "1. Extract all claims: every assertive sentence in the deliverable; never miss one, never invent one.\n"
    "2. Classify evidence type per claim (data report / test output / original-document cross-check / "
    "build exit code / requirements checklist).\n"
    "3. Check freshness: distinguish 'verified this time' from 'verified before' — old results do not count; "
    "if the user did not say it was verified, treat as unverified.\n"
    "4. Five-step gate per claim: identify -> run -> read -> verify -> only then claim. "
    "Skip any step = cannot mark as claimable.\n"
    "5. Flag red-flag words ('should', 'probably', 'seems', 'looks good', 'ran before', 'should be fine') "
    "and mark those claims as pending.\n"
    "6. Every pending item must get a concrete, executable remediation action — not 'double check it'.\n"
    "7. Never write 'verified' for something unverified; never dress up 'pending' as 'mostly fine'.\n"
    "8. Structure strictly: (1) claim verification table, (2) failed items + remediation actions, "
    "(3) excuse-to-reality mapping, (4) final conclusion (deliverable? must-do checklist).\n"
    "9. Mark uncertain items as (TBC); say so when information is insufficient.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_verification_before_completion",
        description="把交付物中的声明逐条核验，输出交付前自查门禁报告（中文技能库 · verification-before-completion）",
    )
    parser.add_argument("input", help="交付物内容路径（或声明清单），或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.verification-before-completion.md）")
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
        raise SystemExit("错误：输入内容为空，请提供交付物内容或声明清单。")
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
    print("输入文本：%d 字，切分为 %d 段，开始生成核验报告……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是交付物内容 / 声明清单（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".verification-before-completion.md"
        else:
            out_path = base + ".verification-before-completion.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：核验报告请对照交付物逐项复核，未通过项全部闭环后再交付。")


if __name__ == "__main__":
    main()