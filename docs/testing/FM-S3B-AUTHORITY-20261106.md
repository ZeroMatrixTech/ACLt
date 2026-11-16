# FM-S3b 本地权威接纳与终态

2026-11-06。本报告记录 FM-S3b 本地权威接纳与终态的候选实现：`ACLt/FM/S3b/1` 固定候选 audit 合约，本地权威服务、终态求值与快照复核入口已交付；`make check-fm-s3-authority` 覆盖签名、边界、重传、冲突、唯一终态、快照和提交后丢回复的局部回归。基线 `9598782` 加本地 ADR-0008 与 S3b 工作区变更。[ADR-0008](../05-decisions/ADR-0008-fm-s3-interface-decisions.md)

`ACLt/FM/S3b/1` 固定候选 audit 合约。无 claim 和不适用参数块采用省略键，新组件引用产生新 Receipt，须重新签名并绑定新测试 genesis。使用 `s3_authority.bind_bundle` 生成候选内容。服务以 `scripts/fm-s2-service.py --s3b --clock-file PATH` 选择该路径，首次启动可加 `--create`。沿用 S2 签名请求封套、SQLite 事务和快照格式，S3b 快照用 `s3_authority.verify_snapshot` 与带外保存的 checkpoint 复核。命令行可使用 `scripts/check-fm-s2-evidence.py --s3b`，提供 genesis pin 和 anchor。使用 `scripts/fm-s2-client.py --body-file PATH` 签署并发送给定 CBOR 的 S3 请求体。

| 操作 | 候选行为 |
|---|---|
| S3_START | 指定角色签署的入口自述，绑定真实已提交 CONSUME 事件。AUDITOR 的该测试入口事实推进 RUNNING。 |
| S3_RESULT | 独立签名请求携带启动引用与规范 OK outcome。签名和内容验证后读权威测试时间，严格小于期限才可接纳。 |
| S3_HOST_FAULT | 同一履约槽位中的自述，零接纳成本。首份合法结果或报告占用槽位，后续异内容返回冲突，每角色只保留第一条冲突证据。 |
| S3_REVOKE | 固定 Requester 签署测试来源撤销，阻止后续启动与接纳，供失效分支回归。 |
| S3_FINALIZE | Requester 触发确定性求值。有配对结果、达到期限或来源撤销时可提交，重复请求返回原决定。 |

接纳成本保守取整项对应角色资金桶。等值重传跨传输 nonce 返回原结果。比较重放使用两份已接纳的规范 outcome 全字节。求值记录含明确的假设结果、未知启动事实、条件向量、比较和终态，终态提交围栏释放暴露，资金继续预留供 S3c。终态只可为 UNRESOLVED 或 EXPIRED。候选规则在此配置中保留 EXECUTION_FAILED 和 BUDGET_EXHAUSTED 条件的位置，其可达性等待受认可的执行闭合来源和可耗尽预算合约。

测试时钟由操作者提供，拒绝小于已提交时间或同次验证前采样的读数。该边界依赖操作者在重启后提供可信的同域时间。签名启动入口是固定 Provider 在候选测试中的自述，后续需绑定真实 RPR 入口。局部入口只接收 OK outcome，Task trap、正式 AssumptionEvaluation 结构及完整 Phase B/D 仍待实现。S3c 权利分配与双物理机故障矩阵另行验证。

`make check-fm-s3-authority` 运行签名、边界、重传、冲突、唯一终态、快照和提交后丢回复的局部回归。此处使用合成结果字节。
