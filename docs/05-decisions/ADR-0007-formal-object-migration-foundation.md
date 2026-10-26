# ADR-0007：正式对象迁移的基础路线与边界

> 状态：`PROPOSED`（未接受草案）  
> 日期：2026-10-26  
> 工程范围：WORK4-F0；基线 `3a001ddba707ce50c0afef472d43043a244522b0`  
> 关联：OQ-02、OQ-03、OQ-04、OQ-05、OQ-06、OQ-09、OQ-10、OQ-11；ADR-0003、ADR-0005、ADR-0006

## 1. 问题、现状与权威边界

Work 1–3 的构建、实验任务承诺、授权、日志、测试资金与恢复已有局部工程证据；[迁移清单](../07-roadmap/formal-object-migration.md)登记了 19 类替身、8 个跨对象缺口与 6 项待决问题。当前不能把这些对象改名拼成正式协议。

三个具体反例决定本路线：

1. task ID 已冻结以后再发布资金政策，无法保证修改费率也改变 ReceiptID（X-4/INV-01、INV-12）。
2. CHECK/CONSUME 与 funded-start 分别允许一次启动，直接合并两个数据库会形成同一义务的第二条授权路径（X-1/INV-03、INV-08、INV-09）。
3. 相同 Python reference 的两个 OK 结果不建立错误支持上界 B；把 MATCH_OK 直接改称 TRUSTED 再付款，会绕过验证 Profile、唯一终态和结算政策（X-5/INV-04、INV-07、INV-14）。

**本 ADR 提供助手起草的候选路线，不将 D-1～D-6 标成已接受决定。** 按[审计程序](../08-governance/audit-procedure.md) §4，未接受草案不能作为正式实现或 conformance 依据。以下“拟采用”均属于候选建议；本轮不变更现行规范、V1 处置、SemanticStatus、Gate、OQ 或 ADR-0006 状态，也不签发正式对象 ID、注册新摘要域或授权生产部署。

正式语义仍来自[协议规范](../03-protocol/protocol-spec.md) §3–18、[生命周期](../02-architecture/task-lifecycle.md) §6–10、[不变量](../01-requirements/invariants.md)和已接受 ADR。

## 2. 六项候选选择

### D-1 编码：共用规范规则，保留对象类型与摘要隔离

拟以 `acl.enc.p0-1@1` 为协议对象编码规则的起点；RIR 外壳沿 ADR-0006 候选 `acl.enc.rir-0@1`，不把二者混称一个 schema。每个对象独立注册类型、版本、字段集合和摘要 tag。签名输入需绑定协议版本、对象类型、网络/部署及签署责任，禁止只签一个无上下文裸 digest。

当前 P0-1B 的 Python/Rust codec 只是 ClaimTemplate/claim 的候选切片，不能直接作为通用正式对象 codec；先审查适用类型、整数范围、NFC/Unicode 版本、map 排序、重复键、输入深度/长度和未知字段的完整合约。Rational 和 SemVer 是 schema 类型规则，不能由任意 array/string 猜测。字段具体编号、上限、tag 字节及签名 envelope 留在第一切片的候选规范中逐项冻结。

旧小型 codec 只留在实验目录；不重编码旧证据、不复用旧 ID。负整数、不同键排序、非最短整数、重复键、非 NFC、未知字段/版本、尾随字节和资源边界均需负例。独立 Rust 编解码与摘要不能借用 Python 预验证；已有同语言共享辅助的核对不算第二实现。

### D-2 终态与费用：audit-only；过程付费与正确性背书分开

拟以受限 `REEXEC_AUDIT_ONLY` 路线连接 stats-int-v1，不在本轮新增 DIRECT_VERIFIED 谓词，也不声称独立主机建立 B/Q。REEXEC 路线仍需合规 Profile、EligibilitySnapshot、AssumptionEvaluation、完整证据及冻结停止规则；固定两端不是省略这些对象的理由。

按现行 INV-07，UNRESOLVED 可以有预声明过程费用，不必先成为 TRUSTED。拟在有效证据齐备/验证预算到限后产生 UNRESOLVED；若 Receipt 最终期限先到则按冻结时序规则提交 EXPIRED。同一 Receipt 终态至多一个；事务顺序、截止点相等时的优先级和时间证据必须先写入候选规则，不依赖客户端时钟或运行时任选顺序。完整不一致/Task trap 不自动证明 Provider 恶意，不把 HostFault 编造为 Task 结果。

费用候选按**已接受、当前 Lease/epoch、签署完整且满足冻结格式的有限履约项**计固定过程费；不以两端相等额外奖励，不把金额当作真理权。支付执行方/验证方各自费用的责任与权利类型须明确，不能让两个身份领取同一义务两次。缺失或只有 permit 不产生该项费用；余款按冻结政策退款，unknown 先查询。任何费用都须引用已提交唯一终态、完整证据和合法 EntitlementKey；金额由政策求值，客户端不能选分支。

这是一项待审的最小经济方案，**不是已冻结 SettlementPolicy**。UNRESOLVED/EXPIRED/FAILED/FUNDING_EXHAUSTED、完整/缺失/HostFault、执行/验证/存储/退款储备等可达组合须逐格给出费用与释放规则。首版仅 requester prefunded 整数测试资产；不支持来源/部分履约/故障格时在创建或准入时拒绝，不能在占用资金后因缺少政策永久卡住。其他合法但不可达终态须附不可达依据，不能伪造全矩阵完成。

### D-3 测试日志：显式风险声明，不借用主网 assurance

拟用新 `network_id`/deployment genesis 固定的单权威测试日志，声明 A 的签署、时序、持久化、组件和不回滚假设，B 保存独立 pin。它是部署配置/风险声明，不新增协议 Principal 或 MainnetAssuranceProfile 替身。

候选 contract 需定义统一 EventRecord、原子事件/投影提交、签名 checkpoint、父引用、inclusion/consistency 检查、消费位置与本部署的提交接受点。SQLite COMMIT/签名只能支持声明过的测试提交假设，不冒充主网 finality 或权威抗回滚。缺失/冲突/不能验证的记录不能推进安全终态或付款；保留未知并在恢复后按原政策有界处理。

协议 §5 的 deployment assurance 字段如何在非主网表达“主网不适用”，仍需候选 schema 和权威文字补齐；不能静默省略，也不能把测试声明放进现有 MainnetAssuranceProfile 字段。该接口未被审查接受前，正式 Receipt 入口不启用。官方主网运行、权威 failover、分叉/回滚防护不在首版范围。

### D-4 身份：先做最小真实角色签署，不把 HMAC 当 Principal

拟在有限测试部署沿用已有 OpenSSL RSA-2048/SHA-256 适配作为候选 suite，避免本轮额外引入签名依赖；它没有因此成为协议默认或生产算法。第一切片必须固定确切 padding、签名编码、hash、key 编码、签名输入、尺寸上限和拒绝规则并提供向量，不能只登记“RSA/SHA256”。

Requester、两个 Provider、日志 issuer 各用不同测试密钥。Requester 签 Receipt，Provider 签 Lease acceptance 和 ResultSubmission，issuer 只能签自己承担的日志/能力责任，不能代签 Provider 履约。PrincipalRecord 版本及适用密钥、网络、权限、有效期须被引用；未知、撤销、过期、错误角色/网络/上下文的签名拒绝。

HMAC 可以继续是传输登记/防误用控制，但不再提供正式身份或结果来源。公钥 pin 的带外来源与撤销生效时点需明确；首版不做在线轮换，变化须停止新准入并显式重建测试部署，已有义务按原有政策和证据处理，不能用换 genesis 抹除债务。固定密钥测试不完成 OQ-03 或证明控制独立。

### D-5 暴露：固定保守多维上限，缺项拒绝

拟先用冻结测试参数，分别绑定 Provider、已知相关簇、Receipt、时间窗和全局暴露，以及并发、价值/损失、尝试数和有效期。来源缺失/过期时拒绝准入；不能只用“每个身份一个槽”冒充相关性控制。未知关联者按共同保守池计入并受全局上限限制，不从身份数推导独立性或 B/Q。

资金承诺与暴露预留是不同桶；Lease 激活需同时校验并原子预留两者。提案未接受不产生执行义务或负面履约证据；激活失败回滚全部预留，过期/终态按政策幂等释放。迟到结果不能占用已释放额度或创建结算权利。Candidate CapabilityEstimate 可后续替换准入参数来源，不能更改当次验证真理权。

### D-6 重试：首版每个 Assignment 一次，无自动 guest 重试

拟在 Receipt/WorkPlan 冻结总 Assignment、每 Assignment attempt、消息重试次数、恢复查询次数、总预算和最终期限。首版同一 Assignment 最多一次 guest invocation，失联/许可未知先查询，不自动续算；消息重传、查询和离线重放不计作新计算，也不能重开已消费槽。

epoch 仍为必需语义：激活时分配、所有能力/提交绑定、旧 epoch 隔离。首版不开放失败后新的执行 epoch；未来启用必须有新政策版本、剩余预算/暴露检查与新 Lease 接受，不能因为需要恢复就隐式重试。机器重启无法判断是否执行过时按未知/期限处理，不以“没有结果文件”推断未执行。

到最终期限，由可信测试时序证据驱动原子终态与冻结资金处置；客户端不可达时不能假装已经释放，权威恢复后再按原记录处理。有限逻辑 deadline 不等于保证网络/主机永久故障时按现实时间到账。

## 3. 接口串接与依赖次序（候选）

下面是逻辑输入输出与写权限，**不是 wire schema/API 定义**。每个调用先做版本/签名/父引用/状态/幂等验证，拒绝不得修改协议业务状态；如记录拒绝审计，不得消费资金、暴露、attempt 或权利。

| 接口 | 冻结输入/责任 | 输出与原子边界 |
|---|---|---|
| prepare policies | Requester，版本/来源/用途/预算/终态矩阵，无 ReceiptID 回指 | Funding/Settlement policy 内容摘要；随后由 Receipt 引用 |
| register task | Requester 签署的完整 ComputeReceipt、政策/Profile/输入及部署引用 | 新 ReceiptID；任一语义改变产生新 ID；无合法政策则创建失败 |
| activate lease | 合法 WorkPlan/Assignment、Provider 接受、Receipt、资金/暴露额度 | 唯一 active Lease + 单调 epoch + 两类预留 + EventRecord，同一事务或先证明等价补偿 |
| dispatch/start | active Lease 派生的 capability、固定执行元组、当前期限/epoch | Dispatch/RPR 两处检查同一权威；持久 intent 后消费唯一 attempt，再执行 |
| accept result | Provider 签名、当前 Lease/epoch、完整 outcome 与输入引用 | 原子接纳+事件+稳定回执；同幂等键异内容冲突 |
| decide terminal | 冻结 Profile/Snapshot/AssumptionEvaluation、完整证据或有界停止事实 | 唯一 VerificationDecision/准确终态+事件；audit-only 不输出 TRUSTED |
| settle | 已提交终态、原政策、合法履约、可用预留 | 派生分项 EntitlementKey；付款/退款/释放+事件原子提交，重试取原结果 |
| recover/query | 当前已认证状态或保存的原回执/锚点 | 不新建业务权利或 guest 调用；未知不推断，恢复推进仍走上述同一入口 |

**修正规划次序，不修改历史实验：** 原迁移清单 F5 中的政策 schema/矩阵必须拆出前半部分，在 F2 Receipt 之前完成；F5 只实现终态驱动的记账和恢复。资金政策不能以将来的 ReceiptID 参与自身摘要，随后 Receipt 又摘要政策，形成哈希环。拟以独立政策内容摘要及 Requester/nonce/部署绑定，由 Receipt 单向引用；登记实例的 Receipt 关联在后续登记/事件中表达。如何满足协议 §3 的可解析关联仍需 schema 审查，不能靠空 ID 或常数绕过。

同理，验证“计划/Snapshot 构造政策”在 Receipt 时冻结，实际 EligibilitySnapshot 在首次 draw 前产生并引用 Receipt，不能先求未来快照摘要再计算 ReceiptID。Lease proposal/accept/active、EventRecord 的自摘要/签名排除字段与因果边也要作无环性检查。

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

本 ADR 的接受至少需要：

1. D-1～D-6 各有明确审阅处置；不能以工具运行 PASS 视为接受。
2. 对 D-2 终态/资金矩阵、D-3 非主网 contract、D-4 签名 envelope 和密钥时效补齐候选细节及反例，无静默默认值。
3. 按 CONTRIBUTING §7 同步审核 protocol-spec、task-lifecycle、invariants、threat-model、v1-profile、身份/架构和相关 Profile；本轮未修改这些权威语义。
4. 新 schema、registry/tag、Python/Rust 无共享 codec/hash 的正负向量、拒绝前后状态不变性质检查。
5. 每个实现阶段以新正式对象重跑至少原对应双机矩阵；未知、并发、截止、迟到、恢复和负例单列。
6. ADR-0006 接受与完整 RIR/RPR conformance 的阻断项不能由本 ADR 顺带关闭。

可独立审阅、可先做候选向量；正式入口在所需规范/schema 未冻结时保持未启用。剩余 B/Q、真实资金、主网 assurance、权威抗回滚、物理断电和独立维护者审计继续单列。

## 2026-10-26 工作范围更正

本文件保留为正式对象迁移的候选设计；此前 WORK4/F0 命名不计入原定第四项。原定第四项是 B/Q 的反例与校准研究，已由[第一片](../06-research/bq-boundaries-slice1.md)开始；本草案未被接受，不更改协议或其余工作状态。
