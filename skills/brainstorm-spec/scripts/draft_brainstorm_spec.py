#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_brainstorm_spec.py — 方案头脑风暴 · 设计规格书草稿生成器（中文技能库 · brainstorm-spec）

把一段模糊的业务想法（新产品 / 活动立项 / 方案选型 / 需求梳理 / 会议对齐方向），
一次性收敛成可审批的 Markdown 设计规格书草稿：
路径分级判断（Spike / Bounded / Architectural）、2-3 个候选方案对比（各带权衡与推荐）、
推荐方案实施要点、风险与待确认问题清单、四项自检结果、审批门提示。

用法示例：
    python draft_brainstorm_spec.py idea.txt --output 2026-09-30-周年庆-design.md
    cat idea.txt | python draft_brainstorm_spec.py -

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
    "你是资深业务方案架构师。请把用户提供的一段模糊想法，"
    "收敛成一份可直接提交审批的中文 Markdown 设计规格书草稿。\n"
    "必须遵守：\n"
    "1. 先复述理解：写清要解决什么问题、为谁、成功标准，并区分“用户已明确的”与“你的假设”；\n"
    "2. 路径分级：先判断属于 Spike（可行性试探，产出是结论）/ "
    "Bounded（已有体系内范围清晰的小改）/ Architectural（新项目或大改，走完整流程），"
    "给出结论与理由，并说明用户可否决；拿不准时走更重的路径；\n"
    "3. 候选方案：提出 2-3 个不同做法，用表格列出做法、优点、代价/风险，"
    "明确首推一个并给一句话理由；用 YAGNI 砍掉不必要的部分；\n"
    "4. 推荐方案实施要点：分节写清各环节做什么、谁来做、怎么衔接、异常与兜底；\n"
    "5. 风险与待确认：列出预算/时间/依赖风险；信息缺口一律列入待确认清单，"
    "并在正文相应位置标注（待确认），绝不编造数据、预算、人手；\n"
    "6. 四项自检：逐项给出占位符扫描、内部一致性、范围是否过大、歧义检查的结论；\n"
    "7. 保留审批门（HARD-GATE）：明示“未经用户明确批准不得进入任何交付动作”，"
    "批准意见留空待用户填写；\n"
    "8. 不要写文件路径、不要写 git 提交；这是业务方案文档，不是技术实现文档。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior business solution architect. Turn the user's rough idea "
    "into an approvable Markdown design spec draft.\n"
    "Rules:\n"
    "1. Restate understanding: the problem, the audience, the success criteria; "
    "separate what the user stated from your assumptions.\n"
    "2. Classify the path: Spike (feasibility probe) / Bounded (small well-scoped change "
    "inside an existing system) / Architectural (new project or major change); give the "
    "conclusion, the reasoning, and note the user may override; when in doubt, take the heavier path.\n"
    "3. Propose 2-3 approaches in a table (approach / pros / trade-offs), clearly recommend "
    "one with a one-line reason; ruthlessly cut unnecessary features (YAGNI).\n"
    "4. Recommended solution: sectioned implementation points — what each part does, "
    "who does it, how they connect, error handling and fallbacks.\n"
    "5. Risks and open questions: list budget/time/dependency risks; mark every information "
    "gap as (TBC), in both the checklist and inline; never invent numbers.\n"
    "6. Four-point self review: placeholder scan, internal consistency, scope check, ambiguity check.\n"
    "7. Keep the HARD-GATE: state explicitly that no delivery action may begin until the user "
    "approves; leave the approval line blank.\n"
    "8. This is a business solution document — no file paths, no git commits.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_brainstorm_spec",
        description="把模糊想法收敛成可审批的设计规格书草稿（中文技能库 · brainstorm-spec）",
    )
    parser.add_argument("input", help="想法描述文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.brainstorm-spec.md）")
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
        raise SystemExit("错误：输入内容为空，请提供想法描述文本。")
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
    print("输入文本：%d 字，切分为 %d 段，开始生成设计规格书草稿……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是用户的想法描述（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".brainstorm-spec.md"
        else:
            out_path = base + ".brainstorm-spec.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：草稿请对照原始想法复核、并经用户审批后方可进入交付动作。")


if __name__ == "__main__":
    main()