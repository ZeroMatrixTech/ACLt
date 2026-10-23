# 实验索引

## 当前入口

| 实验 | 范围 | 运行入口 |
|---|---|---|
| [state3](aclt-minimal-verifier-state3/README.md) | 当前单机实现，运行记录 ACLT-STATE-3 | 仓库根目录执行 `bash scripts/run-singlehost.sh` |
| [多节点 admission](aclt-multinode-admission/README.md) | 预登记模拟身份、持久接收器、重复消息与顺序检查 | 见下方独立命令 |

`make test` 包含当前单机与多节点本地检查；`make workflow` 为各组分别登记证据。兼容入口 `scripts/run-singlehost.sh` 仍只运行单机相关分组。更新包包含两个当前实验；详情见[开发指南](../docs/development.md)。该原型不证明身份独立、Sybil 抵抗、共识、权威复制或磁盘回滚保护，也不表示 G3 已通过。

## 多节点原型的本地复查

在仓库根目录执行，仅需 Python 标准库：

```bash
mkdir -p /tmp/aclt-admission-report
cd experiments/aclt-multinode-admission
ACLT_REPORT_DIR=/tmp/aclt-admission-report python3 -B check.py
```

这是本地逻辑和消息顺序检查，不会启动 VM。VM 驱动与原始磁盘证据位于项目工作区，未包含在本仓库；具体路径与历史测试数字见实验 README。仅凭 checkout 不能完整复现该轮 VM 证据。

## 接纳端回滚与复制保护

新增 [v2 外置权威账本实验](aclt-authority-admission/README.md)。本地复查运行 `make test-authority`；`make test` 与 `make workflow` 已接入。权威账本不随接纳端快照回滚；范围与剩余风险见实验说明，不能外推为任意系统回滚保护。

## 历史版本

`aclt-minimal-verifier/` 和 `aclt-minimal-verifier-state2/` 保留为历史版本及其当时的证据，不参与根目录统一测试和打包。重复的历史结果不计为新增测试。旧任务只使用其对应版本处理。

## RIR 最小构建探针（切片 1）

新增 [aclt-rir-build-probe](aclt-rir-build-probe/README.md)。`make check` 包含限定适配器与证据工具回归；`make test-rir-build-probe` 需显式指定工具链和新输出目录。它是候选 lowering 构建实验，已纳入交付包，不代替 RIR validator/RPR 或现有实验。

## RIR 切片 2：安全 SDK / I/O 候选执行

[aclt-rir-io-probe](aclt-rir-io-probe/README.md)提供 16 字节原样输出负载、受限候选解释器和显式执行入口。18 项回归纳入 make check，工具链及双机执行必须通过显式构建命令启动；同样纳入源码交付。它不替代正式 RIR/RPR 或结算验收。
