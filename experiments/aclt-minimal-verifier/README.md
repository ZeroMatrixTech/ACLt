# ACLt 单机最小验证试验

使用 **Rust 调度与验证 + C++ 计算进程**，在一台 Ubuntu 26.04 LTS 电脑上完成“分块计算 → 检查 → 故障重派 → 汇总”。不需要第三方语言库、网络服务或账户。

这是根据旧对话重建的独立试验，不是原 ACLt 仓库的恢复，也不代表 P0-1B 或整个协议已完成。

## 放到 GitHub 的哪里

建议放在 ACLt 仓库根目录下的 **`experiments/aclt-minimal-verifier/`**。交付 ZIP 已带这个目录结构，解压到仓库根目录即可。不要放入 `src/` 覆盖已有实现，也不要覆盖原来的规范或覆盖登记。

如果新建一个专门的试验仓库，可以保留此目录结构；在 GitHub 仓库主页进入该目录便可看到这份说明。提交整个试验目录即可，`.gitignore` 会忽略编译产物、运行日志和本地工具链。压缩包只包含源码、示例、脚本和文档。

## 从零运行

在 Ubuntu 26.04 LTS 安装官方工具链（已有则跳过）：

```sh
sudo apt-get update
sudo apt-get install -y g++ rustc cargo python3
```

进入本文件所在目录后执行：

```sh
bash scripts/run-ubuntu.sh
```

脚本离线构建程序，并执行 **68 个基础验证案例 + 12 个多进程场景**；任何失败都会以非零退出码结束。正常输出末尾包括：

```text
ACCEPT count=10 chunks=3 sum=28 min=-7 max=12
PASS: 68 verification cases; worker input rejection and Python reference totals checked
PASS: 12 multi-process scenarios; retries, late results, attempt limits, cleanup, and overwrite refusal checked
```

Python 仅负责测试；实际调度和验证由 Rust 完成，计算由 C++ 完成。Rust 需要支持本项目使用的标准库 API，已实测 Ubuntu 官方 1.93.1；C++ 使用 C++17。

## 看一次正常运行和一次超时重派

```sh
bash scripts/demo.sh normal
bash scripts/demo.sh slow
```

每次演示创建新的 `build/demo-*/run/` 目录并打印其路径。其中有输入快照、参数、每次尝试的结果与错误输出、事件记录，以及全部验证通过后发布的 `results.txt`。

`slow` 让第 0 块的首次计算等待 1 秒，超过 500 毫秒期限；调度器重派该块。第二次结果通过后，首次迟到的结果会记为 `STALE` 并忽略。

事件含义：

| 事件 | 意义 |
|---|---|
| START | 启动一个真实 C++ 进程，记录块号、尝试编号和进程号 |
| ACCEPT_BLOCK | 当前有效尝试的结果通过检查 |
| REJECT_BLOCK | 程序失败、格式错误、尝试编号错误或统计错误 |
| TIMEOUT | 当前尝试到期失效，并进入重派流程 |
| STALE | 过期结果被忽略 |
| KILL | 仍不退出的过期进程被终止并回收 |
| COMPLETE | 所有块检查通过，最终结果已写入 |

还可演示 `wrong`、`crash`、`hang`、`duplicate`、`malformed`、`wrong-attempt`、`always-wrong`。这些是内置故障注入模式，不是完整安全测试。`always-wrong` 应失败，不产生最终结果。

## 本轮固定规则

- 最多两个计算进程同时存在，过期而尚未退出的进程也占用一个名额。每次分块尝试创建一个新进程，不是常驻节点。
- 输入为六种 ASCII 空白字符分隔的十进制整数；不允许加号、前导零或负零。
- 输入非空，最多 100,000 个整数，各在 -1,000,000,000 至 1,000,000,000 之间；输入文件最多 2,000,000 字节。
- 分块大小为 1 至 100,000，最后一块可以不足指定大小。结果文件最多 12,000,000 字节，单次尝试输出只读取最多 256 字节并拒绝超限内容。
- 输入先被读取并规范化保存；本次运行按内存中的输入和固定分块大小检查结果。
- 超时或错误结果可重派；总尝试次数包含首次执行，可配置为 1 至 5 次，演示和正常故障测试使用 2 次。
- 超时以后，即使旧结果正确也不能被接受。期限以调度器观察时的单调时钟为准。
- 过期进程保留到启动后的三倍期限，以测试迟到结果；到时仍不退出则终止并回收。始终不突破两个进程的上限。
- 每块只能接受一次；全部通过后按块号合并，再检查一次，最后将临时结果改名为 `results.txt`。任一块耗尽尝试次数，整个任务失败。
- 运行目录必须是新目录，拒绝覆盖或恢复已有目录。普通错误返回时会终止并回收本调度器启动的剩余计算进程。

## 程序入口与结果格式

```sh
build/worker examples/input.txt 4 > build/results.txt
target/debug/aclt-minimal-verifier examples/input.txt 4 build/results.txt

target/debug/coordinator examples/input.txt 4 build/worker build/my-new-run normal 500 2
```

汇总结果每行依次是：块编号、起始位置、数量、总和、最小值、最大值。块编号和位置从零开始。单块进程额外输出尝试编号，由调度器检查后移除。

## 今天的完成边界

本轮已验证单台机器上两种语言的计算一致性、真实子进程调度、超时重派、旧结果拒绝、错误结果拒绝、尝试次数上限及普通失败后的进程清理。完整证据见 [测试报告](docs/TEST-REPORT.md)。

验证器会完整重算，且每个计算进程仍读取整份输入；本轮不证明速度或成本优势。两个进程也不是两个独立的参与者。

尚未实现：调度器崩溃或断电后的恢复、真实网络、任务摘要与签名、参与者身份、敌对程序隔离、持续运行的节点、付款或模拟账务。输入快照不防同一用户恶意改文件；事件日志也不是防篡改审计记录。临时文件改名不等于断电持久性保证。若调度器被强制终止，需由操作系统或操作者清理残留进程。

下一步先接回原 ACLt 仓库，把本试验对应到既有规则；如继续开发，优先增加调度器中断后的恢复，之后再考虑两台物理电脑。
