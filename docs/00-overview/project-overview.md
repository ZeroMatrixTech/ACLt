# ACLt 项目总览

> 文档状态：当前项目基线  
> 更新日期：2026-08-21
> 项目类型：开放、实现中立的去中心化计算协议  
> 当前阶段：G0——协议规格化  
> 历史名称：DistributedCompute、RUDCP、Decentralized Compute Protocol（DCP）  
> 已放弃的短暂候选名：BigMind

## 1. 项目定义

**ACLt** 是一套面向异构、无许可分布式计算的开放、实现中立的去中心化计算协议，致力于综合分布式算力，使多个主体按共同规则分工并交付可验证的计算结果。项目名是受 *accurate* 启发形成的臆造名称，而不是对某个固定短语的缩写。

ACLt 规定不同主体如何在缺乏预先信任的情况下：

1. 对任务语义、预算、期限和政策作出不可静默修改的承诺；
2. 通过 `Lowering + Decomposition + Packing` 将受支持源程序和显式 Logical Object 输入转换为规范 RIR 与合法工作单元；
3. 通过 Provider 显式接受的有限 Lease、单调 epoch、RPR、检查点和有界尝试执行及恢复工作；
4. 按任务类型形成、采样和聚合验证证据；
5. 在证据不足时以明确的 `UNRESOLVED` 状态安全终止；
6. 在预声明资金与结算政策内完成最多一次的结算；
7. 将历史履约证据转化为未来的能力估计和有界风险暴露决策。

ACLt 是协议，不是区块链、平台、市场、基金会或单一软件产品。它可以被理解为一台由多台物理计算机承载的 Abstract Machine 或 “computer-of-computers”，但该抽象不创造共享地址空间，也不假定节点独立。中心化服务、签名日志、Merkle 日志、联盟账本或公共区块链均可作为实现方式，但实现必须保持同一组对象语义、状态转换和不变量。

## 2. 项目要解决的问题

开放分布式计算不能把“存在多个节点”直接解释为“存在多个独立、诚实的控制实体”。节点可能退出、重复提交、串谋或由同一控制者批量创建；任务可能无法廉价验证；计算资源高度异构；验证与恢复会产生真实成本；实现维护者也可能成为额外的信任根。

ACLt 的目标不是消灭这些不确定性，而是将它们转化为显式且可审计的：

- 协议对象与冻结点；
- 状态机和终态；
- 风险、预算与尝试上限；
- 相关性信息与证据折减；
- 统计假设和证明义务；
- 故障归因与结算规则；
- 维护权限边界。

## 3. 核心目标

| 目标 | 协议要求 |
|---|---|
| 共同任务语义 | 用版本化、内容寻址的 `ComputeReceipt` 固定程序、输入、环境、验证、期限、预算和政策 |
| 逻辑对象内存 | V1 使用不可变、内容寻址、显式引用的 Logical Object；Provider 之间没有共享机器地址空间 |
| 统一执行语义 | V1 以 RIR 为机器/网络层规范表示；Rust Profile 只是参考前端，未来前端必须降级到同一 RIR |
| 运行时隔离 | RPR 实现冻结的 runtime/effects/resource 语义；Host OS 隐藏状态不得成为任务输入 |
| 可审计编译 | Compile 分为 Lowering、Decomposition、Packing；任何阶段不得扩大 Receipt 义务或权限 |
| 无许可参与 | 任何 Principal 均可尝试执行公开函数，但输出只有通过协议检查后才生效 |
| 零前置抵押参与 | 普通 Provider 无需先缴抵押；风险通过低初始暴露、并发限制、Lease 和硬损失上限控制 |
| 有界执行与恢复 | Lease、epoch、deadline、attempt limit 和 checkpoint 防止无限占用与迟到覆盖 |
| 单一执行授权 | active Lease 是范围权威；由其派生的 ExecutionCapability 在 Dispatch 与 RPR 两处独立校验，不复制第三份可写 Scope |
| 任务特定验证 | 验证语义随任务族定义，不声称存在适用于任意计算的廉价通用验证器 |
| 显式不确定性 | 无法在上限内形成足够证据时返回 `UNRESOLVED`，不得人工包装为可信结果 |
| 抗 Sybil 风险控制 | 不把身份数量当作独立样本数量；优先限制相关集群和系统最坏损失 |
| 证据驱动准入 | 使用“证据 → 能力估计 → 暴露决策”，不建立 Rank 或信誉权威 |
| 资金可解释 | 执行、验证、储备、补贴、费用和可选增发分别声明并受硬上限约束 |
| 实现中立 | 存储、通信、随机性和结算基础设施可替换，但可观察协议语义必须一致 |
| 分层工程闭合 | Schema/算法义务必须可判定；来源忠实性与部署风险由日志、审计、测试和版本化保障管理，不要求把所有工程事实形式化成定理 |
| 最小治理 | 维护者负责规范、发布和官方主网有限保障，不得裁决运行中的单个任务、追溯修改结果或把报告写入验证权重 |

## 4. 当前协议范围

当前范围包括：

- `Requester` 与 `Provider` 两类不可再约减的 Principal；
- `ProtocolVersion`、`ComputeReceipt`、`WorkPlan`、`Assignment`、`Lease`、`Attempt`、`Checkpoint`、`ResultSubmission` 等核心对象；
- ACLt Abstract Machine 及不可变 Logical Object Memory；
- RIR 版本、规范工件摘要和执行 Profile 的 Receipt 绑定，以及 V1 Rust Profile 参考 lowering；
- RPR 与 Host OS 的 fail-closed 边界；
- `Compile = Lowering + Decomposition + Packing` 及 Provider Dispatch 的 offer/accept/Lease 边界；
- active Lease → ExecutionCapability 的单一权威、多点校验边界；
- `Plan`、`Admit`、`Schedule`、`Execute`、`Sample`、`Verify`、`Aggregate`、`Settle` 和 `UpdateEvidence` 等无许可函数；
- 证据、能力估计、不确定度和风险暴露限制；
- 有限总体、不放回、可审计的序贯验证方向；
- `TRUSTED`、`UNRESOLVED`、`FAILED`、`EXPIRED`、`FUNDING_EXHAUSTED` 等终态；
- 预声明的 `FundingPolicy` 与 `SettlementPolicy`；
- 追加式事件、状态重放、协议版本和最小维护边界；
- 假设失效的完整 `CauseSet` 与由版本化 reducer 派生的兼容 verdict；
- 绑定官方主网、只能收紧能力的 `MainnetAssuranceProfile`；
- 数据库、签名日志或未来区块链实现之间的适配器一致性。

## 5. 非目标

当前范围以外的能力包括：

- 任意程序的廉价或绝对正确验证；
- Provider 标识之间相互独立的证明；
- 依赖固定多数、51% 或简单投票的普遍安全；
- 用 Rank、信誉分或历史履约表现授予“真理权”的做法；
- 对攻击永远无利可图或不可能发生的保证；
- 所有提交任务都能完成、被验证或获得唯一可信答案的保证；
- 通过临时增发掩盖验证、恢复或结算资金耗尽的机制；
- 因使用区块链而自动获得的安全性、去中心化或容错性；
- G0 阶段的系统鲁棒性证明；
- 首版中的跨境支付、公共链治理、通用零知识证明、TEE 或任意非确定性计算；
- V1 对 unsafe Rust、完整 `std`/宿主 OS effects、原生执行、GPU/专用加速器或非确定性任务的支持；
- V1 对跨 Provider 共享可变地址空间、分布式原子操作或隐藏 Host OS 状态的支持；
- 以 Rust 源码、某个编译器输出或本机二进制本身作为协议规范语义。

其中仍处于 `OPEN`、`CANDIDATE` 或 `DEFERRED` 的内容可以作为未来研究或适配方向；已被否决或取代的做法保持其否决或取代记录（见[术语表](terminology.md#10-废弃或禁止的旧术语语义)与相关 ADR）。上述内容均不得写入当前安全主张。

## 6. 最小系统本体

ACLt 只承认两类不可再约减的 Principal：

| Principal | 不可约减原因 | 主要承诺与责任 |
|---|---|---|
| `Requester` | 没有请求方就不存在任务语义、验收要求或预算来源 | 提交任务、声明输入权利、选择政策并提供真实预算承诺 |
| `Provider` | 没有提供方就不存在计算、验证或其他协议函数的实际执行者 | 声明资源、接受 Lease、执行函数并提交可归责证据 |

Planner、Broker、Scheduler、Verifier、Sampler 和 Aggregator 均不是固定身份，而是任何合规 Principal 均可执行的无许可函数。Protocol 是规则而非行为者；Control Plane 是实现而非协议主体；维护组织是可选工程安排而非运行时裁判。

ACLt Abstract Machine、Logical Object Memory、RIR、RPR 和 Compile pipeline 同样是规范或实现边界，不是新的 Principal、组织或真理权威。

## 7. 核心安全方向

ACLt 当前采用以下安全顺序：

1. 先用状态机、不变量、预算、次数、并发和暴露上限限制最坏损失；
2. 再按任务语义形成可审计的验证证据；
3. 显式处理共同控制、软硬件同源和协调行为等相关性；
4. 仅在预声明模型和停止条件成立时输出 `TRUSTED`；
5. 无法满足条件时输出 `UNRESOLVED` 或其他安全终态；
6. 最后才把攻击成本与收益分析作为补充防线。

当前选定但尚未完成证明的验证研究方向，是对冻结有限总体进行不放回抽样，并采用 anytime-valid 序贯推断。验证上限暂由以下边界表达：

$$
N_{\max}=\min(N_{\text{population}},N_{\text{budget}},N_{\text{policy}})
$$

该式只定义上限来源，不构成安全定理；具体总体、分层、相关性折减、误差目标和停止规则仍须规格化、证明和仿真。

## 8. 资金与结算边界

每个任务必须在执行前声明 `FundingPolicy`。允许的资金来源包括：

- Requester 费用；
- 预先建立的储备；
- 外部补贴；
- 可选且有上限的发行机制；
- 上述来源的显式组合。

协议不指定唯一资金来源，但要求任务级、时间窗口级和全局级上限，以及以下守恒边界：

$$
Committed + Settled + RefundReserved \le AuthorizedFundingCap
$$

资金耗尽是合法的安全状态，不得通过未声明的临时资金或增发绕过。结算必须绑定唯一权利键，并在重试、超时、并发或实现迁移后仍保持最多一次提交。

## 9. 维护边界

维护工作可以包括：

- 规范、Schema、状态机和参考实现维护；
- 测试向量、兼容性套件和发布签名；
- 漏洞接收、披露、修复和版本撤销；
- 架构决策记录和升级说明。
- ACLt 官方主网的部署审计、追加式日志运营、版本化保障 Profile 和应急暂停。

维护者不得：

- 修改已经冻结的 `ComputeReceipt`；
- 针对个案改变抽样总体、权重、停止规则或资金政策；
- 覆盖 `VerificationDecision`；
- 制造未授权结算；
- 把维护者意见当作更高权验证证据。
- 把官方主网保障自动外推到分叉、私网或修改版部署；
- 用保障 Profile 放宽已经冻结的验证、资金或终态规则。

是否设立基金会、委员会或链上治理结构仍是可选组织政策，不是协议必要条件。若基金会运营 ACLt 官方主网，它可以承担有限保障、日志与安全响应，但不因此成为运行时 Principal 或个案真理权威。

## 10. 当前成熟度

ACLt 仍处于 **G0：协议规格化阶段**。目前已经形成完整候选架构与关键边界。项目不再要求每个来源事实和部署事实都先被形式化证明：结构与算法必须闭合，来源与部署则以可执行工程假设、追加式日志、访问审计、故障注入和版本化保障形成证据；证据不足时相应能力 fail closed 或保持 audit-only。

进入核心原型之前至少需要完成：

- 规范化 Schema 与 canonical encoding；
- Abstract Machine 和 Logical Object 的 machine-readable Schema、生命周期与可用性规则；
- RIR canonical encoding、validator、runtime/effects/resource model、Rust Profile lowering 与 golden vectors；
- RPR capability contract、Host OS 隔离、资源计量、错误与 checkpoint portability；
- Lowering、Decomposition、Packing 的合法性谓词、TaskGraph 等价和 Provider Dispatch 状态机；
- ExecutionCapability 派生与 Dispatch/RPR 对拍向量；
- Principal、函数、签名责任与权限矩阵；
- WorkPlan、Lease、Result、VerificationDecision 和 Settlement 状态机；
- 任务验证类型注册表；
- 序贯验证统计规范与相关性处理；
- 暴露、尝试、资金和最坏损失上限；
- 结算、退款、故障归因和资金耗尽语义；
- 发布、密钥、撤销、升级和漏洞响应流程；
- CauseSet/reducer conformance 与 MainnetAssuranceProfile 发布、撤销和网络隔离流程；
- 当前项目名称的域名和包名清查；商标部分已按 2026-11-16 决定关闭（见术语表 §11）。

## 11. 可支持的当前结论

ACLt 已形成一套实现中立、证据驱动、显式处理相关性并优先限制最坏损失的完整候选协议架构。它已经将节点退出、任务语义变化、验证不确定性、Sybil 相关性、资金耗尽和维护权限等问题转化为协议对象、不变量、证明义务和可审计工程假设。

系统鲁棒性尚未得到证明；官方主网之外的部署不在上述安全结论的背书范围内。有限总体序贯验证的条件安全、相关性与 B/Q 校准、资金及退款语义、实现一致性和参数化损失界仍是核心工作；但自然人唯一性、日志来源和部署诚实性不再作为阻塞所有接口实现的“必须先证明之定理”。
