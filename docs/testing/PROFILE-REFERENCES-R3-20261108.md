# Profile 排除声明与注册引用第三片（R3）

基线 main `723681c`（#74），2026-11-08，修改前工作区干净。本片按 VerificationProfile §6、§11.3、§17.3/17.4 补排除声明引用和已定义的 wire 类型，范围为方法无关纯校验与限定 audit Phase R。

## 交付与覆盖

- **SV-07**：显式要求 14 项冻结基线 ID 全部在选择集中，每个缺项分别测试；不靠隐式继承。
- **SV-08**：`ExcludedClaims.registry_ref` 必须与显式提供的注册对象完整三元组一致；该对象须能从 `RegistrySnapshot` 的 `EXCLUDED_CLAIMS_REGISTRY` 行解析，选择的每个 ID 必须存在于其 entries。
- **SV-72**：`ACLt/P0-1/ExcludedClaims/1`，输入 `[registry_ref, sorted(exclusion_ids)]`；wire 集合仍须排序/去重，摘要函数的排序不使无序 wire 合法。
- **SV-89**：`ACLt/P0-1/ExcludedClaimsRegistry/1`，投影只含 schema_version、encoding_profile_id、entries；身份/版本不进内容摘要，通过引用链另行绑定。entries 保持有序数组原值，不凭空追加规范未声明的排序规则。

119 Type A 从 **11/36/72** 推进至 **15 implemented / 36 partial / 68 not implemented**。18 个摘要为 5 implemented、2 partial、11 not implemented。方法无关 `check_excluded`/`inspect_excluded` 可供其他方法复用；其余方法的完整 Profile 校验未完成。官方注册授权、A0/A1、P0-1B、Gate 和生产准入不由上述规则通过授予。

## R2 输入简化的修正

R2 的两个形状不能作为正式线上 conformance 证据：

1. §17.3 的 `TimeRange` 在线上是 `[start,end]`，R2 沿用了 §3.2.1 的结构视图 `{start,end}`。R3 只接受二元数组，检查 int64 与 start < end；Phase R 不据此做时效判断。
2. §11.3 已定义 `ExternalTypedObject{schema_ref,canonical_bytes,object_digest}`。R2 把它作为未冻结的 opaque 测试别名过于宽松。R3 要求完整封装，schema_ref 在可信 lock/documents 中逐位解析，内层必须是受支持 schema 的 canonical CBOR，并核对 payload 摘要。checkpoint/proof 裸字节在新入口拒绝。

既有 R2 入口/向量/报告正文/源码包保留历史值；本片在 R2 报告顶部追加更正，继续只支持原限域结论，未改写为正式线上输入。新入口使用独立 flag/mode，避免把历史字节解释为新 wire。Python/Rust 共用声明式类型表，分别实现解释、编解码、SHA 和引用校验；Rust 不调用 Python。

## 输入与导入边界

新适配器输入为 `{envelope,schema_lock,schema_documents,registry_objects}`。规范 `envelope` 仍是 `{phase:"R",bundle,object}`，未向 ValidationBundle 增加协议字段。适配器的 `registry_objects` 本片限一个显式 ExcludedClaimsRegistry 资产，拒绝缺失、额外、重复或错误 kind；不从远程补取。

调用方须在输入之外提供可信 lock SHA-256。R3 支持既有 `OPAQUE_BSTR` 描述和用于 ExternalVersionedObjectRef 的 `VERSIONED_REF` 三元引用描述；别名/schema ID/version/content/pin 均需匹配。未知或不兼容表示 fail closed；R3 禁止再次把 ExternalTypedObject 声明为 opaque import。

**仍未完成的正式导入：** schema 描述格式和测试 pin 是当前校验适配器合约，不是官方 schema 发布/注册。未冻结的 ResourceBounds、RetentionPolicyRef、DocBlock、EffectID 等仍使用显式测试 opaque schema；不猜测其子字段。外部载荷的 `object_digest` 沿用既有 claim codec 的 `SHA256(canonical_bytes)` 测试约定，本片不替其他外部编码/算法建立通用官方注册。种子排除注册表用于生成固定测试对象，状态仍为 SEED_NOT_REGISTERED，未创建官方 ACTIVE 注册表。

纯引用/摘要通过不认证外部组件、日志 proof、finality、时钟来源或发布授权；输出继续 `full_schema_valid:false`、`source_authentication:false`，`--production` 强制拒绝。R3 不改变实际 FM-S3 任务协议或终态/账务行为。

```sh
python3 -B -m tools.verification_profile.validator registration.cbor \
  --registration-references-cbor --schema-lock-sha256 TRUSTED_LOCK_SHA256
make test-profile-references
```

Rust 新模式为 `phase-r3:<trusted-lock-pin><TAB><CBOR-hex>`，纯排除链检查为 `excluded-selection<TAB><CBOR-hex>`；Python 对应 `references.inspect` / `references.inspect_excluded`。

## 验证与复现

固定 104 条向量（12 正例、92 反例）和 15 项新增默认回归，覆盖每个基线缺项、自由文本/未知 ID、选择集顺序/重复、注册对象身份与内容分离、不同快照版本、未知字段/类别、缺失/多余资产、SHA preimage 的 hashlib/OpenSSL 对照、TimeRange wire 唯一性、两种受支持 payload、外部 schema/内容/摘要的篡改与历史限域兼容。

完整 `make test` 退出码为 0：默认 23 组 512 项（R2 497 + 本片 15）及另 25 项执行器测试，共 537 项；20 次 sanitizer、既有 Claim/FM/RIR 对拍通过。R1 66 条、R2 74 条的结果流 SHA-256 均与其原记录一致；24 套历史快照的 249 条事件重新重放通过。

两台物理机分别构建并通过全部 104 条，结果流 SHA-256 均为 `b28d0d466f31dd1303ecb7e82906ce56e3e79acb37ce88212855a2b7d3fce169`，逐文件 pin 相同。环境、源码和结果见[机器摘要](PROFILE-REFERENCES-R3-20261108.summary.json)。[公开最小对拍源码包](public-evidence/PROFILE-REFERENCES-R3-source.tar.gz)已在新目录核对所有 pin 后复跑 104 条，结果哈希一致；包内 `source-sha256.json` 给出精确内容。全量日志、A/B 原始报告与部署记录保留在操作者证据目录。本轮双机范围限于静态构建/编码/引用检查，新增任务协议运行数为 0；两机假设按 DUALHOST-SSH-1，不能推出身份或统计独立。

下一步先补剩余 Phase R 规则与正式 import 处置，再接固定 Profile 的 I/F 创建和绑定；完整五相位和来源认证继续独立验收。
