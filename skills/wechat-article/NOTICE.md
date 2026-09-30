# NOTICE · 二次开发署名

本技能（wechat-article）改编自开源项目：

- 原项目：https://github.com/oaker-io/wewrite
- 原技能：skills/wewrite/SKILL.md（WeWrite 公众号内容主入口）
- 许可：MIT License
- 版权：Copyright (c) 2026 OpenClaw

原项目 LICENSE 全文：

MIT License

Copyright (c) 2026 OpenClaw

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## 本改编做了什么

1. 保留原技能的核心方法论：公众号长文分阶段校验流程 brief（写作任务与意图）→ claims（核心主张清单）→ draft（初稿）→ review_report（编辑审稿：事实 / 观点 / 实用性 / 账号声音 / 可读性五项标准，只有 pass 才进入定稿）→ 封存（正文定稿后不得随意改写）；以及两条核心纪律——搜索失败时不得把模型记忆包装成已核实事实、发布必须用户明确授权。
2. 去除原项目对 wewrite CLI 命令（`wewrite run start/step/finish` 等）与独立任务目录结构的重度绑定，只抽流程骨架，不搬 CLI。
3. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理 / 与脚本配合）。
4. 新增可执行 CLI（scripts/draft_wechat_article.py）：纯标准库、OpenAI 兼容接口、`--stage all/brief/draft/review` 分阶段命令行调用，将"提示词技能"升级为"可运行流水线"。
5. 新增输出模板（scripts/templates/wechat-article.template.md）：四段式文档骨架（核心主张清单 / 初稿 / 自审报告 / 定稿建议）。
6. 本地化约束：zhskills 无联网搜索权限，事实性陈述必须有用户提供依据，否则标注「（待核实）」；本技能只产出正文与审稿报告，不发布、不配图、不排版。