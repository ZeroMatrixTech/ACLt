# 最简验证机 · 多来宾容量排序通用契约验收

本报告记录 M2 多来宾容量排序通用契约验收：2026-11-14，维护者决定 M2 使用本地多来宾，证据范围为**同一物理宿主的来宾级验收**。宿主为 Linux 7.0.0-43-generic x86_64，使用 QEMU 10.2.1（TCG）；来宾使用 Linux 7.0.0-30-generic 和 Python 3.14.4。A、B、C 经 QEMU hub 和宿主回环 socket 互连，虚拟地址依次为 `10.0.3.1`、`10.0.3.2`、`10.0.3.3`；A 协调，B 和 C 求解并交叉复核，证据保留来宾启动标识及 TCP 端点。三来宾配置完成两阶段交付；在丢答复场景中，接手者补算并通过核验；单来宾对照在持久交付容量处失败。

源码固定在 `56b6a495e9d7357aec12f1cdaa6b9265b5ec5179`。源码清单含 95 项，清单 SHA-256 为 `f7ccca6a24deba928e5176e7fd5ad256aa875f12319fcf93fbc9ffb4c7782456`。操作者声明，运行前已获取 PARALLEL-1 §6.4 的宿主实验锁并持有至试验结束。

## 固定作业与账目

冻结输入共 524,288 条 16 字节记录。两个不相交的有序键范围各有 262,144 条。每片核验记录与冻结输入一致、序号唯一、完整覆盖本范围，且按 `(key, ordinal)` 严格递增。按范围拼接完整交付即得规范排序结果。推导沿用[固定容量排序报告](DUALHOST-CAPACITY-SORT-20261114.md#固定交付条件)。

按 [#117 维护者决定](https://github.com/ZeroMatrixTech/ACLt/issues/117#issuecomment-6881603900)，记录数为独立求解计量单位。派发前按片预留，验证后按实际核验的记录数结转，无答复按预留全额计入。执行预算为首算之和加最大分片的补算额度，共 786,432 条记录。整个执行只允许补算一次，派发前用共享日志原子检查补算预留和所有尚未派发的首算额度。整数向量仍独立用 gas。

## 实测

| 场景 | 结果 |
| --- | --- |
| 单来宾、一张 6 MiB 交付镜像 | 可用 5,857,280 字节。首片写入并核验，第二片写入出现块分配失败。残片表观长度 4 MiB，实读核验拒绝。 |
| 三来宾、两张各 6 MiB 的交付镜像 | B 求解片 1、C 复核，接手后 C 求解片 0、B 复核。A 协调并在内存转发有界帧，持久记录只含索引与证据。发布按片 0、1 排列，两张镜像合计交付 8,388,608 字节。 |
| 丢答复、补算、无在途交接 | B 的片 1 首算答复未送达协调器，账计 262,144 条。保留首算答复帧，补算复用该来宾唯一的交付镜像，首算交付字节随镜像被替换。该片补算后通过 C 核验，检查点已计 524,288 条、预留 0。宿主确认旧一轮来宾退出后启动新一轮。接手者先重放同一执行日志并重读已接纳镜像，随后只派发片 0。完整发布已计 786,432 条，余额 0。 |
| 离线负例 | 保持原发布记录时，删除片 1、替换其中一个字节或把片 1 的验证响应绑定用在片 0，分别被拒绝。 |

镜像使用 e2fsprogs 1.47.2 和 `mkfs.ext4 -m 0 -O ^has_journal`，以及本次复制进来宾的宿主默认配置。配置 SHA-256 `f799eeea48dad17da5cfda678f61d75be2cefbcf477109cd581876a68e0f2bc2` 在运行时由操作者于宿主记录，配置文件及其摘要未纳入原证据包。持有原 initramfs 的复核者可先与归档 `result.json` 中的 `initramfs_sha256` 核对，再从镜像提取配置比对。仅凭归档可核对 initramfs 摘要记录。来宾工具版本可见 `control/A/A/result.json` 的 `debugfs` 诊断。按 [#114 维护者决定](https://github.com/ZeroMatrixTech/ACLt/issues/114#issuecomment-6880955352)，单来宾失败是固定输入、编码、镜像容量和工具配置下的经验证据。限制针对持久交付容量，允许求解时使用内存。结论范围限于本次固定实例及可信宿主下的串行交接。

## 复现与重放

从证据标签检出源码，提供可启动的本地来宾内核和空输出路径。

```sh
flock "${XDG_RUNTIME_DIR:-/tmp}/aclt-experiment.lock" \
  python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py run \
  --capacity-sort --guests 3 --accel tcg --general-drop --general-checkpoint 1 \
  --kernel /path/to/vmlinuz --output /tmp/aclt-sort-contract-run
```

[脱敏证据包](public-evidence/MULTIVM-SORT-CONTRACT-public-evidence.tar.gz) SHA-256 为 `56ef93050aa6ae6a2cbaa80fc05e989cd47be21ae38130ac2f67a89bea77733f`。包内含源码清单、单来宾对照、两阶段账及原始 CBOR 帧、交付镜像、来宾报告、串口日志和负例结论。宿主报告中的内核路径仅保留文件名。

> 2026-11-16：按维护者决定（#128）将本包 7 个串口日志中的上游内核联系人邮箱字段统一替换为 `<redacted-email>` 后重新打包；上列 SHA-256 为脱敏后的包，帧、账目、清单和其他字段未变。


从包中的 `before/A/A/execution.cbor` 读取 nonce 构造 `SortJob`，用 `general_vm.replay` 依次重放 `before` 和 `after`，分别传入各阶段的来宾目录及 `sort_contract.replay_response` 检查器。对第二阶段传入第一阶段的原始日志。最后用 `sort_contract.verify_retained` 重读 `before/B/B/delivery.img` 和 `after/C/C/delivery.img` 并比较最终发布记录。
