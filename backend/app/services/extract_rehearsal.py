"""抽取锚点绑定预演：把 DOM 片段与抽取字段的实际匹配写入字段定位清单。

数据流：
1. register_page    录入页面版本（DOM 快照），同步登记 page_snapshot 行
2. run_rehearsal    在指定页面版本上评估候选锚点，实际匹配写入字段定位清单
3. confirm_binding  提交预演：采纳一个锚点作为该字段唯一可执行来源，
                    采纳值与当时的页面版本、匹配节点关联持久化
4. rehearsal_view   按页面版本列出实际获得的值、样本行与冲突排除项；
                    未确认的绑定只保留候选值和来源，样本不计入抽取成功
"""
from __future__ import annotations

import re
from typing import Any

from app import persistence as persist
from app.domselect import Node, css_select, node_path, outer_html, parse_dom, xpath_select
from app.seed import REHEARSAL_PAGES
from app.store import store

_STATE_SUB = "rehearsal"
_MANIFEST_SUB = "manifests"


class RehearsalError(Exception):
    """预演流程的业务错误：模板缺失、版本未录入、锚点未命中等。"""


def _state_path_name(template_code: str) -> str:
    return f"{template_code}.json"


class ExtractRehearsalService:
    """面向 data_extract 模板的锚点绑定预演服务（不占用通用资源模块位）。"""

    # ---------- 基础查询 ----------

    def _template(self, template_code: str) -> dict[str, Any]:
        for row in store.rows("data_extract"):
            if row.get("模板编号") == template_code:
                return row
        raise RehearsalError(f"抽取模板 {template_code} 不存在")

    def _anchors(self, script_code: str) -> list[dict[str, Any]]:
        return [
            row for row in store.rows("element_selector")
            if row.get("关联脚本") == script_code
        ]

    # ---------- 预演状态与字段定位清单的持久化 ----------

    def _load_state(self, template_code: str) -> dict[str, Any]:
        state = persist.read_json(_STATE_SUB, _state_path_name(template_code))
        if state is None:
            state = {
                "模板编号": template_code,
                "pages": [dict(page) for page in REHEARSAL_PAGES.get(template_code, [])],
                "runs": [],
            }
            persist.write_json(_STATE_SUB, _state_path_name(template_code), state)
        return state

    def _save_state(self, template_code: str, state: dict[str, Any]) -> None:
        persist.write_json(_STATE_SUB, _state_path_name(template_code), state)

    def _load_manifest(self, template: dict[str, Any]) -> dict[str, Any]:
        code = template.get("模板编号", "")
        manifest = persist.read_json(_MANIFEST_SUB, _state_path_name(code))
        if manifest is None:
            manifest = {
                "模板编号": code,
                "抽取字段": template.get("抽取字段", ""),
                "关联脚本": template.get("关联脚本", ""),
                "matches": [],
                "confirmed": None,
                "updated_at": "",
            }
        return manifest

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        manifest["updated_at"] = persist.now_iso()
        persist.write_json(_MANIFEST_SUB, _state_path_name(manifest["模板编号"]), manifest)

    # ---------- 页面版本录入 ----------

    def register_page(
        self,
        template_code: str,
        version: str,
        dom: str,
        source: str | None = None,
    ) -> dict[str, Any]:
        """录入一个页面版本的 DOM 快照，并同步登记 page_snapshot 行。"""
        template = self._template(template_code)
        version = version.strip()
        dom = dom.strip()
        if not version:
            raise RehearsalError("页面版本不能为空")
        if not dom:
            raise RehearsalError("DOM 内容不能为空")
        state = self._load_state(template_code)
        if any(page["页面版本"] == version for page in state["pages"]):
            raise RehearsalError(f"页面版本 {version} 已录入，结构不同的页面请使用新版本号")

        # 同步登记 page_snapshot 行，让页面快照模块能看到这次录入
        from app.services.page_snapshot import PageSnapshotService

        existing = store.rows("page_snapshot")
        numbers = [
            int(m.group(1))
            for row in existing
            if (m := re.fullmatch(r"PAGE-(\d+)", str(row.get("快照编号", ""))))
        ]
        snapshot_code = f"PAGE-{max(numbers, default=0) + 1:04d}"
        snapshot_svc = PageSnapshotService()
        entry, missing = snapshot_svc.create_entry({
            "快照编号": snapshot_code,
            "采集来源": source or str(template.get("关联脚本", "")),
            "页面版本": version,
            "DOM摘要": re.sub(r"\s+", " ", dom)[:60],
            "快照时间": persist.now_iso()[:10],
            "快照类型": "预演录入",
            "数据量": f"{len(dom)}B",
            "回收时间": "-",
        })
        if missing:
            raise RehearsalError(f"页面快照登记缺少字段：{'、'.join(missing)}")
        snapshot_svc.run_action(int(entry["id"]), "标记存档")

        page = {
            "页面版本": version,
            "快照编号": snapshot_code,
            "dom": dom,
            "登记时间": persist.now_iso(),
        }
        state["pages"].append(page)
        self._save_state(template_code, state)
        return {k: v for k, v in page.items() if k != "dom"} | {"dom预览": dom[:120]}

    # ---------- 锚点评估 ----------

    def _selector_of(self, anchor: dict[str, Any]) -> tuple[str, str]:
        """按选择器类型取表达式；表达式为空时回退到另一种。"""
        kind = str(anchor.get("选择器类型", "")).strip().lower()
        css = str(anchor.get("CSS表达式", "") or "").strip()
        xpath = str(anchor.get("XPath表达式", "") or "").strip()
        if kind.startswith("xpath"):
            return ("XPath", xpath) if xpath else ("CSS", css)
        return ("CSS", css) if css else ("XPath", xpath)

    def _evaluate_anchor(self, anchor: dict[str, Any], root: Node) -> dict[str, Any]:
        """在 DOM 上评估单个锚点，返回命中节点、值与片段。"""
        kind, expr = self._selector_of(anchor)
        result: dict[str, Any] = {
            "锚点编号": anchor.get("锚点编号", ""),
            "选择器类型": kind,
            "选择器": expr,
            "命中": False,
            "命中数": 0,
            "值": None,
            "节点路径": "",
            "片段": "",
            "错误": "",
        }
        if not expr:
            result["错误"] = "锚点未配置选择器表达式"
            return result
        try:
            nodes = css_select(root, expr) if kind == "CSS" else xpath_select(root, expr)
        except ValueError as exc:
            result["错误"] = str(exc)
            return result

        text_filter = str(anchor.get("文本匹配", "") or "").strip()
        if text_filter:
            nodes = [n for n in nodes if text_filter in n.text()]
        result["命中数"] = len(nodes)
        if not nodes:
            return result

        order_raw = str(anchor.get("元素顺序", "") or "").strip()
        order = int(order_raw) if order_raw.isdigit() else 1
        if order < 1 or order > len(nodes):
            result["错误"] = f"元素顺序 {order_raw} 超出命中数 {len(nodes)}"
            return result
        node = nodes[order - 1]
        result.update({
            "命中": True,
            "值": node.text().strip(),
            "节点路径": node_path(node),
            "片段": outer_html(node),
        })
        return result

    # ---------- 运行预演 ----------

    def run_rehearsal(self, template_code: str, version: str) -> dict[str, Any]:
        """在指定页面版本上评估全部候选锚点，把实际匹配写入字段定位清单。"""
        template = self._template(template_code)
        state = self._load_state(template_code)
        page = next((p for p in state["pages"] if p["页面版本"] == version), None)
        if page is None:
            raise RehearsalError(f"页面版本 {version} 尚未录入模板 {template_code}")

        anchors = self._anchors(str(template.get("关联脚本", "")))
        root = parse_dom(page["dom"])
        evaluations = [self._evaluate_anchor(anchor, root) for anchor in anchors]
        hits = [e for e in evaluations if e["命中"]]
        conflict = len(hits) >= 2

        # 写入字段定位清单：同一版本的旧匹配被本次预演替换
        manifest = self._load_manifest(template)
        confirmed = manifest.get("confirmed")
        manifest["matches"] = [m for m in manifest["matches"] if m["页面版本"] != version]
        for eva in hits:
            if confirmed and eva["锚点编号"] == confirmed["锚点编号"]:
                status = "已采纳"
            elif confirmed:
                status = "冲突未采纳"
            else:
                status = "候选"
            manifest["matches"].append({
                "锚点编号": eva["锚点编号"],
                "选择器": eva["选择器"],
                "选择器类型": eva["选择器类型"],
                "页面版本": version,
                "节点路径": eva["节点路径"],
                "片段": eva["片段"],
                "值": eva["值"],
                "状态": status,
                "记录时间": persist.now_iso(),
            })
        self._save_manifest(manifest)

        state["runs"].append({
            "页面版本": version,
            "时间": persist.now_iso(),
            "锚点数": len(evaluations),
            "命中数": len(hits),
            "冲突": conflict,
        })
        self._save_state(template_code, state)
        persist.append_jsonl("runs", "extract_rehearsal.jsonl", {
            "module": "data_extract",
            "entity": "抽取预演",
            "模板编号": template_code,
            "页面版本": version,
            "action": "run_rehearsal",
            "命中数": len(hits),
            "冲突": conflict,
            "timestamp": persist.now_iso(),
        })
        return {"evaluations": evaluations, "conflict": conflict, "manifest": manifest}

    # ---------- 提交预演：确立唯一可执行来源 ----------

    def confirm_binding(self, template_code: str, version: str, anchor_code: str) -> dict[str, Any]:
        """采纳一个锚点作为该字段的唯一可执行来源，采纳值随页面版本与匹配节点持久化。"""
        template = self._template(template_code)
        manifest = self._load_manifest(template)
        match = next(
            (m for m in manifest["matches"]
             if m["页面版本"] == version and m["锚点编号"] == anchor_code),
            None,
        )
        if match is None:
            # 该版本还没跑过预演：先补跑一次再取匹配
            self.run_rehearsal(template_code, version)
            manifest = self._load_manifest(template)
            match = next(
                (m for m in manifest["matches"]
                 if m["页面版本"] == version and m["锚点编号"] == anchor_code),
                None,
            )
        if match is None:
            raise RehearsalError(f"锚点 {anchor_code} 在版本 {version} 上未命中，无法采纳")

        manifest["confirmed"] = {
            "锚点编号": anchor_code,
            "选择器": match["选择器"],
            "页面版本": version,
            "节点路径": match["节点路径"],
            "值": match["值"],
            "确认时间": persist.now_iso(),
        }
        # 一份预演提交后只保留一个可执行来源：其余锚点的匹配全部转为冲突未采纳
        for item in manifest["matches"]:
            item["状态"] = "已采纳" if item["锚点编号"] == anchor_code else "冲突未采纳"
        self._save_manifest(manifest)
        persist.append_jsonl("runs", "extract_rehearsal.jsonl", {
            "module": "data_extract",
            "entity": "抽取预演",
            "模板编号": template_code,
            "页面版本": version,
            "action": "confirm_binding",
            "锚点编号": anchor_code,
            "timestamp": persist.now_iso(),
        })
        return manifest

    # ---------- 预演视图 ----------

    def rehearsal_view(self, template_code: str) -> dict[str, Any]:
        """汇总预演视图：每版实际获得的值、样本行与冲突排除项。"""
        template = self._template(template_code)
        state = self._load_state(template_code)
        manifest = self._load_manifest(template)
        confirmed = manifest.get("confirmed")
        anchors = self._anchors(str(template.get("关联脚本", "")))
        match_status = {
            (m["锚点编号"], m["页面版本"]): m["状态"] for m in manifest["matches"]
        }

        versions: list[dict[str, Any]] = []
        for page in state["pages"]:
            version = page["页面版本"]
            root = parse_dom(page["dom"])
            evaluations = []
            for anchor in anchors:
                eva = self._evaluate_anchor(anchor, root)
                eva["状态"] = match_status.get(
                    (eva["锚点编号"], version),
                    "候选" if eva["命中"] else "未命中",
                )
                evaluations.append(eva)

            # 样本行：只有已确认的来源能产出计入样本的值
            sample_value = None
            if confirmed:
                source = next(
                    (e for e in evaluations if e["锚点编号"] == confirmed["锚点编号"]), None,
                )
                if source and source["命中"]:
                    sample_value = source["值"]
            sample = {
                "字段": template.get("抽取字段", ""),
                "值": sample_value,
                "来源锚点": confirmed["锚点编号"] if confirmed else None,
                "计入样本": confirmed is not None and sample_value is not None,
            }

            # 冲突排除：命中但没进入样本的匹配，保留候选值和来源
            excluded = []
            for eva in evaluations:
                if not eva["命中"]:
                    continue
                if confirmed and eva["锚点编号"] == confirmed["锚点编号"]:
                    continue
                excluded.append({
                    "锚点编号": eva["锚点编号"],
                    "值": eva["值"],
                    "节点路径": eva["节点路径"],
                    "原因": "冲突未采纳" if confirmed else "未确认绑定",
                })
            versions.append({
                "页面版本": version,
                "快照编号": page["快照编号"],
                "登记时间": page["登记时间"],
                "evaluations": evaluations,
                "sample": sample,
                "excluded": excluded,
            })

        counted = sum(1 for v in versions if v["sample"]["计入样本"])
        stats = {
            "版本数": len(versions),
            "样本行数": len(versions),
            "计入样本数": counted,
            "未计入样本数": len(versions) - counted,
            "冲突排除数": sum(len(v["excluded"]) for v in versions),
            "已确认来源": confirmed is not None,
        }
        return {
            "模板": {
                "模板编号": template.get("模板编号", ""),
                "抽取字段": template.get("抽取字段", ""),
                "关联脚本": template.get("关联脚本", ""),
                "status": template.get("status", ""),
            },
            "anchors": [
                {
                    "锚点编号": a.get("锚点编号", ""),
                    "选择器类型": a.get("选择器类型", ""),
                    "CSS表达式": a.get("CSS表达式", ""),
                    "XPath表达式": a.get("XPath表达式", ""),
                    "文本匹配": a.get("文本匹配", ""),
                    "元素顺序": a.get("元素顺序", ""),
                    "status": a.get("status", ""),
                }
                for a in anchors
            ],
            "pages": [
                {
                    "页面版本": p["页面版本"],
                    "快照编号": p["快照编号"],
                    "登记时间": p["登记时间"],
                    "dom预览": p["dom"][:120],
                }
                for p in state["pages"]
            ],
            "runs": state["runs"],
            "manifest": manifest,
            "versions": versions,
            "stats": stats,
        }
