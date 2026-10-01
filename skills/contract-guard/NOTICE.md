# NOTICE · 二次开发署名

本技能（contract-guard）改编自开源项目：

- 原项目：https://github.com/he-yufeng/ContractGuard
- 原技能：ContractGuard 合同审查 AI Agent（上传合同 → 红旗/警告/保护/缺失保护四分类 + A+~F 公平评分 + 管辖地相关强制规定对照）
- 许可：MIT License
- 版权：Copyright (c) 2026 Yufeng He

原项目 LICENSE 全文：

MIT License

Copyright (c) 2026 Yufeng He

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

1. 保留原技能的核心方法论：条款四分类（红旗 Red Flags / 警告 Warnings / 保护 Protections / 缺失保护 Missing Protections）；A+~F 公平评分并附一句话理由；强制规定逐项对照（违规/合规/未知三态，未知如实标注不冒充通过）；对每条问题给出可落地的修改建议而非泛泛批评。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理）。
3. 新增可执行 CLI（scripts/draft_contract_guard.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"；新增 `--side {甲方,乙方,中立}` 立场参数（默认乙方），使同一份合同可按不同审查方视角出报告。
4. 新增输出模板（scripts/templates/contract-guard.template.md）：将原项目英文 Rich 终端输出 / Pydantic JSON 结构本地化为中文 Markdown 六段式报告（合同概要 / 四分类清单 / 公平评分 / 中国法强制规定对照 / 修改建议 / 待确认与边界声明）；原项目美国加州住宅租赁等辖区规则替换为中国法常见强制规定清单（试用期长度与 80% 工资下限、竞业限制≤2 年且须补偿、加班费 150/200/300%、定金≤20%、民间借贷利率≤签约时一年期 LPR 4 倍、禁止预扣利息、保密义务合理性）。