# NOTICE · 二次开发署名

本技能（idea-refine）改编自开源项目：

- 原项目：https://github.com/addyosmani/agent-skills
- 原技能：idea-refine（把粗糙想法通过发散—收敛—交付三阶段打磨成可执行的一页纸方案）
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

1. 保留原技能的核心方法论：三阶段——发散（HMW 重述原想法、提 3-5 个锐化问题、用透镜生成 5-8 个变体）、收敛（把变体聚成 2-3 个有实质差异的方向、按用户价值/可行性/差异化做压力测试、显式列出隐藏假设）、交付（输出一页纸 Markdown 方案，必含 Not Doing 清单及理由）；保留"做诚实思考伙伴、不做捧场机器""5-8 个想透的胜过 20 个肤浅的""Not Doing 是最有价值部分"等原则。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理），并将原英文方法论完整翻译、本地化到中文职场语境（公众号选题、活动策划、产品立项、创业点子评估、方案选型前的想法筛选）。
3. 新增可执行 CLI（scripts/draft_idea_refine.py）：零依赖、OpenAI 兼容接口、命令行调用，温度 0.4，新增 `--lenses` 自定义发散透镜参数（顿号分隔），将"交互式提示词技能"升级为"可运行流水线"。
4. 新增输出模板（scripts/templates/idea-refine.template.md）：把原英文一页纸结构本地化为六节中文结构（原始想法与 HMW 重述 / 锐化问题 / 方向四维对比表 / 推荐方向与隐藏假设 / Not Doing 清单 / 下一步行动）。