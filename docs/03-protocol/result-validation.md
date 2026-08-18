# ACLt Protocol 结果验证

> 文档状态：`CANDIDATE` verification design  
> 语义基线：v0.5  
> 最后更新：2026-08-18  
> 严格限制：当前方法尚未形成 ACLt 特定统计定理，不得声称验证安全已经证明

## 1. 验证目标

结果验证的目标是在 Receipt 预声明的任务语义、证据模型、相关性处理、误差目标、预算和停止规则下，判断是否可以对一个候选结果作有限背书。

验证不试图提供：

- 对任意程序语义的通用廉价判定；
- 对多个 Provider 独立性的证明；
- 简单多数或固定 51% 阈值；
- 绝对正确或不可撤销的形而上真理；
- 无预算上限的持续争论。

## 2. 任务验证 Registry

每个 Receipt MUST 引用一个版本化 VerificationType。Registry 至少需要描述：

- 适用任务族和输入/输出语义；
- 适用 RIRVersion、执行 Profile、runtime/effects 与规范结果表示；
- 结果等价或聚类规则；
- 验证器输入、输出和错误模型；
- 是否确定性、可重执行、可抽样或依赖证明；
- 资源、环境和独立故障来源；
- 允许的 Aggregation 与终态；
- 负例、已知盲点和升级规则。

为避免与首个工程目标 `V1` 混淆，不再使用 `V0–V3` 作为验证类型占位编号。候选类别仅表示方法族，具体 Registry ID 尚未冻结：

| 候选类型 | 可能语义 | 优点 | 局限 | 状态 |
|---|---|---|---|---|
| `REEXEC_EXACT` | 确定性 RIR 重执行/精确比较 | 语义较清晰 | 成本可能接近原计算；同源 runtime/compiler 故障 | `CANDIDATE` |
| `TASK_PREDICATE` | 任务专用谓词或解析式检查 | 可显著降低成本 | 只覆盖特定任务 | `CANDIDATE` |
| `STATISTICAL` | 冗余、抽样或统计检查 | 可调成本和证据 | 相关性与统计证明困难 | `CANDIDATE` |
| `PROOF_ASSISTED` | 密码学证明、交互证明或可信执行证据 | 可能提供更强证据 | 适用性、性能、信任和实现复杂 | `CANDIDATE` |

上述编号不得在 ADR 冻结前作为互操作规范。

V1 `CORE` 的基础证据类型是 `REEXEC_EXACT`：验证者对相同规范 RIR、Logical Object 输入和 RuntimeProfile 重执行，并依据冻结的 canonical result/equivalence predicate 形成证据。该选择只闭合证据接口，不证明 RIR、RPR、validator 或重执行结果正确。

## 3. 验证生命周期

1. **候选形成**：接收绑定合法 RIRVersion/runtime/current-epoch 的 ResultSubmission；
2. **方法确认**：验证 Receipt 引用的 VerificationType 可用；
3. **结果规范化**：应用预声明等价/聚类规则；
4. **Snapshot**：冻结有限总体、排除、分层、相关性和证据摘要；
5. **随机承诺**：在观察 draw 结果前固定随机性来源；
6. **Sample**：生成不放回 draw；
7. **Verify**：产生带来源、方法、成本和关联信息的证据；
8. **Aggregate**：更新置信或证据状态；
9. **Stop/continue**：应用预声明停止规则；
10. **Decision**：原子提交 `TRUSTED` 或 `UNRESOLVED`；
11. **Evidence update**：追加可归责记录，不产生 Rank。

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
- 若使用 Bayesian policy：prior、likelihood、posterior target 和 prior sensitivity policy；
- anytime-valid safety envelope、适用假设和失效条件；
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

## 6. 不放回序贯验证与候选双层决策

当前优先研究方向是在冻结有限总体内不放回抽样，并把“证据产生”和“序贯停止”分开：

1. **Exact evidence layer**：V1 对确定性 RIR 结果执行规范化精确比较；
2. **Sequential decision layer**：Bayesian policy 可以估计后验风险、选择下一样本或提出停止，但不能单独授予真理权；
3. **Safety envelope**：只有同时满足经证明的 time-uniform/anytime-valid 风险边界和相关性/最大损失限制时，停止提案才可以进入 `TRUSTED` 候选。

候选接受接口为：

\[
AcceptCandidate
\iff
PosteriorRisk\le\epsilon_B
\land
AnytimeRiskBound\le\epsilon_F
\land
CorrelationExposure\le L_{max}
\]

该公式当前只冻结组合边界，不冻结 posterior 定义、prior、统计目标、anytime bound 或参数。若 Bayesian 组件尚未被证明或配置，协议不得仅凭 posterior 输出 `TRUSTED`。

选择该方向的理由：

- 验证轮次可以随证据逐步扩展；
- 预算和延迟可以在达到条件时提前停止；
- 同一抽样单位不应被重复计为新证据；
- 有限总体可利用抽样比例信息。
- Bayesian policy 可以提高抽样效率并显式表达条件不确定性；
- anytime-valid safety envelope 可以限制可选停止与错误 prior 带来的过度确信。

尚未证明的关键内容：

- ACLt 的估计参数或检验目标是什么；
- 恶意、依赖和异质证据是否满足所选定理条件；
- strata 自适应、相关性折减和结果聚类如何进入证明；
- 随机性被偏置或总体被污染时的安全界；
- 多任务、重复攻击和时间依赖如何处理。
- prior 如何生成、冻结、审计并进行敏感性分析；
- posterior risk 与频率学错误界在有限总体、相关性和恶意依赖下如何共同成立；
- 两层条件冲突或其中一层失效时如何安全退化。

因此双层方法的 SemanticStatus 保持 `CANDIDATE`，Priority 为 `P0`，并作为 V1 CORE 阻断。已决定的只有有限总体、不放回、预承诺、显式不确定和不得由 posterior/历史能力单独授予真理权的边界。

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

当前建议为“硬集群暴露上限 + 保守证据折减 + 最坏情形敏感性”，但算法仍未冻结。未知相关性 MUST NOT 设为零。

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

Aggregate MUST 是可复算的纯规则或等价确定过程。它不得根据执行者身份、历史 CapabilityEstimate、FoundationReport、维护意见、付款能力或事后偏好改变真理权重。

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

只表示在冻结模型、数据和停止条件下满足协议背书要求。Decision MUST 携带完整证据链和模型版本。

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

## 12. 验收与证明义务

在允许安全主张前必须完成：

- Verification Registry 与结果等价负例；
- Snapshot canonical schema；
- 可审计随机性与不放回 draw；
- 统计目标、定理条件和证明；
- Bayesian prior/likelihood/posterior 的适用性、校准和 prior sensitivity；
- Bayesian stop proposal 与 anytime-valid safety envelope 的组合证明或反例；
- 相关性/集群处理的误差与隐私分析；
- optional stopping、恶意依赖和总体污染仿真；
- false endorsement、false unresolved、成本和尾延迟测量；
- 并发、重放、崩溃恢复和唯一 Decision 测试；
- 参数敏感性及反证条件。
- frontend lowering、RPR/Host OS 与验证器共因错误的差分/故障测试。

## 13. 文献边界

有限总体 confidence sequence 和 Bayesian sequential inference 文献可以证明各自在特定模型下的方法存在，但不自动覆盖 ACLt 的恶意 Provider、相关控制、错误 prior、分层自适应或任务验证器错误。详细映射见 [`../06-research/claims-and-sources.md`](../06-research/claims-and-sources.md)。

## 14. 更新规则

任何改变 VerificationType、Snapshot、抽样单位、相关性、随机性、停止条件或 Decision 语义的提议必须同步更新 Threat TH-15 至 TH-21、INV-11/12/14、ADR、仿真计划和 open questions。
