"""CSV exports shared by modules. Every export is permission-checked by the
route and recorded in the audit log."""

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext
from app.core.request_meta import RequestMeta
from app.modules.audit.models import AuditOutcome
from app.modules.audit.service import record_event

# Spreadsheet apps execute cells starting with these characters as formulas.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        text = value.isoformat(timespec="minutes")
    elif isinstance(value, date):
        text = value.isoformat()
    else:
        text = str(value)
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def _xlsx_cell(value: object) -> object:
    if isinstance(value, bool) or value is None:
        return "" if value is None else str(value)
    if isinstance(value, int | float | Decimal):
        return value
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return value
    return _cell(value)


def xlsx_response(
    filename: str, sheets: Sequence[tuple[str, Sequence[str], Iterable[Sequence[object]]]]
) -> Response:
    """One worksheet per (title, header, rows). Text never becomes a formula."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    workbook.remove(workbook.active)
    used: set[str] = set()
    for title, header, rows in sheets:
        name = "".join(ch for ch in title if ch not in "[]:*?/\\")[:28] or "Sheet"
        base, n = name, 2
        while name in used:
            name, n = f"{base[:25]} {n}", n + 1
        used.add(name)
        sheet = workbook.create_sheet(name)
        sheet.append([_cell(h) for h in header])
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in rows:
            sheet.append([_xlsx_cell(v) for v in row])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def csv_response(
    filename: str, header: Sequence[str], rows: Iterable[Sequence[object]]
) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if header:
        writer.writerow(header)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def record_export(
    session: AsyncSession, auth: AuthContext, dataset: str, rows: int, meta: RequestMeta
) -> None:
    await record_event(
        session,
        action="data.export",
        outcome=AuditOutcome.SUCCESS,
        actor_user_id=auth.user.id,
        company_id=auth.user.company_id,
        resource_type=dataset,
        meta=meta,
        details={"dataset": dataset, "rows": rows},
    )
    await session.commit()
