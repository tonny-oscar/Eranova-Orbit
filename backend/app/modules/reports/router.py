import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_request_meta, require_permission
from app.api.exports import csv_response, xlsx_response
from app.core.request_meta import RequestMeta
from app.db.session import get_db
from app.modules.reports import service
from app.modules.reports.generators import available
from app.modules.reports.service import (
    RunSummary,
    ScheduleIn,
    ScheduleOut,
    SchedulePatch,
    resolve_period,
)

router = APIRouter(prefix="/reports", tags=["reports"])
READ = Depends(require_permission("report.read"))


@router.get("")
async def catalogue(auth: AuthContext = READ) -> list[dict]:
    return [
        {"key": r.key, "title": r.title, "description": r.description}
        for r in available(auth.principal)
    ]


@router.get("/schedules", response_model=list[ScheduleOut])
async def list_schedules(auth: AuthContext = READ, db: AsyncSession = Depends(get_db)):
    rows = await service.list_schedules(db, auth.principal)
    return await service.schedule_outs(db, auth.principal, rows)


@router.post("/schedules", response_model=ScheduleOut, status_code=201)
async def create_schedule(
    payload: ScheduleIn,
    auth: AuthContext = Depends(require_permission("report.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
):
    s = await service.create_schedule(db, auth.user, auth.principal, payload, meta)
    return (await service.schedule_outs(db, auth.principal, [s]))[0]


@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(
    schedule_id: uuid.UUID,
    payload: SchedulePatch,
    auth: AuthContext = Depends(require_permission("report.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
):
    s = await service.update_schedule(db, auth.user, auth.principal, schedule_id, payload, meta)
    return (await service.schedule_outs(db, auth.principal, [s]))[0]


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("report.create")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    await service.delete_schedule(db, auth.user, auth.principal, schedule_id, meta)
    return Response(status_code=204)


@router.get("/runs", response_model=list[RunSummary])
async def my_runs(auth: AuthContext = READ, db: AsyncSession = Depends(get_db)):
    return [
        RunSummary.model_validate(r, from_attributes=True)
        for r in await service.my_runs(db, auth.principal)
    ]


@router.get("/runs/{run_id}")
async def get_run(
    run_id: uuid.UUID, auth: AuthContext = READ, db: AsyncSession = Depends(get_db)
) -> dict:
    run = await service.get_run(db, auth.principal, run_id)
    return {**run.data, "run_id": str(run.id), "title": run.title}


@router.get("/{key}")
async def run_report(
    key: str,
    start: date | None = None,
    end: date | None = None,
    product_id: uuid.UUID | None = None,
    auth: AuthContext = READ,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await service.run_report(db, auth.principal, key, resolve_period(start, end), product_id)


@router.get("/{key}/export")
async def export_report(
    key: str,
    file_format: str = Query("xlsx", alias="format", pattern="^(csv|xlsx)$"),
    start: date | None = None,
    end: date | None = None,
    product_id: uuid.UUID | None = None,
    auth: AuthContext = Depends(require_permission("report.export")),
    db: AsyncSession = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
) -> Response:
    period = resolve_period(start, end)
    report = await service.run_report(db, auth.principal, key, period, product_id)
    await service.record_report_export(db, auth.user, key, file_format, meta)
    name = f"{key}-report-{period.start}-to-{period.end}"
    tables = service.flatten(report)
    if file_format == "xlsx":
        about = (
            "About",
            ["Field", "Value"],
            [
                ["Report", report["title"]],
                ["Period start", report["period"]["start"]],
                ["Period end", report["period"]["end"]],
                ["Generated at (UTC)", report["generated_at"]],
                ["Generated for", auth.user.full_name],
            ],
        )
        return xlsx_response(f"{name}.xlsx", [about, *tables])
    rows: list[list] = [
        ["Report", report["title"]],
        ["Period", f"{period.start} to {period.end}"],
        ["Generated at (UTC)", report["generated_at"]],
    ]
    for title, header, body in tables:
        rows += [[], [title], header, *body]
    return csv_response(f"{name}.csv", [], rows)
