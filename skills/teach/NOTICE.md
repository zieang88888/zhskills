# NOTICE · 二次开发署名

本技能（teach）改编自开源项目：

- 原项目：https://github.com/mattpocock/skills
- 原技能：teach（在工作区内教会用户一门新技能或概念）
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

1. 保留原技能的核心方法论：MISSION 驱动（先想清楚学员为什么学、学完要能做什么）；最近发展区（内容难度贴着学员现有水平、只略高一点点）；区分"熟练度（fluency）"与"留存强度（storage strength）"，用理想难度设计练习；显式落地三种学习科学方法——提取练习（retrieval practice）、间隔重复（spacing）、交错练习（interleaving）；评估与反馈闭环（练习后尽快给反馈）。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理）。
3. 裁剪：原技能是有状态、多会话的 HTML 教学环境（MISSION.md / lessons/*.html / learning-records 等），本改编**不做多会话 HTML 教学环境、不做逐课对话式教学**，改为 CLI 单轮输出一份完整教案 Markdown。
4. 新增可执行 CLI（scripts/draft_teach.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"；`--duration` 注入系统提示词控制课程大纲时长分配。
5. 新增输出模板（scripts/templates/teach.template.md）：把六节教案结构（教学目标 / 学员画像 / 课程大纲 / 练习设计 / 评估方式 / 课后巩固）固化为占位骨架。