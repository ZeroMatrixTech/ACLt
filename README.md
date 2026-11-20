# ACLt Protocol

ACLt Protocol 是面向分布式计算的开放、实现中立协议。仓库包含协议研究、可运行的实验实现与测试。当前语义基线为 v0.5，工程路线以 RIR、Rust Profile 与 RPR 为主要接口。

> 当前开发政策：维护者于 2026-11-19 授权仓库整肃，决定停用仓库及协议内 SHA 一致性判定；摘要字段保留记录。本轮由维护者审计，组织外 PR 暂停接收。见[当前开发政策](docs/development-policy.md)。

## 已实现的行为

- **问、答、验闭环。** 固定整数任务在 Python 求解、Rust 复核之间传递规范结果，能够观察结果、gas 与 trap 的差异，见[实验入口](experiments/aclt-minimal-verifier-baseline/README.md)和[局部语义](experiments/aclt-minimal-verifier-baseline/SEMANTICS.md)。
- **分布式作业。** 整题、计划与执行实例分别记录；实现了分片派发、跨任务依赖、尝试预算、结果接纳、归并与协调交接，见[作业契约](docs/07-roadmap/distributed-job-contract.md)。
- **多机实验。** 可信局域网的双物理机报告记录固定负载的分工与交叉复核；同宿主多来宾报告记录来宾间通信、恢复和重发情形。各报告分别给出实际拓扑、源码与输入，见[实验索引](experiments/README.md)。
- **候选对象与状态机。** FM 路线实现了固定角色下的任务接纳、审计观察、过程终态和测试资金结算，见[FM-S3 记录](docs/testing/FM-S3-CLOSEOUT-20261106.md)。
- **验证配置。** Python 与 Rust 实现了多个 Profile 结构、字段关系和判决切片；已有规则与待接通路径见[当前覆盖登记](schemas/verification-profile/coverage.json)。本轮摘要校验条目状态为停用，旧覆盖计数作为历史记录。
- **有限总体研究。** 仓库保存条件 Type-I 推导、有理数递推、精确 DP 与有限枚举对照；全域 Schema View 往返与活性推广仍分别由 #213、#215 跟踪，见[模型](docs/06-research/verification-round-mathematical-model.md)。

## 开始使用

```bash
make help
make check
make test
```

`make check` 运行当前本地检查，`make test` 运行较完整的本地实现与对拍。VM 与双物理机通过实验目录中的显式入口运行。运行所需环境与实际检查结果见[开发指南](docs/development.md)及[环境记录](docs/08-governance/environment-standard.md)。

## 阅读与进展

1. [项目总览](docs/00-overview/project-overview.md)：目标、已有工作和实现条件。
2. [术语表](docs/00-overview/terminology.md)：对象、函数与结果层级。
3. [协议骨架](docs/03-protocol/protocol-spec.md)与[Profile 对象](docs/03-protocol/verification-profile-schema.md)：当前结构与接口。
4. [当前状态](docs/07-roadmap/current-status.md)：已实现路径、证据与后续工作。
5. [文档中心](docs/README.md)：规范、研究和历史记录索引。

## 工程阶段

| 方向 | 已有工作 | 下一步 |
|---|---|---|
| 规格与对象 | v0.5 规范、对象字段和候选类型表 | 接通对象定义与实际实现，处理 #213 等已登记问题 |
| 模型与仿真 | 有限总体精确模型、B/Q 研究和安全层实验 | 按具体问题补模型与数据 |
| 本地实现 | 单机执行、Python/Rust 对拍与状态机实验 | 按改动验证实际支持域 |
| 多机与恢复 | LAN、多来宾、预算、交接和服务重启实验 | 扩展所选场景与负载 |

详细状态按[当前状态页](docs/07-roadmap/current-status.md)记录；各项工程成果使用自己的适用条件和验收记录。

## 贡献与许可

当前由组织内协作者推进，组织外 Pull Request 暂停接收。贡献说明见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题的联系入口见 [SECURITY.md](SECURITY.md)。

项目代码、规范、文档、研究和测试材料采用 [Apache License 2.0](LICENSE)。另有标注的 Unicode 数据与字体保留原许可，清单见[第三方材料](docs/08-governance/third-party-materials.md)。代理提交的 DCO 由维护者处理。

ACLt 是受 accurate 启发的项目名称。DistributedCompute、RUDCP、DCP 和 BigMind 用于历史追踪。`research-preview-1` 的发布快照与既有失败证据保留原文。
