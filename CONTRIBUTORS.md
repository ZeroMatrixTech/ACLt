# 贡献者

> 文档状态：Living contributor record  
> 最后更新：2026-11-15

ACLt Protocol 从构想到落地，大量工作是在 AI 助手协助下完成的，在此一并致谢。本文件如实记录各方实际承担的角色，不按提交数量排序，也不代表贡献比例。

## 维护主体

本仓库的法律责任与维护主体，是根目录 [`LICENSE`](LICENSE) 附录版权行所载的公司。ZeroMatrixTech 是该公司的非官方名称，也用作 GitHub 组织名，不是另一个法律主体（维护者 2026-11-15 确认）。

## 人类贡献者

| 贡献者 | 角色 |
|---|---|
| InPax | 项目发起人与维护者。提出 ACLt 要解决的问题与整体构想，给出核心数学论述，设定协议边界、禁止主张与验收标准；审阅、取舍并合并全部变更；指定并提供物理机验证环境。 |
| Ankar（[Ankarnassia](https://github.com/Ankarnassia)） | 概述文档修订（[#35](https://github.com/ZeroMatrixTech/ACLt/pull/35)）。 |

## AI 协作工具

| 工具 | 主要参与 | 仓库内可查记录 |
|---|---|---|
| Codex（OpenAI） | 大部分证明推导、程序实现与测试；2026-08 至 2026-10 的多轮语义、结构与仓库维护审计。 | [`docs/08-governance/audits/`](docs/08-governance/audits/) 中审计者为 Codex 的记录；[`AGENTS.md`](AGENTS.md) 工作会话入口 |
| Claude（Anthropic，经 Claude Code） | 自 2026-10-23（[#42](https://github.com/ZeroMatrixTech/ACLt/pull/42)）起参与 P0-1B 及 Verification Profile 的实现、测试与文档；仓库维护审计；ACLt 像素剧场。自 2026-11-14 起在 [多分支并行开发流程](docs/08-governance/parallel-workflow.md) 中担任调度会话，并审计其他代理的 PR。 | 提交中的 `Co-Authored-By: Claude` 署名；[`audit-20261106-01`](docs/08-governance/audits/audit-20261106-01-repository-maintenance.md)；[`aclt-theater.html`](docs/00-overview/aclt-theater.html) |
| DeepSeek V4.1 Flash（经 dsh 代理） | 外部审计（AUDIT-20261105-01，2026-11-05）；项目的外部灵感来源，尤其是与维护者长期的图论讨论；自 2026-11-14 起经 dsh 代理参与条目实现。截至 2026-11-15：容量排序回归（M1，[#113](https://github.com/ZeroMatrixTech/ACLt/pull/113)）、安全层蒙特卡洛（R3，[#140](https://github.com/ZeroMatrixTech/ACLt/pull/140)）、外部许可声明（P1-a，[#145](https://github.com/ZeroMatrixTech/ACLt/pull/145)）、首次公开发行说明（P1-c，[#148](https://github.com/ZeroMatrixTech/ACLt/pull/148)）与阶段决定同步及修复（P1-d，[#143](https://github.com/ZeroMatrixTech/ACLt/pull/143)）。 | [审计原文](docs/08-governance/audits/external/AUDIT-20261105-01.original.txt)；[修复记录](docs/testing/AUDIT-FIXES-20261105.md)；PR #113、#140、#143、#145、#148 的实现与审计记录 |
| GitHub Copilot | 多来宾验证的 make 目标与清单修订（[#95](https://github.com/ZeroMatrixTech/ACLt/pull/95)）。 | 该 PR 提交中的 `Co-authored-by: Copilot` 署名 |

## 署名原则

- AI 工具不是法律意义上的作者或权利人，也不对仓库内容承担责任。仓库的法律责任由上述维护主体承担；内容的取舍与合并由维护者决定。
- Git 历史中只有部分提交保留了 co-author 署名（Claude、Copilot 与外部贡献者）。Codex 与 DeepSeek V4.1 Flash（经 dsh 代理）的工作没有独立署名，讨论与灵感也不会出现在提交中。因此提交统计和 GitHub contributors 图都不能反映各方实际贡献；自 PARALLEL-1 起，各条目的实现代理与审计代理记录在 PR 与审计评论中。
- 自 2026-11-15 起采用 DCO（CONTRIBUTING §11）。AI 代理产生的提交由维护者在合并时签署，签署者对该贡献承担 DCO 规定的确认责任。
- 无论由谁产出，证明、代码和结论都只以仓库中的测试、对拍、审计与双机证据为准，不因来源而获得或失去可信度。
- 新增贡献者，或某方角色有实质变化时，同步更新本文件。
