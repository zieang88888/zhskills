# NOTICE · 二次开发署名

本技能（brainstorm-spec）改编自开源项目：

- 原项目：https://github.com/obra/superpowers
- 原技能：brainstorming（把想法通过协作对话收敛成设计规格）
- 许可：MIT License
- 版权：Copyright (c) 2025 Jesse Vincent

原项目 LICENSE 全文：

MIT License

Copyright (c) 2025 Jesse Vincent

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

1. 保留原技能的核心方法论：先复述理解并邀请纠正；路径三级分类（Spike 可行性试探 / Bounded 体系内小改 / Architectural 全新立项或大改）；一次只问一个澄清问题（偏好选择题）；提出 2-3 个方案带权衡与推荐；分节呈现设计并逐节获确认；落盘为 YYYY-MM-DD-主题-design.md；写完四项自检（占位符扫描 / 内部一致性 / 范围是否过大 / 歧义检查）；HARD-GATE 未经用户批准不得进入交付动作；隐藏复杂度必须升级路径、棘轮只升不降。
2. 把原文的编码语境（文件 / TDD / git commit / 代码仓库 spec 路径）整体翻译并泛化为中文业务语境：产品需求梳理、活动立项、方案选型、流程改造、会议纪要后方向对齐；"实现"统一表述为"交付动作"。
3. 裁剪原文 Visual Companion 浏览器画 mockup 的可选项。
4. 明确两种使用形态：交互式对话用一次一问、逐节确认；命令行批处理单轮收敛输出完整规格书（路径分级判断、2-3 方案对比、推荐方案实施要点、风险与待确认清单、四项自检结果）。
5. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常 / 与脚本配合）。
6. 新增可执行 CLI（scripts/draft_brainstorm_spec.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"。
7. 新增输出模板（scripts/templates/brainstorm-spec.template.md）。