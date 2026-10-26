# FM-F0 收尾：流程、命名和路线决定

日期：2026-10-26（Europe/Budapest）；基线 `f5f415f7c65952adba01f7b0c9f21d554b14c264`。

## 已完成

- [B/Q PR #58](https://github.com/ZeroMatrixTech/ACLt/pull/58) 已合并；浏览器可见成功状态及合并提交。用户完成 fetch 后，本地 main/origin/main 与该 SHA 一致，从此基线建立正式迁移文档分支。
- 原四份未提交草案只读取自 `store` stash `f0952ea913143a4c0e2c10ffc64bb8fcdc09489c`，F0 提交时 stash 保留且未 pop/drop；随后按维护者要求完成[整合与清理](STORE-INTEGRATION-20261026.md)，原字节另存备份。旧 tracked 草案段落不覆盖新 main，以当前文字和必要更正同步。
- 正式迁移统一用 FM；plan/traceability/F0 报告去掉 work4，验收编号改为 FM-A01～12。BQ-WORK4 保留原名和证据，已提交历史不重写。
- 维护者明确接受 ADR-0007 的六项首轮路线；字段/tag/envelope/矩阵、代码与部署分别保留门槛。接受决定不以 make check 成功替代。
- 修正 audit-only 不使用 EligibilitySnapshot、无 B/Q 参数/活性 claim，与 bounded 参数互斥；AssumptionStateSnapshot 不混用。终态沿用现行 DecisionMapping/ResolveBoundary，不另立墙钟优先规则。
- 补齐 INV-07 的终态、冻结政策、匹配资金、合法权利、未消费键五项要求；幂等同内容取原结果，异内容冲突。
- 路线接受与实现门槛解耦，去掉“必须先做完实现才能接受路线，同时又必须先接受路线才能实现”的循环。ADR-0006 仍 PROPOSED，其 §11/§13 条件不放宽。

## FM-S1a 交接

下一次直接按[实施入口](../07-roadmap/formal-migration-plan.md)做共享编码与最小角色签名代码/向量；D-1～D-6 唯一决定源为 [ADR-0007](../05-decisions/ADR-0007-formal-object-migration-foundation.md)。不再新增总规划或重复决定表。具体字段/签名 padding/输入/上下文在实现切片冻结，现有 P0-1B 候选 codec 作为起点，不冒充完整通用对象实现。

[追踪表](../07-roadmap/formal-migration-traceability.json)仍完整覆盖 6 D、8 X、19 MG 与 12 FM-A；所有实现未完成、全部验收 PLANNED_NOT_RUN、新双机运行数为零。P0-1B 3/19/97、对象 schema 与 OQ/Gate/主网资格保持原状态。

## 检查与留存

只做文档/决策交接，不改运行源码、schema、registry、算法或旧证据。文档核对检查命名、链接、接受范围/待冻结字段、追踪闭合和旧文件 SHA；默认 make check 313 项及清单/diff/包核对通过。测试通过不是 SemanticStatus/部署资格的升级理由。

操作者本地 `<EVIDENCE_ROOT>/formal-migration-foundation-20261026/` 保存原 main/未提交状态、原 stash 草案字节、维护者决定、修订/校验与交付记录。保留失败及旧草案，不在源码包放凭据/密钥/数据库。本轮不推送、不另建 PR，不实现 FM-S1a，也不批准生产部署。
