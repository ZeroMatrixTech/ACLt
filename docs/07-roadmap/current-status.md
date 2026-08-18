# ACLt Protocol v0.5 当前状态

> 文档性质：持续更新的项目快照（living document）  
> 基线版本：v0.5  
> 快照日期：2026-08-18  
> 当前阶段：G0 — 语义与问题空间冻结  
> 权威范围：记录“现在已经知道什么、还没有证明什么、下一步需要什么证据”；不替代协议规范、ADR 或测试结果。

## 1. 状态标签

本文件沿用全项目统一标签：

- `DECIDED`：v0.5 已接受的设计决定；变更需要同步更新受影响文档，必要时新增 ADR。
- `DERIVED`：由已接受决定直接推导，但仍应通过评审或测试确认边界。
- `INVARIANT`：实现、部署和治理均不得破坏的约束。
- `CANDIDATE`：当前首选方向，尚未完成证明或验证。
- `ASSUMPTION`：分析暂时依赖的前提，必须显式记录适用范围。
- `HYPOTHESIS`：可通过实验、仿真或试点证伪的判断。
- `OPEN`：尚未决定或尚无足够证据。
- `SUPERSEDED`：已被新设计取代，仅保留历史追踪价值。
- `REJECTED`：已经评估且当前不采用；重新开启需要新证据。

## 2. 一句话状态

ACLt Protocol v0.5 已完成最小语义基线和文档骨架：两类不可约 Principal、无中心裁决者的函数化流程、证据到暴露的风险链条、有限总体不放回的序贯验证方向，以及 V1 的 RIR/Rust Profile 执行边界已经明确；但对象模式、RIR 形式语义与 runtime、状态机、验证定理、相关性控制、结算矩阵与参考实现都还没有达到可实现冻结状态。

因此，v0.5 当前是“可审查的研究与规范基线”，不是生产就绪协议，也不是已证明安全的系统。

版本连续性：**v0.5 是协议语义基线；V1 是建立在其上的首个执行与 conformance 目标。** 采用 V1 名称不会使 v0.5 自动升级为 v1.0，也不表示 G0 已通过。

## 3. 当前事实表

| 领域 | 当前状态 | 已确定内容 | 尚缺内容 |
|---|---|---|---|
| 名称与定位 | `DECIDED` / `OPEN` | 名称为 **ACLt Protocol**；名称源自 “accurate”；它是协议而非区块链 | 名称法律检索、域名、商标和兼容性标识政策 |
| 代码许可 | `DECIDED` / `IMPLEMENTED` | 代码与参考实现采用 Apache License 2.0（SPDX：`Apache-2.0`）；根目录 `LICENSE` 已存在 | 未来适用源码加入 SPDX 标识；按需建立 `NOTICE` 和第三方许可清单 |
| 其他工件许可 | `OPEN` | 规范、文档、论文、名称和商标不因代码许可而自动适用 Apache-2.0 | 分别选择许可证或使用政策并明确文件边界 |
| 最小本体 | `DECIDED` | 只有 Requester 与 Provider 是不可约 Principal | Principal 标识、密钥轮换与控制关系的规范模式 |
| 协议函数 | `DECIDED` | Plan、Admit、Schedule、Execute、Sample、Verify、Aggregate、Settle、UpdateEvidence 均是 permissionless functions | 每个函数的完整输入、输出、错误和确定性要求 |
| Task 与 Receipt | `INVARIANT` / `OPEN` | 任务语义与承诺必须在结果揭示前冻结；Receipt 是审计承诺 | 规范编码、哈希域、模式版本和兼容性规则 |
| 计划与准入 | `CANDIDATE` | WorkPlan 约束任务拆分、验证、资金和暴露 | 合法性判定算法、冲突处理和资源约束语言 |
| 调度与暴露 | `DECIDED` / `OPEN` | 调度是风险暴露决定，不由全局 Rank 决定 | CapabilityEstimate 模型、冷启动、探索预算和硬上限参数 |
| 执行 | `DERIVED` / `OPEN` | 使用 Assignment、Lease、epoch 与幂等提交处理并发和过期 | 完整状态机、沙箱要求、恢复语义和资源计量标准 |
| 执行表示与前端 | `DECIDED` / `OPEN` | V1 以 RIR 为规范执行表示；Rust Profile 是 reference frontend；未来 C++23 等前端须降级到同一 RIR | RIR schema/形式语义/canonical encoding、validator、Rust lowering、runtime/effects/resource conformance |
| 结果验证 | `CANDIDATE` | 首选有限总体、不放回、anytime-valid 的序贯验证方向 | 统计量、置信过程、停止规则、完整证明和参数化边界 |
| Sybil 与相关性 | `DECIDED` / `OPEN` | 不假设身份独立；采用相关性分组/证据折扣并叠加硬暴露上限 | 可观测信号、隐私边界、分组算法和最坏损失校准 |
| 聚合与终态 | `DECIDED` / `OPEN` | TRUSTED 仅表示在声明模型与阈值下满足接受条件；支持 UNRESOLVED 等显式终态 | 结果等价关系、冲突聚合规则和逐类任务验证器 |
| 资金 | `DECIDED` / `OPEN` | FundingPolicy 可为请求者付费、准备金、补贴、可选发行或混合；发行不是默认值 | 余额模型、资金锁定、耗尽、退款和破产处理 |
| 结算 | `INVARIANT` / `OPEN` | 每项权利只能至多一次生效；所有扣付必须可追溯 | 故障归因矩阵、争议边界、尾数与部分履约规则 |
| 能力证据 | `DECIDED` | 链条是 PerformanceEvidence → CapabilityEstimate ± Uncertainty → ExposureDecision | 更新方程、衰减、迁移、抗操纵与跨任务可比性 |
| 维护边界 | `DECIDED` / `OPEN` | Maintenance 是最小维护边界，不是运行时裁决者 | 发布、撤销、紧急响应、密钥托管和最小组织流程 |
| 实现与适配器 | `OPEN` | Control Plane 是实现；账本、对象存储、支付、身份系统均为可选适配器 | 参考实现、接口一致性、部署配置和互操作测试 |
| 运营成熟度 | `OPEN` | 威胁与不变量清单已经建立 | 可观测性、SLO、事件响应、灾难恢复和试点数据 |

## 4. 已完成的最小文档基线

截至本快照，最小仓库中的 Markdown 文档已经全部建立：

- `00-overview`：项目定义、设计原则、术语和系统上下文。
- `01-requirements`：威胁模型和系统不变量。
- `02-architecture`：分层架构、身份与角色、任务生命周期。
- `03-protocol`：协议规范骨架、结果验证、能力证据与暴露模型。
- `04-analysis`：稳健性论证和管理成本边界。
- `05-decisions`：最小实体原则与 RIR/Rust Profile 两项架构决策记录。
- `06-research`：主张与来源登记。
- `07-roadmap`：当前状态与待决问题。

“文档已建立”不等于相应设计已证明。文档中的状态标签和关闭证据决定其成熟度。

## 5. v0.5 不变量状态

`docs/01-requirements/invariants.md` 当前记录 16 条规范性不变量。它们是实现接受条件的来源，但尚未全部形式化或转化为可执行测试。

| 工作项 | 状态 | 下一证据 |
|---|---|---|
| 不变量编号与自然语言定义 | 已完成 | 跨文档一致性评审 |
| 不变量到威胁的映射 | 部分完成 | 完整双向追踪矩阵 |
| 不变量到协议函数的映射 | 部分完成 | 每个转移的前置/后置条件 |
| 不变量到测试的映射 | 未开始 | conformance test ID 与测试向量 |
| 不变量的形式化表达 | 未开始 | 状态机、时序性质或可检查断言 |

## 6. 验证门（Gates）

版本推进不按文档数量或主观完成百分比判断，而按可复核证据通过以下验证门：

| Gate | 目标 | 退出证据 | 当前状态 |
|---|---|---|---|
| G0 | 规格化：术语、本体、对象、RIR、状态机、不变量、威胁、统计与资金政策 | 每项 P0 决定可由机器/测试表达；连续性审计无未登记冲突 | 进行中 |
| G1 | 仿真与模型验证 | 能力、调度、验证、相关性、攻击、资金、行政成本和 RIR/runtime 模型的敏感性与反例 | 未开始 |
| G2 | 单机参考实现 | Registry、RIR toolchain/runtime、Plan、Lease、Result、Verify、Settle、Event 通过并发/重放/崩溃性质测试 | 未开始 |
| G3 | 局域网多 Provider MVP | 断连、退出、恢复、沙箱和初始 SLO 故障注入 | 未开始 |
| G4 | 持久化与灾难恢复 | 数据库/日志/对象存储适配器、备份恢复、RPO/RTO 与 conformance | 未开始 |
| G5 | 对抗验证 | Sybil、串谋、证据刷取、预算耗尽、compiler/runtime 与维护滥权的损失界或检测率 | 未开始 |
| G6 | 异构扩展与外部试点 | 新硬件、任务类型和可选账本保持不变量且证据不错误迁移 | 未开始 |

任何 Gate 都不得用“已有实现”替代“相应语义已经证明”。实现只能为假设提供证据，不能反向定义协议真相。

### 6.1 2026-08-18 G0 连续性审计

**结论：语义连续性通过，G0 退出未通过。** 本轮已消除 v0.5 与 V1、源语言与规范执行表示、项目 V1 与旧验证类型 `V1` 占位编号之间的冲突，并将 RIR/Rust Profile 决定映射到 ADR、威胁、不变量、协议、验证与路线图。

仍阻断 G0 退出的证据包括：RIR/对象 canonical schemas、完整状态机、RIR validator 与 runtime/effects/resource 语义、Rust Profile lowering、验证定理、相关性与最大损失模型、资金/退款/结算矩阵、控制面一致性/恢复和发布撤销流程。

当前允许开展的是 G0 内的工程化规格工作，例如 schema、validator、golden vectors、可执行模型、差分测试脚手架和仿真准备；这些产物不得被表述为 G1 已完成、G2 参考实现已合格或系统鲁棒性已证明。

## 7. 当前最高优先级

### P0 — 阻断 G1

1. 固定所有规范对象的最小字段、版本、规范编码与哈希域。
2. 固定 Task、Assignment、Lease、Receipt、VerificationSession、Settlement 的状态机。
3. 冻结 RIR grammar/schema、canonical encoding、validator、Rust Profile lowering、runtime effects/resource/error 语义。
4. 建立威胁—不变量—函数—测试四向追踪表。
5. 固定验证器注册、结果等价关系、样本帧快照与随机性承诺。
6. 写出资金锁定、终态、退款、处罚和 at-most-once 结算矩阵。

### P0 — 阻断公开发布

1. 完成 **ACLt Protocol** 名称冲突检索。
2. 保持根目录 Apache License 2.0 `LICENSE` 不被改写，并给未来适用源码加入 `SPDX-License-Identifier: Apache-2.0`。
3. 决定规范、文档、论文、名称、商标和兼容性声明的独立许可/使用政策。
4. 决定贡献者许可机制（仅项目许可证、DCO 或 CLA）及第三方代码接受规则。

### P1 — 阻断 G1/G2 的可信推进

1. 为不放回序贯验证建立可审阅的定理、适用条件与反例。
2. 校准相关性分组、证据折扣和硬暴露上限。
3. 固定 CapabilityEstimate 的不确定性表达、冷启动和衰减模型。
4. 建立最小可执行模型、仿真场景和失败注入基线。
5. 建立 frontend lowering、RIR validator、runtime 与资源计量的差分 conformance 基线。

### P2 — 可在核心稳定后并行

1. 扩展非确定性任务、隐私任务、数据本地性与硬件证明支持。
2. 评估 unsafe/full-std、原生执行、GPU/专用加速器和 C++23 conforming frontend 的独立 Profile；不得绕过 RIR。
3. 评估账本、支付、身份、对象存储等可选适配器。
4. 评估 TEE、零知识证明或其他密码学增强，但不得预设其必要性。

## 8. 进度更新规则

每次会改变 v0.5 认知状态的提交，都应更新本文件：

- `CANDIDATE` 被证明、证伪或替换；
- 新增、删除或重写不变量；
- 某个 Gate 的退出证据发生变化；
- 协议对象、状态机、验证假设、资金或结算规则发生变化；
- 试验、仿真、审计或试点产生了影响结论的新证据；
- 风险由“已知但未量化”变为“已量化”，或反向退化；
- 版本、许可证、维护边界或发布策略发生变化。

更新时必须同时：

1. 修改“当前事实表”中相应行；
2. 更新 `open-questions.md` 的问题状态和证据链接；
3. 更新受影响的规范、分析或 ADR；
4. 在下方日志增加一条记录。

## 9. 状态变更日志

| 日期 | 基线 | 变化 | 证据/文档 | 影响的 Gate |
|---|---|---|---|---|
| 2026-08-17 | v0.5 | 建立最小 Markdown 文档基线；明确当前处于 G0 | `docs/` 全集 | G0 |
| 2026-08-17 | v0.5 | 决定代码与参考实现采用 Apache License 2.0；其他工件维持独立许可边界 | `README.md`、`CONTRIBUTING.md`、OQ-01 | 公开发布/G6 |
| 2026-08-17 20:51:52 CEST | v0.5 | 根目录 `LICENSE` 已切换并落地为 Apache License 2.0 英文全文 | `LICENSE`；提交 `e5d5bc149c2773332c944b000fa23f5f3a5bc97a` | 公开发布 |
| 2026-08-18 | v0.5 / V1 target | 接受 RIR 作为规范执行表示、Rust Profile 作为 V1 参考前端；未来 frontend 必须降级到同一 RIR | ADR-0002 及同步文档 | G0/G1/G2 |

日志只记录影响项目认知或成熟度的变化；排版、错字和无语义重构不必记录。

## 10. v0.6 就绪条件

只有在以下条件同时满足时，才应讨论将 v0.5 基线提升为 v0.6：

- G0 完成，核心术语、问题登记和文档之间不存在已知语义冲突；
- G0 的对象、编码、状态机与错误语义达到可实现冻结状态；
- RIR、Rust Profile、runtime/effects/resource model 与 conformance 规则达到可实现冻结状态；
- 验证核心至少有一套明确、可复核且标注适用边界的证明或反例结论；
- 资金、暴露、终态和结算可以对所有已声明失败路径给出确定结果；
- 不变量至少映射到可执行模型或测试计划；
- 所有仍未解决的高风险问题都具有明确风险接受者、上限和下一关闭证据；
- 名称政策、代码许可证落地、其他公开工件的许可边界与贡献规则不再阻断公开发布。

v0.6 不代表生产就绪；它代表 v0.5 的核心开放问题已经被收敛为一套可实现、可验证的新基线。
