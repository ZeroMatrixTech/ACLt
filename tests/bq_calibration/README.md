# B/Q 第二片：固定样本校准研究

14 项标准库回归，`make check-bq-calibration`。合成数据位于 `fixtures/synthetic-v1.json`：80 个声明独立任务、人工 M=8，所有真值均为指定合成 oracle，不是双机采样数据。

精确尾检验与 Bernoulli DP 对拍，选 Q 后的误校准用多项分布枚举；拒绝重复已知 block、scope 漂移、非独立真值、事后挑选/截短、重复 JSON key/浮点。已知正确任务无支持记 null→0，不丢弃。声明不同 block 不证明独立；任何 conditional_pass 都不会启用部署。

运行 `make test-bq-calibration BQ_CALIBRATION_REPORT=/existing-parent/new.json` 或脚本显式 `--dataset`。报告必须新建，包含输入与八个源码文件 pin。只接受封闭 synthetic 研究数据；不估计 B、TV、真实故障率或现实 Q，不支持 optional stopping。

[方法、误差预算及完整边界](../../docs/06-research/bq-calibration-slice2.md)。
