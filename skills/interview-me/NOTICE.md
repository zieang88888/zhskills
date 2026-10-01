# NOTICE · 二次开发署名

本技能（interview-me）改编自开源项目：

- 原项目：https://github.com/addyosmani/agent-skills
- 原技能：interview-me（在任何方案/文档/代码动工前，通过一次一问、附猜测答案的访谈，把模糊委托收敛成用户真正想要的意图）
- 许可：MIT License
- 版权：Copyright (c) 2025 Addy Osmani

原项目 LICENSE 全文：

MIT License

Copyright (c) 2025 Addy Osmani

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

1. 保留原技能的核心方法论：开口前先写下一句话假设并附诚实置信度数字（低于 ~70% 同行写还缺什么）；一次只问一个问题、每问必附猜测答案与理由；警惕"最佳实践/可扩展/通用做法"等"应该想要"的套话，追问"如果不用向任何人解释你真正想要什么"；用 Outcome / User / Why now / Success / Constraint / Out of scope 六行复述意图（Out of scope 不可省）；要用户明确的"是"才算收敛，"你看着办/听起来不错/沉默"都不算。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理），并把英文方法论完整翻译、本地化到中文职场语境（产品需求梳理、活动立项、跨部门任务交接、客户需求访谈、汇报前对齐）。
3. 新增可执行 CLI（scripts/draft_interview_me.py）：零依赖、OpenAI 兼容接口、命令行调用，将交互式访谈在单轮 CLI 中改造为"问题清单 + 每问附猜测答案供用户逐条确认/修改"的收敛报告；新增可选 --focus 参数指定重点澄清方向；温度 0.3。
4. 新增输出模板（scripts/templates/interview-me.template.md）：固定四节结构（需求原文与初步假设 / 访谈问题清单 / 6 行需求复述 / 待确认汇总与下一步），信息不足处一律标"（待确认）"，猜测答案显式挂牌"这是猜测，请确认或修正"。