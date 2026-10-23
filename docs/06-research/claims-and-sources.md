# ACLt Protocol 论断与来源登记

> 文档状态：Living evidence registry  
> 语义基线：v0.5  
> 最后核查：2026-10-23
> 规则：文献支持理论边界、方法或先例，不替 ACLt Protocol 证明组合系统

## 1. 证据纪律

每个重要论断必须说明：

- Claim ID 和状态；
- 精确命题与适用范围；
- 内部前提、机制和反证条件；
- 外部来源支持什么；
- 外部来源不支持什么；
- 所需证明、测试、仿真或试点。

优先使用原始论文、官方规范和一手实现文档。博客、二手总结和市场材料不能单独支撑协议安全主张。

## 2. 当前论断登记

| Claim ID | 论断 | SemanticStatus | ClaimQualifier | 证据 | 严格边界 |
|---|---|---|---|---|---|
| CLM-001 | 公共/志愿计算可以工程化分发任务、重试并验证结果 | `DECIDED` | `DERIVED` | S01、S02 | 不证明 ACLt 的 Sybil、统计或资金安全 |
| CLM-002 | 低成本身份会削弱把冗余身份视为独立实体的推理 | `DECIDED` | `DERIVED` | S03 | 不直接给出 ACLt 的相关集群算法或损失界 |
| CLM-003 | 对有限总体不放回序贯抽样构造 time-uniform confidence sequences 在数学上可行 | `DECIDED` | `SOURCE_ESTABLISHED` | S04、S05 | 不自动覆盖恶意、相关、异质验证证据 |
| CLM-004 | 在错误支持能力集合于 draw 前固定、与随机排列独立且大小不超过 \(B\) 时，ACLt 的有限总体混合 e-process 保持 \(\varepsilon_F\) Type-I 界 | `DECIDED` | `DERIVED / CONDITIONAL` | S04、S05、ADR-0004、精确对拍资产 | 不证明任何 permissionless 部署能建立 \(B\)；不覆盖验证器或语义错误 |
| CLM-005 | 完全异步、允许故障的共识不能获得无条件终止保证 | `DECIDED` | `DERIVED_BOUNDARY` | S06 | 只在论文模型内成立；ACLt 必须声明自身活性模型 |
| CLM-006 | Byzantine 阈值依赖明确的消息、认证和故障模型 | `DECIDED` | `DERIVED_BOUNDARY` | S07 | 不支持把任何固定阈值直接移植为 ACLt 的 51% |
| CLM-007 | 任意程序的非平凡语义性质不存在通用可判定方法 | `DECIDED` | `DERIVED_BOUNDARY` | S08 | 不排除特定任务族的验证器或证明系统 |
| CLM-008 | 内容摘要和 descriptor 可作为可互操作内容引用先例 | `DECIDED` | `ENGINEERING_PRECEDENT` | S09 | OCI 不定义 ACLt Receipt、状态机或结算语义 |
| CLM-009 | 带不确定度的能力/表现估计有现有模型先例 | `CANDIDATE` | `SUPPORT` | S10、S11 | 不支持 Rank 真理权，也不能直接移植参数 |
| CLM-010 | 风险评估应记录威胁、影响、控制和剩余风险并持续更新 | `DECIDED` | `PROCESS_SUPPORT` | S12、S13 | NIST 不证明 ACLt 协议安全 |
| CLM-101 | 两 Principal + permissionless functions 可缩小固定特权面 | `DECIDED` | `DERIVED` | ADR-0001、Threat model | 属 ACLt 设计结论，非外部定理 |
| CLM-102 | 零抵押与硬暴露上限可以同时存在 | `DECIDED` | `DESIGN_VALID` | INV-09/10 | 是否达到目标完成率和损失界仍需仿真 |
| CLM-103 | PerformanceEvidence→CapabilityEstimate→ExposureDecision 优于单 Rank | `CANDIDATE` | `HYPOTHESIS` | S10、S11 + 架构分析 | 需要校准、公平、漂移和攻击实验 |
| CLM-104 | 显式 UNRESOLVED 可以避免无限验证和伪造确定性 | `DECIDED` | `DERIVED` | INV-04/09/12 | 用户效用、退款和成本仍需验证 |
| CLM-105 | v0.5 已证明 ACLt Protocol 整体鲁棒 | `REJECTED` | — | 无 | 当前证据不足 |
| CLM-106 | ACLt Protocol 的组合是公开系统中完全原创且无先例 | `OPEN` | `PROHIBITED_OVERCLAIM` | 组件均有先例 | 只能在系统化检索和权利清查后作有限原创性表述 |
| CLM-107 | 以 RIR 作为规范执行表示、Rust Profile 作为参考前端，可以在架构上隔离源语言与协议语义 | `DECIDED` | `DERIVED` | ADR-0002、INV-01/16 | 不证明 lowering、RPR、资源计量、确定性或结果正确；需要 ACLt 自身 conformance 证据 |
| CLM-108 | Abstract Machine、不可变 Logical Object、Compile 三阶段和 RPR 边界可以减少隐藏执行语义 | `DECIDED` | `DERIVED` | ADR-0001/0002/0003、INV-01/16 | 只闭合架构边界；不证明 Schema、compiler、RPR 或状态机正确 |
| CLM-109 | Bayesian policy 可以在不进入正确性权重的前提下提高 ACLt 验证采样或成本效率 | `CANDIDATE` | `HYPOTHESIS`，Priority `P1` | 尚无 ACLt 特定效率证据 | posterior 不再是正确性闸门；需要 prior sensitivity、成本和尾延迟实验 |
| CLM-110 | 只限制实际支持票数、却允许支持能力集合在看到 draw 后选择，不能保持有限总体 e-process 的 Type-I 保证 | `DECIDED` | `DERIVED / COUNTEREXAMPLE` | 有理数全枚举和最坏自适应 DP | 反例针对当前算法/参数；\(C=B+1\) 不一定立即超过给定 \(\varepsilon_F\) |
| CLM-111 | 给定正确候选支持下界 \(Q\)，精确有限总体 DP 可以计算最小活性预算并保留平台段 | `DECIDED` | `DERIVED / CONDITIONAL` | DP 与全排列 oracle 对拍 | 端到端活性还需 \(Q\) 的覆盖率 \(1-\delta_Q\)，合成失败界为 \(\delta_Q+\delta_L\) |
| CLM-112 | 保存完整规范化 `CauseSet`，再由版本化 reducer 派生单值 `EffectiveVerdict`，可以同时保留诊断信息与跨实现兼容终态 | `DECIDED` | `DESIGN_VALID` | ADR-0005、INV-13、反例树 | 不证明 reducer 的具体优先序最优；必须以向量验证交换律、幂等性和排序无关性 |
| CLM-113 | active Lease 作为唯一执行范围权威，并派生由 Dispatch 与 RPR 分别校验的 `ExecutionCapability`，比维护第三份可写 Scope 更容易保持一致 | `DECIDED` | `DESIGN_VALID` | ADR-0005、INV-16、任务生命周期 | 不证明 Lease 来源天然忠实；需要派生、拒绝、竞态和对拍测试 |
| CLM-114 | Schema 只能证明输入结构与确定算法，不能单独证明日志、时钟、Registry 或运维系统如实产生了输入 | `DECIDED` | `ENGINEERING_BOUNDARY` | ADR-0005、威胁模型 | 工程实现仍须提供追加性、终局性、访问审计、故障注入和恢复证据 |
| CLM-115 | 版本化且只能收紧能力的官方主网保障 Profile，可以在不授予基金会个案真理权的前提下承接有限部署风险 | `CANDIDATE` | `ENGINEERING_HYPOTHESIS` | ADR-0005、行政成本分析 | 只适用于明示网络和范围；净价值、误暂停率、发布密钥与组织捕获仍需试点数据 |
| CLM-116 | Wasm 官方规范（含其确定性 profile）仍允许非最短 LEB128、`memory.grow` 非确定失败、NaN payload 非确定和实现自定的栈限制，不能原样作为 RIR | `DECIDED` | `SOURCE_ESTABLISHED` | S14、S15 | 只陈述 Wasm 规范行为；不说明 ACLt 规则足以消除全部分歧 |
| CLM-117 | 以 `wasm32v1-none` 产出、再由 ACLt 子集规则、规范编码与计量收窄的 Wasm 1.0 整数子集，可以作为 RIR-0 主体并支撑 Rust Profile lowering | `CANDIDATE` | `ENGINEERING_HYPOTHESIS` | S16、ADR-0006 草案 | 不证明 rustc 产物稳定落在子集内、成本表合理或 RPR 正确；需要 ADR-0006 §13 的双实现对拍与向量 |

## 3. 来源登记与边界

### S01 — BOINC 系统架构

David P. Anderson, *BOINC: A System for Public-Resource Computing and Storage*.  
[原始论文](https://boinc.berkeley.edu/grid_paper_04.pdf)

- 支持：公共资源计算、任务分发和工程可行性先例；
- 不支持：ACLt 的两 Principal 本体、Sybil 边界、序贯验证或资金模型。

### S02 — BOINC 高性能任务分发

David P. Anderson et al., *High-Performance Task Distribution for Volunteer Computing*.  
[原始论文](https://boinc.berkeley.edu/boinc_papers/server_perf/server_perf.pdf)

- 支持：调度、验证、冗余和服务器工程经验；
- 不支持：无许可控制独立性或 ACLt 安全阈值。

### S03 — Sybil Attack

John R. Douceur, *The Sybil Attack*, IPTPS 2002.  
[Microsoft Research 原始出版页](https://www.microsoft.com/en-us/research/publication/the-sybil-attack/)

- 支持：低成本多身份会破坏基于身份冗余的独立性推理；
- 不支持：ACLt 相关性检测一定准确，或硬损失上限已经校准。

### S04 — 有限总体不放回 Confidence Sequences

Ian Waudby-Smith and Aaditya Ramdas, *Confidence Sequences for Sampling Without Replacement*, NeurIPS 2020.  
[NeurIPS 原始页面](https://proceedings.neurips.cc/paper/2020/hash/e96c7de8f6390b1e6c71556e4e0a4959-Abstract.html)

- 支持：有限总体、不放回、time-uniform confidence sequence 方法存在；
- 不支持：恶意串谋、未知相关性、分层自适应和任务验证器缺陷。

### S05 — Time-uniform Chernoff Bounds

Steven R. Howard et al., *Time-uniform Chernoff Bounds via Nonnegative Supermartingales*.  
[Probability Surveys 原始论文](https://projecteuclid.org/journals/probability-surveys/volume-17/issue-none/Time-uniform-Chernoff-bounds-via-nonnegative-supermartingales/10.1214/18-PS321.full)

- 支持：time-uniform 推断的通用数学工具；
- 不支持：完整 ACLt VerificationPolicy。

### S06 — FLP 不可能性边界

Michael J. Fischer, Nancy A. Lynch, Michael S. Paterson, *Impossibility of Distributed Consensus with One Faulty Process*.  
[ACM 原始出版页](https://dl.acm.org/doi/10.1145/3149.214121)

- 支持：完全异步模型下，无条件共识活性存在根本限制；
- 不支持：所有实际系统都无法取得条件性活性，也不直接定义 ACLt 状态机。

### S07 — Byzantine Generals

Leslie Lamport, Robert Shostak, Marshall Pease, *The Byzantine Generals Problem*.  
[作者出版页 PDF](https://lamport.azurewebsites.net/pubs/byz.pdf)

- 支持：阈值结论依赖故障、消息和认证模型；
- 不支持：ACLt 存在默认 51% 或其他通用阈值。

### S08 — Rice 定理边界

H. G. Rice, *Classes of Recursively Enumerable Sets and Their Decision Problems*, 1953.  
[原始论文记录](https://www.jstor.org/stable/1990888)

- 支持：通用程序语义判定存在理论边界；
- 不支持：特定任务不能验证，或所有验证都必须依赖重复计算。

### S09 — OCI 内容描述符

Open Container Initiative, *OCI Image Specification*.  
[官方规范](https://specs.opencontainers.org/image-spec/)

- 支持：digest、descriptor 和可互操作内容引用的工程先例；
- 不支持：ACLt Receipt canonical semantics 或状态安全。

### S10 — Glicko/Glicko-2

Mark E. Glickman, *Glicko and Glicko-2 Rating Systems*.  
[作者官方页面](https://www.glicko.net/glicko.html)

- 支持：随时间表达能力估计与不确定度的模型先例；
- 不支持：将 rating 用作 ACLt 身份等级、真理权或直接安全参数。

### S11 — Beta Reputation System

Roslan Ismail and Audun Jøsang, *The Beta Reputation System*.  
[AIS 论文记录](https://aisel.aisnet.org/bled2002/41/)

- 支持：使用 Beta 分布表达二元表现证据的候选方法；
- 不支持：忽略任务族、相关性、漂移或把历史表现当权威。

### S12 — NIST SP 800-30 Rev. 1

NIST, *Guide for Conducting Risk Assessments*.  
[官方出版页](https://csrc.nist.gov/pubs/sp/800/30/r1/final)

- 支持：威胁、影响、控制和风险响应的持续风险评估过程；
- 不支持：ACLt 的具体攻击概率或安全证明。

### S13 — NIST CSF 2.0

NIST, *The Cybersecurity Framework 2.0*.  
[官方出版页](https://www.nist.gov/publications/nist-cybersecurity-framework-csf-20)

- 支持：Govern、Identify、Protect、Detect、Respond、Recover 的持续治理视角；
- 不支持：新增 Foundation 或治理实体的必要性。

### S14 — WebAssembly Core Specification 1.0

W3C, *WebAssembly Core Specification*, W3C Recommendation, 2019-12-05.  
[官方规范](https://www.w3.org/TR/wasm-core-1/)

- 支持：RIR-0 子集的基线指令、类型、模块结构与执行语义；
- 不支持：ACLt 的规范编码、计量、宿主 ABI 或跨实现一致性。

### S15 — WebAssembly Core Specification 3.0（在线版）

WebAssembly Community Group, *WebAssembly Core Specification*, Release 3.0 online edition, 2026-10-23 核查。  
[二进制整数编码](https://webassembly.github.io/spec/core/binary/values.html)、[执行指令](https://webassembly.github.io/spec/core/exec/instructions.html)、[数值运算](https://webassembly.github.io/spec/core/exec/numerics.html)、[Profiles](https://webassembly.github.io/spec/core/appendix/profiles.html)、[实现限制](https://webassembly.github.io/spec/core/appendix/implementation.html)

- 支持：LEB128 允许补零、`memory.grow` 非确定、NaN payload 非确定、确定性 profile 的范围、实现可限制栈帧与值栈、`div_s`/`rem_s` 的边界语义；
- 不支持：任何 Wasm 引擎满足 ACLt 的确定性或资源语义。

### S16 — rustc `wasm32v1-none` 目标说明

The Rust Project, *The rustc book*, Platform Support: `wasm32v1-none`.  
[官方文档](https://doc.rust-lang.org/rustc/platform-support/wasm32v1-none.html)

- 支持：该目标为 Tier 2，只启用 Wasm Core 1.0 与 mutable-globals，`core`/`alloc` 按同一特性预编译，默认 `panic=abort`，无需 nightly；
- 不支持：rustc 产物稳定落在 RIR-0 子集内，或 lowering 正确、可复现。

## 4. 内部来源优先级

| 来源 | 用途 | 限制 |
|---|---|---|
| 当前 ProtocolVersion/spec | 规范性行为 | 未冻结段落不能当生产规范 |
| invariants.md | 必须保持的安全性质 | 规范意图不等于已证明 |
| accepted ADR | 已接受决定与理由 | 可被新 ADR supersede |
| threat-model.md | 攻击能力与残余风险 | 需随部署和攻击更新 |
| simulations/results | 参数证据 | 只适用于模型和参数范围 |
| 历史 RUDCP/DCP 文档 | 追踪语义演变 | 被 v0.5 冲突项不再有效 |

## 5. 引用新增模板

```text
Source ID:
Full citation:
Primary URL / DOI:
Claim supported:
Assumptions/model:
What it does not support:
ACLt location:
Verification date:
License/copyright constraints:
```

## 6. 论断更新规则

- 新来源不能自动提升 Claim 状态；
- 组合结论必须有 ACLt 自身证明或实验；
- 发现反例时先降级 Claim，再调查原因；
- 被替代论断保留 ID 和历史；
- 原创性、鲁棒性、攻击成本和法律权利属于高风险主张，必须单独核查；
- 每次 v0.5 验证推进都应更新 Claim、PO、OQ 和引用边界。
