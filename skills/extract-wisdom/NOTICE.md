# NOTICE · 二次开发署名

本技能（extract-wisdom）改编自开源项目：

- 原项目：https://github.com/danielmiessler/fabric
- 原技能：patterns/extract_wisdom（从长文本中提炼多维智慧：观点、洞察、金句、事实、习惯、参考与建议）
- 许可：MIT License
- 版权：Copyright (c) 2012-2024 Scott Chacon and others

原项目 LICENSE 全文：

MIT License

Copyright (c) 2012-2024 Scott Chacon and others

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## 本改编做了什么

1. 保留原技能的核心方法论：按维度（而非按原文顺序）组织输出；区分观点与事实；保留原文关键引语（逐字金句，不 paraphrase）；提炼反直觉的洞察；列出对个人 / 团队 / 业务的可迁移启发；识别原文中可疑或缺乏支撑的断言；给出可执行建议。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理），并将原英文 pattern 的输出节本地化重组为 7 个中文维度节：核心观点（带【事实】/【观点】标记）、关键洞察、重要引用、术语与概念、适用场景与启发（个人/团队/业务）、可疑或待核实处、行动建议。
3. 新增可执行 CLI（scripts/draft_extract_wisdom.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"，长文本自动分块后合并。
4. 新增输出模板（scripts/templates/extract-wisdom.template.md）：中文占位骨架，逐节对应 SKILL.md 的输出结构。