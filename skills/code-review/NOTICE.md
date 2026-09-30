# NOTICE · 二次开发署名

本技能（code-review）改编自开源项目：

- 原项目：https://github.com/mattpocock/skills
- 原技能：skills/engineering/code-review（代码双轴审查：Standards + Spec）
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

1. 保留原技能的核心方法论：双轴审查——Standards（成文规范优先，叠加 Fowler《重构》第 3 章 12 条坏味道基线，坏味道只作判断项）与 Spec（只报需求缺失、范围蔓延、看似实现实则错误三类，逐条引需求原文）；两轴分头跑、互不污染，最后按 `## Standards` / `## Spec` 两节并列汇总，末尾各给本轴总数与最严重问题，不跨轴排序。
2. 本地化：去掉对 `git diff/log` 与 issue-tracker 配置文件的依赖，改为用户直接粘贴代码改动（diff 文本或新旧对照）作为输入；需求文档改为 `--spec` 参数传入；原并行子代理调度在 CLI 里退化为顺序两遍（先 Standards 后 Spec，互不串用上下文）。
3. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理 / 与脚本配合）。
4. 新增可执行 CLI（scripts/draft_code_review.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"。
5. 新增输出模板（scripts/templates/code-review.template.md）。