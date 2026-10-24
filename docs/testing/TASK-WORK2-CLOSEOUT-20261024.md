# 第二项工作收尾：最小任务承诺、授权与可重放日志

日期：2026-10-24。工程跟踪标识：`TASK-WORK2`。
**结论：三个切片组成的第二项工程工作，在实验冻结绑定、启动授权和完整提交/接纳/ACK 重放的限定范围内完成。**
这不是新的 SemanticStatus/VersionDisposition；ADR-0006 仍 PROPOSED，G0/G2/P0-1B、B/Q 与生产资格不改变。

安装前基线 `fe75389784de0e29ce401857bebefdd8ad0065eb`，预检工作区干净。三个任务实验及既有 RIR 实验源文件全部保留原字节；本次新增组合入口、五项工具回归、统一维护/交接文档与证据，不迁移旧库、不提交或推送。

## 已验收的三片和组合链

| 范围 | 本次完成内容 | 工程状态 |
|---|---|---|
| 切片 1 | canonical 实验承诺、expected ID、工件/输入/Profile/显式上限/等价规则冻结；替换错绑拒绝 | 完成 |
| 切片 2 | 签名实验 grant、调度/启动双检查、真实 LAN CHECK/CONSUME、启动意图和单一消费账本 | 完成 |
| 切片 3 | 因果日志、完整不可变提交包、原回执幂等、ACCEPT/ACK 分离、独立离线 reducer | 完成 |
| 统一收尾 | 显式双机入口、当前完整源码锁、跨片字节/规则连续性、只读复核和恢复/交接说明 | 完成 |

第三片本身贯通注册→授权→持久启动→outcome→封存提交→接纳→ACK。第二片和第三片保留为独立回归部署，各有不同 task nonce、grant、密钥和账本；收尾不假装把旧库直接升级成一个正式协议实现。

统一核对正常样例的 **RIR 工件原始字节/摘要、输入原始字节/引用、Profile、执行上限和结果等价规则**，三片一致。不同任务 nonce 使 experimental_task_id 不同，这是预期绑定；不要求不同部署共享 task ID 或回执。固定样例沿用第一项已保存的 stats-int-v1 Rust/Wasm fixture 和 Python 参考入口，本次没有重新编译 Rust，也未验证独立 native Rust 授权/重放入口。

## 正式对象与实验替身

| 本轮可执行对象 | 与正式规范的关系 |
|---|---|
| ExperimentalTaskCommitment / experimental_task_id | 实验冻结承诺；不是 ComputeReceipt / ReceiptID，Requester 引用不证明身份控制 |
| ExperimentalExecutionGrant / 单一消费槽位 | 实验 issuer 授权；不是正式 active Lease / ExecutionCapability 或生产 enrollment |
| causal-event / 哈希流 / signed checkpoint | 实验事件/锚点；不是完整正式 EventRecord 契约或权威抗回滚系统 |
| submission / acceptance-receipt / ACK | 完整实验结果包的保存与传输确认；不判定运算正确性、不产生 TRUSTED 或结算 |
| 候选 RIR / outcome / gas | 复用原候选执行子集与固定 Profile；不是完整 RIR/RPR conformance |

正式规范仍是语义权威；上述实验源码与新脚本不定义协议语义。A 可信 issuer/账本是有限部署假设，不新增协议 Principal 或中心验证裁判。task/unit 启动槽位不是抽样资格、身份独立或统计贡献。

## 本轮重新取证

统一入口在全新 A/B 目录执行，源码锁覆盖 **53 个文件**（三个任务实验、统计依赖、组合脚本和工具回归）。分别核对授权和重放部署的精确源文件清单。A 临时服务/账本同一故障域，B 独立持久 worker；CHECK/CONSUME/SUBMIT 走真实 LAN TCP，SSH 仅部署、控制和取证。严格主机密钥检查保持开启，无 VM、系统服务/防火墙变更、新软件安装或依赖下载。

- 两端各 24 条承诺探针记录，共 **48 条**，输入/上限变化保持正确身份边界，错误绑定明确拒绝。探针是无授权诊断入口，不能作为 worker fallback。
- 授权矩阵 **16 个场景**通过，含重复/clone/并发、签名/输入/unit/environment 错绑、过期/epoch 变化、消费丢回复、INTENT/PERMIT 后 SIGKILL 和真实服务不可用。只有 2 份完成的 guest outcome，不把场景数当任务数。
- 提交/重放矩阵 **12 个场景**通过，含同包及并发重传、服务重启原回执、冲突保留原包、ACCEPT 丢回复及恢复、PREPARED 后终止再重传、不完整状态禁止续算、坏副本拒绝后原包接纳。
- 第三片 **7 个篡改反例**全部拒绝：截断、缺失工作证明、改附件、改投影、工作流分叉、错 anchor、错 key。另对统一只读 CLI 实测错误公钥与错误最终 checkpoint，均非零拒绝且未生成成功报告。
- 三片局部回归 A/B 各 **69 项**（19+24+26）。新增五项组合工具回归覆盖证据改动、源码漂移、符号链接、路径逃逸和已有报告保护，纳入默认 `make check`，合计 **196 项**。安装后再次运行默认检查、清单、diff 与源码包核验。

上述矩阵不合并成 28 次计算；承诺探针包含诊断 Task outcome/陷阱，授权与重放也有共享任务/传输重试。第三片共 6 个冻结任务、5 个唯一消费/OUTCOME、4 个接纳并 ACK；1 个停在 OUTCOME，另 1 个停在未消费 INTENT。

第三片最终独立重建 **34 条 A 事件、55 条 B 事件、4 个接纳/5 个消费**。中间 checkpoint 正确呈现 A 已接纳、B 未 ACK。完整包重传返回首次保存的同一回执字节，不新消费或计算；不完整 INTENT/PERMIT/OUTCOME 不自动续算。INVOKE 是调用意图，不是物理执行证明。

统一脚本完成运行后，又在另一个进程以独立保存的 key/checkpoint pin 调用 `verify`，结果与本次 suite 摘要一致；此阶段没有网络、guest 或编译。承诺比较器重新绑定实际字节，第三片 reducer 在独立进程检查附件、序号/前项、签名许可/回执、工作阶段、因果闭包和签名投影。第二片只核对保存矩阵断言/证据哈希，不冒充旧操作行有独立状态 reducer；共享 codec/密码学原语也不是独立密码实现。

## 统一复现与交接

[维护入口](TASK-WORK2-MAINTENANCE.md)提供两条命令：

```sh
make test-task-work2 \
  TASK_WORK2_PEER=USER@B_IP TASK_WORK2_A_HOST=A_LAN_IP \
  TASK_WORK2_REMOTE_ROOT=/absolute/new/B/suite \
  TASK_WORK2_OUTPUT=/absolute/new/A/evidence

python3 -B scripts/task-work2.py verify \
  --evidence /saved/suite --pins /independently/retained-pins.json \
  --report /new/verification.json
```

第一条是显式跨机执行；第二条只是保存证据的只读复核。输出目录/报告必须新建，复核报告位于原证据目录外；当前源码漂移时拒绝。默认检查不联网、不产生新的双机通过记录。

[机器记录](task-work2-closeout-20261024.json)保存本轮组合摘要、源码 pin、checkpoint/key pin 和证据摘要。本地 `<EVIDENCE_ROOT>/task-work2-closeout-20261024/dualhost-run1/` 保存各片原始记录、部署锁、环境/命令日志、公共文件清单和中间/最终锚点；目录外 `standalone-verification.json` 保存另进程复核。此前切片原始报告与失败证据全部保留，不重复累加为本轮结果。

私钥/HMAC enrollment 放独立 private 目录，不入公共清单或源码包；不能把完整运行目录直接公开。入库记录去除实际 IP、用户名和机器绝对路径。公开 SHA 清单只做一致性核对，不是来源认证；key/checkpoint pin 需独立留存。合法旧锚点只证明旧时点，不能发现更新或防止 issuer 回滚/分叉。

## 剩余边界与下一项

保证依赖诚实 pinned worker/config/本地文件系统、A 私钥/时钟、可信 enrollment 和单一不回滚/不分叉账本。任意恶意宿主可以旁路实验程序。无 TLS/DoS 防护、生产密钥注册/撤销/轮换、外部 checkpoint 见证、failover 或真实断电验证；SIGKILL/服务重启只证明对应进程故障范围。两台物理主机仍有相同操作者、LAN、软件/供电等共因，不推导统计独立或 B/Q。

第二项不继续扩大规格范围。**下一项建议：同一冻结任务的双端 outcome 与精确比较证据绑定。** 先固定输入、工件、Profile/上限，分别取得双端 outcome，保存可重放比较记录和错绑反例；明确实验身份与正式对象/签署的迁移缺口。相等只支持本次比较，不新增 `REEXEC_EXACT` 方法，不自动产生 TRUSTED，不顺带引入结算。正式对象、完整 validator/conformance、B/Q、经济和生产资格继续独立跟踪。

历史切片：[承诺](TASK-COMMITMENT-SLICE1-20261023.md)、[授权](TASK-AUTHORIZATION-SLICE2-20261024.md)、[因果重放](TASK-REPLAY-SLICE3-20261024.md)。
