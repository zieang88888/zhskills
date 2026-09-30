# NOTICE · 二次开发署名

本技能（decision-questionnaire）改编自开源项目：

- 原项目：https://github.com/mattpocock/skills
- 原技能：productivity/to-questionnaire（将用户无法独立拍板的决策，转成一份可异步填写的问卷）
- 许可：MIT License
- 版权：Copyright (c) 2026 Matt Pocock

原项目 LICENSE 全文：

MIT License

Copyright (c) 2026 Matt Pocock

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

1. 保留原技能的核心方法论：只访谈发送者本人（收件人是谁 / 需要拿回什么）；针对"收件人知道而用户不知道"的 gap 出题；最重要排最前；一题一意图；每题下方留答题空位；必要时一行 why-this-matters；末尾开放题"还有什么遗漏"；答题说明含"不知道也请标注、不要跳过"的容错提示；总原则"拷问发送者，不拷问被访者"。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理）。
3. 新增可执行 CLI（scripts/draft_decision_questionnaire.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"。
4. 新增输出模板（scripts/templates/decision-questionnaire.template.md）：英文占位符本地化为中文公文式措辞，并补充跨部门信息收集、需求调研、访谈提纲、供应商问询、汇报前材料核实等中文职场高频场景。