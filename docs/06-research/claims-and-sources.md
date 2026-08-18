# ACLt Protocol 论断与来源登记

> 文档状态：Living evidence registry  
> 语义基线：v0.5  
> 最后核查：2026-08-18  
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
| CLM-004 | ACLt 可直接采用某一 confidence sequence 并保持目标误差 | `OPEN` | Priority `P0` | S04、S05 是候选基础 | 必须定义目标、总体、依赖、分层和攻击模型并证明 |
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
| CLM-109 | Bayesian stop proposal 与 anytime-valid safety envelope 的组合可以在 ACLt 攻击模型下同时提高效率并保持目标风险 | `CANDIDATE` | `HYPOTHESIS`，Priority `P0` | 尚无 ACLt 特定证明 | 必须冻结 prior、目标、有限总体、相关性并给出组合定理或反例 |

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
