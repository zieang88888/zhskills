#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_wechat_article.py — 公众号长文流水线生成器（中文技能库 · wechat-article）

按分阶段校验流程跑公众号长文写作：
    brief/claims（核心主张清单）→ draft（初稿）→ review（五项标准自审）→ 定稿建议
单次运行内部多次调用 LLM，默认 --stage all 输出一份四段式 Markdown 文档。

只产出正文与审稿报告：不发布、不配图、不排版。zhskills 无联网搜索权限，
事实性陈述必须来自用户输入，否则模型必须标注「（待核实）」。

用法示例：
    python draft_wechat_article.py brief.txt --output article.md
    python draft_wechat_article.py brief.txt --stage brief
    python draft_wechat_article.py draft.md --stage review
    cat brief.txt | python draft_wechat_article.py -

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

# ---------- 各阶段系统提示词 ----------

BRIEF_SYSTEM_ZH = (
    "你是资深公众号内容编辑，负责「核心主张清单」阶段。\n"
    "用户会给你一个写作任务说明（选题、目标读者、账号定位、已有素材）。\n"
    "你的任务不是写文章，而是先把这篇文章收敛成一份核心主张清单：\n"
    "1. 识别目标读者是谁、这篇文章要让读者看完记住哪几个判断（3-7 条）；\n"
    "2. 每条主张写成一句话，后面用「依据：……」标注来源——仅限用户提供的素材、"
    "无可争议的公开常识；\n"
    "3. zhskills 没有联网搜索权限：凡是数字、引述、案例、时间、人名、机构名，"
    "用户没有给出依据的，一律标注「依据：（待核实）」，绝不允许凭模型记忆补成已核实事实；\n"
    "4. 依据不足、站不住的主张，直接删掉或降级为「观点」，不要硬凑。\n"
    "输出格式：先一行《文章任务理解：……》，然后用编号列表逐条列主张与依据。\n"
    "直接输出 Markdown 正文，不要任何额外解释。"
)

DRAFT_SYSTEM_ZH = (
    "你是资深公众号长文作者，负责「初稿」阶段。\n"
    "用户会给你写作任务说明，以及一份已经确认的核心主张清单（如有）。\n"
    "要求：\n"
    "1. 围绕核心主张写一篇公众号长文初稿：先拟一个标题，正文用小标题分节，开头 3 行内"
    "让目标读者觉得「这篇和我有关」，结尾回到核心主张；\n"
    "2. 事实纪律：初稿里的数字、引述、案例只能来自用户素材或主张清单里已标注依据的项；"
    "任何无来源的事实性陈述必须就地标注「（待核实）」，不得把模型记忆写成已核实事实；\n"
    "3. 可以写分析和经验判断，但要写得像人话，不用空话套话；\n"
    "4. 这是初稿，不是成稿——正常写完整篇，不要中途停下来提问。\n"
    "直接输出 Markdown 正文（标题 + 正文），不要任何额外解释。"
)

REVIEW_SYSTEM_ZH = (
    "你是严格的公众号责任编辑，负责「自审报告」阶段。\n"
    "用户会给你核心主张清单（如有）和待审的文章初稿。\n"
    "请按以下五项标准逐条审稿，每条给出：结论（通过 / 需修改）+ 具体问题位置 + 修改意见：\n"
    "1. 事实：每个数字、引述、案例都能在主张清单或用户素材里找到依据吗？"
    "有没有把模型记忆当成已核实事实？列出所有「（待核实）」项；\n"
    "2. 观点：核心判断是否鲜明、前后一致？有没有骑墙、空话、正确的废话？\n"
    "3. 实用性：读者看完能实际拿走什么（方法 / 判断 / 情绪）？\n"
    "4. 账号声音：口吻是否统一？像这个账号会写的话吗？\n"
    "5. 可读性：有没有超长句、堆砌、逻辑跳转？小标题节奏如何？开头 3 行能否留住人？\n"
    "最后单独一行给出编辑结论：结论：pass 或 结论：need_revision。"
    "只有五项全部达标才允许 pass，不得放水。\n"
    "直接输出 Markdown 审稿报告，不要任何额外解释。"
)

BRIEF_SYSTEM_EN = (
    "You are a senior WeChat-article editor running the 'claims' stage. "
    "Turn the user's writing brief into a 3-7 item list of core claims, each with a source "
    "(user material / common knowledge / '(TBC)' if unverifiable). Never invent facts from memory. "
    "Output the Markdown list only."
)
DRAFT_SYSTEM_EN = (
    "You are a senior WeChat long-form writer. Draft the article from the brief and confirmed claims. "
    "Only use facts with provided sources; mark any unsourced factual claim '(TBC)'. "
    "Output the Markdown draft (title + body) only."
)
REVIEW_SYSTEM_EN = (
    "You are a strict executive editor. Review the draft against five criteria: facts, opinion, "
    "usefulness, account voice, readability. End with one line: verdict: pass or verdict: need_revision. "
    "Do not pass unless all five pass. Output the Markdown review only."
)

STAGE_ORDER = ["all", "brief", "draft", "review"]


def build_parser():
    parser = argparse.ArgumentParser(
        prog="draft_wechat_article",
        description="公众号长文流水线：主张清单 → 初稿 → 五项自审 → 定稿建议（中文技能库 · wechat-article）",
    )
    parser.add_argument("input", help="写作任务说明文件路径（--stage review 时传待审初稿），或用 - 从标准输入读取")
    parser.add_argument("--output", "-o", help="输出 Markdown 文件路径（默认：输入名.wechat-article.md）")
    parser.add_argument("--stage", choices=STAGE_ORDER, default="all",
                        help="运行阶段：all=四段式全流程（默认），brief=只出主张清单，draft=只出初稿，review=只出审稿报告")
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
        raise SystemExit("错误：输入内容为空，请提供写作任务说明文本。")
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


def run_stage(stage_name, system_prompt, user_content, api_key, base_url, model):
    """对单个阶段：按切块多次调用 LLM，合并结果。进度打印到 stderr。"""
    chunks = chunk_text(user_content)
    outputs = []
    for i, chunk in enumerate(chunks, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下内容（第 %d/%d 段）：\n\n%s" % (i, len(chunks), chunk)},
        ]
        outputs.append(chat(messages, api_key, base_url, model))
        print("[%s] 第 %d/%d 段完成。" % (stage_name, i, len(chunks)), file=sys.stderr)
    if len(outputs) == 1:
        return outputs[0]
    return "\n\n".join(
        seg if idx == 0 else "## 补充内容（第 %d 段）\n\n%s" % (idx + 1, seg)
        for idx, seg in enumerate(outputs)
    )


def build_finalization(claims, draft, review):
    """第四段：定稿建议。从审稿报告里宽松识别编辑结论，统计待核实标注。"""
    joined = "\n".join(t for t in (claims, draft, review) if t)
    todo_count = joined.count("（待核实）")
    low = (review or "").lower()
    if "need_revision" in low or "需修改" in (review or "") or "待修改" in (review or ""):
        verdict = "need_revision（自审发现待修项，请勿直接发布）"
    elif "pass" in low:
        verdict = "pass（五项标准已过，可进入定稿；发布仍需用户另行授权）"
    else:
        verdict = "待人工判定（脚本未能从审稿报告中自动识别结论，请人工复核）"
    lines = [
        "## 四、定稿建议",
        "",
        "- 编辑结论：%s" % verdict,
        "- 待核实事实标注：全文共 %d 处「（待核实）」，发布前必须逐条补依据或删除。" % todo_count,
        "- 封存纪律：正文定稿后不得随意改写；如需修改，请回到 brief / draft / review 对应阶段重跑并重新审稿。",
        "- 发布说明：本技能不负责发布；推送到公众号草稿箱或正式发布必须由用户另行明确授权。",
    ]
    return "\n".join(lines)


def resolve_output_path(args):
    if args.output:
        return args.output
    base = args.input if args.input != "-" else "stdin"
    if "." in base:
        return base.rsplit(".", 1)[0] + ".wechat-article.md"
    return base + ".wechat-article.md"


def main():
    args = build_parser().parse_args()
    api_key = resolve_api_key(args)

    prompts = {
        "brief": BRIEF_SYSTEM_ZH,
        "draft": DRAFT_SYSTEM_ZH,
        "review": REVIEW_SYSTEM_ZH,
    } if args.lang == "zh" else {
        "brief": BRIEF_SYSTEM_EN,
        "draft": DRAFT_SYSTEM_EN,
        "review": REVIEW_SYSTEM_EN,
    }

    text = read_input(args.input)
    out_path = resolve_output_path(args)
    stage = args.stage

    claims_text = ""
    draft_text = ""
    review_text = ""

    if stage in ("all", "brief"):
        print("阶段 1/3 · brief → claims：%d 字输入。" % len(text), file=sys.stderr)
        claims_text = run_stage("claims", prompts["brief"], text, api_key, args.base_url, args.model)

    if stage == "brief":
        final = "## 一、核心主张清单（Claims）\n\n%s" % claims_text
    elif stage in ("all", "draft"):
        if stage == "all":
            draft_input = text + "\n\n## 已确认的核心主张清单\n\n" + claims_text
        else:
            draft_input = text
        print("阶段 2/3 · draft：写初稿。", file=sys.stderr)
        draft_text = run_stage("draft", prompts["draft"], draft_input, api_key, args.base_url, args.model)
        if stage == "draft":
            final = "## 二、文章初稿（Draft）\n\n%s" % draft_text
        else:
            print("阶段 3/3 · review：五项标准自审。", file=sys.stderr)
            review_input = ("## 核心主张清单\n\n" + claims_text +
                            "\n\n## 文章初稿\n\n" + draft_text)
            review_text = run_stage("review", prompts["review"], review_input,
                                   api_key, args.base_url, args.model)
            final = "\n\n".join([
                "## 一、核心主张清单（Claims）\n\n" + claims_text,
                "## 二、文章初稿（Draft）\n\n" + draft_text,
                "## 三、自审报告（Review）\n\n" + review_text,
                build_finalization(claims_text, draft_text, review_text),
            ])
    else:  # stage == "review"
        print("阶段 · review：对传入初稿做五项标准自审。", file=sys.stderr)
        review_text = run_stage("review", prompts["review"], text, api_key, args.base_url, args.model)
        final = "\n\n".join([
            "## 三、自审报告（Review）\n\n" + review_text,
            build_finalization("", text, review_text),
        ])

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(final)
    except OSError as exc:
        raise SystemExit("错误：无法写入输出文件 %s（%s）" % (out_path, exc))

    lines = final.count("\n") + 1
    print("已生成：%s（%d 行，stage=%s）" % (out_path, lines, stage))
    print("提示：草稿与审稿报告请人工复核；发布前补全所有（待核实）标注，发布需用户明确授权。")


if __name__ == "__main__":
    main()