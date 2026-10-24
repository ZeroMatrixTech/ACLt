# 第二项工作维护与交接入口

工程标识 `TASK-WORK2`：最小实验任务承诺 → 实验授权/持久启动 → 完整提交/接纳与可重放日志。
这是限定实验工程工作，不是新 SemanticStatus/VersionDisposition；正式 ComputeReceipt、Lease、ExecutionCapability、EventRecord、验证判决和结算仍未实现。接纳只表示结构/绑定一致的完整提交被保留，不表示运算正确。

## 统一运行

从仓库根，在 A 上显式启动真实双机套件：

```sh
make test-task-work2 \
  TASK_WORK2_PEER=USER@B_IP TASK_WORK2_A_HOST=A_LAN_IP \
  TASK_WORK2_REMOTE_ROOT=/absolute/new/B/suite \
  TASK_WORK2_OUTPUT=/absolute/new/A/evidence
```

等效入口为 `python3 -B scripts/task-work2.py run --peer USER@B_IP --a-host A_LAN_IP --remote-root /absolute/new/B/suite --output /absolute/new/A/evidence`。
本地输出必须在仓库外，远端根必须全新；任何已有目录均拒绝覆盖。使用既有严格 SSH、已有 Python/SQLite/OpenSSL，无新安装或依赖下载。遵守 [DUALHOST-SSH-1](../08-governance/dualhost-ssh-validation.md)，不启动 VM 或改系统服务/防火墙。

统一入口先锁定源码、保存两端环境并运行三片本地回归，再分别重跑授权 16 场景和重放 12 场景/7 个篡改反例，运行两端承诺探针/比较，最后另进程重放中间与最终 checkpoint。B 在独立目录执行，A 临时服务和账本属于同一故障域；CHECK/CONSUME/SUBMIT 经实际 LAN TCP，SSH 用于部署、控制、取证。组件驱动只清理本轮临时进程；失败即非零退出，保留现场，不自动换目录重试或重新计算未完成任务。

`authorization/` 和 `replay/` 是独立回归部署，具有不同任务 nonce、grant、密钥和账本，不迁移旧库。`replay/` 本身包含完整组合链；跨片核对要求正常样例的工件/输入原始字节、RIR/Profile 摘要、输入引用、上限和等价规则连续一致，不要求 task ID 或回执相同。承诺探针明确无授权，只用于诊断绑定，不能作为部署 worker fallback。

## 只读核对保存证据

先把 `retained-pins.json` 中的 issuer 公钥摘要与两个 checkpoint digest 独立留存，再运行：

```sh
python3 -B scripts/task-work2.py verify \
  --evidence /saved/suite --pins /independently/retained-pins.json \
  --report /new/verification.json
```

此入口不连接 B、不运行矩阵/编译器/guest、不写旧数据库；报告必须全新且在证据目录外。它核对当前完整源码清单、两份部署锁、公开证据清单/摘要，调用承诺比较器，并在独立进程运行第三片 reducer，对齐 signed checkpoint 与保存投影。当前源码漂移、证据缺失/修改、错误 key/anchor 或不完整矩阵均拒绝。

第二片只复核保存的矩阵断言和证据哈希，不宣称其旧式操作行已被独立 reducer 重建。第三片才有独立状态重建；检查器共享 codec/密码学原语，不代表独立密码实现。公开 SHA 清单是完整性核对，不是来源认证；若攻击者能一起替换证据、清单和 pin 文件，清单本身无法提供信任。合法旧 checkpoint 只能说明旧时点，不能发现更新、阻止权威回滚/分叉。

## 文件与恢复规则

| 记录 | 用途/权威边界 |
|---|---|
| `source-lock.json` | 固定统一入口、回归和三个任务实验/统计依赖源码 |
| `public-inventory.json` | 保存公开证据的文件哈希；不是认证根 |
| `retained-pins.json` | 需独立保存的 key/checkpoint pin；不是密码或私钥 |
| `commitment-A/`、`commitment-B/` | 相同冻结绑定向量和两端诊断记录 |
| `authorization/` | 启动前在线消费、持久意图和故障拒绝记录 |
| `replay/` | 完整提交包、因果流、接纳回执、分离 checkpoint 和投影 |
| `suite.json` | 成功组合摘要或失败原因，不替代原始证据 |

运行私钥/enrollment 在各组件 `private/`，不进入公开清单或源码交付包；勿将整个运行目录作为公开材料发布。源码包不含数据库、密钥、远端地址或本轮原始运行目录。运行日志可能有机器标识/路径，只在操作者本地留存；入库摘要须去除实际 IP/用户/绝对路径。

只有封存完整包和 PREPARED 的状态能重传原字节；不重新消费，不执行 guest，稳定返回首次回执。A ACCEPT 与 B ACK 分开，丢回复可能暂时 accepted 且 unacknowledged。不完整 INTENT/PERMIT/OUTCOME 不自动续算，不通过删除状态、换目录或新 epoch 恢复资格。日志中的 INVOKE 是调用意图；诚实 pinned worker/存储与单一可信不回滚 issuer/时钟仍是接受假设。SIGKILL 和服务重启不代表断电。

## 当前边界与下一步

[第二项总报告](TASK-WORK2-CLOSEOUT-20261024.md)列出本次重跑结果；三个历史切片报告保留原范围。日常 `make check` 仅做本地回归，不自动联网或沿用历史双机通过状态。

下一项建议先做**同一冻结任务的双端 outcome 与精确比较证据绑定**：把已有 RIR 字节、输入、上限、两端 outcome 和独立比较记录连接起来，并明确 experimental_task_id 与正式对象的迁移缺口。相等仅是该次精确比较证据，不新增 `REEXEC_EXACT` 方法，不直接变成 TRUSTED，不顺带引入结算。正式对象字段/签署、完整 conformance、B/Q、经济/生产资格分别跟踪；未因第二项收尾而关闭。
