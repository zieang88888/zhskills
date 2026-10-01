#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_systematic_debugging.py — 根因分析与故障复盘报告生成器（中文技能库 · systematic-debugging）

把一个问题/故障/客诉/异常的描述，通过四阶段强制串行的根因分析方法论，
整理成一份结构化的根因分析复盘报告草稿。

用法示例：
    python draft_systematic_debugging.py problem.txt --output report.md
    cat problem.txt | python draft_systematic_debugging.py -
    python draft_systematic_debugging.py problem.txt --attempts 3

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

SYSTEM_PROMPT_ZH_BASE = (
    "你是资深根因分析与故障复盘专家。请按照四阶段强制串行的根因分析方法论，"
    "把用户提供的问题描述整理成一份结构化的根因分析复盘报告。\n"
    "\n"
    "核心原则：未找到根因之前，绝不提修复方案。症状级修复等于失败。\n"
    "\n"
    "四阶段方法论（必须按顺序体现，前一阶段没做完不能跳到下一阶段）：\n"
    "1. 根因调查：仔细读错误信息 → 稳定复现问题 → 检查最近变更 → "
    "沿组件边界加观测定位断点 → 追溯数据流到源头。\n"
    "2. 模式对比：找正常工作的对照案例 → 完整对比每一个细节差异 → "
    "理解依赖与前提假设。\n"
    "3. 单假设最小验证：一次只验证一个假设 → 做最小实验 → "
    "验证失败就换假设，绝不在旧修复上叠加新修复。\n"
    "4. 单点修复：只改一处根因 → 修复后按验证标准确认有效 → "
    "如果已试 3 次修复仍失败，必须停下质疑架构和基本前提。\n"
    "\n"
    "必须遵守的质量规则：\n"
    "1. 忠于输入：只基于用户提供的信息分析，不编造环境细节；缺失信息标注（待确认）；\n"
    "2. 假设必须配验证方法：每个候选根因都要写清楚最小验证实验怎么做；\n"
    "3. 一次只验证一个假设：禁止同时改多个地方；\n"
    "4. 单点修复：修复方案只能改一处根因，禁止打包重构、顺手优化；\n"
    "5. 症状级修复必须指出：如果用户的修复只是掩盖症状而非修根因，明确指出；\n"
    "6. 复现不了就如实标注：不要硬编复现步骤。\n"
    "\n"
    "输出结构（严格按以下六节输出 Markdown）：\n"
    "## 问题现象与影响\n"
    "一句话描述问题 + 影响范围（谁受影响、严重度分级）。\n"
    "## 复现步骤\n"
    "可复现则给精确步骤；不可复现标注「暂不可稳定复现」并说明已收集的证据。\n"
    "## 假设列表\n"
    "3-5 个候选根因，每个格式为：假设 N：{内容}；验证方法：{最小实验设计}。\n"
    "## 模式对比\n"
    "与正常情况的差异清单，每条标注「可能相关/无关/待验证」。\n"
    "## 最可能根因与修复方案\n"
    "置信度（高/中/低）+ 判断依据；修复方案为单点修复，附验证标准。\n"
    "## 复盘教训\n"
    "流程改进建议——检查点加在哪一层、监控补什么、以后怎么早发现。\n"
    "\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_ZH_ATTEMPTS_WARNING = (
    "\n\n⚠️ 重要提示：用户已尝试修复 {n} 次仍未解决问题。"
    "按照方法论，3 次失败意味着基本假设可能有问题——"
    "你必须在报告的「最可能根因与修复方案」一节末尾，"
    "明确加入一段「⚠️ 基本假设质疑」："
    "指出当前排查方向可能存在架构性偏差，"
    "建议停下来重新审视前提假设，而不是继续在同一方向上硬修。"
    "这段提示是强制要求，不得省略。"
)

SYSTEM_PROMPT_EN_BASE = (
    "You are a senior root cause analysis and incident review expert. "
    "Using the four-phase systematic debugging methodology, produce a structured "
    "root cause analysis report from the user's problem description.\n"
    "\n"
    "Core principle: never propose fixes before finding the root cause. "
    "Symptom-level fixes are failures.\n"
    "\n"
    "Four phases (must be completed in order):\n"
    "1. Root cause investigation: read errors, reproduce, check changes, "
    "add instrumentation at component boundaries, trace data flow.\n"
    "2. Pattern analysis: find working examples, compare every difference, "
    "understand dependencies and assumptions.\n"
    "3. Single hypothesis testing: one hypothesis at a time, minimal experiment, "
    "never stack fixes on top of failed fixes.\n"
    "4. Single point fix: fix only the root cause, verify, "
    "and if 3+ fixes failed, question the architecture.\n"
    "\n"
    "Rules: stay faithful to input, mark missing info as (TBC), "
    "every hypothesis must include a minimal verification experiment, "
    "one variable at a time, single-point fix only, "
    "point out symptom-level fixes, mark unreproducible issues honestly.\n"
    "\n"
    "Output six sections: Problem & Impact, Reproduction Steps, "
    "Hypotheses (3-5 with verification methods), Pattern Comparison, "
    "Most Likely Root Cause & Fix (with confidence and verification criteria), "
    "Lessons Learned.\n"
    "Output Markdown body only, no extra explanation."
)

SYSTEM_PROMPT_EN_ATTEMPTS_WARNING = (
    "\n\nWARNING: The user has already tried {n} fix attempts without success. "
    "Per the methodology, 3+ failed attempts means the fundamental assumptions "
    "may be wrong. You MUST add a 'Fundamental Assumption Challenge' paragraph "
    "at the end of the root cause section, explicitly recommending that the user "
    "stop and question the architecture/assumptions rather than continuing to "
    "fix in the same direction."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_systematic_debugging",
        description="把问题描述整理成结构化根因分析复盘报告（中文技能库 · systematic-debugging）",
    )
    parser.add_argument("input", help="问题描述文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.systematic-debugging.md）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型名（默认 %(default)s）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI 兼容接口根地址（默认 %(default)s）")
    parser.add_argument("--api-key", default=None, help="API Key（优先于环境变量）")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言（默认 zh）")
    parser.add_argument(
        "--attempts", type=int, default=0,
        help="用户已尝试修复的次数（默认 0）；当 >=3 时，系统提示词自动加入「质疑基本假设」的强制提示",
    )
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
        raise SystemExit("错误：输入内容为空，请提供问题描述文本。")
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


def build_system_prompt(lang, attempts):
    """根据语言和已尝试次数组装系统提示词。"""
    if lang == "zh":
        prompt = SYSTEM_PROMPT_ZH_BASE
        if attempts >= 3:
            prompt += SYSTEM_PROMPT_ZH_ATTEMPTS_WARNING.format(n=attempts)
    else:
        prompt = SYSTEM_PROMPT_EN_BASE
        if attempts >= 3:
            prompt += SYSTEM_PROMPT_EN_ATTEMPTS_WARNING.format(n=attempts)
    return prompt


def main():
    args = build_parser().parse_args()
    api_key = resolve_api_key(args)
    system_prompt = build_system_prompt(args.lang, args.attempts)

    text = read_input(args.input)
    chunks = chunk_text(text)
    print("输入文本：%d 字，切分为 %d 段，开始生成根因分析报告……" % (len(text), len(chunks)), file=sys.stderr)
    if args.attempts >= 3:
        print("⚠️ 检测到已尝试 %d 次修复，已启用「质疑基本假设」强制提示。" % args.attempts, file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是问题描述（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".systematic-debugging.md"
        else:
            out_path = base + ".systematic-debugging.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：报告草稿请对照实际情况复核后再交付。")


if __name__ == "__main__":
    main()