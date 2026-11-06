# FM-S3c 候选账务与恢复

2026-11-06。基线 `9598782` 加本地 S3b 权威状态机及 ADR-0008。适用资产为冻结 FundingPolicy 中的预付测试整数资产。[ADR-0008](../05-decisions/ADR-0008-fm-s3-interface-decisions.md) · [S3b 范围](FM-S3B-AUTHORITY-20261106.md)

## 权威入口与分配规则

同一 S3b 权威服务接受 Requester 签署的 `S3_SETTLE` 和 `S3_SETTLEMENT_STATUS`。请求体为 `{receipt}`。原有 client 支持直接发送这两个操作，无须自定义请求体。

- 结算从当前 Receipt 的投影取唯一终态，并在已认证事件前缀中查找唯一 `S3_FINALIZE` 事件，核对终态摘要。完整重放逐条验证链和状态摘要。
- 使用冻结的 S1b 费用表。首份合法结果投影为 COMPLETE，首份 HostFault 自述为 HOST_FAULT，无提交为 MISSING，存储固定为 MISSING。比较结果只参与判决记录。执行与审计分项费受对应槽位的已预占成本约束。
- 费用权利分配给 Assignment 绑定的 Provider，退款归冻结的 Requester。权利键由候选域、genesis、Receipt、权利种类与受益人派生，金额不进入键。只有正金额生成权利，已分配键不得再次使用。
- 唯一终态事件引用、Decision 摘要、政策引用、权利、预留释放与退款在同一 SQLite COMMIT 提交。未曾预留的 Receipt 以零金额关闭。账本不变量是可用资金、仍预留资金和已分配过程费之和等于初始资金。
- 同内容重传和并发分配请求返回原结算记录。查状态可区分 AWAITING_TERMINAL、READY 和 COMMITTED，查询不增加业务事件。COMMIT 前中断可恢复 READY，COMMIT 后丢回复可取回原权利与金额。

## 验证范围

`make check-fm-s3-authority` 覆盖未终态/非 Requester 拒绝、客户端试图指定政策/金额/终态拒绝、不一致结果按冻结政策付费、HostFault 与缺失项的退款、无预留零分配、并发请求、已分配后为另一 Receipt 预留及 COMMIT 边界的异常注入和重新打开账本。结算快照沿用带外 checkpoint 的 S3b 重放入口。

本地实现只覆盖 S3b 当前可产生的候选 UNRESOLVED 与 EXPIRED。权利记录与余额变动留在测试账本。Task trap、执行闭合与可耗尽预算路径依赖 S3b 后续证据。双物理机上的进程中断、传输丢回复和端到端重放列入下一阶段验收。
