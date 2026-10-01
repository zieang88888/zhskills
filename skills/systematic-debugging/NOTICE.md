# NOTICE · 二次开发署名

本技能（systematic-debugging）改编自开源项目：

- 原项目：https://github.com/obra/superpowers
- 原技能：systematic-debugging（遇到任何 bug、测试失败或异常行为时，在提出修复之前使用的系统化根因分析方法论）
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

1. 保留原技能的核心方法论：四阶段强制串行（根因调查 → 模式对比 → 单假设最小验证 → 单点修复）；核心铁律"未找到根因之前绝不提修复"；3 次修复失败即停下质疑架构/基本假设；沿组件边界加观测定位断点；找正常对照案例列差异；一次只验证一个假设；只修根因一处不顺手优化。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理），并将方法论从代码调试场景泛化到中文职场的线上故障复盘、客诉根因分析、质检异常、流程事故复盘、业务指标异常排查等场景。
3. 新增可执行 CLI（scripts/draft_systematic_debugging.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"；新增 --attempts 参数，传入已尝试修复次数，≥3 时自动在系统提示词中注入"质疑基本假设"强制提示。
4. 新增输出模板（scripts/templates/systematic-debugging.template.md）：六节结构（问题现象与影响 / 复现步骤 / 假设列表 / 模式对比 / 最可能根因与修复方案 / 复盘教训），配表格化差异对比与验证实验设计。