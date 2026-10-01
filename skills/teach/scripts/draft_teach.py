#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_teach.py — 培训教案草稿生成器（中文技能库 · teach）

把一个培训主题 + 学员背景，设计成一份可直接执行的单轮培训教案 Markdown：
教学目标（MISSION）/ 学员画像与前置评估 / 课程大纲 /
练习设计（提取练习 · 间隔重复 · 交错练习）/ 评估方式 / 课后巩固。

用法示例：
    python draft_teach.py brief.txt --output plan.md --duration 120
    cat brief.txt | python draft_teach.py - --duration 90

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
    "你是资深企业培训设计师。请根据用户提供的培训主题与学员背景，"
    "设计一份可直接执行的单轮培训教案大纲（Markdown）。\n"
    "必须遵守：\n"
    "1. MISSION 驱动：先写 2-4 条可检验的教学目标，每条用行为动词开头"
    "（说出/操作/判断/区分/独立完成……），禁止单独使用'了解''熟悉''掌握'；"
    "每条目标写完要能回答'学员课后具体会做什么'；\n"
    "2. 贴着学员最近发展区：依据学员背景判断现有水平与知识缺口，学员已经会的内容一笔带过，"
    "只教比现有水平略高一点点的部分；学员背景没说清楚的水平与缺口，一律标注'（待确认）'，绝不脑补；\n"
    "3. 课程大纲分模块，每个模块写明：内容要点 / 教学动作（讲授/演示/带练/讨论）/ 时长（分钟）；\n"
    "4. 练习设计必须显式落地三种学习科学方法，每种至少 1 个具体设计：\n"
    "   - 提取练习：写出至少 3 道具体回忆题（合上讲义凭记忆作答）；\n"
    "   - 间隔重复：给出一张跨天/跨周的复习安排表（第几天复习哪块内容、什么形式）；\n"
    "   - 交错练习：给出混合不同知识点/不同情境的混练示例；\n"
    "   禁止'加强练习''多做题''加深记忆'这类空话；\n"
    "5. 评估方式：给每条教学目标配一个可检验的课后检验方法（笔试/实操/情景模拟/作业 + 及格线）；\n"
    "6. 课后巩固：间隔复习计划 + 本主题学员最常犯的 3-5 个错误及纠正提示；\n"
    "7. 课程大纲各模块时长之和必须与总时长一致；每个练习写清怎么给学员反馈（对答案/讲师点评/巡场）。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior corporate training designer. Based on the training topic "
    "and learner background provided, design a directly executable single-round "
    "training lesson plan in Markdown.\n"
    "Rules:\n"
    "1. Mission-driven: write 2-4 testable objectives, each starting with a "
    "behavioral verb (name / perform / judge / distinguish / complete independently); "
    "never use vague words like 'understand / be familiar with / master' alone.\n"
    "2. Target the zone of proximal development: skip what learners already know, "
    "teach just slightly above their current level; mark unknown gaps as (TBC), never invent.\n"
    "3. Break the syllabus into modules, each with: key points / teaching action / duration (min).\n"
    "4. Exercise design must explicitly land three learning-science methods, each with >=1 concrete design: "
    "retrieval practice (>=3 concrete recall questions), spaced repetition (a day-by-day review schedule), "
    "interleaving (mixed-type practice examples); no empty phrases like 'practice more'.\n"
    "5. Assessment: pair each objective with a testable post-training check (test / hands-on / scenario / homework + pass line).\n"
    "6. Post-course consolidation: spaced review plan + the 3-5 most common mistakes and corrections.\n"
    "7. Module durations must sum to the total duration; state how feedback is given for each exercise.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_teach",
        description="把培训主题 + 学员背景设计成可执行的单轮培训教案（中文技能库 · teach）",
    )
    parser.add_argument("input", help="培训主题与学员背景文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.teach.md）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型名（默认 %(default)s）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI 兼容接口根地址（默认 %(default)s）")
    parser.add_argument("--api-key", default=None, help="API Key（优先于环境变量）")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言（默认 zh）")
    parser.add_argument(
        "--duration", type=int, default=None, metavar="分钟",
        help="培训总时长（分钟），注入系统提示词控制课程大纲的时长分配（可选）",
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
        raise SystemExit("错误：输入内容为空，请提供培训主题与学员背景文本。")
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
    if args.duration:
        system_prompt += (
            "\n本次培训总时长为 %d 分钟：课程大纲各模块时长（分钟）之和必须严格等于 %d 分钟。"
            % (args.duration, args.duration)
        )

    text = read_input(args.input)
    chunks = chunk_text(text)
    print("输入文本：%d 字，切分为 %d 段，开始生成培训教案……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是培训主题与学员背景（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".teach.md"
        else:
            out_path = base + ".teach.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：教案草稿请对照学员实际情况复核后再交付。")


if __name__ == "__main__":
    main()