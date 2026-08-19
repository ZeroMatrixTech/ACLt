# ACLt 语义结构与 G0 连续性审计报告

> 报告状态：`COMPLETE_LOCAL_PREPARED_CHANGE`
> 审计编号：`AUDIT-20260818-01`
> 审计类别：语义连续性审计、文档变更审计、G0 Gate 退出审计
> 审计日期与时区：2026-08-18T20:05:51+02:00
> 审计者：Codex（本地修订与审计执行）
> 程序版本：[`../audit-procedure.md`](../audit-procedure.md)
> 仓库与基线：`tenneidp/ACLt`，`main`
> 完整 commit SHA：`83ac52597991ec394228e55c0fa9d8eddebd4681`
> 后续处置：本报告覆盖的 23 个文件已由 PR #23 合入 `main`，提交 `a99e344f29f58e61a22c1d0c1b304fd9191c6295`；本文件作为该次审计的历史记录补交

## 1. 审计目标与权限

| 项目 | 内容 |
|---|---|
| 目标 | 将 SemanticStatus 与 VersionDisposition 二维分离落入仓库；保守闭合可由现有决定支持的 Abstract Machine、Logical Object、Compile、RPR 和 Dispatch 边界；重新判断 G0 |
| 范围 | 根 README/CONTRIBUTING、`docs/00` 至 `docs/08` 的现行 Markdown、根 LICENSE、相关 ADR/TH/INV/CLM/OQ/PO 与 V1 Profile |
| 排除范围 | 不修改 `docs/codocs` 历史正文；不创建实现、Schema、测试或仿真；不执行名称/商标法律检索；不证明统计定理 |
| 允许的只读操作 | Git 状态、提交、差异、文件盘点、全文检索、链接/标题/围栏/ID/FeatureKey 检查 |
| 是否允许准备本地修订 | 是；用户明确授权落实到本地仓库 |
| 禁止的仓库写操作 | 不提交、不推送、不创建分支、不创建 Pull Request、不修改远端 |
| 偏离记录 | 无 |

## 2. 基线与文件盘点

| 类型 | 数量或路径 | 备注 |
|---|---|---|
| 当前规范/文档 | 27 个现行 Markdown（含本报告；不含 `codocs`） | 根 2 个；`docs/` 25 个 |
| 历史文档 | `docs/codocs/` 共 9 个文件，其中 8 个 Markdown、1 个 DOCX | 全部只读复核，未修改 |
| 实现与测试 | 0 | `spec/`、`simulations/` 和 reference implementation 尚不存在 |
| 许可证与发布文件 | 根 `LICENSE` 1 个；无 NOTICE | Apache License 2.0 正文未修改 |
| 新增 | 3 | V1 Profile、ADR-0003、本审计报告 |
| 修改 | 21 | README/CONTRIBUTING 及跨文档同步链 |
| 删除 | 0 | 无历史或当前文件删除 |
| 未变化但已复核 | ADR-0001、审计程序、审计模板、LICENSE、`codocs` 索引/档案 | 不属于本轮语义修订目标 |

新增文件：

- `docs/03-protocol/v1-profile.md`；
- `docs/05-decisions/ADR-0003-separate-semantic-status-and-version-disposition.md`；
- `docs/08-governance/audits/audit-20260818-01-semantic-structure.md`。

## 3. 时间戳与来源

| 对象 | 原时间/时区 | 审计确认时间/时区 | 处理 |
|---|---|---|---|
| 基线 commit | 2026-08-19T01:34:44+08:00 | 2026-08-18T19:42:54+02:00 拉取确认 | 记录完整 SHA；未改写提交时间 |
| 用户接受二维模型 | 2026-08-18；精确时间未独立记录 | 2026-08-18T20:05:51+02:00 | 作为本轮明确决定写入 ADR-0003 |
| 本轮现行文档 | 2026-08-18 | 2026-08-18T20:05:51+02:00 | 更新内容但不伪造更早决定时间 |
| `docs/codocs` 历史材料 | 各历史文件原时间 | 2026-08-18T20:05:51+02:00 | 未修改正文和时间戳 |

## 4. 语义差异矩阵

| Change ID | 触发依据 | 之前 | 之后 | 影响对象/函数 | DP/TH/INV/ADR/CLM/OQ/PO | Gate | 同步文件 |
|---|---|---|---|---|---|---|---|
| CHG-001 | 用户接受二维分存 | 成熟度、Priority、DEFERRED 可被紧凑字符串混用 | SemanticStatus 与 VersionDisposition 分离；Qualifier/Priority/IssueStatus 独立 | ProtocolVersion、ConformanceTarget、状态登记 | TH-02；INV-02/16；ADR-0003；OQ-02 | G0 | terminology、docs index、current status、claims、contributing |
| CHG-002 | V1 需要唯一能力范围 | V1 排除项分散在 ADR/overview | 新建唯一 `FeatureKey → VersionDisposition` Profile | V1 Profile、conformance claim | ADR-0002/0003；OQ-02/14 | G0/G2 | v1-profile、README、protocol、roadmap |
| CHG-003 | 会话冻结的机器模型 | 无 ACLt Abstract Machine/Logical Object 权威定义 | 冻结对象驱动机器、无共享地址空间、不可变显式对象边界 | Abstract Machine、Logical Object | DP-03/16；TH-01/14/34；INV-01/09/16；CLM-108；OQ-02/05；PO-12 | G0/G2/G4 | overview、architecture、protocol、requirements、analysis |
| CHG-004 | Compile 语义缺失 | Plan 泛化，lowering/拆分/打包边界不清 | `Compile = Lowering + Decomposition + Packing` | Compile、Plan、WorkPlan、Assignment | DP-01/03/16；TH-04/33；INV-01/09/16；CLM-108；OQ-04；PO-13 | G0/G2 | terminology、architecture、lifecycle、protocol、threat、analysis |
| CHG-005 | RIR 与 Host OS 边界缺失 | runtime 为泛称 | RPR default-deny Host OS capability；禁止隐藏状态和 native fallback | RPR、Host OS、ExecutionProfile | DP-03/10/16；TH-14/34/35；INV-01/09/16；OQ-05；PO-11/12 | G0/G2 | overview、architecture、protocol、requirements、analysis |
| CHG-006 | Provider dispatch 语义缺失 | Schedule/Lease 接受存在但未形成完整边界 | proposal 不产生义务；Provider accept 后 active Lease 生效；传输中立 | Admit、Schedule、Lease、Provider | DP-02/09/10；TH-10/11/28；INV-03/08/09/10；OQ-04/05；PO-02/13 | G0/G2/G3 | context、architecture、lifecycle、protocol、roles、threat |
| CHG-007 | Bayesian 与仓库 anytime-valid 路线冲突 | 只列 anytime-valid 候选；Bayesian 仅零散出现 | exact evidence + Bayesian stop proposal + anytime-valid safety envelope 候选 | VerificationProfile、Snapshot、Aggregate | DP-04/05/07/08；TH-15—20；INV-10—12/14；CLM-003/004/109；OQ-06—08；PO-04/05/14 | G0/G1 | validation、terminology、threat、claims、robustness、roadmap |
| CHG-008 | 权威与资金边界需要显式落到新模型 | 原原则已存在但 FoundationReport 未作为类型写明 | 历史能力、付款和 FoundationReport 不进入真理权重；FundingPolicy 不证明 correctness | CapabilityEstimate、VerificationEvidence、FundingPolicy | DP-07/11/12；TH-09/22/30；INV-06/14/15；OQ-10/13；PO-09/10 | G0/G2 | principles、protocol、reputation、invariants、analysis、V1 Profile |

## 5. 连续性核查

| 核查面 | 权威文件 | 结果 | 冲突或证据 |
|---|---|---|---|
| Overview / terminology | `docs/00-overview/*` | PASS | 两维定义、机器/对象/RPR/Compile/Dispatch 术语一致 |
| ADR | ADR-0001/0002/0003 | PASS | ADR-0003 不改变 Principal 或 RIR 既有决定；ADR-0002 已连接 V1 Profile |
| Threat model | `threat-model.md` | PASS | TH-01/02/04/10/14/19/34 覆盖新边界 |
| Invariants | `invariants.md` | PASS | INV-01/02/14/15/16 已同步；未伪造形式化完成 |
| Architecture / protocol | `system-architecture.md`、`task-lifecycle.md`、`protocol-spec.md`、`v1-profile.md` | PASS | 唯一职责和失败关闭边界一致 |
| Analysis / claims | `robustness.md`、`administrative-cost.md`、`claims-and-sources.md` | PASS | 新增 CLM-108/109、PO-12—14；组合安全保持候选 |
| Current status / open questions | `current-status.md`、`open-questions.md` | PASS | 已决定边界与仍开放证据分别列出 |
| Gate definitions | README、current status、invariants | PASS | G0 仍进行中；CORE 不被写成完成 |
| Prohibited claims | README、V1 Profile、threat、invariants | PASS | 51%、真理权、隐藏宿主状态、静默回退和维护覆盖均禁止 |

## 6. 威胁—不变量—实现证据

| Threat | Invariant | 函数/状态转换 | Proof obligation | Test/conformance | 状态 |
|---|---|---|---|---|---|
| TH-02 | INV-02/16 | version/profile resolution | ContractTuple 与 V1 registry join | 未建立 machine-readable registry | `OPEN/BLOCKER` |
| TH-01/34 | INV-01/09/16 | Object publish → RPR Execute | PO-12；对象身份与隐藏宿主输入隔离 | Schema、vectors、RPR 负例均未建立 | `OPEN/BLOCKER` |
| TH-04/33 | INV-01/09/16 | Lowering → Decomposition → Packing | PO-13；语义保持与权限不扩大 | TaskGraph、golden/differential tests 未建立 | `OPEN/BLOCKER` |
| TH-10/28 | INV-03/08/09/10 | proposal → accept → active Lease | PO-02/13；竞态与旧 epoch 隔离 | 可执行状态机和竞态测试未建立 | `OPEN/BLOCKER` |
| TH-15—20 | INV-10—12/14 | Snapshot → Sample → Verify → Aggregate | PO-04/05/14；Bayesian/anytime 组合有效 | 定理、prior sensitivity、仿真未建立 | `OPEN/BLOCKER` |
| TH-09/30 | INV-14/15 | capability/report → exposure only | PO-09；权威旁路不可达 | 权限 Schema 和负例未建立 | `OPEN/BLOCKER` |
| TH-22—24 | INV-05—07/12 | terminal → entitlement → Settle | PO-10；守恒和 at-most-once | 结算矩阵与故障注入未建立 | `OPEN/BLOCKER` |

孤立项、缺失证据和无法保持不变量的路径：

- 目前只有自然语言状态转换，没有 machine-readable Abstract Machine；
- V1 Profile 有 38 个唯一 FeatureKey，但尚无可执行 registry 和 conformance runner；
- 没有 Schema、validator、reference RPR、测试或仿真实现；
- Bayesian/anytime 双层验证没有 ACLt 特定组合定理；
- 相关性、最大损失、资金退款和发布撤销仍无完整证明或状态矩阵。

## 7. 历史、许可与外部事实

| 项目 | 事实 | 当前陈述 | 结果/处理 | 来源 |
|---|---|---|---|---|
| 历史权威性 | `docs/codocs` 含旧 RUDCP/DCP/Rank/51% 等材料 | 只作历史追踪，不构成当前规范 | PASS；未修改历史正文 | `docs/codocs/README.md` |
| LICENSE / SPDX | 根 LICENSE 是 Apache License 2.0 正文 | 只覆盖代码与参考实现的项目许可决定 | PASS；文件未修改 | 根 `LICENSE`、OQ-01 |
| NOTICE / 第三方许可 | 当前无 NOTICE 和实现依赖 | 按需建立 | NOTE；公开发布前继续跟踪 | OQ-01 |
| 名称与商标 | ACLt 是当前工作名称 | 未完成外部权利清查 | OPEN；本次未作法律判断 | terminology、OQ-01 |
| 其他外部事实 | 本次没有新增需要网络核实的安全事实 | Bayesian 组合只登记为 ACLt 候选 | PASS；没有把外部先例写成 ACLt 证明 | claims registry |

## 8. 发现项

| Finding ID | 等级 | 状态 | 证据位置 | 影响 | 必需处理 |
|---|---|---|---|---|---|
| `AUD-20260818-001` | MAJOR | `RESOLVED_IN_PREPARED_CHANGE` | ADR-0003、terminology、docs index | 成熟度、版本范围和优先级可能混淆 | 两维分存；Qualifier/Priority/IssueStatus 独立 |
| `AUD-20260818-002` | MAJOR | `RESOLVED_IN_PREPARED_CHANGE` | `v1-profile.md` | V1 能力边界分散，无法机械盘点 | 建立唯一 Profile 和稳定 FeatureKey |
| `AUD-20260818-003` | MAJOR | `RESOLVED_IN_PREPARED_CHANGE` | architecture、protocol、lifecycle | Abstract Machine、Logical Object、RPR、Compile、Dispatch 缺少共同边界 | 已闭合概念职责与禁止行为；形式证据转入阻断项 |
| `AUD-20260818-004` | BLOCKER | `OPEN` | OQ-02/04/05/11；PO-01/02/11—13 | V1 CORE 无 machine-readable Schema、状态机、RIR/RPR/Compile/Dispatch conformance | 完成 Schema、validator、状态模型、vectors 和至少两个可比较实现 |
| `AUD-20260818-005` | BLOCKER | `OPEN` | result-validation；OQ-06/07；PO-04/14 | Bayesian/anytime 组合无统计目标、prior 和定理 | 给出组合证明或反例；失败时退回更保守 Profile |
| `AUD-20260818-006` | BLOCKER | `OPEN` | OQ-08；PO-05 | 相关集群、未知相关性和最大损失无校准 | 定义观测、隐私、折减、硬上限与敏感性/攻击仿真 |
| `AUD-20260818-007` | BLOCKER | `OPEN` | OQ-10；PO-10 | terminal—fault—fee—refund—settlement 矩阵不存在 | 建立守恒模型、唯一权利和故障/舍入/资不抵债测试 |
| `AUD-20260818-008` | BLOCKER | `OPEN` | invariants §24、protocol §18 | INV-01—16 仍无完整机器谓词与测试 | 建立 Threat→Invariant→Function→PO→Test 双向登记 |
| `AUD-20260818-009` | MAJOR | `OPEN` | OQ-01/13 | 规范/文档许可、贡献机制、名称权利和发布撤销不完整 | 公开发布前完成政策、外部检索和发布/撤销流程 |

## 9. 机械检查结果

| 检查 | 预期 | 实际 | 结果 |
|---|---|---|---|
| 每份 Markdown 一个 H1 | 27 个文件各 1 个 | 27/27 | PASS |
| fenced code blocks | 成对 | 0 个奇数文件 | PASS |
| 相对链接 | 全部存在 | 0 个断链 | PASS |
| 文件与索引 | 一致 | README、docs index、V1 Profile、审计路径一致 | PASS |
| 追踪编号与计数 | 唯一且符合登记 | DP 16、TH 35、INV 16、ADR 3、CLM 19、OQ 14、PO 14、Gate 7 | PASS |
| V1 FeatureKey | 唯一 | 38/38 唯一 | PASS |
| 过期短语 | 0 个未解释冲突 | 旧紧凑状态只在 ADR-0003 的迁移背景或明确禁止示例中出现 | PASS |
| 临时/敏感文件 | 0 | 0 | PASS |
| 压缩包完整性 | 通过 | 23 个源修订文件；逐项读取成功 | PASS |

机械检查通过不表示 G0 退出。

## 10. 审计结论

> 语义连续性：`PASS`；G0 退出：`FAIL`；结构完整性：`PASS`。
> 允许开展：G0 内的 machine-readable registry、Schema、RIR/RPR、状态机、golden vectors、差分 conformance、验证证明和仿真准备。
> 禁止宣称：G0 已关闭、G1 已完成、V1 已实现、Bayesian/anytime 验证安全已证明、ACLt 整体鲁棒或生产就绪。

| 维度 | 结果 | 依据 |
|---|---|---|
| 语义连续性 | `PASS` | CHG-001—008 已同步全部权威链；无已知未登记语义冲突 |
| 目标 Gate | `FAIL` | AUD-20260818-004—008 为 G0 BLOCKER |
| 结构完整性 | `PASS` | H1、围栏、链接、路径、ID、FeatureKey 检查通过 |
| 历史隔离 | `PASS` | `codocs` 未修改且当前入口明确隔离 |
| 发布准备 | `NOT_ASSESSED` | 本轮未进行名称/商标、文档许可和发布流程外部核验 |

## 11. 偏离、限制与残余风险

- 程序偏离：无。
- 无法取得的证据：不存在实现、Schema、测试、仿真、统计证明和外部法律意见。
- 已接受风险：无；全部不能闭合的 P0 作为 OPEN/BLOCKER 保留。
- 尚待外部判断：名称/商标、规范/文档许可、贡献机制和未来组织形式。
- 下一次审计触发条件：任一 BLOCKER 形成 Schema、定理、状态机、测试或 ADR；V1 Profile 发生处置变化；准备退出 G0。

## 12. 修订与交付

| 目标目录 | 文件 | 操作 | Finding ID |
|---|---|---|---|
| 根目录 | README.md、CONTRIBUTING.md | 修改 | AUD-20260818-001—003 |
| `docs/00-overview` | design-principles、project-overview、system-context、terminology | 修改 | AUD-20260818-001—003 |
| `docs/01-requirements` | threat-model、invariants | 修改 | AUD-20260818-003—008 |
| `docs/02-architecture` | identities-and-roles、system-architecture、task-lifecycle | 修改 | AUD-20260818-003/004 |
| `docs/03-protocol` | protocol-spec、reputation、result-validation | 修改 | AUD-20260818-003—008 |
| `docs/03-protocol` | v1-profile.md | 新增 | AUD-20260818-002 |
| `docs/04-analysis` | administrative-cost、robustness | 修改 | AUD-20260818-003—009 |
| `docs/05-decisions` | ADR-0002 | 修改 | AUD-20260818-001—003 |
| `docs/05-decisions` | ADR-0003 | 新增 | AUD-20260818-001/002 |
| `docs/06-research` | claims-and-sources | 修改 | AUD-20260818-003/005 |
| `docs/07-roadmap` | current-status、open-questions | 修改 | AUD-20260818-001—009 |
| `docs` | README.md | 修改 | AUD-20260818-001/002 |
| `docs/08-governance/audits` | 本报告 | 新增 | 全部 |

- 更新包文件名：`aclt-audit-20260818-01-update.zip`
- 文件数量：23 个源修订文件；审计报告独立保存，不进入更新包
- SHA-256：`d4a4ee62480d11dcbf4aca2cd36f9ccc604e91a2c6f06883e31172be0cde40fc`
- 未包含但已复核的文件：ADR-0001、audit-procedure、audit-report-template、LICENSE、`docs/codocs/` 全部档案
- 故意排除的文件：缓存、渲染图、工作环境元数据、`.git`、历史正文
- 仓库写操作：只准备本地修订；未提交、未推送、未创建分支或 PR
- 回验结果：A2–A10 已执行；压缩包含 23 个预期文件、可逐项读取，临时打包目录已清理

## 13. 审计签署

| 角色 | 名称 | 日期 | 结论 |
|---|---|---|---|
| 审计者 | Codex（本地执行） | 2026-08-18 | 语义连续性 PASS；G0 FAIL；结构 PASS |
| 技术复核 | 待项目合作者 | — | 待复核 |
| PR/合入批准 | 待授权流程 | — | 未执行 |
