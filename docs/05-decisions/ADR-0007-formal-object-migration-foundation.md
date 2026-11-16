# ADR-0007：正式对象迁移的基础路线与边界

> 状态：`ACCEPTED`（仅接受 D-1～D-6 的首轮测试迁移路线；不是字段冻结或部署验收）
> 日期：2026-10-26
> 工程范围：FM-F0 → FM-S1a；修订基线 `f5f415f7c65952adba01f7b0c9f21d554b14c264`
> 关联：OQ-02、OQ-03、OQ-04、OQ-05、OQ-06、OQ-09、OQ-10、OQ-11；ADR-0003、ADR-0005、ADR-0006

## 1. 问题、现状与权威边界

Work 1–3 的构建、实验任务承诺、授权、日志、测试资金与恢复已有局部工程证据；[迁移清单](../07-roadmap/formal-object-migration.md)登记了 19 类替身、8 个跨对象缺口与 6 项待决问题。当前不能把这些对象改名拼成正式协议。

三个具体反例决定本路线：

1. task ID 已冻结以后再发布资金政策，无法保证修改费率也改变 ReceiptID（X-4/INV-01、INV-12）。
2. CHECK/CONSUME 与 funded-start 分别允许一次启动，直接合并两个数据库会形成同一义务的第二条授权路径（X-1/INV-03、INV-08、INV-09）。
3. 相同 Python reference 的两个 OK 结果不建立错误支持上界 B；把 MATCH_OK 直接改称 TRUSTED 再付款，会绕过验证 Profile、唯一终态和结算政策（X-5/INV-04、INV-07、INV-14）。

**2026-10-26 项目维护者明确回复：“接受六项路线，保留字段与实现验收门槛”。据此接受 §2 的 D-1～D-6 作为首轮有限测试部署的路线决定（该范围的 SemanticStatus 为 DECIDED）。** 字段/wire keys/tag、签名精确 suite/envelope、终态费用矩阵与非主网表达仍未冻结；后文标为待冻结的内容不是已接受的对象 Schema。V1 VersionDisposition、各对象原有 OPEN/CANDIDATE、OQ、Gate、ADR-0006 与生产准入不因本路线接受而改变。不签发正式对象 ID、不注册新摘要域、不授权上线。

正式语义仍来自[协议规范](../03-protocol/protocol-spec.md) §3–18、[生命周期](../02-architecture/task-lifecycle.md) §6–10、[不变量](../01-requirements/invariants.md)和已接受 ADR。

## 2. 已接受的六项路线

### D-1 编码：共用规范规则，保留对象类型与摘要隔离

首轮采用 `acl.enc.p0-1@1` 为协议对象编码规则的起点；RIR 外壳沿 ADR-0006 候选 `acl.enc.rir-0@1`，不把二者混称一个 schema。每个对象独立注册类型、版本、字段集合和摘要 tag。签名输入需绑定协议版本、对象类型、网络/部署及签署责任，禁止只签一个无上下文裸 digest。

当前 P0-1B 的 Python/Rust codec 只是 ClaimTemplate/claim 的候选切片，不能直接作为通用正式对象 codec；先审查适用类型、整数范围、NFC/Unicode 版本、map 排序、重复键、输入深度/长度和未知字段的完整合约。Rational 和 SemVer 是 schema 类型规则，不能由任意 array/string 猜测。字段具体编号、上限、tag 字节及签名 envelope 留在第一切片的候选规范中逐项冻结。

旧小型 codec 只留在实验目录；不重编码旧证据、不复用旧 ID。负整数、不同键排序、非最短整数、重复键、非 NFC、未知字段/版本、尾随字节和资源边界均需负例。独立 Rust 编解码与摘要不能借用 Python 预验证；已有同语言共享辅助的核对不算第二实现。

### D-2 终态与费用：首轮 audit-only；过程付费与正确性背书分开

首轮采用受限 `REEXEC_AUDIT_ONLY` 路线连接 stats-int-v1：首轮接入不新增 DIRECT_VERIFIED 谓词，独立主机建立 B/Q 也不属于首轮接入的证明目标。这限定当前实现路线，不排除其他任务族未来采用 DIRECT_VERIFIED。

audit-only 必须使用合规 Profile 的 ReexecAuditParams/AuditFailureMapping，safety_parameters 与 liveness_parameters 为空，不冻结 EligibilitySnapshot、不做随机抽样，不承载 B/Q 或统计活性 claim（Profile §7.4、§8.5、§10.2）。完整证据、冻结停止/失败规则及规范要求的显式 AssumptionEvaluation 仍需提供；AssumptionStateSnapshot 与有限总体 EligibilitySnapshot 不可混淆。只有未来的 REEXEC_BOUNDED 路线才接入后者及其总体/随机性绑定。

按现行 INV-07，UNRESOLVED 可以有预声明过程费用，不必先成为 TRUSTED。准确终态由冻结的 DecisionMapping、EvaluateDecision 与 ResolveBoundary 派生，沿用 Profile §11.3 的优先级与显式事件 DAG；不能把“deadline 先到”另立成覆盖 VERIFICATION_INVALIDATING/EXECUTION_FAILED 等条件的总规则。audit-only 的条件结构不含 ACCEPT，不能产生 TRUSTED。同一 Receipt 终态至多一个，不能依赖客户端时钟、数组顺序或运行时任选次序。完整不一致/Task trap 不自动证明 Provider 恶意，不把 HostFault 编造为 Task 结果。

费用候选按**已接受、当前 Lease/epoch、签署完整且满足冻结格式的有限履约项**计固定过程费；不以两端相等额外奖励，不把金额当作真理权。支付执行方/验证方各自费用的责任与权利类型须明确，不能让两个身份领取同一义务两次。缺失或只有 permit 不产生该项费用；余款按冻结政策退款，unknown 先查询。费用合法性须逐项满足 INV-07：同一 Receipt 的唯一已提交终态、冻结 SettlementPolicy、足额且用途匹配的授权资金、由终态/故障归因派生的合法权利，以及尚未提交的 EntitlementKey。完全相同的幂等请求仍返回原结果，不创建第二次业务分配；异内容才冲突。金额由政策求值，客户端不能选分支。

已接受的是“非 TRUSTED 终态也可按预声明政策产生过程费用”的路线，**不是已冻结 SettlementPolicy**。UNRESOLVED/EXPIRED/FAILED/FUNDING_EXHAUSTED、完整/缺失/HostFault、执行/验证/存储/退款储备等可达组合须逐格给出费用与释放规则。首版仅 requester prefunded 整数测试资产；不支持来源/部分履约/故障格时在创建或准入时拒绝，不能在占用资金后因缺少政策永久卡住。其他合法但不可达终态须附不可达依据，不能伪造全矩阵完成。

### D-3 测试日志：显式风险声明，不借用主网 assurance

首轮使用新 `network_id`/deployment genesis 固定的单权威测试日志，声明 A 的签署、时序、持久化、组件和不回滚假设，B 保存独立 pin。它是部署配置/风险声明，不新增协议 Principal 或 MainnetAssuranceProfile 替身。

待冻结的测试 contract 需定义统一 EventRecord、原子事件/投影提交、签名 checkpoint、父引用、inclusion/consistency 检查、消费位置与本部署的提交接受点。SQLite COMMIT/签名只能支持声明过的测试提交假设，不冒充主网 finality 或权威抗回滚。缺失/冲突/不能验证的记录不能推进安全终态或付款；保留未知并在恢复后按原政策有界处理。

协议 §5 的 deployment assurance 字段如何在非主网表达“主网不适用”，仍需候选 schema 和权威文字补齐；不能静默省略，也不能把测试声明放进现有 MainnetAssuranceProfile 字段。该接口未被审查接受前，正式 Receipt 入口不启用。官方主网运行、权威 failover、分叉/回滚防护不在首版范围。

### D-4 身份：先做最小真实角色签署，不把 HMAC 当 Principal

在首轮有限测试部署沿用已有 OpenSSL RSA-2048/SHA-256 适配作为测试 suite 路线，避免本轮额外引入签名依赖；它没有因此成为协议默认或生产算法。FM-S1a 必须固定确切 padding、签名编码、hash、key 编码、签名输入、尺寸上限和拒绝规则并提供向量，不能只登记“RSA/SHA256”。

Requester、两个 Provider、日志 issuer 各用不同测试密钥。Requester 签 Receipt，Provider 签 Lease acceptance 和 ResultSubmission，issuer 只能签自己承担的日志/能力责任，不能代签 Provider 履约。PrincipalRecord 版本及适用密钥、网络、权限、有效期须被引用；未知、撤销、过期、错误角色/网络/上下文的签名拒绝。

HMAC 可以继续是传输登记/防误用控制，但不再提供正式身份或结果来源。公钥 pin 的带外来源与撤销生效时点需明确；首版不做在线轮换，变化须停止新准入并显式重建测试部署，已有义务按原有政策和证据处理，不能用换 genesis 抹除债务。固定密钥测试不完成 OQ-03 或证明控制独立。Requester/Provider 是协议 Principal；日志 issuer 只承担实现日志签署职责，其密钥不得被伪装成第三种 Principal。

### D-5 暴露：固定保守多维上限，缺项拒绝

首轮先用冻结测试参数，分别绑定 Provider、已知相关簇、Receipt、时间窗和全局暴露，以及并发、价值/损失、尝试数和有效期。来源缺失/过期时拒绝准入；不能只用“每个身份一个槽”冒充相关性控制。未知关联者按共同保守池计入并受全局上限限制，不从身份数推导独立性或 B/Q。

资金承诺与暴露预留是不同桶；Lease 激活需同时校验并原子预留两者。提案未接受不产生执行义务或负面履约证据；激活失败回滚全部预留，过期/终态按政策幂等释放。迟到结果不能占用已释放额度或创建结算权利。Candidate CapabilityEstimate 可后续替换准入参数来源，不能更改当次验证真理权。

### D-6 重试：首版每个 Assignment 一次，无自动 guest 重试

在首轮 Receipt/WorkPlan 冻结总 Assignment、每 Assignment attempt、消息重试次数、恢复查询次数、总预算和最终期限。首版同一 Assignment 最多一次 guest invocation，失联/许可未知先查询，不自动续算；消息重传、查询和离线重放不计作新计算，也不能重开已消费槽。

epoch 仍为必需语义：激活时分配、所有能力/提交绑定、旧 epoch 隔离。首版不开放失败后新的执行 epoch；未来启用必须有新政策版本、剩余预算/暴露检查与新 Lease 接受，不能因为需要恢复就隐式重试。机器重启无法判断是否执行过时按未知/期限处理，不以“没有结果文件”推断未执行。

到最终期限，由可信测试时序证据驱动唯一终态提交及按冻结政策的后续资金处置；客户端不可达时不能假装已经释放，权威恢复后再按原记录处理。有限逻辑 deadline 不等于保证网络/主机永久故障时按现实时间到账。

## 3. 接口约束与待冻结细节

下面是逻辑输入输出与写权限，**不是 wire schema/API 定义**。每个调用先做版本/签名/父引用/状态/幂等验证，拒绝不得修改协议业务状态；如记录拒绝审计，不得消费资金、暴露、attempt 或权利。

| 接口 | 冻结输入/责任 | 输出与原子边界 |
|---|---|---|
| prepare policies | Requester，版本/来源/用途/预算/终态矩阵，无 ReceiptID 回指 | Funding/Settlement policy 内容摘要；随后由 Receipt 引用 |
| register task | Requester 签署的完整 ComputeReceipt、政策/Profile/输入及部署引用 | 新 ReceiptID；任一语义改变产生新 ID；无合法政策则创建失败 |
| activate lease | 合法 WorkPlan/Assignment、Provider 接受、Receipt、资金/暴露额度 | 唯一 active Lease + 单调 epoch + 两类预留 + EventRecord，同一事务或先证明等价补偿 |
| dispatch/start | active Lease 派生的 capability、固定执行元组、当前期限/epoch | Dispatch/RPR 两处检查同一权威；持久 intent 后消费唯一 attempt，再执行 |
| accept result | Provider 签名、当前 Lease/epoch、完整 outcome 与输入引用 | 原子接纳+事件+稳定回执；同幂等键异内容冲突 |
| decide terminal | 冻结 Profile/AssumptionEvaluation、完整证据或有界停止事实；仅 bounded 使用 EligibilitySnapshot | 唯一 VerificationDecision/准确终态+事件；audit-only 不输出 TRUSTED |
| settle | 已提交终态、原政策、合法履约、可用预留 | 派生分项 EntitlementKey；付款/退款/释放+事件原子提交，重试取原结果 |
| recover/query | 当前已认证状态或保存的原回执/锚点 | 不新建业务权利或 guest 调用；未知不推断，恢复推进仍走上述同一入口 |

**修正规划次序，不修改历史实验：** 原迁移清单 F5 中的政策 schema/矩阵必须拆出前半部分，在 F2 Receipt 之前完成；F5 只实现终态驱动的记账和恢复。资金政策不能以将来的 ReceiptID 参与自身摘要，随后 Receipt 又摘要政策，形成哈希环。首轮采用独立政策内容摘要及 Requester/nonce/部署绑定，由 Receipt 单向引用；登记实例的 Receipt 关联在后续登记/事件中表达。如何满足协议 §3 的可解析关联仍需 schema 审查，不能靠空 ID 或常数绕过。

对于未来 bounded 路线，验证“计划/Snapshot 构造政策”在 Receipt 时冻结，实际 EligibilitySnapshot 在首次 draw 前产生并引用 Receipt，不能先求未来快照摘要再计算 ReceiptID。Lease proposal/accept/active、EventRecord 的自摘要/签名排除字段与因果边也要作无环性检查。

## 4. 不变量、威胁与反例

| 约束 | 必须拒绝的直接反例 | 主要威胁 |
|---|---|---|
| INV-01/02/12 | 改资金政策后仍同 ReceiptID；缺版本；观察后改规则 | TH-01、TH-02、TH-15、TH-24、TH-30 |
| INV-03/08/09 | funded-start 另开槽；旧 epoch 覆盖；恢复重算；无界占用 | TH-10、TH-11、TH-28、TH-38 |
| INV-04/07 | audit-only 输出 TRUSTED；没有终态付款；客户端选终态/金额 | TH-21、TH-23、TH-24 |
| INV-05/06 | 竞争双付；来源/用途互借；退款与付款重复占用同一份资金 | TH-22、TH-23 |
| INV-10/14 | 拆身份绕簇/全局 cap；支付或履约信誉成为真理票 | TH-07、TH-08、TH-09、TH-17、TH-19 |
| INV-13/16 | 拼接两套日志当同一事实；未验证 checkpoint 推进；codec 漂移 | TH-01、TH-02、TH-27、TH-29、TH-37 |

威胁编号的定义仍见[威胁模型](../01-requirements/threat-model.md)；上表只是本方案的追踪入口，不新增威胁语义。

## 5. 假设、权限与成本

新增的是待声明的测试 contract：独立角色公钥来源、有限可信时序、固定暴露参数和统一事务边界；继续依赖诚实 pinned 宿主与单一不回滚测试权威。它们不由 schema、签名或双机本身证明。

不新增 Broker/Verifier/Foundation 裁决者；签名者只承担已有 Requester/Provider 或实现日志职责。行政成本包括角色密钥/pin、policy/Profile/schema 登记、矩阵维护、独立实现向量、部署风险声明和逐段双机回归。先限定一个任务族、一种预置测试资产及固定有限配置，不同时扩展真实支付、浮点/GPU、定价或通用重试。

## 6. 兼容、退出与接受条件

新对象从全新测试部署开始；旧实验原字节与入口保留作历史回归，但不能被新正式入口接收，不把试验 ID 转为正式 ID。部署与签名/tag 做隔离，停用旧入口的范围限定为新部署。已有义务不凭空消失。

路线接受、字段冻结、实现验收与部署启用分别处理，不能互相充当完成证据：

| 层次 | 本轮状态 | 后续要求 |
|---|---|---|
| D-1～D-6 路线决定 | 已由维护者明确接受 | 本 ADR §2 是该首轮路线的唯一决定源 |
| 字段/编码/签名/费用矩阵冻结 | 未完成 | FM-S1a/S1b 给出精确候选与向量，按权威规范逐项审查并同步 |
| 实现与集成验收 | 未完成 | 独立 Python/Rust 字节/摘要、拒绝状态不变、单一 Lease/账务/日志与相应真实双机矩阵 |
| 部署/能力启用 | 未完成 | 正式来源、assurance、风险预算、撤销与必要 conformance；本 ADR 不授予资格 |

schema 与向量未完成不反过来撤销已接受的路线；路线接受也不允许把候选字段称为正式 wire 合约。FM-S1a 可以在该边界内开始代码与向量工作，正式入口在所需规范/schema 未冻结时仍保持未启用。

ADR-0006 继续 PROPOSED，其 §11 文档同步和 §13 接受证据不被本 ADR 放宽。尚缺的独立 Rust 外壳读取/验证/摘要、完整拒绝/计量/HostFault conformance，以及正式 ReceiptID 身份变化测试仍须逐项补齐。不能把“路线接受”包装成 RIR/RPR 已验收。

兼容退出仍采用新测试部署、旧证据保留、不迁移旧库。B/Q、真实资金、主网 assurance、权威抗回滚、物理断电和独立维护者审计继续单列。

## 7. 来源与命名连续性

初稿由助手于 2026-10-26 准备，曾错误使用 WORK4-F0 名称；原定第四项始终是已合并的 BQ-WORK4 研究。维护者本轮接受仅针对本 ADR 的六项路线。旧草案的原字节已在操作者备份中留存，store 的整合与清理见[收尾记录](../testing/STORE-INTEGRATION-20261026.md)，不改写已提交的 B/Q 研究或历史测试结果。迁移入口统一使用 FM，详见[实施入口](../07-roadmap/formal-migration-plan.md)。

## 2026-10-28 FM-S1a 实现证据

D-1/D-4 的首轮局部实现已形成[候选测试合约](../../schemas/formal-migration/README.md)与[报告](../testing/FM-S1A-20261028.md)：沿用独立编码/摘要核心，固定 RSA-2048/e65537、PKCS#1 v1.5/SHA-256、DER SPKI 和完整上下文输入。仅最小固定角色/pin 与测试 payload；无新 Principal 或官方 schema/import 注册。此处不扩大六项路线的接受范围，D-2/D-3/D-5/D-6、ADR-0006 与部署门槛不变。

## 2026-10-28 FM-S1b 实现证据

[本轮报告](../testing/FM-S1B-20261028.md)固定 D-1/D-2/D-4/D-6 所需的局部候选政策/Receipt 字段、111 格费用规则与签名输入。政策无 Receipt 回指，Receipt 单向引用政策/输入/执行组件；金额由冻结费用行派生。正式政策/Receipt、非主网 assurance 接口和组件语义仍须审查；并未把无副作用报价当作有效终态、资金来源或 EntitlementKey，也不扩展原六项路线的接受/部署范围。

## FM-S2 限定实现证据（2026-10-31）

[候选执行合约](../../schemas/formal-migration/execution.md)与[双机报告](../testing/FM-S2-20261031.md)落实本路线的单权威/原子预留/统一日志和一次 Attempt；官方字段/注册与运行合规门槛保持原状态。固定测试 host 不等于 OS sandbox；到期 FENCE 不代替判决或退款。此次不新增路线接受或协议语义变更。
