"""拆站管理接口：维护拆站任务，覆盖提交审批、开始拆除、回收完成等动作；物资回收走批量登记。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult, RecyclingBatchPayload
from app.services.demolition import DemolitionService
from app.services.recycling import RecyclingService

router = APIRouter(prefix="/api/demolition", tags=["拆站管理"])

service = DemolitionService()
recycling = RecyclingService()

LIST_FIELDS = ["任务编号", "拆除站点", "拆除原因", "拆除范围", "施工队伍", "计划工期", "物资回收", "任务状态"]
STATUSES = ["待审批", "已批复", "拆除中", "已拆除"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按任务编号检索"),
    status: str | None = Query(default=None, description="待审批、已批复、拆除中、已拆除"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按任务编号与状态过滤拆站管理列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/recycling/preview")
def recycling_preview(payload: RecyclingBatchPayload) -> dict[str, Any]:
    """把勾选任务里没登记的物资类别逐条带出来（含单位、单价），登记中断的从缺的那一类接着填。"""
    if not payload.task_ids:
        raise HTTPException(status_code=400, detail="请先勾选同一批拆站任务，再登记物资回收")
    return recycling.preview(payload.task_ids)


@router.post("/recycling/batch", response_model=ActionResult)
def recycling_batch(payload: RecyclingBatchPayload) -> ActionResult:
    """批量登记回收数量与去向：缺去向的行单独退回并说明是第几行，其余照常落记录。"""
    result, message = recycling.register_batch(payload.task_ids, payload.rows)
    if result is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=bool(result["ok"]), message=message, entry=result)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出拆站管理清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "demolition", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条拆站任务明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"拆站任务 {entry_id} 不存在或已归档")
    return entry


@router.get("/{entry_id}/recycling")
def recycling_progress(entry_id: int) -> dict[str, Any]:
    """单任务回收进度：各类别登记情况、接着填哪一类、回收款合计。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"拆站任务 {entry_id} 不存在或已归档")
    progress = recycling.progress_for_task(entry_id)
    return {"任务编号": entry.get("任务编号"), **progress}


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条拆站任务，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="拆站任务已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条拆站任务执行提交审批、开始拆除、回收完成；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
