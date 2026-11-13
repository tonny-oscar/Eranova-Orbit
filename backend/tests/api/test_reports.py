import io
from datetime import timedelta

from openpyxl import load_workbook
from sqlalchemy import select

from app import worker
from app.db.base import utc_now
from app.modules.reports.models import ReportRun, ReportSchedule
from tests.conftest import login


async def _seed(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    for i, source in enumerate(["website", "website", "=HYPERLINK(1)"]):
        r = await client.post(
            "/api/v1/leads",
            json={"full_name": f"Lead {i}", "email": f"lead{i}@example.com", "source": source},
            headers=h,
        )
        assert r.status_code == 201, r.text
    return h


async def test_catalogue_and_sections_follow_permissions(client, make_user):
    await _seed(client, make_user)
    await make_user("sales@eranova.co.ke", role="sales")
    await login(client, "sales@eranova.co.ke")
    keys = {r["key"] for r in (await client.get("/api/v1/reports")).json()}
    assert {"executive", "sales", "product"} <= keys
    assert "support" not in keys and "people" not in keys
    assert (await client.get("/api/v1/reports/support")).status_code == 403

    executive = (await client.get("/api/v1/reports/executive")).json()
    titles = [s["title"] for s in executive["sections"]]
    assert "Sales" in titles and "Support" not in titles
    sales = (await client.get("/api/v1/reports/sales")).json()
    summary = {m["label"]: m["value"] for m in sales["sections"][0]["metrics"]}
    assert summary["New leads"] == 3
    by_source = dict(map(tuple, sales["sections"][1]["rows"]))
    assert by_source["website"] == 2


async def test_excel_export_is_audited_and_formula_safe(client, make_user):
    await _seed(client, make_user)
    r = await client.get("/api/v1/reports/sales/export", params={"format": "xlsx"})
    assert r.status_code == 200
    book = load_workbook(io.BytesIO(r.content))
    assert book.sheetnames[0] == "About"
    values = [c.value for row in book["New leads by source"].iter_rows() for c in row]
    assert "'=HYPERLINK(1)" in values
    csv = await client.get("/api/v1/reports/sales/export", params={"format": "csv"})
    assert "'=HYPERLINK(1)" in csv.text
    await make_user("sales@eranova.co.ke", role="sales")
    await login(client, "sales@eranova.co.ke")
    assert (await client.get("/api/v1/reports/sales/export")).status_code == 403


async def test_scheduled_reports_respect_recipient_access(client, make_user, db):
    h = await _seed(client, make_user)
    sales = await make_user("sales@eranova.co.ke", role="sales")
    hr = await make_user("hr@eranova.co.ke", role="hr")
    rejected = await client.post(
        "/api/v1/reports/schedules",
        json={
            "name": "Weekly sales",
            "report_key": "sales",
            "frequency": "weekly",
            "range_days": 7,
            "recipient_user_ids": [str(sales.id), str(hr.id)],
        },
        headers=h,
    )
    assert rejected.json()["error"]["code"] == "recipient_not_permitted"
    created = await client.post(
        "/api/v1/reports/schedules",
        json={
            "name": "Weekly sales",
            "report_key": "sales",
            "frequency": "weekly",
            "range_days": 7,
            "recipient_user_ids": [str(sales.id)],
        },
        headers=h,
    )
    assert created.status_code == 201, created.text
    schedule = await db.get(ReportSchedule, created.json()["id"])
    first = schedule.next_run_at
    schedule.next_run_at = utc_now() - timedelta(minutes=1)
    await db.commit()

    await worker.scheduled_reports(db)
    run = await db.scalar(select(ReportRun))
    assert run.recipient_user_id == sales.id
    await db.refresh(schedule)
    assert schedule.next_run_at > utc_now() and schedule.last_run_at
    assert first is not None

    assert (await client.get(f"/api/v1/reports/runs/{run.id}")).status_code == 404
    await login(client, "sales@eranova.co.ke")
    mine = (await client.get("/api/v1/reports/runs")).json()
    assert [r["id"] for r in mine] == [str(run.id)]
    snapshot = (await client.get(f"/api/v1/reports/runs/{run.id}")).json()
    assert snapshot["key"] == "sales" and snapshot["sections"]
