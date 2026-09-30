# NOTICE · 二次开发署名

本技能（xiaohongshu-profile）改编自开源项目：

- 原项目：https://github.com/mengke-wang/xiaohongshu-ai-workbench
- 原技能：xiaohongshu-profile（主页体检与简介改写）
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

1. 保留原技能的核心方法论：3 秒第一眼判断、7 个诊断维度（第一眼清晰度 / 目标用户 / 具体结果 / 信任材料 / 转化动作 / 置顶结构 / 语气一致性）、简介五要素原则、4 版简介改写（清晰专业版 / 亲近人话版 / 转化引导版 / 个人 IP 版）。
2. 场景泛化：从单一小红书主页扩展为 LinkedIn 档案、微信签名、知乎个人介绍等中文职场个人简介场景。
3. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理）。
4. 新增可执行 CLI（scripts/draft_xiaohongshu_profile.py）：零依赖、OpenAI 兼容接口、命令行调用，将"提示词技能"升级为"可运行流水线"。
5. 新增输出模板（scripts/templates/xiaohongshu-profile.template.md）。