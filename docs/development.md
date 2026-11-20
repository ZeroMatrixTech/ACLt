# 开发与维护入口

> 2026-11-19。当前执行规则见[开发政策](development-policy.md)。

## 统一入口

```bash
make help
make check
make test
```

`make check` 用于当前本地回归，`make test` 覆盖较完整的本地实现、编译、对拍与 sanitizer。选择与改动相关的检查，保留本次命令和实际结果。多虚拟机、双物理机以及外部实验通过各自显式入口执行，拓扑按[ENV-1](08-governance/environment-standard.md)和[DUALHOST-SSH-1](08-governance/dualhost-ssh-validation.md)记录。

## SHA 校验与交付

本轮决定停用清单、源码、工件、快照和协议内 SHA 一致性判定，入口同步情况逐项记录。摘要与原清单保留记录。`make manifests`、`make check-manifests`、`make verify-source` 和相关旧检查按当前政策停用；正常开发与打包按内容、文件范围和实际运行核对。

交付保留源码、数据、许可、测试与运行入口。历史归档和失败报告说明原运行，新运行结果另存。当前规则和旧说明冲突时以[当前开发政策](development-policy.md)为准。

## 目录

| 位置 | 内容 |
|---|---|
| `docs/00-overview` 至 `docs/08-governance` | 当前设计、研究、状态与协作说明 |
| `tools/`、`schemas/`、`registries/` | 对象与验证实现、类型和注册数据 |
| `tests/`、`experiments/` | 本地回归、模型与实验 |
| `scripts/` | 运行和维护入口 |
| `docs/testing/`、`docs/codocs/`、`docs/08-governance/audits/` | 按日期保存的报告和历史材料 |

## 实验与研究

最简验证机的问答复核、分片、预算和交接见[实验入口](../experiments/aclt-minimal-verifier-baseline/README.md)及[作业契约](07-roadmap/distributed-job-contract.md)。候选正式对象路径见[迁移说明](07-roadmap/formal-migration-plan.md)。有限总体研究见[数学模型](06-research/verification-round-mathematical-model.md)。

具体环境记录使用已发生的版本和拓扑；维护者可调整下一次运行采用的环境与额度。测试说明其实际支持域，待研究的数学性质继续引用既有问题。
