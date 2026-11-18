# P0-1B 实现覆盖盘点（2026-11-17）

本报告基于基线 `1533290ed82347a5a5006e4d35a5092d02362780`，以现行 [规范 §13.2](../03-protocol/verification-profile-schema.md#132-校验清单) 为准盘点 P0-1B 实现覆盖：119 项 Type A 中 80 项 implemented、36 项 partial、3 项 not implemented；18 个规范摘要均 implemented。本轮只盘点、修正覆盖登记与路线图，validator 行为未修改，P0-1B、G0 与 G2 保持未关闭。

## 核对结论

规范 §13.2 共 127 行：119 项 Type A、6 项 Type B、SV-15 作废、SV-40 延期。D-08-c 是额外 Type B 义务，不计入这 6 项 SV 计数。

119 项 Type A：80 项 implemented、36 项 partial、3 项 not implemented（SV-27、SV-50、SV-61）；18 个规范摘要全部 implemented。implemented 只表示该规则的实现与直接测试已在本轮核对中成立，不表示完整相位、SchemaValid、第二语言全量 conformance 或生产准入；生产模式继续 fail closed。

唯一状态登记为 [coverage.json](../../schemas/verification-profile/coverage.json)，逐项实现、测试符号与缺口见 [inventory.json](../../schemas/verification-profile/inventory.json)。本表从规范表逐行提取，保留非连续及拆分编号（无 SV-83；Type B 单列于后），编号不按 01–121 推测。既有单机、VM 与双机场景只提供工程证据，规范 conformance 需另行验收。

## 核对范围与方法

- 逐项核对 §13.2 的 requirement、相位与层是否与登记一致；`check-profile-inventory.py` 同时校验这三项。
- 逐项核对 status：查看 implementation 符号指向的函数是否真的判定该规则，test 符号是否直接覆盖该规则的正例或反例；不把历史测试通过记录当成本次执行结果。
- 本轮逐项复核 SV-41–80 区间共 43 个编号（其中 41 项 Type A、2 项 Type B）；接手修复时（dsh）补做 SV-01–40 与 SV-81–121 的逐项核对，至此 119 项 Type A 全部逐项核对；另对全部登记符号做机器可解析性检查。
- 状态判断以现行 §13.2 与当前代码为准，不以切片报告的措辞为准。
- 核对阶段只读；最终验证命令与退出码记录在 PR 正文。

## 与 2026-10-23 基线的差异

10-23 报告基线为 `01e8ee2`，当时 119 项 Type A 为 3 implemented / 8 partial / 108 not implemented，18 个摘要均未实现。现行登记与之一致的变化共 108 项：

- `N -> I`，74 项：

```text
SV-02 SV-05 SV-06 SV-07 SV-08 SV-09 SV-12R SV-13 SV-16 SV-17 SV-18
SV-19 SV-20 SV-21 SV-22 SV-23 SV-28 SV-29R SV-33 SV-35 SV-36 SV-37
SV-38 SV-39 SV-41 SV-44 SV-45 SV-46 SV-47 SV-48 SV-49 SV-51 SV-53a
SV-53b SV-54b SV-59 SV-63 SV-68 SV-70 SV-71 SV-72 SV-73 SV-74 SV-75b
SV-77 SV-78 SV-79 SV-82 SV-84 SV-85 SV-86a SV-86b SV-86c SV-87
SV-88 SV-89 SV-90 SV-92 SV-93 SV-94 SV-95 SV-97 SV-99 SV-101 SV-103
SV-104 SV-105 SV-106 SV-107 SV-108 SV-112 SV-113 SV-114 SV-120
```

- `N -> P`，31 项：

```text
SV-04 SV-12I SV-14 SV-25 SV-26 SV-29I SV-42 SV-43 SV-52 SV-55 SV-58
SV-60 SV-62 SV-64 SV-65 SV-66 SV-69 SV-75a SV-81 SV-91 SV-96 SV-98
SV-102 SV-109 SV-110 SV-115 SV-116 SV-117 SV-118 SV-119 SV-121
```

- `P -> I`，3 项：SV-03、SV-31、SV-32。

其余 11 项状态未变：SV-10/11/76 继续 implemented，SV-01/30/54a/57/80 继续 partial，SV-27/50/61 继续 not implemented。18 个摘要均为 `N -> I`。

本轮复核没有改变上述统计：SV-41–80 区间与接手补做的 SV-01–40、SV-81–121 区间逐项核对后，Type A 仍为 80/36/3；除 SV-04 的规则级证据已充分但按计划卡修订 1 保持 PARTIAL 外，其余状态全部维持，只修正了与状态无关的登记瑕疵。

补做核对发现 SV-04 的 `check_parameters` 已按四方法封闭参数类型判定变体（`method_rules.py:39`，12 条 `swapped-params-*` 向量中 9 条直接命中），现行 gap 的 `predicate_signature` 理由属于相邻 import/全局类型范围。提升 SV-04 会改变 80/36/3 并需同步四处计数与依赖清单，超出本轮修订 1 的文件集，故只记录、不提升，留待维护者决定或另开条目。其余登记瑕疵（SV-10/11 的 v2 接线缺口、诊断标签、部分测试符号错配）同样只记录。

## 本次登记修正

- `coverage.json` 的复核说明更新为 2026-11-17 与基线 `1533290`；`inventory.json` 的 `review_date`、`baseline_commit`、`scope` 同步。
- 18 个摘要补上现行 implementation 与 tests 符号；此前多数摘要条目为空。
- 改善 R9–R16 的证据登记：SV-81/82/85/86c/87/89/94/96/102/105/109/110/115/118。
- SV-117 补入 R14–R16 的非主网 I/F/B/D 信封、部署绑定与签名撤销证据，并保留 `ENABLED`/主网 MAP 缺口；SV-119 补入 FM-S2/FM-S3 checkpoint、包含、anchor 与 R14–R16 信封证据，并保留 `log_backend_ref`/finality 缺口；SV-121 补入 FM-S3 closure/observer 与负例，并保留正式闭合摘要合同缺口。三项均保持 partial。
- SV-43 移除与 D-06 degraded-slot 判定无关的 R8 候选胶囊符号；SV-49 补判定入口 `check_spec`；SV-55 补角色过滤循环 `applicability` 与 INFO 排除测试；SV-75a 修正过时的“只接 audit Phase R”缺口说明（R/B/D 已接线，缺 I/F）；SV-80 改登记 `registration.py#identifier` 与真正的 ID 向量测试，替换此前不触碰该规则的符号。
- 新增 `later_profile_slice_evidence`，登记 R6–R16 的切片报告、completed/partial 规则与范围；R12–R16 没有新增 completed 规则，只登记其规则级 partial 证据。旧 R1–R5 顶层字段保留切片时状态，不在本轮改写。

## 全量 Type A 清单

I = implemented，P = partial，N = not implemented。每项的代码和测试符号在机器清单中；缺口列给出剩余范围。状态是规则级覆盖，不是相位、项目或 Gate 完成度。

| ID | 相位 | 层 | 状态 | 检查及剩余范围 |
|---|---|---|---|---|
| SV-01 | R | L1a | P | `schema_version` 与 `encoding_profile_id` 已知；无未知字段；仅顶层字段与版本；嵌套未知字段尚未封闭。 |
| SV-02 | R | L2 | I | `profile_digest` 按 §17.4 与 UVP-1V 重算一致；该条规则已在原始 CBOR Phase R 入口实现。完整 SchemaValid、registry/source 与其他 SV 独立验收。 |
| SV-03 | R | L1a | I | `verification_method` ∈ 四元枚举；方法无关注册规则 helper 已在四种方法下独立 Python/Rust 对拍；非 audit 参数/claim 块在规则专用向量中为未检验占位，完整方法、注册授权和 Phase R 其余规则不由本项通过授予。 |
| SV-04 | R | L1a | P | `method_parameters` 变体与 `verification_method` 匹配；四种参数块的冻结字段和测试 import 已有封闭结构校验；Direct predicate_signature 线上编码与其他正式 import 未冻结，不能完成全局类型验收。 |
| SV-05 | R | L1a | I | `claim_template_ref.template_id` 与方法一一对应（CLM-3）；三种产生 claim 的方法固定对应模板 ID；audit 不引用模板。注册授权与模板正文来源独立验收。 |
| SV-06 | R | L1b | I | `binding_schema` 键集合 = 模板槽位集合；`RUNTIME` 槽位不出现在 `static_bindings`（CS-1、CS-3）；模板与 binding_schema 的 slot/decl 按规范 CBOR 字节一致；STATIC 键完整，RUNTIME 不得进入 static_bindings。bool 与整数不能用 Python 相等关系混同。 |
| SV-07 | R | L1b | I | `exclusion_ids` ⊇ 全部 `EXC-BASE-*`（14 项）；方法无关排除选择/注册对象 helper 与限定 audit R3 入口已实现，独立 Python/Rust 固定字节对拍通过；完整 Profile/注册授权/五相位仍待验收。 |
| SV-08 | R | L1b | I | `exclusion_ids` 全部存在于 `registry_ref` 所指 `ExcludedClaimsRegistry` 的 `entries` 中，且该对象在 `RegistrySnapshot` 中可解析；方法无关排除选择/注册对象 helper 与限定 audit R3 入口已实现，独立 Python/Rust 固定字节对拍通过；完整 Profile/注册授权/五相位仍待验收。 |
| SV-09 | R | L1b | I | 方法特定排除项齐备；`soundness_class = SOUND` ⇒ `reject_attribution = NO_ATTRIBUTION`（DV-1）；三方法的六个冻结排除项已接入显式排除注册表解析；Direct SOUND 仍强制 NO_ATTRIBUTION。 |
| SV-10 | R | L1b | I | `REEXEC_BOUNDED`：\(0\le B<Q\le G\)、\(\Delta_{bound}\ge\delta_{min}>0\)；局部精确参数谓词已实现；不代表完整 Phase R 可接受。 |
| SV-11 | R | L1b | I | `REEXEC_BOUNDED`：\(\sum\pi(m)=1\) 精确，且 \(\forall m\in\mathrm{supp}(\pi): m\ge Q\)；局部权重谓词已实现；不代表完整 Phase R 可接受。 |
| SV-12R | R | L1b | I | `support_capability_bound_ref` 指向本 Profile 中 `assumption_class = SUPPORT_CAPABILITY_BOUND` 且 `role = SAFETY_CRITICAL` 的条目（AR-3）；support_capability_bound_ref 唯一解析到本 Profile 的 SUPPORT_CAPABILITY_BOUND/SAFETY_CRITICAL；只检查引用，不证明假设为真。 |
| SV-12I | I | L1b | P | 该假设在 `scope` 与 `validity_window` 内。**失败产生 `SUPPORT_CAPABILITY_BOUND_UNAVAILABLE` 触发条件，不是拒绝**；已检查引用假设的六维包含与半开有效窗，失败作为测试判定结果，不拒绝 Profile；DeclaredScope 来自显式测试适配器，NormalizeDeclaredScope(Intent) 与正式触发原因 wire 未接。 R8 已有独立 TEST tag 的候选输入胶囊派生与字节绑定，但没有升级现行 ReceiptIntent/1、正式 imports 或通用 ReplayPhaseI，故仍 partial。 |
| SV-13 | R | L1b | I | `q_source` ∈ {`ANCHORED_IN_CLASS`, `FAULT_INJECTED_IN_CLASS`}（LP-1）；四方法冻结矩阵/声明约束已实现并独立对拍；只完成本规则，不授予完整参数/claim/import、SchemaValid、统计来源或部署资格。 |
| SV-14 | I | L1b | P | \(N_{required}\le N_{max}\)；失败产生 `POPULATION_TOO_SMALL`；N_required≤N_max 的独立测试判定已对拍，N_max 为显式适配器输入；从正式 Intent/预算约束导出 N_max 和创建期触发接线仍缺。 R8 已有独立 TEST tag 的候选输入胶囊派生与字节绑定，但没有升级现行 ReceiptIntent/1、正式 imports 或通用 ReplayPhaseI，故仍 partial。 |
| SV-16 | R | L1a | I | `DIRECT_VERIFIED`：`effects` 为空、`determinism = DETERMINISTIC`；四方法冻结矩阵/声明约束已实现并独立对拍；只完成本规则，不授予完整参数/claim/import、SchemaValid、统计来源或部署资格。 |
| SV-17 | R | L1b | I | `REEXEC_AUDIT_ONLY`：`decision_mapping` 的条件序列不含 `ACCEPT`，故值域不含 `TRUSTED`（AO-1 的推论）；该条规则已在原始 CBOR Phase R 入口实现。完整 SchemaValid、registry/source 与其他 SV 独立验收。 |
| SV-18 | R | L1b | I | `failure_mapping` 变体正确，且 `entries` 键集合**恰好等于** §10.2 矩阵为本方法确定的适用事件集合；四方法冻结矩阵/声明约束已实现并独立对拍；只完成本规则，不授予完整参数/claim/import、SchemaValid、统计来源或部署资格。 |
| SV-19 | R | L1a | I | `failure_mapping` 变体与方法匹配；`INVALID_SAMPLE` 只出现在 `ReexecFailureMapping`（FM-0）；四方法冻结矩阵/声明约束已实现并独立对拍；只完成本规则，不授予完整参数/claim/import、SchemaValid、统计来源或部署资格。 |
| SV-20 | R | L1b | I | `decision_mapping.rules` 的元素集合恰好等于 §11.3.3 为本方法规定的适用 `DecisionCondition` 集合；缺失、多余、重复均拒绝；四方法冻结矩阵/声明约束已实现并独立对拍；只完成本规则，不授予完整参数/claim/import、SchemaValid、统计来源或部署资格。 |
| SV-21 | R | L1b | I | `WeakeningEdge` 合法：`edge_class = AUTO_DECIDABLE`，源与目标 `ProfileDigest` 与实际 Profile 一致，满足 §6.5 四项；显式 source/target 对象与快照解析；只接受 bounded→audit 的 AUTO_DECIDABLE，检查排除集包含、目标无 claim、task/constraints/equivalence 一致。无部署启用或 WeakeningEdge 来源认证。 |
| SV-22 | R | L1a | I | `DegradationDecl.triggers` ⊆ §9.3 封闭集合；方法无关注册规则 helper 已在四种方法下独立 Python/Rust 对拍；非 audit 参数/claim 块在规则专用向量中为未检验占位，完整方法、注册授权和 Phase R 其余规则不由本项通过授予。 |
| SV-23 | I | L1b | I | `DEGRADED` slot 仅当 `degradation_authorized = true` 时可被考虑；DEGRADED slot 只有显式 bool true 才可被考虑；PRIMARY 不依赖降级授权。该规则独立 helper 不代替完整选择算法。 |
| SV-25 | R | L2 | P | `encoding_profile_id = acl.enc.p0-1@1`；原始 CBOR 无 float/null/undefined/其他 simple value、无 indefinite-length；不检查整数范围或集合排序；已检查切片 primitive/禁令；未接入五相位全部对象及 encoding profile contract。 |
| SV-26 | I | L1b | P | `allowed_effects` ⊇ Intent 的允许 effects；已实现 Intent effects⊆Profile allowed_effects 的精确集合方向；Intent/ContractTuple 的实际 effects 取值链尚未冻结接入。 R8 已有独立 TEST tag 的候选输入胶囊派生与字节绑定，但没有升级现行 ReceiptIntent/1、正式 imports 或通用 ReplayPhaseI，故仍 partial。 |
| SV-27 | R | L1b | N | `V1Admissible` 检查（§12、§13.1 与当前 V1 `VersionDisposition`）；`SchemaValid` 不含此项；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-28 | I | L1b | I | Profile 状态 ∈ {`REGISTERED`, `ACTIVE`}；完整 Profile 三元身份在显式 RegistrySnapshot 中解析；REGISTERED/ACTIVE 返回可考虑，DEPRECATED/REVOKED 返回不适用。来源认证和实际 Phase I 管线独立验收。 |
| SV-29R | R | L1a | I | `ReexecFailureMapping.max_invalid_samples` 已声明；四方法冻结矩阵/声明约束已实现并独立对拍；只完成本规则，不授予完整参数/claim/import、SchemaValid、统计来源或部署资格。 |
| SV-29I | I | L1b | P | `max_invalid_samples ≤ N_max`（FM-2；依赖 Intent，故属 Phase I）；max_invalid_samples≤N_max 的独立测试判定已对拍；N_max 正式来源与 Phase I 接线仍缺。 R8 已有独立 TEST tag 的候选输入胶囊派生与字节绑定，但没有升级现行 ReceiptIntent/1、正式 imports 或通用 ReplayPhaseI，故仍 partial。 |
| SV-30 | R | L1a | P | v2 在 `REEXEC_AUDIT_ONLY` 下省略 `verified_claim_spec`，其余方法要求合法 `VerifiedClaimSpec` 对象；Profile v2 已校验键在场性和顶层对象类型；完整 VerifiedClaimSpec 形状、正式 Profile wire 与注册接线待验收。 |
| SV-31 | R | L1a | I | 参数块互斥矩阵（§8.5）逐行成立；四方法冻结矩阵/声明约束已实现并独立对拍；只完成本规则，不授予完整参数/claim/import、SchemaValid、统计来源或部署资格。 |
| SV-32 | R | L1a | I | 不含 `post_execution_predicate` 字段（迁移检查）；方法无关注册规则 helper 已在四种方法下独立 Python/Rust 对拍；非 audit 参数/claim 块在规则专用向量中为未检验占位，完整方法、注册授权和 Phase R 其余规则不由本项通过授予。 |
| SV-33 | R | L1a | I | 每个 `AssumptionReference` 的 `revocation_mapping` 三阶段字段齐备；方法无关注册规则 helper 已在四种方法下独立 Python/Rust 对拍；非 audit 参数/claim 块在规则专用向量中为未检验占位，完整方法、注册授权和 Phase R 其余规则不由本项通过授予。 |
| SV-35 | D | L1b | I | `concrete_bindings` 键集合 = `binding_schema`；`STATIC` 槽位值与 `static_bindings` 逐位相同（CB-1）；concrete_bindings 键集合与 schema 精确相等；STATIC 外壳和值逐位等于 Profile 冻结绑定，即使重算 claim digest 也不能替换。 |
| SV-36 | D | L1b | I | `terminal_state = TRUSTED` ⇒ `claim_binding` 完整（D-08-a）；TRUSTED 输入必须有完整、方法匹配的 ClaimBinding；audit 不得携带 claim。仅组件 guard，不重放 evaluator 或产生 Decision。 |
| SV-37 | R | L1a | I | `role = SAFETY_CRITICAL` ⇒ `revocation_mapping` 恰为 AR-1 的三元组，无 `PROCEED`/`NO_EFFECT`；方法无关注册规则 helper 已在四种方法下独立 Python/Rust 对拍；非 audit 参数/claim 块在规则专用向量中为未检验占位，完整方法、注册授权和 Phase R 其余规则不由本项通过授予。 |
| SV-38 | R | L1b | I | 方法必需的 `assumption_class` 与 `role` 齐备（AR-2）；方法无关注册规则 helper 已在四种方法下独立 Python/Rust 对拍；非 audit 参数/claim 块在规则专用向量中为未检验占位，完整方法、注册授权和 Phase R 其余规则不由本项通过授予。 |
| SV-39 | R | L1b | I | `decision_mapping.rules` 顺序与 §11.3 冻结优先级一致；`default = UNRESOLVED`；该条规则已在原始 CBOR Phase R 入口实现。完整 SchemaValid、registry/source 与其他 SV 独立验收。 |
| SV-41 | R | L1b | I | `SelectionPolicy` 展开后 slot index 唯一、gate 按 slot 携带（**不含 `policy_digest`**，该职责归 SV-53b）；slot index 唯一；gate 属于每次候选出现的 slot，不按 ProfileID 合并；同一 Profile 可重复出现并有不同 gate。 |
| SV-42 | R | L2 | P | 容器 canonicality：map key 顺序、集合/规范 pair-array 排序去重、`Rational` 既约；不检查 primitive 禁令、整数域或摘要；支持切片 map、pair-array、text-set、Rational；全协议容器类型未覆盖。 |
| SV-43 | I | L1b | P | `DEGRADED` slot 的 `failure_reasons[degraded_from] ⊆ enabling_triggers`（D-06）；测试原因标签的全集包含判定及混合非触发原因跳过已对拍；`degraded_from` 的来源 slot 索引、正式 FailureReason/触发投影及 D-06 接线尚未完成。测试入口还要求非空失败事实。 |
| SV-44 | R | L1b | I | `static_bindings` 的每个值与 method parameters 对应字段逐位相同（CS-2）；Direct/Proof/Bounded 的全部规范 STATIC 对应字段使用显式映射、锁定载荷 schema 和原生 CBOR 字节比较；不是第二份参数权威。 |
| SV-45 | F | L1b | I | 选中 slot 的 `profile_digest` 与注册表中该 Profile 的实际 digest 一致；slot、实际 Profile 重算摘要和显式快照中的完整三元引用逐位一致，拒绝摘要单值或跨版本替换。 |
| SV-46 | D | L2 | I | `rendered_claim_digest` 按 §5.1.1 与 §17.4 正确（CB-2）；正式 RenderedClaim/1 对完整 [template_ref, concrete_bindings] 重算；支持已锁定的通用原生载荷与外部版本引用，不再限定 claim-test-bytes；不验证任务性质。 |
| SV-47 | R | L1b | I | `calibration_ref` 指向本 Profile 中 `assumption_class = CALIBRATION` 且 `role = LIVENESS` 的条目（LP-5）；calibration_ref 唯一解析到本 Profile 的 CALIBRATION/LIVENESS，未知引用与错误类/角色拒绝。 |
| SV-48 | R | L1b | I | `claim_template_ref` 的 `template_digest` 与注册表中模板实际 digest 一致；模板状态 ∈ {`REGISTERED`, `ACTIVE`}；模板实际对象、三元引用和显式快照一致；只允许 REGISTERED/ACTIVE。未证明快照/注册来源真实。 |
| SV-49 | R | L1b | I | Profile 侧以 `VersionRange` 约束的量，其同名 claim 槽位为 `RUNTIME`（CS-4）；已冻结 VersionRange 字段到声明 slot 的显式映射，相关 slot 必须 RUNTIME；约束范围不等于运行时点值。 |
| SV-50 | R | L1a | N | 无嵌套 `[ADVISORY]`：该标记只出现在顶层字段（§17.6）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-51 | R | L1a | I | 适用方法的 `decision_mapping.rules` 含 `EXECUTION_FAILED`；对象内不存在可覆盖 `CanonicalTerminal` 的 terminal 字段（§11.3.5）；四方法冻结矩阵/声明约束已实现并独立对拍；只完成本规则，不授予完整参数/claim/import、SchemaValid、统计来源或部署资格。 |
| SV-52 | R | L2 | P | 整数唯一 owner：无 CBOR bignum（tag 2/3）、最短整数；`int` ∈ [−2⁶³, 2⁶³−1]，`uint` ∈ [0, 2⁶⁴−1]（§17.5A）；最短编码、int64/uint64 和 bignum 拒绝已对拍；完整类型表与所有对象尚未接入。 |
| SV-53a | R | L1b | I | `expanded_slots == Expand(ordered_candidates)`（结构派生复算）；按 D-06 候选顺序逐位复算 primary 及紧邻 degraded slot，index 为从 0 开始的展开位置；已声明 gate 只复制到所属 primary slot，degraded_from 指向该来源位置。 |
| SV-53b | R | L2 | I | `policy_digest` 按 §17.4 同时绑定 `ordered_candidates` 与 `expanded_slots`；SelectionPolicy 的正式 tag/ContentMap 同时覆盖 ordered_candidates、expanded_slots 与 on_none_applicable；身份/版本不入摘要。 |
| SV-54a | D | L1b | P | 当 `assumption_evaluation = COMPLETE(snapshot)` 时，状态行恰好覆盖 `SAFETY_CRITICAL/LIVENESS`、排除 `INFORMATIONAL`；行与 `cause_set` 排序去重；`effective_verdict = Reduce(reducer_ref, cause_set)`；`INVALIDATING` 分支不要求快照；新增原始 CBOR 状态组件：精确角色覆盖、证据版本、编码字节排序与默认 reducer 复算；保留全部原因。正式 sum wire、Phase D 与 reducer 发布/来源闭合仍缺。 |
| SV-54b | D | L2 | I | `assumption_state_digest` 按 §17.4 重算一致（owner）；AssumptionState/1 精确覆盖 [reducer_ref, sorted(rows)]；不把 Receipt/id 混入该派生摘要。源码与字节向量独立对拍。 |
| SV-55 | I | L1b | P | 每个 `SAFETY_CRITICAL`/`LIVENESS` 假设满足 `Intent ⊑ scope`（AR-4）；纯 ScopeContains 已覆盖标量相等、半开版本区间和 Intent⊆Scope；仅检查 SAFETY_CRITICAL/LIVENESS，INFO 不影响结果。正式 Intent→DeclaredScope 投影仍缺。 R8 已有独立 TEST tag 的候选输入胶囊派生与字节绑定，但没有升级现行 ReceiptIntent/1、正式 imports 或通用 ReplayPhaseI，故仍 partial。 |
| SV-57 | D | L1b | P | `terminal_state = TRUSTED` ⇒ `assumption_evaluation = COMPLETE(snapshot)` 且全部 `SAFETY_CRITICAL` 假设的 `effective_verdict = VALID`（AS-1/ASS-7）；COMPLETE 分支和所有 safety-critical VALID guard 已在新组件接入并覆盖重算摘要后的反例；完整 evaluator/Phase D/主网准入未验收，不产生 Decision。 |
| SV-58 | I | L1b | P | `NormalizeDeclaredScope(Intent)` 六维齐备，且 `fault_domains`、`geography` 非空（SC-1）；显式 DeclaredScope 六维、类型与非空 fault_domains/geography 已对拍；当前冻结 ReceiptIntent 没有直接提供全部字段，不能从不透明 ContractTuple 猜内部结构，NormalizeDeclaredScope 接线未完成。 R8 已有独立 TEST tag 的候选输入胶囊派生与字节绑定，但没有升级现行 ReceiptIntent/1、正式 imports 或通用 ReplayPhaseI，故仍 partial。 |
| SV-59 | R | L1a | I | `ScopeSpec` 六维齐备，无可选维度（SC-1）；方法无关注册规则 helper 已在四种方法下独立 Python/Rust 对拍；非 audit 参数/claim 块在规则专用向量中为未检验占位，完整方法、注册授权和 Phase R 其余规则不由本项通过授予。 |
| SV-60 | R | L2 | P | **仅对版本化对象**：若 `ContentMap(a) == ContentMap(b)` 且二者只在 ID/Version 上不同，则 `Digest(a) == Digest(b)`（UVP-1V）。运行期对象因 `id` 入 ContentMap 不适用；只验证 ClaimTemplate 身份/版本/advisory 排除；其他版本化对象未覆盖。 |
| SV-61 | R | L1b | N | 相对前一版本：改内容字段 ⇒ `MAJOR` +1 且 digest 改变；仅改 `[ADVISORY]` ⇒ `MINOR` +1 且 digest 不变；仅改排版 ⇒ `PATCH` +1 且 digest 不变（§3.3、§3.5）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-62 | R | L1b | P | 引用类型正确：版本化 UVP 对象用 `VersionedObjectRef`；不版本化运行期产物用对应 `RuntimeObjectRef<IDType>` 具体别名；外部工程组件用 `ExternalVersionedObjectRef`，不得伪装成 `RegistryObjectKind`；任何引用不得只给 `Digest`（REF-1—REF-6）；模板及 audit R3 外部载荷的结构化版本引用已有局部绑定；其他运行对象、外部组件授权和官方 import 全集仍缺。 R9 的 ClusterMappingRef 使用封闭 {id,digest} 与 ClusterMappingID，拒绝 Version 与跨 ID 域；其他引用全集仍未闭合。 |
| SV-63 | R | L1a | I | `DecisionMapping.rules` 是 `[DecisionCondition]`，**不含** `terminal` 字段；无 `CanonicalTerminal` 覆盖字段（§11.3.2）；该条规则已在原始 CBOR Phase R 入口实现。完整 SchemaValid、registry/source 与其他 SV 独立验收。 |
| SV-64 | R | L1b | P | `reachable_terminals` 恰等于 `CanonicalTerminal[rules] ∪ {UNRESOLVED}`；不重复检查 rules 集合（归 SV-20）；Audit wire 与四方法派生 RT-1/helper 已对拍；非 audit 参数类型未声明 reachable_terminals 的承载字段，适配器预期值不能代替正式 wire。 |
| SV-65 | R | L1b | P | 投影 \(\Pi\)（§11.3.2A）未被 Profile 覆盖或参数化；冻结方法结果/聚合耗尽行已有纯函数模型并拒绝自定义投影输入；完整 AggregateState/evaluator contract、共通来源行与 Phase D 尚未接入。 |
| SV-66 | R/I/F/B/D | L1a | P | 相位输入是合法 discriminated union；Phase B payload 为 §13.0.4 七个封闭变体之一；Phase D 必带完整 `evaluation_input`。不重复检查 bundle 内部结构（归 SV-91）；本片只接 audit Phase R；其他方法/相位的信封接线仍缺，测试导入绑定不构成正式 schema import 或完整 SchemaValid。 R9 新增完整显式 B bundle 绑定/闭合 DAG 检查，其他相位及正式 imports/部署接线仍未全部验收。 |
| SV-68 | B | L1b | I | Lease 激活与 Snapshot 冻结时，对每个 `SAFETY_CRITICAL`/`LIVENESS` 假设检查 `ScopeContains(scope, ActualBoundScope)`（SB-1）；R9 已实现该 Type A 显式输入结构/绑定/状态守卫，并有独立 Python/Rust 正负向量；使用带外 pin 的 TEST snapshot imports。不代表完整正式 Phase B conformance、实际事件/Lease/总体来源忠实性、状态原子写入或生产准入。 |
| SV-69 | B | L1b | P | `EligibilitySnapshot.population_definition` 的每个抽样单位落在 scope 内（SB-2）；R9 已逐单位比较显式快照适配器中的六维 scope；尚未冻结真实 population_definition imported schema，无法证明适配器列出的单位/属性与正式总体定义完整一致，保留 partial。 |
| SV-70 | R | L2 | I | `template_digest` 按 §17.4 与 UVP-1V 重算一致（owner）；完整 ContentMap_Template 与正式 tag 已重算；原生 value_type/ENUM 内容按原始 CBOR 保留，不猜 ENUM wire。L1a 类型语义和完整注册另验收，摘要 owner 不承担该职责。 |
| SV-71 | D | L2 | I | `AssumptionStateSnapshot.snapshot_digest` 按 §17.4 重算一致（owner）；AssumptionStateSnapshot/1 覆盖 runtime id、Receipt、instant、reducer 和全部行；不同于仅 reducer/rows 的派生状态摘要。 |
| SV-72 | R | L2 | I | `excluded_claims.digest` 按 §17.4 重算一致（owner）；方法无关排除选择/注册对象 helper 与限定 audit R3 入口已实现，独立 Python/Rust 固定字节对拍通过；完整 Profile/注册授权/五相位仍待验收。 |
| SV-73 | R | L2 | I | `assumption_set_digest` 按 §17.4 重算一致（owner）；方法无关注册规则 helper 已在四种方法下独立 Python/Rust 对拍；非 audit 参数/claim 块在规则专用向量中为未检验占位，完整方法、注册授权和 Phase R 其余规则不由本项通过授予。 |
| SV-74 | R | L2 | I | `manifest_digest` 按 §17.4 重算 `ContentMap_Manifest` 并逐位比较（owner；CM-2）；Manifest 正式 tag/完整 ContentMap 与摘要比较；仅检查已声明清单，不读取文件或给测试资产授予语义注册权。 |
| SV-75a | R/I/F/B/D | L1b | P | `registry_snapshot_ref` 可解析；`bundle.registry_snapshot` 的三元组与该引用逐位一致（CTX-6）；R9 新增完整显式 B bundle 绑定/闭合 DAG 检查；D 相位在重放中复用同一等式。I/F 相位信封、正式 imports/部署接线及注册来源真实性仍未全部验收。 |
| SV-75b | R/I/F/B/D | L2 | I | 对**显式提供的** `RegistrySnapshot` 原始字节重算 `registry_snapshot_digest`（owner；CTX-10：L2 不得取远程对象）；规则级纯摘要/注册条目检查已实现并经独立 Rust 固定字节对拍；不代表完整相位、来源认证或生产准入。 |
| SV-76 | R | L1b | I | `assumption_id` 在一个 Profile 内唯一（ASS-3）；局部 assumption_id 唯一性已实现。 |
| SV-77 | B | L1a | I | `ActualBoundScope` 六维齐备，且 `fault_domains`、`geography` 非空（SC-1）；R9 已实现该 Type A 显式输入结构/绑定/状态守卫，并有独立 Python/Rust 正负向量；使用带外 pin 的 TEST snapshot imports。不代表完整正式 Phase B conformance、实际事件/Lease/总体来源忠实性、状态原子写入或生产准入。 |
| SV-78 | D | L1b | I | 当产生 `TRUSTED` 时，`COMPLETE(snapshot)` 的 identity 与 `claim_binding.assumption_state_snapshot_ref` 一致且 snapshot.receipt_id 匹配；其他终态按方法规则允许无 ClaimBinding；ClaimBinding 与 COMPLETE snapshot 的完整 runtime 引用、实际 ReceiptID 一致；其他终态允许无 ClaimBinding，INVALIDATING 不要求快照。 |
| SV-79 | R | L1b | I | `RegistrySnapshot.entries` 按 RS-1 排序、按 RS-2 去重；`object_kind` ∈ 封闭枚举（RS-3；「不含快照自身」是该封闭枚举的结构推论，在 L1a 即被拒，见 RS-4）；规则级纯摘要/注册条目检查已实现并经独立 Rust 固定字节对拍；不代表完整相位、来源认证或生产准入。 |
| SV-80 | R | L1a | P | 全部标识符符合 §3.2 的封闭语法与注册域；表外 ID 形态 MUST 被拒（M-05）；`identifier` 已覆盖 §3.2 的封闭语法与部分注册域（Profile/Task/Assumption/Registry 等 ID 类型）；注册域完整性（如 ClaimSpecID 的 Profile 内唯一性登记）及其他标识符全集仍待完成。 |
| SV-81 | B | L1b | P | `REEXEC_BOUNDED` 的 `EligibilitySnapshot` 满足 PB-1—PB-4 四条绑定等式（owner，§13.1B）；R9 已实现 PB-1—PB-4 的显式引用、总体基数以及 pinned TEST commitment 方案/参数集合检查；当前参数引用及方案为 opaque TEST imports，正式版本化 population/schema/randomness 合约、来源认证与具体 verifier 尚未冻结，保留 partial。 |
| SV-82 | B | L1b | I | `sampling_units` ID 唯一（PB-5）；`EligibilitySnapshot.cluster_mapping_ref` 存在（PB-5b）；R9 已实现该 Type A 显式输入结构/绑定/状态守卫，并有独立 Python/Rust 正负向量；使用带外 pin 的 TEST snapshot imports。不代表完整正式 Phase B conformance、实际事件/Lease/总体来源忠实性、状态原子写入或生产准入。 |
| SV-84 | R | L1b | I | `supersedes` 若存在，是完整三元组且所指对象在 `RegistrySnapshot` 中可解析（UVP-4）；方法无关注册规则 helper 已在四种方法下独立 Python/Rust 对拍；非 audit 参数/claim 块在规则专用向量中为未检验占位，完整方法、注册授权和 Phase R 其余规则不由本项通过授予。 |
| SV-85 | R | L1a | I | `ConformanceManifest.header` 提供唯一 `(id, version, digest)`，不得接受扁平重复字段；`file_digests` 的 path 使用正斜杠相对路径（CM-1、CM-5）；Manifest 唯一嵌套 header，拒绝扁平重复身份、绝对路径、反斜杠、drive 路径和 NUL；文件路径升序唯一。不进行文件系统读取，允许相对父路径作为清单数据。 |
| SV-86a | R | L1a | I | 版本化对象严格使用 §3.3.2 为该对象冻结的唯一 wire shape；不得同时接受嵌套/展开两种形态；八种版本化治理对象的唯一 wire shape 已集中检查；Profile 为 FLAT，其余为 NESTED_HEADER。只关闭 header shape owner，不代表全部嵌套 schema 已完成。 |
| SV-86b | R/I/F/B/D | L1a | I | 运行期对象严格使用 `NESTED_HEADER`；无 `version`；`header.id` 经 UVP-1R 投影进入 ContentMap；四类 RuntimeObjectHeader 使用嵌套 header，无 version，且 id 进入各自 ContentMap；运行期摘要与身份可独立对拍。 |
| SV-86c | R/I/F/B/D | L1a | I | 对象未在 header 外重复声明 `id`/`version`/`digest`；扁平 Profile 不得额外出现 `header`；八类版本化与四类运行期治理对象拒绝 header 外重复身份/摘要字段；扁平 Profile 拒绝额外 header。 |
| SV-87 | R | L1a | I | `ProfileSelectionPolicy.expanded_slots` 字段存在于对象结构且列入 `ContentMap_Policy`（§3.3.3）；Policy 唯一嵌套 header wire，expanded_slots 字段必填且进入正式 ContentMap；缺字段/重复身份/未知字段拒绝。 |
| SV-88 | R | L2 | I | `edge_digest` 按 §17.4 重算 `ContentMap_WeakeningEdge`（owner）；WeakeningEdge 正式 tag/ContentMap 重算；source/target/class/可选 evidence_ref 均被摘要绑定。 |
| SV-89 | R | L2 | I | `ExcludedClaimsRegistry.registry_digest` 按 §17.4 重算（owner）；方法无关排除选择/注册对象 helper 与限定 audit R3 入口已实现，独立 Python/Rust 固定字节对拍通过；完整 Profile/注册授权/五相位仍待验收。 |
| SV-90 | R | L1b | I | `RegistryEntry` 的每个 `object_kind`（含 `MAINNET_ASSURANCE_PROFILE`）都有可解析的 `VersionedObjectRef`（RS-7）；规则级纯摘要/注册条目检查已实现并经独立 Rust 固定字节对拍；不代表完整相位、来源认证或生产准入。 |
| SV-91 | R/I/F/B/D | L1a | P | `bundle.context`、`registry_snapshot`、`event_frontier_snapshot` 均在场；两个快照字段缺一即拒绝；本片只接 audit Phase R；其他方法/相位的信封接线仍缺，测试导入绑定不构成正式 schema import 或完整 SchemaValid。 R9 新增完整显式 B bundle 绑定/闭合 DAG 检查，其他相位及正式 imports/部署接线仍未全部验收。 |
| SV-92 | B | L1b | I | Receipt/Profile/MainnetAssurance 完整绑定链；RB-3 仅在 payload 携带快照时求值，network/assurance 引用逐位一致；R9 已实现该 Type A 显式输入结构/绑定/状态守卫，并有独立 Python/Rust 正负向量；使用带外 pin 的 TEST snapshot imports。不代表完整正式 Phase B conformance、实际事件/Lease/总体来源忠实性、状态原子写入或生产准入。 |
| SV-93 | B | L1a | I | `PhaseBEnvelope.payload` 恰为 §13.0.4 七个 tagged union 变体之一，字段集合精确匹配且 transition 必填；R9 已实现该 Type A 显式输入结构/绑定/状态守卫，并有独立 Python/Rust 正负向量；使用带外 pin 的 TEST snapshot imports。不代表完整正式 Phase B conformance、实际事件/Lease/总体来源忠实性、状态原子写入或生产准入。 |
| SV-94 | B | L1b | I | 状态转换约束 PB-6—PB-9、RG-1/RG-2 与 NS-1—NS-3，使用显式状态、方法、绑定和因果快照判定（owner，§13.1B.2A）；PB-6—PB-9、RG-1/RG-2 与无快照轮次的显式输入谓词及正负例已实现；仍使用 TEST Snapshot/事件输入，不认证来源、不写状态，也不产出正式 Decision。 |
| SV-95 | I/F/B/D | L1b | I | 四类运行期对象无伪 `Version`，且引用使用对应具体别名（REF-2）；REF-2 的四类具体 runtime alias 检查 ID 命名域、digest 和无伪 version；不同 runtime 类型不能互换。 |
| SV-96 | I/F | L1b | P | I 期 transcript 满足 CC-2I；F 期满足 CC-2F 与 CC-3。CC-1 只由 SV-101 检查；固定 audit 路径已实现 CC-2I、CC-2F、Profile 三元身份及 Intent/selected_slot 比较；通用 I/F 类型与其他方法路径尚未接入。 |
| SV-97 | I/F | L2 | I | `context_digest` 按 §17.4 重算 `ContentMap_CreationValidationContext`（owner）；CreationContext 全部冻结字段按正式 tag 重算；运行期 ID 入摘要。正式导入/来源认证与其他相位规则独立验收。 |
| SV-98 | I/F | L1a | P | I 期输出以 `PhaseIValidationTranscript` 物化；F 期携带完整 `phase_i_transcript`、`creation_context`、`profile` 与 `phase_f_event_ref`；I transcript 与 F 完整字段、内联对象在测试 import lock 下封闭；正式 MainnetAssuranceProfile/ContractTuple 等导入尚未验收。 |
| SV-99 | B | L1b | I | PB-5b 完整映射链：Snapshot、prior、proposed，以及冻结时的 freeze record 逐位相等；R9 已实现该 Type A 显式输入结构/绑定/状态守卫，并有独立 Python/Rust 正负向量；使用带外 pin 的 TEST snapshot imports。不代表完整正式 Phase B conformance、实际事件/Lease/总体来源忠实性、状态原子写入或生产准入。 |
| SV-101 | I/F | L1b | I | CC-1 的 evaluation instant 与 registry snapshot 两字段等式；这是 CC-1 的唯一 owner。CreationContext 不绑定会随相位推进的 event frontier；CC-1 的 instant/RegistrySnapshot 两字段由独立 helper 比较；不绑定相位间递进的 frontier，也不证明时钟或注册表来源真实。 |
| SV-102 | I/F | L1b | P | CC-4 与 CC-6：record 绑定当前 Intent/slot，且 `ReplayPhaseI` 的 outcome/failure_reasons 逐位一致；CC-4 和固定 audit TEST 的 CC-6 投影已完成；ReplayPhaseI 仍是 opaque ContractTuple 精确比较，不覆盖通用 admission predicate、scope、gate、降级求值与失败原因 wire。 |
| SV-103 | I/F | L2 | I | `phase_i_record_digest` 按 §17.4 重算（owner）；PhaseIValidationRecord 的完整冻结 ContentMap、正式 tag 与摘要比较；记录是否对应有效选择仍由 102/110 分别验收。 |
| SV-104 | I/F | L2 | I | `intent_digest` 按 §17.4 对 `ContentMap_ReceiptIntent` 重算（owner；CTX-13）；ReceiptIntent 封闭 ContentMap 与正式 tag，输入数组保序保重复，RI-1 恰一选择引用；record 的 intent_digest 重算比较。导入对象的内部语义不属于此摘要 owner。 |
| SV-105 | B | L1b | I | `round_stage` 单调，且方法、payload 与阶段转换满足 RG-1/RG-2；round_stage 单调及 RG-1/RG-2 的七个 payload 分支已覆盖；事件来源、状态写入和完整正式 Phase B 另行验收。 |
| SV-106 | B | L1b | I | 集群映射首次固定与不变性：CM-FIX-1—CM-FIX-3；`round_stage ⪰ FROZEN_PRE_DRAW` 后 `cluster_mapping_ref` 不变；R9 已实现该 Type A 显式输入结构/绑定/状态守卫，并有独立 Python/Rust 正负向量；使用带外 pin 的 TEST snapshot imports。不代表完整正式 Phase B conformance、实际事件/Lease/总体来源忠实性、状态原子写入或生产准入。 |
| SV-107 | B | L1b | I | PB-6 的两个事件在显式 `EventFrontierSnapshot` 中解析为正确 kind/subject，且按 EF-3 满足 `Precedes`；R9 已实现该 Type A 显式输入结构/绑定/状态守卫，并有独立 Python/Rust 正负向量；使用带外 pin 的 TEST snapshot imports。不代表完整正式 Phase B conformance、实际事件/Lease/总体来源忠实性、状态原子写入或生产准入。 |
| SV-108 | R/I/F/B/D | L2 | I | `event_frontier_digest` 按 §17.4 重算 `ContentMap_EventFrontierSnapshot`（owner）；规则级纯摘要/注册条目检查已实现并经独立 Rust 固定字节对拍；不代表完整相位、来源认证或生产准入。 |
| SV-109 | R/I/F/B/D | L1b | P | EventFrontierSnapshot 身份与 context 引用一致；事件排序、唯一、闭合、无环，frontier 存在（EF-1—EF-4）；本片只接 audit Phase R；其他方法/相位的信封接线仍缺，测试导入绑定不构成正式 schema import 或完整 SchemaValid。 R9 新增完整显式 B bundle 绑定/闭合 DAG 检查，其他相位及正式 imports/部署接线仍未全部验收。 |
| SV-110 | F | L1b | P | CC-5：Phase I/F 事件 kind 与 subject 正确，且 `Precedes(produced_by_event, phase_f_event_ref)`；显式已校验 DAG 内 I/F kind、I subject、严格祖先关系已有 Python/Rust 对拍；EventRef、日志 proof 与正式相位来源仍用测试导入，未做正式全路径验收。 |
| SV-112 | D | L1b | I | 从 `BoundaryObservation` 的显式 funding/deadline refs 与事件 DAG 调用 `ResolveBoundary`；事件缺失、kind/subject 错误先产生 invalidating；Phase D 审计候选入口与双语向量覆盖显式边界、因果顺序和无效事件。权威来源和日志认证另行验收。 |
| SV-113 | R | L2 | I | `MainnetAssuranceProfile.assurance_digest` 按 §17.4 重算；`human_summary` 不入摘要；完整 MAP ContentMap 使用 MainnetAssuranceProfile/1，排除 human_summary 与 ID/Version；只关闭摘要 owner，不接受主网发布、签名或能力启用。 |
| SV-114 | D | L2 | I | `DecisionEvaluationRecord.input_digest` 对完整 `DecisionEvaluationInput` 按 §17.4 重算一致；DecisionEvaluationInput/1 覆盖完整七字段显式输入和内联 canonical_input 包装；不是 evaluator 重放或 SV-115/完整 Phase D 验收。 |
| SV-115 | D | L1b | P | 重放 method evaluator；重算 condition vector、`FirstTrue`、`CanonicalTerminal`，并要求与 Decision.terminal_state 逐位一致（DE-1—DE-3）；固定 REEXEC_AUDIT_ONLY evaluator 已有 Python/Rust 重放、R11 来源投影、R12 候选编码、R13 独立对拍和 R14 B/D 信封；其他方法、正式 evaluator/import 合约与完整正式 Phase D 仍缺。 |
| SV-116 | D | L1a | P | `AssumptionEvaluationResult` 恰为 `COMPLETE(snapshot)` 或 `INVALIDATING(failure)`；两分支字段互斥且完备；COMPLETE(snapshot)/INVALIDATING(failure) 的封闭结构和可构造失败路径已有原始 CBOR 组件；tag/snapshot/failure 是本片规范化适配器，正式 sum wire/Phase D 接线仍待评审。 |
| SV-117 | I/F/B/D | L1b | P | `MainnetAssuranceProfile` 的 network、窗口、Profile capability、组件/ExecutionCapability contract/reducer 允许集合与损失上限绑定；未 `ENABLED` 的方法不得产生 `ACCEPT`；新版非主网分支按 §9.2.2 验证部署绑定；已检查非主网候选 I/F/B/D 的固定测试部署绑定、来源引用、窗口、资金上限与签名撤销；仍缺主网 MAP 的 network/窗口/Profile capability、组件/ExecutionCapability contract/reducer 允许集合与损失上限绑定，未 `ENABLED` 方法不得产生 `ACCEPT` 的检查，以及正式 §9.2.2 信封、来源注册/授权与撤销传播/新鲜性验收。 |
| SV-118 | R/I/F/B/D | L2 | P | `ToSchemaView/FromSchemaView` 可逆；输入满足 primitive/key 限制；`cbor_hex` 与 `schema_view` 向量逐位一致；候选 ClaimTemplate/claim 切片的 Schema View 可逆、primitive/key 限制和字节对拍已完成；全对象 wire-key 表与五相位投影尚未冻结。 |
| SV-119 | R/I/F/B/D | L1b | P | 按 `log_backend_ref` 验证 checkpoint finality、EventRecord inclusion/consistency，并与 MainnetAssuranceProfile 逐位绑定（EF-6/EF-7）；FM-S2/FM-S3 测试后端已校验签发者 checkpoint 签名、线性前缀重放/包含、预期 checkpoint 精确匹配及外部 anchor 一致性；仍缺按 `MainnetAssuranceProfile.log_backend_ref` 绑定后端、该后端的 checkpoint finality 与逐 EventRecord inclusion/consistency 证明。精确 pin 不是 finality oracle；OQ-04/OQ-05 的时钟/日志终局性合约未冻结，全相位来源认证未验收。 |
| SV-120 | R/I/F/B/D | L1b | I | `CausalEventRecord.event_kind -> subject_ref` 满足 EF-4a 封闭矩阵；完整十类 event kind→subject 封闭矩阵，subject 必填、类型正确且无未知字段；此 helper 不认证日志或替代 snapshot 版本检查。 |
| SV-121 | D | L1b | P | `ExecutionObservation` 投影：合法 closure 且零有效提交才产生 `EXECUTION_FAILED`；source unavailable/malformed 产生 invalidating；已实现并测试 source unavailable/malformed/untrusted 的失效投影、合法闭合的 Receipt/合约/摘要/事件绑定，以及零有效提交且未开始验证才产生 `EXECUTION_FAILED`；仍缺正式闭合摘要合同（现为 `ACLT/TEST/R10/ExecutionClosure/1` 测试编码）、观察方/入口的权威来源授权与正式来源验收。 |

## 18 个摘要

全部 implemented：现行公式/ContentMap 或完整显式输入投影已有实现与直接测试。此状态不关闭其他 L2 规则、未冻结的 ENUM/正式 wire、完整五相位或 SchemaValid。

| 摘要 | tag | 输入 | 唯一 owner | 状态 |
|---|---|---|---|---|
| `profile_digest` | `ACLt/P0-1/Profile/2` | `cbor(ContentMap_Profile)`（§3.3.3） | SV-02 | I |
| `policy_digest` | `ACLt/P0-1/SelectionPolicy/1` | `cbor(ContentMap_Policy)`（§3.3.3；**含 `on_none_applicable`**） | SV-53b | I |
| `template_digest` | `ACLt/P0-1/ClaimTemplate/1` | `cbor(ContentMap_Template)`（§3.3.3） | SV-70 | I |
| `rendered_claim_digest` | `ACLt/P0-1/RenderedClaim/1` | `cbor([claim_template_ref, concrete_bindings])` | SV-46 | I |
| `assumption_state_digest` | `ACLt/P0-1/AssumptionState/1` | `cbor([reducer_ref, AssumptionStateRows])`（§5.2.2） | SV-54b | I |
| `snapshot_digest`（`AssumptionStateSnapshot`） | `ACLt/P0-1/AssumptionStateSnapshot/1` | `cbor(ContentMap_AssumptionStateSnapshot)`（§3.3.3） | SV-71 | I |
| `excluded_claims.digest` | `ACLt/P0-1/ExcludedClaims/1` | `cbor([registry_ref, sorted(exclusion_ids)])`（派生摘要值） | SV-72 | I |
| `assumption_set_digest` | `ACLt/P0-1/AssumptionSet/1` | `cbor(sorted([[assumption_id, statement_digest], ...]))` | SV-73 | I |
| `manifest_digest` | `ACLt/P0-1/Manifest/1` | `cbor(ContentMap_Manifest)`（§3.3.3、§3.4） | SV-74 | I |
| `edge_digest` | `ACLt/P0-1/WeakeningEdge/1` | `cbor(ContentMap_WeakeningEdge)`（§3.3.3、§6.5） | SV-88 | I |
| `registry_digest`（`ExcludedClaimsRegistry`） | `ACLt/P0-1/ExcludedClaimsRegistry/1` | `cbor(ContentMap_ExcludedClaimsRegistry)`（§3.3.3、§6.3） | SV-89 | I |
| `assurance_digest`（`MainnetAssuranceProfile`） | `ACLt/P0-1/MainnetAssuranceProfile/1` | `cbor(ContentMap_MainnetAssuranceProfile)`（§3.3.3、§3.6） | SV-113 | I |
| `DecisionEvaluationRecord.input_digest` | `ACLt/P0-1/DecisionEvaluationInput/1` | `cbor(DecisionEvaluationInput)`（§11.1；完整显式输入） | SV-114 | I |
| `context_digest`（`CreationValidationContext`） | `ACLt/P0-1/CreationContext/1` | `cbor(ContentMap_CreationValidationContext)`（§3.3.3、§13.0.2） | SV-97 | I |
| `registry_snapshot_digest` | `ACLt/P0-1/RegistrySnapshot/1` | `cbor(ContentMap_RegistrySnapshot)`（§3.3.3、§3.5；`entries` 排序去重见 RS-1/RS-2） | SV-75b | I |
| `phase_i_record_digest` | `ACLt/P0-1/PhaseIValidationRecord/1` | `cbor(ContentMap_PhaseIValidationRecord)`（§3.3.3、§13.0.2） | SV-103 | I |
| `intent_digest` | `ACLt/P0-1/ReceiptIntent/1` | `cbor(ContentMap_ReceiptIntent)`（§3.3.3、CTX-13） | SV-104 | I |
| `event_frontier_digest` | `ACLt/P0-1/EventFrontierSnapshot/1` | `cbor(ContentMap_EventFrontierSnapshot)`（§3.3.3、§13.0.1） | SV-108 | I |

## Type B、作废与延期项

6 项 Type B 不计入 P0-1B Type A 关闭数：

| ID | 相位 | 检查 | 说明 |
|---|---|---|---|
| SV-24 | R | Profile 不含以 Principal 身份、`PerformanceEvidence`、`CapabilityEstimate`、资金状态或维护报告为输入的字段 | 不计入 P0-1B Type A；须独立处理其工程义务或延期/作废状态。 |
| SV-34 | R | `cost_parameters` 无字段被任何合法性判断读取（静态数据流） | 不计入 P0-1B Type A；须独立处理其工程义务或延期/作废状态。 |
| SV-56 | R | 实现 MUST NOT 把 `INVALID_SAMPLE` 实现为重抽、从总体移除或不消耗单位（FM-3）。这是实现行为而非 Profile 字段，Profile 无法表达，故为 Type B | 不计入 P0-1B Type A；须独立处理其工程义务或延期/作废状态。 |
| SV-67 | — | validator MUST NOT 自行读取时钟、随机性或网络；判定时刻只来自 `ValidationContext`（CTX-2） | 不计入 P0-1B Type A；须独立处理其工程义务或延期/作废状态。 |
| SV-100 | — | 官方主网实现不得绕过 MAP-6 日志后端写入或用未 finalized 事件改变协议状态；由接口审计、故障恢复和链/透明日志对账承担 | 不计入 P0-1B Type A；须独立处理其工程义务或延期/作废状态。 |
| SV-111 | — | Assignment/Dispatch 只能消费活动 Lease 已绑定的执行元组；实现不得绕过 Lease 或在 Dispatch 侧覆盖 scope 字段（DB-1—DB-3） | 不计入 P0-1B Type A；须独立处理其工程义务或延期/作废状态。 |

SV-15 作废（draft-2），原为 `cost_ratio_upper_bound < 1`；成本不决定接口合法性。SV-40 延期到 P0-5（DEFERRED）：终态后 qualification join 需要新的 `QualificationUpdateEnvelope` 与显式 update 集合，不计入 P0-1B Type A/B 关闭数。D-08-c 是额外 Type B 义务，不计入这 6 项 SV 计数。

## 横向缺口

- L2 仍为局部：SV-25/42/52/60/118。编码、容器、整数与 Schema View 只在已建模对象或切片上成立；全对象接入、完整容器类型表与逐对象摘要重算仍未完成。
- 五相位 envelope 未全接入：SV-66/91/98/116 等。Phase R/B 的显式信封与绑定已有实现；Phase I/F 的正式信封、Phase D 的完整 `evaluation_input` 接线与统一 bundle 入口仍缺。
- 注册表可解析，但只有种子数据，没有官方 ACTIVE 主网注册源或来源认证；`RegistrySnapshot` 检查不认证来源真实。
- 外部 Schema lock 是显式 caller pin（带外提供），不是官方导入权威；`runtime-imports-candidate-r9.json` 的 TEST imports 不构成正式注册授权。
- Python/Rust 已覆盖 R1–R9 及部分 R10–R16 切片（摘要、绑定、信封与判决重放），但不是全量第二语言 conformance：Rust 入口只覆盖已冻结切片，未覆盖全部规则与所有对象。
- 正式来源、人口与统计合同仍使用 TEST imports 或 opaque 引用（SV-69/81 等）；主网 MAP 绑定、日志后端 finality 与撤销传播/新鲜性未冻结。

## 下一批切片建议

按依赖排序，只作建议，切片范围由维护者决定。每片只列规则、前置与预计文件范围。

1. **B1：L2 编码与投影完整化（SV-25/42/52/118）**。前置：无；复用现有 codec 与 frozen vectors。预计文件：`tools/verification_profile/codec.py`、`tests/verification_profile/test_codec.py`、`tests/verification_profile/codec/`、`schemas/verification-profile/` 的相关 Schema 与向量。目标是把 primitive 禁令、整数域、容器 canonicality 与 Schema View 可逆从切片推进到全对象接入，并保持 Python/Rust 对拍。
2. **B2：版本、身份与引用完整化（SV-27/50/60/61/62/80）**。前置：B1。预计文件：`tools/verification_profile/profile.py`、`codec.py`、`references.py`、`registration.py`、`validator.py` 与对应测试。目标是 V1Admissible、版本变化规则、无嵌套 `[ADVISORY]`、ID 注册域与引用类型全集。
3. **B3：五相位 envelope 与 bundle 接线（SV-66/91/98/116，连带 SV-109/110/75a 的 I/F 分支）**。前置：B1、B2。预计文件：`validator.py`、`registration.py`、`runtime_bindings.py`、`decision_replay.py`、`creation.py` 与对应测试。目标是把 Phase I/F 正式信封、统一 bundle 入口与 Phase D `evaluation_input` 接入现有显式输入组件。
4. **B4：正式来源与主网绑定（SV-117/119/121 及 SV-69/81 等）**。前置：维护者冻结正式 population/schema/randomness 合约、`log_backend_ref`/finality 合同与 OQ-04/OQ-05 结论；不建议在合同冻结前实现。预计文件范围仅登记：`tools/verification_profile/deployment.py`、`tools/formal_migration/` 相关合同、`schemas/verification-profile/` 的相关合约。

## 规范勘误需求

只列不改。本轮核对未发现必须立即修正的规范矛盾，保留两项历史待确认：

- 10-23 报告指出的 SV-42 与 §17.4 表后历史说明不一致已在现行规范修正：§17.4 表后说明明确 SV-42 仅负责容器 canonicality，primitive 禁令归 SV-25，整数范围、最短整数与 bignum 禁令归 SV-52。该勘误已落地，本轮不再重复。
- §13.2 的 SV-61 引用“§3.3、§3.5”，但 UVP 版本变化规则位于 §3.3.4，§3.5 是 `RegistrySnapshot`。建议维护者确认是否应改为 §3.3.4；B0 不改规范。

## 未关闭范围与复查入口

P0-1B 保持 `STARTED / NOT CLOSED`，G0、G2 均不变；生产模式继续 fail closed；种子注册数据不是 ACTIVE 主网注册表。

复查入口：运行 `python3 -B scripts/check-profile-inventory.py` 校验规则/摘要与规范表一致、覆盖登记互斥、owner 唯一及证据函数存在；它只验证追踪关系，不证明语义覆盖。逐项登记为 [coverage.json](../../schemas/verification-profile/coverage.json) 与 [inventory.json](../../schemas/verification-profile/inventory.json)；R6–R16 的机器可读切片证据在同文件的 `later_profile_slice_evidence`。
