#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_code_review.py — 代码审查草稿生成器（中文技能库 · code-review）

对一段代码改动（diff 文本或新旧代码对照）做双轴审查：
  - Standards 轴：是否符合项目成文规范，并叠加 Fowler《重构》第 3 章
    12 条坏味道基线（只作判断项，不作硬违规）；
  - Spec 轴：是否忠实实现需求文档（--spec 传入），只报三类问题——
    需求缺失/半成品、范围蔓延、看似实现实则错误，每条引需求原文。

两轴按顺序执行（先 Standards 后 Spec），互不串用上下文；结果按
`## Standards` / `## Spec` 两节并列输出，末尾各给本轴总数与最严重问题，
不跨轴排序。不带 --spec 时只跑 Standards 轴。

用法示例：
    python draft_code_review.py change.diff --spec requirement.md -o review.md
    cat change.diff | python draft_code_review.py - --spec requirement.md
    python draft_code_review.py change.diff        # 不带 --spec，只跑 Standards 轴

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

SMELL_BASELINE_ZH = (
    "Fowler《重构》第 3 章 12 条坏味道基线（每条只作判断项，措辞用「可能的……」，"
    "永远不作硬违规；成文规范认可的写法要压制不报；linter/格式化器已强制的事项跳过）：\n"
    "1. 神秘命名（Mysterious Name）：函数/变量/类型名看不出它做什么、存什么 → 改名；"
    "起不出诚实的名字说明设计本身含糊。\n"
    "2. 重复代码（Duplicated Code）：相同的逻辑形状出现在多个 hunk/文件 → 提取共用形状，两处调用。\n"
    "3. 依恋情结（Feature Envy）：一个方法过多地操作别的对象的数据而非自己的数据 → 把方法挪到它依恋的数据那边。\n"
    "4. 数据泥团（Data Clumps）：同样几个字段/参数总是一起出现 → 捆成一个类型传递。\n"
    "5. 基本类型偏执（Primitive Obsession）：用基本类型/字符串顶替本该有自己类型的领域概念 → 给概念一个小类型。\n"
    "6. 重复 switch（Repeated Switches）：同一个类型上的 switch/if 级联在多处重复 → 用多态或一处共享 map 替换。\n"
    "7. 散弹式修改（Shotgun Surgery）：一个逻辑改动逼得在 diff 里散改很多文件 → 把总是一起变的东西收拢到一个模块。\n"
    "8. 发散式变化（Divergent Change）：同一个文件/模块因好几桩不相干的原因被改 → 拆分，让每个模块只为一个原因变。\n"
    "9. 推测性泛化（Speculative Generality）：为需求里不存在的需要提前做的抽象/参数/钩子 → 删掉，内联回去直到有真实需要。\n"
    "10. 过长消息链（Message Chains）：调用方不该依赖的 a.b().c().d() 长导航 → 在第一个对象上用一个方法藏住这段走法。\n"
    "11. 中间人（Middle Man）：一个类/函数基本只在转手上一层 → 删掉，直接调真正目标。\n"
    "12. 拒绝继承（Refused Bequest）：子类/实现者忽略或覆写了大半继承来的东西 → 丢掉继承，改用组合。"
)

SYSTEM_PROMPT_STANDARDS_ZH = (
    "你是资深代码审查人，负责「Standards 轴」：只审查代码改动是否符合规范，"
    "不评估它是否实现了需求（那是另一轴的事）。\n"
    "审查要点：\n"
    "1. 成文规范优先：若材料中可见项目成文规范（CODING_STANDARDS / CONTRIBUTING / 文件头注释中的约定等），"
    "逐条对照 diff；每处违反都引用规范出处（文件 + 条款），记为「硬违规」。材料里看不到成文规范时，"
    "明确注明「未见项目成文规范，仅按 Fowler 基线审查」。\n"
    "2. 无论有没有成文规范，都用下面的坏味道基线过一遍 diff：\n" + SMELL_BASELINE_ZH + "\n"
    "3. 硬违规与判断项分开列；坏味道永远是判断项（「可能的 XX」），并引用对应代码片段；"
    "成文规范认可的写法即使撞基线也要压制不报。\n"
    "4. 按文件/代码块分组，每条发现一句话说清问题 + 位置/出处 + 怎么改。\n"
    "5. 忠于材料：材料里没有的规范条款不编造；存疑处标「（待确认）」。\n"
    "直接输出本轴的 Markdown 正文（不要写 `## Standards` 标题，不要任何额外解释）；"
    "末尾另起一行写：本轴小结：共 N 项发现（硬违规 a 项 / 判断项 b 项）；最严重问题：……"
)

SYSTEM_PROMPT_SPEC_ZH = (
    "你是资深需求符合性审查人，负责「Spec 轴」：只对照需求文档审查代码改动是否忠实实现了需求，"
    "不评代码风格与规范（那是另一轴的事）。\n"
    "只报告三类问题，每条都必须引用需求原文：\n"
    "1. 需求缺失或只做了一半：需求要求了，但 diff 里没有或只实现一部分；\n"
    "2. 范围蔓延：diff 里做了需求没要求的行为；\n"
    "3. 看似实现、实则错误：代码看起来实现了该需求，但实现方式与需求原文不符或行为错误。\n"
    "要求：\n"
    "- 按上述三类分组列出；每条先引需求原文（加引号），再说 diff 里的对应情况；\n"
    "- 忠于材料：不编造需求条款，存疑处标「（待确认）」；\n"
    "直接输出本轴的 Markdown 正文（不要写 `## Spec` 标题，不要任何额外解释）；"
    "末尾另起一行写：本轴小结：共 N 项发现；最严重问题：……"
)

SYSTEM_PROMPT_STANDARDS_EN = (
    "You are a senior code reviewer running the STANDARDS axis only: judge whether the diff "
    "follows documented conventions; do NOT judge whether it meets requirements (that is the other axis).\n"
    "1. Documented repo standards override everything: if conventions are visible in the material "
    "(CODING_STANDARDS / CONTRIBUTING / header comments), cite file + rule for every breach (hard violation); "
    "if none is visible, say so and rely on the baseline only.\n"
    "2. Always apply the Fowler smell baseline as labelled heuristics only (never hard violations): "
    "Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, "
    "Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, Refused Bequest. "
    "Name each as \"possible X\" and quote the hunk; suppress anything a documented standard endorses; "
    "skip what linters/formatters already enforce.\n"
    "3. Group by file/hunk; one line per finding: problem + location + fix. Stay faithful; mark doubts as (TBC).\n"
    "Output this axis's Markdown body only (no `## Standards` heading, no extra explanation); "
    "end with: Axis summary: N findings (a hard violations / b judgement calls); worst issue: ..."
)

SYSTEM_PROMPT_SPEC_EN = (
    "You are a senior spec-conformance reviewer running the SPEC axis only: compare the diff against the "
    "requirements document; do NOT review code style (other axis).\n"
    "Report only three classes, each quoting the requirement verbatim: "
    "(a) required but missing or partial; (b) scope creep the spec never asked for; "
    "(c) looks implemented but is actually wrong. Group by the three classes; quote the spec line first.\n"
    "Stay faithful; mark doubts as (TBC).\n"
    "Output this axis's Markdown body only (no `## Spec` heading, no extra explanation); "
    "end with: Axis summary: N findings; worst issue: ..."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_code_review",
        description="对代码改动做双轴审查（Standards 规范 + Fowler 坏味道基线 / Spec 需求符合性），中文技能库 · code-review",
    )
    parser.add_argument("input", help="代码改动路径（diff 文本或新旧代码对照），或用 - 从标准输入读取")
    parser.add_argument("--spec", default=None, help="需求文档路径（可选；不提供则只跑 Standards 轴）")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.code-review.md）")
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
        raise SystemExit("错误：输入内容为空，请提供代码改动（diff 文本或新旧对照）。")
    return text


def read_spec(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        raise SystemExit("错误：无法读取需求文档 %s（%s）" % (path, exc))
    if not text.strip():
        raise SystemExit("错误：需求文档 %s 内容为空。" % path)
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


def run_axis(axis_label, system_prompt, chunks, api_key, base_url, model, spec_text=None):
    """跑一个轴：逐块调用 chat；Spec 轴把需求文档放在每段 user 消息开头。"""
    outputs = []
    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        if spec_text:
            user_content = (
                "【需求文档全文】\n\n%s\n\n"
                "【待审查代码改动（第 %d/%d 段）】\n\n%s" % (spec_text, i, total, chunk)
            )
        else:
            user_content = "【待审查代码改动（第 %d/%d 段）】\n\n%s" % (i, total, chunk)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        outputs.append(chat(messages, api_key, base_url, model))
        print("%s：第 %d/%d 段完成。" % (axis_label, i, total), file=sys.stderr)
    return outputs


def merge_chunks(outputs):
    """多段结果合并，后续段以补充小节衔接。"""
    if len(outputs) == 1:
        return outputs[0]
    return "\n\n".join(
        seg if idx == 0 else "## 补充内容（第 %d 段）\n\n%s" % (idx + 1, seg)
        for idx, seg in enumerate(outputs)
    )


def main():
    args = build_parser().parse_args()
    api_key = resolve_api_key(args)

    if args.lang == "zh":
        standards_prompt = SYSTEM_PROMPT_STANDARDS_ZH
        spec_prompt = SYSTEM_PROMPT_SPEC_ZH
    else:
        standards_prompt = SYSTEM_PROMPT_STANDARDS_EN
        spec_prompt = SYSTEM_PROMPT_SPEC_EN

    code_text = read_input(args.input)
    chunks = chunk_text(code_text)
    spec_text = read_spec(args.spec) if args.spec else None

    base = args.input if args.input != "-" else "stdin"
    title = os.path.splitext(os.path.basename(base))[0] if base != "stdin" else "未命名改动"
    spec_desc = args.spec if args.spec else "未提供（仅 Standards 轴）"

    print("输入代码：%d 字，切分为 %d 段。" % (len(code_text), len(chunks)), file=sys.stderr)

    # Standards 轴：先跑，独立上下文
    print("开始 Standards 轴（成文规范 + Fowler 12 条坏味道基线）……", file=sys.stderr)
    standards_outputs = run_axis(
        "Standards 轴", standards_prompt, chunks, api_key, args.base_url, args.model
    )
    standards_body = merge_chunks(standards_outputs)

    # Spec 轴：后跑，独立上下文；不带 --spec 时跳过
    if spec_text:
        print("开始 Spec 轴（需求符合性）……", file=sys.stderr)
        spec_outputs = run_axis(
            "Spec 轴", spec_prompt, chunks, api_key, args.base_url, args.model, spec_text=spec_text
        )
        spec_body = merge_chunks(spec_outputs)
    else:
        print("未提供 --spec：跳过 Spec 轴，仅执行 Standards 轴。", file=sys.stderr)
        spec_body = None

    lines = [
        "# 代码审查 · %s" % title,
        "",
        "> 输入：%s ｜ 需求文档：%s" % (base, spec_desc),
        "",
        "## Standards",
        "",
        standards_body.strip(),
        "",
        "## Spec",
        "",
    ]
    if spec_body:
        lines.append(spec_body.strip())
    else:
        lines.append("未提供需求文档（--spec），本轴跳过；本次仅执行 Standards 轴审查。")
    lines += [
        "",
        "---",
        "",
        "两轴分头顺序执行、互不串用上下文；以上两节并列输出，未跨轴排序。",
    ]
    final = "\n".join(lines)

    if args.output:
        out_path = args.output
    else:
        if "." in base:
            out_path = base.rsplit(".", 1)[0] + ".code-review.md"
        else:
            out_path = base + ".code-review.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(final)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    review_lines = final.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, review_lines))
    print("提示：审查草稿请对照代码与需求原文复核后再交付。")


if __name__ == "__main__":
    main()