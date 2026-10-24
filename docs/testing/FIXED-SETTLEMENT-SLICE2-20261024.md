# 第三项工作 · 切片 2：双端结果绑定与固定测试结算

日期：2026-10-24。状态：**本切片限定工程范围完成**。
基线 `146d83235e3ceee01487600e22f8877ef6da273b`，预检工作区干净。新增 [aclt-fixed-settlement](../../experiments/aclt-fixed-settlement/README.md) 独立 v2 实验；第一片资金预留、既有任务/RIR 等实验源码全部保持原字节，旧库不迁移。

## 本片冻结的规则

`aclt.exp.funding-policy@2` 在原资金字段之外冻结 comparison_rule，policy/funding-event/request/response/reservation/export/checkpoint 与哈希域明确使用 v2，旧 @1 对象不混用。固定费用、收款方、精确等价规则和分支在预留和 START 前确定，观察结果后不能改价、换收款人或选择付款/退款分支。

| 已保存证据 | 实验决定 | 支付/退款 |
|---|---|---|
| A/B 完整 outcome 精确一致且为 OK | MATCH_OK | 固定 success_fee 给 payee，cap-fee 退 payer |
| A/B 均完整，但不一致或相同非 OK Task outcome | CLOSED_NO_PAY | 0 支付，cap 全退 |
| 缺少一端、无效/半成品、HostFault 或未知 | PENDING | 不支付不退款，继续占用 |

比较覆盖 outcome kind、gas_used、OK 的原始输出字节和 ABORT 的 abort_code。comparison 引用两份原始 report 摘要和冻结等价规则，结算回执再绑定 comparison 摘要。Task/工件/输入/Profile/上限通过原任务绑定和 funded permit 的完整 binding 摘要关联，不能拿另一任务的“相等”证据付款。

该“不一致不付款”是预先声明的有限机械测试政策，不判断故障责任、不罚没、不冒充正式 FAILED/UNRESOLVED，也不关闭完整终态×故障×资金来源矩阵。现有 ACCEPT、单端 OK 或超时不能作为结算依据；不新增 `REEXEC_EXACT` 方法或自动产生 TRUSTED。

## 资金先于本入口执行

A genesis 固定 A/B 两个不同 actor 和实际 boot/source/Profile environment 摘要，分别配置独立测试 HMAC enrollment。A 角色密钥和 issuer RSA 私钥留在 A；B 只获得自己的角色与 Requester 凭据。角色引用/环境绑定依赖诚实 pinned 部署，不是远程证明；两端运行同一 Python 参考实现，不称为独立实现验证或统计独立。

新 `executor.py` 执行前验证 caller expected task ID、原始 artifact/input/policy 和当前环境，持久化排他 intent，再经 TCP START。A 必须已为该 policy 预留完整 cap，且 `(policy,role)` 一次性槽位未用、未结算；将槽位消费和 signed funded-start 许可及事件同事务提交。许可绑定 deployment/reservation/policy/task/role/actor/environment/完整 binding 摘要。

工作端验证许可后先 fsync permit 与 invoke 意图，再调用原 Python RIR。新 nonce、clone 状态目录不能重开已消费槽位。START 回复丢失或中断可以消耗资格而没有 outcome；不续算、不退款或补发执行许可。INVOKE 是调用意图，不是物理执行或恶意宿主不可旁路证明。

完整 outcome 只落盘一次，绑定原许可、task/role/environment，随后由对应角色 HMAC 提交。A 检查结构、资源、原始 outcome digest 和已消费 funded start，封存各一份报告；原字节重传幂等，冲突不能覆盖。A 不再次执行来证明恶意 worker 的算术结果。独立 `submit` 模式只重传保存字节，不重新计算或按当前 boot 重新授权执行。

这补齐的是**新实验入口**的资金先于启动边界，不是正式 active Lease/ExecutionCapability；旧诊断/授权入口尚不咨询本资金账本。实验没有其他执行 fallback。

## 唯一权利、支付与退款

SETTLE 只接受 policy_id，并校验冻结 payer。服务端从自己保存的两端报告派生 comparison；调用方不能提供费用、结果分支或自选权利 ID。

`ACLt/Experiment/FixedEntitlement/1` 对 `[authority_id,reservation_id,policy_id]` 派生一个覆盖**整个分配**的实验权利。同一事务中生成 comparison、唯一权利及签名 fixed-settlement 回执，清除 active reserved，给 payee 记 paid、给 payer 记 refunded，并追加事件。没有分开的 PAY/REFUND/CANCEL 入口争用同一余额。

回执绑定 task、policy、reservation、payer/payee/asset、权利 ID、comparison digest、决定和实际 paid/refunded。提交前签名/事件失败整体回滚；提交后回复失败保留原分配，STATUS/重复 SETTLE 返回原回执。后续 RESERVE 只返回旧预留证明，不重新扣款。

精确整数满足：Σavailable+Σactive reserved=初始总量；active reserved 等于未结算预留之和；每份结算 paid+refunded=原 cap；每个预留至多一份不可变分配。paid/refunded 是已计入 available 的历史流量，不再加进总资产一次。本轮没有真实付款、外部适配器或舍入。

## 本轮真实双机矩阵

新目录固定部署 **48 个源文件**，分别核对 B 源码清单及环境。A 同机运行权威账本/临时服务和 A reference worker，B 为 Requester 和 B reference worker；两端执行同一冻结工件/输入，保留各自独立持久状态。FREEZE/RESERVE/START/SUBMIT/SETTLE/STATUS 使用真实 TCP，B→A 经 LAN；A worker 与服务同一故障域明确保留。SSH 只部署/控制/取证，严格主机密钥检查保持开启，无 VM、安装、下载、Rust 重编译或系统服务/防火墙变更。

**12 个场景通过：**

| 场景 | 本轮结果 |
|---|---|
| 同一冻结任务，预留后双端各一次执行 | A/B 正常 outcome 原始字节精确一致，gas=9126 |
| 双端 OK 固定结算 | 支付 30，退款 70 |
| 重复请求/新 nonce | 原权利、原回执、不重复记账 |
| 两个 B 进程并发重传已结算请求 | 均取原分配，无额外付款 |
| 保存的 B outcome 重传 | 原记录，不重复计算 |
| 非 payer 发起结算 | DENIED |
| 双端完整 gas 陷阱 | 两端 gas_limit=8192，CLOSED_NO_PAY，全退 100 |
| 退款后的重复结算 | 原回执，无再次退款 |
| 只有 B 完整结果 | PENDING，完整 cap=100 继续预留 |
| 未预留就启动 B | 拒绝，无 guest invocation |
| 错误 expected task ID | 调用前拒绝，无新 invocation |
| A 服务进程重启后查询/重传 | 返回原结算回执 |

矩阵共 4 份冻结政策、3 份预留、5 份有效 START 和完整 outcome、2 份唯一结算，另有未预留 START 被拒绝。A/B 各自保留的 invoke/outcome 共 **5 份**，不把局部回归的模型/执行检查或传输重试累计为新任务。两端 gas 陷阱是完整 Task 证据，不能将 HostFault 当成同类全退。

初始 1000 个测试单位；最终 payer available=870、payee available=30、A witness available=0、active reserved=100，合计 1000。历史 paid=30、refunded=170（70+100），另一个未完整任务仍锁 100；这些流量不能再加入资产总量。

A **30 条事件**：GENESIS 1、FREEZE 4、RESERVE 3、START 6（含拒绝）、SUBMIT 6（含原包重传）、SETTLE 9（含重复、PENDING 和拒绝）、STATUS 1。保存 **17 份 B client 原请求/签名回复**并核对其与权威事件一致；另保存两端启动许可、调用意图、完整 outcome 和比较/结算原字节。

**6 个篡改反例全部拒绝**：截断事件、修改余额投影、修改事件前项、错 key pin、错 checkpoint digest、修改 comparison 投影。仅改副本，原始记录保留。

独立 `audit.py` 不导入 Ledger 或运行 guest，从原始事件重建先资金后启动/结果的顺序、双方报告、精确 comparison、唯一权利及全部余额，与 signed checkpoint 对照。另进程 CLI 得到相同的 **30 条事件、2 份结算、paid 30/refunded 170/active reserved 100**。它共享对象/codec/密码学辅助，HMAC 认证依赖权威签名日志，不称为独立密码实现或恶意 issuer 证明。

## 回归与交付

A/B 各 **26 项新增回归**通过，覆盖 OK/完整非 OK/不一致/缺失一端、唯一权利及首次并发结算、错 payer/不可自选金额和分支、HostFault 拒绝、资金前置、启动一次性与角色隔离、任务/环境/许可/结果摘要错绑、资源/部分输出、原报告幂等/冲突、签名/事件失败回滚、提交后丢回复、重启原分配、不重复预留、真实 reference 执行后仅重传、零/全费、2^63-1 整数分配、START 丢回复无额外计算和离线反例。`ResourceWarning` 作为错误检查。

新增 `make check-fixed-settlement` 纳入默认检查，合计 **244 项**。默认不联网，显式双机矩阵仅全新目录；安装后再次核对默认检查、清单、diff 和源码包。先前所有实验源码/历史记录保留，不自动运行旧实验或迁移状态。

[机器记录](fixed-settlement-slice2-20261024.json)包含当前源码锁、摘要和结果。本地 `<EVIDENCE_ROOT>/fixed-settlement-slice2-20261024/dualhost-run1/` 保存原始 A/B 证据、导出/分离 checkpoint、公钥与日志；目录外有 standalone-audit 和独立保存 pins。实际 IP、用户名和机器绝对路径不入库。私钥、HMAC config、数据库和大体积运行目录不入源码包；公开取证不包含 private 目录。

## 保留边界与第三切片

诚实 pinned workers/config/宿主/文件系统、A 密钥/enrollment、单一不回滚/不分叉权威仍是接受假设。合法旧锚点只证明旧时点，不能发现更新或防止 issuer 回滚/分叉；公开 SHA 不是认证根，key/checkpoint pin 需独立保存。两个物理主机仍有共同操作者、软件/LAN/供电等共因。没有任意恶意 worker 防护、独立执行引擎验证、TLS/DoS、生产身份/密钥生命周期、failover、真实断电或真实支付。

本片进程重启只验证保存分配可查询；回复签名失败/事务故障和首次结算竞争目前是局部回归，未冒充真实 LAN 丢回复/整机故障证据。**下一切片**扩展真实双机故障与账务重放：结算 COMMIT 后实际丢回复、首次并发竞争、结算前后受控中断、恢复查询原权利、不完整状态保持占用和原始日志一致性。OQ-10、正式对象/终态/结算矩阵、G0/G2/P0-1B、ADR-0006、B/Q 与生产资格保持原状态。
