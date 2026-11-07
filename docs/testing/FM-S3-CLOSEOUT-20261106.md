# FM-S3 候选双机验收与总体收尾

2026-11-06，基线 `9598782` 加本轮工作区。两台物理机各自核对同一源码清单并独立构建 Rust 执行器，二进制 SHA-256 均为 `3942c7bb33b667c13832ffe793e6f3632cd0fc434993b13de80087c8ef6d158e`。A 运行权威与审计者，B 运行执行者。业务请求经 LAN TCP，SSH 用于部署、控制和复核。三张 Receipt 共用一个候选测试账本。源码、快照及带外保存的 checkpoint 摘要见 [机器摘要](FM-S3-CLOSEOUT-20261106.summary.json)。

| 实测场景 | 结果 |
|---|---|
| 真实跨机 RPR 执行与结果接纳 | A、B 各运行真实 OK outcome，签名结果经权威接纳，一致比较派生 UNRESOLVED |
| 重传与冲突 | B 重传返回首份结果，异内容冲突保留首份 |
| 并发结算 | 两个独立请求取到同一分配 |
| B 结果的 TCP 丢回复 | 权威已接纳，B 重传恢复原结果 |
| COMMIT 前服务中断 | 受控进程退出，重开后状态为 READY |
| COMMIT 后服务中断 | 受控进程退出且回复中断，重开后查到 COMMITTED，重传取原权利 |
| 截止竞争 | B 在恰好 deadline 提交，A 同时请求终态。晚结果未纳入，终态 EXPIRED，执行槽位投影 MISSING |
| A/B 公开重放 | 两端以相同 genesis pin 与保存的 checkpoint 复核，39 事件、链头及状态摘要一致 |

账本最终为可用 39、已分配 29、预留 0，共 68 测试单位。两条 UNRESOLVED 与一条 EXPIRED 记录均有各自唯一分配。候选入口和结算合同见 [S3b](FM-S3B-AUTHORITY-20261106.md)与 [S3c](FM-S3C-SETTLEMENT-20261106.md)。

2026-11-07 公开材料已按留存字节入库，归档摘要、genesis/checkpoint 索引与离线回放入口见 [证据归档收尾](FM-EVIDENCE-CLOSEOUT-20261107.md)。

## 四项工作收尾

| 工作 | 已交付范围 | 正式验收待补 |
|---|---|---|
| 接口决定 | 维护者接受首轮候选测试路线。[ADR-0008](../05-decisions/ADR-0008-fm-s3-interface-decisions.md) | 正式对象、相位和部署接口按独立门槛推进 |
| 结果接纳和判决 | 真实执行入口前由固定 Provider 签署并等待启动确认。接纳记录验证完成时刻、期限、首份结果、因果日志及候选判决 | 启动记录为受信测试适配器自述。完整 Phase B/D、AssumptionEvaluation、Task trap、受认可的执行闭合来源及可耗尽预算路径仍待验收 |
| 权利与恢复 | 两种候选终态的过程费和退款、唯一权利键、并发去重、原子分配及查询恢复 | 其他终态及完整 INV-07 规则证据仍待扩展 |
| 双机与正式接口审查 | 候选双机矩阵 8 场景通过，归档可重放公开材料 | 正式接口保持 OPEN，后续按下表验收 |

| 正式接口 | 候选证据 | 正式验收要求 |
|---|---|---|
| AUTHORITATIVE-OBSERVATIONS | 验证完成时间与原子接纳，认证快照可重放 | 核验正式来源 contract、完整 frontier 以及各边界和闭合来源 |
| AUDIT-PHASE-B-PATH | 无 EligibilitySnapshot 的测试入口和状态推进 | 规范转换矩阵、方法约束与正式阶段证明 |
| AUDIT-WIRE-BOTTOM | 新候选版本采用省略键并重新签名 Receipt | 正式 ContentMap、Schema View、编码向量与注册 |
| NONMAINNET-ASSURANCE | 带外测试 genesis pin 与独立 checkpoint | 部署联合类型、引用及各相位接线、正式准入评审 |

当前可收口的是首轮候选 audit-only 执行与测试账务。完整历史矩阵复跑、正式接口及 G0/P0-1B 验收保留独立记录。进程退出证据覆盖本轮两个 COMMIT 边界。

## 复现

运行 `python3 -B scripts/fm-s3-dualhost.py --peer <B_USER>@<B_IP> --a-host <A_IP> --remote-root /tmp/fm-s3-<NEW_RUN> --output <NEW_LOCAL_DIR>`。两端均使用新目录，B 主机密钥严格校验。公开归档包含 config、snapshot、anchor、源码清单及对应复核程序，重放入口为 `scripts/check-fm-s2-evidence.py --s3b`。复核时使用独立留存的 genesis 与 anchor pin。
