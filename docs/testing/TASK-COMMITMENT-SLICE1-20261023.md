# 第二项工作 · 切片 1：最小任务承诺与身份绑定

日期：2026-10-23。状态：**本切片候选工程范围完成**。
安装前核对基线 `233d5fac514340ca231cf76e6d39cc8af80ed227`，主仓库工作区干净；第一项三切片及总收尾保持原样。环境沿用 ENV-1、DUALHOST-SSH-1。

## 已交付

新增 [aclt-task-commitment](../../experiments/aclt-task-commitment/README.md)：候选 schema、受限 canonical CBOR 编解码器、冻结承诺/身份函数、执行前绑定检查、CLI、双机探针/比较工具和回归 golden。

对象为 `ExperimentalTaskCommitment`（`aclt.exp.task-commitment@1`），身份字段为 `experimental_task_id`。这些都是实验对象，不叫正式 `ComputeReceipt`、`ReceiptID`、`Lease`、`ExecutionCapability` 或 `EventRecord`。
旧外置账本中的 `receipt_id` 是包含结果摘要的实验接纳回执；它不是执行前冻结的任务承诺，本轮未改名或复用。

候选承诺闭合绑定 schema/encoding/context、任务族、请求者引用、nonce、RIR 版本/摘要/入口、一个输入的实验 bytes 类型/摘要/长度、执行 Profile ID/摘要、四个显式上限和结果等价规则。
请求者引用仅是 32 字节不透明引用，nonce 由调用方给定，两者不证明身份、唯一性、控制关系或授权。
CBOR 是权威内容；JSON schema/view 明确标注哪些字段是 hex 视图对应的 bstr，不猜测任意字符串类型。未知字段、未知版本/Profile/等价规则、错误类型/位宽、非最短编码、重复/乱序键和尾随字节均拒绝。

任务身份：

```text
SHA256(u8(len(tag)) || ASCII(tag) || canonical_commitment_cbor)
tag = ACLt/Experiment/TaskCommitment/1
```

输入摘要为 `SHA256(raw input bytes)`，不冒充正式 LogicalObject identity。RIR 沿用第一项候选工件域；Profile 使用单独的 `ACLt/Experiment/ExecutionProfile/1` 域。
候选 Profile 固定有限机器/ABI/effects/结果比较与源码 pin；支持 gas 8192..50000000、output 0..4800000、memory=2 页、call depth 1..64。它们是本实验支持界限，不修改协议全局默认值。

## 验收行为

1. 相同语义内容和不同 map 插入顺序产生相同字节与 ID；冻结字节不随调用方之后修改列表/字典而变化。
2. 改输入或可支持的上限会改变任务 ID，保留原 rir_digest；改 RIR 工件同时改变两者。不支持的内存/其他上限明确拒绝。
3. 请求者引用或 nonce 变化也改变 ID。输出结果不进入承诺，不形成“执行完才决定任务身份”的循环。
4. `bind()` 必须接收调用方原先保存的 expected task ID；一个替换对象即使自洽重算 ID，也不能替代原承诺。
5. 工件、输入、ID、Profile 或上下文错绑在任何 guest 指令执行前拒绝。执行探针只消费已冻结上限，CLI 不提供覆盖它们的参数。
6. 重用既有 stats-int-v1 候选工件执行；样例 chunk=2、`[3,-1,5,8]` 得到原二进制统计行及 gas=9126。减少 gas/output 上限分别得到相应 Task trap，非 OK 不保留部分输出。

输入是显式引用的原始 bytes，本轮不将统计输入语义检查提前到创建期；内容格式错误可在绑定成功后触发原程序 ABORT。

## 本轮实测

A/B 使用同一摘要锁定源码，各自在新目录运行探针。每端 24 条记录：18 个拒绝、5 个 Task outcome、1 个编码顺序一致性检查；共 48 条，CBOR、输入、候选工件、身份、视图和执行记录逐字节一致。五个身份变化向量单独保存，不当成额外 Task 计数。
每端的 5 个 outcome 为正常/深度 1 执行 OK 各一，以及 gas、output、unreachable 各一。

- A 本地、B 远端各 19 项新回归通过，覆盖手写 CBOR golden、截断、非规范编码、身份变化、闭合字段、错绑前不执行、CLI 状态与拒绝覆盖、主机失败分类。
- CLI 另验证保存承诺 → 新进程从文件加载 → 使用已保存 ID 绑定并执行，身份和 outcome 与探针相同。
- 主仓库 `make check` 共 141 项，安装时重新核对；同时检查清单、diff 和更新包。
- 双机采用同一 Python 编解码实现，不声称跨实现独立。使用第一项保存的 Rust/Wasm fixture，经当前受限 decoder 验证与规范化后执行；本轮没有运行 Rust 编译器或声称新增原生 Rust 承诺 codec。

实验任务 ID：`5a0765d5b4c40a147b74525ead5b80fba0fa2d89e1b3238a13b5f75f589ea319`。
RIR 摘要仍为 `7077c1ac21677dc89040c65a95a3008c43b0292c9e3763a67a4e44055c8a2879`。
版本、源文件、保留字节摘要、身份变化与具体计数见 [机器记录](task-commitment-slice1-20261023.json)。

`make test-task-commitment TASK_COMMITMENT_OUTPUT=/new/host-run` 在每台物理机分别生成证据，再以实验目录的 `compare.py` 核对。默认 `make check` 只运行局部回归，不自动联网、安装或运行 VM。
实际地址、用户名和路径仅留在操作者本地 `<EVIDENCE_ROOT>/task-commitment-slice1-20261023/`。远端使用新建私有实验目录，保留之前所有产物。开发时负向向量曾错误假定顶层 map 字段数量，探针按失败保留；随后按实际字段数构造非最短长度向量，拒绝要求未改变。

## 保留边界与下一切片

调用方须独立保留期望任务 ID；本轮没有签名登记或持久化注册来保证它。哈希/源文件 pin 仅在可信部署下检查内容一致性，不认证恶意宿主或抗回滚。
A/B 物理独立是接受的有限实验假设，不构成身份/统计独立证明；SSH 仅部署和取证，不是任务协议。

`execute-probe` 明确记录 `explicit-binding-probe-without-authorization`。它不是部署 worker 的准入入口，允许绑定测试不等于已实现授权，更不保证同一任务只执行一次。普通文件写出也不等于已完成崩溃一致的登记日志。

**下一切片接入实验授权和 RIR 启动边界**：把本候选承诺 ID 与执行单元、Provider、epoch、环境/scope 绑定；同一授权在调度入口和执行器启动处检查，启动意图持久化后才能执行，再覆盖伪造、换绑、过期和重复启动。之后第三切片才做完整事件链与离线重放。
正式 Receipt 的完整字段、签名/登记、Lease/capability、EventRecord、验证判决和结算均未实现；ADR/Gate、B/Q 和生产资格状态不变。
