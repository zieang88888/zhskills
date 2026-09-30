# NOTICE · 二次开发署名

本技能（execution-plan）改编自开源项目：

- 原项目：https://github.com/obra/superpowers
- 原技能：writing-plans（编写实施计划）
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

1. 保留原技能的核心方法论：范围检查（多子系统拆分计划）、先画责任结构图锁定边界、任务粒度切分（每个任务自带可独立验收的交付物）、文档头强制含 Goal/范围/全局约束/Review Focus、任务结构含交付物与接口、无占位符铁律、四项自检（需求覆盖/占位符扫描/跨任务一致性/检查点落验）。
2. 本地化适配：将 TDD 测试循环替换为「验收标准/检查点」，将 git commit 替换为「里程碑交付」，将「文件责任图」替换为「交付物责任结构图」；将 Review Focus 翻译为业务语言（预算/审批/对外沟通等易漏点）；适用场景改写为中文职场（项目排期、工作计划、活动执行方案、任务拆解）。
3. 按 zhskills 标准重写 SKILL.md 结构（定位 / 输入要求 / 输出结构 / 工作流程 / 质量规则 / 边界与异常处理）。
4. 新增可执行 CLI（scripts/draft_execution_plan.py）：零依赖、OpenAI 兼容接口、命令行调用，将「提示词技能」升级为「可运行流水线」。
5. 新增输出模板（scripts/templates/execution-plan.template.md）。