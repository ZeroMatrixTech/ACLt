# FM-S3 的 audit-only 依赖入口

日期：2026-10-28；2026-11-07 同步覆盖与来源清单。这是实施依赖清单，不是规则实现或规范状态升级。
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

未来新模块/向量位置、每个 SV 的主责包及守卫编号列在 JSON 中。所有验收仍是 PLANNED_NOT_RUN，全局覆盖登记现为 **80/35/4**。

## 正式实现前必须明确的四个接口

1. **AUDIT-WIRE-BOTTOM**：Profile schema v2 的 CBOR 与 Schema View 已规定 audit 省略 claim 键。局部 bootstrap 实现与固定字节向量见 [Schema 工件](../../schemas/verification-profile/README.md)。Profile ContentMap/摘要已由 R1 实现；R2 补 audit 注册上下文，正式导入、其他引用与完整注册验收仍待完成。
2. **AUDIT-PHASE-B-PATH**：已定义无 Snapshot 的 Phase B 变体、四条转换及启动/终态因果守卫。局部向量已接默认回归，正式日志来源、完整信封接线与跨机验收仍待完成。
3. **NONMAINNET-ASSURANCE**：§9.2.2 定义带 tag 的非主网部署声明与各相位接线草案，局部 guard 已覆盖绑定和拒绝向量。正式信封、来源证明及准入待验收。
4. **AUTHORITATIVE-OBSERVATIONS**：S1b 报价的 COMPLETE/MISSING/HOST_FAULT 是假设输入；只有 FM-S2 提供的已认证、当前 Lease/epoch、资金/期限/事件事实，才可能进入 FM-S3 求值。报价不是合法权利证明。

2026-11-06 [ADR-0008](../05-decisions/ADR-0008-fm-s3-interface-decisions.md) 收敛了四项接口及首轮计费路线，适用于候选 S3b/S3c。精确字段、来源 contract、正式规范兼容与准入按 ADR 的实施顺序验收。SV-66/91/92/93/94/105/112/117/119 等共同约束继续适用。

FM-S2 限定双机集成已交付权威事实源；[FM-S3a](../testing/FM-S3A-RESULTS-20261105.md)先实现候选 Profile 内容绑定和签名结果的纯重放，尚未实现正式 A0/A1 注册或 A4 判决。候选接纳、求值、判决和账务已有 [FM-S3 双机收尾证据](../testing/FM-S3-CLOSEOUT-20261106.md)。正式规则验收按本清单和收尾记录继续推进。完整其他方法、selection 与后续 qualification 不随本清单自动完成，也不影响未来其他任务族采用 DIRECT_VERIFIED 的决定。

2026-11-07 [Profile 第一片](../testing/PROFILE-DIGEST-R1-20261107.md)落实四项全局规则及四项 audit 分支。A0/A1 工作包的整体验收仍按剩余规则推进；机器清单只同步当前覆盖和来源 pin，不由依赖规划授予验收。

2026-11-07 [R2](../testing/PROFILE-REGISTRATION-R2-20261107.md)补四项规则级完成、八项 audit Phase R 局部检查。工作包整体验收仍保持计划状态，不能用局部向量代替完整信封、正式导入或来源认证。

2026-11-08 [R3](../testing/PROFILE-REFERENCES-R3-20261108.md)落实 SV-07/08/72/89，提供方法无关排除集/注册对象核对与 audit 注册接线。其余 import、引用/相位和 A0/A1 工作包验收保持各自边界；R2 的 TimeRange 结构视图/opaque wrapper 不能作为线上 conformance 证据。

2026-11-08 [R4](../testing/PROFILE-RULES-R4-20261108.md)补九项共同注册规则与静态假设集合摘要，四种方法的规则专用检查可独立调用；集成只接固定 audit，其他参数、claim、降级资格、完整 Phase R 和官方准入仍独立验收。

2026-11-08 [R5](../testing/PROFILE-MATRICES-R5-20261108.md)落实八项四方法矩阵/声明规则；SV-04/09/64/65 保留部分实现及明确接口缺口。Audit 集成继续使用冻结字段；非 audit 终态预期值只在测试适配器内，不能据此增加线上字段或授予工作包验收。

R6 的固定 audit I/F 测试接线见[报告](../testing/PROFILE-CREATION-R6-20261108.md)：三个摘要和 CC-1 helper 已完成；通用 ReplayPhaseI 与正式导入仍缺失。此依赖清单继续是计划追踪，不把组件证据自动记作 FM-A 验收或新增本计划实现。

R7 集中实现与范围表见[报告](../testing/PROFILE-SELECTION-R7-20261108.md)：基础 13 项加 SV-23 完成，扩展 7 项仍为 partial。未把测试适配器输入或组件完成计为正式 FM-A 验收。

[R8](../testing/PROFILE-COMMITMENTS-R8-20261108.md)补 Claim、假设快照与承诺绑定，18 个摘要 owner 完成公式/投影；组件不自动授予正式 FM-A 验收，7 项输入适用性仍为 partial。

[R9](../testing/PROFILE-RUNTIME-R9-20261108.md)集中实现显式 Phase B 的结构/绑定/冻结与阶段守卫；使用 pinned TEST population/randomness imports，SV-69/81 保留 partial，真实 Lease/事件来源、正式 B conformance 和 FM-A 工作包验收不变。
