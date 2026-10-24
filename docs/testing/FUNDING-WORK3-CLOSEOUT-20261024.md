# 第三项工作收尾：测试资金预留、固定分配与故障恢复

日期：2026-10-24。工程跟踪标识：`FUNDING-WORK3`。
**结论：三个切片组成的第三项工程工作，在预置整数测试资产、冻结政策、固定内部支付/退款和进程故障恢复的限定范围内完成。**
这不是新 SemanticStatus/VersionDisposition；OQ-10、G0/G2/P0-1B、ADR-0006、B/Q 与生产资格保持原状态。

安装前基线 `6bc557276b5c955ae4dc9544c991044e7ab01e8e`，预检工作区干净。三个切片和既有其他实验源码保持原字节，历史失败/成功记录保留；本次新增组合脚本、五项工具回归、维护/交接入口和本轮重跑证据，不迁移旧库、不提交或推送。

## 三片与组合验收

| 范围 | 已完成的限定内容 | 本轮新跑 |
|---|---|---|
| 切片 1 | v1 冻结资金政策、整数余额、按 cap 原子预留、重复查询原回执、守恒 | 12 场景、5 个篡改反例，A/B 各 22 回归 |
| 切片 2 | v2 资金前置 START、双端完整 outcome 精确比较、唯一整笔权利、固定支付/退款 | 12 场景、6 个篡改反例，A/B 各 26 回归 |
| 切片 3 | 实际 TCP 丢回复、COMMIT 前后 SIGKILL、首次 barrier 竞争、worker 持久边界故障、查询原权利 | 14 场景、6 个篡改反例，A/B 各 16 回归 |
| 统一收尾 | 当前源码/部署锁、三片字节/规则连续性、11 个 checkpoint 独立复核、复现/交接 | 组合脚本与另进程 verify 一致，5 项新增工具回归 |

这些是三套**独立测试部署**，各自拥有 genesis、authority、enrollment、账本和供给。第一片 v1 与后两片 v2 是显式政策演进；后两片自身已各自打通资金→执行/证据→固定分配。收尾不把旧库直接升级成一个正式生产系统，也不合并三套余额或把共享样例当成同一生产任务多次付款的许可。

## 连续性与正式对象边界

组合核对正常样例的 Task commitment 原始字节/experimental_task_id、RIR/input 原字节、Profile、执行上限相同。原始工件/输入通过旧 binding checker 重新绑定；后两片 A/B 保存的四份正常 outcome 的 result 和原 outcome digest 一致，gas=9126、output=96 字节。只核对保存字节，不新增计算或把哈希相等解释为来源认证。

共享资金字段 task/requester/asset/精度/来源/cap/fee/结算退款待定 rule ID 一致，正常 cap=100、fee=30。第一片 policy 为 @1，后两片为含 comparison_rule 的 @2，v2 policy 原字节在后两片相同。payee 在各自政策/部署中冻结绑定，第一片的测试收款引用不强行等同于后两片角色身份。reservation/entitlement 受不同 authority/deployment 约束，不跨库复用。

| 可执行实验对象 | 正式规范尚缺 |
|---|---|
| ExperimentalTaskCommitment / experimental_task_id | 正式 ComputeReceipt/ReceiptID、身份签署、完整注册与对象编码 |
| funding-policy @1/@2、prefunded test unit | 完整 FundingPolicy/SettlementPolicy、全终态×故障×来源矩阵 |
| funded-start 与一次性角色槽位 | 正式 active Lease/ExecutionCapability、统一生产准入及旧入口迁移 |
| 相同 reference 的双端 outcome/comparison | 完整 RIR/RPR conformance、独立实现/恶意 worker 验证、TRUSTED 条件 |
| 固定整笔 entitlement / 原回执 | 正式 EntitlementKey、真实支付/适配器/最终性及偿付语义 |
| 实验事件流 / signed checkpoint | 正式 EventRecord、assurance/finalized log、外部见证和权威抗回滚 |

A 的可信单账本是有限实验假设，不新增协议 Principal/验证裁判。比较不新增 `REEXEC_EXACT` 方法，不自动产生 TRUSTED。资金预留与 Provider 暴露或统计贡献/独立资格不同，公开源文件或数据一致性不支持 B/Q。

## 本轮重新取证

新组合入口固定 **67 个源文件**（三片、统计/授权/承诺依赖、组合脚本和测试）。三套部署分别核对 B 上 47/48/57 文件的精确 source lock，均使用新目录；没有用历史 PASS 或复制旧运行库替代当前执行。已有 Python/SQLite/OpenSSL、保存的 Rust/Wasm fixture 沿用，无新依赖、安装或 Rust 重编译。

A 服务/账本与适用 A worker 同故障域，B 独立请求/worker 目录。实际资金、START、SUBMIT、SETTLE/STATUS 经 TCP，B→A 经 LAN；SSH 仅控制/部署/取证，严格主机密钥检查开启。恢复矩阵只中断本轮创建的实验进程，不断开管理 SSH，不改系统服务/防火墙，不运行 VM。两台物理主机仍是 DUALHOST-SSH-1 有限接受假设，相同代码、操作者/LAN/供电存在共因。

A/B 各 **64 项**三片局部回归（22+26+16）通过；新增 **5 项**工具回归防止源码漂移、证据修改、缺失/多余 pin、路径/符号链接替换和覆盖旧报告。默认 `make check` 合计 **265 项**。三组分别通过 12/12/14 场景与 5/6/6 篡改反例，不把这些场景/传输重试累计为计算次数或不同攻击类型数量。

三个账本分别核对：

| 独立部署 | 初始测试总量 | 最终 available | 最终 active reserved | 历史 paid/refunded | 唯一状态 |
|---|---:|---:|---:|---|---|
| reservation v1 | 300 | 50 | 250 | 无支付/退款 | 2 份预留，18 条事件 |
| fixed v2 | 1000 | 900 | 100 | 30 / 170 | 2 份结算，30 条事件 |
| recovery v2 | 1000 | 900 | 100 | 150 / 450 | 6 份结算，61 条事件 |

每行独立守恒，不能跨行加成一个资金池。paid/refunded 是已进入 available 的历史流量，不再加到资产供给。固定矩阵有 5 份 outcome；恢复矩阵 14 个有效 START/13 份 outcome，最后一个 B 只有 permit，因此完整 cap=100 继续预留。没有真实资金或外部支付。

## 恢复与离线组合复核

正常 recover 只发 STATUS：已结算取原回执，RESERVED 保持占用，不可用保留未知，不自动付款/退款或重算。完整 fsynced outcome 可原字节重传；permit-only/半成品没有续算许可。只有查询确认未提交回滚后，才显式再发原政策下的 SETTLE。

本轮恢复矩阵中：支付/全退款的 COMMIT 后真实关闭 TCP，B 没有成功回执报告；查询恢复原 receipt digest。COMMIT 前 SIGKILL 的热日志恢复与原 event/projection/checkpoint 一致，未提交事件不存在；COMMIT 后 SIGKILL 保留原事件/分配。两 B 进程均 ready、政策尚未结算后 barrier 放行，一 SETTLED、一 DUPLICATE 原回执相同。worker 许可/完整 outcome 边界的 SIGKILL 不产生额外计算或未知退款。

组合工具在独立进程调用原维护 auditor，重新检查 **11 个 checkpoint**：第一片 final、第二片 final、第三片 9 个中间/final。全部与保存投影一致，且第三片提交前/回滚后的导出与签名 anchor 相同。核对后又在另一个进程用独立留存的 pins 执行统一 `verify`，与 suite 摘要一致；这个阶段没有网络、guest、编译器或活数据库写事务。

另对组合入口实际执行 **4 个负向控制**：错 recovery issuer pin、错最终 checkpoint digest、缺失回滚 checkpoint pin、修改仅公开证据副本。全部非零拒绝，未生成成功报告；原始证据和失败日志保留，private 材料未复制进副本。签名锚点核对共享旧 schema/codec/密码学辅助，HMAC 来源依赖权威签名日志，不冒充独立密码/身份实现。

## 复现、交付与交接

[维护入口](FUNDING-WORK3-MAINTENANCE.md)给出双机新跑、只读核对、证据布局和原失败恢复边界：

```sh
make test-funding-work3 \
  FUNDING_WORK3_PEER=USER@B_IP FUNDING_WORK3_A_HOST=A_LAN_IP \
  FUNDING_WORK3_REMOTE_ROOT=/absolute/new/B/suite \
  FUNDING_WORK3_OUTPUT=/absolute/new/A/evidence

python3 -B scripts/funding-work3.py verify \
  --evidence /saved/suite --pins /independently/retained-pins.json \
  --report /new/verification.json
```

第一条显式运行三组真实双机矩阵，第二条只读复核保存记录。输出根和报告必须新建，verify 报告位于旧证据根外；当前源码变化/证据缺失时拒绝，不从历史通过状态或报告补齐缺失 pin。默认检查不联网。

[机器摘要](funding-work3-closeout-20261024.json)保存源码 SHA、共享字节/政策范围、三个账本及 11 个 checkpoint 汇总和原始文件摘要；不将大体积重复原始包/投影搬进仓库。本地 `<EVIDENCE_ROOT>/funding-work3-closeout-20261024/dualhost-run1/` 保存三片原始运行、源码锁、公共清单、key/checkpoint pin 与完整 suite；目录外保存 standalone-verification、四个反例和交付核验。此前三片/失败证据全部保留，不重复累加为本轮成果。

安装后重新检查默认回归、清单、diff 和源码包，并核对已安装/归档源码与本轮 source lock 一致。源码包不含 key/HMAC config/数据库/运行目录；公开 B 证据不含 private。实际 IP、用户和机器路径只在操作者本地，不能将整个含 private 的运行根直接公开。

## 剩余条件与下一轮

保证仍依赖诚实 pinned 宿主/config/持久存储、A 私钥/enrollment 和单一不回滚/不分叉权威。哈希清单不是认证根，需独立留存 key/checkpoint pin；合法旧锚点仅说明旧时点，不能证明新鲜性、finality 或权威回滚/分叉保护。SIGKILL/热日志恢复不是整机断电/重启、存储控制器测试或 failover。路由级分区、TLS/DoS、attestation、生产身份/密钥生命周期、任意恶意 worker、独立执行实现和真实支付适配器均未覆盖。

本次不继续扩展经济范围。**下一轮建议先收敛正式对象与接口**：整理任务/资金政策、准入许可、comparison、权利、EventRecord 与规范对象的最小迁移/签署/conformance 缺口，并给出清晰拒绝和验收条件，再确定实施切片。完整终态/故障/来源/破产/舍入矩阵、B/Q 与生产 assurance 分开跟踪，不据三项实验闭环关闭 G0/G2/OQ-10。

历史切片：[资金预留](FUNDING-RESERVATION-SLICE1-20261024.md)、[比较与固定分配](FIXED-SETTLEMENT-SLICE2-20261024.md)、[故障恢复](SETTLEMENT-RECOVERY-SLICE3-20261024.md)。
