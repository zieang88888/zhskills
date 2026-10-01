# NOTICE · 二次开发署名

本技能（verification-before-completion）改编自开源项目：

- 原项目：https://github.com/obra/superpowers
- 原技能：verification-before-completion（交付前核验：没有新鲜的验证证据，不得声称完成）
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

1. 保留原技能的核心方法论：铁律"没有新鲜的验证证据，不得声称完成"；五步门控（识别→执行→读取→对照→才声称）；借口-现实对照表；红旗词清单（should/probably/seems 等）；常见失败对照表（测试/linter/构建/bug修复/回归/Agent交付/需求满足）；违反字面规则 = 违反规则精神。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理）。
3. 新增可执行 CLI（scripts/draft_verification_before_completion.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"。
4. 新增输出模板（scripts/templates/verification-before-completion.template.md）：英文方法论本地化为中文职场场景（周报数据核实、公文发出前核对、汇报材料自检、交付前检查清单、发布前门禁），借口对照表中文化为"应该没问题""之前跑过测试了""我很确定""就这一次"等中文职场高频借口。