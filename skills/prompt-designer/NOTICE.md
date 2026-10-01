# NOTICE · 二次开发署名

本技能（prompt-designer）改编自开源项目：

- 原项目：https://github.com/danielmiessler/fabric
- 原技能：patterns 提示词编写方法论（将"模糊愿望"结构化拆解为角色 / 输入 / 步骤指令 / 输出格式 / 质量规则的提示词 pattern）
- 许可：MIT License
- 版权：Copyright (c) 2012-2024 Scott Chacon and others

原项目 LICENSE 全文：

MIT License
Copyright (c) 2012-2024 Scott Chacon and others

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the
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

1. 保留原项目 patterns 的核心方法论：一份好提示词由"触发场景与角色设定 / 输入材料说明 / 明确的任务指令（含禁止事项）/ 输出格式约束 / 质量规则与自检"五要素构成，并遵循"一次成型 → 试运行反馈 → 迭代修正"的打磨流程。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理）。
3. 新增可执行 CLI（scripts/draft_prompt_designer.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"；新增 `--mode {design, optimize}` 区分从零设计与优化已有提示词。
4. 新增输出模板（scripts/templates/prompt-designer.template.md）：英文 prompt-engineering 术语本地化为中文职场表达（"让 AI 扮演的角色""你要喂给它的材料"），并覆盖写工作邮件 / 会议纪要、审合同摘要、周报数据整理、小红书文案标题等中文职场高频场景。