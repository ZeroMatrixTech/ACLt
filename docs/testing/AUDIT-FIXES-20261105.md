# 2026-11-05 有界审计修复

2026-11-07 补记。本轮依据维护者授权，对 2026-11-05 外部有界审计的已确认项和定点复核结论执行有限修复，修复范围限于已确认项和定点复核结论，不覆盖报告的全部指控。所依据的 [外部审计原文](../08-governance/audits/external/AUDIT-20261105-01.original.txt)已按原字节归档，首次 CI 失败及修复后通过见 [收尾记录](FM-EVIDENCE-CLOSEOUT-20261107.md#github-ci-运行记录)。

基线：main `9cf939838c6d8c59c3568d3b23dd8614b6aefb72`。完整 `make test` 退出 0：默认 391 个 unittest，Claim 29766、FM-S1a 179、FM-S1b 196、RIR 独立核心 161 项对拍及 20 次 sanitizer 通过；同名机器摘要记录确切范围。协议状态、B/Q、V1、OQ/Gate 与正式准入保持原状；主线继续 FM-S3。

## 交付与边界

1. SOURCE-BASELINE.json 原字节保留。[更正记录](SOURCE-BASELINE-correction-20261105.json)保留不可解析原提交和原分支，映射到 `802cd74389d8b338b7fd5b03c985eab769b7c19b`，核对 43 个 pinned files。该对应关系不证明原未知提交的整个树等同于映射提交，不能直接改成 ab9f2334。
2. 评审移到 [REVIEW-20261028](../05-decisions/reviews/REVIEW-20261028-layered.md)，原 ADR-0006 仍是唯一决定载体。ClaimQualifier 维持既有三值，证据类别、条件和优先级分列，命题/严格边界及 SemanticStatus 未因表格整理变更。环境正文就地标明历史缺项已补齐，历史总数加时点，state3 README 改成真实入口和禁止恢复计算的说明；缺档审计诚实登记，归档只加冲突横幅。
3. 三个历史测试 HTTP 控制入口默认 loopback，并需显式私有 token；receiver 默认不启用管理 HTTP。认证先于读取正文或调用签署/状态修改操作；唯一长度、帧上限、重复 JSON key、非 JSON 常量、深度及请求头/体超时均检查。token 只属于本轮测试控制面，不替代 Principal 凭据。原 TCP 数据路径的已有上限/超时保持其范围。
4. 私钥用 O_EXCL/O_NOFOLLOW 及 0600 已打开 fd 生成，不依赖后置 chmod 或 OpenSSL 默认模式。没有宣称已证明本机曾有 0644 窗口。
5. state3 Rust `test-faults` / C++ `ACLT_ENABLE_TEST_FAULTS` 与放宽 registry root 的测试功能分开；部署 debug 产物不含故障环境钩子，测试变体仍通过原故障矩阵。删除不可达恢复计算代码，保留 resume 明确拒绝；旧恢复脚本/报告是历史，不接回门禁。
6. 31 个非 state1/state2 归档树中的 assert 验证模块在 -O/PYTHONOPTIMIZE 下先拒绝，不能跳过断言后生成 PASS；历史 state1/state2 不改写。新增控制面、元数据/源码映射、文档标签/路径/ID、交付范围与确定性打包回归。
7. [交付范围](../../DELIVERY-SCOPE.json)覆盖 AGENTS、历史 state1/state2/codocs 和 CI；未知受管路径不能静默掉出交付。生成目录排除只锚定已知位置；普通 tools/.../build 源文件仍会被清单捕获。源码包无需 .git，Git coverage/source dimension 单独声明，无 .git 时 NOT_RUN。
8. ZIP 采用固定时间/权限/顺序与 ZIP_STORED，测试不同输出名和源文件 mtime 下字节一致。清单仍是内容一致性机制，没有新建发布签名/外部信任根。CI 配置固定 checkout action revision、只读权限、不保留凭据，在 PR/main push/手动触发时执行完整本地门禁；本轮未推送或声称 GitHub CI 已运行。完整编译器/OS 内容锁也未完成。

## 回归与原始记录

A 权威/测试服务与 B 客户端采用 DUALHOST-SSH-1 的有限物理双机假设。新的控制面 LAN 回归对三个入口各执行 11 项（共 33 项），覆盖未授权 inject、错令牌、负数/超大/缺失/重复长度、重复 key、NaN、深度、合法只读和请求头超时。默认管理关闭，拒绝不改变业务账本或 worker 数据，guest 调用为零。另以全新部署重跑 FM-S2 17 场景，旧授权、结算和原证据目录未迁移或覆盖。

控制面回归不代表整套旧 multinode/VM 任务矩阵完成；历史 VM boot/image 没有被自动授予新令牌，未经显式适配新入口及完整源码工具依赖时失败关闭。本轮没有运行 VM、改系统服务/网络或触碰小鲸鱼/Codex 进程。

同名 JSON 摘要保存本轮源码/场景及验证范围。本地 `<EVIDENCE_ROOT>/audit-fixes-20261105/` 留存首次开发失败、源码钉扎检测、完整 make 日志、新控制面和 FM-S2 双机目录。旧研究文档被既有证据钉扎，初次回归发现修改它会破坏来源锁，因此恢复原字节；下文只补条件说明，不重写原报告或重算历史摘要。

命令：

```sh
make check
make test
make verify-source  # 完整 Git checkout；离线、不 fetch、不执行历史代码
python3 scripts/check-test-controls.py --output /new/local-run
python3 scripts/check-test-controls.py --peer user@B --a-host A_LAN_IP --remote-root /new/B/path --output /new/A/path
make test-fm-s2 FM_S2_PEER=user@B FM_S2_A_HOST=A_LAN_IP FM_S2_REMOTE_ROOT=/new/B/fm FM_S2_OUTPUT=/new/A/fm
```

## 审计误报与保留问题

Reader 的 decode 字节上限已检查，不重复补检查；required_draws 仍用 Fraction，报告所称的 log/ceil 路径不存在；WAL 仍为串行写者，本次修复不改写事务算法；`open('xb')` 拒绝已有最终符号链接；父目录/SQLite 打开竞态留待另行建模，未使用未经验证的 /proc/fd 封装。canonical JSON 签名契约不因重新编码而成为密码学缺陷。历史身份/路径不批量替换，原证据不以刷新 hash 的方式伪装成未改动。

给定有效 Q 的抽样预算仍由条件活性曲线和 δL 决定。校准好事件上，未来失败风险受 δQ+δL 控制；跨校准与未来任务，“发布且失败”可保守加 α，该加项不构成给定发布后的后验或条件保证。该澄清不改变条件模型、B/Q 准入或统计算法。

Formal schema/非主网 assurance、四项 audit 接口、完整 RIR/RPR/OS sandbox、恶意宿主、断电、权威回滚/failover、结果判决与权利/退款各自按门槛推进。保护测试控制入口不构成生产部署安全认证。
