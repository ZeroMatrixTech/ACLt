# R16 非主网测试部署的签名撤销

R16 实现非主网测试部署的签名撤销：新账本提交 20 个事件，两条 Receipt 完成
Phase B/D 回放与结算，9 个负例按预期拒绝，`make test` 通过 668 项 Python 测试
及 20 次 sanitizer 检查。基线为 main `967d6a7`（R15）；部署在 genesis 中选择撤销版本，
固定测试签发者签署该 genesis 的撤销声明，由 Requester 在现有签名通道提交；
撤销随权威日志事件提交，重复提交返回原记录。 [撤销合约](../../schemas/formal-migration/deployment-revocation.md)

撤销阻止新的 Receipt、Lease 激活、已发能力的首次消费和结果接纳。未决 Receipt
通过既有 Phase D 失效条件进入 `UNRESOLVED`，并按冻结政策处理资金。已有终态
及其结算权利可继续按原规则兑现。回放从固定检查点认证撤销事件和签名，
使用该事件在日志中的位置重建两类 Receipt 的状态。

`make test-deployment-revocation` 在新账本检查伪签名、跨 genesis 签名、授权、
nonce 冲突、撤销后提交以及篡改的历史快照。Rust 独立重算两条 Phase D 候选判决。

本切片适用于 ADR-0008 的候选非主网审计路径。正式 FM-A08 验收还依赖
Profile 与来源审批、撤销传播和新鲜性，以及正式部署证据。当前信任模型依赖固定
签发者、Requester 转送和单一权威日志。 [ADR-0008](../05-decisions/ADR-0008-fm-s3-interface-decisions.md)

## 验证结果

新账本提交 20 个事件，两条 Receipt 完成 Phase B/D 回放与结算。既有权利支付 12、
退款 5，撤销后的未决任务支付 0、退款 17。9 个负例按预期拒绝。
`make test` 通过，含 668 项 Python 测试及 20 次 sanitizer 检查。
R1–R15 的结果摘要逐项匹配历史记录。

双机验证待恢复。已配置的 `aki2` 在 SSH 预检返回 `no route to host`。
[机器可读证据](PROFILE-PHASE-D-R16-20261111.summary.json)
