# 文档导航维护记录

> 审计编号：AUDIT-20261013-01  
> 日期：2026-10-13（Europe/Budapest）  
> 类别：限域文档变更检查  
> 审计者：Codex  
> 基线提交：`c0e0800d720d147bcbd87ffda88df2dd45d1975b`  
> 程序：[审计程序](../audit-procedure.md)

## 目标与权限

用户要求维护四个仓库文档，本记录仅覆盖 ACLt。授权准备并落地本地文档修改；不提交、推送或发布。开始时仓库工作区干净。排除历史报告正文、协议语义修改和 Gate 退出评估。

## 发现与修订

| 发现 | 修订文件 | 状态 |
|---|---|---|
| 实验索引只列单机版本，未收录已存在的多节点原型 | `experiments/README.md`、根 README、文档中心 | RESOLVED_IN_PREPARED_CHANGE |
| 本地多节点检查与外部 VM 驱动的复现边界缺少统一导航 | `experiments/README.md` | RESOLVED_IN_PREPARED_CHANGE |
| 架构指南和交互演示缺少文档中心入口 | `docs/README.md` | RESOLVED_IN_PREPARED_CHANGE |
| 旧维护报告被称作“本轮” | 根 README、文档中心 | RESOLVED_IN_PREPARED_CHANGE |

## 连续性与边界

协议语义、v0.5 基线、V1 Profile、ADR、威胁与不变量不变，未提升 G0–G6。多节点可运行不证明身份独立、Sybil 抵抗、共识或权威磁盘回滚保护。历史 state2/state3 报告和日期保留，不把历史测试数量写成本次重跑结果。

本次新增本记录；修改根 README、文档中心与实验索引。研究正文、历史档案及许可文本未修改。未核实新的外部法律、商标或依赖事实。

## 检查与结论

对仓库跟踪的 Markdown 文件检查内联相对链接目标；准备变更后没有缺失文件目标。新文档命令对照 `scripts/run-singlehost.sh` 和多节点 `check.py`。新增导航链接均指向已有文件。

语义连续性：限上述文档变更 PASS；Gate 退出：NOT_ASSESSED。本地复查结果另见本轮交付记录；未重跑完整单机套件、VM 故障注入或原始磁盘离线恢复。链接检查未验证公网 URL、Markdown 片段锚点或浏览器渲染。

## 偏离与交付

限域维护记录采用简化格式，未逐项复制完整审计模板；原因是本次只补导航与复现边界，不构成协议、实现或发布审计。不能将本记录用作正式 Gate 审计结论。无独立技术复核或合入签署。本地修改经文件差异与链接回验后交付，Git 提交和推送不在本次范围。
