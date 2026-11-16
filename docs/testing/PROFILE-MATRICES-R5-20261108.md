# 方法参数与失败／判决矩阵第五片（R5）

本片实现 VerificationProfile §7、§8.5、§10.2、§11.3 中已冻结的矩阵并接入固定 audit 路线，382 条固定向量在 A/B 两台物理机上全部通过且结果流 SHA-256 一致，完整 `make test` 退出码为 0，119 条 Type A 由 **24/30/65** 变为 **32 implemented / 29 partial / 58 not implemented**。基线 `3b85c59`，日期 2026-11-08，开始时分支 `feat/profile-r3-r4-20261108`、工作区干净；规范正文与既有线上字段保持原值。

## 交付

| 规则 | 本片结果 |
|---|---|
| SV-18/19 | 四种 FailureMapping，sorted key/value 行及各自 outcome/evidence_class；Direct 证书事件随 certificate_required 精确增删；缺失、多余、重复、乱序、变体混用均拒绝 |
| SV-20 | 四方法精确条件集合；Direct SOUND 与 SOUND_AND_COMPLETE 使用不同 REJECT 条件，Audit 无 ACCEPT，Bounded 无 REJECT |
| SV-31 | safety/liveness 两块互斥及各方法字段/变体选择；Bounded 必须两块非空，其余省略；正式 import 内部语义另行验收 |
| SV-51 | 每种方法含 EXECUTION_FAILED，终态仅由冻结 CanonicalTerminal 派生；DecisionMapping 不能提供 terminal 覆盖字段 |
| SV-13/16/29R | q_source 仅两种允许声明；Direct 声明 DETERMINISTIC、effects 为空；仅 Bounded 声明 uint max_invalid_samples。这些结构通过不证明校准、实际无 effects 或采样消耗行为 |

八项新增完成使 119 Type A 从 **24/30/65** 变为 **32 implemented / 29 partial / 58 not implemented**，18 个摘要仍为 6 implemented、2 partial、10 not implemented。

Python `method_rules.py`、Rust `method_rules.rs` 分别实现矩阵与投影模型；双方共享被 pin 的声明式参数类型表 `method_types.json`，各自使用独立编解码/类型解释。复用既有 typed 解释器时显式传入新类型目录，避免改变 R2/R3/R4 fixture 的导入集。旧 FM/RIR 部署清单和各对拍 source pin 采集同步加入 Rust 新模块与类型表；旧归档不修改。ValidatorRef/PredicateRef 的引用版本分量另补 uint64 边界。

## 明确保留的缺口

| 状态 | 处置 |
|---|---|
| 已冻结并实现 | 原生字段、枚举、布尔/整数/VersionRange/TimeRange、互斥、四方法失败事件/条件矩阵、CanonicalTerminal 的常量投影 |
| 显式测试 import | ResourceBounds、EffectID、RetentionPolicyRef、DocBlock 及 Proof/Bounded 工程引用等沿用调用方固定 schema lock。DatasetRef 使用 §3.2.1 固定 import ID；其测试不透明载荷不构成官方注册 |
| **SV-04 PARTIAL** | Direct predicate_signature 给出函数类型但未冻结其线上表示；本片以明确命名的测试 opaque schema 承载，不宣称解析或证明了该函数签名。Proof ceremony 识别和其他正式 import 仍未完成 |
| **SV-64 PARTIAL** | 规范只在 AuditParams 中声明 reachable_terminals，其他三种参数没有该字段。R5 对四方法派生 RT-1 并校验适配器预期值；不向其他参数或 Profile 擅自加字段，非 audit 正式 wire 仍需决定 |
| **SV-65 PARTIAL** | 方法 outcome/聚合耗尽行已有固定纯函数，拒绝自定义投影参数；完整 AggregateState/evaluator contract、共通来源行和 Phase D 接线仍缺。测试布尔状态不是权威事实或统计资本计算 |
| **SV-09 PARTIAL** | 检查 Direct SOUND 的 REJECT 归因为 NO_ATTRIBUTION；方法特定排除项及其完整引用链待后续接入 |

非 audit 的参数已填充已知冻结字段；未冻结的引用/签名是测试绑定，数值亦为测试输入，B/Q、DP 校准、proof soundness 与运行语义不在本片证明范围内。非 audit 的 verified_claim_spec 仍为未验证占位，完整 claim/注册授权另行接通。`full_schema_valid:false`、`source_authentication:false`、非 audit 部署未启用及生产强制拒绝保持不变；Phase R、A0/A1、P0-1B 与 Gate 的关闭状态由各自的验收决定。

## 入口

- `method-matrix:<pin><TAB><CBOR-hex>` / `--method-matrix-cbor`：适配器为 R4 rule helper 的五字段再加 reachable_terminals。该额外值仅为测试断言，不是新增协议字段。
- `phase-r5:<pin><TAB><CBOR-hex>` / `--registration-r5-cbor`：沿用固定 audit 完整信封/引用/R4 规则，补矩阵检查，不启用其他方法。
- `frozen-projection<TAB><CBOR-hex>`：测试适配器显式给 method/outcome/aggregate_exhausted，Direct 再给 soundness_class，Bounded 再给 threshold_met/null_bound_exactly_exceeded。只核对 §11.3.2A 方法结果行；无条件时输出测试元数据 condition_present:false，不定义协议 ⊥ 的新 wire。

```sh
make test-method-matrices
python3 -B -m tools.verification_profile.validator matrix.cbor \
  --method-matrix-cbor --schema-lock-sha256 TRUSTED_LOCK_SHA256
python3 -B -m tools.verification_profile.validator audit.cbor \
  --registration-r5-cbor --schema-lock-sha256 TRUSTED_LOCK_SHA256
```

## 验证与复现

固定 382 条（84 正例、298 反例），含 Direct 两类 soundness/证书开关、各方法事件/条件逐项缺失、重复、乱序、混用、字段缺失、参数互换、三块互斥、max_invalid_samples、q_source、Direct 声明及 72 个投影状态组合。13 项新增默认回归从规范原表独立提取事件/条件集合，核对条件证书事件、终态派生、引用版本上界、CLI/生产边界、输入不变与旧部署传递依赖。验证配置的 118 项单元测试已通过。

修复后的完整 `make test` 退出码为 0：默认 23 组 539 项（R4 526 + 本片 13），另 25 项执行器测试，共 564 项；20 次 sanitizer、既有 Claim/FM/RIR 对拍通过。R1–R4 的 66/74/104/145 条结果流 SHA-256 均与原记录一致；24 套公开历史快照的 249 条事件重放通过。

两台物理机各自构建并通过 382 条，结果流 SHA-256 均为 `ef42c715fda6fb2c5d0831afb95acdd4fb121aff554db7ff0dcef189d61136b1`，源码 pin 相同。环境及结果见[机器摘要](PROFILE-MATRICES-R5-20261108.summary.json)。[公开最小对拍源码包](public-evidence/PROFILE-MATRICES-R5-source.tar.gz)已在新目录逐文件核对 pin 并复跑全部 382 条，结果一致；完整单元/组合回归使用仓库全量源码，而非此最小对拍包。

首轮全量检查在仓库优化模式入口规则处失败；类型目录的不重名约束改为始终执行的显式异常检查，验证 `-O` 模式仍拒绝错误矩阵，再对修复后的精确源码重跑双机和完整回归。初次失败日志、修复前后 A/B 原始报告、部署记录及最终全量日志保留在操作者证据目录。双机范围为静态构建/编码/矩阵核对，新增任务协议运行数为 0；不推导身份或统计独立性。

下一步可在固定 audit 路径推进 I/F 的测试接线，并逐项处置该路径必需的正式 import/来源边界。Direct 签名 wire 和非 audit 终态字段在各自方法路径继续追踪；它们不作为 audit 测试接线的额外前置条件。矩阵或测试 schema 不能代替完整注册、正式导入与部署验收。
