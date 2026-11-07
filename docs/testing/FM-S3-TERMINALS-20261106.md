# FM-S3 候选执行闭合、可耗尽预算与 RPR 入口绑定

2026-11-06，基线 main `9f915c3`，分支 `feat/fm-s3-terminals-20261106`。本切片属于推进列表第二项"补齐候选执行与终态"，在 [Task trap 切片](FM-S3-TASK-TRAP-20261106.md)之后补齐另外三块：

- `FAILED` 所需的执行闭合；
- `FUNDING_EXHAUSTED` 所需的可耗尽预算；
- 绑定到可验证 RPR 入口的启动记录。

精确字段见[候选合约](../../schemas/formal-migration/audit-terminals.md)。范围限于 [ADR-0008](../05-decisions/ADR-0008-fm-s3-interface-decisions.md) 的首轮测试路线，不是正式准入。

## 组成与来源

执行闭合部分来自同日双机运行时所用的源码，原样纳入：

- **纳入方式**：`s3_closure.py`、`fm-s2-client.py` 与该运行的源码清单逐字节一致。`s3_authority.py`、`s2_worker.py`、`fm-s3-dualhost.py` 以该运行的版本为底，之后叠加了本切片的改动。
- **运行身份**：该运行的源码清单 SHA-256 为 `f9eb469d…c9d06d`，公开归档 SHA-256 为 `acbbc8b1…255643`，genesis 为 `47a1de71…5d8c0d`。
- **运行结果**：6 个场景通过，9 个事件，链头 `8e0d4a4c…`，状态摘要 `6f3effe0…`，测试账本 68 单位全额退回。
- **归档位置**：归档保存在维护者本地证据目录，不在仓库内。

本切片新增或修改的内容：

| 部分 | 内容 |
|---|---|
| RPR 入口 | `S3_ENTRY` 携带由冻结 Receipt 推出的入口描述，权威逐字节核对；worker 只从该描述生成运行时参数。原自述 `S3_START` 在该合约下被拒绝 |
| 启动状态 | 权威投影 `NOT_CONSUMED`、`AUTHORIZATION_CONSUMED`、`EXECUTION_STARTED`，求值时将"已消费但无入口"判为 `START_UNKNOWN`，并转为 `VERIFICATION_INVALIDATING` |
| 执行闭合 | 沿用观察方签名的 `S3_CLOSE_EXECUTION`；闭合所需的执行方启动记录改由已核验入口提供。执行方自签的 HostFault 不构成闭合 |
| 可耗尽预算 | 首次激活无法从有限预付测试余额中冻结 Receipt 额度时，权威记录资金边界事件，之后的证据不予接纳。求值复用 `admission.resolve_boundary`，按权威日志的因果链与期限观察比较先后 |

## 本地验证

- **回归**：`make check` 共 23 组、463 项 unittest 通过，其中 `check-fm-s3-terminals` 新增 14 项，覆盖入口字段篡改、旧合约拒收入口、启动未知、自签不闭合、伪造观察方、闭合前置条件、撤销优先、资金边界的重试与阻断、边界先于期限、边界引用错位与缺失，以及 worker 在进程内调用权威时的参数推导、物理故障闭合和两种中断阶段。
- **旧证据重放**：三份留存公开快照用合并后的代码重放，链头与状态摘要都和原摘要一致：
  - S3 收尾：39 个事件，`d72ea7fb…`；
  - Task trap：39 个事件，`993aaf1b…`；
  - 执行闭合：9 个事件，`8e0d4a4c…`。
- **旧合约字节**：仅 OK 与 Task trap 两种合约的字节由回归固定，与 main 一致。

## 双机验收

**后续实测通过。** 组合矩阵已在两套独立测试账本上通过，见 [本轮双机结果](FM-S3-HISTORICAL-MATRIX-20261106.md#本轮双机结果2026-11-06)。以下保留 #71 合入时的计划和未运行记录。

`python3 -B scripts/fm-s3-dualhost.py --terminals --peer <B_USER>@<B_IP> --a-host <A_IP> --remote-root /tmp/fm-s3-terminals-<RUN> --output <NEW_DIR>`

状态：**NOT_RUN**。本切片新增的入口绑定与资金边界路径尚无双物理机证据。上文执行闭合的双机结果对应的是闭合原始源码，不覆盖本切片的入口绑定与资金边界。

`--terminals` 在一个新 genesis 上建立 5 个 Receipt。前 4 个 Receipt 冻结后测试余额（73 单位）只剩 5 单位，计划场景如下：

| Receipt | 场景 | 期望终态 |
|---|---|---|
| 0 | 两端各自经已核验入口执行，结果配对 | UNRESOLVED（CONCORDANT） |
| 1 | B 的运行时经已核验入口产生物理宿主故障；自签不闭合，伪造观察方被拒，真实观察方闭合，闭合后审计方无法激活 | FAILED |
| 2 | B 的 worker 在 CONSUME 之后、入口之前被杀；重启只报告阶段，不重执行；审计方结果照常提交 | 期限后 UNRESOLVED（START_UNKNOWN） |
| 3 | B 的 worker 在入口之后、guest 之前被杀；重启不重执行，执行方自报 INTERRUPTED | 期限后 EXPIRED |
| 4 | 首次激活资金不足，记录边界，后续激活被拒 | FUNDING_EXHAUSTED |

结算阶段在 FAILED 的结算上分别于 COMMIT 前后终止权威进程并恢复，然后分配其余 Receipt，最后由 B 独立重放公开快照。

故障域：A 运行权威、审计方并持有闭合观察方密钥；B 运行执行方。A 上三者共处一个故障域。两台主机仅为有限实验假设，不推导身份或统计独立。

## 留给规范修订的事项

以下差异或选择留给第一项（正式规范与向量）处理，本切片不修改 00–03 规范：

1. **资金边界只在激活时可达**：资金边界只发生在首次激活冻结之前，因为 S2 在首次激活时冻结整个 Receipt。过程中按计量耗尽未建模；`ResolveBoundary` 的"不可比"分支在单链日志里不可达。
2. **期限观察的记法**：期限观察作为权威在求值时追加的子事件进入 frontier 投影，不是日志里的独立事件。正式 Phase D 需决定期限事件是否落盘。
3. **闭合来源**：闭合来源是合约钉住的测试观察方密钥，对应规范的"受认可 closure 来源"，但不解决 OQ-04/OQ-05，也不是 MainnetAssuranceProfile 组件。闭合要求验证尚未开始，与 §11.3.5"此时验证从未开始"一致。
4. **启动未知的处理**：`START_UNKNOWN` 按 ADR-0008 走 `INVALIDATING`。入口描述证明 Provider 签署了确切调用，不证明运行时已执行。

P0-1B 覆盖、ADR-0006、Gate 与主网资格均不变。
