# ADR-0004：验证 Profile 与有限总体 e-process 边界

> 状态：`ACCEPTED`
> 决定日期：2026-08-19
> 适用范围：结果验证、VerificationProfile、Snapshot、Aggregate、Decision、G0/G1
> 关联：OQ-06、OQ-07、OQ-08；TH-15—TH-20；INV-10—INV-12、INV-14

## 1. 背景

此前候选验证公式把 Bayesian posterior、anytime-valid 风险界和相关性处理并列为三个真理闸门，但没有定义统计命题、错误支持上界或正确候选活性边界。后续反例证明：实际支持票数不超过某个预算，不足以支持不放回 Type-I 定理；需要在随机排列前冻结、且与排列独立的错误支持能力集合上界。

同时，不同任务的正确性锚点不同。任务专用 predicate、证明验证、条件性重执行和纯审计重执行不得被强制压入同一投票模型。

## 2. 决定

1. **VerificationProfile 是所有验证路径的严格前置对象。** Profile 必须声明 `VerifiedClaim`、`ExcludedClaims`、证据类型、正确性假设、活性假设、成本、终态和 conformance。
2. **验证路径分为 `DIRECT_VERIFIED`、`PROOF_VERIFIED`、`REEXEC_BOUNDED` 与 `REEXEC_AUDIT_ONLY`。** 具体 Registry ID 仍由后续 Schema 冻结。
3. **`REEXEC_BOUNDED` 使用单任务、单候选、二元集群证据的有限总体 e-process。** 其数学内核采用 `H0: c 无效且错误支持能力集合大小不超过 B`，活性边界使用 `M(c)≥Q`。
4. **`B` 上界能力集合，不上界事后票数。** 能力集合必须先于抽样排列确定并与排列独立；只限制实际票数的模型被反例拒绝。
5. **Bayesian 只优化效率。** 与任务类活性有关且不依赖本轮观察的信息可以形成观察前冻结的备择 mixture，但 `PosteriorRisk` 不再作为独立真理闸门。CapabilityEstimate、FoundationReport 和个体历史不得进入 mixture；分量死亡后不得重新归一化。
6. **接受权来自 anytime-valid e-process。** 在 Bridge、Snapshot 和随机性前提有效时，累计资本达到 `1/epsilonF` 才能进入 `TRUSTED` 候选。
7. **活性与安全分离。** `B/epsilonF` 属于安全边界；`Q/deltaQ/deltaL/Nrequired` 属于活性和成本。增加预算不能补偿未建立的 `B`，也不能补偿 `Q≤B`。
8. **规范计算使用精确或等价确定算术。** `NULL_BOUND_EXACTLY_EXCEEDED`、分量活性失效和 `p=0,X=0` 必须有离散语义，不得依赖浮点无穷、NaN 或实现自选 cap。

## 3. 状态边界

本 ADR 接受：

- VerificationProfile 的前置地位；
- 单任务、单候选有限总体数学对象；
- 能力集合上界语义；
- Bayesian mixture 的非真理权角色；
- DP 活性预算与对拍测试要求。

本 ADR 不证明或关闭：

- 通用 permissionless 总体的 `B`；
- 具体任务 Profile 的 `Q` 校准；
- RIR、RPR、validator 或 task predicate 正确；
- 多候选、多任务或非二元扩展；
- `DIRECT_VERIFIED`/`PROOF_VERIFIED` 的具体 Registry 和实现；
- 任何外部用途、Requester 意图或 Source→RIR lowering 正确性。

因此，数学内核是条件性 `DECIDED/DERIVED`；具体 `REEXEC_BOUNDED` 部署 Profile 仍为 `CANDIDATE/P0`。

## 4. 被替代和拒绝的候选

| 旧候选 | 处置 | 理由 |
|---|---|---|
| `PosteriorRisk ∧ AnytimeRiskBound` 双真理闸门 | `SUPERSEDED` | posterior 不增加模型内 Type-I 安全，并引入额外治理与活性阻断 |
| 只限制实际错误支持票数 | `REJECTED` | `C>B` 时可按抽样顺序搬移有限票数，已有精确反例 |
| design effect/ESS 进入安全似然 | `REJECTED` for this Profile | 未知相关性下可能产生虚假精度 |
| `3×KL` 作为 `Nmax` 规则 | `REJECTED` | 只是一阶规划近似；精确 DP 成本足够低 |
| mixture 分量死亡后重归一化 | `REJECTED` | 观察后补充资本，破坏冻结 mixture 证明 |

## 5. 后果

- 普通 permissionless 重执行在无法建立 `B` 时只能形成 `REEXEC_AUDIT_ONLY` 证据；
- V1 应优先实现 VerificationProfile Schema 和 `DIRECT_VERIFIED` 任务类；
- `REEXEC_BOUNDED` 的主要成本转移到能力集合、相关性和共因故障论证；
- `TRUSTED` 必须绑定 `VerifiedClaim`，不得被外部系统解释为 Source intent、规范无缺陷或业务适用性保证；
- G1 必须对安全反例、活性分位数、成本和参数适用域分别出具证据。

## 6. 验证证据

数学说明见 [`../06-research/verification-round-mathematical-model.md`](../06-research/verification-round-mathematical-model.md)。标准库对拍测试见 [`../../tests/verification_model/`](../../tests/verification_model/)。当前测试包括递推/闭式、DP/全枚举、最坏自适应弃票和能力集合反例。
