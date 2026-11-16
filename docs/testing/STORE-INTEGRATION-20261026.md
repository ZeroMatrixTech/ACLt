# store 草案整合与清理

日期：2026-10-26；整合基线 `80db6ac2cb3d2ff2e522cd80b335f3f98e748a38`。按维护者要求，九个文件的 store stash `f0952ea913143a4c0e2c10ffc64bb8fcdc09489c` 已并入并清理：ADR-0007 的六项路线、接口、不变量、假设与退出边界按决定接受，Formal 计划替换旧基线与错误第四项名称（逐项去向见下表）。该 stash 与 round4 历史 stash 相互独立。

## 内容去向

| 原文件 | 当前去向与处置 |
|---|---|
| ADR-0007 | 同路径；保留六项路线、接口、不变量、假设与退出边界，已根据维护者决定接受路线；修正 audit-only/Snapshot、终态优先级及 INV-07 |
| formal-work4-plan.md | formal-migration-plan.md；细分 FM-S1a/S1b，统一 FM-A 编号；本次补回逐片交付义务及原 12/12/14 场景回归基线 |
| formal-work4-traceability.json | formal-migration-traceability.json；6 D、8 X、19 MG、12 项验收保留；实现仍未完成 |
| FORMAL-WORK4-F0-20261026.md | FORMAL-MIGRATION-F0-20261026.md；替换旧基线与错误第四项名称，保留设计交付和非实现边界；旧检查结果仅保存在原始备份，不充作本轮证据 |
| formal-object-migration.md | 保留政策先于 Receipt、无环摘要、同内容幂等返回原结果的更正 |
| current-status.md | 当前入口表与 FM-F0 收尾记录；不恢复旧的 PROPOSED 状态或覆盖已合并 B/Q 记录 |
| open-questions.md | FM 路线接受、字段未冻结及 OQ 仍 OPEN 的说明 |
| docs/README.md | 当前 ADR/FM 入口及报告链接；不恢复旧 work4 链接 |
| SINGLEHOST-SHA256SUMS | 根据最终内容重新生成，不恢复旧哈希 |

以上去向均相对 docs 目录中的对应原目录。唯一实施入口仍为[正式迁移计划](../07-roadmap/formal-migration-plan.md)，本次不新增路线决定、不实现 FM-S1a、不改变 Gate。

操作者本地 `<EVIDENCE_ROOT>/store-integration-20261026/` 留存九文件原字节、tracked patch、stash 元数据和 SHA-256 清单。提交和清单检查完成后，仅删除上述 store stash；其他 stash 不变。不推送远端。
