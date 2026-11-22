"""抽取锚点绑定预演测试：冲突匹配写入清单、来源确认、样本计数与跨版本核对。"""
from __future__ import annotations

import os
import sys

# 确保后端目录在导入路径中
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import persistence as persist

# 清理测试数据目录（含预演状态与字段定位清单）
for sub in ["runs", "snapshots", "reports", "exports", "rehearsal", "manifests"]:
    p = persist.data_path(sub, "")
    if os.path.isdir(p):
        for f in os.listdir(p):
            os.remove(os.path.join(p, f))


def test_selector_engine_subset():
    """DOM 选择器引擎：CSS 与 XPath 子集都能定位到正确节点。"""
    from app.domselect import css_select, node_path, parse_dom, xpath_select
    from app.seed import REHEARSAL_V1_DOM

    root = parse_dom(REHEARSAL_V1_DOM)
    narrow = css_select(root, "#main-product .price")
    assert len(narrow) == 1
    assert narrow[0].text() == "¥299.00"
    broad = css_select(root, ".price")
    assert len(broad) == 2
    assert broad[0].text() == "¥199.00"  # 促销区在文档序中靠前
    xp = xpath_select(root, "//*[@id='main-product']//span[contains(@class,'price')]")
    assert len(xp) == 1 and xp[0].text() == "¥299.00"
    assert node_path(narrow[0]) == "/html[1]/body[1]/div[2]/span[1]"


def test_rehearsal_writes_manifest_with_conflict():
    """主商品区和促销区都有价格：两个锚点命中不同区域，冲突写入字段定位清单。"""
    from app.services.extract_rehearsal import ExtractRehearsalService

    svc = ExtractRehearsalService()
    result = svc.run_rehearsal("DATA-0004", "product-v1")
    hits = [e for e in result["evaluations"] if e["命中"]]
    assert len(hits) == 2, f"预期两个锚点都命中: {result['evaluations']}"
    values = {e["锚点编号"]: e["值"] for e in hits}
    assert values["ELEM-0004"] == "¥299.00"  # 窄锚点 → 主商品区
    assert values["ELEM-0005"] == "¥199.00"  # 宽锚点 → 促销区
    assert result["conflict"] is True

    # 实际匹配已写入字段定位清单，且两个锚点指向不同节点
    manifest = persist.read_json("manifests", "DATA-0004.json")
    assert manifest is not None, "字段定位清单未持久化"
    assert manifest["抽取字段"] == "价格"
    assert len(manifest["matches"]) == 2
    assert all(m["状态"] == "候选" for m in manifest["matches"])
    assert manifest["confirmed"] is None
    paths = {m["锚点编号"]: m["节点路径"] for m in manifest["matches"]}
    assert paths["ELEM-0004"] != paths["ELEM-0005"]


def test_unconfirmed_sample_not_counted():
    """未确认的绑定保留候选值和来源，但样本不能按抽取成功计数。"""
    from app.services.extract_rehearsal import ExtractRehearsalService

    svc = ExtractRehearsalService()
    svc.run_rehearsal("DATA-0004", "product-v1")
    view = svc.rehearsal_view("DATA-0004")
    v1 = next(v for v in view["versions"] if v["页面版本"] == "product-v1")
    assert v1["sample"]["计入样本"] is False
    assert v1["sample"]["值"] is None
    assert view["stats"]["计入样本数"] == 0
    # 候选值与来源保留在排除清单里，原因是不确认绑定
    assert len(v1["excluded"]) == 2
    assert all(e["原因"] == "未确认绑定" for e in v1["excluded"])
    assert {e["值"] for e in v1["excluded"]} == {"¥299.00", "¥199.00"}


def test_confirm_establishes_single_executable_source():
    """提交预演后只确立一个可执行来源，采纳值随页面版本与匹配节点持久化。"""
    from app.services.extract_rehearsal import ExtractRehearsalService

    svc = ExtractRehearsalService()
    svc.run_rehearsal("DATA-0004", "product-v1")
    manifest = svc.confirm_binding("DATA-0004", "product-v1", "ELEM-0004")
    confirmed = manifest["confirmed"]
    assert confirmed["锚点编号"] == "ELEM-0004"
    assert confirmed["页面版本"] == "product-v1"
    assert confirmed["值"] == "¥299.00"
    assert confirmed["节点路径"] == "/html[1]/body[1]/div[2]/span[1]"
    assert confirmed["确认时间"]
    statuses = {m["锚点编号"]: m["状态"] for m in manifest["matches"]}
    assert statuses["ELEM-0004"] == "已采纳"
    assert statuses["ELEM-0005"] == "冲突未采纳"

    # 磁盘上的清单同样只有一个可执行来源
    on_disk = persist.read_json("manifests", "DATA-0004.json")
    assert on_disk["confirmed"]["锚点编号"] == "ELEM-0004"

    # 换锚点再次确认：来源被替换，仍然只有一个
    replaced = svc.confirm_binding("DATA-0004", "product-v1", "ELEM-0005")
    assert replaced["confirmed"]["锚点编号"] == "ELEM-0005"
    assert replaced["confirmed"]["值"] == "¥199.00"
    # 恢复为窄锚点，供后续跨版本测试使用
    svc.confirm_binding("DATA-0004", "product-v1", "ELEM-0004")


def test_register_second_version_and_cross_version_view():
    """确认字段后录入结构不同的第二版页面：每版实际值与冲突排除都可见。"""
    from app.seed import REHEARSAL_V2_DOM
    from app.services.extract_rehearsal import ExtractRehearsalService
    from app.store import store

    svc = ExtractRehearsalService()
    # 录入第二版页面（结构不同：#main-product 被 section.product-hero 取代）
    page = svc.register_page("DATA-0004", "product-v2", REHEARSAL_V2_DOM)
    assert page["页面版本"] == "product-v2"
    assert page["快照编号"] == "PAGE-0005"
    # 页面快照模块同步可见
    snap_rows = [r for r in store.rows("page_snapshot") if r.get("页面版本") == "product-v2"]
    assert len(snap_rows) == 1 and snap_rows[0]["status"] == "已存档"

    # 重复录入同一版本应被拒绝
    try:
        svc.register_page("DATA-0004", "product-v2", REHEARSAL_V2_DOM)
    except Exception as exc:
        assert "已录入" in str(exc)
    else:
        raise AssertionError("重复录入同一页面版本未被拒绝")

    # 在第二版上运行预演：窄锚点失效，宽锚点仍命中促销区
    result = svc.run_rehearsal("DATA-0004", "product-v2")
    by_anchor = {e["锚点编号"]: e for e in result["evaluations"]}
    assert by_anchor["ELEM-0004"]["命中"] is False
    assert by_anchor["ELEM-0005"]["命中"] is True
    assert by_anchor["ELEM-0005"]["值"] == "¥189.00"

    # 视图列出每版实际获得的值
    view = svc.rehearsal_view("DATA-0004")
    versions = {v["页面版本"]: v for v in view["versions"]}
    v1, v2 = versions["product-v1"], versions["product-v2"]
    assert v1["sample"]["值"] == "¥299.00" and v1["sample"]["计入样本"] is True
    assert v2["sample"]["值"] is None and v2["sample"]["计入样本"] is False
    assert v2["sample"]["来源锚点"] == "ELEM-0004"

    # 冲突没有进入样本的匹配：v1 的促销价与 v2 的宽锚点命中
    ex1 = v1["excluded"]
    assert len(ex1) == 1 and ex1[0]["锚点编号"] == "ELEM-0005"
    assert ex1[0]["值"] == "¥199.00" and ex1[0]["原因"] == "冲突未采纳"
    ex2 = v2["excluded"]
    assert len(ex2) == 1 and ex2[0]["锚点编号"] == "ELEM-0005"
    assert ex2[0]["值"] == "¥189.00" and ex2[0]["原因"] == "冲突未采纳"

    # 样本计数：只有 v1 计入抽取成功
    assert view["stats"]["版本数"] == 2
    assert view["stats"]["计入样本数"] == 1
    assert view["stats"]["冲突排除数"] == 2

    # v2 的匹配也已写入字段定位清单，窄锚点来源仍是唯一已采纳
    manifest = persist.read_json("manifests", "DATA-0004.json")
    v2_matches = [m for m in manifest["matches"] if m["页面版本"] == "product-v2"]
    assert len(v2_matches) == 1 and v2_matches[0]["状态"] == "冲突未采纳"
    assert manifest["confirmed"]["锚点编号"] == "ELEM-0004"


def test_data_extract_snapshot_reports_manifests():
    """数据抽取的 domain_snapshot 汇总预演清单与已确认来源数。"""
    from app.services.data_extract import DataExtractService

    snap = DataExtractService().domain_snapshot()
    assert snap["rehearsal_manifests"] >= 1
    assert snap["confirmed_bindings"] >= 1


if __name__ == "__main__":
    test_selector_engine_subset()
    print("PASS: test_selector_engine_subset")
    test_rehearsal_writes_manifest_with_conflict()
    print("PASS: test_rehearsal_writes_manifest_with_conflict")
    test_unconfirmed_sample_not_counted()
    print("PASS: test_unconfirmed_sample_not_counted")
    test_confirm_establishes_single_executable_source()
    print("PASS: test_confirm_establishes_single_executable_source")
    test_register_second_version_and_cross_version_view()
    print("PASS: test_register_second_version_and_cross_version_view")
    test_data_extract_snapshot_reports_manifests()
    print("PASS: test_data_extract_snapshot_reports_manifests")
    print("\nALL 6 REHEARSAL TESTS PASSED")
