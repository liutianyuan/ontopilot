"""Procurement ontology conversation test — 22 tasks.
Tests query, retrieval QA, analysis, decision support, and data simulation
for the supplier allocation / procurement scenario.
"""
import json
import os
import shutil
import sys
import time
import urllib.request
import urllib.error

API_BASE = os.environ.get("ONTOPILOT_API_BASE", "http://localhost:8000/api")
CONFIG_DIR = "config"
TEST_MODEL_ID = os.environ.get("ONTOPILOT_TEST_MODEL_ID")

total = 0
passed = 0
failed = 0
results: list[str] = []


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


_FILE_MAP = {
    "schema": ("procurement_ontology.yaml", "ontology_schema.yaml"),
    "seed":   ("procurement_seed.yaml", "seed_data.yaml"),
    "perms":  ("procurement_permissions.yaml", "permissions.yaml"),
    "ctx":    ("procurement_context.yaml", "context_sources.yaml"),
}


def swap_procurement(backup: dict[str, str]):
    """Copy procurement config files into config/. Backup originals first."""
    test_dir = "tests/test_data"
    for cfg_type in ("schema", "seed", "perms", "ctx"):
        src_name, dst_name = _FILE_MAP[cfg_type]
        src_path = os.path.join(test_dir, src_name)
        dst_path = os.path.join(CONFIG_DIR, dst_name)
        if not os.path.exists(src_path):
            print(f"  ⚠️  Missing {src_path}, skipping")
            continue
        if dst_name not in backup:
            backup[dst_name] = dst_path + ".bak"
            shutil.copy2(dst_path, backup[dst_name])
        shutil.copy2(src_path, dst_path)


def restore_config(backup: dict[str, str]):
    """Restore config files from backup."""
    for dst, bak in backup.items():
        if os.path.exists(bak):
            shutil.copy2(bak, os.path.join(CONFIG_DIR, dst))
            os.remove(bak)


def chat(message: str, role: str = "procurement_manager") -> dict:
    """Send a chat message and return the response."""
    body = {
        "session_id": None,
        "user_id": f"{role}_001",
        "role": role,
        "warehouse_id": "",
        "message": message,
        "confirmed": False,
    }
    if TEST_MODEL_ID:
        body["model_id"] = TEST_MODEL_ID
    result, status = api_post("/chat", body, timeout=600)
    result["_status"] = status
    return result


def chat_with_confirm(message: str, role: str = "procurement_manager") -> dict:
    """Send a confirmed chat message (for actions requiring confirmation)."""
    body = {
        "session_id": None,
        "user_id": f"{role}_001",
        "role": role,
        "warehouse_id": "",
        "message": message,
        "confirmed": True,
    }
    if TEST_MODEL_ID:
        body["model_id"] = TEST_MODEL_ID
    result, status = api_post("/chat", body, timeout=600)
    result["_status"] = status
    return result


def check_response(resp: dict, task_desc: str) -> bool:
    """Verify a chat response has no errors. Returns True if OK."""
    global total, passed, failed
    total += 1
    status = resp.get("_status", 0)

    if status != 200:
        text = resp.get("response", str(resp.get("error", "")))
        print(f"  ❌ [{task_desc}] HTTP {status}: {text[:120]}")
        failed += 1
        return False

    text = resp.get("response", "")
    # Only server-generated errors, not LLM emoji in Chinese responses
    server_errors = ["模型初始化失败", "Internal Server Error", "处理请求时出错"]
    for marker in server_errors:
        if marker in text:
            print(f"  ❌ [{task_desc}] Server error: {text[:200]}")
            failed += 1
            return False

    if not text or len(text) < 5:
        print(f"  ❌ [{task_desc}] Empty/short response")
        failed += 1
        return False

    passed += 1
    print(f"  ✅ [{task_desc}] OK ({len(text)} chars)")
    return True


# ══════════════════════════════════════════════════════════════════════
# 22 PROCUREMENT CONVERSATION TASKS
# ══════════════════════════════════════════════════════════════════════

PROCUREMENT_TASKS: list[tuple[str, str, str]] = [
    # ── Query (8) ──
    ("查询所有物料及品类标签", "列出所有物料，包括名称、品类、毛利率和品类标签", "procurement_manager"),
    ("查询所有供应商基本信息", "查询所有供应商的名称、区域、认证等级和月产能", "procurement_manager"),
    ("按品类标签过滤物料", "查找品类标签为leveraged_competitive的物料有哪些", "procurement_manager"),
    ("查询毛利率高的物料", "查询毛利率超过25%的物料及其类别", "procurement_manager"),
    ("查询分货计划状态", "列出所有分货计划及其当前状态和分配策略", "procurement_manager"),
    ("查询待处理的分货批次", "查看所有状态为pending的分货批次", "procurement_manager"),
    ("查询供应商评分", "查询所有供应商2026年6月的绩效评分", "procurement_manager"),
    ("查询采购订单", "查看所有已批准和已发货的采购订单", "procurement_manager"),

    # ── Retrieval QA (6) ──
    ("最高质量评分供应商", "哪个供应商的质量评分最高？良品率是多少？", "procurement_manager"),
    ("各供应商交付及时率对比", "比较所有供应商的交付及时率，排出优劣", "procurement_manager"),
    ("高毛利物料的主供应商", "毛利率最高的物料是哪几个？它们的首选供应商是谁？", "procurement_manager"),
    ("A级认证供应商能力分析", "A级认证的供应商有哪些？它们的综合能力如何？", "procurement_manager"),
    ("华东区供应商及其订单", "华东地区的供应商有哪些？各自有多少采购订单？", "procurement_manager"),
    ("物料供应来源分析", "锂离子电芯和主控芯片都分配给了哪些供应商？", "procurement_manager"),

    # ── Analysis / Decision Support (5) ──
    ("推荐分货方案", "帮我推荐MAT-001锂离子电芯的最佳分货方案，需求5000件", "procurement_manager"),
    ("供应风险分析", "分析PLAN-003主控芯片分货计划的供应风险", "procurement_manager"),
    ("供应商方案对比", "对比SUP-001华兴科技和SUP-002东方精密在MAT-001上的能力", "procurement_manager"),
    ("成本效率分析", "分析SUP-003北方工业的成本效率", "procurement_manager"),
    ("品类策略分析", "分析leveraged_competitive品类物料的分货是否有单供应商依赖风险", "procurement_manager"),

    # ── Data Simulation / Action (3) ──
    ("模拟分货调整：增加某供应商份额", "如果要把主控芯片在东方精密的订单从400增加到800，会有什么影响？", "procurement_manager"),
    ("创建新分货计划(需确认)", "为MAT-004光学镜头模组创建2026年7月的分货计划，总量2000件，策略用quality_priority", "procurement_manager"),
    ("多维度数据综合分析", "结合供应商评分、交付及时率、良品率和价格，综合分析哪个供应商最适合作为MAT-003铝合金外壳的主供应商", "procurement_manager"),
]


def main():
    global total, passed, failed

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

    print(f"\n{'='*60}")
    print(f"📦 PROCUREMENT ONTOLOGY — {len(PROCUREMENT_TASKS)} tasks")
    print(f"{'='*60}")

    try:
        # Save original config
        import datetime
        orig_dir = f"config_orig_{int(time.time())}"
        for _, dst_name in _FILE_MAP.values():
            dst_path = os.path.join(CONFIG_DIR, dst_name)
            if os.path.exists(dst_path):
                os.makedirs(orig_dir, exist_ok=True)
                shutil.copy2(dst_path, os.path.join(orig_dir, dst_name))

        # Swap in procurement config
        swap_procurement(backup)

        # Import
        result, status = api_post("/ontology/import", {}, timeout=30)
        if status != 200:
            print(f"  ❌ Failed to import ontology: {result.get('error', str(result))[:200]}")
            return 1
        print(f"  ✅ Ontology imported: {result.get('object_type_count', '?')} types, "
              f"{result.get('action_count', '?')} actions, "
              f"{result.get('function_count', '?')} functions")

        # Run tasks
        all_ok = True
        for i, (desc, message, role) in enumerate(PROCUREMENT_TASKS, 1):
            print(f"  [{i}/{len(PROCUREMENT_TASKS)}] {desc}...", end=" ", flush=True)
            try:
                resp = chat(message, role)
                ok = check_response(resp, desc[:40])
                if not ok:
                    all_ok = False
            except Exception as e:
                print(f"  ❌ [{desc[:40]}] Exception: {e}")
                total += 1
                failed += 1
                all_ok = False
            time.sleep(0.3)

        results.append(f"procurement: {len(PROCUREMENT_TASKS)} tasks — {'PASS' if all_ok else 'HAD ERRORS'}")

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
    finally:
        # Restore from original backup
        for _, dst_name in _FILE_MAP.values():
            dst_path = os.path.join(CONFIG_DIR, dst_name)
            orig_path = os.path.join(orig_dir, dst_name)
            if os.path.exists(orig_path):
                shutil.copy2(orig_path, dst_path)
        # Cleanup
        shutil.rmtree(orig_dir, ignore_errors=True)
        # Import the restored ontology
        api_post("/ontology/import", {}, timeout=30)

    # Summary
    print(f"\n{'='*60}")
    print(f"📊 FINAL RESULTS")
    print(f"{'='*60}")
    for r in results:
        print(f"  {r}")
    print(f"\n  Total: {total} | ✅ Passed: {passed} | ❌ Failed: {failed}")
    print(f"{'='*60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
