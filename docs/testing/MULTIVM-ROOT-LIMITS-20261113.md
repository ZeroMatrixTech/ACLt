# 最简验证机 · 整题资源准入（2026-11-13）

实跑源码 `6490f599aa3d5c3dfc6e4c2826606b2f9518c915`。三台同宿主 QEMU 来宾运行固定 `stats-int-v1` 三叶树作业，使用 Ubuntu 7.0.0-30-generic、TCG 和每来宾 1024 MiB 内存。

## 准入条件

对固定工件和合法输入，设元素数为 (n)，块大小为 (k)，块数为 (b=\lceil n/k\rceil)。整题成功路径需要 `8312 + 108n + 191b` gas 和 `48b` 输出字节。先沿用 `ask` 校验整题上限和工件，再核对这两个下限。该工件固定实例化两页内存，合法输入路径只有深度为 1 的 Wasm 入口及宿主导入。gas 上限也覆盖每次正成本计量所使用的步数保护。推导依据见[计量说明](../../experiments/aclt-minimal-verifier-baseline/GAS-ALLOCATION.md)。

沿原块边界切分时，整题与分片写出相同统计块。整题资源准入通过后，分片另按各自路径费用冻结，并检查作业求解预算。整题上限、各次尝试的 gas 与作业预算保持各自的语义。协调器和宿主重放继续执行整题参照并比较输出。显式上限的实验保存整题题目字节，宿主也逐字节核对。

## 验收

| 整题 gas 上限 | 整题输出上限 | 结果 |
|---:|---:|---|
| 9425 | 144 字节 | 三来宾通过，分片求解共 26049 gas，输出与整题参照逐字节一致 |
| 9424 | 144 字节 | 派发前拒绝，未创建运行目录 |
| 9425 | 143 字节 | 派发前拒绝，未创建运行目录 |
| 9424 | 143 字节 | 派发前拒绝，未创建运行目录 |

回归另在整题单独执行时复查相差一单位的 gas 与输出 trap，并用 Rust 复核 Python 的完整结果。准入的报错顺序只说明检查哪项上限先失败。一般工件的资源界、多个上限同时不足时的精确 trap、宿主故障及整题完整 Outcome 的跨片推导仍待验收。

[证据包](public-evidence/MULTIVM-ROOT-LIMITS-public-evidence.tar.gz) SHA-256 为 `02d4f26ee6af9694c52c45d29d2dce20905e0f459e8a3cad43a8ea00de83d6ad`，包含三来宾原始证据和三组派发前拒绝。默认最简验证机回归重放成功场景，并检查整题上限变动能被检出。

```sh
python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py run \
  --guests 3 --root-gas-limit 9425 --root-output-limit 144 --solve-budget 26049 \
  --kernel /path/to/vmlinuz --output /tmp/aclt-root-exact
```
