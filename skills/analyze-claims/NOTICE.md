# NOTICE · 二次开发署名

本技能（analyze-claims）改编自开源项目：

- 原项目：https://github.com/danielmiessler/fabric
- 原技能：analyze_claims（分析并评估输入文本中的事实声明与论证，逐条给出支持证据、反驳证据与质量评级）
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

1. 保留原技能的核心方法论：把输入文本中的事实声明与论证拆开；逐条列出主张、支持证据与反驳证据；识别逻辑谬误；对每条声明给出质量评级（原 A–F 档）与整体分析；强调证据必须真实、外部可验证、不得编造。
2. 按中文信息甄别场景本地化：输出重构为「声明拆解（原文片段 / 类型 / 可证伪性）→ 逐条评估（证据强度 / 来源可靠度 / 与已知事实冲突）→ 可信度结论（高 / 中 / 低）→ 需核实清单 → 边界说明」；声明类型体系改为事实断言 / 价值判断 / 情绪表达 / 建议，评级由 A–F 简化为高 / 中 / 低。
3. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理）。
4. 新增可执行 CLI（scripts/draft_analyze_claims.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"。
5. 新增输出模板（scripts/templates/analyze-claims.template.md）。