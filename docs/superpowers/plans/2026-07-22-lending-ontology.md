# 信贷金融 Ontology 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一套信贷金融 ontology，支持贷前风控、贷中监控、贷后催收三阶段演示和决策仿真。

**Architecture:** 纯 YAML 配置 + Python 函数实现。Ontology 定义、权限、种子数据、上下文均为 `config/lending_*.yaml` companion 文件，由现有 `_rebuild_runtime` 自动发现和加载。4 个新函数在 `ontopilot/functions.py` 中实现，通过现有 `call_function` 工具调用，不修改 simulation.py 或 tools.py。

**Tech Stack:** Python (FastAPI backend), YAML, 现有 FunctionRegistry / SchemaRegistry / ObjectStore

## Global Constraints

- 遵循现有 companion file 命名约定：`lending_ontology.yaml` → 自动发现 `lending_seed.yaml`, `lending_permissions.yaml`, `lending_context.yaml`
- 等额本息计算公式必须精确：`M = P × r × (1+r)^n / ((1+r)^n - 1)`，其中 `r = annualRate / 12`
- Function 实现用纯 Python 计算，不依赖外部 API
- 不修改 simulation.py 和 tools.py — 所有 lending 函数通过 `call_function` 调用
- 不修改前端代码
- 种子数据使用真实感的中文姓名和场景

---

### Task 1: Ontology 定义文件

**Files:**
- Create: `config/lending_ontology.yaml`

**Interfaces:**
- Produces: 7 object_types (Borrower, LoanApplication, CreditReport, LoanContract, RepaymentPlan, RepaymentRecord, CollectionCase), 8 actions, 4 functions 的完整 YAML 定义

- [ ] **Step 1: Write `config/lending_ontology.yaml`**

按照设计文档第 2、3、4 节的完整定义，包含所有属性、类型、links、actions 和 functions 声明。

```yaml
# 信贷金融 Ontology — 个人贷款全流程
object_types:

  Borrower:
    description: 借款人
    properties:
      borrowerId:         { type: string, primary_key: true }
      name:               { type: string }
      age:                { type: int }
      monthlyIncome:      { type: float }
      occupation:         { type: string }
      dti:                { type: float }
      creditScore:        { type: int }
      historicalDefaults: { type: int }
      region:             { type: string }

  LoanApplication:
    description: 贷款申请
    properties:
      applicationId: { type: string, primary_key: true }
      borrowerId:   { type: string }
      amount:       { type: float }
      termMonths:   { type: int }
      purpose:      { type: enum, values: [consumption, business, education, medical, debt_consolidation] }
      status:       { type: enum, values: [pending, under_review, approved, rejected] }
      appliedAt:    { type: datetime }
    links:
      submittedBy: { target: Borrower, foreign_key: borrowerId }

  CreditReport:
    description: 征信报告
    properties:
      reportId:        { type: string, primary_key: true }
      applicationId:   { type: string }
      creditScore:     { type: int }
      inquiryCount6m:  { type: int }
      existingDebt:    { type: float }
      overdueHistory:  { type: int }
      fraudFlag:       { type: bool }
    links:
      assessedFor: { target: LoanApplication, foreign_key: applicationId }

  LoanContract:
    description: 贷款合同
    properties:
      contractId:     { type: string, primary_key: true }
      applicationId:  { type: string }
      borrowerId:     { type: string }
      principal:      { type: float }
      annualRate:     { type: float }
      termMonths:     { type: int }
      monthlyPayment: { type: float }
      totalInterest:  { type: float }
      status:         { type: enum, values: [active, paid_off, defaulted, restructured] }
      originatedAt:   { type: datetime }
    links:
      approvedFrom: { target: LoanApplication, foreign_key: applicationId }
      belongsTo:    { target: Borrower, foreign_key: borrowerId }

  RepaymentPlan:
    description: 还款计划
    properties:
      planId:            { type: string, primary_key: true }
      contractId:        { type: string }
      totalPeriods:      { type: int }
      monthlyPayment:    { type: float }
      remainingPrincipal: { type: float }
    links:
      hasPlan: { target: LoanContract, foreign_key: contractId }

  RepaymentRecord:
    description: 还款记录
    properties:
      recordId:   { type: string, primary_key: true }
      contractId: { type: string }
      period:     { type: int }
      dueDate:    { type: datetime }
      paidDate:   { type: datetime, nullable: true }
      paidAmount: { type: float }
      status:     { type: enum, values: [on_time, late, missed, upcoming] }
    links:
      belongsTo: { target: LoanContract, foreign_key: contractId }

  CollectionCase:
    description: 催收案件
    properties:
      caseId:            { type: string, primary_key: true }
      contractId:        { type: string }
      borrowerId:        { type: string }
      overdueDays:       { type: int }
      outstandingAmount: { type: float }
      strategy:          { type: enum, values: [sms, phone_call, legal_notice, door_visit, external_agency] }
      status:            { type: enum, values: [open, in_progress, resolved, written_off] }
      assignedTo:        { type: string }
      openedAt:          { type: datetime }
    links:
      triggeredBy: { target: LoanContract, foreign_key: contractId }
      subjectOf:   { target: Borrower, foreign_key: borrowerId }

actions:

  submitApplication:
    description: "提交贷款申请"
    params:
      borrowerId: { type: string, required: true }
      amount:     { type: float, required: true }
      termMonths: { type: int, required: true }
      purpose:    { type: enum, values: [consumption, business, education, medical, debt_consolidation], required: true }
    target_type: LoanApplication
    creates: true
    requires_confirmation: true

  runCreditCheck:
    description: "对贷款申请执行征信查询，生成征信报告"
    params:
      applicationId: { type: string, required: true }
    target_type: CreditReport
    creates: true
    requires_confirmation: false

  approveLoan:
    description: "审批通过贷款申请，生成合同与还款计划"
    params:
      applicationId: { type: string, required: true }
      annualRate:    { type: float, required: true }
      termMonths:    { type: int, required: true }
      principal:     { type: float, required: true }
    target_type: LoanContract
    creates: true
    requires_confirmation: true

  rejectLoan:
    description: "拒绝贷款申请"
    params:
      applicationId: { type: string, required: true }
      reason:        { type: string, required: true }
    target_type: LoanApplication
    edits: { status: rejected }
    requires_confirmation: true

  adjustLoanTerms:
    description: "调整贷款合同条款（用于利率调整或重组场景）"
    params:
      contractId: { type: string, required: true }
      annualRate: { type: float, required: false }
      termMonths: { type: int, required: false }
      principal:  { type: float, required: false }
      reason:     { type: string, required: true }
    target_type: LoanContract
    edits: { annualRate: annualRate, termMonths: termMonths, principal: principal }
    requires_confirmation: true

  recordRepayment:
    description: "记录一笔还款"
    params:
      contractId: { type: string, required: true }
      period:     { type: int, required: true }
      dueDate:    { type: datetime, required: true }
      paidDate:   { type: datetime, required: true }
      paidAmount: { type: float, required: true }
      status:     { type: enum, values: [on_time, late, missed], required: true }
    target_type: RepaymentRecord
    creates: true
    requires_confirmation: false

  openCollectionCase:
    description: "对逾期合同开启催收案件"
    params:
      contractId: { type: string, required: true }
      reason:     { type: string, required: true }
      strategy:   { type: enum, values: [sms, phone_call, legal_notice, door_visit, external_agency], required: true }
    target_type: CollectionCase
    creates: true
    requires_confirmation: true

  applyCollectionStrategy:
    description: "对催收案件更换催收策略"
    params:
      caseId:   { type: string, required: true }
      strategy: { type: enum, values: [sms, phone_call, legal_notice, door_visit, external_agency], required: true }
      reason:   { type: string, required: true }
    target_type: CollectionCase
    edits: { strategy: strategy }
    requires_confirmation: true

functions:

  assessApplicationRisk:
    description: "对贷款申请进行综合风控评估（征信分+DTI+历史逾期+查询次数）"
    params:
      applicationId: { type: string, required: true }
    returns: "{riskLevel, riskScore, recommendedMaxAmount, reasons, creditScore, dti}"
    permission: assessApplicationRisk

  evaluateLoanPortfolio:
    description: "扫描全部贷款合同的还款状态，识别高风险合同"
    params:
      filters: { type: object, required: false }
    returns: "list[{contractId, borrowerName, status, overdueDays, remainingPrincipal, lastPaymentStatus, riskFlags}]"
    permission: evaluateLoanPortfolio

  compareLoanOptions:
    description: "对比不同贷款方案的月供、总利息、DTI变化与风险评级"
    params:
      applicationId: { type: string, required: true }
      options:       { type: list, required: true }
    returns: "list[{optionName, monthlyPayment, totalInterest, newDti, affordabilityScore, riskLevel}]"
    permission: compareLoanOptions

  compareCollectionOptions:
    description: "对比不同催收策略的预估回款率、回款金额与成本"
    params:
      caseId:  { type: string, required: true }
      options: { type: list, required: true }
    returns: "list[{strategy, estimatedRecoveryRate, estimatedRecoveryAmount, estimatedCost, recommendation}]"
    permission: compareCollectionOptions
```

- [ ] **Step 2: 验证 YAML 能被加载**

```bash
python -c "
import yaml
with open('config/lending_ontology.yaml') as f:
    d = yaml.safe_load(f)
print('object_types:', list(d['object_types'].keys()))
print('actions:', list(d['actions'].keys()))
print('functions:', list(d['functions'].keys()))
"
```

Expected: 7 object_types, 8 actions, 4 functions

- [ ] **Step 3: Commit**

```bash
git add config/lending_ontology.yaml
git commit -m "feat: add lending ontology definition (7 types, 8 actions, 4 functions)"
```

---

### Task 2: 权限与上下文配置文件

**Files:**
- Create: `config/lending_permissions.yaml`
- Create: `config/lending_context.yaml`

**Interfaces:**
- Consumes: lending_ontology.yaml 中的 object type、action、function 名称
- Produces: 3 个角色权限定义 + context_sources 配置

- [ ] **Step 1: Write `config/lending_permissions.yaml`**

```yaml
# Permissions — 信贷金融场景
roles:
  loan_officer:
    query_types: [Borrower, LoanApplication, CreditReport, LoanContract, RepaymentPlan, RepaymentRecord]
    functions: [assessApplicationRisk, compareLoanOptions]
    actions:
      submitApplication:         { requires_confirmation: true }
      runCreditCheck:            { requires_confirmation: false }
      approveLoan:               { requires_confirmation: true }
      rejectLoan:                { requires_confirmation: true }
      adjustLoanTerms:           { requires_confirmation: true }
      recordRepayment:           { requires_confirmation: false }
      openCollectionCase:        { requires_confirmation: true }
      applyCollectionStrategy:   { requires_confirmation: true }
    data_scope: {}

  risk_manager:
    query_types: [Borrower, LoanApplication, CreditReport, LoanContract, RepaymentPlan, RepaymentRecord, CollectionCase]
    functions: [assessApplicationRisk, evaluateLoanPortfolio, compareLoanOptions, compareCollectionOptions]
    actions:
      submitApplication:         { requires_confirmation: true }
      runCreditCheck:            { requires_confirmation: false }
      approveLoan:               { requires_confirmation: true }
      rejectLoan:                { requires_confirmation: true }
      adjustLoanTerms:           { requires_confirmation: true }
      recordRepayment:           { requires_confirmation: false }
      openCollectionCase:        { requires_confirmation: true }
      applyCollectionStrategy:   { requires_confirmation: false }
    data_scope: {}

  admin:
    query_types: [Borrower, LoanApplication, CreditReport, LoanContract, RepaymentPlan, RepaymentRecord, CollectionCase]
    functions: [assessApplicationRisk, evaluateLoanPortfolio, compareLoanOptions, compareCollectionOptions]
    actions:
      submitApplication:         { requires_confirmation: false }
      runCreditCheck:            { requires_confirmation: false }
      approveLoan:               { requires_confirmation: false }
      rejectLoan:                { requires_confirmation: false }
      adjustLoanTerms:           { requires_confirmation: false }
      recordRepayment:           { requires_confirmation: false }
      openCollectionCase:        { requires_confirmation: false }
      applyCollectionStrategy:   { requires_confirmation: false }
    data_scope: {}
```

- [ ] **Step 2: Write `config/lending_context.yaml`**

```yaml
# Context sources for lending — 信贷金融场景上下文
context_sources:
  - type: scoped_query
    object_type: LoanApplication
    filters:
      status: [pending, under_review]
    properties:
      - applicationId
      - borrowerId
      - amount
      - termMonths
      - purpose
      - status
      - appliedAt
    max_objects: 20

  - type: scoped_query
    object_type: LoanContract
    filters:
      status: [active, defaulted]
    properties:
      - contractId
      - applicationId
      - borrowerId
      - principal
      - annualRate
      - termMonths
      - monthlyPayment
      - status
      - originatedAt
    max_objects: 20

  - type: scoped_query
    object_type: CollectionCase
    filters:
      status: [open, in_progress]
    properties:
      - caseId
      - contractId
      - borrowerId
      - overdueDays
      - outstandingAmount
      - strategy
      - status
      - assignedTo
      - openedAt
    max_objects: 20
```

- [ ] **Step 3: Commit**

```bash
git add config/lending_permissions.yaml config/lending_context.yaml
git commit -m "feat: add lending permissions (3 roles) and context config"
```

---

### Task 3: 种子数据文件

**Files:**
- Create: `config/lending_seed.yaml`

**Interfaces:**
- Consumes: lending_ontology.yaml 中的 object type 定义
- Produces: 8 借款人、12 贷款申请、10 合同、10 还款计划、35 条还款记录、4 催收案件的 YAML 种子数据

- [ ] **Step 1: Write `config/lending_seed.yaml`**

数据设计覆盖三个决策阶段的演示场景：

```yaml
# Lending seed data — 信贷金融场景测试数据

Borrower:
  - borrowerId: BOR-001
    name: 张伟
    age: 32
    monthlyIncome: 18000.0
    occupation: 软件工程师
    dti: 0.25
    creditScore: 720
    historicalDefaults: 0
    region: 北京

  - borrowerId: BOR-002
    name: 李婷
    age: 28
    monthlyIncome: 12000.0
    occupation: 市场专员
    dti: 0.40
    creditScore: 650
    historicalDefaults: 1
    region: 上海

  - borrowerId: BOR-003
    name: 王强
    age: 45
    monthlyIncome: 25000.0
    occupation: 企业主
    dti: 0.55
    creditScore: 580
    historicalDefaults: 3
    region: 广州

  - borrowerId: BOR-004
    name: 赵芳
    age: 35
    monthlyIncome: 15000.0
    occupation: 教师
    dti: 0.20
    creditScore: 780
    historicalDefaults: 0
    region: 深圳

  - borrowerId: BOR-005
    name: 陈明
    age: 24
    monthlyIncome: 8000.0
    occupation: 应届生
    dti: 0.15
    creditScore: 620
    historicalDefaults: 0
    region: 杭州

  - borrowerId: BOR-006
    name: 刘洋
    age: 38
    monthlyIncome: 20000.0
    occupation: 销售经理
    dti: 0.48
    creditScore: 610
    historicalDefaults: 2
    region: 成都

  - borrowerId: BOR-007
    name: 孙丽
    age: 30
    monthlyIncome: 16000.0
    occupation: 医生
    dti: 0.30
    creditScore: 750
    historicalDefaults: 0
    region: 南京

  - borrowerId: BOR-008
    name: 周杰
    age: 52
    monthlyIncome: 10000.0
    occupation: 出租车司机
    dti: 0.60
    creditScore: 520
    historicalDefaults: 5
    region: 武汉

LoanApplication:
  # ── 待审申请 ──
  - applicationId: APP-001
    borrowerId: BOR-001
    amount: 150000.0
    termMonths: 36
    purpose: consumption
    status: under_review
    appliedAt: "2026-07-15T10:00:00+00:00"

  - applicationId: APP-002
    borrowerId: BOR-002
    amount: 80000.0
    termMonths: 24
    purpose: education
    status: under_review
    appliedAt: "2026-07-16T14:00:00+00:00"

  - applicationId: APP-003
    borrowerId: BOR-003
    amount: 200000.0
    termMonths: 48
    purpose: business
    status: under_review
    appliedAt: "2026-07-14T09:00:00+00:00"

  - applicationId: APP-004
    borrowerId: BOR-005
    amount: 50000.0
    termMonths: 12
    purpose: consumption
    status: under_review
    appliedAt: "2026-07-18T11:00:00+00:00"

  # ── 已批准（转合同） ──
  - applicationId: APP-005
    borrowerId: BOR-004
    amount: 120000.0
    termMonths: 36
    purpose: medical
    status: approved
    appliedAt: "2026-04-01T08:00:00+00:00"

  - applicationId: APP-006
    borrowerId: BOR-006
    amount: 180000.0
    termMonths: 60
    purpose: debt_consolidation
    status: approved
    appliedAt: "2026-03-15T10:00:00+00:00"

  - applicationId: APP-007
    borrowerId: BOR-007
    amount: 100000.0
    termMonths: 24
    purpose: consumption
    status: approved
    appliedAt: "2026-05-20T13:00:00+00:00"

  - applicationId: APP-008
    borrowerId: BOR-001
    amount: 80000.0
    termMonths: 12
    purpose: consumption
    status: approved
    appliedAt: "2026-06-01T09:00:00+00:00"

  - applicationId: APP-009
    borrowerId: BOR-002
    amount: 60000.0
    termMonths: 18
    purpose: education
    status: approved
    appliedAt: "2026-05-10T15:00:00+00:00"

  - applicationId: APP-010
    borrowerId: BOR-008
    amount: 200000.0
    termMonths: 60
    purpose: business
    status: approved
    appliedAt: "2026-02-01T10:00:00+00:00"

  # ── 已拒绝 ──
  - applicationId: APP-011
    borrowerId: BOR-008
    amount: 300000.0
    termMonths: 60
    purpose: business
    status: rejected
    appliedAt: "2026-01-10T09:00:00+00:00"

  - applicationId: APP-012
    borrowerId: BOR-003
    amount: 500000.0
    termMonths: 120
    purpose: business
    status: rejected
    appliedAt: "2026-02-20T11:00:00+00:00"

CreditReport:
  - reportId: CR-001
    applicationId: APP-001
    creditScore: 735
    inquiryCount6m: 2
    existingDebt: 50000.0
    overdueHistory: 0
    fraudFlag: false

  - reportId: CR-002
    applicationId: APP-002
    creditScore: 660
    inquiryCount6m: 4
    existingDebt: 80000.0
    overdueHistory: 1
    fraudFlag: false

  - reportId: CR-003
    applicationId: APP-003
    creditScore: 545
    inquiryCount6m: 8
    existingDebt: 300000.0
    overdueHistory: 5
    fraudFlag: false

  - reportId: CR-004
    applicationId: APP-004
    creditScore: 625
    inquiryCount6m: 1
    existingDebt: 10000.0
    overdueHistory: 0
    fraudFlag: false

LoanContract:
  # ── 正常还款 ──
  - contractId: CT-001
    applicationId: APP-005
    borrowerId: BOR-004
    principal: 120000.0
    annualRate: 0.065
    termMonths: 36
    monthlyPayment: 3677.39
    totalInterest: 12386.09
    status: active
    originatedAt: "2026-04-15T10:00:00+00:00"

  - contractId: CT-002
    applicationId: APP-007
    borrowerId: BOR-007
    principal: 100000.0
    termMonths: 24
    annualRate: 0.058
    monthlyPayment: 4425.58
    totalInterest: 6213.92
    status: active
    originatedAt: "2026-06-01T09:00:00+00:00"

  - contractId: CT-003
    applicationId: APP-008
    borrowerId: BOR-001
    principal: 80000.0
    termMonths: 12
    annualRate: 0.052
    monthlyPayment: 6858.51
    totalInterest: 2302.14
    status: active
    originatedAt: "2026-06-15T10:00:00+00:00"

  # ── 开始逾期 ──
  - contractId: CT-004
    applicationId: APP-006
    borrowerId: BOR-006
    principal: 180000.0
    termMonths: 60
    annualRate: 0.088
    monthlyPayment: 3725.61
    totalInterest: 43536.53
    status: active
    originatedAt: "2026-04-01T10:00:00+00:00"

  - contractId: CT-005
    applicationId: APP-009
    borrowerId: BOR-002
    principal: 60000.0
    termMonths: 18
    annualRate: 0.072
    monthlyPayment: 3595.32
    totalInterest: 4715.69
    status: active
    originatedAt: "2026-05-25T14:00:00+00:00"

  # ── 严重逾期/违约 ──
  - contractId: CT-006
    applicationId: APP-010
    borrowerId: BOR-008
    principal: 200000.0
    termMonths: 60
    annualRate: 0.105
    monthlyPayment: 4289.37
    totalInterest: 57362.20
    status: defaulted
    originatedAt: "2026-02-15T10:00:00+00:00"

  # ── 已结清 ──
  - contractId: CT-007
    applicationId: APP-008
    borrowerId: BOR-001
    principal: 50000.0
    termMonths: 12
    annualRate: 0.048
    monthlyPayment: 4277.85
    totalInterest: 1334.17
    status: paid_off
    originatedAt: "2025-06-01T09:00:00+00:00"

  # ── 重组合同 ──
  - contractId: CT-008
    applicationId: APP-006
    borrowerId: BOR-006
    principal: 150000.0
    termMonths: 36
    annualRate: 0.095
    monthlyPayment: 4804.86
    totalInterest: 22975.02
    status: restructured
    originatedAt: "2026-05-01T10:00:00+00:00"

RepaymentPlan:
  - planId: PLAN-001
    contractId: CT-001
    totalPeriods: 36
    monthlyPayment: 3677.39
    remainingPrincipal: 105000.0

  - planId: PLAN-002
    contractId: CT-002
    totalPeriods: 24
    monthlyPayment: 4425.58
    remainingPrincipal: 80000.0

  - planId: PLAN-003
    contractId: CT-003
    totalPeriods: 12
    monthlyPayment: 6858.51
    remainingPrincipal: 60000.0

  - planId: PLAN-004
    contractId: CT-004
    totalPeriods: 60
    monthlyPayment: 3725.61
    remainingPrincipal: 175000.0

  - planId: PLAN-005
    contractId: CT-005
    totalPeriods: 18
    monthlyPayment: 3595.32
    remainingPrincipal: 50000.0

  - planId: PLAN-006
    contractId: CT-006
    totalPeriods: 60
    monthlyPayment: 4289.37
    remainingPrincipal: 190000.0

  - planId: PLAN-007
    contractId: CT-007
    totalPeriods: 12
    monthlyPayment: 4277.85
    remainingPrincipal: 0.0

  - planId: PLAN-008
    contractId: CT-008
    totalPeriods: 36
    monthlyPayment: 4804.86
    remainingPrincipal: 140000.0

RepaymentRecord:
  # ── CT-001 正常还款（赵芳，已还3期）──
  - recordId: REC-00101
    contractId: CT-001
    period: 1
    dueDate: "2026-05-15T10:00:00+00:00"
    paidDate: "2026-05-14T09:00:00+00:00"
    paidAmount: 3677.39
    status: on_time

  - recordId: REC-00102
    contractId: CT-001
    period: 2
    dueDate: "2026-06-15T10:00:00+00:00"
    paidDate: "2026-06-15T08:00:00+00:00"
    paidAmount: 3677.39
    status: on_time

  - recordId: REC-00103
    contractId: CT-001
    period: 3
    dueDate: "2026-07-15T10:00:00+00:00"
    paidDate: "2026-07-14T10:00:00+00:00"
    paidAmount: 3677.39
    status: on_time

  - recordId: REC-00104
    contractId: CT-001
    period: 4
    dueDate: "2026-08-15T10:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: upcoming

  # ── CT-002 正常还款（孙丽，已还2期）──
  - recordId: REC-00201
    contractId: CT-002
    period: 1
    dueDate: "2026-07-01T09:00:00+00:00"
    paidDate: "2026-06-30T15:00:00+00:00"
    paidAmount: 4425.58
    status: on_time

  - recordId: REC-00202
    contractId: CT-002
    period: 2
    dueDate: "2026-08-01T09:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: upcoming

  # ── CT-003 正常还款（张伟，已还1期）──
  - recordId: REC-00301
    contractId: CT-003
    period: 1
    dueDate: "2026-07-15T10:00:00+00:00"
    paidDate: "2026-07-15T10:00:00+00:00"
    paidAmount: 6858.51
    status: on_time

  - recordId: REC-00302
    contractId: CT-003
    period: 2
    dueDate: "2026-08-15T10:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: upcoming

  # ── CT-004 开始逾期（刘洋，已还4期，最近2期问题）──
  - recordId: REC-00401
    contractId: CT-004
    period: 1
    dueDate: "2026-05-01T10:00:00+00:00"
    paidDate: "2026-05-02T10:00:00+00:00"
    paidAmount: 3725.61
    status: late

  - recordId: REC-00402
    contractId: CT-004
    period: 2
    dueDate: "2026-06-01T10:00:00+00:00"
    paidDate: "2026-06-05T10:00:00+00:00"
    paidAmount: 3725.61
    status: late

  - recordId: REC-00403
    contractId: CT-004
    period: 3
    dueDate: "2026-07-01T10:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: missed

  - recordId: REC-00404
    contractId: CT-004
    period: 4
    dueDate: "2026-08-01T10:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: upcoming

  # ── CT-005 开始逾期（李婷，已还2期，最新迟还）──
  - recordId: REC-00501
    contractId: CT-005
    period: 1
    dueDate: "2026-06-25T14:00:00+00:00"
    paidDate: "2026-06-26T10:00:00+00:00"
    paidAmount: 3595.32
    status: late

  - recordId: REC-00502
    contractId: CT-005
    period: 2
    dueDate: "2026-07-25T14:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: missed

  - recordId: REC-00503
    contractId: CT-005
    period: 3
    dueDate: "2026-08-25T14:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: upcoming

  # ── CT-006 严重违约（周杰，已还3期后全部missed）──
  - recordId: REC-00601
    contractId: CT-006
    period: 1
    dueDate: "2026-03-15T10:00:00+00:00"
    paidDate: "2026-03-16T10:00:00+00:00"
    paidAmount: 4289.37
    status: late

  - recordId: REC-00602
    contractId: CT-006
    period: 2
    dueDate: "2026-04-15T10:00:00+00:00"
    paidDate: "2026-04-20T10:00:00+00:00"
    paidAmount: 4289.37
    status: late

  - recordId: REC-00603
    contractId: CT-006
    period: 3
    dueDate: "2026-05-15T10:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: missed

  - recordId: REC-00604
    contractId: CT-006
    period: 4
    dueDate: "2026-06-15T10:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: missed

  - recordId: REC-00605
    contractId: CT-006
    period: 5
    dueDate: "2026-07-15T10:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: missed

  # ── CT-007 已结清（张伟，12期全部按时还清）──
  - recordId: REC-00701
    contractId: CT-007
    period: 1
    dueDate: "2025-07-01T09:00:00+00:00"
    paidDate: "2025-06-28T10:00:00+00:00"
    paidAmount: 4277.85
    status: on_time

  - recordId: REC-00711
    contractId: CT-007
    period: 11
    dueDate: "2026-05-01T09:00:00+00:00"
    paidDate: "2026-04-30T10:00:00+00:00"
    paidAmount: 4277.85
    status: on_time

  - recordId: REC-00712
    contractId: CT-007
    period: 12
    dueDate: "2026-06-01T09:00:00+00:00"
    paidDate: "2026-05-30T10:00:00+00:00"
    paidAmount: 4277.85
    status: on_time

  # ── CT-008 重组合同（刘洋，已还3期，开始有逾期迹象）──
  - recordId: REC-00801
    contractId: CT-008
    period: 1
    dueDate: "2026-06-01T10:00:00+00:00"
    paidDate: "2026-06-02T10:00:00+00:00"
    paidAmount: 4804.86
    status: late

  - recordId: REC-00802
    contractId: CT-008
    period: 2
    dueDate: "2026-07-01T10:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: missed

  - recordId: REC-00803
    contractId: CT-008
    period: 3
    dueDate: "2026-08-01T10:00:00+00:00"
    paidDate: null
    paidAmount: 0.0
    status: upcoming

CollectionCase:
  # ── 早期逾期 ──
  - caseId: CC-001
    contractId: CT-004
    borrowerId: BOR-006
    overdueDays: 21
    outstandingAmount: 7451.22
    strategy: sms
    status: in_progress
    assignedTo: collector_001
    openedAt: "2026-07-05T10:00:00+00:00"

  # ── 中期逾期 ──
  - caseId: CC-002
    contractId: CT-005
    borrowerId: BOR-002
    overdueDays: 28
    outstandingAmount: 7190.64
    strategy: phone_call
    status: open
    assignedTo: collector_002
    openedAt: "2026-07-20T10:00:00+00:00"

  # ── 严重逾期 ──
  - caseId: CC-003
    contractId: CT-006
    borrowerId: BOR-008
    overdueDays: 120
    outstandingAmount: 34314.96
    strategy: phone_call
    status: in_progress
    assignedTo: collector_001
    openedAt: "2026-06-15T10:00:00+00:00"

  # ── 重组后仍有问题 ──
  - caseId: CC-004
    contractId: CT-008
    borrowerId: BOR-006
    overdueDays: 51
    outstandingAmount: 9609.72
    strategy: door_visit
    status: open
    assignedTo: collector_003
    openedAt: "2026-07-01T10:00:00+00:00"
```

- [ ] **Step 2: 验证种子数据完整性**

```bash
python -c "
import yaml
with open('config/lending_seed.yaml') as f:
    d = yaml.safe_load(f)
for k in ['Borrower', 'LoanApplication', 'CreditReport', 'LoanContract', 'RepaymentPlan', 'RepaymentRecord', 'CollectionCase']:
    items = d.get(k, [])
    print(f'{k}: {len(items)} records')
"
```

Expected: 8, 12, 4, 8, 8, 23+, 4 records (RepaymentRecord should be >= 23)

- [ ] **Step 3: Commit**

```bash
git add config/lending_seed.yaml
git commit -m "feat: add lending seed data (8 borrowers, 12 apps, 8 contracts, 23+ repayments, 4 cases)"
```

---

### Task 4: Function 实现（functions.py）

**Files:**
- Modify: `ontopilot/functions.py`

**Interfaces:**
- Consumes: SchemaRegistry (get_object_type), ObjectStore (get, query, fork, update)
- Produces: 4 个新 function 方法 + FUNCTION_PARAMS entries + `_fns` registry entries

- [ ] **Step 1: 添加 FUNCTION_PARAMS entries**

在 `FUNCTION_PARAMS` dict 末尾添加（在 `calculateCostEfficiency` 结束后）：

```python
    # ── Lending functions ────────────────────────────────────────────────
    "assessApplicationRisk": {
        "description": "Comprehensive risk assessment for a loan application (credit score + DTI + overdue history + inquiry count)",
        "required": {"applicationId": "str — application ID to assess"},
    },
    "evaluateLoanPortfolio": {
        "description": "Scan all loan contracts and their repayment records, identify high-risk contracts",
        "required": {},
        "optional": {"filters": "dict — e.g. {'status': 'active', 'overdueMinDays': 30}"},
    },
    "compareLoanOptions": {
        "description": "Compare multiple loan options with equal-installment simulation (monthly payment, total interest, DTI, risk)",
        "required": {
            "applicationId": "str — application ID",
            "options": "list[dict] — each option with name, annualRate, termMonths, principal. e.g. [{'name': '方案A', 'annualRate': 0.065, 'termMonths': 36, 'principal': 150000}]",
        },
    },
    "compareCollectionOptions": {
        "description": "Compare collection strategies by estimated recovery rate, amount, and cost",
        "required": {
            "caseId": "str — collection case ID",
            "options": "list[dict] — each option with strategy. e.g. [{'strategy': 'phone_call'}, {'strategy': 'door_visit'}]",
        },
    },
```

- [ ] **Step 2: 注册新函数到 `_fns` dict**

在 `_fns` dict 末尾添加：

```python
            "assessApplicationRisk": self._assess_application_risk,
            "evaluateLoanPortfolio": self._evaluate_loan_portfolio,
            "compareLoanOptions": self._compare_loan_options,
            "compareCollectionOptions": self._compare_collection_options,
```

- [ ] **Step 3: 实现 `_assess_application_risk`**

在 `_calculate_cost_efficiency` 方法之后添加：

```python
    # ── Lending: assessApplicationRisk ────────────────────────────────────

    def _assess_application_risk(self, params: dict) -> dict:
        application_id: str = params.get("applicationId", "")
        if not application_id:
            return {"error": "Missing applicationId param"}

        application = self._store.get("LoanApplication", application_id)
        if not application:
            return {"error": f"LoanApplication {application_id} not found"}

        borrower = self._store.get("Borrower", application.get("borrowerId", ""))
        if not borrower:
            return {"error": f"Borrower not found for application {application_id}"}

        # Try to get credit report via traverse
        credit_reports = self._store.traverse(
            "LoanApplication", application_id, "assessedFor", None
        ) if "assessedFor" in self._schema.get_object_type("LoanApplication").links else []
        # traverse returns CreditReports linked via assessedFor; if empty try query
        if not credit_reports:
            all_reports = self._store.query("CreditReport",
                {"applicationId": application_id}, None)
            credit_reports = all_reports

        report = credit_reports[0] if credit_reports else {}

        score = 0
        reasons = []

        # Credit score assessment
        cs = report.get("creditScore", borrower.get("creditScore", 600))
        if cs >= 750:
            score += 0
        elif cs >= 650:
            score += 15
            reasons.append(f"征信分中等 ({cs})")
        elif cs >= 550:
            score += 30
            reasons.append(f"征信分偏低 ({cs})")
        else:
            score += 50
            reasons.append(f"征信分严重偏低 ({cs})")

        # DTI assessment
        dti = borrower.get("dti", 0)
        if dti > 0.50:
            score += 30
            reasons.append(f"债务收入比过高 ({dti*100:.0f}%)")
        elif dti > 0.36:
            score += 15
            reasons.append(f"债务收入比偏高 ({dti*100:.0f}%)")

        # Inquiry count
        inquiry_count = report.get("inquiryCount6m", 0)
        if inquiry_count >= 6:
            score += 20
            reasons.append(f"近6个月查询次数过多 ({inquiry_count})")
        elif inquiry_count >= 3:
            score += 10
            reasons.append(f"近6个月查询次数偏多 ({inquiry_count})")

        # Historical defaults
        defaults = borrower.get("historicalDefaults", 0)
        if defaults >= 3:
            score += 25
            reasons.append(f"历史逾期次数多 ({defaults})")
        elif defaults >= 1:
            score += 10
            reasons.append(f"有历史逾期记录 ({defaults})")

        # Fraud flag
        if report.get("fraudFlag"):
            score += 40
            reasons.append("反欺诈标记命中")

        # Risk level
        if score >= 60:
            risk_level = "reject"
        elif score >= 35:
            risk_level = "high"
        elif score >= 15:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Recommended max amount: monthlyIncome * 36 / (1 + DTI), capped at application amount
        monthly_income = borrower.get("monthlyIncome", 0)
        recommended_max = round(monthly_income * 36 / max(1 + dti, 1.1), -3)
        if risk_level == "reject":
            recommended_max = 0

        return {
            "applicationId": application_id,
            "borrowerName": borrower.get("name"),
            "riskLevel": risk_level,
            "riskScore": score,
            "creditScore": cs,
            "dti": dti,
            "recommendedMaxAmount": recommended_max,
            "reasons": reasons,
        }
```

- [ ] **Step 4: 实现 `_evaluate_loan_portfolio`**

```python
    # ── Lending: evaluateLoanPortfolio ────────────────────────────────────

    def _evaluate_loan_portfolio(self, params: dict) -> list[dict]:
        filters = params.get("filters") or {}
        status_filter = filters.get("status")
        overdue_min = filters.get("overdueMinDays", 0)

        if status_filter:
            contracts = self._store.query("LoanContract", {"status": status_filter}, None)
        else:
            # Get all non-paid-off contracts
            contracts = self._store.query("LoanContract", {}, None)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        results = []

        for contract in contracts:
            # Skip paid-off contracts unless explicitly requested
            if not status_filter and contract.get("status") == "paid_off":
                continue
            if contract.get("status") not in ("active", "defaulted", "restructured"):
                continue

            cid = contract.get("contractId")
            records = self._store.query("RepaymentRecord", {"contractId": cid}, None)
            if not records:
                continue

            # Analyze repayment patterns
            records.sort(key=lambda r: r.get("dueDate", ""))
            last_3 = [r for r in records if r.get("status") != "upcoming"][-3:]

            statuses = [r.get("status") for r in last_3]
            consecutive_missed = 0
            consecutive_late = 0
            for s in reversed(statuses):
                if s == "missed":
                    consecutive_missed += 1
                elif s == "late":
                    consecutive_late += 1
                else:
                    break

            # Calculate overdue days from earliest missed record
            overdue_days = 0
            for r in records:
                if r.get("status") == "missed":
                    due_raw = r.get("dueDate", "")
                    if due_raw:
                        due = datetime.fromisoformat(due_raw)
                        if due.tzinfo is None:
                            due = due.replace(tzinfo=timezone.utc)
                        days = (now - due).days
                        overdue_days = max(overdue_days, days)

            if overdue_days < overdue_min:
                continue

            risk_flags = []
            if consecutive_missed >= 2:
                risk_flags.append(f"连续{consecutive_missed}期未还")
            if consecutive_late >= 2:
                risk_flags.append(f"连续{consecutive_late}期迟还")
            if contract.get("status") == "defaulted":
                risk_flags.append("合同已违约")
            if contract.get("status") == "restructured":
                risk_flags.append("合同已重组")

            # Borrower info
            borrower = self._store.get("Borrower", contract.get("borrowerId", "")) or {}

            last_status = last_3[-1].get("status") if last_3 else "unknown"
            results.append({
                "contractId": cid,
                "borrowerName": borrower.get("name", ""),
                "status": contract.get("status"),
                "overdueDays": overdue_days,
                "remainingPrincipal": round(contract.get("principal", 0) - sum(
                    r.get("paidAmount", 0) for r in records if r.get("status") in ("on_time", "late")
                ), 2),
                "monthlyPayment": contract.get("monthlyPayment"),
                "lastPaymentStatus": last_status,
                "riskFlags": risk_flags,
            })

        # Sort by overdueDays descending (worst first)
        results.sort(key=lambda x: x["overdueDays"], reverse=True)
        return results
```

- [ ] **Step 5: 实现 `_compare_loan_options`**

```python
    # ── Lending: compareLoanOptions ───────────────────────────────────────

    def _compare_loan_options(self, params: dict) -> list[dict]:
        application_id: str = params.get("applicationId", "")
        options: list[dict] = params.get("options", [])

        application = self._store.get("LoanApplication", application_id)
        if not application:
            return [{"error": f"LoanApplication {application_id} not found"}]

        borrower = self._store.get("Borrower", application.get("borrowerId", ""))
        if not borrower:
            return [{"error": f"Borrower not found for application {application_id}"}]

        monthly_income = borrower.get("monthlyIncome", 0)
        existing_dti = borrower.get("dti", 0)
        # Estimate existing monthly debt payments from DTI
        existing_monthly_debt = monthly_income * existing_dti

        results = []
        for option in options:
            name = option.get("name", option.get("strategy", "unknown"))
            annual_rate = option.get("annualRate", 0.072)
            term_months = option.get("termMonths", 36)
            principal = option.get("principal", application.get("amount", 100000))

            # Equal installment formula: M = P * r * (1+r)^n / ((1+r)^n - 1)
            monthly_rate = annual_rate / 12.0
            if monthly_rate == 0:
                monthly_payment = principal / term_months
            else:
                factor = (1 + monthly_rate) ** term_months
                monthly_payment = principal * monthly_rate * factor / (factor - 1)

            total_interest = monthly_payment * term_months - principal

            # New DTI
            new_monthly_debt = existing_monthly_debt + monthly_payment
            new_dti = round(new_monthly_debt / monthly_income, 3) if monthly_income > 0 else 1.0

            # Affordability assessment
            if new_dti <= 0.36:
                affordability = "good"
                risk_level = "low"
            elif new_dti <= 0.50:
                affordability = "caution"
                risk_level = "medium"
            else:
                affordability = "high_risk"
                risk_level = "high"

            results.append({
                "optionName": name,
                "monthlyPayment": round(monthly_payment, 2),
                "totalInterest": round(total_interest, 2),
                "totalRepayment": round(principal + total_interest, 2),
                "newDti": new_dti,
                "affordabilityScore": affordability,
                "riskLevel": risk_level,
                "annualRate": annual_rate,
                "termMonths": term_months,
                "principal": principal,
            })

        return results
```

- [ ] **Step 6: 实现 `_compare_collection_options`**

```python
    # ── Lending: compareCollectionOptions ─────────────────────────────────

    def _compare_collection_options(self, params: dict) -> list[dict]:
        case_id: str = params.get("caseId", "")
        options: list[dict] = params.get("options", [])

        case = self._store.get("CollectionCase", case_id)
        if not case:
            return [{"error": f"CollectionCase {case_id} not found"}]

        overdue_days = case.get("overdueDays", 0)
        outstanding = case.get("outstandingAmount", 0)

        # Recovery rate model by overdue range and strategy
        BASE_RATES = {
            "sms":       {(0, 30): 0.70, (31, 90): 0.40, (91, 9999): 0.15},
            "phone_call":{(0, 30): 0.85, (31, 90): 0.55, (91, 9999): 0.30},
            "door_visit":{(0, 30): 0.90, (31, 90): 0.65, (91, 9999): 0.30},
            "legal_notice": {(0, 30): 0.80, (31, 90): 0.50, (91, 9999): 0.35},
            "external_agency": {(0, 30): 0.60, (31, 90): 0.45, (91, 9999): 0.35},
        }
        COST_PER_ACTION = {
            "sms": 5, "phone_call": 30, "door_visit": 150,
            "legal_notice": 300, "external_agency": 0,  # external is % based
        }

        def get_recovery_rate(strategy: str, days: int) -> float:
            rates = BASE_RATES.get(strategy, {})
            for (lo, hi), rate in rates.items():
                if lo <= days <= hi:
                    return rate
            return 0.3

        results = []
        for option in options:
            strategy = option.get("strategy", "phone_call")
            recovery_rate = get_recovery_rate(strategy, overdue_days)
            recovery_amount = round(outstanding * recovery_rate, 2)

            if strategy == "external_agency":
                cost = round(recovery_amount * 0.20, 2)
            else:
                cost = COST_PER_ACTION.get(strategy, 30)

            net_recovery = round(recovery_amount - cost, 2)

            if recovery_rate >= 0.60:
                recommendation = "推荐"
            elif recovery_rate >= 0.40:
                recommendation = "可考虑"
            else:
                recommendation = "效果有限"

            results.append({
                "strategy": strategy,
                "overdueDays": overdue_days,
                "outstandingAmount": outstanding,
                "estimatedRecoveryRate": round(recovery_rate, 2),
                "estimatedRecoveryAmount": recovery_amount,
                "estimatedCost": cost,
                "netRecovery": net_recovery,
                "recommendation": recommendation,
            })

        results.sort(key=lambda x: x["netRecovery"], reverse=True)
        return results
```

- [ ] **Step 7: 验证 functions.py 无语法错误**

```bash
python -c "from ontopilot.functions import FunctionRegistry; print('Import OK')"
```

Expected: `Import OK`

- [ ] **Step 8: Commit**

```bash
git add ontopilot/functions.py
git commit -m "feat: add 4 lending functions (assessApplicationRisk, evaluateLoanPortfolio, compareLoanOptions, compareCollectionOptions)"
```

---

### Task 5: E2E 验证

**Files:**
- 无新建文件

**Interfaces:**
- Consumes: 所有 Task 1-4 的产出
- Produces: 验证通过的确认

- [ ] **Step 1: 启动后端并激活 lending ontology**

```bash
cd /Users/jingwang/Documents/projects/ontopilot
set -a && source .env && set +a
uv run uvicorn api.main:app --port 8001 &
sleep 3
# Activate the lending ontology
curl -s -X POST http://localhost:8001/ontology/activate \
  -H "Content-Type: application/json" \
  -d '{"filename": "lending_ontology.yaml"}' | python -m json.tool
```

Expected: JSON with `"status": "ok"`, object_types 包含 7 个类型

- [ ] **Step 2: 验证 7 个 object types 可查询**

```bash
# Query each object type to verify seed data loaded
for ot in Borrower LoanApplication CreditReport LoanContract RepaymentPlan RepaymentRecord CollectionCase; do
  echo -n "$ot: "
  curl -s http://localhost:8001/ontology/query -H "Content-Type: application/json" \
    -d "{\"user_id\":\"admin\",\"role\":\"admin\",\"object_type\":\"$ot\",\"filters\":{},\"aggregation\":\"count\"}"
  echo
done
```

Expected: 所有类型返回 count > 0

- [ ] **Step 3: 验证 4 个 functions 可调用**

```bash
# Test assessApplicationRisk
curl -s http://localhost:8001/function/call -H "Content-Type: application/json" \
  -d '{"user_id":"admin","role":"admin","function_name":"assessApplicationRisk","params":{"applicationId":"APP-001"}}' | python -m json.tool

# Test evaluateLoanPortfolio
curl -s http://localhost:8001/function/call -H "Content-Type: application/json" \
  -d '{"user_id":"admin","role":"admin","function_name":"evaluateLoanPortfolio","params":{}}' | python -m json.tool

# Test compareLoanOptions
curl -s http://localhost:8001/function/call -H "Content-Type: application/json" \
  -d '{"user_id":"admin","role":"admin","function_name":"compareLoanOptions","params":{"applicationId":"APP-001","options":[{"name":"低利率","annualRate":0.055,"termMonths":36,"principal":150000},{"name":"短期","annualRate":0.065,"termMonths":12,"principal":150000}]}}' | python -m json.tool

# Test compareCollectionOptions
curl -s http://localhost:8001/function/call -H "Content-Type: application/json" \
  -d '{"user_id":"admin","role":"admin","function_name":"compareCollectionOptions","params":{"caseId":"CC-003","options":[{"strategy":"phone_call"},{"strategy":"door_visit"},{"strategy":"legal_notice"}]}}' | python -m json.tool
```

Expected: 所有 4 个函数返回合理 JSON 结果，无 error

- [ ] **Step 4: 验证 ontology 可视化面板正确渲染**

前端启动后，切换到 lending ontology，确认：
- 7 个 object type 节点渲染
- 节点间 links 连线正确
- 工具提示显示属性

```bash
# Kill backend
kill %1 2>/dev/null
```

- [ ] **Step 5: 停止后端**

```bash
kill %1 2>/dev/null
```

- [ ] **Step 6: 更新 progress ledger**

```bash
# Append to .superpowers/sdd/progress.md
echo "" >> .superpowers/sdd/progress.md
echo "---" >> .superpowers/sdd/progress.md
echo "" >> .superpowers/sdd/progress.md
echo "Plan: docs/superpowers/plans/2026-07-22-lending-ontology.md" >> .superpowers/sdd/progress.md
echo "Base commit (plan start): $(git rev-parse HEAD)" >> .superpowers/sdd/progress.md
```
