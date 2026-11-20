# ACLt 项目总览

> 当前执行见[开发政策](../development-policy.md)（2026-11-19）；本页旧 SHA 校验与审批要求按该决定处理。


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

ACLt 以协议对象和任务状态组织多台计算机。中心化服务、日志或账本可以承载相关实现；各实现说明它实际支持的对象、状态和可观察行为。

## 2. 项目要解决的问题

开放分布式计算不能把“存在多个节点”直接解释为“存在多个独立、诚实的控制实体”。节点可能退出、重复提交、串谋或由同一控制者批量创建；任务可能无法廉价验证；计算资源高度异构；验证与恢复会产生真实成本；实现维护者也可能成为额外的信任根。

当前设计把这些问题组织为：

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

## 5. 当前能力与后续方向

当前已实现的问答复核、分片、预算和恢复行为见[项目入口](../../README.md#已实现的行为)。报告分别记录固定任务族、可信参与者、同宿主多来宾或物理双机的实际条件。

后续任务族、执行后端、隐私和证明方法按具体需求比较。已有数学模型按其前提使用，工程支持范围由实际实现与运行说明。版本标签、历史排除列表及实现便利作为设计背景，维护者可根据当前目标调整。

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

## 9. 维护工作

维护者负责当前方向、数学研究、审计、签署和合并；协作者实现授权工作并提供实际检查结果。运行任务的状态与资金处置按相应实现记录。发布、运行协调与开发审查各自说明责任。当前工作方式见[开发政策](../development-policy.md)。

## 10. 当前工程进展

仓库保存了本地执行、多来宾与可信物理双机实验、候选对象状态机、有限总体模型与测试。它们各自链接源码、实际输入和运行记录。当前工作是接通已有实现、修复复现差异并扩展所选场景。工程状态见[当前状态](../07-roadmap/current-status.md)，本轮协作与 SHA 处置见[当前政策](../development-policy.md)。

## 11. 当前结果入口

已实现行为与证据见[项目首页](../../README.md#已实现的行为)，待研究事项见[开放问题](../07-roadmap/open-questions.md)。本轮修改按当前输入输出、实际运行和维护者审查记录结果。
