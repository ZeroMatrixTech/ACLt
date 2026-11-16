# FM-S3 候选 Task trap 接纳

2026-11-06，基线 `3275a63`。本报告记录 FM-S3 候选 Task trap 接纳：固定除零向量在两端独立执行，实际输出 `TRAP_INTEGER_DIVIDE_BY_ZERO`；8 个 LAN 场景通过，两端重放 39 个事件一致，测试账本 68 单位最终为可用 39、已分配 29、预留 0。候选 audit 合约显式启用 `RIR_OK_ABORT_AND_TRAPS_V1`，合约字节进入 Receipt 组件绑定，试验用新签名 Receipt 与新 genesis；已有仅 OK 合约按原限制复核。

| 结果 | 规范字段 |
|---|---|
| OK | outcome、gas_used、output，output 受冻结上限约束 |
| ABORT | outcome、gas_used、uint32 abort_code |
| 执行器有限枚举内的 Task trap | outcome、gas_used |

所有变体必须使用规范 CBOR，gas 不超过 Receipt 的冻结预算。Task trap 和 ABORT 均省略 output，避免把失败前的部分输出计为完整结果。宿主故障、输入拒绝及未知类型拒绝进入结果槽位。worker 复核运行时返回的结果字节摘要后才生成提交体。候选权威按原角色、执行及期限绑定验签，再按完整结果字节比较。

Task trap 是有效提交。双方 trap 一致时生成 CONCORDANT 与候选 UNRESOLVED，已接纳结果按冻结政策投影为 COMPLETE。执行闭合事实、真正可耗尽的预算和权威可验证启动来源属于第二项后续切片。

2026-11-07 公开材料已按留存字节入库，归档摘要、genesis/checkpoint 索引与离线回放入口见 [证据归档收尾](FM-EVIDENCE-CLOSEOUT-20261107.md)。

## 双机结果

A 承载权威和审计者，B 承载执行者。两端使用固定的除零向量独立执行，实际输出 TRAP_INTEGER_DIVIDE_BY_ZERO。通过 8 个 LAN 场景，包括签名结果接纳、重复与冲突、并发分配、结果回复丢失、COMMIT 前后重启、截止竞争和公开快照复核。两端重放 39 个事件，链头及状态摘要一致。测试账本 68 单位最终为可用 39、已分配 29、预留 0。[机器摘要](FM-S3-TASK-TRAP-20261106.summary.json)

复现沿用 [S3 双机入口](FM-S3-CLOSEOUT-20261106.md)，增加 `--task-trap` 参数，并使用新的两端运行目录。ABORT 与其他 trap 的字段覆盖来自局部回归，物理实跑向量为除零。
