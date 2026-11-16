# 最简验证机 · R2 跨物理主机 nVM 验收

2026-11-15，按[阶段 #128 决定 2](https://github.com/ZeroMatrixTech/ACLt/issues/128)和 [DUALHOST-SSH-1](../08-governance/dualhost-ssh-validation.md)在物理 A、B 上实跑 [R2 #132](https://github.com/ZeroMatrixTech/ACLt/issues/132)。维护者授权覆盖首次公开阶段，阶段结束即终止。两端各持有 PARALLEL-1 §6.4 宿主锁，锁覆盖 QEMU 启动、退出和证据回收。B 的部署、启动和回收使用严格主机密钥验证的 SSH。作业帧通过来宾虚拟网卡，在跨宿主链路上由 QEMU TCP stream 直接经 LAN 传输。A 的 QEMU hub 汇接来宾，本地来宾链路使用宿主回环。

两端为 Linux 7.0.0-43-generic x86_64，QEMU 10.2.1，实跑均用 KVM。来宾 Linux 7.0.0-30-generic，Python 3.14.4。两端各用独立运行目录与证据盘。共享的来宾内核和 initramfs 在 B 落盘后逐项验摘要，每个来宾核验冻结源码清单和执行器指纹。实跑源码为 `35062a2d0f279da0316d1601e9680e0fa0afc843`，99 项源码清单摘要为 `bbeb1abd9e0e32096bcdc3f6b899046b52853adabafcaed8f5ac00e733be93da`。

| 场景 | 物理 A 来宾 | 物理 B 来宾 | 结果 |
|---|---|---|---|
| 三来宾三片 | A、C | B | 三片归并发布，离线重放与冻结参照逐字节一致，计 26,049 gas |
| 四来宾六片 | A、C | B、D | 六片归并发布，离线重放与冻结参照逐字节一致，计 52,206 gas |
| 远端断连 | A、C | B | B 在 `SOLVE-1` 收件后断连。首片接纳，片 1 无答复计 8,719 gas，累计 17,438 / 34,768 gas。重放为 `SAFE_STOP`，没有发布 |
| 远端丢答复和补算 | A、C | B | B 保留 `SOLVE-1` 的求解答复，协调来宾未收到。无答复计 8,719 gas，协调来宾补算一次，最终发布与三片正常结果一致，累计 34,768 / 34,768 gas |

来宾 A 是协调器。角色按分片轮换求解与交叉复核。物理 B 上的每个 QEMU LAN 连接均有 A、B 两端的反向一致端点记录，归档 `host-topology.json` 使用 A-LAN、B-LAN 代替真实地址。来宾的虚拟端点、不同启动标识、对应角色的请求和答复原始帧可独立复核。缺失求解答复帧、替换成另一操作的答复、篡改一侧已观测端口均被拒绝。

初次用旧 QEMU socket 后端，宿主 TCP 已建立但来宾连接超时。QEMU 自身的来宾链路诊断看到 ARP 请求没有收到回复。物理链路切到 TCP stream 后完成上述矩阵。原始失败串口日志和脱敏拓扑收在 `failed/`。

## R3 调用

现有本地入口继续可用。跨宿主时提供仓库外 JSON 配置，字段为 `ssh_target`、`host_a_lan`、`host_b_lan` 和 `remote_root`。其中远端目录应由操作者指定为可创建本轮私有子目录的位置。

```sh
python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py run \
  --kernel <kernel> --output <new-dir> --guests 3 --leaves 3 \
  --dualhost-config <private-json> --host-b-roles B \
  --solve-budget 34768 --interrupt drop-reply SOLVE-1 --retry-solve
python3 -B experiments/aclt-minimal-verifier-baseline/multivm.py replay \
  --evidence <run-dir> --executor <matching-executor>
```

双机入口自动取得两端锁。每次调用可选择零或一个故障。R3 可从 `outcome.json` 读取版本 `aclt.nvm-outcome/1`、请求与实触发事件、发布标志、独立重放账和证据位置。正常发布退出 0，验证过的安全停止退出 1，配置、启动、取证或重放失败退出 2。启动前拒绝且未创建运行目录时，以退出码为准。离线重放对能核对的发布或安全停止均退出 0，无法核对时退出 2。种子、样本汇总及后续多次运行属于 R3/R4。

[可重放脱敏证据包](public-evidence/DUALHOST-MULTIVM-R2-public-evidence.tar.gz) SHA-256 为 `bfff182e64340be122b92b2bd9e806b5f9b120a38b703eccfb4ea206aceae4a7`。包含 198 个文件，涵盖冻结输入、来宾原始帧和串口、宿主拓扑、账目、原和重放结果。复核使用证据提交构建并匹配摘要的独立执行器。适用范围为可信双机 LAN 和本报告的固定用例。宿主故障域的统计独立、跨宿主协调器接手、故障概率和经济性由后续工作处理。

> 2026-11-16：按维护者决定（#128）将本包 19 个串口日志中的上游内核联系人邮箱字段统一替换为 `<redacted-email>` 后重新打包；上列 SHA-256 为脱敏后的包，帧、账目、清单和其他字段未变。
