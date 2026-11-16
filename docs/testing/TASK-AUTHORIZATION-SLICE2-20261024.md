# 第二项工作 · 切片 2：实验授权与启动意图持久化

日期：2026-10-24。状态：**本切片限定工程范围完成**：实验授权与启动意图持久化在 A/B 两台物理主机上通过 16 个场景（覆盖本地重复、新状态目录 clone、伪造签名、过期/epoch 替换、并发启动与受控终止），A、B 各 24 项回归与默认 `make check` 165 项通过（见「真实双机矩阵」）。
基线 `9ce507c44e89f6d84a770ab38f929f2b8b38464a`，预检工作区干净。此前 RIR 三片、总收尾与 ExperimentalTaskCommitment 全部保留，源文件保持未改。

## 本轮交付和权威边界

新增 [aclt-task-authorization](../../experiments/aclt-task-authorization/README.md)：闭合字段的 ExperimentalExecutionGrant、已有 OpenSSL 签名适配、单一实验消费账本、真实 LAN CHECK/CONSUME、调度/启动双检查、独占持久启动意图、正常 CLI、显式故障驱动与可复用双机矩阵。

A 上的实验 issuer/SQLite 是本轮唯一授权状态来源；B 上的 Dispatch 和 Python RIR 启动入口分别检查同一个已签名 grant。二者不创建第二套 scope 或覆盖执行元组。
这不是正式 active Lease / ExecutionCapability：A 的可信授权组件是实现假设，不是新协议 Principal、验证裁决者或生产调度器。

grant 绑定 authority deployment、随机 grant nonce、实验任务 ID、Provider/unit 引用、environment/scope/execution tuple 摘要、epoch 和起止时间。scope 从冻结承诺派生，绑定工件、输入、Profile、上限和结果等价规则；不能由 Dispatch 本地补写。
B 环境摘要覆盖实际 boot、内核/Python、Profile 及 wrapper 源文件，必须与受信部署配置和 grant 一致。它是环境绑定，不是远程证明。

使用专用实验 schema/哈希域；签名对象为 canonical CBOR payload，签名域前缀、字段与运行命令详见实验 README。Provider 请求使用独立测试 HMAC 凭据，回复由 A 测试 RSA-2048/SHA-256 密钥签名并绑定 request digest/nonce/op/grant/deployment。
私钥不发送到 B；HMAC enrollment 配置通过受信 SSH 放在 B 私有目录，不进入收集的 B 公共证据或源码包。Requester/Provider 的正式身份签署、密钥生命周期与生产 enrollment 未实现。

## 启动顺序

1. Dispatch 验证 expected task ID、原始工件/输入、grant 签名和本地 provider/unit/environment/scope/tuple，向 A 发 CHECK。CHECK 只确认当前可用，不消费执行槽位。
2. 独立启动入口重新验证同一 grant 和实际绑定；旧 CHECK 不能替代 CONSUME，过期/epoch 变化在启动时再次由 A 判定。
3. B 先 `O_EXCL → file fsync → directory fsync` 保存 task/unit 对应的启动意图，再发一个新 nonce 的 CONSUME。
4. A `BEGIN IMMEDIATE` 检查当前 active grant、Provider/tuple 与 A 时钟，并以 `synchronous=FULL` 将 ISSUED 原子改为 CONSUMED；COMMIT 后才签回复。
5. B 校验并持久化本次消费许可，再保存 invocation-intent，随后才执行绑定的候选 RIR。输出单独存储，outcome 附带 grant/tuple/permit/输出摘要。

文件名锁定 task/unit，不因新 epoch 或新 grant nonce 改变。A 只允许未消费 grant 以更高 epoch 替换；已消费槽位不因新目录、重启或增加 epoch 重新可用。
这是每个冻结实验 task/unit 的一次启动权，不是抽样资格、独立贡献或跨不同 task ID 的统计防重；修改任务 nonce 不能因此获得验证真理权重。

本地状态必须是受信持久目录，A 账本不得回滚或分叉。丢失消费回复、签名失败、持久化失败或不确定中断可以消耗槽位但不计算；不自动退款、清理标记或恢复计算。invoke 文件只证明调用意图，不证明物理指令已经运行。

## 真实双机矩阵

沿用 DUALHOST-SSH-1 的有限物理独立假设：A issuer/账本，B Dispatch/启动器/本地状态；SSH 部署/取证，实际 CHECK 和 CONSUME 经 B→A LAN TCP。没有修改系统服务、SSH 主机密钥检查、防火墙或全局软件。

本轮 **16 个场景全部通过**：

| 场景组 | 本轮结果 |
|---|---|
| 正常授权执行 | B 完成原统计行，gas=9126，保留签名许可与输出 |
| 本地重复、新状态目录 clone、A 授权服务进程重启后重放 | 拒绝，无新增消费或计算 |
| 伪造签名、错误输入/unit/本地 environment | 执行前拒绝 |
| 已过期、Dispatch 后过期、Dispatch 后 epoch 被替换 | 拒绝；旧 CHECK 不足以启动 |
| 两个独立 B 进程并发启动 | 一个 Task outcome、一个拒绝；唯一 CONSUME |
| A 已提交 CONSUME 后主动丢失回复 | B 为 HostFault，无 invocation；新状态 clone 仍被拒绝 |
| fsynced intent 后受控 SIGKILL | 无 CONSUME/guest；原状态不自动恢复 |
| fsynced permit 后受控 SIGKILL | CONSUME 保留，无 guest；原状态及新状态 clone 均拒绝 |
| Dispatch 后真实停止 A 服务 | B 启动 HostFault，无消费/guest |

16 个场景不是 16 次完成的计算；部分共享同一正常任务检查重放。共 13 个冻结测试任务、14 个 ISSUE（含未消费 grant 的一次 epoch 替换）、4 个唯一消费槽位、2 个完成的 guest outcome（正常执行和并发唯一赢家）。另两次消费对应丢回复和消费后终止，保守损失活性。

本轮保存并核对 13 份 intent、3 份持久签名消费许可、2 份 invocation-intent、2 份完整 outcome。补充检查用独立保存的公开 issuer key 验证许可签名和 request digest/nonce/operation/grant 关联，再核对 intent/输出摘要与账本消费计数；它是有限文件关联审计，不是下一切片的完整事件重放检查器。

A、B 各 **24 项回归**通过，包括 scope/元组错绑、同状态/clone 并发、旧回复替换、坏凭据、过期、旧 epoch、文件同步失败、许可落盘失败和消费后禁止重发。SQLite 连接关闭警告已修正并按 `ResourceWarning` 为错误重跑；早期日志保留。默认 `make check` 共 **165 项**，安装后再次核对；清单、diff 与交付包一并校验。

机器记录见 [本轮 JSON](task-authorization-slice2-20261024.json)。本地 `<EVIDENCE_ROOT>/task-authorization-slice2-20261024/` 保留源码锁、测试日志和新双机目录；`dualhost-run1/` 中 A 保存公开账本/公钥，B 保存取回的任务、bundle、启动文件和报告。运行私密材料只在独立 private 目录；实际 IP、用户和绝对路径不入库。SIGKILL 是实验进程终止，不是断电；服务重启不证明 A 自身抗回滚。

## 复现与依赖

`make check-task-authorization` 运行局部回归，不连接 B。它与默认 `make check` 现在需要已有系统 OpenSSL CLI；没有新增下载、第三方 Python/Cargo 包或软件安装。
双机集成显式运行实验目录的 `dualhost.py --peer USER@B_IP --a-host A_LAN_IP --remote-root /absolute/new/B/path --output /absolute/new/A/path`，所有本地/远端根目录必须全新；工具仅启动和清理本轮服务/测试进程，所有日志保留。
第一项保存的 Rust/Wasm fixture 在现有 Python 参考入口执行；本轮没有重编译 Rust，也未给独立 native Rust 入口加授权包装。

## 尚未实现与下一切片

保证依赖诚实的 pinned worker/config、文件系统语义、issuer 私钥/enrollment、A 时钟与单一不回滚/不分叉的账本；任意恶意宿主仍可绕过整个实验程序。旧 execute-probe 的定位是显式无授权诊断，本入口不以其作为 fallback。
网络无 TLS/加密/DoS 防护，生产准入、注册/撤销/轮换、权限最小化、环境 attestation、故障转移和真实断电一致性仍未验证。

正式 ComputeReceipt、Lease、ExecutionCapability、EventRecord、验证判决及结算仍未实现；ADR-0006 PROPOSED、G0/G2/P0-1B、B/Q 与生产资格状态不变。

**下一切片：完整可重放事件链。** 串起承诺、授权、意图、消费许可、outcome、完整提交包和接纳回执，规定因果/幂等/恢复规则，并用独立离线 reducer 重建状态。重放完整已保存提交包的用途限于重建已保存状态，不重算任务；本轮的局部标记和 SQLite op 行不构成该契约的完成。
