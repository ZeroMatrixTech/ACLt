# ACLt Protocol 履约证据、能力估计与风险暴露

> 当前执行见[开发政策](../development-policy.md)（2026-11-19）；本页旧 SHA 校验与审批要求按该决定处理。


> 文件名兼容说明：`reputation.md` 为仓库规划中的历史文件名；本文使用 PerformanceEvidence、CapabilityEstimate 与 ExposureDecision 表示当前相关对象
> 文档状态：`DECIDED` semantic replacement；模型 `CANDIDATE/P1`  
> 语义基线：v0.5  
> 最后更新：2026-08-17

## 1. 核心决定

旧版“信誉分/Rank”把任务类型、环境、时间和不确定性压缩为一个可积累标量，并容易被误用为身份等级或验证权。v0.5 已将其替代为：

\[
PerformanceEvidence_{i,t}
\rightarrow CapabilityEstimate_{i,f,t}\pm Uncertainty_{i,f,t}
\rightarrow ExposureDecision_{i,j,t}
\]

其中：

- `i`：Principal/Provider；
- `f`：任务族与条件；
- `j`：具体任务；
- `t`：证据和决策时间。

该链描述任务条件、估计不确定度和实际风险额度；验证结果由相应方法与证据路径记录。

## 2. 当前表示与数据流

已有设计分别记录履约证据、任务族估计和单次风险额度。估计附输入、时间、模型与不确定度；暴露决策消费这些字段，验证路径消费自己的任务配置与证据。缓存用于读取已有估计，更新可追踪到原记录。

这是当前的对象和职责分配。引入新估计、迁移机制或证据使用方式时，说明具体接口、数据来源与适用模型，并按实际影响验证。不同任务族的迁移、故障归因和后验构造分别属于待研究问题，旧的一揽子禁止清单保留在 Git 历史。

## 3. PerformanceEvidence

证据至少应包含：

| 字段组 | 内容 |
|---|---|
| Identity | Provider/PrincipalID、签名、控制关联引用 |
| Task | ReceiptID、Assignment、任务族、难度和价值 |
| Environment | 硬件、软件、镜像、资源、区域和网络条件 |
| Commitment | Lease、epoch、接受时间、deadline、资源声明 |
| Outcome | 完成、失败、超时、取消、stale 或不可归责 |
| Quality | VerificationEvidence、结果簇、置信与方法版本 |
| Attribution | Provider、Requester、任务、验证器、平台或外部故障 |
| Cost/time | 执行时间、资源、传输、验证和恢复成本 |
| Provenance | EventRecord、因果父对象、修正链和证据版本 |

Evidence MUST append-only；更正必须追加并指向原记录。

## 4. 故障归因

候选归因类型：

- `PROVIDER_FAULT`；
- `REQUESTER_SPEC_FAULT`；
- `VERIFIER_FAULT`；
- `IMPLEMENTATION_FAULT`；
- `INFRASTRUCTURE_FAULT`；
- `EXTERNAL_FAULT`；
- `AMBIGUOUS`；
- `NOT_APPLICABLE`。

归因枚举和证据阈值仍为 `OPEN/P0`。不能充分归因时必须保留不确定，而不是选择最方便的责任主体。

## 5. CapabilityEstimate

CapabilityEstimate 是特定任务族和条件下的概率分布、区间或保守下界。它至少绑定：

- 使用的 Evidence digest 与时间窗口；
- task family、环境和难度范围；
- 模型与参数版本；
- 点估计/区间/后验或其他输出；
- 不确定度和样本有效性；
- 数据陈旧、概念漂移和硬件变化；
- 有效期和不可迁移边界。

现有估计按任务族和条件记录；跨任务族迁移需要明确模型与数据。休眠、硬件/软件变化和分布漂移作为估计输入与不确定度来源记录。

## 6. 候选估计方案

| 方案 | 优点 | 局限 | 当前用途 |
|---|---|---|---|
| Beta/Bayesian 成功率 | 可表达不确定度，更新直观 | 独立同分布假设可能不成立 | 基线候选 |
| 保守置信下界 | 风险决策清晰 | 可能过度保守 | 推荐比较 |
| Glicko-like 动态模型 | 能表达不确定度和时间变化 | 原设计面向对局，不可直接移植 | 仅作表示参考 |
| 校准分类/生存模型 | 可纳入任务和环境特征 | 数据污染、可解释和漂移风险 | 仿真候选 |
| 规则型能力边界 | 可审计、易测试 | 利用率可能较低 | G0/G1 基线 |

当前有多种候选模型；后续比较使用校准、损失和反例表现。

## 7. ExposureDecision

具体任务的准入至少考虑：

- 硬资源与环境兼容；
- 任务族 CapabilityEstimate 的保守量；
- 不确定度、有效期和数据陈旧；
- 当前并发、在途价值和已消耗尝试；
- Provider 与相关集群集中度；
- Receipt、资产和时间窗口最大损失；
- deadline、恢复成本和验证预算；
- 新 Provider 探索额度。

决策 MUST 原子预留额度并绑定证据版本。它是一次性、可过期的风险许可，不是持久身份等级。

## 8. 新 Provider 与探索

可选方案：

| 方案 | 优点 | 风险 |
|---|---|---|
| 固定低价值任务池 | 简单、有硬损失界 | 晋升慢、任务供给依赖 |
| 随机探索配额 | 减少冷启动歧视 | 可被 Sybil 消耗 |
| 上下文 bandit | 利用率较高 | 模型复杂且易受污染 |
| 请求方自选风险 | 灵活 | 可能外部化系统风险 |
| 混合硬上限方案 | 兼顾探索与安全 | 参数校准复杂 |

当前方向是混合方案：新 Provider 保留证据获取路径，但所有探索同时受 Provider、相关集群、Receipt 和窗口硬上限约束。

## 9. Sybil 与证据刷取

多个标识可能由同一控制者操作。协议必须：

- 保存控制相关性证据；
- 对相同或高度相关任务证据防重复计数；
- 限制单集群的探索与暴露；
- 对未知关联增加不确定度；
- 仿真反复创建—探索—退出攻击；
- 不把“通过身份验证”直接视为行为独立。

## 10. 估计与验证的接口

当前设计中 CapabilityEstimate 进入 Admit/ExposureDecision；验证实现消费本任务的 VerificationPolicy、Snapshot、显式混合权重和 VerificationEvidence。把这两条实际数据流分别写清，便于核对实现。

观察前固定、非负且归一化的混合权重是现有 e-process 模型的条件；输入来源与职责划分属于工程选择。未来若使用履约信息构造某个 prior 或采样策略，需说明它的可观察时间、构造方式和所依赖模型，不能把当前数据流选择写成对所有未来方法的数学排斥。

## 11. 可解释性与申诉

每个 ExposureDecision SHOULD 能说明：

- 使用了哪些证据和模型版本；
- 哪些硬约束通过或失败；
- 不确定度和相关性如何影响上限；
- 决策有效期与可重新评估条件；
- 证据错误如何追加更正。

申诉不能直接修改历史或人工提高权限；它只能提交新证据、更正来源或触发可复算的重新决策。

## 12. 验收指标

- calibration error / coverage；
- 新 Provider 获得首个正常暴露的时间；
- 完成率、弃单率和尾延迟；
- 每 Provider/集群/窗口最大损失；
- Sybil 探索消耗与证据刷取收益；
- 任务族误迁移率；
- 漂移后的恢复速度；
- 错误归因与错误关联率；
- 不同群体/硬件条件下的系统性偏差。

## 13. 当前未决问题

- PerformanceEvidence Schema 和故障归因；
- task family ontology；
- CapabilityEstimate 输出接口、模型、校准和衰减；
- cross-family transfer 和 concept drift；
- 新 Provider 探索政策；
- 相关集群、隐私和错误关联；
- ExposureDecision 原子额度和参数；
- 可解释性、更正和申诉流程。

## 14. 迁移说明

历史 Rank/Reputation 表述按具体含义映射：履约记录对应 PerformanceEvidence，对未来履约的估计对应 CapabilityEstimate，任务大小与并发额度对应 ExposureDecision。旧文本中验证影响力或治理权的设想作为历史设计，后续若采用具体机制，另行说明其对象、职责与验证依据。

文件名保留只为仓库导航稳定，不表示恢复旧语义。
