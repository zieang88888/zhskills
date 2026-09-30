#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_xiaohongshu_title.py — 小红书标题生成器（中文技能库 · xiaohongshu-title）

改编自 mengke-wang/xiaohongshu-ai-workbench（MIT © 2026 王梦珂），
把素材 / 卖点 / 选题方向 / 已有标题变成小红书风格候选标题。
三种模式：quick（默认，12 风格 24 个标题）/ diagnose（4 方向 20 标题 + 首推）/ optimize（诊断并改写已有标题）。

用法示例：
    python draft_xiaohongshu_title.py 素材.txt --mode quick --output titles.md
    python draft_xiaohongshu_title.py 素材.txt --mode optimize --titles "标题A；标题B"
    cat 素材.txt | python draft_xiaohongshu_title.py -

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
CHUNK_SIZE = 9000
CHUNK_OVERLAP = 400
REQUEST_TIMEOUT = 120

BANNED_WORDS = (
    "直击灵魂、极致体验、视觉盛宴、天花板、YYDS、绝绝子、封神、宝藏、氛围感拉满、"
    "谁懂啊、家人们、狠狠、狠狠拿捏、闭眼入、不允许还有人不知道、建议所有人、我宣布、"
    "被问爆了、高级感、松弛感、这谁顶得住"
)
BANNED_PATTERNS = (
    "不是……而是……、这不算 X 实际是 Y、表面是 X 背后是 Y、看起来是 X 本质是 Y、"
    "与其说 X 不如说 Y、原来真正的 X 是……、成年人的崩溃往往……、看似普通其实藏着……、"
    "这才是 X 该有的样子"
)

RULES_ZH = (
    "你是小红书标题外科医生。任务是从用户内容里抓住具体画面、真实处境和传播钩子，"
    "生成像真人会点、会停、会转发的标题。\n"
    "规则：\n"
    "1. 忠于输入：只基于用户输入与通用创作原则，不引用外部案例、不编造价格/销量/效果/身份/背书；\n"
    "2. 不确定表达：无可验证结果时用'像/可能/适合/看起来'，不写成确定承诺；\n"
    "3. 禁用词零容忍：不得出现「%s」；\n"
    "4. 禁用句式：不得使用「%s」；\n"
    "5. 标题 6-18 字，搜索转化类最多 22 字；感叹号最多连续 2 个，默认不用；\n"
    "6. 造场景不概括观点：先找具体的人、事、动作、物件、数字、价格、冲突和反常细节；\n"
    "7. 从用户处境切入，不留卖方视角；\n"
    "8. 留一点未完成：不要把答案说完，保留悬念、动作、冲突或问题。\n"
) % (BANNED_WORDS, BANNED_PATTERNS)

QUICK_PROMPT = (
    RULES_ZH + "\n"
    "请严格按以下 12 组风格依次输出，每组 2 个标题（A./B.），只输出标题，不寒暄、不解释、不总结。\n"
    "【1 犀利吐槽风】【2 情绪定性风】【3 悬念代价风】【4 反常识风】【5 冷知识风】\n"
    "【6 强反转风】【7 人话口吻风】【8 趣味夸张风】【9 评论区风】【10 对话提问风】【11 数字焦虑风】【12 独体句风】\n"
    "自检：至少 4 组带标点或问句；至少 3 组带'我'或'你'；至少 3 组带数字；12 组句式有明显差异。\n"
    "输出格式：\n"
    "【1 犀利吐槽风】\nA. ____\nB. ____\n……（直到第 12 组）"
)

DIAGNOSE_PROMPT = (
    RULES_ZH + "\n"
    "请按以下格式输出：\n"
    "先给 4 个方向及其适用场景：1 封面短句（短、怪、像人话，图片/视频第一眼有画面感）"
    "；2 评论区口吻（像高赞评论，适合互动、转发、接梗）"
    "；3 洞察判断（有判断、带一点刺，适合品牌、消费、职场、商业观察）"
    "；4 搜索转化（保留关键词，适合教程、测评、避坑、产品和服务内容）。\n"
    "然后按方向给标题：A 封面短句 8 个；B 评论区口吻 5 个；C 洞察判断 4 个；D 搜索/转化 3 个。\n"
    "最后给：首推标题 + 为什么选它（一句理由）+ 可继续细化方向（更短 / 更像评论区 / 更稳 / 更清楚）。"
)

OPTIMIZE_PROMPT = (
    RULES_ZH + "\n"
    "用户提供了已有标题，请先做原标题诊断（具体指出问题：太像摘要、太卖方视角、缺少画面、"
    "标题说完答案、没有用户处境、存在虚假承诺风险等，不要泛泛而谈），\n"
    "再给：保留原方向改写 3 条；换方向改写 5 条；最后首推标题 + 为什么选它（一句理由）。"
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_xiaohongshu_title",
        description="小红书标题生成与优化（中文技能库 · xiaohongshu-title）",
    )
    parser.add_argument("input", help="素材文件路径，或用 - 从标准输入读取")
    parser.add_argument("--mode", choices=["quick", "diagnose", "optimize"], default="quick",
                        help="模式（默认 %(default)s）：quick 快速 24 标题 / diagnose 方向诊断 / optimize 已有标题优化")
    parser.add_argument("--titles", help="优化模式必填：已有标题，用中文分号分隔，如 \"标题A；标题B\"")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.xiaohongshu-title.md）")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型名（默认 %(default)s）")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI 兼容接口根地址（默认 %(default)s）")
    parser.add_argument("--api-key", default=None, help="API Key（优先于环境变量）")
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
        raise SystemExit("错误：输入内容为空，请提供素材文本。")
    return text


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
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
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.9,
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

    if args.mode == "optimize" and not args.titles:
        raise SystemExit("错误：optimize 模式需要提供已有标题，请用 --titles \"标题A；标题B\"。")

    prompt = {"quick": QUICK_PROMPT, "diagnose": DIAGNOSE_PROMPT, "optimize": OPTIMIZE_PROMPT}[args.mode]

    text = read_input(args.input)
    chunks = chunk_text(text)
    print("素材：%d 字，切分为 %d 段，模式：%s，开始生成标题……" % (len(text), len(chunks), args.mode), file=sys.stderr)

    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        extra = "\n\n用户已有标题：%s" % args.titles if (args.mode == "optimize" and args.titles) else ""
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "以下是素材（第 %d/%d 段）：\n\n%s%s" % (i, len(chunks), chunk, extra)},
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
            out_path = base.rsplit(".", 1)[0] + ".xiaohongshu-title.md"
        else:
            out_path = base + ".xiaohongshu-title.md"

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = merged.count("\n") + 1
    print("已生成：%s（%d 行）" % (out_path, lines))
    print("提示：标题发布前请人工复核，确保没有夸大承诺。")


if __name__ == "__main__":
    main()
