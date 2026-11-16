# 原定第四项第二片：Q 校准方法与敏感性记录

日期：2026-10-26（Europe/Budapest）；标识 BQ-W4-S2。第二片在方法、输入契约、合成条件校准和敏感性范围完成，结论见下文“完成范围与下一片”。
Git 基线：`3a001ddba707ce50c0afef472d43043a244522b0`；本轮开始时已有前两轮候选迁移材料与 BQ-W4-S1 的未提交内容，均纳入 439 文件快照后保留。本轮不提交、推送、迁移旧数据或改变旧数学内核。

## 本轮结果

[研究正文](../06-research/bq-calibration-slice2.md)、[完整机器结果](bq-calibration-slice2-20261026.json)、[14 项新回归](../../tests/bq_calibration/test_calibration.py)和封闭的[合成输入](../../tests/bq_calibration/fixtures/synthetic-v1.json)共同交付。代码只接受 synthetic 研究输入，不提供真实观察数据适配或生产审批。

- 精确二项式下尾与独立 Bernoulli DP 对拍；多项分布全枚举核验有限候选家族选择后的误校准控制。α、δQ、δL、εF 的角色分别记录。
- 人工零失败样例中，α=δQ=1/20：单 Q 的最小样本量 59；三候选 Q 的保守 Bonferroni 方案为 80；58 或三候选下 60 个样本均不足以取得对应证书，不据此断言真实性能差。
- 同任务/已知共享依赖 block、scope 变化、非独立真值或事后挑选均有拒绝；固定期限无支持保留为失败，不丢任务。不同 block ID、scope 哈希和 iid 声明不等于来源证据。
- 五组压力分析有 5 个漏计能力点、4 个支持损失点、3 个共同故障点、3 个外生 TV 点，以及 20 个未来参数/预算网格。所有隐藏规模和概率均是给定值，不是实测估计。
- 另进程实际运行四项不合法 CLI 输入：scope-drift、shared-block、majority-truth、postselection，全部非零拒绝、没有生成成功报告；原输入和日志留存。

PASS 仅指研究重现与对拍通过，不是实际 Q、B、iid 或 deployment assurance 已建立。所有报告固定标示不自动获得部署资格、不估 B、不完成现实校准；已接受的条件数学定理和 Profile 准入不变。

## 验证与复现

14 项局部新回归通过，暂存及安装后默认 `make check` 各 290 项通过。文档链接、封闭字段/源码 pin、两个最终另进程报告一致性、安装/归档摘要、清单与 diff 核验通过；再用已安装源码生成第三份相同最终报告。初稿输出与最终字段标签修订分开保留，不把初稿摘要当最终 source pin。

```sh
make check-bq-calibration
make test-bq-calibration BQ_CALIBRATION_REPORT=/existing-parent/new-report.json
```

显式输入可用 `python3 -B scripts/check-bq-calibration.py --dataset /saved/synthetic.json --report /existing-parent/new.json`。拒绝重复 JSON key、浮点/NaN、未知/缺失字段和覆盖旧报告。metadata 不构成签名认证或校准预登记。旧第一片与递推/闭式/original vectors/manifest 原字节保留；本轮只新增标准库研究路径与相应默认回归。

本轮未安装软件、下载代码、运行 guest/编译器、SSH、VM 或真实网络/主机故障，不把局部统计研究计作双机来源证据。NIST S17 官方页仅复核精确二项式方法背景，没有第三方实现代码。

操作者本地 `<EVIDENCE_ROOT>/bq-work4-slice2-20261026/` 保存起始未提交状态/文件 pin、局部与完整检查、两份最终重现、四项拒绝控制、安装备份及交付核验。源码包无凭据、数据库或运行密钥。

## 完成范围与下一片

第二片在“方法、输入契约、合成条件校准、敏感性”范围完成；真实独立真值数据、任务 iid、B 能力全集、外推距离及部署审核留待建立。有限样本置信 α 不替换 δQ，联合界不构成条件于通过后的后验保证。

下一片整理 bounded/audit-only/禁用的证据与降级条件，绑定 B、Q/α、抽样来源、预算/损失、有效期、撤销和拒绝原因；无现实证据的项明确保留未建立。OQ、Gate、SemanticStatus、V1 处置与 ADR-0006/0007 状态保持原状；不依赖 B/Q 的 RIR/运行时实现可以继续推进。
