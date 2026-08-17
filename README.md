# ACLt
An Distributed Computing Solution

[中文 v0.4 文档](https://github.com/tenneidp/RUDCP/blob/main/Project_DOcuments/Cooperate_Files/RUDCP_%E5%AE%8C%E6%95%B4%E9%A1%B9%E7%9B%AE%E6%80%9D%E8%B7%AF%E6%9E%B6%E6%9E%84%E4%B8%8E%E8%AE%BA%E8%AF%81%E6%98%A0%E5%B0%84_v0.4_%E4%B8%AD%E6%96%87.md)

[English v0.4 Documentation](https://github.com/tenneidp/RUDCP/blob/main/Project_DOcuments/Cooperate_Files/RUDCP_Complete_Project_Architecture_and_Argument_Mapping_v0.4_EN.md)

## Repository Structure

本项目采用单仓库结构，以协议定义、形式化规范和安全分析为核心。现阶段只创建实际需要的目录；候选组件只有在证明其必要性后才加入仓库，以贯彻“如无必要勿增实体”的设计原则。

```text
distributed-compute/
├── README.md                       # 项目简介、快速开始与文档入口
├── LICENSE                         # 开源许可证
├── CONTRIBUTING.md                 # 贡献规范
├── SECURITY.md                     # 安全政策与漏洞披露流程
├── CODE_OF_CONDUCT.md              # 社区行为准则
├── CHANGELOG.md                    # 版本变更记录
├── CITATION.cff                    # 学术引用信息
│
├── docs/                           # 项目的权威文档中心
│   ├── README.md                   # 文档索引、阅读顺序与状态说明
│   │
│   ├── 00-overview/                # 项目总览
│   │   ├── project-overview.md     # 项目目标、适用范围与非目标
│   │   ├── design-principles.md    # 核心设计原则
│   │   ├── terminology.md          # 统一术语与符号定义
│   │   └── system-context.md       # 系统环境、参与者与外部依赖
│   │
│   ├── 01-requirements/            # 系统要求与基本假设
│   │   ├── functional.md           # 功能需求
│   │   ├── non-functional.md       # 安全、性能、可用性等要求
│   │   ├── threat-model.md         # 威胁模型与攻击者能力
│   │   └── invariants.md           # 系统必须始终满足的不变量
│   │
│   ├── 02-architecture/            # 系统架构
│   │   ├── system-architecture.md  # 完整系统架构
│   │   ├── identities-and-roles.md # 身份组、职能与权限边界
│   │   ├── trust-model.md          # 信任模型与信任边界
│   │   ├── task-lifecycle.md       # 任务或仓单的完整生命周期
│   │   ├── data-model.md           # 核心数据结构及其关系
│   │   └── protocol-flow.md        # 主要协议交互流程
│   │
│   ├── 03-protocol/                # 协议设计
│   │   ├── protocol-spec.md        # 规范性协议正文
│   │   ├── task-assignment.md      # 任务分配算法
│   │   ├── result-validation.md    # 结果验证与最大验证轮机制
│   │   ├── reputation.md           # 信用、Rank 与权重机制
│   │   ├── rewards-penalties.md    # 报酬、惩罚与成本核算
│   │   ├── disputes-disclosure.md  # 争议处理与道德披露机制
│   │   └── protocol-parameters.md  # 协议参数、约束及默认值
│   │
│   ├── 04-analysis/                # 理论分析与证明
│   │   ├── robustness.md           # 系统鲁棒性分析
│   │   ├── incentive-compatibility.md
│   │   ├── sybil-resistance.md     # 女巫攻击抵抗能力
│   │   ├── collusion-analysis.md   # 串谋攻击分析
│   │   ├── economic-security.md    # 经济安全与攻击成本
│   │   ├── administrative-cost.md  # 行政成本及其必要性分析
│   │   └── proof-obligations.md    # 待证明命题及证明状态
│   │
│   ├── 05-decisions/               # 架构决策记录（ADR）
│   │   ├── README.md               # ADR 编号、格式与使用规则
│   │   ├── ADR-0001-single-repository.md
│   │   ├── ADR-0002-no-unnecessary-entities.md
│   │   └── ADR-xxxx-template.md    # ADR 模板
│   │
│   ├── 06-research/                # 研究资料与成果归属
│   │   ├── literature-review.md    # 文献综述
│   │   ├── related-systems.md      # 相关系统及对比分析
│   │   ├── claims-and-sources.md   # 系统论断与资料来源对应表
│   │   └── bibliography.bib        # BibTeX 参考文献数据库
│   │
│   ├── 07-roadmap/                 # 项目进度与协作
│   │   ├── current-status.md       # 已确定、暂定与未完成事项
│   │   ├── open-questions.md       # 未解决问题及候选方案
│   │   ├── milestones.md           # 阶段目标与里程碑
│   │   └── collaboration-guide.md  # 合作、分工与交接指南
│   │
│   ├── 08-operations/              # 部署与运行维护
│   │   ├── deployment.md           # 部署方式
│   │   ├── observability.md        # 日志、指标与可观测性
│   │   ├── incident-response.md    # 故障及安全事件响应
│   │   └── governance.md           # 项目治理边界
│   │
│   └── diagrams/                   # 架构图与协议流程图
│       ├── source/                 # Mermaid、PlantUML 等源文件
│       └── exported/               # 导出的 SVG 或 PNG 文件
│
├── spec/                            # 可被实现和测试引用的形式化规范
│   ├── schemas/                     # JSON Schema、Protobuf 等结构定义
│   ├── state-machines/              # 协议状态机
│   ├── algorithms/                  # 规范性算法与伪代码
│   ├── test-vectors/                # 标准输入、输出和边界案例
│   └── protocol-version.md          # 协议版本及兼容性规则
│
├── src/                             # 正式实现
│   ├── core/                        # 不依赖网络和存储的纯协议逻辑
│   ├── node/                        # 通用节点功能
│   ├── verification/                # 验证、复验与结果聚合
│   ├── reputation/                  # 信用和 Rank 计算
│   ├── ledger/                      # 仓单、任务及参与记录
│   ├── economics/                   # 报酬、惩罚和成本模型
│   ├── networking/                  # 节点发现与通信
│   ├── storage/                     # 数据持久化适配层
│   └── api/                         # 对外接口
│
├── simulations/                     # 协议和经济模型仿真
│   ├── scenarios/                   # 正常运行场景
│   ├── attacks/                     # 攻击与异常场景
│   ├── parameters/                  # 仿真参数集
│   ├── notebooks/                   # 探索性分析
│   └── results/                     # 可复现的实验结果
│
├── tests/                           # 自动化测试
│   ├── unit/                        # 单元测试
│   ├── integration/                 # 集成测试
│   ├── protocol/                    # 协议一致性测试
│   ├── adversarial/                 # 对抗性与攻击测试
│   ├── property/                    # 属性测试与不变量测试
│   └── fixtures/                    # 公共测试数据
│
├── tools/                           # 研究及开发辅助工具
│   ├── parameter-analysis/          # 参数敏感性分析
│   ├── data-generation/             # 测试及仿真数据生成
│   └── documentation/               # 文档生成和校验工具
│
├── examples/                        # 最小可运行示例
│   ├── minimal-network/
│   ├── task-provider/
│   └── compute-node/
│
├── config/                          # 配置模板
│   ├── development/
│   ├── simulation/
│   └── production.example/
│
├── scripts/                         # 项目级辅助脚本
│   ├── test.sh
│   ├── simulate.sh
│   └── build-docs.sh
│
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── pull_request_template.md
│   └── workflows/
│
└── .gitignore
```

### Documentation Authority

为避免相同结论分散在多个文件中，每类内容应设置唯一的权威文档。

| 内容 | 权威位置 |
|---|---|
| 项目介绍与快速开始 | `README.md` |
| 项目目标、边界与非目标 | `docs/00-overview/project-overview.md` |
| 核心设计原则 | `docs/00-overview/design-principles.md` |
| 身份组、职能与权限 | `docs/02-architecture/identities-and-roles.md` |
| 完整系统架构 | `docs/02-architecture/system-architecture.md` |
| 规范性协议定义 | `docs/03-protocol/protocol-spec.md` |
| 信用、Rank 与任务权重 | `docs/03-protocol/reputation.md` |
| 验证轮与结果共识 | `docs/03-protocol/result-validation.md` |
| 攻击模型与经济安全论证 | `docs/04-analysis/` |
| 行政成本分析 | `docs/04-analysis/administrative-cost.md` |
| 关键架构决定及其理由 | `docs/05-decisions/` |
| 文献、引用与成果归属 | `docs/06-research/` |
| 当前进度与未决问题 | `docs/07-roadmap/` |
| 机器可读或可验证的协议规范 | `spec/` |
| 仿真实验、参数与结果 | `simulations/` |

### Initial Repository Structure

项目早期不应一次性创建所有候选目录。第一阶段建议仅建立以下最小结构：

```text
distributed-compute/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
│
├── docs/
│   ├── README.md
│   ├── 00-overview/
│   │   ├── project-overview.md
│   │   ├── design-principles.md
│   │   └── terminology.md
│   │
│   ├── 01-requirements/
│   │   ├── threat-model.md
│   │   └── invariants.md
│   │
│   ├── 02-architecture/
│   │   ├── system-architecture.md
│   │   ├── identities-and-roles.md
│   │   └── task-lifecycle.md
│   │
│   ├── 03-protocol/
│   │   ├── protocol-spec.md
│   │   ├── result-validation.md
│   │   └── reputation.md
│   │
│   ├── 04-analysis/
│   │   ├── robustness.md
│   │   └── administrative-cost.md
│   │
│   ├── 05-decisions/
│   │   └── ADR-0001-no-unnecessary-entities.md
│   │
│   ├── 06-research/
│   │   ├── claims-and-sources.md
│   │   └── bibliography.bib
│   │
│   └── 07-roadmap/
│       ├── current-status.md
│       └── open-questions.md
│
├── spec/
│   ├── algorithms/
│   └── state-machines/
│
└── simulations/
    ├── scenarios/
    └── results/
```

### Expansion Rule

`src/`、`tests/`、部署配置、治理机制以及任何具有特殊权限的组件，均应在其需求和边界得到确认后再加入。

新增重要组件前，应至少满足以下条件：

1. 该组件承担的职能已经被明确证明为必要；
2. 该职能不能由现有参与者或公开、确定的协议算法合理完成；
3. 已明确其信任假设、权限范围和失效影响；
4. 已在 `docs/05-decisions/` 中记录对应的架构决策；
5. 已同步更新系统架构、威胁模型和协议规范。

仓库目录不是系统参与者清单。目录可以用于代码组织，但不得因为存在某个目录，就默认系统中必须存在对应的特权实体。
