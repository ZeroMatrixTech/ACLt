# FM-S3 的 audit-only 依赖入口

日期：2026-10-28；这是实施依赖清单，不是规则实现或规范状态升级。
[机器清单](fm-s3-audit-dependencies.json)按现有 inventory 的全部编号逐项分类；要求、实现状态和原测试路径只引用原 inventory，不在此复制另一份权威。

## 限定范围

只接一个明确固定的 REEXEC_AUDIT_ONLY Profile，不新增 selection/degradation/weakening 注册路径。Audit 不引用 ClaimTemplate、不产生 claim/ACCEPT/TRUSTED，不使用 B/Q、EligibilitySnapshot 或随机抽样；安全/活性参数为空。显式 AssumptionEvaluation 仍必需，AssumptionStateSnapshot 不是 EligibilitySnapshot。

AuditFailureMapping 必须精确覆盖规范方法矩阵的 13 个事件；五个条件依次为 VERIFICATION_INVALIDATING、EXECUTION_FAILED、BUDGET_EXHAUSTED、DEADLINE_REACHED、EVIDENCE_EXHAUSTED，默认 UNRESOLVED。四个派生终态为 UNRESOLVED、FAILED、FUNDING_EXHAUSTED、EXPIRED。S1b 的三个 prestart 零费用退出格不是额外 Audit Decision 终态。

完整 ValidationContext、registry/event frontier、I/F transcript、Phase B/Decision 输入仍要保留。固定 Profile 不等于删除创建和最终绑定相位；没有 Claim 也不等于删除 registry、证据来源、原因集合或事件因果检查。

## 谁补、何时补、交付什么

| 包 | 主责与前置 | 规则范围（机器清单为准） | 可审查产物 |
|---|---|---|---|
| A0 通用基础 | 后续 audit 编码切片；先于 A1 | 29 个公共编码/身份/registry/event 约束 | 复用 codec，补对象 wire/import/ContentMap、Schema View 与字节向量 |
| A1 Profile 注册 | 后续 FM-S3 Profile 切片，依赖 A0 | 24 个 audit/公共注册约束，含 SV-05/17/18/19/20/30/31/39/51/63/64/65 | Audit 参数/失败事件/条件顺序/Profile 摘要与拒绝向量 |
| A2 I/F 创建 | FM-S2 提供 Intent/Receipt/事件；audit 创建模块接入 | 13 个创建/最终绑定约束 | 完整固定 slot、context、transcript 和 ReplayPhaseI |
| A3 Lease 绑定 | FM-S2 先做单一权威/六维 scope/统一事件 | 6 个共同 Phase B 约束 | 实际 scope/transition/Receipt-Profile 绑定，不能伪造 Snapshot |
| A4 方法与判决 | FM-S3 判决模块，依赖 A0–A3 | 8 个 Decision 约束，含 SV-54a/54b/71/112/114/115/116/121 | AssumptionEvaluation、方法重放、Boundary/Execution 观察、唯一派生终态 |
| B0 接口/来源 | FM-S2/3 集成与故障审计 | 5 个共同 Type B 加 D-08-c | 资金/信誉不入真理条件、显式时点、无旁路、无只给 terminal 的端点 |
| G0 正式准入 | 维护者审查，不能由测试自行批准 | 4 个 MAP/V1/日志准入约束 | 官方/测试网络边界与来源/finality，不伪造正式 MAP |

这里的 **84 个 Type A 依赖不等于新写 84 项实现**：公共基础需要复用、对象绑定要分阶段集成，部分还被官方接口阻塞。另有 35 个 Type A 由限定功能边界守卫拒绝，合计仍为原 119 项；守卫也要正负测试，不能标成已实现或全局 N/A。Type B 中 SV-56 属 bounded 抽样路径，限定 audit 入口必须证明不存在该路径，不能借此关闭其全局义务。

未来新模块/向量位置、每个 SV 的主责包及守卫编号列在 JSON 中。所有验收仍是 PLANNED_NOT_RUN，全球覆盖登记仍为 **3/19/97**。

## 正式实现前必须明确的四个接口

1. **AUDIT-WIRE-BOTTOM**：`verified_claim_spec=⊥` 的唯一 CBOR/Schema View 表示。不能将 bootstrap JSON null 当成符合全局禁 null 的正式 wire。
2. **AUDIT-PHASE-B-PATH**：Audit 不冻结 EligibilitySnapshot 时，Phase B 六种 payload/round_stage 的合法执行/终态路径；post-freeze 变体的必填 Snapshot 不能擅自补假对象，transition 也不能省略。
3. **NONMAINNET-ASSURANCE**：现行 RI-6/MAP 的 outside_network_disposition=DISABLED 与本轮非主网测试声明之间的正式接口；候选 network/deployment pin 不是 MAP。
4. **AUTHORITATIVE-OBSERVATIONS**：S1b 报价的 COMPLETE/MISSING/HOST_FAULT 是假设输入；只有 FM-S2 提供的已认证、当前 Lease/epoch、资金/期限/事件事实，才可能进入 FM-S3 求值。报价不是合法权利证明。

这些是待审查事项，本轮不私自改规范。不能为简化 audit 而删掉 SV-66/91/92/93/94/105/112/117/119 等共同约束。

FM-S2 是当前主线，先交付限定双机集成和权威事实源；之后 A1/A4 接入成为 FM-S3 的最小 audit-only 闭环。完整其他方法、selection 与后续 qualification 不随本清单自动完成，也不影响未来其他任务族采用 DIRECT_VERIFIED 的决定。
