"""物资回收业务规则：类别单价、批量登记、差异校验与拆站台账回写都收在这里。

拆站任务拆除完成后要按物资类别登记回收数量与去向；回收款按类别单价结算，
同一批物资重复登记只结算一次。登记齐了的任务会把回收结论写回拆站台账。
"""
from __future__ import annotations

import datetime
from typing import Any

from app.store import store

MODULE = "recycling"
DEMOLITION_MODULE = "demolition"

# 物资类别单价表：回收款按类别单价结算，批量登记时逐条带出；不在表里的类别一律不收。
MATERIAL_CATEGORIES: list[dict[str, Any]] = [
    {"物资类别": "蓄电池", "单位": "组", "单价": 450.0},
    {"物资类别": "铁塔钢材", "单位": "吨", "单价": 2800.0},
    {"物资类别": "馈线", "单位": "米", "单价": 12.0},
    {"物资类别": "开关电源", "单位": "台", "单价": 800.0},
    {"物资类别": "空调", "单位": "台", "单价": 350.0},
    {"物资类别": "其他物资", "单位": "批", "单价": 100.0},
]


def _parse_quantity(raw: Any) -> float | None:
    """数量只认非负数字；填了文字、负数或留空都视为没填对，返回 None。"""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _fmt_quantity(value: float) -> str:
    """数量展示去掉多余的 .0：4.0 记成 4，10.5 保持 10.5。"""
    return str(int(value)) if float(value).is_integer() else str(value)


class RecyclingService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        category: str | None = None,
        destination: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("任务编号", ""))]
        if category:
            rows = [row for row in rows if row.get("物资类别") == category]
        if destination:
            rows = [row for row in rows if destination in str(row.get("物资去向", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def summary(self) -> dict[str, Any]:
        """页头统计卡用：回收记录数、回收款合计、有差异说明的笔数。"""
        rows = store.rows(MODULE)
        return {
            "记录数": len(rows),
            "回收款合计": round(sum(float(row.get("回收款", 0) or 0) for row in rows), 2),
            "差异笔数": sum(1 for row in rows if str(row.get("差异说明") or "").strip()),
        }

    def categories(self) -> list[dict[str, Any]]:
        return [dict(item) for item in MATERIAL_CATEGORIES]

    def records_for_task(self, task_id: int) -> list[dict[str, Any]]:
        return [row for row in store.rows(MODULE) if int(row.get("任务ID", 0) or 0) == task_id]

    def progress_for_task(self, task_id: int) -> dict[str, Any]:
        """单任务回收进度：各类别登记情况、还没登记的类别、接着该填哪一类。"""
        records = self.records_for_task(task_id)
        by_category = {row.get("物资类别"): row for row in records}
        items: list[dict[str, Any]] = []
        missing: list[str] = []
        for cat in MATERIAL_CATEGORIES:
            record = by_category.get(cat["物资类别"])
            items.append({
                "物资类别": cat["物资类别"],
                "单位": cat["单位"],
                "单价": cat["单价"],
                "已登记": record is not None,
                "记录编号": record.get("记录编号") if record else None,
                "回收数量": record.get("回收数量") if record else None,
                "物资去向": record.get("物资去向") if record else None,
            })
            if record is None:
                missing.append(cat["物资类别"])
        return {
            "类别进度": items,
            "未登记类别": missing,
            "接着填": missing[0] if missing else None,
            "登记完成": not missing,
            "回收款合计": round(sum(float(row.get("回收款", 0) or 0) for row in records), 2),
        }

    def preview(self, task_ids: list[int]) -> dict[str, Any]:
        """把勾选任务里还没登记的物资类别逐条带出来（含单位、单价）。

        登记中断过的任务只带缺的那几类，打开面板就是从断点接着填。
        """
        rows_out: list[dict[str, Any]] = []
        tasks: list[dict[str, Any]] = []
        for task_id in task_ids:
            task = store.find(DEMOLITION_MODULE, task_id)
            if task is None:
                continue
            progress = self.progress_for_task(task_id)
            tasks.append({
                "task_id": task_id,
                "任务编号": task.get("任务编号"),
                "拆除站点": task.get("拆除站点"),
                "接着填": progress["接着填"],
                "未登记类别": progress["未登记类别"],
                "登记完成": progress["登记完成"],
            })
            for item in progress["类别进度"]:
                if item["已登记"]:
                    continue
                rows_out.append({
                    "行号": len(rows_out) + 1,
                    "task_id": task_id,
                    "任务编号": task.get("任务编号"),
                    "拆除站点": task.get("拆除站点"),
                    "物资类别": item["物资类别"],
                    "单位": item["单位"],
                    "单价": item["单价"],
                })
        return {"rows": rows_out, "tasks": tasks}

    def register_batch(self, task_ids: list[int], rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
        """批量登记回收数量与去向。

        逐行校验：缺去向的单独退回并说明是第几行，其余照常落记录；
        同一批物资重复登记只结算一次。返回 (结果, 消息)，结果为 None 表示整批没法处理。
        """
        if not task_ids:
            return None, "请先勾选同一批拆站任务，再登记物资回收"
        if not rows:
            return None, "没有可登记的回收行，请先带出待登记物资"
        tasks: dict[int, dict[str, Any]] = {}
        for task_id in task_ids:
            task = store.find(DEMOLITION_MODULE, task_id)
            if task is not None:
                tasks[task_id] = task
        if not tasks:
            return None, "勾选的拆站任务都不存在或已归档"
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for line_no, raw in enumerate(rows, start=1):
            record, reason = self._accept_row(raw, tasks)
            if record is None:
                rejected.append({"行号": line_no, "原因": reason})
            else:
                accepted.append(record)
        # 落完一批再统一回看：登记齐了的任务把回收结论写回拆站台账
        for task in tasks.values():
            self._write_back_conclusion(task)
        settled = round(sum(float(record["回收款"]) for record in accepted), 2)
        result = {"ok": not rejected, "已登记": accepted, "退回": rejected, "回收款合计": settled}
        if rejected:
            detail = "；".join(f"第{item['行号']}行{item['原因']}" for item in rejected)
            message = f"已落记录 {len(accepted)} 条，回收款合计 {settled} 元；退回 {len(rejected)} 行：{detail}"
        else:
            message = f"批量登记完成：落记录 {len(accepted)} 条，回收款合计 {settled} 元"
        return result, message

    def _accept_row(
        self, raw: dict[str, Any], tasks: dict[int, dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, str]:
        label = f"（{raw.get('任务编号') or raw.get('task_id') or '?'}·{raw.get('物资类别') or '?'}）"
        try:
            task_id = int(raw.get("task_id"))
        except (TypeError, ValueError):
            return None, f"{label}没有对应的拆站任务"
        task = tasks.get(task_id)
        if task is None:
            return None, f"{label}的任务不在本批勾选范围"
        category = str(raw.get("物资类别") or "").strip()
        info = next((cat for cat in MATERIAL_CATEGORIES if cat["物资类别"] == category), None)
        if info is None:
            return None, f"{label}物资类别不在单价表里"
        declared = _parse_quantity(raw.get("登记数量"))
        recovered = _parse_quantity(raw.get("回收数量"))
        if declared is None or recovered is None:
            return None, f"{label}登记数量与回收数量要填非负数字"
        destination = str(raw.get("物资去向") or "").strip()
        if not destination:
            return None, "缺物资去向"
        note = str(raw.get("差异说明") or "").strip()
        if recovered < declared and not note:
            return None, f"{label}回收数量少于登记数量，要说明差异在哪"
        # 同一批物资重复登记只结算一次：已落过记录的类别不再重复登记
        if any(row.get("物资类别") == category for row in self.records_for_task(task_id)):
            return None, f"{label}重复登记，同一批物资只结算一次"
        amount = round(recovered * float(info["单价"]), 2)
        rows = store.rows(MODULE)
        record_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        record = {
            "id": record_id,
            "status": "已结算",
            "pending": False,
            "abnormal": bool(note),
            "记录编号": f"RECY-{record_id:04d}",
            "任务编号": task.get("任务编号"),
            "任务ID": task_id,
            "拆除站点": task.get("拆除站点"),
            "物资类别": category,
            "单位": info["单位"],
            "登记数量": declared,
            "回收数量": recovered,
            "差异说明": note,
            "单价": info["单价"],
            "回收款": amount,
            "物资去向": destination,
            "登记时间": datetime.date.today().isoformat(),
        }
        rows.append(record)
        return record, ""

    def _write_back_conclusion(self, task: dict[str, Any]) -> None:
        """物资登记齐了之后，把回收结论写回拆站台账；去向明细以物资去向清单为准。"""
        task_id = int(task.get("id", 0))
        progress = self.progress_for_task(task_id)
        if not progress["登记完成"]:
            return
        records = sorted(self.records_for_task(task_id), key=lambda row: int(row.get("id", 0)))
        conclusion = "；".join(
            f"{row['物资类别']}{_fmt_quantity(float(row.get('回收数量', 0) or 0))}{row.get('单位', '')}→{row.get('物资去向', '')}"
            for row in records
        )
        task["物资回收"] = f"已回收{len(MATERIAL_CATEGORIES)}类·回收款合计{progress['回收款合计']}元"
        task["回收结论"] = conclusion
        task["回收款合计"] = progress["回收款合计"]
