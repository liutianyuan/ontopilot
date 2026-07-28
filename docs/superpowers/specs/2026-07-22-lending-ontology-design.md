# 信贷金融 Ontology 设计文档

**日期：** 2026-07-22  
**目的：** 新增一套信贷/消费金融场景的 ontology，支持演示和模拟，参考奇富科技的个人贷款全流程业务模式。

## 1. 概述

在三阶段决策视角下构建 Ontology：
- **贷前** — 申请提交 → 征信评估 → 审批决策 → 方案仿真对比
- **贷中** — 还款记录追踪 → 风险监控扫描
- **贷后** — 逾期催收案件管理 → 催收策略对比

AI 代理人可在各阶段调用分析函数和仿真对比函数辅助决策。

## 2. Object Types（7个）

### Borrower（借款人）
- `borrowerId`: string (primary_key)
- `name`: string
- `age`: int
- `monthlyIncome`: float — 月收入（元）
- `occupation`: string
- `dti`: float — 债务收入比
- `creditScore`: int — 内部信用评分 (300-850)
- `historicalDefaults`: int — 历史逾期次数
- `region`: string

### LoanApplication（贷款申请）
- `applicationId`: string (primary_key)
- `borrowerId`: string → links to Borrower
- `amount`: float — 申请金额（元）
- `termMonths`: int — 申请期限（月）
- `purpose`: enum [consumption, business, education, medical, debt_consolidation]
- `status`: enum [pending, under_review, approved, rejected]
- `appliedAt`: datetime
- links: `submittedBy` → Borrower

### CreditReport（征信报告）
- `reportId`: string (primary_key)
- `applicationId`: string → links to LoanApplication
- `creditScore`: int — 征信分数 (300-900)
- `inquiryCount6m`: int — 近6个月查询次数
- `existingDebt`: float — 现有负债总额
- `overdueHistory`: int — 近2年逾期月份数
- `fraudFlag`: bool — 反欺诈标记
- links: `assessedFor` → LoanApplication

### LoanContract（贷款合同）
- `contractId`: string (primary_key)
- `applicationId`: string → links to LoanApplication
- `borrowerId`: string → links to Borrower
- `principal`: float — 合同本金
- `annualRate`: float — 年利率（如 0.072 表示 7.2%）
- `termMonths`: int — 期限（月）
- `monthlyPayment`: float — 月供
- `totalInterest`: float — 总利息
- `status`: enum [active, paid_off, defaulted, restructured]
- `originatedAt`: datetime — 放款日期
- links: `approvedFrom` → LoanApplication, `belongsTo` → Borrower

### RepaymentPlan（还款计划）
- `planId`: string (primary_key)
- `contractId`: string → links to LoanContract
- `totalPeriods`: int — 总期数
- `monthlyPayment`: float — 每期应还金额
- `remainingPrincipal`: float — 剩余本金
- links: `hasPlan` → LoanContract

### RepaymentRecord（还款记录）
- `recordId`: string (primary_key)
- `contractId`: string → links to LoanContract
- `period`: int — 第几期
- `dueDate`: datetime
- `paidDate`: datetime (nullable)
- `paidAmount`: float
- `status`: enum [on_time, late, missed, upcoming]
- links: `belongsTo` → LoanContract

### CollectionCase（催收案件）
- `caseId`: string (primary_key)
- `contractId`: string → links to LoanContract
- `borrowerId`: string → links to Borrower
- `overdueDays`: int
- `outstandingAmount`: float — 欠款总额
- `strategy`: enum [sms, phone_call, legal_notice, door_visit, external_agency] — 当前催收策略
- `status`: enum [open, in_progress, resolved, written_off]
- `assignedTo`: string — 催收人员
- `openedAt`: datetime
- links: `triggeredBy` → LoanContract, `subjectOf` → Borrower

## 3. Actions（8个）

| Action | 目标类型 | creates | edits | requires_confirmation |
|---|---|---|---|---|
| submitApplication | LoanApplication | true | — | true |
| runCreditCheck | CreditReport | true | — | false |
| approveLoan | LoanContract | true | — | true |
| rejectLoan | LoanApplication | — | status: rejected | true |
| adjustLoanTerms | LoanContract | — | annualRate / termMonths / principal | true |
| recordRepayment | RepaymentRecord | true | — | false |
| openCollectionCase | CollectionCase | true | — | true |
| applyCollectionStrategy | CollectionCase | — | strategy / status | true |

## 4. Functions（4个）

### 4.1 `assessApplicationRisk` — 贷前风控评估
- **输入：** `applicationId: str`
- **输出：** `{ riskLevel, riskScore, recommendedMaxAmount, reasons, creditScore, dti }`
- **逻辑：**
  - 读取 LoanApplication → Borrower → CreditReport
  - 风险评分模型：征信分低 → +score，DTI 高 → +score，查询次数多 → +score，有历史逾期 → +score
  - 建议最高额度：月收入 × 36 / (1 + DTI)
  - 风险等级：low / medium / high / reject

### 4.2 `evaluateLoanPortfolio` — 贷中风险监控
- **输入：** `filters: dict`（可选 status / overdueMinDays / 日期范围）
- **输出：** `[{ contractId, borrowerName, status, overdueDays, remainingPrincipal, lastPaymentStatus, riskFlags[] }]`
- **逻辑：**
  - 扫描 LoanContract → 关联 RepaymentRecord
  - 风险信号：连续2期 late → flag、已 missed → flag、剩余本金 > 月收入 × 36 → flag
  - 按 overdueDays 降序排列

### 4.3 `compareLoanOptions` — 贷前方案仿真对比
- **输入：** `applicationId: str`, `options: [{ name, annualRate, termMonths, principal }]`
- **输出：** `[{ optionName, monthlyPayment, totalInterest, newDti, affordabilityScore, riskLevel }]`
- **逻辑：**
  - 等额本息公式：月供 = P × r × (1+r)^n / ((1+r)^n - 1)
  - 计算新 DTI = (现有负债月供 + 新月供) / 月收入
  - 可负担评分：DTI < 0.36 → good, 0.36-0.50 → caution, > 0.50 → high_risk
  - 使用 forked store 模拟，不做真实变更

### 4.4 `compareCollectionOptions` — 贷后催收策略对比
- **输入：** `caseId: str`, `options: [{ strategy }]`
- **输出：** `[{ strategy, estimatedRecoveryRate, estimatedRecoveryAmount, estimatedCost, recommendation }]`
- **逻辑：**
  - 简单回款模型：逾期 1-30天 sms 回款率 0.7，phone_call 0.85；31-90天 phone_call 0.5，door_visit 0.65；90+天 door_visit 0.3，external_agency 0.45，legal_notice 0.4
  - 成本模型：sms=5, phone_call=30, door_visit=150, legal_notice=300, external_agency=回款×0.2
  - 返回每个策略的估算值和推荐

## 5. Roles（3个）

### loan-officer（信贷员）
- query_types: [Borrower, LoanApplication, CreditReport, LoanContract, RepaymentPlan, RepaymentRecord]
- functions: [assessApplicationRisk, compareLoanOptions]
- actions: submitApplication, runCreditCheck, approveLoan, rejectLoan, adjustLoanTerms, recordRepayment
- data_scope: {}

### risk-manager（风控经理）
- query_types: 全部类型
- functions: [assessApplicationRisk, evaluateLoanPortfolio, compareLoanOptions, compareCollectionOptions]
- actions: 全部 actions（approveLoan 和 rejectLoan 需要 confirmation）
- data_scope: {}

### admin
- query_types: 全部
- functions: 全部
- actions: 全部（无 confirmation 要求）
- data_scope: {}

## 6. 配套文件

| 文件 | 操作 | 说明 |
|---|---|---|
| `config/lending_ontology.yaml` | 新建 | object_types + actions + functions 定义 |
| `config/lending_permissions.yaml` | 新建 | 3 个角色权限 |
| `config/lending_seed.yaml` | 新建 | 模拟数据（8-10 借款人，12+ 申请/合同，30+ 还款记录，3-5 催收案件） |
| `config/lending_context.yaml` | 新建 | 上下文配置（scoped_query 范围控制） |
| `ontopilot/functions.py` | 修改 | 新增 4 个 `_method` 实现 + `_fns` 注册 + `FUNCTION_PARAMS` |
| `ontopilot/simulation.py` | 修改 | 新增 `LendingSimulator` 或泛化现有 `SingleStepSimulator` |

## 7. 技术约束

- 遵循现有 companion file 命名约定：`lending_ontology.yaml` → 自动发现
- Function 实现用纯 Python 计算，不依赖外部 API
- 仿真使用 `store.fork()` 机制，与现有 `compareDecisions` 一致
- 前端完全 ontology-agnostic，无需修改
- 等额本息计算公式必须精确：`M = P × r × (1+r)^n / ((1+r)^n - 1)`，其中 `r = annualRate / 12`
