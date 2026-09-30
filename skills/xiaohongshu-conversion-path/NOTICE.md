# NOTICE · 二次开发署名

本技能（xiaohongshu-conversion-path）改编自开源项目：

- 原项目：https://github.com/mengke-wang/xiaohongshu-ai-workbench
- 原技能：xiaohongshu-conversion-path（成交路径设计）
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

1. 保留原技能的核心方法论：6 段成交路径（吸引 → 筛选 → 信任 → 行动 → 私信 → 复访）；4 类内容分工（吸引 / 信任 / 筛选 / 转化，每类目的 + 3 个选题建议）；主页承接、置顶内容、评论区动作；私信筛选问题（用问题筛需求，不一上来成交）；推广免费工具 / 小程序时"成交"= 体验、收藏、反馈、转发的口径。
2. 场景从单一小红书账号泛化为中文职场私域转化 / 销售漏斗 / 落地页文案 / 销售邮件序列。
3. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理）。
4. 新增可执行 CLI（scripts/draft_xiaohongshu_conversion_path.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"。
5. 新增输出模板（scripts/templates/xiaohongshu-conversion-path.template.md）。