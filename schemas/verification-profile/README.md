# VerificationProfile Schema 工件

状态：`P0-1B STARTED / NOT CLOSED`。

- `verification_profile.schema.json`：`ACLt Schema View v1` 的首批 L1a 骨架；
- `verification_profile_v2.schema.json`：Profile schema v2 的 L1a 骨架。audit 省略 claim 键，其余方法要求对象。固定字节见 [SV-30 局部向量](../../tests/verification_profile/codec/profile-v2-claim-presence.json)。SV-30 仍为 partial，完整 VerifiedClaimSpec、ContentMap 摘要与注册待验收。
- `coverage.json`：唯一实现覆盖登记，区分完整、部分、未实现、Type B 与 DEFERRED；
- 权威语义：[`../../docs/03-protocol/verification-profile-schema.md`](../../docs/03-protocol/verification-profile-schema.md)。

当前 Schema 只固定顶层字段、基础 ID、方法枚举及部分参数块在场性。它尚不是完整 P0-1B Schema，不能用于主网准入。新增覆盖时必须同时更新 `coverage.json`、对应测试和审计证据；不得仅因 JSON Schema 能解析就把规则标为完成。


2026-10-03 单机复查：新增畸形输入、精确参数边界和原因组合测试，生产模式仍强制拒绝。SV-57 的 helper 有测试，但完整 Phase D / COMPLETE 分支接入未完成，coverage.json 改为 partial；目前登记 3 项 implemented、5 项 partial。见 ../../docs/testing/SINGLEHOST-REPORT.md。

2026-10-23：全量盘点为 119 项 Type A（3 implemented、8 partial、108 not implemented），18 个规范摘要均未实现。详见 [逐项盘点](../../docs/testing/P0-1B-INVENTORY-20261023.md)。此次只修正覆盖登记，不新增验证能力；历史数量保留为当时快照。

后续编码切片更新（历史快照）：本页 3/8/108 与 18 摘要全未实现的统计保留为盘点时基线；当时登记变为 3/24/92，2 个摘要部分实现、16 个未实现。Python/Rust 限域对拍及 SV-42 说明勘误见 [编码切片记录](../../docs/testing/CLAIM-CODEC-20261023.md)；以 coverage.json / inventory.json 当前记录为准。

无 Snapshot Phase B 的局部 guard 和[转换向量](../../tests/verification_profile/test_phase_b.py)覆盖 SV-93/94/105 的新增分支，三项登记为 partial。调用依赖已验证的 frontier 与 Receipt/Profile 绑定。正式来源 contract、全信封校验和日志忠实性另行验收。

结果接纳切片补充 EA-4—EA-6，并在候选 S3 权威复用精确预算检查。SV-112 登记为 partial，局部向量覆盖严格期限、预算上限、边界因果序和无效来源。[向量](../../tests/verification_profile/test_admission.py)

2026-11-07 [Profile 摘要第一片](../../docs/testing/PROFILE-DIGEST-R1-20261107.md)实现正式 ContentMap/摘要及通用判决结构，登记为 7 implemented / 28 partial / 84 not implemented。Profile 摘要 implemented，模板/claim 摘要 partial，其余 15 项摘要未实现。原始 CBOR 入口见 `python3 -m tools.verification_profile.validator PROFILE --profile-cbor`。完整 SchemaValid、导入/注册与生产准入继续独立验收。

2026-11-07 [Profile 注册第二片](../../docs/testing/PROFILE-REGISTRATION-R2-20261107.md)新增四项规则级完成与八项 partial，当前 **11 implemented / 36 partial / 72 not implemented**。RegistrySnapshot/事件快照摘要已实现，audit Phase R 接显式 bundle；导入内部结构采用调用方钉住的测试 opaque schema，尚非正式全量 SchemaValid。原 JSON bootstrap schema 文件维持原骨架，新增严格类型表位于 `tools/verification_profile/rust/audit_types.json`。

2026-11-08 [R3](../../docs/testing/PROFILE-REFERENCES-R3-20261108.md)完成 SV-07/08/72/89，当前 **15 implemented / 36 partial / 68 not implemented**。新的 `--registration-references-cbor` 入口使用线上二元 TimeRange 与三字段 ExternalTypedObject，并要求显式 ExcludedClaimsRegistry 资产。`--registration-cbor` 保留 R2 历史限域行为，其 map TimeRange/opaque wrapper 不构成正式 wire conformance；官方 import 注册、完整 SchemaValid 和生产准入仍待完成。

2026-11-08 [R4](../../docs/testing/PROFILE-RULES-R4-20261108.md)完成 SV-03/22/32/33/37/38/59/73/84；当前 **24 implemented / 30 partial / 65 not implemented**。规则专用入口 `--registration-rules-cbor` 可检查四种方法的上述规则，不能用来声明完整 ValidateR；`--registration-r4-cbor` 为固定 audit 集成。未检验参数/claim、正式 import、版本迁移、日志来源和完整相位仍待验收。

2026-11-08 [R5](../../docs/testing/PROFILE-MATRICES-R5-20261108.md)完成 SV-13/16/18/19/20/29R/31/51；当前 **32 implemented / 29 partial / 58 not implemented**。新增 `--method-matrix-cbor` 与固定 audit `--registration-r5-cbor`；参数结构表在 `method_types.json`，现有旧源码部署清单加入其传递依赖。SV-04/09/64/65 仍 partial，不能将测试 import、非 audit adapter 终态预期值或冻结投影模型当成完整 SchemaValid/正式部署。

R6 新增 `creation.py` / Rust `creation.rs` 的固定 audit I/F **测试**入口：

```sh
python3 -B -m tools.verification_profile.validator /path/phase-f.cbor --creation-f-cbor --schema-lock-sha256 <trusted-lock-pin> --test-contract-sha256 <trusted-test-contract-pin>
make test-creation-bindings
```

Phase I 改用 `--creation-i-cbor`。外部调用者必须同时提供两个可信 pin；不得从待验输入现算 pin 来授权陌生数据。`test_contract` 位于测试适配器外层，不是协议对象字段。它仅为已绑定 Profile 的 opaque ContractTuple 精确相等谓词，既非通用 `ReplayPhaseI`，也不认证主网 assurance；`--production` 始终拒绝。规则覆盖 36/33/50，摘要 9 implemented / 2 partial / 7 not implemented。详见 [R6 报告](../../docs/testing/PROFILE-CREATION-R6-20261108.md)。
