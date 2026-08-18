# 为 ACLt Protocol 作出贡献

> 文档状态：Living contribution policy  
> 语义基线：v0.5  
> 最后更新：2026-08-18

ACLt Protocol 当前处于 G0 规格化阶段。贡献的首要目标不是快速增加功能，而是让协议的前提、对象、状态转换、不变量、证明义务和失败边界更清晰、更可测试。

## 1. 可以贡献什么

- 协议对象、Schema、canonical encoding 和测试向量；
- 状态机、并发模型、性质测试和形式化验证；
- RIR parser/validator、canonical encoding、Rust Profile lowering 和差分 conformance 测试；
- 验证统计、相关性模型和攻击仿真；
- FundingPolicy、SettlementPolicy 和账务状态机；
- 威胁建模、故障注入、适配器一致性和供应链安全；
- 文献核查、论断—来源映射和相关系统比较；
- 术语、文档结构、图表和可复现实验；
- 对既有假设、候选算法或安全主张的反例。

反例、失败结果和“不足以支持结论”的实验与正结果同等重要。

## 2. 贡献前必须理解的边界

贡献不得重新引入以下旧语义：

- Rank/Reputation 作为实体、等级或权威；
- 固定 Broker、Planner、Verifier 或 Scheduler 身份；
- Foundation 作为协议必需参与者；
- Provider 数量代表独立控制实体；
- `Nmax = 51% × Provider 数量`；
- 履约能力自动提高验证权；
- 验证资金默认来自发行；
- 区块链自动提供 ACLt Protocol 安全性；
- `TRUSTED` 表示绝对正确。
- 让某个源语言、编译器或原生二进制定义协议执行语义；
- 未经新 Profile/ADR 就把 unsafe Rust、完整宿主 effects、原生执行、GPU 或非确定性任务纳入 V1。

若要重新讨论已拒绝语义，必须提供新的威胁模型、反例、净风险分析和 ADR，不得仅替换名称。

## 3. 状态标签

所有实质性文档变更必须使用以下标签之一：

| 标签 | 使用条件 |
|---|---|
| `DECIDED` | 已经接受的项目决定 |
| `DERIVED` | 可由明确前提推出的结论 |
| `INVARIANT` | 所有正确实现都不得违反的性质 |
| `CANDIDATE` | 已选方向，但算法、参数或证明尚未冻结 |
| `ASSUMPTION` | 结论依赖但尚未证明的条件 |
| `HYPOTHESIS` | 需要实验或仿真检验的经验主张 |
| `OPEN` | 尚未决定或规格化 |
| `SUPERSEDED` | 被更新语义替代，但保留历史价值 |
| `REJECTED` | 明确排除的设计或主张 |

不得把 `CANDIDATE`、`ASSUMPTION` 或 `HYPOTHESIS` 写成已经成立的系统事实。

## 4. 变更类型

### 4.1 文档澄清

不改变协议语义的拼写、链接、排版和解释改进，可以直接提交，但仍应确认没有改变 MUST/MUST NOT 的含义。

### 4.2 规范变更

改变对象字段、函数、状态机、终态、资金、验证、暴露或权限的变更必须包含：

1. 问题陈述和可复现反例；
2. 当前行为与拟议行为；
3. 受影响的不变量和 Threat ID；
4. 新增假设、信任根和行政成本；
5. 兼容性、迁移、撤销和安全退出；
6. 正例、负例、边界和并发测试；
7. ADR 或对现有 ADR 的更新；
8. `current-status.md` 与 `open-questions.md` 的同步修改。

### 4.3 新实体或特权组件

新增 Principal、组织、中介或特殊权限前，必须证明：

- 该职能不可缺少；
- 现有 Principal 或 permissionless function 无法合理承担；
- 净安全收益大于权限扩张、行政成本和新单点故障；
- 权限、责任、退出和失陷影响已经机器可测试。

不满足以上条件的提议应改写为公开函数、协议对象或实现组件。

### 4.4 统计或经济主张

提交必须明确：模型、总体、随机性、依赖结构、误差目标、时间窗口、外部收益、参数来源和反证条件。只给模拟均值、单组参数或“攻击看起来不划算”不足以支持安全结论。

## 5. 推荐工作流

1. 先在 `docs/07-roadmap/open-questions.md` 中找到对应 Issue ID；
2. 写明假设、候选方案和拒绝条件；
3. 更新相应规范或分析文件；
4. 为变更添加确定性测试、性质测试、模型检查或仿真；
5. 更新 `docs/06-research/claims-and-sources.md` 中的论断状态；
6. 运行全部现有检查；
7. 提交小而可审查的变更；
8. 在证据不足时保留 `OPEN/CANDIDATE`，不要提前关闭问题。

## 6. 提交说明模板

```text
Change:
Problem / counterexample:
Status before:
Status after:
Affected objects/functions:
Affected invariants:
Affected threats:
New assumptions:
Compatibility/migration:
Tests or proofs:
Residual risk:
Documents updated:
```

## 7. 文档同步矩阵

| 变更 | 必须同步检查 |
|---|---|
| Principal / function / authority | terminology、identities-and-roles、system-context、threat-model、ADR |
| 对象或状态机 | protocol-spec、task-lifecycle、invariants、test vectors |
| RIR、前端或执行 Profile | terminology、system-architecture、protocol-spec、threat-model、ADR、conformance tests |
| 验证或统计 | result-validation、robustness、claims-and-sources、open-questions |
| 能力或暴露 | reputation、threat-model、robustness、simulations |
| 资金或结算 | protocol-spec、task-lifecycle、invariants、open-questions |
| 维护或治理 | administrative-cost、ADR、threat-model、current-status |
| Adapter / 区块链 | system-architecture、invariants、robustness、conformance tests |

## 8. 质量要求

- 使用 `terminology.md` 中的规范术语；
- 使用 **ACLt Protocol**，不得展开 ACLt；
- 每个外部事实优先引用原始论文、官方规范或一手实现文档；
- 明确写出文献支持范围，不能让外部成果替 ACLt Protocol 证明组合系统；
- 不提交无法复现的实验结果；
- 测试必须覆盖合法路径、直接反例、边界、并发、重放和故障恢复；
- 前端/编译器变更必须证明其输出满足同一 RIR 语义；不能以“Rust 编译成功”替代 RIR validator、golden vector 与跨实现差分测试；
- 隐私或控制关联数据必须最小化并说明用途；
- 不得静默删除失败实验、反例或被取代的决定。

## 9. 审查标准

变更只有在以下问题得到回答后才可合并：

- 是否缩小了歧义或证明义务？
- 是否保持全部相关不变量？
- 是否引入新的身份、权限、假设或行政成本？
- 在 Sybil、串谋、分区、重放、崩溃和资金耗尽下会怎样？
- 是否存在安全终态和回滚路径？
- 是否把候选结论误写为事实？
- 是否同步更新全部权威文档？

## 10. 行为与安全问题

保持技术讨论可审计、具体并针对论证，不针对个人。涉及未公开漏洞、密钥或可直接利用细节时，不应先进入公开讨论；正式安全披露流程仍为 `OPEN/P0`，在流程建立前应暂停公开可利用细节并联系当前维护者。

## 11. 许可

代码与参考实现的项目许可证已确定为 **Apache License 2.0**（SPDX：`Apache-2.0`），根目录已经包含相应 `LICENSE`。未来适用源码仍须加入 SPDX 标识；提交内容不得仅因位于同一仓库，就推定协议规范、文档、研究成果、名称或商标也适用 Apache-2.0。

贡献许可机制（仅依项目许可证、DCO 或 CLA）、第三方代码/依赖接受规则、`NOTICE` 维护规则，以及规范、文档和论文的独立许可证仍为 `OPEN/P0`。在这些规则完成前，外部贡献应逐项确认来源、版权归属和许可证兼容性，不得合入来源或授权不明的内容。
