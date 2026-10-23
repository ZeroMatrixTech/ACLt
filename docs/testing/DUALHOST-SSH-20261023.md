# 双物理机 SSH 验证第 1 轮：2026-10-23

本轮远端环境验收与限定双机场景通过。适用 DUALHOST-SSH-1；不关闭 P0-1B、G0/G2，不改变协议、生产准入或统计独立性结论。

## 基线和拓扑

- 主仓库基线 `9e569e1459efe0266aef88107cfb797cf9036f47`，叠加此前未提交的环境切换文档，以及本轮两个候选运行适配器 `dualhost_node.py` / `dualhost_service.py`。未提交或推送。
- 固定源码 292 个文件；源码清单 SHA-256 `38940e9623b2c696d7ccfad4bbaf5f83931a046346a401f9003d4d7806a58e1e`；部署归档 SHA-256 `f1d7d12f0ac002d49441e5ac2d979bb20466320639f637accc5643dc5997a902`。因有未提交改动，仅 checkout 基线不足以复现，须使用保存的快照。
- A：`inpax-aki / <A_IP>`；运行唯一权威账本、两个接纳端及两个专用响应丢失转发端。
- B：`aki2 / <B_IP>`；用户 `<B_USER>`；在 `/home/<B_USER>/aclt-dualhost/round1-20261023-152700` 使用独立 ext4 运行目录和持久 worker 状态。
- 任务协议从 B 直接通过 LAN TCP 连接 A；SSH 只执行控制命令和传送证据。实际请求目标地址在逐请求 wire 记录中。
- A 的权威服务与接纳端同属一个物理故障域。两个接纳端和并发 worker store 不算额外物理节点或独立身份。

## 远端环境验收

用户完成 sudo 安装后，实测 rustc/Cargo 1.93.1（Ubuntu 包 1.93.1ubuntu1）、Python 3.14.4 / Unicode 16.0.0、G++ 15.2.0、Git 2.53.0、OpenSSL 3.5.5、Make 4.4.1、Bash 5.3.9。系统 Ubuntu 26.04.1 LTS / Linux 7.0.0-38-generic，x86_64；磁盘可用约 137 GiB。排他创建、fsync、flock、硬链接和 rename 探针通过；不据此证明物理断电持久性。

远端全量 `make test` 退出码 0，保留完整日志与 JSON 工件：

- Python 回归 74 项（13 模型、34 配置/编码、27 流程/交付）；交付清单和覆盖盘点通过。
- state3：68 验证、133 严格接纳、10 对抗场景；204 精确数据集、408 结果变异、20 sanitizer 运行、12 畸形输入、22 归约器向量通过。
- 多节点本地 32 检查，24 消息顺序 / 96 转换；权威实验 25 项本地场景通过。
- Python/Rust 编码候选 29,766 样本及 2 项 OpenSSL 摘要复核通过。

以上是 B 上的环境/本地回归，不混入跨机统计。

## 实际双机场景

28 次 SSH 控制操作、30 次直接 LAN 协议请求，80 项运行断言通过：

1. 正常授权、远端 C++ 计算、接纳、只读审计和完整包重传，回执稳定。
2. 同一 worker store 再次计算被持久标记拒绝。
3. 冲突结果保留原贡献和回执，并记录 conflict。
4. 接纳端进程硬终止/重建后可重传；权威进程硬终止/重建后原回执保留。
5. 两个接纳端并发争用同一 unit，只有一次计算、一次贡献；另一 store 获 consumed。
6. 首个结果无效后永久失败；原正确保存包不能修复该资格。
7. 权威提交资格后，接纳端实际关闭 socket 丢失 reserve 响应；本次不计算，新 store 也不能重新领取。
8. 权威接纳后丢失 submit 响应；原始包重传返回 duplicate 和原回执。
9. 仅停止本轮接纳服务造成端口不可达；不获得离线授权、不计算，恢复后同 store 不重算。
10. 权威不可达时无法成功接纳；恢复后只重传保存包，首次接纳随后 duplicate。

不触碰管理 SSH、系统网卡、其他进程或物理电源。端口不可达是受控服务故障，不冒充路由级网络分区或物理断网；进程重启不冒充整机重启。

## 离线核对与结论

独立核对器不导入被测实现模块，689 项检查通过，逐份验证请求 HMAC、26 份 RSA 签名响应、请求/任务/boot/nonce/身份绑定，独立复算整数结果和回执摘要，并核对源码与回收文件摘要。

最终账本与远端文件对账：6 次持久资格占用、5 个启动意图、5 次完成调用、4 份贡献、12 个账本事件。无额外资格占用或完成计算；丢失授权响应与接纳端不可达场景均无计算。5 次计算中有 1 次属于故意无效首结果场景，因此贡献数为 4。

两个 gateway 和实际服务进程均已停止；远端新建实验目录与证据保留。运行前后远端源码 pin 均匹配，另回收 16 份 JSON 工件（含构建元数据）。测试私钥留在本地私有产物，不进入仓库；远端仅有公钥与本轮测试 HMAC 凭据。私有证据目录不作为公开发布包。

## 证据与复查

本轮完整产物：`<EVIDENCE_ROOT>/dualhost-round1-20261023`（本地私有路径，占位符含义见[双机约定](../08-governance/dualhost-ssh-validation.md)）。

- `summary.json`、`round-result.json`、`checks.json`：分别记录最终结论、运行断言及场景原始结果。
- `source.tar.gz`、`source-files.json`、`setup.json`：冻结源码、摘要与部署信息。
- `remote-environment.json`、`remote-make-test.log`、`remote-test-result.json`：环境与全量远端回归。
- `operations/`、`remote-evidence/`、`state/`：控制输出、逐请求 wire、持久 worker 文件、账本和服务日志。
- `remote-final-provenance.json`、`remote-baseline-reports/`：运行后来源与基线工件。
- `prepare.py`、`run_round.py`、`driver/`：本轮一次性适配器；未成为通用仓库测试入口。
- `check_offline.py`：在原产物目录执行 `python3 check_offline.py` 可只读重核原始证据；输出写 offline-result.json。
- `EVIDENCE-SHA256SUMS.json`：本地静态产物摘要；不构成外部可信签名。

## 余项与下一切片

下一轮优先交换两端角色，并覆盖 worker 计算进程中断、持久标记存在但无完整提交包的恢复语义；之后把一次性适配器整理为可参数化双机入口。任何新增切片仍先固定源码与验收条件。

本轮未覆盖真实断电、路由级网络分区、权威账本自身回滚、恶意 worker、worker 磁盘回滚、统计/身份独立性和生产安全。旧 VM 场景未重跑；不声称完整复现五 VM 的独立故障范围。既有协议实现缺口保持原状态。
