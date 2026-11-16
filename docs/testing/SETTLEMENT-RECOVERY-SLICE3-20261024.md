# 第三项工作 · 切片 3：真实结算故障与账务恢复

日期：2026-10-24。状态：**本切片限定工程范围完成**：以真实 TCP 丢回复、COMMIT 前后进程终止和首次结算竞争为条件，14 个故障/恢复场景在 A/B 两台物理主机全部通过（见「真实双机结果」）。
基线 `afde34097ed283790e08bfefde4467428b5fb524`，预检工作区干净。新增 [aclt-settlement-recovery](../../experiments/aclt-settlement-recovery/README.md) 独立恢复测试入口；第二片 v2 结算转移、政策/证据对象、独立 auditor 和其他既有实验源码全部保持原字节，旧库不迁移，价格与判定保持不变。

## 本轮补齐的证据

第二片已实现唯一固定分配，但真实 LAN 丢回复、首次结算竞争与进程中断证据不足。本片把断点放在实际 SQL COMMIT 前/后，以及 B 的许可/完整 outcome 持久化后，分别验证未提交回滚、已提交回执恢复和不完整证据继续占用。

`RecoveryLedger` 继承原转移/投影；只在 handle 中实际 COMMIT 两侧提供可选测试回调。正常 service 不配置回调。仅显式 `--test-control` 的本地私有控制文件能启用故障，不是网络请求或新协议管理权。控制绑定操作、policy、点位、模式、随机 token 和新 ready 文件。

ready marker 经 fsync 保存 point、请求/事件/回执摘要和测试 PID/token。服务 SIGKILL 只针对本矩阵创建且 PID/token 匹配的进程；B worker 的 kill 另核对 fault_driver 脚本路径、测试模式及 `/proc` start ticks，防止误杀无关或复用 PID。marker 是受信测试仪器，不称为独立密码学执行证明。

## 查询优先的正常恢复入口

`client.py recover` 只发送 **一次 STATUS**，核对原始签名回复和 request digest/nonce/deployment，再检查原结算回执的 policy/reservation/entitlement/payer/asset 绑定；不信任未签名 decoded view。

| 权威响应 | 客户端诊断 | 恢复行为 |
|---|---|---|
| SETTLED + 正确原回执 | RECOVERED | 保存原分配，不发新 SETTLE |
| RESERVED | HELD | 继续占用，不自动结算、退款或重算 |
| 已冻结但 UNRESERVED | UNFUNDED | 不自动预留或支付 |
| 不可用/拒绝/无效 | 失败 | 保留未知，不猜测付款或退款 |

这些诊断不是新账本/协议状态。未提交请求经确认回滚后，显式另发 SETTLE 才创建原政策下的一份分配；已提交但回执丢失时，只取回已保存的原权利。重复请求仍绑定同一唯一整笔 entitlement，不能重新支付/退款。

B 在完整 outcome fsync 后被终止，可只重传保存字节；只有 permit 没有 outcome 时，不能提交半成品或通过 clone 重新计算。缺少一端不能伪造 CLOSED_NO_PAY 或释放 cap。新执行 wrapper 的 environment 摘要同时绑定原 v2 环境及本片 wrapper 源码；正常 execute 不使用测试 hook，旧入口不改动。

## 真实双机结果

固定 **57 个源文件**部署到 B 全新目录，核对两端环境与 B 源码。A 放单一可信服务/账本和 A worker，同一故障域明确保留；B 为 Requester/B worker，分别管理运行目录和 HMAC 角色。资金、START、SUBMIT、SETTLE/STATUS 经实际 TCP，B→A 使用 LAN；SSH 只控制/部署/取证，严格主机密钥检查开启。无 VM、新安装/下载、Rust 编译或系统服务/防火墙变更，仅使用测试资产。

**14 个场景全部通过：**

| 场景 | 本轮证据 |
|---|---|
| 支付已 COMMIT 后真实关闭 TCP、不发回复 | B 失败且无成功回执报告，A 已保存分配 |
| 支付丢回复后查询及原请求重传 | 原 receipt digest 相同，paid=30/refund=70，不重复分配 |
| 全退款已 COMMIT 后关闭 TCP | B 失败，A 原全退款仍存在 |
| 全退款丢回复后查询/重传 | 原 receipt digest 相同，paid=0/refund=100，不重复退款 |
| 结算事件追加但 COMMIT 前暂停并 SIGKILL A 服务 | 热日志恢复后，事件/投影/签名 checkpoint 与请求前逐字节相同，临时事件不存在 |
| 查询未结算后显式再结算 | 先 HELD，再创建唯一一份分配 |
| COMMIT 后、回复前暂停并 SIGKILL A 服务 | 已提交事件和原分配完整保留 |
| A 重启后查询/重传 | 原回执摘要匹配故障 marker，不再付款 |
| 首次并发结算 | 两个 B 进程均 ready 且政策未结算后共用 barrier 放行；一 SETTLED、一 DUPLICATE，原回执相同 |
| B 完整 outcome fsync 后 SIGKILL、尚未提交 | A 仍 PENDING，占用原 cap |
| 已保存 outcome 恢复 | clone 重算拒绝；只重传原 outcome 后合法结算，无新调用 |
| B permit fsync 后、invoke 前 SIGKILL | 无 B invoke/outcome，提交及 clone 均拒绝，资金继续占用 |
| 权威服务真正停止时 recover | 客户端失败，不猜测退款/支付 |
| 服务重启后查询不完整任务 | HELD，完整 cap=100 保留 |

前两组丢失的是实际 TCP 回复，不是仅在客户端替换返回值。A 两次 SIGKILL 分别验证真实未提交事务回滚和已提交状态保留；未恢复已提交账本快照，不声称防止权威自身回滚。服务/worker 都是受控进程终止，不是断电或整机重启。

矩阵共 **7 个冻结任务/预留，14 个有效 START，13 份完整 outcome/调用意图，6 份唯一结算**。最后一个 B 仅有 permit，因此缺一份 invoke/outcome、保留 100。传输重试、模型回归和中间检查不累计成新的任务或计算。五份正常 OK 分配各付 30、退 70，一份完整 gas-trap 分配退 100，总 paid=150、refunded=450。初始 1000；最终 payer available=750、payee available=150、A worker available=0、active reserved=100，总量保持 1000。paid/refunded 是历史流量，不重复加到资产总量。

A 最终 **61 条事件**：GENESIS 1、FREEZE 7、RESERVE 7、START 16（含 clone 拒绝）、SUBMIT 13、SETTLE 12（含重复/PENDING）、STATUS 5。提交前被杀请求没有 committed SETTLE 事件；提交后的丢回复操作则保留原事件。B 保存 **28 份 client 原请求/签名回复**并核对权威事件，其中 **5 次成功 recover 都只有 STATUS 请求**。四个丢回复/服务被杀的结算请求没有成功 B 回执报告，原失败日志/marker 保留。

## 中间锚点与离线重放

保存 **9 份独立 export/checkpoint/reduced**：支付丢回复、退款丢回复、提交前基线、回滚后、提交后被杀尚未恢复、首次 race 放行前、已保存未提交 outcome、permit-only 保留及最终状态。

原 v2 `audit.py` 不导入活账本转移函数或执行 guest，分别从字节重建每个 checkpoint 的政策、许可/结果、comparison、唯一权利与余额。另进程对全部 9 份逐一运行 CLI，均与矩阵内投影一致。最终重建 **61 条事件、6 份结算、paid 150/refunded 450/active reserved 100**。提交前基线与回滚后各 25 条事件，导出与签名锚点相同；提交后故障的 committed event 则存在于对应导出。

**6 个篡改反例全部拒绝**：截断、改余额投影、改事件前项、错公钥 pin、错 checkpoint digest、改 comparison 投影。原证据不改动。auditor 共享对象/编码/密码学辅助，HMAC 认证依赖签名权威日志；不是独立密码实现或恶意 issuer 的安全证明。

## 回归、交付与维护

A/B 各 **16 项新增回归**通过，包括提交前/后故障、无 hook 正常分配、恢复只发 STATUS、HELD/UNFUNDED/不可用不自动资金操作、原签名 bytes 优先、nonce/权利错绑、真实 drop callback、禁止提交前伪装 reply loss、permit-only 不重算、保存 outcome 重传、回滚不延长 checkpoint、已结算与保留资金区分。`ResourceWarning` 作为错误检查。

新增 `make check-settlement-recovery` 纳入默认检查，合计 **260 项**。默认仅局部回归/模型，不连接 B；显式 dualhost 需要全新目录，失败保留现场，只清理本轮创建的进程。安装后再核对默认检查、清单、diff 和源码包；第二片及此前全部实验源码保持原样。

命令及正常/测试入口见 [README](../../experiments/aclt-settlement-recovery/README.md)。[机器记录](settlement-recovery-slice3-20261024.json)保存当前源码、原始证据摘要、checkpoint pins 和重放摘要。完整证据在本地 `<EVIDENCE_ROOT>/settlement-recovery-slice3-20261024/dualhost-run1/`，目录外保存 9 份 standalone 结果和另存 pins。实际 IP/用户/机器路径不入库；私钥、HMAC config、运行数据库/大体积证据不进入源码包，B 公共取证不包含 private 目录。

## 限制与后续

本切片的信任前提为诚实的 pinned 宿主/config/文件系统、角色/issuer 密钥与单一不回滚/不分叉权威。两台物理主机只是 DUALHOST-SSH-1 的有限接受假设，相同参考实现、操作者/LAN/供电构成共因。整机断电/重启、存储控制器一致性、路由级分区、TLS/DoS、attestation、生产密钥生命周期、failover 与任意恶意宿主均在本切片范围之外。合法旧 checkpoint 只证明旧时点；SHA 的覆盖范围是完整性，来源认证与新鲜性另需独立保存的 key/checkpoint pin。

本切片的资产限于预置整数测试资产与固定机械分配；真实支付适配器、正式终态×故障×资金来源矩阵、TRUSTED 与生产结算资格均不在本轮范围。未知资金可能继续锁定，紧急退款与管理覆盖入口未提供。OQ-10、ADR/G0/G2/P0-1B、B/Q 状态不变。

**下一步是第三项工作三切片统一收尾**：组合检查冻结预留、结果/唯一分配和故障恢复的共同边界，固定统一复现/只读复核及交接清单。本次完成的范围限于第三切片；整体收尾与正式协议验收仍待相应切片。
