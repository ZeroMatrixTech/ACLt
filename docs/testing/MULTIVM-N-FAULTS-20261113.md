# 最简验证机 · 多来宾作业中断验收（2026-11-13）

实跑源码为 `d1b4c3cd498774accec57adf17bea73810f6fccf`。同一宿主上的三台 QEMU 来宾运行固定 `stats-int-v1` 三叶树作业。来宾各有独立内核、磁盘和 TCP 栈，使用 Ubuntu 7.0.0-30-generic 内核、TCG 和每来宾 1024 MiB 内存。协调器 A 顺序派发，叶子编号从零开始。

| 场景 | 来宾与操作 | 中断点 | A 最终状态 |
|---|---|---|---|
| 工作进程退出 | B，`SOLVE-1` | 保存请求后，执行前退出，来宾入口状态 75 | `EXCHANGE_INCOMPLETE` |
| TCP 断连 | C，`VERIFY-1` | 保存请求后，复核前关闭 TCP | `EXCHANGE_INCOMPLETE` |
| 正常对照 | A、B、C | 无注入 | `PASS`，输出 SHA-256 `1216b67718f016f305a97cc465db4f34fb268c348fde0f1e75befbf49a347d56` |

两种中断都发生在叶子 1，对应输入区间 `[2, 4)`。叶子 0 的已接受回执仍留在帧证据中，叶子 1、2 均未接受。协调器写出 `failure.json` 并结束作业。宿主重放已完成的请求、响应和接受回执，核对最后请求同时留在双方证据中，以及对应响应、后续帧、归并输出和成功摘要均缺席。预期中断仍以失败状态和退出码 1 表示。证据限定于来宾工作进程退出与应用 TCP 关闭；后续可另行测量链路失联、宿主故障及恢复语义。

[证据包](public-evidence/MULTIVM-N-FAULTS-public-evidence.tar.gz) SHA-256 为 `e1e46e3b320c398be0c6720bcafa8a1a121a4f57135989e6e846e43bfece2ee2`。最简验证机回归重放两个中断场景，并检查伪造中断标记、缺少原始请求及提前生成归并输出均会被拒绝。

> 2026-11-16：按维护者决定（#128）将本包 6 个串口日志中的上游内核联系人邮箱字段统一替换为 `<redacted-email>` 后重新打包；上列 SHA-256 为脱敏后的包，帧、账目、清单和其他字段未变。


```sh
python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py run \
  --guests 3 --kernel /path/to/vmlinuz --output /tmp/aclt-worker-exit \
  --interrupt worker-exit SOLVE-1
python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py run \
  --guests 3 --kernel /path/to/vmlinuz --output /tmp/aclt-disconnect \
  --interrupt disconnect VERIFY-1
```

本轮只规定遇到不完整交换时停止和留证。是否重派、是否沿用已接受叶子、如何给二次执行计费，以及整题资源上限和 trap 如何组合，均需要独立的规则与验收。
