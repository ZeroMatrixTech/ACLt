# 第三项工作维护与交接入口

工程 `FUNDING-WORK3` 的限定工作已完成，本页记录其维护与交接入口，内容覆盖统一双机运行、只读复核和证据布局。该工程按三阶段组织：冻结测试资金政策与原子预留、双端 outcome 与固定支付退款、实际进程故障与原权利恢复。
完成该限定工作不改变 SemanticStatus、VersionDisposition、ADR 或 Gate；正式对象与终态矩阵、真实支付和 OQ-10 仍分别跟踪。

## 统一双机运行

从仓库根在 A 显式启动：

```sh
make test-funding-work3 \
  FUNDING_WORK3_PEER=USER@B_IP FUNDING_WORK3_A_HOST=A_LAN_IP \
  FUNDING_WORK3_REMOTE_ROOT=/absolute/new/B/suite \
  FUNDING_WORK3_OUTPUT=/absolute/new/A/evidence
```

等效入口为 `python3 -B scripts/funding-work3.py run --peer USER@B_IP --a-host A_LAN_IP --remote-root /absolute/new/B/suite --output /absolute/new/A/evidence`。

本地根必须在仓库外且不存在，远端根必须全新。采用已有严格 SSH、Python/SQLite/OpenSSL 和保存的 Wasm fixture；不安装软件、下载依赖、重新编译 Rust、启动 VM 或修改系统服务/防火墙。遵守 [DUALHOST-SSH-1](../08-governance/dualhost-ssh-validation.md)。正常日常 `make check` 只做局部回归，不连接 B 或产生新的双机证据。

统一工具先锁定源码，顺序运行三组局部回归及真实双机矩阵，再只读核对全部保存证据。`reservation/`、`fixed/`、`recovery/` 各使用新目录、各自 genesis/issuer/enrollment/账本。A 的服务/账本和适用的 A worker 同故障域，B 独立目录运行请求/worker；实际资金、启动、结果和结算 RPC 通过 TCP，B→A 经 LAN。SSH 仅控制、部署、取证。

三组测试账本**不合并余额、权利或供给**。样例可复用相同冻结 Task ID，但 reservation/entitlement 还受不同 authority/deployment 约束；不能把三个测试部署当作同一生产任务重复付款的许可。第一片 v1 policy 与后两片 v2 policy 是显式版本演进，旧库/旧入口不迁移。

失败返回非零，保留原根目录、日志和原始失败，组件只清理本轮拥有的实验进程。不得复用旧输出目录或通过删除启动标记恢复计算；需要另一次取证时明确使用新根。

## 只读复核

将 `retained-pins.json` 的三份 issuer 公钥 digest 和完整 11 份 checkpoint digest 独立保存后：

```sh
python3 -B scripts/funding-work3.py verify \
  --evidence /saved/suite --pins /independently/retained-pins.json \
  --report /new/verification.json
```

该入口不 SSH、不启动矩阵/guest/编译器、不打开活数据库写事务，报告必须全新且在原证据根外。它会：

1. 核对当前完整源码锁与三份部署锁的闭合文件集合；源码漂移明确拒绝。
2. 核对公共文件清单和原字节摘要、三组矩阵/反例/回归记录；修改、丢失、符号链接和路径逃逸拒绝。
3. 在独立进程调用原维护 auditor：第一片 final、第二片 final，以及第三片 9 个中间/final，合计 11 个 checkpoint；缺失 pin 不从报告自动补齐。
4. 重建账户/预留/比较/结算状态并与保存投影一致；核对第三片提交前与回滚后导出及 anchor 相同。
5. 对正常样例重新绑定同一 Task commitment、RIR/input 原始字节、Profile/上限，以及两端保存 outcome；检查共享费用/cap 和声明的 v1→v2 演进，v2 policy 在后两片保持原字节。

哈希清单只提供完整性，不能自行认证来源；攻击者若能一起换证据、清单及所有 pin，清单本身不是信任根。合法旧 checkpoint 只说明其 as-of 状态，不能发现更新、防止权威回滚/分叉或提供生产 finality。auditor 共享 schema/codec/密码学原语，HMAC 认证来源是签名权威日志，不是独立泄露 enrollment key 后验证。三片的原始信任假设继续适用。

## 证据布局

| 文件/目录 | 内容和边界 |
|---|---|
| `source-lock.json` | 组合脚本/回归及三片与统计/授权/承诺依赖的完整源码 pin |
| `public-inventory.json` | 公共证据文件摘要，非认证根 |
| `retained-pins.json` | 三份 key pin、11 份 checkpoint pin；应独立保存，不含私钥 |
| `reservation/` | v1 冻结政策/可用与预留的单一测试账本、请求/回执、final checkpoint |
| `fixed/` | v2 资金前置、双端完整结果、比较/唯一分配、final checkpoint |
| `recovery/` | 真实丢回复、首次竞争、COMMIT/worker 中断、9 个 checkpoint 和恢复查询 |
| `suite.json` | 当前组合结果或失败摘要，不能替代原始证据 |

组件 `private/` 下的 issuer key/HMAC config 不进入公共清单，B 公共取证不含远端 private 目录，源码包不含运行库、密钥和运行目录。完整根仍可能有私密材料/机器标识，不能直接整体公开。运行路径/IP/用户名只在操作者本地保留；入库报告使用占位和摘要。

## 恢复与完成边界

当前正常恢复路径只发 STATUS。已结算取原回执；RESERVED 继续占用；不可用的结果保持未知，自动支付与退款不在恢复路径内。未提交事务确认回滚后可以显式 SETTLE，仍受原政策及唯一权利约束。worker 仅在持有完整 fsynced outcome 时重传；permit-only 或半成品不具备续算、补发执行资格或自动退款的条件。

历史 paid/refunded 已进入 available，资产供给只计一次。第一片覆盖范围不含 guest；后两片使用同一 Python reference，两台独立物理主机不构成独立执行实现或统计身份独立。SIGKILL/热日志恢复的适用范围限于进程崩溃；断电、整机重启、failover 与权威抗回滚需另行验证。

[工程总报告](FUNDING-WORK3-CLOSEOUT-20261024.md)列出新跑数据和交付验证。三片原始报告与失败保留。后续建议先做正式对象/接口收敛：列清 ExperimentalTaskCommitment、funding policy、funded-start、comparison、entitlement、EventRecord 与规范对象的迁移和证据缺口，再选最小范围补齐；价格/支付适配器范围保持现状，G0/G2/OQ-10 的关闭需另行证据。
