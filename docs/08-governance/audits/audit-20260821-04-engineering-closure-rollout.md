# ACLt 工程闭合原则全仓库落地审计

> 报告状态：`COMPLETE_LOCAL_PREPARED_CHANGE`
> 审计编号：`AUDIT-20260821-04`
> 审计类别：工程假设、主网保障、单一权威与文档连续性审计
> 审计日期与时区：2026-08-21T21:51:49+02:00
> 审计者：Codex（本地工作树语义与机械核查）
> 程序版本：[`../audit-procedure.md`](../audit-procedure.md)
> 基线 commit：`a99e344f29f58e61a22c1d0c1b304fd9191c6295`

## 1. 审计目标与权限

| 项目 | 内容 |
|---|---|
| 目标 | 将“结构/算法必须闭合，来源/部署允许以可执行工程假设闭合”的原则同步到仓库，并跳出最后两个二选一问题 |
| 范围 | Overview、requirements、architecture、protocol、analysis、ADR、research、roadmap、governance、README 和既有验证模型测试 |
| 排除范围 | 不提交、不推送、不修改外部网络；不启动 P0-1B 实现；不把 draft-11 直接宣布为规范 |
| 允许的写操作 | 更新 Markdown 规范与索引，新增 ADR、思路树和本审计 |
| 既有修改保护 | 工作树在本轮开始前已包含用户的 ADR-0004、验证模型、测试和多份文档修改；全部保留，未回退或覆盖 |

## 2. 本轮工程决定

### 2.1 四层证据模型

| 层 | 关闭方法 | 阻塞规则 |
|---|---|---|
| A 结构 | Schema、canonical encoding、静态向量 | 不闭合则阻塞对应接口 |
| B 算法 | 纯函数、定理、模型检查、差分对拍 | 不闭合则阻塞对应判决 |
| C 来源忠实性 | 追加式日志、权限隔离、集成测试、故障注入、实现审计 | 不阻塞无关 Schema；来源未建立时关闭对应能力 |
| D 部署风险 | 版本化主网保障、允许组件集合、损失预算、有效期、撤销 | 不阻塞通用协议工件；不得对未保障部署作安全主张 |

### 2.2 身份与官方主网

- V1 不证明每个 PrincipalID 对应不同自然人；身份数量不能直接成为独立证据数量。
- 官方主网可以在有限网络、版本、组件、相关性策略和损失预算内接受工程风险。
- Foundation/维护组织可以发布只能收紧能力的 `MainnetAssuranceProfile`，但不是 Principal、不是个案裁判，报告不得进入验证权重或停止条件。
- fork、私网和替换组件不自动继承官方主网保障。

### 2.3 日志忠实性

- 协议冻结日志消费 contract、编码、因果引用、包含/一致性/终局验证和失败语义。
- 日志可由区块链、Merkle transparency log 或等价追加式模块实现。
- Schema 不声称证明写入方没有旁路；该性质由权限边界、故障注入、崩溃恢复、重放和独立对账验收。

## 3. 最后两个问题的跳脱闭合

| 原问题 | 被拒绝的假二选一 | 当前闭合 | 后续证据 |
|---|---|---|---|
| 单值 verdict vs flag set | 要么兼容、要么信息完整 | 保存规范化 `CauseSet`；由版本化纯函数派生唯一 `EffectiveVerdict` | Schema/摘要/归约向量 + 多故障注入 |
| 是否增加第三个 Dispatch scope | 要么少检查、要么复制第三份真相 | active Lease 是唯一执行范围权威；派生 `ExecutionCapability`，Dispatch 与 RPR 分别校验 | 派生/消费 golden vectors + API 数据流、竞态、恢复和旁路审计 |

两个结论均不依赖“全局最优性证明”。只要接口不可歧义、失败时 fail closed、保留升级逃生口，即可进入工程实现。

## 4. 跨文档连续性矩阵

| 文档面 | 同步内容 | 结果 |
|---|---|---|
| Design / overview | DP-17、条件性 TRUSTED、官方主网边界 | `PASS` |
| Threat / invariants | assurance 滥用、日志旁路、scope 旁路、原因丢失；INV-13/15/16 | `PASS` |
| Architecture / lifecycle / roles | ExecutionCapability、单一权威、多点校验、Foundation 有限职责 | `PASS` |
| Protocol / validation / V1 | assurance 绑定、CauseSet/reducer、条件安全和失败语义 | `PASS` |
| Robustness / administration / claims | 工程证据层、成本、残余风险和 CLM-112—115 | `PASS` |
| Roadmap / open questions | 从“等待完美理论”改为分层 Gate；两项不再是理论阻塞 | `PASS` |
| README / contribution / governance | 阅读入口、贡献证据类型与审计规则 | `PASS` |

## 5. 仍然不能闭合的结构

| 项目 | 通俗解释 | 当前处置 | 是否阻塞 P0-1B |
|---|---|---|---:|
| 通用 permissionless 的 (B) | 无法只看注册身份就知道到底有多少独立攻击能力 | 官方主网按有限环境做准入、相关簇、暴露和损失预算；条件不足则 `AUDIT_ONLY/DISABLED` | 否；阻塞该部署启用 `REEXEC_BOUNDED` |
| 目标任务类的 (Q) | 容易验证任务上的成功率不一定能外推到困难任务 | 同类锚定、故障注入、保守下界与活性 DP；无数据则不保证活性 | 否；阻塞相应 Profile 的经济启用 |
| RIR/RPR/validator 正确性 | 多次执行不能发现所有实现共享的同一个 bug | DIRECT/PROOF 优先、多实现差分、conformance、漏洞撤销 | 否；阻塞缺少 CorrectnessBridge 的 Claim |
| 日志/Registry 来源诚实 | 数据格式正确不代表记录者没有漏写或绕过 | 追加式终局日志、权限隔离、透明度证明、恢复与对账 | 否；来源证据缺失时相应能力 fail closed |
| Foundation/保障失陷 | 有限组织仍可能犯错、被捕获或密钥失陷 | 只能收紧、范围绑定、有效期、多签/撤销、公开证据和绝对损失上限 | 否；阻塞官方主网保障发布 |

这些问题不是被“证明消失”，而是被移到正确的工程 Gate。任何 Profile 只能在自己的条件与保障范围内启用。

## 6. 机械与模型检查

| 检查 | 结果 |
|---|---|
| 验证模型 unittest | 13/13 `PASS` |
| Markdown 文件 | 43 个 |
| 相对链接 | 0 个缺失 |
| H1 | 每文件恰好 1 个 |
| fenced code block | 全部成对 |
| HTML 空格实体与转义标题 | 0 个 |
| 临时 `__pycache__` | 测试后已删除 |

## 7. 判定

| 审计问题 | 判定 |
|---|---|
| 工程闭合原则是否已同步到主要仓库层 | `PASS` |
| 最后两个问题是否仍需作为理论二选一阻塞 | `NO` |
| 是否允许准备 P0-1B 工件 | `PASS_WITH_ENTRY_CONDITIONS` |
| P0-1A 是否因本报告自动通过 | `NO`；draft-11 仍需独立入口审计 |
| P0-1 是否关闭 | `NO`；P0-1B 与跨文档 conformance 尚未完成 |
| G0 是否关闭 | `NO` |
| 是否可声称通用 permissionless `TRUSTED` | `NO` |

## 8. 后续工程顺序

1. 独立审计 VerificationProfile draft-11，只检查 A/B 接口闭合和 fail-closed 完整性；
2. 实现 P0-1B 的 L1a/L1b/L2、CauseSet/reducer、MainnetAssuranceProfile 和向量；
3. 实现 ExecutionCapability 派生、Dispatch/RPR 双点校验及旁路/竞态/恢复测试；
4. 建立追加式终局日志、权限审计、重放和故障注入证据；
5. 以 `DISABLED → AUDIT_ONLY → ENABLED` 逐 Profile 推进官方主网试点；
6. 用试点数据审计 Foundation 净价值、误暂停、保障范围和剩余损失，不将经验数据变成个案真理权。

## 9. 最终结论

> 本轮全仓库工程语义连续性 `PASS`。两个长期徘徊的问题已经从“寻找唯一理论最优解”改写为可实现、可对拍、可撤销的接口设计。P0-1B 可以在 draft-11 独立入口审计通过后启动；现实身份、日志来源和主网风险不再阻塞所有工程工作，但对应能力在工程证据不足时必须关闭、降级或 fail closed。
