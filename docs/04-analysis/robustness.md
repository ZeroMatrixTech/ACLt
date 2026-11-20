# ACLt Protocol 鲁棒性分析

> 当前执行见[开发政策](../development-policy.md)（2026-11-19）；本页旧 SHA 校验与审批要求按该决定处理。


> 文档状态：Living evidence ledger  
> 语义基线：v0.5  
> 当前结论：完整候选架构已形成；整体鲁棒性 **未证明**  
> 最后更新：2026-08-21

## 1. 鲁棒性的严格含义

ACLt Protocol 不把鲁棒性视为一个单一布尔值。任何“系统鲁棒”主张都必须至少说明：

- 对哪类任务和部署；
- 在什么网络、时钟、存储和故障模型下；
- 攻击者控制哪些 Principal、函数、实现或维护权限；
- 允许何种 Sybil、串谋和外部收益；
- 保护哪个安全目标；
- 最大损失、错误率、延迟和资金上限；
- 证据来自证明、模型检查、仿真、故障注入还是外部试点；
- 哪些反例会推翻结论。

对外主张使用“鲁棒”一词时，须同时给出上述限定。

## 2. 鲁棒性维度

| 维度 | 目标 | 当前证据 | 状态 |
|---|---|---|---|
| 语义完整性 | 同一 ReceiptID 绑定同一义务 | INV-01/02 和设计规则 | `NORMATIVE / 未形式化` |
| 状态安全 | epoch、终态、结算在竞态下唯一 | INV-03—08 | `NORMATIVE / 未测试` |
| 资源与损失 | 尝试、预算、暴露和恢复有界 | INV-06/09/10 | `NORMATIVE / 参数开放` |
| 验证可靠性 | 条件性 TRUSTED，证据不足显式 UNRESOLVED | INV-11/12/14 | `CANDIDATE / 未证明` |
| Sybil/串谋 | 不假定独立，按相关性和硬上限控制 | Threat model + Exposure interface | `CANDIDATE / 未仿真` |
| 经济安全 | 资金守恒，攻击收益模型仅补充 | INV-06/10 | `部分确定 / 参数开放` |
| 条件性活性 | 在声明假设下推进或安全终止 | Lease/deadline/terminal design | `CANDIDATE` |
| 操作恢复 | 崩溃、分区、回滚和 DR 不破坏不变量 | INV-13/16 | `OPEN/P0` |
| 治理安全 | 维护者不能裁决个案 | INV-15、ADR-0001 | `DECIDED / 未测试` |
| 实现中立 | Adapter 替换保持语义 | INV-16 | `OPEN/P0` |
| 执行一致性 | frontend、compiler 与 runtime 保持同一 RIR/Profile 语义 | ADR-0002、INV-01/02/09/16 | `DECIDED direction / OPEN/P0 evidence` |
| 逻辑机器一致性 | Abstract Machine、Logical Object、Compile 和 Dispatch 不引入隐藏共享状态或权威 | ADR-0003、INV-01/02/08/16 | 边界 `DECIDED`；证据 `OPEN/P0` |
| 工程部署可信度 | 官方主网只在版本化组件、日志、有效期和损失预算内启用能力 | ADR-0005 | 边界 `DECIDED`；具体部署证据 `OPEN/P0` |

## 3. 证据等级

| 等级 | 证据 | 可支持的结论 |
|---|---|---|
| E0 | 设计直觉或类比 | 只能提出问题或候选方案 |
| E1 | 明确前提、机制、边界和反例 | 可形成 `DERIVED/CANDIDATE` |
| E2 | 机器化 Schema、状态机和性质测试 | 支持实现内安全属性 |
| E3 | 模型检查、数学证明或统计证明 | 支持声明模型下的性质 |
| E4 | 大规模仿真、故障注入和对抗实验 | 支持参数范围和工程风险结论 |
| E5 | 外部异构试点与持续运行数据 | 支持受限部署经验，不等于普遍证明 |

当前项目大多数安全结论处于 E1；16 条不变量的规范意图已定，但尚未整体达到 E2。

证据等级不是一条只能向“形式证明”前进的单线。规范算法优先追求 E2/E3；来源忠实性通常需要 E4，部署风险接受需要 E4/E5 与持续监控。工程证据不能证明开放世界真理，但可以在明确范围内支持能力启用。

## 4. 当前可支持的论证链

### RB-01：最小 Principal 集合缩小特权面

- 前提：Planner、Verifier 等输出可以被公开规则验证；
- 机制：只保留 Requester/Provider，把职能写成 permissionless functions；
- 结论：固定特权身份、信任根和治理接口更少；
- 边界：恶意函数输出仍必须验证，函数间串谋仍存在；
- SemanticStatus：`DECIDED`；ClaimQualifier：`DERIVED`；尚无量化净风险证明。

### RB-02：不可变 Receipt 提供共同义务引用

- 前提：全部实质语义进入 canonical encoding；
- 机制：变化生成新 ReceiptID；
- 结论：执行、验证和结算可以引用同一承诺；
- 边界：编码、哈希、内容可用性和版本迁移尚未完成；
- SemanticStatus：接口 `INVARIANT`；形式证据 `OPEN`；Priority：`P0`。

### RB-03：零抵押可与有界风险共存

- 前提：初始暴露、并发、价值、Lease、尝试和损失具有硬上限；
- 机制：证据驱动的 CapabilityEstimate 和 ExposureDecision；
- 结论：无需前置抵押也可限制单次绩效外部性；
- 边界：不消除 Sybil、弃单或探索预算攻击；
- 状态：`DECIDED/HYPOTHESIS`。

### RB-04：Lease/epoch 隔离迟到结果

- 前提：epoch 原子递增，所有输出绑定 epoch；
- 机制：旧 epoch 只保留为 stale evidence；
- 结论：迟到结果不能覆盖当前状态或产生当前权利；
- 边界：事务、时钟和分区模型尚未冻结；
- SemanticStatus：接口 `INVARIANT`；事务与时钟证据 `OPEN`；Priority：`P0`。

### RB-05：显式 UNRESOLVED 防止伪造确定性

- 前提：验证边界、Nmax 和失效条件预声明；
- 机制：不能背书时进入 UNRESOLVED；
- 结论：协议无需以无限成本或人工裁决强制给出答案；
- 边界：退款、过程费用和用户接受度仍需验证；
- 状态：`DECIDED`。

### RB-06：相关性感知优于标识多数

- 前提：多个身份可能同控或共享故障；
- 机制：集群上限、证据折减和最坏情形敏感性；
- 结论：不会把原始 Provider 数量直接当作有效独立证据；
- 边界：集群算法、隐私和误关联尚未解决；
- 状态：`DECIDED` 原则，`CANDIDATE` 方法。

### RB-07：资金守恒限制预算外损失

- 前提：全部资金来源与用途预声明；
- 机制：授权上限、资金桶、唯一权利和最多一次结算；
- 结论：实现不得通过隐性借用或临时发行掩盖成本；
- 边界：资产、精度、退款和资不抵债语义开放；
- SemanticStatus：接口 `INVARIANT`；账务语义 `OPEN`；Priority：`P0`。

### RB-08：维护最小权限防止个案捕获

- 前提：运行时守卫不依赖维护者裁量；
- 机制：维护只影响未来版本或追加更正；
- 结论：维护组织不能成为最高验证/结算裁判；
- 边界：发布密钥失陷、紧急响应和组织形式仍开放；
- 状态：`DECIDED / 未测试`。

### RB-09：规范 RIR 隔离源语言与协议语义

- 前提：不同 source frontend 可以共享一个可验证的机器/网络执行表示；
- 机制：Receipt 绑定 RIRVersion、RIRDigest 与执行 Profile，frontend/runtime 必须通过统一 conformance；
- 结论：Rust 或未来 C++23 frontend 不会仅因语言不同就合法改变协议执行义务；
- 边界：lowering、validator、runtime、effects、资源计量和共因 compiler 错误尚未验证；
- 状态：架构选择 `DECIDED`，鲁棒性结论 `OPEN/P0`。

### RB-10：Abstract Machine 与 Logical Object 隔离物理宿主状态

- 前提：Task 只读取显式 Logical Object 和 ExecutionProfile capability；
- 机制：不可变内容寻址对象、RPR default-deny Host OS 边界和 fail-closed validator；
- 结论：Provider 本地路径、RAM、环境变量或设备状态不能静默成为共享协议输入；
- 边界：Object Schema、capability ABI、内容可用性、RPR 和跨实现测试尚未完成；
- SemanticStatus：架构边界 `DECIDED`；鲁棒性证据 `OPEN`，Priority `P0`。

### RB-11：Compile 与 Dispatch 分阶段减少隐含权威

- 前提：Lowering、Decomposition、Packing 和 proposal/accept/active Lease 均可由冻结规则检查；
- 机制：Compile/Plan/Schedule 是 permissionless functions，Provider 必须显式接受 Lease；
- 结论：compiler、Planner 或 Scheduler 不能仅凭身份改变任务义务或强加执行责任；
- 边界：TaskGraph 等价、计划合法性、候选排序、时钟与并发状态机仍未冻结；
- SemanticStatus：边界 `DECIDED`；算法和证据 `OPEN`，Priority `P0`。

### RB-12：当前 Bayesian 策略与模型条件

- 前提：prior、likelihood、Snapshot 和提案接口在观察前冻结；
- 机制：Bayesian policy 只提出抽样顺序、候选或成本计划；`REEXEC_BOUNDED` 的接受仅由冻结有限总体 e-process 及其外部假设决定；
- 结论：posterior、历史能力或 FoundationReport 不能单独产生 TRUSTED；
- 研究：prior sensitivity 和效率收益仍需实验；观察前权重构造的来源属于具体模型选择，模型仍要求权重非负、归一化并在观察前固定；
- SemanticStatus：职责边界 `DECIDED`；效率模型 `CANDIDATE/P1`。

### RB-13：主网 assurance 将开放世界问题限域

- 前提：assurance 在结果出现前版本化绑定网络、组件、有效期、相关性策略和损失预算；
- 机制：能力取 `DISABLED/AUDIT_ONLY/ENABLED`，运行中只能保守减权；
- 结论：无需先证明所有身份独立或所有实现无缺陷，也能对官方主网有限条件作可撤销的工程风险接受；
- 边界：assurance 不进入个案权重，不适用于主网外，维护密钥和被审组件仍可能失陷；
- 状态：职责边界 `DECIDED`；具体对象和部署证据 `CANDIDATE/P0`。

### RB-14：一个权威值可以有多个诊断和检查点

- 前提：原因 reducer 与 Lease 派生 capability 均版本化、可复算；
- 机制：完整 `CauseSet` 派生一个 `EffectiveVerdict`；Dispatch/RPR 多次检查同一 active Lease capability；
- 结论：不会为了保存诊断信息制造多套终态，也不会为了增加检查制造第三份 scope 权威；
- 边界：日志旁路、实现绕过和 reducer 代码错误仍需 Type B 审计与差分测试；
- 状态：结构决定 `DECIDED`；Schema、接口与测试 `OPEN/P0`。

## 5. 主张与证据状态

下表列出各项主张及其对外成立所需的证据；所列证据尚未闭合。

| 主张 | 所需证据 |
|---|---|
| 整体系统鲁棒 | 完整模型、状态机、参数、证明、仿真和试点 |
| 验证错误率达到某个数值 | 统计目标、定理、相关性和实现验证 |
| Sybil 攻击成本高于回报 | 身份租赁、外部收益、集群和时间窗口模型 |
| 零抵押不会显著降低完成率 | 大规模行为仿真和外部试点 |
| 维护结构净价值为正 | 事件频率、风险降低、延迟和行政成本数据 |
| 区块链实现更安全 | Adapter、重组、最终性、费用和攻击面对比 |
| 中心化参考实现可安全迁移 | conformance、重放和迁移证明 |
| RIR 或 Rust Profile 已保证确定性/正确性 | RIR 形式语义、validator、lowering、runtime、effects/resource conformance 与差分测试 |
| Abstract Machine 或 Logical Object 已实现共享一致内存 | V1 明确不提供共享可变地址空间；仍需 Object Schema、可用性和恢复证据 |
| 通用 permissionless 重执行已提供安全停止保证 | 具体部署对支持能力集合上界 \(B\)、集合冻结/独立性、活性下界 \(Q\) 和验证器语义的证据 |
| 官方主网 assurance 等于普遍正确 | 主网外、替换组件、未知实现缺陷和外部业务语义不在其保证内 |

## 6. 核心证明义务

| ID | 义务 | 方法 | Gate |
|---|---|---|---|
| PO-01 | canonical Receipt 唯一性与跨实现等价 | 形式化编码 + golden vectors | G0/G2 |
| PO-02 | Lease/terminal/settlement 竞态保持唯一 | 状态机模型检查 | G0/G2 |
| PO-03 | 所有资源和资金边界在恢复后仍有界 | property tests + fault injection | G2/G4 |
| PO-04 | 序贯验证在声明模型下误差受控 | 数学证明 + 仿真 | G0/G1 |
| PO-05 | 相关性折减在错误聚类下的残余风险 | 敏感性和攻击仿真 | G1/G5 |
| PO-06 | CapabilityEstimate 校准且不扩大损失 | calibration + regret/loss analysis | G1 |
| PO-07 | 新 Provider 有证据路径且探索损失有界 | 仿真 + pilot | G1/G6 |
| PO-08 | Adapter 替换保持可观察语义 | conformance + differential testing | G4 |
| PO-09 | 发布/撤销/维护权限不能改个案 | 权限测试 + key compromise exercise | G2/G5 |
| PO-10 | 资金、退款和外部通道最多一次 | accounting model + failure injection | G2/G4 |
| PO-11 | frontend lowering 与 runtime 对同一 RIR/Profile 保持规范执行语义 | golden vectors + differential/conformance tests + fault injection | G0/G2 |
| PO-12 | Logical Object 在存储、复制、缓存和恢复后保持 canonical identity 与显式引用 | Schema + golden vectors + availability/fault tests | G0/G2/G4 |
| PO-13 | Lowering/Decomposition/Packing 与 Provider Dispatch 不改变 Receipt 义务或产生未接受权利 | 状态机 + semantic differential tests + race injection | G0/G2/G3 |
| PO-14 | 有限总体 e-process 在声明的能力集合模型下保持 Type-I 界，并与精确 DP/跨实现规则一致 | 条件证明 + 有理数全枚举 + 递推/闭式对拍 + 事后选择反例 | G0/G1 |
| PO-15 | 主网 assurance 只能限域、减权且不能进入个案权重 | Schema/权限测试 + key compromise + 发布/撤销演练 | G0/G2/G5 |
| PO-16 | 经批准日志后端没有已知旁路，恢复后仍能重放唯一状态 | integration audit + inclusion/consistency/finality + crash/reorg injection | G2/G4 |
| PO-17 | 多原因集合在所有实现中派生同一 verdict 且不丢失诊断事实 | golden vectors + reducer differential tests | G0/G2 |
| PO-18 | Dispatch/RPR 只消费 active Lease capability，执行元组变化不能静默绕过绑定 | data-flow audit + race/replay/environment-swap tests | G0/G2/G3 |

## 7. 仿真最小集合

### 正常场景

- 异构 Provider、任务族和网络延迟；
- 新 Provider 探索和能力收敛；
- Lease 到期、checkpoint 和恢复；
- 多种验证难度和资金政策。
- Rust Profile source→RIR、恶意/边界 RIR、不同 RPR/Host OS 与资源耗尽语义；
- Logical Object 缺失/别名/篡改、不同 Compile 策略和 Provider pull/push Dispatch。

### 对抗场景

- Sybil 批量进入、证据刷取和探索耗尽；
- 串谋结果与相关验证；
- 共享软件缺陷造成相关错误；
- 身份租赁、外部头寸和纯破坏动机；
- 随机性偏置、Snapshot 污染和可选停止攻击；
- Funding exhaustion、重复结算和退款竞态；
- Maintainer/发布密钥失陷和 Adapter 语义漂移。
- compiler 后门、lowering/decomposition/packing 分歧、隐藏宿主 effect、native fallback 与 RPR 计量分歧；
- 能力集合事后选择、\(B\) 误设、活性语料外推、Bayesian/FoundationReport 权重注入；
- assurance 跨网络复用、事后升权、日志旁路、未 finalized 事件、Lease capability 重放与换环境；
- 多个假设同时失效、原因顺序变化和 reducer 版本迁移；

### 输出指标

- false endorsement / false unresolved；
- completion、tail latency、retry 和 recovery；
- 每 Provider/集群/Receipt/窗口最大损失；
- 验证、存储、传输和行政成本；
- 暴露集中度和有效证据；
- 资金缺口和重复权利；
- 新 Provider 获取正常任务的时间；
- 隐私误关联和相关性漏检。

## 8. 反证规则

出现以下任一情况，相关结论必须降级：

- 找到违反 INV-01 至 INV-16 的可达历史；
- 统计方法在声明模型下无法保持误差目标；
- 某参数范围内最大损失无界或超过预声明上限；
- Sybil 通过重复身份线性放大有效证据或暴露；
- CapabilityEstimate 产生系统性错误迁移或真理权旁路；
- 恢复、Adapter 或维护权限能够产生双终态/双结算；
- 实验不能被独立复现；
- 外部试点的假设与原模型不一致。

失败结果必须保留，不得为了维持版本叙事删除。

## 9. 当前残余风险

- 任务验证器本身可能错误；
- 控制相关性可能不可观察或被伪装；
- 隐私限制会降低相关性检测能力；
- 同一集群识别失效会同时放宽支持能力上界 \(B\) 与 INV-10 的相关集群暴露限制；二者不是独立防线，最坏情况下只剩绝对资金和任务预算上限；
- 外部经济收益可能超过协议内上限；
- 中心化参考实现会保留运行和审查单点；
- 维护发布与依赖供应链可能失陷；
- 资金与结算通道可能有法律或最终性风险；
- 异构硬件和非确定性任务可能破坏结果等价。
- Rust frontend、RIR validator 或 RPR 的共因缺陷可能让多次执行产生相同错误；
- Logical Object 可用性、Compile 语义保持和 Dispatch 竞态仍无证明；有限总体数学内核虽已条件闭合，部署 \(B\)、\(Q\) 与能力集合独立性仍无通用证明。
- 主网 assurance、日志后端、ExecutionCapability 与 reducer 会引入新的实现和维护信任面；它们通过限域、测试、撤销和损失上限管理，不被描述为形式证明。

## 10. 当前严格结论

v0.5 已把主要风险转化为显式对象、不变量、上限和证明义务，并删除 Rank、51%、默认发行和固定角色等不受支持的安全捷径。官方主网可以在版本化 assurance 的有限工程条件内推进实现和试验；这是一项可撤销、损失有界的工程结论，不是开放世界的鲁棒性证明。

## 11. 更新记录要求

每次验证推进必须记录：日期、Claim/PO ID、模型与参数、方法、结果、反例、可复现位置、状态变化和受影响文档。`current-status.md` 保存当前快照，本文件保存论证与证据链。

## 2026-10-26 B/Q 边界反例（限域模型证据）

[研究第一片](../06-research/bq-boundaries-slice1.md)把 B 的能力集合误设、响应选择/排列偏置与 Q 的尾部/域漂移分开。现有条件定理保持不变，八个人工见证不提供部署概率或实际 B/Q。即便聚类全部相关单位，所得 G/B 也可能无可用间隔；即便 B 有效，响应过滤仍可能失去抽样条件。未知相关性不为零、任务级覆盖率不能用均值代替，损失预算不能当真理证据。后续校准与真实来源审计仍缺，不关闭整体鲁棒性、G1 或生产资格。

## 2026-10-26 校准置信与共同尾部敏感性

[第二片研究](../06-research/bq-calibration-slice2.md)把校准误颁证 α、任务支持尾部 δQ 和抽样活性 δL 分开；联合保守界不应被误读为“已通过后的后验概率”。已知依赖 block、scope 不匹配或多数自证输入被拒绝；未知依赖/真实同分布仍不能靠元数据证明。潜在能力增加和支持损失可能同时消耗 B<Q 间隔，正间隔也可能不符合原预算。示例全部合成，TV/故障质量是外部压力参数，不关闭现实相关性或 bounded 准入缺口。

## 2026-10-26 B/Q 失效与减权的研究闭合

[第三片](../06-research/bq-readiness-slice3.md)区分 bounded 统计前提不足、共同执行/日志合约不足、创建前显式选择和既有 Receipt 失效。不能把研究的 audit-only 建议当成运行中 Profile 切换，也不能将正间隔/DP 通过当作来源有效。当前材料只支持有限研究与旧实验；无正式 reexec 准入候选不等于停用已授权诊断实验。自然到期不自动追溯撤销有效时发出的 Decision，来源未知不猜 verdict，终态保留。18 项回归不替代来源忠实性或完整 P0-5/主网保证。
