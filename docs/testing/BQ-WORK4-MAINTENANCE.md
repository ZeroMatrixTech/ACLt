# B/Q 三片研究：运行、复核与交接

本页给出 B/Q 三片研究的本地运行、复核与交接入口，仅使用现有 Python 标准库，不依赖下载、编译器、guest、SSH、VM 或数据库。运行范围限于本地数学与文件研究，部署审批另行处理。三片正文见[收尾报告](BQ-WORK4-CLOSEOUT-20261026.md)。

```sh
make check
make test-bq-work4 BQ_WORK4_OUTPUT=/existing-parent/new-run
python3 -B scripts/bq-work4.py verify \
  --evidence /saved/new-run --report /existing-parent/new-verification.json
```

run 输出必须是仓库外新目录，拒绝覆盖已有根。verify 报告必须新建且位于原证据根之外，核对时会在临时目录重算三片的确定性数学结果，不改写保存证据。当前源码/报告/工件改变、文件缺失、symlink/不安全路径或 suite 结论漂移时拒绝；先登记变更并新跑，不补写旧 PASS。

运行根保留：source-lock.json、三个 slice 的原始 JSON/日志、inventory.json 和 suite.json。独立 verify 报告放根外。25 文件锁包括三个原始报告声明的源码与旧工件，以及统一入口/回归；它们不是认证根、独立实现数或新任务样本数。

保持三片代码/fixture/旧数学模型与原始 source pin 对应。若有意修改算法/范围，使用新算法 ID/证据并保留旧失败/成功记录，不能仅更新 hash 来保留旧结论。篡改者即使重算保存文件清单，仍需通过与当前源码/原始报告及重计算结果的一致性检查；这不抵抗可信仓库本身被攻破。

分片入口仍可独立运行：

```sh
make check-bq-boundaries
make check-bq-calibration
make check-bq-readiness
```

合成样例、非权威审阅状态不代表现实校准/来源已建立；所有资格开关、终态与资金保持不变。失效处置按现行规范，不能在同一 Receipt 换 Profile 或因到期/断连自动重算、退款/改判。

本地 commit 的校验在仅含本次提交的副本上重跑；保留在工作区的 ADR-0007/迁移草案不属于 B/Q commit。用户手动推送后可用 commit 内容审查，避免把未提交草案误认为分支已交付的一部分。
