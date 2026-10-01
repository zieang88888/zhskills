#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_idea_refine.py — 想法打磨草稿生成器（中文技能库 · idea-refine）

把一个粗糙、未经推敲的想法（选题 / 点子 / 活动创意 / 立项想法），
通过「发散—收敛—交付」三阶段方法论，打磨成一份可执行的一页纸 Markdown 方案：
原始想法与 HMW 重述、锐化问题、方向四维对比、推荐方向与隐藏假设、
Not Doing 清单、下一步行动。

用法示例：
    python draft_idea_refine.py idea.txt --output refine.md
    cat idea.txt | python draft_idea_refine.py -
    python draft_idea_refine.py idea.txt --lenses "付费意愿、渠道能力、政策合规"

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
DEFAULT_LENSES = "用户价值、商业回报、技术实现、时间窗口、成本投入、风险代价、差异化"

SYSTEM_PROMPT_ZH = (
    "你是一位资深的想法打磨伙伴（ideation partner），擅长把粗糙、未经推敲的想法"
    "打磨成可执行的一页纸方案。\n"
    "请对用户给出的想法（选题 / 点子 / 活动创意 / 立项想法），按「发散—收敛—交付」"
    "三阶段方法论完成打磨，并直接输出 Markdown 一页纸方案。\n"
    "必须遵守：\n"
    "1. 忠于想法、不脑补：只基于用户给出的想法与背景展开；用户没说的事实不编造；"
    "信息不足处一律标注「（待确认）」。\n"
    "2. 三阶段——\n"
    "   发散：先把原想法重述成一句 How Might We（HMW）问题；再提 3-5 个锐化问题"
    "（面向谁 / 成功长什么样 / 真实约束 / 之前试过什么 / 为什么是现在）；"
    "然后用给定透镜各生成若干变体（5-8 个想透的，不要 20 个肤浅的）。\n"
    "   收敛：把变体聚成 2-3 个彼此有实质差异的方向；逐方向做四维压力测试——"
    "用户价值、可行性、差异化、风险；并显式说出每个方向在赌什么、什么会杀死它。\n"
    "   交付：按下方结构输出一页纸方案。\n"
    "3. 输出结构必须严格包含以下六节，逐节齐全：\n"
    "   一、原始想法与重述（HMW）：先原样复述粗糙想法，再改写为一句 How Might We 问题。\n"
    "   二、锐化问题：3-5 个，用户没答到的标「（待确认）」。\n"
    "   三、方向对比：2-3 个方向，用表格逐方向评估【用户价值 / 可行性 / 差异化 / 风险】"
    "四维，四格都必须填写，不许留空或写「待定」了事。\n"
    "   四、推荐方向与理由 + 隐藏假设清单：选一个方向说清理由；紧接着逐条列出隐藏假设，"
    "每条标「（待确认）」并附一句如何验证。\n"
    "   五、Not Doing 清单：明确这次不做什么，每条都必须带理由。\n"
    "   六、下一步行动：三选一——进入设计 / 进入立项 / 放弃（放弃需说明理由）。\n"
    "4. 做诚实的思考伙伴，不做捧场机器：想法弱要敢于具体指出；但语气直接、带善意，不刻薄。\n"
    "5. 一页纸为度，每节点到即止，不堆废话。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a sharp ideation partner. Refine the user's raw idea into a concrete, "
    "actionable Markdown one-pager through structured divergent and convergent thinking.\n"
    "Rules:\n"
    "1. Stay grounded: only use the idea and background the user gave; never invent facts; "
    "mark gaps as (TBC).\n"
    "2. Three phases: Divergent — restate as a How-Might-We problem, ask 3-5 sharpening "
    "questions, generate 5-8 considered variations with the given lenses; "
    "Convergent — cluster into 2-3 meaningfully different directions, stress-test each on "
    "user value / feasibility / differentiation / risk, surface hidden assumptions; "
    "Deliver — output a one-pager.\n"
    "3. Output must contain exactly six sections: (1) Raw idea & HMW restatement; "
    "(2) 3-5 sharpening questions; (3) direction comparison table with all four cells "
    "filled (user value / feasibility / differentiation / risk), never left blank; "
    "(4) recommended direction + reasons + explicit hidden assumptions, each marked "
    "(TBC) with how to validate; (5) a Not Doing list, each item with a reason; "
    "(6) next step: go to design / go to kickoff / abandon (with reason).\n"
    "4. Be an honest thinking partner, not a yes-machine; push back specifically and kindly.\n"
    "5. Keep it to one page; no filler.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_idea_refine",
        description="把粗糙想法打磨成可执行的一页纸方案（中文技能库 · idea-refine）",
    )
    parser.add_argument("input", help="想法描述文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.idea-refine.md）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型名（默认 %(default)s）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI 兼容接口根地址（默认 %(default)s）")
    parser.add_argument("--api-key", default=None, help="API Key（优先于环境变量）")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言（默认 zh）")
    parser.add_argument("--lenses", default=None,
                        help="自定义发散透镜，用顿号分隔（默认：%s）" % DEFAULT_LENSES)
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
        raise SystemExit("错误：输入内容为空，请提供一段想法描述。")
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
    system_prompt = SYSTEM_PROMPT_ZH if args.lang == "zh" else SYSTEM_PROMPT_EN

    text = read_input(args.input)
    lenses = args.lenses or DEFAULT_LENSES
    chunks = chunk_text(text)
    print("输入想法：%d 字，切分为 %d 段，使用透镜：%s，开始打磨……"
          % (len(text), len(chunks), lenses), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        user_content = (
            "以下是需要打磨的原始想法（可能含背景与约束），第 %d/%d 段：\n\n%s\n\n"
            "【发散透镜】本次用以下透镜生成变体：%s"
            % (i, len(chunks), chunk, lenses)
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
            out_path = base.rsplit(".", 1)[0] + ".idea-refine.md"
        else:
            out_path = base + ".idea-refine.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：方案草稿请对照原始想法与约束复核后再交付。")


if __name__ == "__main__":
    main()