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

## 历史版本

`aclt-minimal-verifier/` 和 `aclt-minimal-verifier-state2/` 保留为历史版本及其当时的证据，不参与根目录统一测试和打包。重复的历史结果不计为新增测试。旧任务只使用其对应版本处理。
