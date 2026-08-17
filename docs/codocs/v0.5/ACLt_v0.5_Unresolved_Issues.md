# RUDCP v0.5 未解决问题清单

> 文档状态：v0.5 后续研究基线  
> 目的：界定进入 v0.6 前仍需解决、形式化或验证的问题  
> 范围：协议语义、验证理论、信任与风险、经济机制、治理边界

## 1. 基线与已冻结前提

本文以 **RUDCP v0.5 的语义冻结稿**为基线，并吸收 v0.5 之后已经确定的修正。以下结论视为当前设计前提，不再列入未解决问题：

- RUDCP 是协议，而不是区块链；区块链仅保留为未来可选实现。
- 遵循 **Entity Minimality Principle（实体最小化原则）**：任何职能，只要可由现有角色、公开协议规则或确定性算法完成，就不新增独立实体、身份组或特权中介。
- 核心经济参与者为 `Requester + Broker + Provider`。
- Foundation 仅承担维护、分析、披露及当前外围职能；其报告不得进入协议权重，也不得人工覆盖协议状态。
- 信誉与验证权解耦。
- “51% Provider”不再是 $N_{\max}$ 的默认安全含义。
- 通过积分增发支付验证成本，已降级为可选的 funding policy，而不是协议不变量。

## 2. 优先级定义

| 优先级 | 含义 |
|---|---|
| **P0** | v0.6 理论或协议闭合所必需；应优先解决 |
| **P1** | 不一定阻塞最小核心协议，但必须形成明确边界、接口或后续方案 |
| **P2** | 可在核心技术与经济模型稳定后处理的治理或法律问题 |
| **P0/P1** | 项目级约束：既影响核心可行性，也可随设计逐步细化 |

## 3. 十四组未解决问题

### 3.1 通用 Assignment / Job 的正式语义仍未闭合【P0】

已知 Requester 提交 Job，Broker 按“最简贪心 + 基本边界”将其拆为合法 Assignment，但以下内容尚无正式定义：

- 哪些计算可以表示为 Assignment；
- Assignment 间的依赖关系如何表达；
- 输入与输出如何引用；
- 执行环境如何描述；
- 资源限制如何声明；
- 失败、超时与中断状态如何表示。

**建议：** 先冻结最小 Assignment Schema 和状态机，不追求一次支持所有计算类型。

### 3.2 Broker 的“最简贪心拆单”仍缺数学定义【P0】

当前原则是：Broker 只保证拆分结果合法，不保证全局最优；Requester 也可以自行拆单。但“最简”“贪心”与“不过分”的边界仍未定义，包括：

- 最小与最大 Assignment 规模；
- 最大拆分数量；
- 依赖关系保持；
- 对无意义重复计算的禁止规则。

**建议：** 定义一个 canonical greedy algorithm 和少量 hard constraints，不引入全局优化目标。

### 3.3 验证的统计停止规则仍是核心未解决问题【P0】

协议已不再采用简单的“多数票 + 51% Provider”作为安全定义。真正的问题是：在有限 Provider 总体、分轮无放回抽样的条件下，何时已有证据足以停止验证？所需决策形式为：

$$
Evidence_t \rightarrow Stop/Continue
$$

该规则还必须允许在任意时点检查，而不破坏统计有效性。

**建议：** 优先研究 finite-population anytime-valid sequential verification，例如有限总体下的 sequential test 或 confidence sequence，而不是预先指定固定样本量。

### 3.4 “可信”的含义仍需形式化【P0】

协议不能声称输出“绝对正确”，而应输出类似：

$$
Result=R^*,\qquad EvidenceStrength=s
$$

其中关键问题是如何定义 $s$。参与者并非严格 IID，Provider 之间还可能存在一致行动与 correlated failure，因此不能把证据强度误写为不存在的绝对真值概率。

**建议：** 将目标明确为“在公开假设下达到某个可解释的证据阈值”，并完整披露该阈值依赖的假设。

### 3.5 Sybil / 一致行动人的安全边界仍未证明【P0】

当前经济直觉是：若取得足够 capability / evidence history 的成本高于攻击回报，同时验证奖励池固定，则批量养号缺乏明显的协议内套利空间。这可以降低攻击动机，但仍不能把：

$$
P_1,\ldots,P_n
$$

数学上视为严格独立。

**建议：** 将 Sybil resistance 写成明确的 threat model，而不是宣称问题已经解决；通过身份成熟成本、历史证据、无放回抽样和经济模拟，证明攻击成本下界。不得为解决 Sybil 问题直接新增身份认证机构。

### 3.6 Capability / Evidence / Exposure 模型仍需数学化【P0】

不能继续让单一 “Rank” 同时承担身份、信誉、能力、验证权与任务规模五种含义。更清晰的关系应为：

$$
Evidence
\rightarrow CapabilityEstimate
\rightarrow Exposure/RiskDecision
$$

节点完成过多少任务、哪些被证伪、哪些未完成，属于 evidence；协议据此估算节点在某类任务上的可靠能力，再决定允许其承担多大的经济暴露。

**建议：** 将旧 Rank 拆成相互独立的量。Rank 最多保留为 UI 层摘要，不再作为安全原语。

### 3.7 Maximum-Trust 原则的准确统计含义仍未闭合【P1】

当前核心指标为：

$$
FailureRate=\frac{F+I}{T}
$$

其中，被证伪数量 $F$ 与接受后未完成数量 $I$ 才构成负证据；`UNRESOLVED` 不算错误。该定义适合作为“最大信任”历史指标，但“未被证伪”不等于“已验证正确”。

**建议：** 保留 Maximum-Trust 作为 exposure 决策的证据之一，同时单独记录 verified evidence，不再强行压缩为一个“正确率”。

### 3.8 Non-deterministic Computation Consensus 仍明确搁置【P1】

浮点差异、不同 GPU 实现、随机算法、Monte Carlo 与机器学习训练等任务都可能出现：

$$
R_1\neq R_2
$$

但双方均未失常。

**建议：** v0.x 首先严格支持 deterministic / canonicalizable computation；将 `EXACT`、`TOLERANCE`、`STATISTICAL`、`APPLICATION-DEFINED` 等 verification semantics 留作扩展，不让非确定性共识阻塞核心协议。

### 3.9 不可操纵的审计与抽样随机性仍未确定【P1】

Requester 没有审计决定权，Foundation 也没有，因此仍需定义：

$$
Audit(A)=?
$$

以及验证者如何被随机选取。

**建议：** 先规定随机选择接口必须满足“公开、可重现、事前难预测、单方难操纵”，再选择 VRF、randomness beacon、commit–reveal 等具体实现。协议先定义所需性质，不提前绑定技术。

### 3.10 验证达到极端状态后的终止语义仍需定稿【P1】

验证不是无限争论。系统实际运行验证程序本身就是有效服务，因此 `UNRESOLVED` 不自动触发退款。但旧定义：

$$
N_{\max}=51\%\ Providers
$$

不应继续作为默认安全定义。

**建议：** 将 $N_{\max}$ 定义为资源或有限总体意义上的 hard safety cap，主要停止依据则由 sequential evidence rule 决定。达到 cap 仍无法得出可信结果时，输出 `UNRESOLVED + complete distribution`。

### 3.11 验证成本最终由谁承担仍未决定【P1】

过去提出的“验证奖励 $aC$ 由凭空创造的积分支付，并成为主要通胀机制”现已降级为候选方案，而不是协议不变量。可能的资金来源包括：

- 协议增发；
- Requester verification fee；
- Foundation 或其他 subsidy；
- 系统收入池；
- 混合机制。

应先把验证定义为真实资源成本：

$$
C_v
$$

**建议：** 独立设计 $FundingPolicy(C_v)$，避免让货币政策绑死验证协议。

### 3.12 积分、支付锁定和市场定价仍未完整设计【P1】

尚需解决：

- Requester 如何锁定报酬；
- Provider 在接受 Assignment 前如何确认付款保证；
- Assignment 完成、失败或取消时如何结算；
- Broker fee 如何支付；
- 余额是否允许为负。

Foundation 的 Fiat ↔ Credit 通道只是外围入口，不负责定价。

**建议：** 先设计协议原生的 escrow / settlement，再研究积分与法币的外围关系。

### 3.13 Administrative Cost / Economic Viability 仍是项目级未解决问题【P0/P1】

该问题决定系统是否值得存在，而不是普通性能优化。定义额外成本与有效计算成本的比率：

$$
\rho=
\frac{
C_{\text{protocol}}+C_{\text{verification}}+C_{\text{network}}+C_{\text{maintenance}}
}{
C_{\text{useful compute}}
}
$$

如果 trust minimization 的额外成本超过分布式闲置算力带来的优势，则协议即使安全，也没有经济价值。

**建议：** 在大规模实现之前建立 cost model 与 Monte Carlo / agent simulation，寻找任务规模、争议率、验证率和网络规模变化下的 break-even frontier。

### 3.14 Protocol Governance 与 Foundation 法律外壳仍未解决【P2】

Foundation 的权力边界已经明确：维护、分析与披露；其报告不得进入协议权重，也不能人工覆盖协议状态。但以下问题仍未解决：

- 新协议版本如何被网络接受；
- Foundation 采用何种法律实体与注册方式；
- Fiat ↔ Credit 涉及哪些监管义务。

**建议：** 技术治理坚持：`Foundation proposes, implementations remain open, nodes adopt`。法律结构应在经济模型与积分性质稳定后再设计，避免法律实体反向塑造核心协议。

## 4. v0.6 关键依赖链

v0.6 是否成立，并不要求十四个问题同时彻底解决。最关键的理论与协议依赖链为：

$$
\boxed{
Assignment\ Semantics
\rightarrow
Broker\ Breaking
\rightarrow
Evidence\ Model
\rightarrow
Sequential\ Verification
\rightarrow
Sybil/Correlation\ Assumptions
\rightarrow
Exposure\ Decision
}
$$

在上述链条闭合后，才能稳妥进入：

$$
Payment/Funding
\rightarrow
Economic\ Simulation
\rightarrow
Engineering
$$

可将其概括为三个阶段：

1. **语义闭合：** Assignment Semantics → Broker Breaking；
2. **信任闭合：** Evidence Model → Sequential Verification → Sybil/Correlation Assumptions → Exposure Decision；
3. **落地验证：** Payment/Funding → Economic Simulation → Engineering。

## 5. 已删除或降级的旧问题

以下旧问题不再作为独立的核心研究问题：

| 旧问题 | 当前处理 | 替代问题或框架 |
|---|---|---|
| “51% 是否安全？” | **删除为核心问题** | finite-population stopping、sequential evidence rule，以及仅作为资源上限的 $N_{\max}$ |
| “如何设计一个统一 Rank？” | **删除为核心问题** | $Evidence\rightarrow CapabilityEstimate\rightarrow Exposure/RiskDecision$；Rank 最多作为 UI 摘要 |
| “应增发多少积分支付 verifier？” | **降级为资金政策问题** | 将真实验证成本 $C_v$ 与 $FundingPolicy(C_v)$ 分离 |
| “是否需要新增 Validator / Scheduler / Judge / Registry 等实体？” | **原则上删除** | 由现有角色、公开协议规则或确定性算法承担；仅在无法保持必要系统性质时新增实体 |

## 6. 当前结论

RUDCP v0.5 之后的主要工作，不是继续增加角色或堆叠机制，而是把既有设计原则转化为：

- 可执行的协议字段与状态机；
- 可解释、可检验的统计规则；
- 明确的攻击假设与经济边界；
- 与验证理论解耦的支付和资金政策；
- 能够通过仿真验证的项目级成本模型。

因此，v0.6 的首要目标应是闭合“Assignment 语义—证据—顺序验证—风险暴露”主链，而不是同时完成全部外围法律、治理和非确定性计算扩展。
