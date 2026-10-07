# ACLt Markdown 维护报告

> 报告状态：`RESOLVED_IN_PREPARED_CHANGE`  
> 审计编号：`AUDIT-20261007-01`  
> 类别：文档变更维护与机械检查  
> 日期与时区：2026-10-07，Europe/Budapest（UTC+02:00）  
> 审计者：Codex  
> 程序：[`audit-procedure.md`](../audit-procedure.md)  
> 仓库：`/home/tenneidp/Documents/ACLt/ACLt`，分支 `main`  
> 完整基线：`5e8263ae48aee30b7219275ddbf3686ff802374e`

## 1. 目标、授权与范围

依据用户本次维护全部 Markdown 的指令，盘点原有 74 份 Markdown，检查结构、文件链接、日期和当前工程入口；仅修订有明确本地证据的过期说明。初始工作区干净。在隔离副本准备和回验，再申请文件系统许可复制修订；不提交、推送或合并，不修改协议规则、决定日期、历史正文或原测试证据。

## 2. 时间戳与来源

README、文档索引、当前状态和待决问题的页首日期仍停在 8 月，正文已经包含 10 月证据。本轮实际更新这些入口及 workflow，日期为 2026-10-07。未变化文件不刷新日期；历史审计、codocs、旧实验和历史示例保持原文及原日期。2026-10-03 集成证据的 Europe/Vienna 原时区保留。决定日期与最后复审日期未修改。

## 3. 变化与连续性

| 发现 | 等级 | 修订 | 状态 |
|---|---|---|---|
| AUD-20261007-001 | MINOR | 首页补工程目录和证据入口；语义目录树标为节选 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261007-002 | MINOR | 当前状态事实表、G2 行和问题队列同步 state3；局部实验已存在，完整 Gate 未通过 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261007-003 | MINOR | workflow 当前测试数量从 19 改为 22；明确历史集成与本轮测试的日期 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261007-004 | MINOR | 实际修改的持续更新文档同步页首日期；新增工程文档索引 | RESOLVED_IN_PREPARED_CHANGE |

本轮没有对象、函数、状态机、权限或资金语义变更，故不新增 ADR。SemanticStatus、V1 VersionDisposition、P0-1A 关闭与 P0-1B 未关闭保持。没有新增威胁、不变量或证明义务。原有规范与历史材料的正文摘要不会替代其权威来源。

## 4. 证据及保留问题

[集成报告](../../testing/INTEGRATION-FIX.md)与其 JSON 摘要记录 265 场景、13 项模型、24 项验证配置、22 项流程测试；这是 2026-10-03 的已存证据，本轮没有重新执行全部单机实验、内存检测或验证数学模型。2026-10-07 在隔离副本运行 `python3 -B -m unittest discover -s tests/workflow -v`，22 项通过；修改前及修改后各运行一次，修改后先刷新校验清单。

仍保留集成报告中的三语言 reducer 对拍、更多变异、临时结果清理、输出/数值规范化和规模性能问题。日志忠实性、实际部署 assurance、资金/结算和 RIR/RPR 证据仍不足；局部测试不改变威胁—不变量—证明义务的关闭状态。

## 5. 机械检查与历史隔离

原 74 份及新增本报告共 75 份 Markdown 检查单一 H1、代码围栏配对、Markdown 内相对文件链接存在性。文件链接检查不包含 URL 可用性和页内锚点。历史文件的哈希与基线比较保持不变。当前入口一致指向 state3。规范 ID 定义及登记未修改，DP-01—17、INV-01—16、OQ-01—14 和 ADR-0001—0005 保持；全协议追踪覆盖完整性未重新证明。校验清单按仓库脚本更新并由现有集成测试回验。

## 6. 结论与限制

> 语义连续性：`PASS`（限本轮无协议语义变更的修订）；目标 Gate 退出：`NOT_ASSESSED`；结构完整性：`PASS`（限上述机械检查）。  
> 允许开展：沿用当前工程入口继续局部测试及未决问题收敛。  
> 禁止宣称：P0-1B 关闭、G0/G2 退出、整体安全或生产就绪。

历史隔离：`PASS`；发布准备：`NOT_ASSESSED`。本轮是维护审计，A5 以无状态转换变更为边界，A7 仅保留现有许可证陈述；未重新审计法律、名称或外部事实，也未更新这些陈述。未执行全协议语义、部署或发布审计；这项范围缩减依用户维护请求确定，不把机械检查当作完整安全审计。无人工技术签署或合入批准。

## 7. 修订、目录映射与交付

更新包在隔离目录生成，仅含变更文件、报告和两份交付校验清单；SHA-256 与完整性结果在独立交付 JSON 中记录，避免报告与包哈希循环。逐文件 SHA-256 在独立清单中记录。仓库源代码、历史证据、缓存、凭据和本机测试产物不进入更新包。本地文件修改尚未合入主分支，不标记 CLOSED_ON_MAIN。

| 原路径/目标路径（仓库相对） | 处理 |
|---|---|
| `CONTRIBUTING.md` | 未变化；结构、文件链接检查 |
| `README.md` | 修改 |
| `docs/00-overview/architecture-guide.md` | 未变化；结构、文件链接检查 |
| `docs/00-overview/design-principles.md` | 未变化；结构、文件链接检查 |
| `docs/00-overview/project-overview.md` | 未变化；结构、文件链接检查 |
| `docs/00-overview/system-context.md` | 未变化；结构、文件链接检查 |
| `docs/00-overview/terminology.md` | 未变化；结构、文件链接检查 |
| `docs/01-requirements/invariants.md` | 未变化；结构、文件链接检查 |
| `docs/01-requirements/threat-model.md` | 未变化；结构、文件链接检查 |
| `docs/02-architecture/identities-and-roles.md` | 未变化；结构、文件链接检查 |
| `docs/02-architecture/system-architecture.md` | 未变化；结构、文件链接检查 |
| `docs/02-architecture/task-lifecycle.md` | 未变化；结构、文件链接检查 |
| `docs/03-protocol/protocol-spec.md` | 未变化；结构、文件链接检查 |
| `docs/03-protocol/reputation.md` | 未变化；结构、文件链接检查 |
| `docs/03-protocol/result-validation.md` | 未变化；结构、文件链接检查 |
| `docs/03-protocol/v1-profile.md` | 未变化；结构、文件链接检查 |
| `docs/03-protocol/verification-profile-schema.md` | 未变化；结构、文件链接检查 |
| `docs/04-analysis/administrative-cost.md` | 未变化；结构、文件链接检查 |
| `docs/04-analysis/robustness.md` | 未变化；结构、文件链接检查 |
| `docs/05-decisions/ADR-0001-no-unnecessary-entities.md` | 未变化；结构、文件链接检查 |
| `docs/05-decisions/ADR-0002-normative-rir-and-v1-rust-profile.md` | 未变化；结构、文件链接检查 |
| `docs/05-decisions/ADR-0003-separate-semantic-status-and-version-disposition.md` | 未变化；结构、文件链接检查 |
| `docs/05-decisions/ADR-0004-verification-profiles-and-finite-population-e-process.md` | 未变化；结构、文件链接检查 |
| `docs/05-decisions/ADR-0005-engineering-assumptions-and-mainnet-assurance.md` | 未变化；结构、文件链接检查 |
| `docs/06-research/claims-and-sources.md` | 未变化；结构、文件链接检查 |
| `docs/06-research/last-two-problem-trees.md` | 未变化；结构、文件链接检查 |
| `docs/06-research/verification-round-mathematical-model.md` | 未变化；结构、文件链接检查 |
| `docs/07-roadmap/current-status.md` | 修改 |
| `docs/07-roadmap/open-questions.md` | 修改 |
| `docs/08-governance/audit-procedure.md` | 未变化；结构、文件链接检查 |
| `docs/08-governance/audit-report-template.md` | 未变化；结构、文件链接检查 |
| `docs/08-governance/audits/audit-20260818-01-semantic-structure.md` | 未变化；结构、文件链接检查 |
| `docs/08-governance/audits/audit-20260819-02-verification-model-closure.md` | 未变化；结构、文件链接检查 |
| `docs/08-governance/audits/audit-20260819-03-submission-scope.md` | 未变化；结构、文件链接检查 |
| `docs/08-governance/audits/audit-20260821-04-engineering-closure-rollout.md` | 未变化；结构、文件链接检查 |
| `docs/08-governance/audits/audit-20260821-10-p0-1a-independent-entry.md` | 未变化；结构、文件链接检查 |
| `docs/README.md` | 修改 |
| `docs/codocs/README.md` | 未变化；结构、文件链接检查 |
| `docs/codocs/v0.3/RUDCP_Public_Argument_Proof_Obligations_and_Project_Structure_v0.3_EN.md` | 未变化；结构、文件链接检查 |
| `docs/codocs/v0.3/RUDCP_公开论证链与项目结构_v0.3_中文.md` | 未变化；结构、文件链接检查 |
| `docs/codocs/v0.4/RUDCP_Complete_Project_Architecture_and_Argument_Mapping_v0.4_EN.md` | 未变化；结构、文件链接检查 |
| `docs/codocs/v0.4/RUDCP_完整项目思路架构与论证映射_v0.4_中文.md` | 未变化；结构、文件链接检查 |
| `docs/codocs/v0.5/ACLt_v0.5_Unresolved_Issues.md` | 未变化；结构、文件链接检查 |
| `docs/codocs/v0.5/DCP_Complete_Project_Architecture_Argument_and_Traceability_v0.5_EN.md` | 未变化；结构、文件链接检查 |
| `docs/codocs/v0.5/DCP_完整项目思路架构与论证映射_v0.5_中文.md` | 未变化；结构、文件链接检查 |
| `docs/testing/INTEGRATION-FIX.md` | 未变化；结构、文件链接检查 |
| `docs/testing/SINGLEHOST-REPORT.md` | 未变化；结构、文件链接检查 |
| `docs/workflow/README.md` | 修改 |
| `docs/workflow/example/ACLT-PROGRESS.md` | 未变化；结构、文件链接检查 |
| `experiments/README.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier/README.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier/docs/BATCH-REPORT.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier/docs/NEXT-TEST.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier/docs/RECOVERY-REPORT.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier/docs/STAGE-REVIEW.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier/docs/TEST-REPORT.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state2/README.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state2/docs/BATCH-REPORT.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state2/docs/LIFECYCLE-REPORT.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state2/docs/NEXT-TEST.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state2/docs/RECOVERY-REPORT.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state2/docs/STAGE-REVIEW.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state2/docs/TEST-REPORT.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state3/README.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state3/docs/BATCH-REPORT.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state3/docs/LIFECYCLE-REPORT.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state3/docs/NEXT-TEST.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state3/docs/RECOVERY-REPORT.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state3/docs/SINGLEHOST-NOTES.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state3/docs/STAGE-REVIEW.md` | 未变化；结构、文件链接检查 |
| `experiments/aclt-minimal-verifier-state3/docs/TEST-REPORT.md` | 未变化；结构、文件链接检查 |
| `schemas/verification-profile/README.md` | 未变化；结构、文件链接检查 |
| `tests/verification_model/README.md` | 未变化；结构、文件链接检查 |
| `tests/verification_profile/README.md` | 未变化；结构、文件链接检查 |
| `docs/08-governance/audits/audit-20261007-01-markdown-maintenance.md` | 新增本报告 |
| `WORKFLOW-SHA256SUMS` | 同步交付哈希 |
| `SINGLEHOST-SHA256SUMS` | 同步交付哈希 |
