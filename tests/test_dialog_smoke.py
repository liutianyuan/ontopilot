"""10-round dialog smoke test per ontology.
Covers multi-step reasoning, simulation comparison, and risk assessment.
"""
import json
import os
import shutil
import sys
import time
import urllib.request
import urllib.error

API_BASE = "http://localhost:8000/api"
CONFIG_DIR = "config"
TOTAL = 0
PASSED = 0
FAILED = 0

_CFG_MAP = {
    "schema": "ontology_schema.yaml",
    "seed": "seed_data.yaml",
    "perms": "permissions.yaml",
    "ctx": "context_sources.yaml",
}

ONTOLOGIES = {
    "simple": {
        "schema": "simple_ontology.yaml",
        "seed": "simple_seed.yaml",
        "perms": "simple_permissions.yaml",
        "ctx": "simple_context.yaml",
    },
    "medium": {
        "schema": "medium_ontology.yaml",
        "seed": "medium_seed.yaml",
        "perms": "medium_permissions.yaml",
        "ctx": "medium_context.yaml",
    },
    "complex": {
        "schema": "complex_ontology.yaml",
        "seed": "complex_seed.yaml",
        "perms": "complex_permissions.yaml",
        "ctx": "complex_context.yaml",
    },
    "procurement": {
        "schema": "procurement_ontology.yaml",
        "seed": "procurement_seed.yaml",
        "perms": "procurement_permissions.yaml",
        "ctx": "procurement_context.yaml",
    },
    "logistics": {
        "schema": "logistics_ontology.yaml",
        "seed": "logistics_seed.yaml",
        "perms": "logistics_permissions.yaml",
        "ctx": "logistics_context.yaml",
    },
}


def api_post(path: str, body: dict, timeout: int = 180):
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:200]}, e.code
    except Exception as e:
        return {"error": str(e)}, 0


def chat(message: str, role: str = "admin", model_id: str = "model-mqqgwumv") -> dict:
    body = {
        "session_id": None,
        "user_id": f"{role}_001",
        "role": role,
        "warehouse_id": "",
        "message": message,
        "confirmed": False,
        "model_id": model_id,
    }
    result, status = api_post("/chat", body, timeout=600)
    result["_status"] = status
    return result


def check(resp: dict, desc: str) -> bool:
    global TOTAL, PASSED, FAILED
    TOTAL += 1
    status = resp.get("_status", 0)
    if status != 200:
        print(f"  ❌ [{desc}] HTTP {status}: {str(resp.get('error',''))[:120]}")
        FAILED += 1
        return False
    text = resp.get("response", "")
    markers = ["模型初始化失败", "Internal Server Error", "处理请求时出错"]
    for m in markers:
        if m in text:
            print(f"  ❌ [{desc}] Server error: {text[:200]}")
            FAILED += 1
            return False
    if not text or len(text) < 5:
        print(f"  ❌ [{desc}] Empty response")
        FAILED += 1
        return False
    PASSED += 1
    print(f"  ✅ [{desc}] OK ({len(text)} chars)")
    return True


def swap_config(onto_key: str, backup: dict[str, str]):
    onto = ONTOLOGIES[onto_key]
    for cfg_type in ("schema", "seed", "perms", "ctx"):
        src_name = onto[cfg_type]
        dst_name = _CFG_MAP[cfg_type]
        src_path = os.path.join("tests/test_data", src_name)
        dst_path = os.path.join(CONFIG_DIR, dst_name)
        if not os.path.exists(src_path):
            print(f"  ⚠️  Missing {src_path}, skipping")
            continue
        if dst_name not in backup:
            backup[dst_name] = dst_path + ".bak"
            shutil.copy2(dst_path, backup[dst_name])
        shutil.copy2(src_path, dst_path)


def run_ontology(onto_key: str, tasks: list[tuple[str, str]], role: str = "admin", backup: dict[str, str] | None = None):
    if backup is None:
        backup = {}
    print(f"\n{'='*60}")
    print(f"📊 {onto_key.upper()} — {len(tasks)} dialog rounds")
    print(f"{'='*60}")
    swap_config(onto_key, backup)
    result, status = api_post("/ontology/import", {}, timeout=30)
    if status != 200:
        print(f"  ❌ Import failed: {result.get('error', str(result))[:200]}")
        return False
    print(f"  ✅ Imported: {result.get('object_type_count', '?')} types, {result.get('action_count', '?')} actions, {result.get('function_count', '?')} functions")
    ok = True
    for i, (desc, msg) in enumerate(tasks, 1):
        print(f"  [{i}/{len(tasks)}] {desc}...")
        resp = chat(msg, role)
        if not check(resp, desc):
            snippet = resp.get('response', '')[:200]
            print(f"    ↳ {snippet}")
            ok = False
        time.sleep(0.3)
    return ok


# ══════════════════════════════════════════════════════════════════
# SIMPLE — query-only, but requires multi-hop reasoning
# ══════════════════════════════════════════════════════════════════

SIMPLE_TASKS = [
    ("1. 人员年龄分析",
     "查询所有人员信息，列出姓名和年龄，计算平均年龄，找出最年长和最年轻的人员"),
    ("2. 人口与经济数据",
     "列出所有城市的人口数量，按人口从高到低排序，找出人口超过2000万的城市"),
    ("3. 行业分布统计",
     "列出所有公司和所属行业，按行业分组统计公司数量，找出公司最多的行业"),
    ("4. 书籍出版时间分析",
     "列出所有书籍的出版年份，按年份分组统计，找出哪一年出版的书籍最多"),
    ("5. 图书品类分布",
     "列出所有书籍及其品类（genre），统计每个品类有多少本书，给出品类占比分析"),
    ("6. 公司成立时间分析",
     "查询2010年后成立的公司，列出名称和成立年份，评估公司的新老分布"),
    ("7. 年龄与城市数据结合分析",
     "先查询所有人员的年龄范围，再查询所有城市的人口数据，对比分析"),  # no links — pure multi-query
    ("8. 图书跨品类查询",
     "统计计算机科学类书籍的数量，同时统计其他品类书籍合并的数量，做对比"),
    ("9. 多维度过滤组合",
     "查询2015年之后出版的计算机科学书籍，以及2015年之前出版的非计算机科学书籍"),
    ("10. 全景数据报告",
     "分别查询人员、城市、公司、书籍的数量，给出总体数据规模和分布概览报告"),
]

# ══════════════════════════════════════════════════════════════════
# MEDIUM — link traversal + actions
# ══════════════════════════════════════════════════════════════════

MEDIUM_TASKS = [
    ("1. 组织人才网络分析",
     "查询所有人员及其所属组织，找出同一组织内的人员，分析各组织的人才构成"),
    ("2. 事件参与全景",
     "查询所有事件的信息以及参与人员，找出哪些事件有多人参加，分析最活跃的事件"),
    ("3. 学术产出与组织关联",
     "查询所有出版物及其作者，再查询作者的所属组织和职业，分析学术产出分布"),
    ("4. 城市与组织关系",
     "查询所有组织所在城市，按城市列出组织清单，评估各城市的组织活跃度"),
    ("5. 多步路径查询：人员→事件→地点",
     "查询王强（P-003）参加了哪些事件，这些事件在哪个城市举办，其他参与人是谁"),
    ("6. 研究人员事件参与分析",
     "查询所有职业为研究员和教授的人员，列出他们参加的事件以及各自的组织"),
    ("7. 时间线综合：事件与出版物",
     "查询2025年的事件及其参与人员，再查询同一年的出版物及作者，交叉分析年度产出"),
    ("8. 出版作者关联网络",
     "对每本出版物，列出所有作者及其职业和组织，识别多作者跨组织合作情况"),
    ("9. 组织活跃度对比",
     "对比星辰科技和蓝海研究院：各有多少人员、参加了多少事件、人员发表了多少出版物"),
    ("10. 综合数据报告",
     "统计并汇总：各城市有多少组织、各类事件参与人数、各作者出版物数量，形成指标体系"),
]

# ══════════════════════════════════════════════════════════════════
# COMPLEX — functions + actions + decision support
# ══════════════════════════════════════════════════════════════════

COMPLEX_TASKS = [
    ("1. 组织架构与人员能力分析",
     "查询所有部门信息，列出每个部门的人员名单及其技能标签，分析各部门的核心技术能力分布"),
    ("2. 项目健康度与团队构成",
     "查询所有active项目，列出参与人员及其角色分配比例，找出人员投入最大的项目"),
    ("3. 技能缺口量化评估",
     "计算智能客服平台的技能缺口，分析当前团队在哪些技能上存在不足"),
    ("4. 基于技能缺口推荐最佳团队",
     "根据智能客服平台的需求，从现有人员中推荐最佳项目团队，对比不同配置方案的优劣"),
    ("5. 多项目风险分析",
     "分析智能客服平台和数据中台建设两个项目的健康度，对比两者的风险等级和改善建议"),
    ("6. KPI指标与项目表现联动分析",
     "列出所有KPI及其跟踪的项目，分析哪些KPI未达标，评估这些未达标KPI对项目的影响"),
    ("7. 跨项目人员负荷评估",
     "查找同时参与多个项目的人员，分析他们的分配比例是否合理，评估是否存在过度分配风险"),
    ("8. 文档-人员-项目关联追溯",
     "列出所有文档及其作者、关联项目，分析各项目的文档完备度"),
    ("9. 人员调整方案模拟",
     "查询张明（P-00001）当前参与的智能客服平台和数据中台项目，以及李娜（P-00002）在智能客服平台的参与情况"),
    ("10. 综合管理决策建议",
     "结合项目健康度分析、技能缺口分析和KPI达标情况，给出智能客服平台当前的管理决策建议"),
]

# ══════════════════════════════════════════════════════════════════
# PROCUREMENT — full decision-support workflow with simulation
# ══════════════════════════════════════════════════════════════════

PROCUREMENT_TASKS = [
    ("1. 供应商基础能力评估",
     "列出所有供应商的产能、良品率、交付及时率和价格指数，按综合能力排序，识别出Top3和Bottom2"),
    ("2. 物料供应矩阵分析",
     "查询所有物料及其首选供应商、毛利率，分析不同品类的物料对单一供应商的依赖程度"),
    ("3. 多方案分货推荐与对比",
     "为MAT-001锂离子电芯推荐分货方案，需求5000件，要求列出各供应商的分配比例并对比成本和产能可行性"),
    ("4. 供应风险深度评估",
     "分析PLAN-003主控芯片分货计划的供应风险，特别关注单供应商依赖和产能瓶颈"),
    ("5. 供应商能力对比决策",
     "对比SUP-001华兴科技和SUP-002东方精密在为MAT-001锂离子电芯供货方面的综合能力"),
    ("6. 成本效率多维分析",
     "分析SUP-003北方工业在MAT-003铝合金外壳上的成本效率，综合考虑价格、质量损失和交付延迟"),
    ("7. 分货调整影响评估",
     "模拟调整分货方案：目前MAT-001的分货情况如何？如果增加SUP-001的份额到60%，会有什么影响？"),
    ("8. 品类策略与风险分析",
     "分析leveraged_competitive品类物料的分货是否有单供应商依赖风险，给出品类管理建议"),
    ("9. 供应商评分与绩效追溯",
     "查询所有供应商的绩效评分记录，分析评分趋势，识别哪些供应商评分在下降"),
    ("10. 综合分货决策报告",
     "汇总所有信息：对MAT-004光学镜头模组做全面的供应分析，包括当前供应商能力、风险评估、成本对比，并给出2026年7月分货计划的决策建议（总量2000件）"),
]


# ══════════════════════════════════════════════════════════════════
# LOGISTICS — order/carrier/simulation workflow
# ══════════════════════════════════════════════════════════════════

LOGISTICS_TASKS = [
    ("1. 订单查询与承运商信息",
     "查询所有订单信息，列出订单编号、优先级、金额和客户ID，再查询所有承运商的价格和评分"),
    ("2. 延误风险批量评估",
     "查询所有delayed状态的Shipment，列出其当前ETA和延误原因，再对这些Shipment批量计算延误风险"),
    ("3. 承运商优化推荐",
     "查看SH-0001（ORT-001的部分货物）当前承运商顺达物流的信息，然后推荐是否有更优的替代承运商方案"),
    ("4. 承运商切换方案仿真对比",
     "对SH-0001对比两种方案：方案A-保持当前承运商顺达物流，方案B-切换到极速专配CARRIER-C。用compareDecisions对比仿真结果"),
    ("5. 执行承运商替换",
     "SH-0001当前由承运商顺达物流承运，已延误多次，推荐替换到更优承运商并执行assignCarrier操作"),
    ("6. 紧急订单延误风险计算",
     "查询所有urgent订单的Shipment状态（查看订单ORD-001, ORD-009, ORD-011对应的shipment），对已延误的发货计算延误风险等级"),
    ("7. 创建发货单与分配承运商",
     "为订单ORD-003（ZZ零售集团，medium优先级，要求交货7月5日）在华东仓创建一个发货单，使用承运商CARRIER-B中通速运，重15公斤。创建后如果还有延误问题，建议更换到极速专配并做仿真对比"),
    ("8. VIP客户集中分析与方案",
     "查询VIP客户CUST-001和CUST-006的所有订单及其Shipment状态，汇总延误情况，对每个延误Shipment给出改善建议"),
    ("9. 多仓库积压对比与影响评估",
     "查询所有仓库的积压数据，对比华南仓和华北仓，分析积压对Shipment延误的影响，计算涉及积压延误的Shipment数量"),
    ("10. 综合物流运营决策报告",
     "汇总所有信息：当前有多少订单和Shipment，延误率多高，主要延误原因分布，各承运商的绩效对比，给出运营改善优先级建议"),
]


def main():
    # Wait for backend
    print("Waiting for backend...")
    for i in range(30):
        try:
            urllib.request.urlopen(f"{API_BASE}/settings", timeout=5)
            print("Backend ready.")
            break
        except Exception:
            time.sleep(1)
    else:
        print("❌ Backend not available")
        sys.exit(1)

    backup: dict[str, str] = {}
    results = []

    try:
        results.append(("simple", run_ontology("simple", SIMPLE_TASKS, backup=backup)))
        results.append(("medium", run_ontology("medium", MEDIUM_TASKS, backup=backup)))
        results.append(("complex", run_ontology("complex", COMPLEX_TASKS, backup=backup)))
        results.append(("procurement", run_ontology("procurement", PROCUREMENT_TASKS, "procurement_manager", backup)))
        results.append(("logistics", run_ontology("logistics", LOGISTICS_TASKS, "admin", backup)))
    finally:
        for dst, bak in backup.items():
            if os.path.exists(bak):
                shutil.copy2(bak, os.path.join(CONFIG_DIR, dst))
                os.remove(bak)
        api_post("/ontology/import", {}, timeout=30)

    print(f"\n{'='*60}")
    print("📊 SMOKE TEST SUMMARY")
    print(f"{'='*60}")
    for name, ok in results:
        print(f"  {name}: {'✅ PASS' if ok else '❌ FAIL'}")
    print(f"\n  Total: {TOTAL} | ✅ Passed: {PASSED} | ❌ Failed: {FAILED}")
    print(f"{'='*60}")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
