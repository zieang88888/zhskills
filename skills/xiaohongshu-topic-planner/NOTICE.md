# NOTICE · 二次开发署名

本技能（xiaohongshu-topic-planner）改编自开源项目：

- 原项目：《小红书运营手册 · AI工作台》（https://xiaobot.net/p/xiaohongshuku）
- 原技能：选题策划 / topic-planner（把账号定位与目标拆成可连续发布的选题系统）
- 许可：MIT License
- 版权：Copyright (c) 2026 王梦珂

原项目 LICENSE 全文：

MIT License

Copyright (c) 2026 王梦珂

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

1. 保留原技能的核心方法论：6 类功能选题（吸引 / 共鸣 / 信任 / 教育 / 转化 / 互动）的定义；每条选题带功能标签（发这条是为了什么）；不引用外部资料、他人案例，不承诺爆款、涨粉或搜索排名；优先发布顺序与系列规划；按指定周期输出发布日历。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理），并补充：账号阶段配比（冷启动重吸引共鸣、稳定期重信任转化）、日历功能节奏（相邻两天不连续同一功能）、与 xiaohongshu-magazine 的栏目 / 母题挂接关系（magazine 定方向、本技能排日历）。
3. 新增可执行 CLI（scripts/draft_xiaohongshu_topic_planner.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"；新增 --days 参数控制规划周期（默认 14 天），输出结构按模板 5 节组织。
4. 新增输出模板（scripts/templates/xiaohongshu-topic-planner.template.md）：选题池按 6 类分组表格化（标题方向 / 功能标签 / 一句话思路 / 对应栏目），优先级前 5 条带理由，发布日历表格化（日期 / 选题 / 功能 / 栏目 / 发布形式）。