"""CSV exports shared by modules. Every export is permission-checked by the
route and recorded in the audit log."""

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date, datetime

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


def csv_response(
    filename: str, header: Sequence[str], rows: Iterable[Sequence[object]]
) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
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
