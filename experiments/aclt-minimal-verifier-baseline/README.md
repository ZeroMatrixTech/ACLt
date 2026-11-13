# ACLt 最简验证机

[立项与首轮规格](../../docs/07-roadmap/minimal-verifier-baseline.md)下的切片验证实验。判题规则 `aclt.exp.rir-stats-exact@1` 固定[候选 RIR stats-core](../aclt-rir-stats-probe/INDEPENDENT-CORE.md)的精确结果语义。

- `ask(artifact, data, limits)` 验证工件和上限，生成规范 CBOR 的 `Question`。题目绑定规则版本、RIR 工件摘要、输入摘要，以及 gas、输出、调用深度和内存页上限。题目和输入使用各自的实验摘要域；工件沿用既有 RIR 摘要域。
- `solve(question, artifact, data)` 用现有 Python 求值器产生 `Answer`，包含题目摘要与规范 `Outcome` 字节。
- `verify(question, artifact, data, answer, executor=...)` 核对题目和字节的绑定，调用验证者本地指定的 Rust 执行器，从原始工件和输入独立求值。逐字节比较规范结果，返回 `ACCEPT` 或带原因的 `REJECT`。执行器启动失败或无法产出结果时抛出 `ExecutionError`，提交仍待判定。

从仓库根目录复现，需要 ENV-1 的 Python 和 Rust：

```sh
make test-minimal-verifier
```

该命令也纳入 `make test`。测试在临时目录构建 Rust 执行器，以冻结的 `stats-int-v1` 向量检验正常输出、同题的正确与错误提交、不同 gas 上限下的跨题提交，以及已有除零 trap。另有工件与输入绑定、未知规则和执行器错误的用例。阶段 2 增加手算输出、相邻 gas 上限、结果字段负例及单侧计量偏差注入，详见[语义验收](SEMANTICS.md)。这些判决与证据仅适用于本地实验。

[双机作业切片](DISTRIBUTED.md)说明拆分、跨机交叉验证、归并、资源边界和验收命令。

## 本地双来宾运行

物理双机暂停期间，用同一物理宿主上的两个 QEMU 来宾分别承担 A、B。两端有独立内核、根文件系统、证据磁盘和 TCP 栈，作业帧走来宾间的 QEMU socket 链路；宿主之外的网络不参与。这是来宾级证据，不是物理双机证据，也不是统计独立性证据。

```sh
make test-minimal-verifier-multivm \
  MULTIVM_KERNEL=/path/to/vmlinuz \
  MULTIVM_OUTPUT=/tmp/aclt-multivm-1
```

需要 QEMU、`cpio`、`mkfs.ext4`、`debugfs`、静态 `busybox`、宿主 CPython，以及可读的 guest 内核镜像。来宾根文件系统由 `multivm.py` 用宿主 `busybox` 与 CPython 现场组装，也可用 `--runtime-root` 指定已有目录（需含 `bin/busybox` 与 `usr/bin/python3`）。Rust 执行器在宿主用 `-C target-feature=+crt-static` 静态编译后放入两个来宾，来宾内不编译。

证据目录保存两端串口日志、来宾报告 `guest.json`、两侧原始帧、`plan.cbor` 与归并结果、源码/内核/initramfs/执行器摘要，以及汇总的 `result.json`。可选参数：`MULTIVM_SOLVE_BUDGET`（每片 gas 预算）、`MULTIVM_RECURSIVE=1`（递归归并）、`MULTIVM_ACCEL=kvm|tcg`；`--memory`、`--runtime-root`、`--keep-work` 直接传给 `multivm.py run`。不带 `MULTIVM_RECURSIVE` 时目标只跑平坦计划，静默忽略该变量会让人误以为测了树归并。运行要求实验源码已提交且工作区干净，与双机驱动相同。

### 可配置来宾数

默认双来宾入口保留。设置 `MULTIVM_GUESTS=3` 至 `16` 会启用树作业，默认每台来宾对应一个统计块；可用 `MULTIVM_LEAVES` 显式指定叶子数，范围为来宾数至 32。A 按叶子序号轮换指定求解方与下一台验证方，逐次执行交换，所有来宾均保存自己的证据。详见[三与四来宾验收](../../docs/testing/MULTIVM-N-20261112.md)。

多来宾入口可用 `--interrupt MODE OPERATION` 在远端保存指定请求后注入工作进程退出或 TCP 关闭。两种验收及退出码见[作业中断报告](../../docs/testing/MULTIVM-N-FAULTS-20261113.md)。

派发前检查固定统计工件的[整题资源下限](../../docs/testing/MULTIVM-ROOT-LIMITS-20261113.md)。三来宾及以上可用 `--root-gas-limit` 和 `--root-output-limit` 指定整题上限，分片求解预算仍用 `--solve-budget`。

三来宾三叶作业可使用 `--handoff` 测试由宿主串行化的[协调器交接](../../docs/testing/MULTIVM-HANDOFF-20261113.md)，需要显式分片求解预算。
