# NOTICE · 二次开发署名

本技能（xiaohongshu-comment-reply）改编自开源项目：

- 原项目：https://github.com/mengke-wang/xiaohongshu-ai-workbench
- 原技能：xiaohongshu-comment-reply（评论区回复）
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

1. 保留原技能的核心方法论：真人感回复原则（先回应对方再补充自己、少客服腔少感叹号、不吵架不阴阳、不硬导私信、质疑先承接顾虑再说明边界、价格/效果/法律/医疗/财务不做承诺）；单条评论"友好 / 专业 / 评论区口吻 / 引导私信 / 不建议这样回"五段输出；置顶评论三方向；恶意评论优先给"不争辩"的处理建议。
2. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理 / 与脚本配合）。
3. 新增可执行 CLI（scripts/draft_xiaohongshu_comment_reply.py）：零依赖、OpenAI 兼容接口、新增 `--persona` 账号人设参数（专业 / 亲切 / 幽默 / 品牌号 / 个人IP），场景从小红书泛化到中文互联网评论区（客服话术、差评回复、社群互动、微博评论区），不编造产品事实、不做承诺，将"提示词技能"升级为"可运行流水线"。
4. 新增输出模板（scripts/templates/xiaohongshu-comment-reply.template.md）。