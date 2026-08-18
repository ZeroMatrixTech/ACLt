# ADR-0001：如无必要勿增实体

> 状态：`ACCEPTED`  
> 决定日期：2026-08-15  
> 语义基线：v0.5  
> 最后复审：2026-08-18  
> 复审触发：提议新增 Principal、固定角色、组织、中介或特殊权限

## Context

早期设计曾把 Requester、Broker、Provider、Verifier、Scheduler、Foundation、Protocol 和 Control Plane 混合描述为“参与者”。这种建模会把职能名称误写为独立身份，并为本可由公开规则完成的工作增加权限、信任根和行政成本。

ACLt Protocol 需要区分：

- 谁能签署承诺并承担权利义务；
- 哪些工作只是可验证函数；
- 哪些名词只是协议对象；
- 哪些组件属于实现；
- 哪些责任属于维护生命周期。

## Decision

ACLt Protocol 采用以下原则：

> 若一项职能能够由公开、确定、版本化且可验证输入输出的协议算法完成，则不为该职能新增特权身份、组织或中介实体。

当前只保留两类不可再约减 Principal：

- `Requester`：对任务、输入、政策和预算承诺负责；
- `Provider`：对资源、Lease 接受、执行和证据承诺负责。

Plan、Admit、Schedule、Execute、Sample、Verify、Aggregate、Settle 和 UpdateEvidence 被定义为 permissionless functions。Protocol 是规则；Control Plane 是实现；Maintenance 是最小责任边界。

## Rationale

该决定：

- 减少固定特权身份和授权接口；
- 降低角色捕获、串谋和密钥失陷影响面；
- 允许同一 Principal 执行多个函数而不获得附加权威；
- 让输出合法性依赖协议规则而不是执行者头衔；
- 减少基金会、委员会和人工裁决的默认行政成本；
- 使中心化参考实现与未来分布式实现共享同一协议本体。

## Consequences

### Positive

- 参与者模型更小且可机器表达；
- Broker/Verifier 等服务可以竞争、替换或本地执行；
- 权限审计和威胁模型更清晰；
- 不需要证明某个固定中介永远诚实；
- 协议可在不同存储、日志和账本上实现。

### Negative

- 每个函数输出都需要明确的合法性检查；
- 责任归属不能依赖角色名称，必须绑定签名和因果证据；
- 无许可函数可能被垃圾输出或串谋攻击，需要资源和暴露限制；
- 部分实现为了性能仍会集中组件，必须防止实现权力泄漏到协议；
- 维护、发布和漏洞响应仍不能完全自动化。

## Alternatives Considered

### A. 固定 Requester/Broker/Provider 三角色

拒绝。Broker 的规划职能可以公开验证，不足以证明独立 Principal 必要性。

### B. 固定 Verifier/Scheduler/Sampler/Aggregator

拒绝。职能可以由任意 Principal 执行，固定身份会增加验证垄断和真理权风险。

### C. Foundation 作为最终裁判

拒绝。它会引入个案追溯、治理捕获、行政成本和单点权威。只保留最小 Maintenance Boundary。

### D. Protocol/Control Plane 作为参与者

拒绝。Protocol 不持有密钥或承担责任；Control Plane 是实现，不应获得协议身份。

### E. 完全无维护

拒绝绝对化。规范、发布、兼容和漏洞响应仍需要责任边界，但不能拥有运行时个案权。

## New Entity Admission Test

任何新增实体必须证明：

1. 职能不可缺少；
2. 现有 Principal 或公开函数无法合理承担；
3. 特殊权限不可由输出验证替代；
4. 权限、责任、退出和失陷影响明确；
5. 净风险降低与净行政价值为正；
6. 具有撤销、迁移、recusal 和安全终止；
7. Threat model、Invariant、测试和 ADR 已更新。

## Invariant and Threat Impact

- 主要支持：INV-14、INV-15、INV-16；
- 相关威胁：TH-07、TH-09、TH-17、TH-30、TH-31；
- 相关原则：DP-01、DP-02、DP-03、DP-12。

## Validation

必须通过：

- Schema/API 中不存在隐藏角色权威；
- 函数执行者改变身份不会改变输出合法性；
- 能力估计不能进入验证/治理权限；
- Maintainer 和实现管理员不能覆盖个案；
- 组件拆分/合并不改变 Principal 集合；
- 新实体提议完成准入测试。

## Supersedes

- Broker、Verifier、Scheduler 作为固定身份；
- Foundation 作为协议必需参与者；
- Protocol 与 Control Plane 作为参与者；
- Rank/Reputation 作为可积累权威。

## Review Conditions

若未来发现某项关键职能无法公开验证、无法归责或必须由法律主体承担，允许重新评估。但在新 ADR 被接受前，本决定保持有效；工程便利本身不足以推翻该原则。
