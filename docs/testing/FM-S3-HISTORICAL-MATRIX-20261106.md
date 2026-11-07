# Work 2/3 历史矩阵与 FM-S2/S3 候选回归

基线 `b555231143b462c54fd320dc2924107a57fac4af` 加本轮测试驱动。矩阵逐项引用原实验驱动的场景标识。覆盖判定针对迁移后的候选路径及对应安全性质。旧回执、费用规则与持久化文件按各自版本解读。

| 代号 | 双机证据 |
|---|---|
| S2 | [FM-S2 运行报告](FM-S2-20261031.md) |
| S3 | [FM-S3 收尾报告](FM-S3-CLOSEOUT-20261106.md) |
| TRAP | [真实除零 Task trap](FM-S3-TASK-TRAP-20261106.md) |
| T | 本轮 `--terminals`，组合核验入口、闭合、预算与事务恢复 |
| H | 本轮 `--historical-gaps`，补跑 Work 2/3 迁移后的故障边界 |

## Work 2 任务日志与重放（12 项）

来源为 [Work 2 切片报告](TASK-REPLAY-SLICE3-20261024.md) 和 [原驱动](../../experiments/aclt-task-replay/dualhost.py)。

| 历史场景 | FM 对照 |
|---|---|
| `normal-complete-chain` | S3、T。B 持有效 Lease 执行，权威签名接纳，参与唯一终态。 |
| `identical-packet-replay` | H `concurrent_exact_result_replay`。原签名请求字节重发，签名结果与 checkpoint 不变。 |
| `concurrent-identical-retransmissions` | H `concurrent_exact_result_replay`。B 两连接共用屏障，重发同一签名请求。 |
| `authority-restart-stable-receipt` | H `restart_exact_result_replay`。重开权威后原签名请求保留结果与 checkpoint。 |
| `conflicting-packet-preserves-original` | S3 `duplicate_and_conflict`。冲突指向首份接纳身份。 |
| `accepted-without-worker-ack` | S3、H `result_commit_reply_loss_and_recovery`。新账本以一次接纳事件表达；旧 worker ACK 状态已退出此路径。 |
| `lost-reply-recovers-same-receipt` | H `result_commit_reply_loss_and_recovery`。补发返回与唯一接纳事件结果摘要一致的签名响应。 |
| `offline-replay-does-not-recompute` | H `saved_outcome_resubmitted_without_guest`。停服时持久化 outcome 可从原目录读取；后续仅上传保存结果。 |
| `prepared-process-kill-retransmits-complete-packet` | H `saved_outcome_process_exit_holds_funds`、`saved_outcome_resubmitted_without_guest`。新边界是 outcome fsync 后退出，恢复时以保存结果形成签名提交。 |
| `incomplete-after-intent-never-recomputed` | H `worker_exit_after_intent_no_reexecution`。保留 INTENT_ONLY，拒绝部分结果。 |
| `incomplete-after-outcome-never-recomputed` | H `worker_exit_after_guest_before_persistence_no_reexecution`。guest 返回后、持久化前退出，保留未知且拒绝部分结果。 |
| `corrupt-copy-rejected-original-replayed` | H `invalid_first_result_then_valid`。正确签名携带坏 outcome，checkpoint 不变，原结果随后可接纳。 |

## Work 3 固定结算（12 项）

来源为 [固定结算报告](FIXED-SETTLEMENT-SLICE2-20261024.md) 和 [原驱动](../../experiments/aclt-fixed-settlement/dualhost.py)。

| 历史场景 | FM 对照 |
|---|---|
| `same-frozen-task-funded-once-executed-on-two-hosts` | S2、T。双端绑定同一冻结 Receipt，各有一份 Lease，结果精确一致。 |
| `exact-OK-fixed-fee-and-remainder-refund` | S3、T、H。双端 OK 后 UNRESOLVED，按冻结政策分配过程费 12，退款 5。 |
| `same-entitlement-original-receipt` | H `payment_commit_reply_loss_and_recovery`。原 nonce 与新 nonce 都返回同一分配，checkpoint 不变。 |
| `concurrent-retransmissions-no-extra-payment` | H `payment_commit_reply_loss_and_recovery`。两个 B 连接对已结算任务并发重试，保留唯一分配。 |
| `saved-outcome-retransmission-no-reexecution` | H `saved_outcome_resubmitted_without_guest`、`concurrent_exact_result_replay`。 |
| `nonpayer-cannot-settle` | H `non_requester_settlement_rejected`。已签名 Provider 调用被角色绑定拒绝，checkpoint 不变。 |
| `two-complete-gas-traps-full-refund` | TRAP 覆盖真实双端除零 trap 接纳；T/H 覆盖零过程费时全额退款。旧版 gas trap 必须全退的业务规则已由冻结过程费政策替代。双机 [RIR 独立核心](RIR-INDEPENDENT-CORE-20261028.md)已有 gas 耗尽向量。FM-S3 账务路径未单独重跑该 trap。 |
| `refund-idempotence` | H `full_refund_commit_reply_loss_and_recovery`。完全相同及新 nonce 重试保留同一笔退款。 |
| `missing-side-holds-full-reservation` | H `single_role_holds_full_reservation`。期限前只有执行方结果时保留 17，尚无终态或分配。 |
| `unreserved-start-no-guest` | H `unfunded_start_no_guest`。无激活 Lease 时本地不写 intent。 |
| `wrong-task-rejected-before-invocation` | H `foreign_receipt_no_guest`。活动 Lease 对应另一 Receipt 时不能重用已绑定的 worker 目录。 |
| `restart-query-original-settlement` | S3、T `failed_settlement_after_commit_restart`。重开后查到原分配，重传不重复分配。 |

## Work 3 结算恢复（14 项）

来源为 [结算恢复报告](SETTLEMENT-RECOVERY-SLICE3-20261024.md) 和 [原驱动](../../experiments/aclt-settlement-recovery/dualhost.py)。

| 历史场景 | FM 对照 |
|---|---|
| `lost-pay-committed-without-TCP-reply` | H `payment_commit_reply_loss_and_recovery`。B 未收到回复，账本已有支付与余额退款。 |
| `lost-pay-query-original-no-repeat-allocation` | H 同上。带签名的查询恢复原分配，事件摘要一致，重发不增加事件。 |
| `lost-refund-committed-without-TCP-reply` | H `full_refund_commit_reply_loss_and_recovery`。EXPIRED 全退已提交，B 未收到回复。 |
| `lost-refund-query-original-no-repeat-allocation` | H 同上。查询恢复全退，重发不增加事件。 |
| `SIGKILL-before-COMMIT-rolls-back-money-entitlement-event` | T `failed_settlement_before_commit_restart`。事务内追加后受控进程退出，恢复时 READY 且 checkpoint 完全相同。 |
| `query-unsettled-then-explicit-one-settlement` | T 同上及 `failed_settlement_after_commit_restart`。先只读查询 READY，再显式结算，链恰延长一条。 |
| `SIGKILL-after-COMMIT-retains-original-allocation` | T `failed_settlement_after_commit_restart`。事务已提交后受控进程退出，重开为 COMMITTED。 |
| `restart-query-original-receipt-after-committed-kill` | T 同上。查询恢复唯一分配，重发返回相同分配。 |
| `two-barrier-released-B-clients-first-settlement-one-entitlement` | H `first_settlement_two_B_clients_barrier`。两份独立签名请求由 B 同屏障放行，只一条结算事件，同一分配。 |
| `worker-SIGKILL-after-fsync-outcome-still-pending` | H `saved_outcome_process_exit_holds_funds`。观察已 fsync，进程受控退出，权威仍未接纳结果，资金全额占用。 |
| `saved-outcome-retransmit-without-new-invocation` | H `saved_outcome_resubmitted_without_guest`。拒绝新目录启动，原目录返回同一观察并恢复提交。 |
| `worker-SIGKILL-after-permit-no-recompute-no-refund` | T `executor_killed_after_permit_consume` 和 H `worker_exit_before_guest_holds_funds`。已消费无调用记录与已记调用入口无 outcome 分别复核；期限前继续占用。 |
| `unavailable-authority-no-guessed-payment-refund` | H `offline_settlement_query_no_inference`。B 真实连接被拒，无权威结算结果。 |
| `incomplete-evidence-retains-full-reservation-after-restart` | H `restart_incomplete_holds_full_reservation`。恢复后 checkpoint 原样，期限前继续占用 17。 |

## 本轮双机结果（2026-11-06）

两个模式均以退出码 0 完成。36 组断言含四次跨机公开重放。A、B 对各账本的链头和状态摘要一致。下表四套账本各自守恒，事件数和资产彼此独立。

| 模式与账本 | 通过组数 | A/B 重放事件 | 初始余额 | 可用 | 已分配 | 预留 |
|---|---:|---:|---:|---:|---:|---:|
| `terminals-primary` | 11 | 36 | 68 | 51 | 17 | 0 |
| `terminals-secondary` | 5 | 13 | 22 | 22 | 0 | 0 |
| `historical-gaps-primary` | 11 | 29 | 68 | 44 | 24 | 0 |
| `historical-gaps-secondary` | 9 | 24 | 68 | 68 | 0 | 0 |

T 的首套账本复核了两端入口、已核验入口后的注入宿主资源故障、`FAILED` 的原子结算，以及已消费但入口未知时的 `UNRESOLVED`。第二套复核了入口后中断走到 `EXPIRED`，以及激活所需 17、余额仅 5 时的 `FUNDING_EXHAUSTED`。

H 的首套账本确认两条来自 B 的首次结算连接只追加一条分配事件，支付和余额退款的回复丢失可恢复。第二套确认 worker 在 intent、guest 前与 guest 后未落盘边界均不会补算，停服期间查询没有可用权威结果，重开仍持有资金，到期后的全额退款可在丢回复后恢复。

首跑在任务创建前因五份完整 Receipt 超过编码器 10,000 项限制退出。拆分后首轮复跑又发现客户端会将未签名的拒绝帧归为通用 `S2 fields`。最终驱动直接核对预期诊断，并用签名响应或 checkpoint 核对权威状态。共享编码上限与协议实现保持原样。失败原始日志和运行目录分别留存。

两端 Ubuntu x86_64，A 内核 7.0.0-43，B 内核 7.0.0-42；两端 Python 3.14.4、Rust 1.93.1。双机分别构建的执行器 SHA-256 相同。本地 `make check` 23 组 463 项通过。

四套账本的 genesis、链头、状态摘要和源码清单 SHA-256 见 [机器摘要](FM-S3-HISTORICAL-MATRIX-20261106.summary.json)。外置公开归档 `FM-S3-HISTORICAL-MATRIX-public-evidence.tar.gz` 的 SHA-256 为 `706b92fdbbca8d7d411769a008c592e0e470d1561ec95fd57c68b85ad872cba8`，包含每套的 config、anchor、snapshot、回放入口和本轮固定源码。归档内不含私钥或运行数据库。

2026-11-07 公开材料已按留存字节入库，归档摘要、genesis/checkpoint 索引与离线回放入口见 [证据归档收尾](FM-EVIDENCE-CLOSEOUT-20261107.md)。

## 复跑入口

沿用 DUALHOST-SSH-1。两个模式使用同一源码树，各启动两套独立 genesis 与运行目录，每套最多三份 Receipt。A 持权威、审计和 T 的观察方密钥；B 运行执行方，H 的结算请求由 A 签名后通过 B 的 TCP 连接发出。事务故障和 worker 故障通过测试钩子受控退出进程。测试时钟由操作者提供。各模式保留单独的账本与 A/B 重放证据。

```sh
python3 -B scripts/fm-s3-dualhost.py --terminals \
  --peer '<B_USER>@<B_IP>' --a-host '<A_IP>' \
  --remote-root '/tmp/fm-s3-terminals-<RUN>' --output '<EVIDENCE_ROOT>/terminals'
python3 -B scripts/fm-s3-dualhost.py --historical-gaps \
  --peer '<B_USER>@<B_IP>' --a-host '<A_IP>' \
  --remote-root '/tmp/fm-s3-history-<RUN>' --output '<EVIDENCE_ROOT>/historical'
```

本轮仍在候选测试层。FM-A01–A12、正式对象准入、真实断电、权威回滚与主网保证继续使用各自的验收证据。
