#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_execution_plan.py — 执行计划书草稿生成器（中文技能库 · execution-plan）

把一份需求 / 规格 / 任务说明，拆解成一份对零上下文执行者也友好的分步执行计划书 Markdown。
输出包含：目标、范围、全局约束、关键检查点、交付物责任结构图、逐任务分步动作与验收标准。

用法示例：
    python draft_execution_plan.py requirements.md --output plan.md
    cat requirements.md | python draft_execution_plan.py -

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
    "你是资深项目计划撰写人。请把用户提供的需求/规格/任务说明，"
    "拆解成一份对零上下文执行者也友好的分步执行计划书 Markdown。\n"
    "必须遵守：\n"
    "1. 先做范围检查：如果需求覆盖多个独立子系统，建议拆成多份计划，每份单独可交付；\n"
    "2. 先画交付物责任结构图：列出所有交付物、责任方、依赖关系，锁定边界；\n"
    "3. 任务切分：每个任务自带可独立验收的交付物，粒度小到每步可独立验收；\n"
    "4. 文档头必须包含：目标（一句话）、范围（覆盖什么/不覆盖什么）、"
    "全局约束（逐条照抄需求中的硬性数值）、关键检查点（需求没明说但最易踩的坑，"
    "如预算超支、审批遗漏、对外沟通口径、数据格式、权限不足等，逐条写明情况+期望行为）；\n"
    "5. 每个任务结构：交付物、接口（输入/输出）、分步动作用 - [ ] 勾选框、"
    "收尾写里程碑交付（验收标准）；\n"
    "6. 无占位符铁律：禁止 TBD、TODO、适当处理边界情况、同任务 N 等偷懒写法，"
    "每步必须写清具体做什么、产出什么、怎么验收；\n"
    "7. 不确定处标注（待确认）并说明需要谁确认；\n"
    "8. 写完做四项自检：需求覆盖、占位符扫描、跨任务一致性、检查点是否落验，"
    "在文末简要列出修正了什么。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior implementation-plans writer. Convert the provided "
    "requirements/spec into a step-by-step execution plan Markdown that a "
    "zero-context executor can follow.\n"
    "Rules:\n"
    "1. Scope check: if the spec covers multiple independent subsystems, "
    "recommend splitting into separate plans, each independently deliverable.\n"
    "2. Draw a deliverable-responsibility map first: list deliverables, owners, "
    "and dependencies to lock boundaries.\n"
    "3. Task right-sizing: each task carries its own independently verifiable "
    "deliverable; steps are granular enough to verify each one alone.\n"
    "4. Header must include: Goal (one sentence), Scope (in/out), Global "
    "Constraints (verbatim hard values from spec), Review Focus (input classes "
    "or failure modes the spec implies but does not test, e.g. budget overflow, "
    "missing approvals, inconsistent external messaging, data format, "
    "insufficient permissions; each line names the condition and expected behavior).\n"
    "5. Each task: Deliverables, Interfaces (consumes/produces), checkbox steps "
    "(- [ ]), and a milestone delivery (acceptance criteria) at the end.\n"
    "6. No placeholders: no TBD, TODO, handle edge cases appropriately, same as "
    "task N; every step must say exactly what to do, what to produce, how to verify.\n"
    "7. Mark uncertain items as (TBC) and state who needs to confirm.\n"
    "8. Self-review after writing: spec coverage, placeholder scan, cross-task "
    "consistency, checkpoints pinned to tasks; list fixes at the end.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_execution_plan",
        description="把需求/规格拆解成分步执行计划书草稿（中文技能库 · execution-plan）",
    )
    parser.add_argument("input", help="需求/规格文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.execution-plan.md）")
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
        raise SystemExit("错误：输入内容为空，请提供需求/规格文本。")
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
    print("输入文本：%d 字，切分为 %d 段，开始生成执行计划书草稿……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是需求/规格（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".execution-plan.md"
        else:
            out_path = base + ".execution-plan.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：草稿请对照需求原文复核后再交付。")


if __name__ == "__main__":
    main()