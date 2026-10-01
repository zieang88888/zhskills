# NOTICE · 二次开发署名

本技能（data-storytelling）改编自开源项目：

- 原项目：https://github.com/wshobson/agents
- 原技能：data-storytelling（把零散数据/指标组织成有叙事结构的汇报报告）
- 许可：MIT License
- 版权：Copyright (c) 2024 Seth Hobson

原项目 LICENSE 全文：

MIT License

Copyright (c) 2024 Seth Hobson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## 本改编做了什么

1. 保留原技能的核心方法论：Setup→Conflict→Resolution 故事结构；Narrative Arc（Hook/Context/Rising Action/Climax/Resolution/CTA）；三大支柱 Data/Narrative/Visuals；三种故事框架（Problem-Solution / Trend / Comparison）；7 页 Data Story Flow 模板与单页仪表盘模板；结论式标题公式（具体数字 + 业务影响 + 可行动上下文）；过渡话术（Building / Insight / Action）；不确定性表达（置信区间 / 区间估算 / 保守-乐观双情景）；Do's（结论前置、三点法则、让数据说话、连接听众目标、以行动收尾）与 Don'ts（不做数据倾倒、不埋洞察、不堆术语、不先讲方法论）。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理 / 与脚本配合），并完整中文化：英文框架名本地化为「问题-解决方案 / 趋势 / 对比」，示例换成中文职场语境（复购率、投放 ROI、区域扩张）。
3. 新增可执行 CLI（scripts/draft_data_storytelling.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"；新增 --framework 参数允许显式指定故事框架。
4. 新增输出模板（scripts/templates/data-storytelling.template.md）：把原英文 7 页流模板重排为中文 7 节结构（核心信息 / 框架选择 / 数据支撑 / 叙事结构 / 洞察与建议 / 不确定性声明 / Do & Don't 自查），并补充中文职场高频场景（经营分析会、月度复盘、看板解读、投放效果汇报、市场分析）。