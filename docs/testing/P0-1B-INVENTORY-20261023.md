# P0-1B 实现覆盖盘点（2026-10-23）

基线：`01e8ee2`（update/miniver #41）。本轮仅盘点、修正覆盖登记和路线图；未修改 validator 行为，未关闭 P0-1B、G0 或 G2。

## 核对结论

规范 §13.2 共 127 行：119 项 Type A、6 项 Type B、SV-15 作废、SV-40 延期。D-08-c 是额外 Type B 义务，不能混入这 6 项 SV 计数。

119 项 Type A：3 项局部谓词 implemented、8 项 partial、108 项 not implemented。18 个规范摘要全部未实现。implemented 仅表示已有局部谓词及测试，不代表完整相位/生产准入；生产模式继续拒绝。

唯一状态登记为 [coverage.json](../../schemas/verification-profile/coverage.json)，逐项实现、测试符号与缺口见 [inventory.json](../../schemas/verification-profile/inventory.json)。本表从规范表逐行提取，保留非连续及拆分编号，不按 01–121 猜测编号。既有单机/VM 场景不冒充规范 conformance。

## 本次登记修正与待办

- 默认未实现策略现在排除 partial，避免同一规则同时被描述为部分实现和未实现。
- SV-03 的枚举检查、SV-32 的顶层旧字段拒绝、SV-80 的局部 ID 检查已有实现，但归属诊断、专用向量或完整类型范围不足，保守登记为 partial；不是本轮新增功能。
- SV-54a/SV-57 仍是独立 helper，主 validate 只调用顶层与参数检查；没有完整 Phase D envelope 接入。
- JSON Schema 文件与手写 validator 不等价：例如 schema_version 的 Schema 只约束 uint 文本，而 validator 仅接受 1；Claim BOTTOM 的反向约束未在 JSON Schema 同步。应补一致性向量，不能仅凭一个入口通过就提升状态。
- §17.4 表后 SV-42 历史说明仍含 primitive/整数职责，与 §13.2 的拆分（SV-25/42/52）不一致。本轮保留规范原文，后续先作窄范围规范勘误，以 §13.2 的明确 owner 分工作实现核对。
- 五相位完整 envelope、注册表解析、外部 Schema 锁定、L2 和第二语言实现均缺失；种子注册数据不是 ACTIVE 主网注册表。

## 下一实现切片建议

优先 ClaimTemplate → template_digest（SV-70）→ VersionedObjectRef → rendered_claim_digest（SV-46）。模板 ContentMap 只有 schema_version、encoding_profile_id、normative_text、slot_decls，派生摘要绑定结构化引用与 concrete_bindings；比完整 Profile/ReceiptIntent 依赖更小。

前置工作为 SV-25/42/52 的编码职责、SV-118 Schema View 可逆投影以及对应的 wire/header/ID 子集（SV-80/86a/86c）。测试应覆盖模板内容变更、ID/Version 与 translations 排除、域 tag、引用及 concrete bindings 篡改，以及原始非规范字节拒绝。仅该链通过不能宣称 SV-60/80/86/118 全对象覆盖，更不能宣称全部 P0-1B 关闭。第二语言应独立生成相同字节和摘要。

## 全量 Type A 清单

I = 局部已实现，P = 部分实现，N = 未实现。每项的代码和测试符号在机器清单中；N 项显式记录缺口，无测试证据时列表为空。

| ID | 相位 | 层 | 状态 | 检查及剩余范围 |
|---|---|---|---|---|
| SV-01 | R | L1a | P | `schema_version` 与 `encoding_profile_id` 已知；无未知字段；仅顶层字段与版本；嵌套未知字段尚未封闭。 |
| SV-02 | R | L2 | N | `profile_digest` 按 §17.4 与 UVP-1V 重算一致；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-03 | R | L1a | P | `verification_method` ∈ 四元枚举；枚举检查已存在，但诊断使用 SV-31；缺少按 SV-03 归属的独立 conformance 向量。 |
| SV-04 | R | L1a | N | `method_parameters` 变体与 `verification_method` 匹配；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-05 | R | L1a | N | `claim_template_ref.template_id` 与方法一一对应（CLM-3）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-06 | R | L1b | N | `binding_schema` 键集合 = 模板槽位集合；`RUNTIME` 槽位不出现在 `static_bindings`（CS-1、CS-3）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-07 | R | L1b | N | `exclusion_ids` ⊇ 全部 `EXC-BASE-*`（14 项）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-08 | R | L1b | N | `exclusion_ids` 全部存在于 `registry_ref` 所指 `ExcludedClaimsRegistry` 的 `entries` 中，且该对象在 `RegistrySnapshot` 中可解析；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-09 | R | L1b | N | 方法特定排除项齐备；`soundness_class = SOUND` ⇒ `reject_attribution = NO_ATTRIBUTION`（DV-1）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-10 | R | L1b | I | `REEXEC_BOUNDED`：\(0\le B<Q\le G\)、\(\Delta_{bound}\ge\delta_{min}>0\)；局部精确参数谓词已实现；不代表完整 Phase R 可接受。 |
| SV-11 | R | L1b | I | `REEXEC_BOUNDED`：\(\sum\pi(m)=1\) 精确，且 \(\forall m\in\mathrm{supp}(\pi): m\ge Q\)；局部权重谓词已实现；不代表完整 Phase R 可接受。 |
| SV-12R | R | L1b | N | `support_capability_bound_ref` 指向本 Profile 中 `assumption_class = SUPPORT_CAPABILITY_BOUND` 且 `role = SAFETY_CRITICAL` 的条目（AR-3）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-12I | I | L1b | N | 该假设在 `scope` 与 `validity_window` 内。**失败产生 `SUPPORT_CAPABILITY_BOUND_UNAVAILABLE` 触发条件，不是拒绝**；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-13 | R | L1b | N | `q_source` ∈ {`ANCHORED_IN_CLASS`, `FAULT_INJECTED_IN_CLASS`}（LP-1）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-14 | I | L1b | N | \(N_{required}\le N_{max}\)；失败产生 `POPULATION_TOO_SMALL`；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-16 | R | L1a | N | `DIRECT_VERIFIED`：`effects` 为空、`determinism = DETERMINISTIC`；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-17 | R | L1b | N | `REEXEC_AUDIT_ONLY`：`decision_mapping` 的条件序列不含 `ACCEPT`，故值域不含 `TRUSTED`（AO-1 的推论）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-18 | R | L1b | N | `failure_mapping` 变体正确，且 `entries` 键集合**恰好等于** §10.2 矩阵为本方法确定的适用事件集合；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-19 | R | L1a | N | `failure_mapping` 变体与方法匹配；`INVALID_SAMPLE` 只出现在 `ReexecFailureMapping`（FM-0）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-20 | R | L1b | N | `decision_mapping.rules` 的元素集合恰好等于 §11.3.3 为本方法规定的适用 `DecisionCondition` 集合；缺失、多余、重复均拒绝；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-21 | R | L1b | N | `WeakeningEdge` 合法：`edge_class = AUTO_DECIDABLE`，源与目标 `ProfileDigest` 与实际 Profile 一致，满足 §6.5 四项；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-22 | R | L1a | N | `DegradationDecl.triggers` ⊆ §9.3 封闭集合；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-23 | I | L1b | N | `DEGRADED` slot 仅当 `degradation_authorized = true` 时可被考虑；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-25 | R | L2 | N | `encoding_profile_id = acl.enc.p0-1@1`；原始 CBOR 无 float/null/undefined/其他 simple value、无 indefinite-length；不检查整数范围或集合排序；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-26 | I | L1b | N | `allowed_effects` ⊇ Intent 的允许 effects；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-27 | R | L1b | N | `V1Admissible` 检查（§12、§13.1 与当前 V1 `VersionDisposition`）；`SchemaValid` 不含此项；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-28 | I | L1b | N | Profile 状态 ∈ {`REGISTERED`, `ACTIVE`}；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-29R | R | L1a | N | `ReexecFailureMapping.max_invalid_samples` 已声明；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-29I | I | L1b | N | `max_invalid_samples ≤ N_max`（FM-2；依赖 Intent，故属 Phase I）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-30 | R | L1a | P | `verified_claim_spec = ⊥` 当且仅当 `REEXEC_AUDIT_ONLY`；BOTTOM 双向检查已有；ClaimSpec 完整结构及 Schema/validator 一致性缺失。 |
| SV-31 | R | L1a | P | 参数块互斥矩阵（§8.5）逐行成立；仅 safety/liveness 在场性；failure_mapping 与独立参数变体未检查。 |
| SV-32 | R | L1a | P | 不含 `post_execution_predicate` 字段（迁移检查）；顶层白名单会拒绝旧字段；现有测试只用通用 unknown，缺少迁移字段专用负例与 SV-32 诊断。 |
| SV-33 | R | L1a | N | 每个 `AssumptionReference` 的 `revocation_mapping` 三阶段字段齐备；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-35 | D | L1b | N | `concrete_bindings` 键集合 = `binding_schema`；`STATIC` 槽位值与 `static_bindings` 逐位相同（CB-1）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-36 | D | L1b | N | `terminal_state = TRUSTED` ⇒ `claim_binding` 完整（D-08-a）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-37 | R | L1a | N | `role = SAFETY_CRITICAL` ⇒ `revocation_mapping` 恰为 AR-1 的三元组，无 `PROCEED`/`NO_EFFECT`；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-38 | R | L1b | N | 方法必需的 `assumption_class` 与 `role` 齐备（AR-2）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-39 | R | L1b | N | `decision_mapping.rules` 顺序与 §11.3 冻结优先级一致；`default = UNRESOLVED`；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-41 | R | L1b | N | `SelectionPolicy` 展开后 slot index 唯一、gate 按 slot 携带（**不含 `policy_digest`**，该职责归 SV-53b）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-42 | R | L2 | N | 容器 canonicality：map key 顺序、集合/规范 pair-array 排序去重、`Rational` 既约；不检查 primitive 禁令、整数域或摘要；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-43 | I | L1b | N | `DEGRADED` slot 的 `failure_reasons[degraded_from] ⊆ enabling_triggers`（D-06）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-44 | R | L1b | N | `static_bindings` 的每个值与 method parameters 对应字段逐位相同（CS-2）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-45 | F | L1b | N | 选中 slot 的 `profile_digest` 与注册表中该 Profile 的实际 digest 一致；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-46 | D | L2 | N | `rendered_claim_digest` 按 §5.1.1 与 §17.4 正确（CB-2）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-47 | R | L1b | N | `calibration_ref` 指向本 Profile 中 `assumption_class = CALIBRATION` 且 `role = LIVENESS` 的条目（LP-5）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-48 | R | L1b | N | `claim_template_ref` 的 `template_digest` 与注册表中模板实际 digest 一致；模板状态 ∈ {`REGISTERED`, `ACTIVE`}；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-49 | R | L1b | N | Profile 侧以 `VersionRange` 约束的量，其同名 claim 槽位为 `RUNTIME`（CS-4）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-50 | R | L1a | N | 无嵌套 `[ADVISORY]`：该标记只出现在顶层字段（§17.6）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-51 | R | L1a | N | 适用方法的 `decision_mapping.rules` 含 `EXECUTION_FAILED`；对象内不存在可覆盖 `CanonicalTerminal` 的 terminal 字段（§11.3.5）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-52 | R | L2 | N | 整数唯一 owner：无 CBOR bignum（tag 2/3）、最短整数；`int` ∈ [−2⁶³, 2⁶³−1]，`uint` ∈ [0, 2⁶⁴−1]（§17.5A）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-53a | R | L1b | N | `expanded_slots == Expand(ordered_candidates)`（结构派生复算）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-53b | R | L2 | N | `policy_digest` 按 §17.4 同时绑定 `ordered_candidates` 与 `expanded_slots`；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-54a | D | L1b | P | 当 `assumption_evaluation = COMPLETE(snapshot)` 时，状态行恰好覆盖 `SAFETY_CRITICAL/LIVENESS`、排除 `INFORMATIONAL`；行与 `cause_set` 排序去重；`effective_verdict = Reduce(reducer_ref, cause_set)`；`INVALIDATING` 分支不要求快照；独立 helper；COMPLETE/INVALIDATING envelope 与完整 Phase D 尚未接入。 |
| SV-54b | D | L2 | N | `assumption_state_digest` 按 §17.4 重算一致（owner）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-55 | I | L1b | N | 每个 `SAFETY_CRITICAL`/`LIVENESS` 假设满足 `Intent ⊑ scope`（AR-4）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-57 | D | L1b | P | `terminal_state = TRUSTED` ⇒ `assumption_evaluation = COMPLETE(snapshot)` 且全部 `SAFETY_CRITICAL` 假设的 `effective_verdict = VALID`（AS-1/ASS-7）；helper 安全假设闸门已有；完整 COMPLETE 分支与 Decision 入口缺失。 |
| SV-58 | I | L1b | N | `NormalizeDeclaredScope(Intent)` 六维齐备，且 `fault_domains`、`geography` 非空（SC-1）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-59 | R | L1a | N | `ScopeSpec` 六维齐备，无可选维度（SC-1）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-60 | R | L2 | N | **仅对版本化对象**：若 `ContentMap(a) == ContentMap(b)` 且二者只在 ID/Version 上不同，则 `Digest(a) == Digest(b)`（UVP-1V）。运行期对象因 `id` 入 ContentMap 不适用；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-61 | R | L1b | N | 相对前一版本：改内容字段 ⇒ `MAJOR` +1 且 digest 改变；仅改 `[ADVISORY]` ⇒ `MINOR` +1 且 digest 不变；仅改排版 ⇒ `PATCH` +1 且 digest 不变（§3.3、§3.5）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-62 | R | L1b | N | 引用类型正确：版本化 UVP 对象用 `VersionedObjectRef`；不版本化运行期产物用对应 `RuntimeObjectRef<IDType>` 具体别名；外部工程组件用 `ExternalVersionedObjectRef`，不得伪装成 `RegistryObjectKind`；任何引用不得只给 `Digest`（REF-1—REF-6）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-63 | R | L1a | N | `DecisionMapping.rules` 是 `[DecisionCondition]`，**不含** `terminal` 字段；无 `CanonicalTerminal` 覆盖字段（§11.3.2）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-64 | R | L1b | N | `reachable_terminals` 恰等于 `CanonicalTerminal[rules] ∪ {UNRESOLVED}`；不重复检查 rules 集合（归 SV-20）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-65 | R | L1b | N | 投影 \(\Pi\)（§11.3.2A）未被 Profile 覆盖或参数化；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-66 | R/I/F/B/D | L1a | N | 相位输入是合法 discriminated union；Phase B payload 为 §13.0.4 六个封闭变体之一；Phase D 必带完整 `evaluation_input`。不重复检查 bundle 内部结构（归 SV-91）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-68 | B | L1b | N | Lease 激活与 Snapshot 冻结时，对每个 `SAFETY_CRITICAL`/`LIVENESS` 假设检查 `ScopeContains(scope, ActualBoundScope)`（SB-1）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-69 | B | L1b | N | `EligibilitySnapshot.population_definition` 的每个抽样单位落在 scope 内（SB-2）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-70 | R | L2 | N | `template_digest` 按 §17.4 与 UVP-1V 重算一致（owner）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-71 | D | L2 | N | `AssumptionStateSnapshot.snapshot_digest` 按 §17.4 重算一致（owner）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-72 | R | L2 | N | `excluded_claims.digest` 按 §17.4 重算一致（owner）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-73 | R | L2 | N | `assumption_set_digest` 按 §17.4 重算一致（owner）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-74 | R | L2 | N | `manifest_digest` 按 §17.4 重算 `ContentMap_Manifest` 并逐位比较（owner；CM-2）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-75a | R/I/F/B/D | L1b | N | `registry_snapshot_ref` 可解析；`bundle.registry_snapshot` 的三元组与该引用逐位一致（CTX-6）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-75b | R/I/F/B/D | L2 | N | 对**显式提供的** `RegistrySnapshot` 原始字节重算 `registry_snapshot_digest`（owner；CTX-10：L2 不得取远程对象）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-76 | R | L1b | I | `assumption_id` 在一个 Profile 内唯一（ASS-3）；局部 assumption_id 唯一性已实现。 |
| SV-77 | B | L1a | N | `ActualBoundScope` 六维齐备，且 `fault_domains`、`geography` 非空（SC-1）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-78 | D | L1b | N | 当产生 `TRUSTED` 时，`COMPLETE(snapshot)` 的 identity 与 `claim_binding.assumption_state_snapshot_ref` 一致且 snapshot.receipt_id 匹配；其他终态按方法规则允许无 ClaimBinding；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-79 | R | L1b | N | `RegistrySnapshot.entries` 按 RS-1 排序、按 RS-2 去重；`object_kind` ∈ 封闭枚举（RS-3；「不含快照自身」是该封闭枚举的结构推论，在 L1a 即被拒，见 RS-4）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-80 | R | L1a | P | 全部标识符符合 §3.2 的封闭语法与注册域；表外 ID 形态 MUST 被拒（M-05）；只有 ProfileID/TaskTypeID/AssumptionID 等局部检查；完整封闭 ID 类型和注册域缺失。 |
| SV-81 | B | L1b | N | `REEXEC_BOUNDED` 的 `EligibilitySnapshot` 满足 PB-1—PB-4 四条绑定等式（owner，§13.1B）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-82 | B | L1b | N | `sampling_units` ID 唯一（PB-5）；`EligibilitySnapshot.cluster_mapping_ref` 存在（PB-5b）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-84 | R | L1b | N | `supersedes` 若存在，是完整三元组且所指对象在 `RegistrySnapshot` 中可解析（UVP-4）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-85 | R | L1a | N | `ConformanceManifest.header` 提供唯一 `(id, version, digest)`，不得接受扁平重复字段；`file_digests` 的 path 使用正斜杠相对路径（CM-1、CM-5）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-86a | R | L1a | N | 版本化对象严格使用 §3.3.2 为该对象冻结的唯一 wire shape；不得同时接受嵌套/展开两种形态；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-86b | R/I/F/B/D | L1a | N | 运行期对象严格使用 `NESTED_HEADER`；无 `version`；`header.id` 经 UVP-1R 投影进入 ContentMap；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-86c | R/I/F/B/D | L1a | N | 对象未在 header 外重复声明 `id`/`version`/`digest`；扁平 Profile 不得额外出现 `header`；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-87 | R | L1a | N | `ProfileSelectionPolicy.expanded_slots` 字段存在于对象结构且列入 `ContentMap_Policy`（§3.3.3）；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-88 | R | L2 | N | `edge_digest` 按 §17.4 重算 `ContentMap_WeakeningEdge`（owner）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-89 | R | L2 | N | `ExcludedClaimsRegistry.registry_digest` 按 §17.4 重算（owner）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-90 | R | L1b | N | `RegistryEntry` 的每个 `object_kind`（含 `MAINNET_ASSURANCE_PROFILE`）都有可解析的 `VersionedObjectRef`（RS-7）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-91 | R/I/F/B/D | L1a | N | `bundle.context`、`registry_snapshot`、`event_frontier_snapshot` 均在场；两个快照字段缺一即拒绝；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-92 | B | L1b | N | Receipt/Profile/MainnetAssurance 完整绑定链；RB-3 仅在 payload 携带快照时求值，network/assurance 引用逐位一致；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-93 | B | L1a | N | `PhaseBEnvelope.payload` 恰为 §13.0.4 六个 tagged union 变体之一，字段集合精确匹配且 transition 必填；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-94 | B | L1b | N | 状态转换约束 PB-6—PB-9 与 RG-1/RG-2，仅用 `transition.prior_round_state → proposed_round_state` 与 `snapshot_freeze_record` 判定（owner，§13.1B.2A）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-95 | I/F/B/D | L1b | N | 四类运行期对象无伪 `Version`，且引用使用对应具体别名（REF-2）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-96 | I/F | L1b | N | I 期 transcript 满足 CC-2I；F 期满足 CC-2F 与 CC-3。CC-1 只由 SV-101 检查；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-97 | I/F | L2 | N | `context_digest` 按 §17.4 重算 `ContentMap_CreationValidationContext`（owner）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-98 | I/F | L1a | N | I 期输出以 `PhaseIValidationTranscript` 物化；F 期携带完整 `phase_i_transcript`、`creation_context`、`profile` 与 `phase_f_event_ref`；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-99 | B | L1b | N | PB-5b 完整映射链：Snapshot、prior、proposed，以及冻结时的 freeze record 逐位相等；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-101 | I/F | L1b | N | CC-1 的 evaluation instant 与 registry snapshot 两字段等式；这是 CC-1 的唯一 owner。CreationContext 不绑定会随相位推进的 event frontier；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-102 | I/F | L1b | N | CC-4 与 CC-6：record 绑定当前 Intent/slot，且 `ReplayPhaseI` 的 outcome/failure_reasons 逐位一致；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-103 | I/F | L2 | N | `phase_i_record_digest` 按 §17.4 重算（owner）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-104 | I/F | L2 | N | `intent_digest` 按 §17.4 对 `ContentMap_ReceiptIntent` 重算（owner；CTX-13）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-105 | B | L1b | N | `round_stage` 单调，且 trigger—阶段转换满足 RG-1/RG-2 四行矩阵；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-106 | B | L1b | N | 集群映射首次固定与不变性：CM-FIX-1—CM-FIX-3；`round_stage ⪰ FROZEN_PRE_DRAW` 后 `cluster_mapping_ref` 不变；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-107 | B | L1b | N | PB-6 的两个事件在显式 `EventFrontierSnapshot` 中解析为正确 kind/subject，且按 EF-3 满足 `Precedes`；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-108 | R/I/F/B/D | L2 | N | `event_frontier_digest` 按 §17.4 重算 `ContentMap_EventFrontierSnapshot`（owner）；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-109 | R/I/F/B/D | L1b | N | EventFrontierSnapshot 身份与 context 引用一致；事件排序、唯一、闭合、无环，frontier 存在（EF-1—EF-4）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-110 | F | L1b | N | CC-5：Phase I/F 事件 kind 与 subject 正确，且 `Precedes(produced_by_event, phase_f_event_ref)`；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-112 | D | L1b | N | 从 `BoundaryObservation` 的显式 funding/deadline refs 与事件 DAG 调用 `ResolveBoundary`；事件缺失、kind/subject 错误先产生 invalidating；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-113 | R | L2 | N | `MainnetAssuranceProfile.assurance_digest` 按 §17.4 重算；`human_summary` 不入摘要；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-114 | D | L2 | N | `DecisionEvaluationRecord.input_digest` 对完整 `DecisionEvaluationInput` 按 §17.4 重算一致；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-115 | D | L1b | N | 重放 method evaluator；重算 condition vector、`FirstTrue`、`CanonicalTerminal`，并要求与 Decision.terminal_state 逐位一致（DE-1—DE-3）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-116 | D | L1a | N | `AssumptionEvaluationResult` 恰为 `COMPLETE(snapshot)` 或 `INVALIDATING(failure)`；两分支字段互斥且完备；缺少该规则的完整对象 Schema/相位结构检查及专用正负向量。 |
| SV-117 | I/F/B/D | L1b | N | `MainnetAssuranceProfile` 的 network、窗口、Profile capability、组件/ExecutionCapability contract/reducer 允许集合与损失上限绑定；未 `ENABLED` 的方法不得产生 `ACCEPT`；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-118 | R/I/F/B/D | L2 | N | `ToSchemaView/FromSchemaView` 可逆；输入满足 primitive/key 限制；`cbor_hex` 与 `schema_view` 向量逐位一致；无规范 CBOR/投影/摘要实现及字节级正负向量。 |
| SV-119 | R/I/F/B/D | L1b | N | 按 `log_backend_ref` 验证 checkpoint finality、EventRecord inclusion/consistency，并与 MainnetAssuranceProfile 逐位绑定（EF-6/EF-7）；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-120 | R/I/F/B/D | L1b | N | `CausalEventRecord.event_kind -> subject_ref` 满足 EF-4a 封闭矩阵；缺少该规则的语义/绑定判定及专用正负向量。 |
| SV-121 | D | L1b | N | `ExecutionObservation` 投影：合法 closure 且零有效提交才产生 `EXECUTION_FAILED`；source unavailable/malformed 产生 invalidating；缺少该规则的语义/绑定判定及专用正负向量。 |

## 18 个摘要

全部 N：无规范实现与 conformance 向量。输入与 tag 保留规范 §17.4 原文。

| 摘要 | tag | 输入 | 唯一 owner |
|---|---|---|---|
| `profile_digest` | `ACLt/P0-1/Profile/1` | `cbor(ContentMap_Profile)`（§3.3.3） | SV-02 |
| `policy_digest` | `ACLt/P0-1/SelectionPolicy/1` | `cbor(ContentMap_Policy)`（§3.3.3；**含 `on_none_applicable`**） | SV-53b |
| `template_digest` | `ACLt/P0-1/ClaimTemplate/1` | `cbor(ContentMap_Template)`（§3.3.3） | SV-70 |
| `rendered_claim_digest` | `ACLt/P0-1/RenderedClaim/1` | `cbor([claim_template_ref, concrete_bindings])` | SV-46 |
| `assumption_state_digest` | `ACLt/P0-1/AssumptionState/1` | `cbor([reducer_ref, AssumptionStateRows])`（§5.2.2） | SV-54b |
| `snapshot_digest`（`AssumptionStateSnapshot`） | `ACLt/P0-1/AssumptionStateSnapshot/1` | `cbor(ContentMap_AssumptionStateSnapshot)`（§3.3.3） | SV-71 |
| `excluded_claims.digest` | `ACLt/P0-1/ExcludedClaims/1` | `cbor([registry_ref, sorted(exclusion_ids)])`（派生摘要值） | SV-72 |
| `assumption_set_digest` | `ACLt/P0-1/AssumptionSet/1` | `cbor(sorted([[assumption_id, statement_digest], ...]))` | SV-73 |
| `manifest_digest` | `ACLt/P0-1/Manifest/1` | `cbor(ContentMap_Manifest)`（§3.3.3、§3.4） | SV-74 |
| `edge_digest` | `ACLt/P0-1/WeakeningEdge/1` | `cbor(ContentMap_WeakeningEdge)`（§3.3.3、§6.5） | SV-88 |
| `registry_digest`（`ExcludedClaimsRegistry`） | `ACLt/P0-1/ExcludedClaimsRegistry/1` | `cbor(ContentMap_ExcludedClaimsRegistry)`（§3.3.3、§6.3） | SV-89 |
| `assurance_digest`（`MainnetAssuranceProfile`） | `ACLt/P0-1/MainnetAssuranceProfile/1` | `cbor(ContentMap_MainnetAssuranceProfile)`（§3.3.3、§3.6） | SV-113 |
| `DecisionEvaluationRecord.input_digest` | `ACLt/P0-1/DecisionEvaluationInput/1` | `cbor(DecisionEvaluationInput)`（§11.1；完整显式输入） | SV-114 |
| `context_digest`（`CreationValidationContext`） | `ACLt/P0-1/CreationContext/1` | `cbor(ContentMap_CreationValidationContext)`（§3.3.3、§13.0.2） | SV-97 |
| `registry_snapshot_digest` | `ACLt/P0-1/RegistrySnapshot/1` | `cbor(ContentMap_RegistrySnapshot)`（§3.3.3、§3.5；`entries` 排序去重见 RS-1/RS-2） | SV-75b |
| `phase_i_record_digest` | `ACLt/P0-1/PhaseIValidationRecord/1` | `cbor(ContentMap_PhaseIValidationRecord)`（§3.3.3、§13.0.2） | SV-103 |
| `intent_digest` | `ACLt/P0-1/ReceiptIntent/1` | `cbor(ContentMap_ReceiptIntent)`（§3.3.3、CTX-13） | SV-104 |
| `event_frontier_digest` | `ACLt/P0-1/EventFrontierSnapshot/1` | `cbor(ContentMap_EventFrontierSnapshot)`（§3.3.3、§13.0.1） | SV-108 |

## 复查入口

运行 `python3 -B scripts/check-profile-inventory.py` 校验规则/摘要与规范表一致、覆盖登记互斥、owner 唯一及证据函数存在；它只验证追踪关系，不证明语义覆盖。运行 `make check` 复查现有回归与交付清单。
