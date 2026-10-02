"""拆站管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "demolition"
REQUIRED_FIELDS = ["任务编号", "拆除站点", "拆除原因"]
STATUS_ORDER = ["待审批", "已批复", "拆除中", "已拆除"]
ACTION_RULES = {"提交审批": "已批复", "开始拆除": "拆除中", "回收完成": "已拆除"}
NEGATIVE_ACTIONS = []

# 物资类别价目表：回收款按类别单价结算，登记数量是拆除时登记的应回收数量
MATERIAL_CATALOG: list[dict[str, Any]] = [
    {"物资类别": "蓄电池", "单位": "组", "登记数量": 2, "单价": 1200.0},
    {"物资类别": "铁塔材料", "单位": "吨", "登记数量": 4, "单价": 3600.0},
    {"物资类别": "馈线", "单位": "米", "登记数量": 300, "单价": 45.0},
    {"物资类别": "开关电源", "单位": "台", "登记数量": 1, "单价": 800.0},
]


def _new_materials() -> list[dict[str, Any]]:
    """按价目表给新任务生成一份待登记的物资清单。"""
    return [
        {**item, "回收数量": None, "去向": "", "差异说明": "", "回收款": None, "已登记": False}
        for item in MATERIAL_CATALOG
    ]


def _parse_quantity(raw: Any) -> float | None:
    """回收数量只接受非负数字，其余一律视为无效。"""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


class DemolitionService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("任务编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["物资清单"] = _new_materials()
        entry["回收记录"] = []
        entry["物资回收"] = "未登记"
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"拆站任务 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于拆站管理可执行范围"
        if action == "回收完成":
            missing = [m["物资类别"] for m in entry.get("物资清单", []) if not m.get("已登记")]
            if missing:
                return None, f"物资回收未登记完（{'、'.join(missing)}），不能标为已拆除"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"拆站任务已{action}"

    def register_recycling(
        self, entry_id: int, items: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, str, list[dict[str, Any]], list[dict[str, Any]]]:
        """批量登记物资回收：逐行校验，合格的落记录，不合格的按行号退回。

        退回不牵连其他行；同一类物资已登记过的再次提交只退回不重复结算。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"拆站任务 {entry_id} 不存在或已归档", [], []
        status = entry.get("status")
        if status != "拆除中":
            return None, f"任务当前状态为「{status}」，只有拆除中的任务能登记物资回收", [], []
        if not items:
            return None, "没有需要登记的物资行，请先勾选物资", [], []
        materials = entry.setdefault("物资清单", [])
        by_category = {str(m.get("物资类别")): m for m in materials}
        settled: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for index, raw in enumerate(items, start=1):
            if not isinstance(raw, dict):
                rejected.append({"row": index, "reason": "这一行不是有效的物资登记内容"})
                continue
            category = str(raw.get("物资类别") or "").strip()
            if not category:
                rejected.append({"row": index, "reason": "物资类别为空"})
                continue
            target = by_category.get(category)
            if target is None:
                rejected.append({"row": index, "reason": f"物资类别「{category}」不在本任务的物资清单里"})
                continue
            if target.get("已登记"):
                rejected.append({"row": index, "reason": f"「{category}」已登记过，同一批物资只结算一次"})
                continue
            quantity = _parse_quantity(raw.get("回收数量"))
            if quantity is None:
                rejected.append({"row": index, "reason": f"「{category}」回收数量缺失或不是有效数字"})
                continue
            destination = str(raw.get("去向") or "").strip()
            if not destination:
                rejected.append({"row": index, "reason": f"「{category}」缺去向"})
                continue
            note = str(raw.get("差异说明") or "").strip()
            if quantity < float(target.get("登记数量") or 0) and not note:
                rejected.append({"row": index, "reason": f"「{category}」回收数量少于登记数量，需说明差异在哪"})
                continue
            amount = round(quantity * float(target.get("单价") or 0), 2)
            target.update({
                "回收数量": quantity,
                "去向": destination,
                "差异说明": note,
                "回收款": amount,
                "已登记": True,
            })
            record = {
                "任务编号": entry.get("任务编号"),
                "拆除站点": entry.get("拆除站点"),
                "物资类别": category,
                "回收数量": quantity,
                "单价": target.get("单价"),
                "回收款": amount,
                "去向": destination,
                "差异说明": note,
                "登记时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            entry.setdefault("回收记录", []).append(record)
            settled.append(record)
        self._refresh_conclusion(entry)
        if rejected:
            message = f"已落记录 {len(settled)} 行，退回 {len(rejected)} 行（退回明细见返回结果）"
        else:
            message = f"物资回收已登记 {len(settled)} 行，本次回收款合计 ¥{sum(r['回收款'] for r in settled):.2f}"
        return entry, message, settled, rejected

    def recycling_ledger(
        self,
        *,
        keyword: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """物资去向清单：把各任务的回收记录摊平成一张清单，每登记一条这里多一条。"""
        rows: list[dict[str, Any]] = []
        for entry in store.rows(MODULE):
            rows.extend(entry.get("回收记录", []))
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("任务编号", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [dict(row, id=start + offset + 1) for offset, row in enumerate(rows[start:start + size])], total

    def _refresh_conclusion(self, entry: dict[str, Any]) -> None:
        """把回收结论写回拆站台账的「物资回收」字段。"""
        materials = entry.get("物资清单") or []
        done = sum(1 for m in materials if m.get("已登记"))
        total = len(materials)
        if total == 0:
            entry["物资回收"] = "无回收物资"
        elif done < total:
            entry["物资回收"] = f"已登记 {done}/{total} 类"
        else:
            amount = sum(float(m.get("回收款") or 0) for m in materials)
            entry["物资回收"] = f"回收完成，回收款合计 ¥{amount:.2f}"
