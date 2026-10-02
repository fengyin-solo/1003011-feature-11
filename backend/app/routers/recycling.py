"""物资回收接口：物资去向清单的查询、汇总与导出；登记入口在拆站管理的批量回收接口。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import PageResult
from app.services.recycling import RecyclingService

router = APIRouter(prefix="/api/recycling", tags=["物资回收"])

service = RecyclingService()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按任务编号检索"),
    category: str | None = Query(default=None, description="按物资类别过滤"),
    destination: str | None = Query(default=None, description="按物资去向检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """物资去向清单：每落一条回收登记，这里跟着多出一条；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, category=category, destination=destination, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/summary")
def summary() -> dict[str, Any]:
    """回收汇总：记录数、回收款合计、差异笔数，给页头统计卡用。"""
    return service.summary()


@router.get("/catalog")
def catalog() -> dict[str, Any]:
    """物资类别单价表：回收款按类别单价结算，登记时逐条带出。"""
    return {"items": service.categories()}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出物资去向清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "recycling", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条回收记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"回收记录 {entry_id} 不存在或已归档")
    return entry
