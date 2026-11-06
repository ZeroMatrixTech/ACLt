# VerificationProfile Schema 工件

状态：`P0-1B STARTED / NOT CLOSED`。

- `verification_profile.schema.json`：`ACLt Schema View v1` 的首批 L1a 骨架；
- `verification_profile_v2.schema.json`：Profile schema v2 的 L1a 骨架。audit 省略 claim 键，其余方法要求对象。固定字节见 [SV-30 局部向量](../../tests/verification_profile/codec/profile-v2-claim-presence.json)。SV-30 仍为 partial，完整 VerifiedClaimSpec、ContentMap 摘要与注册待验收。
- `coverage.json`：唯一实现覆盖登记，区分完整、部分、未实现、Type B 与 DEFERRED；
- 权威语义：[`../../docs/03-protocol/verification-profile-schema.md`](../../docs/03-protocol/verification-profile-schema.md)。

当前 Schema 只固定顶层字段、基础 ID、方法枚举及部分参数块在场性。它尚不是完整 P0-1B Schema，不能用于主网准入。新增覆盖时必须同时更新 `coverage.json`、对应测试和审计证据；不得仅因 JSON Schema 能解析就把规则标为完成。


2026-10-03 单机复查：新增畸形输入、精确参数边界和原因组合测试，生产模式仍强制拒绝。SV-57 的 helper 有测试，但完整 Phase D / COMPLETE 分支接入未完成，coverage.json 改为 partial；目前登记 3 项 implemented、5 项 partial。见 ../../docs/testing/SINGLEHOST-REPORT.md。

2026-10-23：全量盘点为 119 项 Type A（3 implemented、8 partial、108 not implemented），18 个规范摘要均未实现。详见 [逐项盘点](../../docs/testing/P0-1B-INVENTORY-20261023.md)。此次只修正覆盖登记，不新增验证能力；历史数量保留为当时快照。

后续编码切片更新：本页 3/8/108 与 18 摘要全未实现的统计保留为盘点时基线；当前登记已变为 3/24/92，2 个摘要部分实现、16 个未实现。Python/Rust 限域对拍及 SV-42 说明勘误见 [编码切片记录](../../docs/testing/CLAIM-CODEC-20261023.md)；以 coverage.json / inventory.json 当前记录为准。

无 Snapshot Phase B 的局部 guard 和[转换向量](../../tests/verification_profile/test_phase_b.py)覆盖 SV-93/94/105 的新增分支，三项登记为 partial。调用依赖已验证的 frontier 与 Receipt/Profile 绑定。正式来源 contract、全信封校验和日志忠实性另行验收。

结果接纳切片补充 EA-4—EA-6，并在候选 S3 权威复用精确预算检查。SV-112 登记为 partial，局部向量覆盖严格期限、预算上限、边界因果序和无效来源。[向量](../../tests/verification_profile/test_admission.py)
