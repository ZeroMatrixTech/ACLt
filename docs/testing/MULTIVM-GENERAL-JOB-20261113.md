# 最简验证机 · 通用作业契约首轮联合验收

实跑提交 `75827bc9057bc8a228b5f2a5c6d85099e72d45b6`。同一可信宿主上的三个 QEMU 10.2.1/KVM 来宾，各 1024 MiB，使用 Ubuntu 7.0.0-30-generic 来宾内核。三来宾以独立启动标识、磁盘和 TCP 栈通信。宿主核对拓扑、源码、工件和逐端原始帧。

## 作业与结果

整数向量声明冻结三个字面量及一个倍增操作。C 在 A 通过验证后，才从接纳证据取得 A 的结果字节。求解使用 Python，另一个来宾使用 Rust 独立复核。根按声明顺序组成 `[2,3,4,11]`。树形和平铺使用不同计划摘要，五次运行共享同一整题摘要，各有自己的执行实例。

| 场景 | 接纳顺序 | 求解 gas 记账 | 结果 |
|---|---|---:|---|
| 树形计划 | A、B、C、D | 32938 | 发布 |
| 平铺计划 | D、B、A、C | 32938 | 发布 |
| B 丢答复并补算，接纳 B 后交接 | B、A、C、D | 41170 | 发布 |
| B 丢答复并补算，接纳 B 和 A 后交接 | B、A、C、D | 41170 | 发布 |
| B 丢答复，预算 41169 | 无 | 8232 | 补算前停止，退出码 1，无发布 |

B 的首算用原请求完成执行，故障注入在工作来宾落盘后丢弃答复。协调端保留请求和无答复事件，按 8232 gas 全额入账。交接发生在无在途尝试处。宿主等待旧来宾全部退出，重放账和回执，再把原日志交给新一组来宾。接手者用同一执行身份继续，新协调轮次递增。第二个交接场景的 C 直接消费交接前已接纳的 A。宿主重放全部阶段，逐字节核对发布记录和日志摘要。

本地回归另检验依赖成环、提前派发、错绑答复、迟到答复、重复接纳、少记 gas、在途交接拒绝和并发预留。独立的整题对照工件在 8242 gas 下触发 `TRAP_GAS_EXHAUSTED`，在 8253 gas 时输出相同向量。来宾验收只依赖分布式声明、各片验证和日志。该对照验证验收条件的独立性，实际超出单节点可用资源的负载仍待运行。

## 复现与证据

```sh
python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py run \
  --general --guests 3 --general-order 1023 --general-drop --general-checkpoint 2 \
  --kernel /path/to/vmlinuz --output /tmp/aclt-general-handoff
```

复现另一交接点可指定 `--general-checkpoint 1`。只保留 `--general --guests 3` 运行正常树形计划，加入 `--general-flat --general-order 3102` 运行平铺计划。预算负例使用 `--general-order 1023 --general-drop --solve-budget 41169`。

[原始证据包](public-evidence/MULTIVM-GENERAL-JOB-public-evidence.tar.gz) SHA-256 为 `d07c6b6c66171a1e3fca5780f2f3cddb91695adb1bb372746ab947ab8d15ed45`，包含五场景的两端帧、账本、来宾和宿主报告、源码清单、串口日志及终态证据。物理故障域、在途自动恢复与开放环境的协调权仍需独立验收。
