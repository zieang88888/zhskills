#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_proposal_writer.py — 立项报告草稿生成器（中文技能库 · proposal-writer）

把用户提供的"立项主题 + 关键事实/数据/需求清单"，按
「证据表 → 论证图 → 章节契约 → 四层QA」的写作状态机，
生成一份结构完整的中文立项报告 Markdown 草稿。

适用场景：项目立项申请、课题开题报告、活动方案申报、预算申请材料、内部创新提案。

用法示例：
    python draft_proposal_writer.py facts.txt --output proposal.md
    cat facts.txt | python draft_proposal_writer.py -

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
    "你是资深项目立项报告撰写人。请把用户提供的「立项主题 + 关键事实/数据/需求清单」，"
    "按「证据表 → 论证图 → 章节契约 → 四层QA」的写作状态机，"
    "整理成一份可直接提交评审的结构化中文立项报告 Markdown 草稿。\n"
    "必须遵守：\n"
    "1. 忠于事实：只使用用户提供的或清单中真实存在的信息，绝不编造数据、引用、人名、金额、日期；"
    "凡缺失的信息一律标注「（待确认）」，不要替用户脑补；\n"
    "2. 证据表先行：动笔前先把支撑立项的事实/数据/需求逐条登记成证据表（带来源、可靠度高/中/低），"
    "正文里的每条主张都必须能在证据表中找到依据；\n"
    "3. 论证链清晰：按「背景 → 问题 → 目标 → 方案 → 预期价值」串成一条因果论证链，每节只论证一个主张；\n"
    "4. 问题与目标一一对应：每条问题必须映射到至少一条可检验的目标（有量化指标或验收标准）；\n"
    "5. 章节契约式写作：每一节都有明确的说服目的，超纲或证据不足的句子直接删除，不找补；\n"
    "6. 结构化输出：严格包含以下七节——\n"
    "   一、立项基本信息（名称/类别/申请方/周期/预算，缺失标（待确认））；\n"
    "   二、背景与意义（引用证据表真实信息，不编造）；\n"
    "   三、问题与目标（问题-目标一一对应，目标可检验）；\n"
    "   四、方案与计划（技术路线/实施步骤/里程碑/资源）；\n"
    "   五、预期价值与风险（价值主张 + 风险清单及应对）；\n"
    "   六、证据表（用户提供的证据逐条 + 来源/可靠度/是否用于论证）；\n"
    "   七、四层QA自检报告（内容层：主张有证据支撑吗 / 结构层：章节符合契约吗 / "
    "语言层：表述准确不夸大吗 / 评分层：对照评审标准自评打分并说明扣分点，四层逐项给结论，不省略）；\n"
    "7. 不自动升级事实强度：「可能改善」不许写成「显著提升」，除非有证据支撑；\n"
    "8. 关键证据缺失到无法支撑核心主张时，在第七节如实标注「本报告因证据不足暂不具备申报条件」。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

SYSTEM_PROMPT_EN = (
    "You are a senior proposal writer. Turn the user's project idea plus the provided "
    "facts / data / needs list into a complete Chinese (or English, per input) project "
    "proposal draft following the state machine: evidence table -> argument map -> "
    "section contracts -> four-layer QA.\n"
    "Rules:\n"
    "1. Stay faithful: only use information actually provided; mark missing facts as (TBC), never invent.\n"
    "2. Evidence first: list supporting facts/data/needs in an evidence table (source + reliability); "
    "every claim in the body must trace to an evidence row.\n"
    "3. Clear argument chain: background -> problem -> goal -> plan -> expected value, one claim per section.\n"
    "4. Problem-goal one-to-one mapping; every goal must be testable (quantified or verifiable).\n"
    "5. Section-contract writing: each section has a clear persuasive purpose; cut unsupported sentences.\n"
    "6. Structure strictly: basic info / background & significance / problems & goals / "
    "plan & schedule / expected value & risks / evidence table / four-layer QA self-check "
    "(content / structure / language / scoring), each layer with an explicit verdict.\n"
    "7. Never upgrade claim strength without evidence.\n"
    "Output the Markdown body only, with no extra explanation."
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_proposal_writer",
        description="把立项主题+事实/数据清单整理成结构化立项报告草稿（中文技能库 · proposal-writer）",
    )
    parser.add_argument("input", help="立项主题与事实/数据/需求清单文本路径，或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.proposal-writer.md）")
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
        raise SystemExit("错误：输入内容为空，请提供立项主题与事实/数据/需求清单。")
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
    print("输入材料：%d 字，切分为 %d 段，开始生成立项报告草稿……" % (len(text), len(chunks)), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是立项主题与事实/数据/需求清单（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
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
            out_path = base.rsplit(".", 1)[0] + ".proposal-writer.md"
        else:
            out_path = base + ".proposal-writer.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：草稿请对照原始事实清单复核后再交付。")


if __name__ == "__main__":
    main()