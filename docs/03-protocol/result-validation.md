# ACLt Protocol 结果验证

> 当前执行见[开发政策](../development-policy.md)（2026-11-19）；本页旧 SHA 校验与审批要求按该决定处理。


> 文档状态：`CANDIDATE` verification design  
> 语义基线：v0.5  
> 最后更新：2026-08-21
> 适用范围：有限总体 e-process 的条件模型、Profile对象与已有验证路径。工程部署记录实际 network/assurance；活性推广继续由 #215 跟踪。

## 1. 验证目标

结果验证消费 Receipt 声明的任务语义、证据模型、相关性处理、误差目标、预算和停止规则，对具体候选结果给出该方法下的判决。每项结论列出其模型条件、使用数据与实际实现范围。不同方法分别说明执行过程与成本。

## 2. 任务验证 Registry

每个 Receipt MUST 引用一个版本化 `VerificationProfile`；具体证据方法作为其 `VerificationType`。Registry 的对象类型、快照结构与校验规则以 [`verification-profile-schema.md`](verification-profile-schema.md) 的 §3.1、§3.5、§5 与 §6 为权威；Profile、Claim、ExcludedClaims、MainnetAssurance、五相位 validator 与 canonical encoding 的当前权威语义见同一文件。该文件已关闭 P0-1A；P0-1B 实现覆盖仍在进行。

为避免与首个工程目标 `V1` 混淆，不再使用 `V0–V3` 作为验证类型占位编号。候选类别仅表示方法族，具体 Registry ID 尚未冻结：

| 候选类型 | 可能语义 | 优点 | 局限 | 状态 |
|---|---|---|---|---|
| `REEXEC_EXACT` | 确定性 RIR 重执行/精确比较 | 语义较清晰 | 成本可能接近原计算；同源 runtime/compiler 故障 | `CANDIDATE` |
| `TASK_PREDICATE` | 任务专用谓词或解析式检查 | 可显著降低成本 | 只覆盖特定任务 | `CANDIDATE` |
| `STATISTICAL` | 冗余、抽样或统计检查 | 可调成本和证据 | 相关性与统计证明困难 | `CANDIDATE` |
| `PROOF_ASSISTED` | 密码学证明、交互证明或可信执行证据 | 可能提供更强证据 | 适用性、性能、信任和实现复杂 | `CANDIDATE` |

上述类别用于方法讨论；互操作采用具体实现已经支持的 Registry ID 和版本。

V1 `CORE` 的基础证据类型是 `REEXEC_EXACT`：验证者对相同规范 RIR、Logical Object 输入和 RuntimeProfile 重执行，并依据冻结的 canonical result/equivalence predicate 形成证据。该选择只闭合证据接口，不证明 RIR、RPR、validator 或重执行结果正确。

Profile 分为 `DIRECT_VERIFIED`、`PROOF_VERIFIED`、`REEXEC_BOUNDED` 与 `REEXEC_AUDIT_ONLY`。只有前三者在各自前提成立时可以产生 `TRUSTED`；没有可审计的支持能力上界时，重执行只能使用 `REEXEC_AUDIT_ONLY`。权威决定见 [`../05-decisions/ADR-0004-verification-profiles-and-finite-population-e-process.md`](../05-decisions/ADR-0004-verification-profiles-and-finite-population-e-process.md)。

官方主网还必须绑定版本化 `MainnetAssuranceProfile`，声明 `network_id`、Profile capability、允许的 RPR/validator/log backend、相关性策略、有效期与损失预算。它是部署准入，不是额外证据权重；主网外环境不继承该声明。工程信任边界见 [ADR-0005](../05-decisions/ADR-0005-engineering-assumptions-and-mainnet-assurance.md)。

## 3. 验证生命周期

1. **部署准入**：检查绑定网络的 assurance、Profile capability、组件允许集合与有效期；
2. **候选形成**：接收绑定合法 RIRVersion/runtime/current-epoch 的 ResultSubmission；
3. **方法确认**：验证 Receipt 引用的 VerificationType 可用；
4. **结果规范化**：应用预声明等价/聚类规则；
5. **Snapshot**：冻结有限总体、排除、分层、相关性和证据摘要；
6. **随机承诺**：在观察 draw 结果前固定随机性来源；
7. **Sample**：生成不放回 draw；
8. **Verify**：产生带来源、方法、成本和关联信息的证据；
9. **Aggregate**：更新置信或证据状态；
10. **Stop/continue**：应用预声明停止规则；
11. **Decision**：原子提交 `TRUSTED` 或 `UNRESOLVED`；
12. **Evidence update**：追加可归责记录，不产生 Rank。

## 4. EligibilitySnapshot

首次 draw 前 MUST 冻结：

- population definition 与大小；
- 抽样单位；
- 纳入、排除和重复处理；
- strata 与各层规则；
- control/correlation clusters 及未知关联处理；
- 证据版本和候选结果摘要；
- 随机性承诺；
- error target、tolerance 和 stopping rule；
- `VerificationProfile`、`VerifiedClaim`、`ExcludedClaims`；
- `network_id`、`MainnetAssuranceProfile` 版本/digest、组件允许集合与绝对损失上限；
- 若使用 Bayesian policy：仅用于效率的 prior、likelihood、采样提案和 prior sensitivity policy；
- `REEXEC_BOUNDED` 的 \(G,B,Q,\varepsilon_F,\delta_Q,\delta_L\)、e-process 算法版本、精确算术规则和冻结混合权重；
- 支持能力集合冻结、随机排列独立性、Bridge 与活性校准的证据引用、适用假设和失效条件；
- Npopulation、Nbudget、Npolicy；
- 验证 FundingPolicy 和 SettlementPolicy。

任何实质字段在观察后改变，当前验证 MUST 失效；不得选择性保留有利证据。

## 5. 有限总体与 Nmax

当前接口为：

\[
N_{max}=\min(N_{population},N_{budget},N_{policy})
\]

- `Npopulation`：Snapshot 中不同抽样单位数量；
- `Nbudget`：授权验证预算可支持的最大 draw；
- `Npolicy`：Receipt/ProtocolVersion 允许的政策上限。

Nmax 只限制最多使用多少证据，不保证该数量足以安全背书，也不具有 51% 默认含义。

## 6. 不放回有限总体 e-process

`REEXEC_BOUNDED` 检验候选 \(c\) 的零假设：候选无效时，冻结总体中**有能力支持该错误候选**的相关集群集合 \(A^-(c)\) 在随机排列前固定，且 \(|A^-(c)|\le B<G\)。\(B\) 不是本轮实际支持票数上界，也不能由本轮票数反推。更一般的充分数学条件是每一步的条件支持概率不超过下式；冻结能力集合是当前可审计的实现方式。

令第 \(t\) 次 draw 前剩余单位数 \(R_t=G-t+1\)，累计支持数为 \(s_{t-1}\)，则零假设条件概率为：

\[
p_t=\frac{B-s_{t-1}}{R_t}.
\]

对于备择总体支持数 \(m\ge Q>B\)，令：

\[
q_t^{(m)}=\frac{m-s_{t-1}}{R_t},\qquad
E_t^{(m)}=
\begin{cases}
q_t^{(m)}/p_t,&X_t=1,\\
(1-q_t^{(m)})/(1-p_t),&X_t=0.
\end{cases}
\]

资本 \(M_t^{(m)}=\prod_{j=1}^tE_j^{(m)}\)。使用首抽前冻结、总和为一的有理权重 \(\pi(m)\) 时，\(M_t^{mix}=\sum_m\pi(m)M_t^{(m)}\) 仍为非负 e-process；达到 \(M_t^{mix}\ge1/\varepsilon_F\) 才可精确拒绝零假设。当前接受路径使用该 e-process 阈值；已有设计也将 Bayesian 信息用于候选、采样和成本规划。权重来源的选择与数学条件分别记录。

在上述条件成立时，Ville 界给出：

\[
\Pr_{c\ invalid}\!\left(\exists t:M_t^{mix}\ge1/\varepsilon_F\right)\le\varepsilon_F.
\]

关键状态必须按以下语义实现：

- \(p_t=0\land X_t=1\)：`NULL_BOUND_EXACTLY_EXCEEDED`，是在已建立假设条件下对零假设的精确否证；
- \(p_t=0\land X_t=0\)：普通更新，不是特殊失败；
- 某个混合分量与历史不相容：该分量资本局部归零，权重不得事后重归一；
- 外部证据撤销能力集合冻结、随机性或 Bridge：`ASSUMPTION_INVALID`，不得继续生成 `TRUSTED`；
- 预算耗尽或全部有效路径死亡：`UNRESOLVED`。

活性假设与安全假设分开。若正确候选至少得到 \(Q\) 个集群支持的校准覆盖率为 \(1-\delta_Q\)，并由精确有限总体动态规划选择最小 \(N_{max}\) 使 \(\Pr(\tau\le N_{max}\mid M(c)\ge Q)\ge1-\delta_L\)，则端到端活性失败界至多为 \(\delta_Q+\delta_L\)。KL 近似只能用于规划，不能生成规范预算。

条件数学模型、证明边界和对拍结果见 [`../06-research/verification-round-mathematical-model.md`](../06-research/verification-round-mathematical-model.md)。条件 Type-I 推导与递推已有记录；活性推广仍由 #215 跟踪。具体部署的 \(B\)、\(Q\)、能力集合冻结与独立性论证仍为 `CANDIDATE / P0`。没有这些证据时必须使用 `REEXEC_AUDIT_ONLY`。

## 7. 相关性与有效证据

原始 Provider 数量不是有效独立样本量。相关性信号包括共同控制、资金、网络、设备、硬件镜像、软件栈和协调行为。

可选处理方案：

| 方案 | 优点 | 风险 |
|---|---|---|
| 每个相关集群计一次 | 简单、保守 | 误聚类会损失有效证据 |
| 集群权重上限 | 连续可调 | 参数和组合方式复杂 |
| design effect / ESS 折减 | 可表达部分相关 | 估计错误可能产生虚假精度 |
| 最坏情形敏感性 | 安全边界清晰 | 可能频繁 UNRESOLVED |
| 混合方案 | 兼顾硬边界和利用率 | 需要证明和仿真 |

当前建议为“硬集群暴露上限 + 保守证据折减 + 最坏情形敏感性”，但算法仍未冻结。未知相关性 MUST NOT 设为零。对 `REEXEC_BOUNDED`，相关性处理最终必须产出对支持能力集合的事前上界 \(B\)；事后观察到的票数或 Provider ID 数量不能替代该论证。

## 8. VerificationEvidence

每条证据至少绑定：

- ReceiptID、RIRVersion/Profile、runtime、Result digest、VerificationType 和版本；
- 执行 Verify 的 Principal/Node 与签名；
- 输入、输出、时间、环境和资源；
- control/correlation references；
- 成本、失败和不确定信息；
- draw index、stratum 和 Snapshot digest；
- 幂等键和因果父事件。

格式正确但任务方法不适用的证据 MUST 被拒绝。

## 9. Aggregation 与停止

当前 Aggregate 采用显式输入与确定更新规则。混合权重的非负、归一化与观察前固定条件见模型；CapabilityEstimate 与维护报告在当前接口中分别记录。未来方法的来源选择按其具体模型评估。

停止条件必须明确：

- 被支持的命题/结果簇；
- 误差或证据目标；
- 相关性和异质性处理；
- 最大成本、draw 和时间；
- 多候选结果冲突；
- 验证器失效、随机性失效和总体污染；
- 到达边界后的终态。

## 10. Decision 语义

### `TRUSTED`

只表示 `VerifiedClaim` 在冻结模型、数据、假设、主网 assurance 和停止条件下满足协议背书要求。Decision MUST 携带完整证据链、Profile、模型版本、`network_id`、assurance 引用和 `ExcludedClaims`。对于重执行，默认只背书“绑定的 RIR 在绑定的 RPR/equivalence 语义下得到该结果”，不背书 Source→RIR lowering 正确，也不背书结果符合 Requester 的未编码意图或主网外环境。

### `UNRESOLVED`

表示在 Nmax、预算、政策或有效性边界内无法背书单一结果。它不表示所有结果相同错误，也不表示继续增加未授权验证一定能解决。

Maintainer、Requester、多数 Provider 或高能力 Provider MUST NOT 覆盖 Decision。

## 11. 故障与攻击响应

| 情况 | 必须响应 |
|---|---|
| VerificationType 不支持 | UNSUPPORTED 或创建拒绝 |
| 验证器异常/缺陷 | 证据无效；UNRESOLVED 或 FAILED |
| Snapshot 事后改变 | 当前流程失效 |
| 随机性承诺无效 | 不得 TRUSTED |
| 重复 draw | 不增加有效证据 |
| 相关性未知 | 保守折减和硬限额 |
| Nmax/预算耗尽 | UNRESOLVED 或 FUNDING_EXHAUSTED |
| 两个 Decision 并发 | 原子唯一约束；只允许一个提交 |
| 维护者要求改权重 | 拒绝；通过未来版本处理 |
| assurance 缺失、过期、撤销或组件不匹配 | 创建期降级/拒绝；运行期 `VERIFICATION_INVALIDATING`，不得产生新的 `TRUSTED` |
| 多个假设同时失效 | 保存完整规范 `CauseSet`，由冻结 reducer 派生唯一 `EffectiveVerdict`；不得人工挑选原因 |
| 日志 checkpoint/finality/inclusion/consistency 无法验证 | 对应事件不产生协议效力；fail closed |

## 12. 验收与证明义务

具体主张按其所使用的机制提供对应证据。已有研究与实现检查包括：

- Verification Registry 与结果等价负例；
- Snapshot canonical schema；
- 可审计随机性与不放回 draw；
- `VerificationProfile`、`VerifiedClaim`、`ExcludedClaims` 和成本接口；
- \(B\) 对支持能力集合的事前上界论证，以及集合与 draw order 的独立性证据；
- \(Q,\delta_Q,\delta_L\) 校准来源、外推标记和精确 DP 活性预算；
- e-process 公式、冻结混合权重、精确有理数/定点数规则与逐步测试向量；
- 混合权重构造、观察前固定条件与 prior sensitivity；
- 相关性/集群处理的误差与隐私分析；
- optional stopping、能力集合事后选择反例、恶意依赖和总体污染测试；
- false endorsement、false unresolved、成本和尾延迟测量；
- 并发、重放、崩溃恢复和唯一 Decision 测试；
- 独立递推实现与闭式/全枚举 oracle 的持续对拍；
- 参数敏感性及反证条件。
- frontend lowering、RPR/Host OS 与验证器共因错误的差分/故障测试。
- `MainnetAssuranceProfile` 的网络/版本/组件/有效期/减权/损失预算正反向量；
- `CauseSet + EffectiveVerdict` 的多原因组合对拍；
- append-only/finality 日志的 inclusion/consistency、重组、恢复和旁路测试。

## 13. 文献边界

有限总体 confidence sequence、非负超鞅和 Bayesian sequential inference 文献可以证明各自在特定模型下的方法存在，但不自动证明 ACLt 部署的能力集合上界、相关控制、任务语义或验证器正确。详细映射见 [`../06-research/claims-and-sources.md`](../06-research/claims-and-sources.md)。

## 14. 更新规则

变更更新实际受影响的定义、接口、模型和证据入口。已有 Threat、INV 与 ADR 用于定位相关讨论；同步范围由本次实际影响确定。
