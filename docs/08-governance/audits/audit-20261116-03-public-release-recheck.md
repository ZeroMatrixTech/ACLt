# ACLt 首次公开发布准备增量回验续轮

> 编号：AUD-20261116-03 · 状态：供维护者审阅，待 dsh 入库
> 类别：发布准备审计 · 审计代理：Codex
> 基线：`origin/main` `89ae3a8b7174afd08d03e3ee841b110c0f3bf09a`（#171）
> 增量：`d0bf56e8fa8bd1fdfe4903c198b1898dd6d9930b..89ae3a8b7174afd08d03e3ee841b110c0f3bf09a`
> 审计窗口：2026-11-16 19:05:45–19:09:26 CET，Europe/Budapest（UTC+01:00）
> 依据：[计划卡 #161](https://github.com/ZeroMatrixTech/ACLt/issues/161) · [阶段 #128](https://github.com/ZeroMatrixTech/ACLt/issues/128) · [前轮报告](audit-20261116-02-public-release-recheck.md) · [审计程序](../audit-procedure.md)

## A0 — 授权、权限与偏离

在临时 bare 副本通过 GitHub fetch 固定主线和证据标签，建立分离 worktree。原检出保持只读。范围为前轮 A9 中尚未关闭的项、增量提交、公开包、DCO、文档整合和发布检查。禁止修改仓库、PR、Issue、设置及标签。未运行 SSH、VM、物理双机、全量 `make test` 或新的 R4 campaign。未修改 PREVIEW。

按本轮要求，上一轮的全历史扫描沿用，新增对象与正文按 A7 的窗口和模式扫描；全量测试、最终提交重扫和源码包对拍留给 PREVIEW §10。报告以保留发现的方式交付。进度末端基线 CI 仍在运行，报告把它保留为待核，不沿用早期提交结果。归档拆包在内存中读取成员，避免向审计树释出内容。清理前审计树 `git status --porcelain` 为空，移除后从外部目录确认列表仅余临时 bare 副本。原检出最终状态也为空。

## A1 — 仓库与文件盘点

9 个 first-parent 提交，143 个路径变动（新增 15，修改 124，删除 4），1,448 行新增、824 行删除。

| 区域 | 提交、条目与复核证据 |
|---|---|
| 前轮报告归档 | `bdefaff` #162 |
| P1-i 代理文件移出当前交付 | `7232164` #167 / #164，[审计](https://github.com/ZeroMatrixTech/ACLt/pull/167#issuecomment-6921100256) |
| P1-g 状态与证据卫生 | `e72acd3` #169 / #163，[审计](https://github.com/ZeroMatrixTech/ACLt/pull/169#issuecomment-6921808544) |
| P1-j 本地字体、DCO 补救 | `29ae739` #168 / #165，[审计](https://github.com/ZeroMatrixTech/ACLt/pull/168#issuecomment-6922689479)；`864561a` |
| P1-h3 路线图与发行文案 | `3204bd7` #170 / #166，[审计](https://github.com/ZeroMatrixTech/ACLt/pull/170#issuecomment-6923727509) |
| P1-h2 规范、分析、ADR 与研究文风 | `0084705` #173 / #166，[审计](https://github.com/ZeroMatrixTech/ACLt/pull/173#issuecomment-6923855531) |
| P1-h4 证据报告入口和结论 | `7b21932` #172 / #166，[审计](https://github.com/ZeroMatrixTech/ACLt/pull/172#issuecomment-6924137123) |
| P1-h1 入口、行为准则与 Issue 模板 | `89ae3a8` #171 / #166，[审计](https://github.com/ZeroMatrixTech/ACLt/pull/171#issuecomment-6924236027) |

## A2 — 时间戳与来源

前轮基线 d0bf56e 的 Git 时间为 2026-11-16 14:57:51 CET，GitHub 正文扫描以对应 UTC 时点 13:57:51 为下界。来源优先采用固定提交、证据标签和基线对应的 GitHub API 结果。R4 标签仍解析到 `a9aeddbd706630808bf6a8985646c3075d673d27`，和 R4 报告里的实跑源码一致。PREVIEW 文首的 155a752 是起草和计数基线，89ae3a8 是本轮审计基线，发布提交尚未选定。

## A3 — 语义差异矩阵

| 变更 | 原义与现状 | 影响 |
|---|---|---|
| P1-h1/h2 | README 保留 draft/research baseline、不可部署与 #101 限定。协议生产使用限制、验证范围、V1 DEFERRED、ADR-0007 首轮 audit-only 及 B/Q 证据限度保留。 | 无协议对象、状态机、资金或 Gate 变化。协作报告入口新增。 |
| P1-h3/h4 | R1 规范性要求及 R4 报告范围保留。R4 的四份清单对应已完成 campaign，首次中断原样留存。P1-h4 自有差异限 Markdown 与交付清单。 | 文档字段与发布冻结步骤，无新实验保证。 |
| P1-g/i/j | 公开包经授权脱敏，现行代理文件退出交付，剧场本地化字体，许可覆盖纳入 WOFF2。 | 公共交付边界变化；历史 Git 对象、运行数据和根 LICENSE 保留。 |

## A4 — 跨文档连续性

- README 入口、PREVIEW §1 与状态页仍将 v0.5 定位为研究与规范基线。README「安全主张的当前适用范围」与 PREVIEW §7 保留固定协调器、同宿主 VM 证据级别、无许可及独立性限制。抽核 #171、#170 的对照及 #172 的修订，未发现上调生产、主网或 Gate 结论。
- PREVIEW §5/§7、current-status §9、R1 §6.6 与 R4 报告一致：每 pass 32 个带种子运行、违反 0 次、可复现。安全层 0 违反不等于全系统安全。未把固定样本写成违反概率、置信度或上界。
- OQ-01:75–79、current-status:163–165 与 PREVIEW §7/§10 已记名称决定。README:204,210 仍把名称或商标清查列为 OPEN，状态页 :63 仍列法律检索为下一项。current-status:11,17,32 也仍把已合入的 P1-g/i/j/h 写成待办。见 A9 新发现 002。
- PREVIEW §10 已区分候选文本、维护者重新冻结与 Release 权威入口。公开设置清单的 DCO 触发语句与 PREVIEW §10 的 fork 阻合并实测先后顺序需对齐，见新发现 003。

## A5 — 威胁、不变量、实现证据与理论边界

抽核 R1 检查器独立判定、预算及停止条件、R4 的固定源码和统计边界。P1-h2 对逐字节固定的 VerificationProfile Schema 已撤回改动，`make check` 中的 migration evidence 回归通过。R1 §6.6 的安全层限定保留。TG-6（#123）故障过程模型仍 OPEN，R1:306 明文登记。本轮没有利用该模型推出实测之外的保证，未发现新的理论依赖。协议威胁覆盖、规范准入和 Gate 退出不在本轮目标内。

## A6 — 历史档案与权威

从前轮基线以来，审计报告目录只新增 #162 的前轮报告，codocs 无差异。状态日志现有行保留，本轮提交增加日期行。#172 的历次审计对超出入口或结论的改动做过回退，包括 R2 2026-11-08 更正说明，最终合入未修改数据归档。#169 的授权脱敏影响十个包的 107 个串口成员；逐成员对照确认仅邮箱替换、文件库存无变化，原压缩包仍在历史提交中。历史 DCO 失败按原结果留存。LICENSE 字节与 d0bf56e 相同。

## A7 — 许可、发布与外部事实

### A7.1 凭据与个人信息

- 增量可达 172 个新增 blob 枚举；文本和非压缩对象以有限模式检查 PEM、常见平台 token、带凭据 URL 和邮箱。WOFF2 走公开交付与许可检查，证据压缩成员另扫。路径中 `task-*` 被 token 子串模式误命中，分类后未发现凭据。新增邮件形态出现在字体署名及许可声明，GitHub 文本也有署名和联络示例。报告不转录地址。
- 在 GitHub 读取更新窗口内的 issue/PR、评论和 review 项，去重后扫描 59 条正文，7 条含邮箱形态，已核对未发现凭据格式命中。范围为 API 可见正文及评论和本地已取对象，外部账户、不可见记录和未来发布提交待对应发布检查。
- 逐个打开 `docs/testing/public-evidence/` 的全部 28 个 tar.gz，共 4,285 个常规成员，邮箱与凭据模式均 0。十个 P1-g 包的实际 SHA-256 均出现在对应报告；26 份 `source-sha256.json` 以同目录 `commit.txt` 在 Git 中重算，2,324 个条目全部吻合。此为归档一致性与范围核验。对应物理实跑沿用前轮结果。

### A7.2 交付范围与第三方材料

`git ls-files -- AGENTS.md .claude` 空，DELIVERY-SCOPE 的清单不含两项。一次源码包构建与 ZIP CRC 校验通过，801 个 ZIP 成员，AGENTS.md、.claude 命中 0。审计包 SHA-256 为 `6d7703c6fc7c4e847921e25f07cba203d8ffd24644db14e70af44a85f8c2936c`，只标识这一基线的临时包。历史版本按决定保留。

theater HTML 静态检查仅见本地五个 WOFF2 URL，未见第三方 URL、外部脚本或主动网络请求入口。字体目录随附三份 OFL 全文，REUSE.toml:106–128 以 OFL-1.1 覆盖五个文件。README、PREVIEW 和第三方材料表披露 Unicode 和字体许可例外。外部材料、AI 产出权利由维护者决定。本轮未运行浏览器或进行法律判断。

### A7.3 协作入口、DCO 与线上状态

SECURITY 保留漏洞私密入口及无细节公开备援。CODE_OF_CONDUCT 与 Issue chooser 提供独立的无细节行为联络模板，涉及可能是唯一维护者的报告对象时可绕开项目渠道，对平台违规直报 GitHub。两类公开模板都禁止披露事件或漏洞细节，允许自愿留下联络方式。未实际发送报告；建议发布时让表单明确提示联络方式可被公开阅读。

| main 提交 | push DCO | 处理 |
|---|---|---|
| `bdefaff` #162 | success | API 核对 |
| `7232164` #167 | failure | 原提交消息中虽有签署文字，Git trailer 解析为空；[日志](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43899444114/job/133411763302)。见新发现 001。 |
| `e72acd3` #169 | success | API 核对 |
| `29ae739` #168 | failure | 签署前缺空行，Git 未解析为 trailer；[日志](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43911879653/job/133455647293)。 |
| `864561a` | success | 空提交，维护者补签；签署可解析。处理范围仅 29ae739，原失败保留。 |
| `3204bd7` #170 | success | API 核对 |
| `0084705` #173 | success | API 核对 |
| `7b21932` #172 | success | API 核对 |
| `89ae3a8` #171 | success | 本轮固定基线。local-validation 最后读回为 in progress。 |

仓库 API 确认当前 private，描述为「ACLt Protocol：面向异构、无许可分布式计算的开放、实现中立协议。研究与规范基线 v0.5（draft）。」topics 为 distributed-computing、fault-tolerance、permissionless、protocol、protocol-specification、research、rust、verifiable-computing。与 [020 完成记录](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6920321654) 一致。保护规则、私密报告、fork DCO 门禁留待公开后验收。

## A8 — 机械一致性

`make check` 通过，23 组 699 项。生成清单、仓库证据及链接、要求 Git 的许可覆盖和 `make verify-source` 均通过。许可覆盖 348，缺失 0。增量 `git diff --check` 退出 2，命中 8 条尾部空格：三份保留的 OFL 原文各一行，前轮归档报告文首五个 Markdown 硬换行。保留这些失败诊断与原文本。基线 [local-validation](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43924902996/job/133501657940) 最后查询仍运行中，基线 [DCO](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43924902605/job/133501655775) 通过。

## A9 — 发现与结论

### 前轮 OPEN 项逐项回验

| 编号 | 状态 | 定位与依据 |
|---|---|---|
| AUD-20261115-007 | ACCEPTED_BY_MAINTAINER | [#128 决定 1](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6920084883)，OQ-01:75–79、PREVIEW §10.1。放弃名称检索，接受同名风险，维护者不声明商标。README 同步见新发现 002。 |
| AUD-20261115-008 | OPEN | R4 #160 的证据与标签已闭合，PREVIEW §10.7–15 的最终发布提交核验由维护者执行。 |
| AUD-20261115-009 | OPEN | public-repository-settings 第 3–11 行、PREVIEW §10，转公开后实测和记录。DCO 设置顺序见新发现 003。 |
| AUD-20261115-015 | CLOSED_ON_MAIN | #169 已修前轮快照日期及“R4 下一步”问题，current-status:5,11,17,32。四个 P1-h 合入后的新入口同步见新发现 002。 |
| AUD-20261115-020 | CLOSED_ON_MAIN | GitHub repo API 描述及八个 topics 与维护者记录一致。 |
| AUD-20261115-023 | CLOSED_ON_MAIN | #128 决定 3 明确已告知外部贡献者，公开包中新出现的上游联系人按补充决定脱敏。历史提交元数据保留。 |
| AUD-20261115-024 | CLOSED_ON_MAIN | #167、Git 跟踪列表、DELIVERY-SCOPE 和实打源码包核对，历史版本按维护者决定保留。 |
| AUD-20261115-026 | OPEN | 字体子项由 #168 落地，五个本地字体、三份 OFL 文本和 REUSE 再核通过。外部材料与 AI 产出的权利决定留给维护者。 |
| AUD-20261115-027 | CLOSED_ON_MAIN | #171 的 CODE_OF_CONDUCT、缺陷/文档及联络模板已合入。英文暂缓由 #128 决定 7 接受。 |
| AUD-20261116-02-001 | CLOSED_ON_MAIN | #169，R1:306 的 §5.6 锚点包含对应标题的日期后缀。 |
| AUD-20261116-02-002 | CLOSED_ON_MAIN | #169，R4:187 写明 14 个子场景，第 172 行仍记录 13 个测试方法。 |
| AUD-20261116-02-003 | CLOSED_ON_MAIN | #169 与 #170，R4:199 和 PREVIEW:36 都限定四份清单对应四个完成 campaign，首次中断保留且无清单。 |
| AUD-20261116-02-004 | CLOSED_ON_MAIN | [#128 补充决定](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6920210856)及 #169，28 包扫描没有邮箱命中。 |
| AUD-20261106-012 | OPEN | 同 008。R4 已作为当前发布前置，选定提交后的核验待执行。 |
| AUD-20261106-017 | ACCEPTED_BY_MAINTAINER | 许可决定已记入 OQ-01、README 与 CONTRIBUTING；剩余名称检索风险由 007 的决定接受。 |

### 本轮新增发现

| 编号 | 级别及状态 | 证据、影响与处置 |
|---|---|---|
| AUD-20261116-03-001 | MAJOR / OPEN | #167 的 main squash `7232164` 缺可解析 DCO trailer，云端 push 检查与本地全增量检查均失败。已知补救 `864561a` 只指向 `29ae739`。请维护者独立确认并按不改历史的方式明确处理 #167，保留失败记录并核查补救提交的 trailer 和 CI。代理可整理证据，签署决定与执行属于维护者。 |
| AUD-20261116-03-002 | MINOR / OPEN | README:204,210 与 OQ-01:75–79、PREVIEW §7/§10.1 的名称决定不同步。current-status:11,17,32 仍把已合入的 P1 清理列作后续，:63 的现行名称摘要仍列检索。请用小型文档条目同步入口，保留历史日志。该发现不重新打开 007 的名称检索决策。 |
| AUD-20261116-03-003 | MINOR / OPEN | public-repository-settings:5 提到观察到检查名称后要求 DCO，PREVIEW §10 要求先用 fork PR 验证缺签阻合并、补签后的最新头通过。公开设置清单应引用这个时序，避免把看到检查名称当作配置完成。 |
| AUD-20261116-03-004 | NOTE / OPEN | 增量 diff 格式检查退出 2。8 条诊断均定位于原样收录的 OFL 文本或归档 Markdown 的硬换行。发布检查记录这个边界，保留原许可与归档字节。 |

新增 **0 BLOCKER、1 MAJOR、2 MINOR、1 NOTE**。前轮原编号事项与发布门禁另列。

| 维度 | 结果 | 理由 |
|---|---|---|
| 语义连续性 | PASS（协议限域） | 规范义务、R4 统计口径和测试结论维持；发布状态文字有独立发现。 |
| 目标 Gate 退出 | NOT_ASSESSED | #161 范围为发布准备。 |
| 结构完整性 | FAIL | 跨文档的公开入口与设置步骤不同步；增量格式检查退出 2。 |
| 历史隔离 | PASS | 历史文件、运行数据和失败记录保留；P1-g 脱敏按明确授权且可核对。 |
| 发布准备 | FAIL | #167 DCO 补救待决定，基线 CI 未读到成功，发布提交及线上检查尚待执行。 |

**代理侧剩余事项。** 另开文档同步条目处理 002、003，修订后定向复核。复核 #167 的维护者处理记录和候选提交上的 CI。当前尚有未完成的代理侧发布准备工作。

**维护者侧剩余事项。** 决定并处理 #167 DCO。冻结前确认发布文案同步及 026 的外部材料权利处理，重新冻结 PREVIEW，选定发布提交，在该提交上重扫凭据、按 PREVIEW §10 复跑完整测试、来源和归档检查、做源码包对拍并核对 GitHub CI。转公开后落实 009 的设置并用 fork PR 实测 DCO 门禁。决定 025 的标签是否签名，然后打标签、创建 Release 并核对发布资产与摘要。

**允许开展。** 将本报告交 dsh 入库，登记后续文档修订与 DCO 处置；准备维护者发布检查及复核。

**禁止宣称。** 当前已通过发布准备、历史 DCO 全通过、自动 fork 门禁已实测、名称可用或权利审查完成。不得据此宣称任何 Gate 退出、生产就绪、统计独立或全系统安全。

## A10 — 交付、限制与审计签署

交付中文报告、report.sha256 和 summary.txt，供 dsh 按独立入库流程交付。建议落点为 `docs/08-governance/audits/audit-20261116-03-public-release-recheck.md`，后续索引、日志和交付清单归入库会话。Codex 签署本轮只读结论。无修订、提交、推送、PR、标签或仓库设置变更。

## 附录：命令与退出码

| 编号 | 命令或类别 | 退出码 | 结果 |
|---|---|---|---|
| M1 | 临时 bare clone、远端 fetch 主线和 evidence tags、`git worktree add --detach`、`git rev-parse`、`git status --porcelain` | 0 | 89ae3a8，初始与结束均干净。 |
| M2 | GitHub issue/PR/评论、review、repo、提交 check-runs 及 DCO 两次失败日志读取 | 0（显式设定 GH_REPO 后） | 初次 gh 上下文选择因临时副本远端为本地路径退出 1，随后指定仓库读取成功。 |
| M3 | `git rev-list --objects d0bf56e..HEAD`、`git cat-file`、有界凭据及邮箱模式、GitHub 正文增量扫描 | 0 | 172 个新增 blob、59 条正文；扫描覆盖见 A7。 |
| M4 | Python tar 成员扫描并对照旧包、报告摘要、固定提交源清单 | 0 | 28 包、4,285 成员，十包重打、107 成员替换，26 份清单、2,324 项匹配。 |
| M5 | `git ls-files`、DELIVERY-SCOPE 检查、`python3 -B scripts/package-singlehost.py <临时 ZIP>`、ZIP CRC/成员扫描 | 0 | 801 个成员，未包含两项代理文件。 |
| M6 | `make check` | 0 | 23 组，699 项。 |
| M7 | `python3 -B scripts/update-manifests.py --check`、`python3 -B scripts/check-repository-evidence.py --repository .`、`python3 -B scripts/check-license-coverage.py --require-git`、`make verify-source` | 0 / 0 / 0 / 0 | 清单、链接、许可覆盖、证据来源通过。 |
| M8 | `git diff --check d0bf56e..HEAD` | 2 | 保留 8 行诊断，见 A8。 |
| M9 | `git interpret-trailers --parse`；`git diff-tree --no-commit-id --name-only -r 864561a`；`scripts/check-dco.py push --before d0bf56e --after HEAD` | 0 / 0 / 1 | 864561a 是可解析签署的空提交，整个范围仍复现两个原始失败提交。 |
| M10 | 基线 check-runs 最后读取；`git status --porcelain`、`git worktree remove`、`git worktree list --porcelain` | API 0；状态 0；移除成功；列表首次 128、换目录后 0 | 首次列表仍从已删除的工作目录调用，换到外部目录核验清理成功。 |
