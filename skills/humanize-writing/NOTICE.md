# NOTICE · 二次开发署名

本技能（humanize-writing）改编自开源项目：

- 原项目：https://github.com/op7418/humanizer-zh
- 原技能：humanizer-zh（中文文本去模板化润色 / 去 AI 味）
- 许可：MIT License
- 版权：Copyright (c) 2026 歸藏

原项目 LICENSE 全文：

MIT License

Copyright (c) 2026 歸藏

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

1. 保留原技能的核心方法论：四级约束优先级（保留信息与确定程度 > 遵守编辑范围 > 匹配作者声音 > 处理具体表达问题）、文体与作者声音校准、文件保护规则（代码块 / URL / YAML front matter / 表格 / 锚点），以及 A–F 共 31 条中文编辑规则（每条含「改写前 / 改写后 / 保留」三段式示例）与交付前核对清单。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理），并明确边界：不判断作者身份、不承诺通过 AI 检测器、规则是检查线索而非词表黑名单、禁止机械替换。
3. 新增可执行 CLI（scripts/draft_humanize_writing.py）：零依赖、OpenAI 兼容接口、命令行调用，支持 --notes 输出按 A–F 规则组归类的主要改动说明，将“提示词技能”升级为“可运行流水线”。
4. 新增输出模板（scripts/templates/humanize-writing.template.md）。