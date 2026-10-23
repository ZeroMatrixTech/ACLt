# VerificationProfile Schema 工件

状态：`P0-1B STARTED / NOT CLOSED`。

- `verification_profile.schema.json`：`ACLt Schema View v1` 的首批 L1a 骨架；
- `coverage.json`：唯一实现覆盖登记，区分完整、部分、未实现、Type B 与 DEFERRED；
- 权威语义：[`../../docs/03-protocol/verification-profile-schema.md`](../../docs/03-protocol/verification-profile-schema.md)。

当前 Schema 只固定顶层字段、基础 ID、方法枚举及部分参数块在场性。它尚不是完整 P0-1B Schema，不能用于主网准入。新增覆盖时必须同时更新 `coverage.json`、对应测试和审计证据；不得仅因 JSON Schema 能解析就把规则标为完成。


2026-10-03 单机复查：新增畸形输入、精确参数边界和原因组合测试，生产模式仍强制拒绝。SV-57 的 helper 有测试，但完整 Phase D / COMPLETE 分支接入未完成，coverage.json 改为 partial；目前登记 3 项 implemented、5 项 partial。见 ../../docs/testing/SINGLEHOST-REPORT.md。

2026-10-23：全量盘点为 119 项 Type A（3 implemented、8 partial、108 not implemented），18 个规范摘要均未实现。详见 [逐项盘点](../../docs/testing/P0-1B-INVENTORY-20261023.md)。此次只修正覆盖登记，不新增验证能力；历史数量保留为当时快照。
