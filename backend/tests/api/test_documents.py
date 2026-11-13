from sqlalchemy import select

from app.modules.audit.models import AuditLog
from tests.conftest import login

PDF = b"%PDF-1.7\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


async def _upload(client, h, *, name="policy.pdf", data=PDF, **fields):
    form = {"title": "Leave policy", "category": "policy", **fields}
    return await client.post(
        "/api/v1/documents",
        data=form,
        files={"file": (name, data, "application/octet-stream")},
        headers=h,
    )


async def test_upload_download_and_versions(client, make_user, db):
    await make_user("root@eranova.co.ke", role="super_admin")
    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    r = await _upload(client, h, name="../../Leave Policy?.pdf")
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["filename"] == "Leave Policy_.pdf"
    assert doc["content_type"] == "application/pdf"

    v2 = (
        await client.post(
            f"/api/v1/documents/{doc['id']}/versions",
            files={"file": ("policy-v2.pdf", PDF + b"\n% v2", "application/pdf")},
            data={"note": "Updated carry-over rules"},
            headers=h,
        )
    ).json()
    assert v2["current_version"] == 2 and [v["version"] for v in v2["versions"]] == [2, 1]

    latest = await client.get(f"/api/v1/documents/{doc['id']}/download")
    assert latest.content.endswith(b"% v2")
    assert latest.headers["x-content-type-options"] == "nosniff"
    assert latest.headers["content-disposition"].startswith("attachment;")
    first = await client.get(f"/api/v1/documents/{doc['id']}/download", params={"version": 1})
    assert first.content == PDF
    downloads = list(
        await db.scalars(select(AuditLog).where(AuditLog.action == "document.download"))
    )
    assert len(downloads) == 2


async def test_unsafe_files_are_rejected(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    html = await _upload(client, h, name="page.html", data=b"<script>alert(1)</script>")
    assert html.json()["error"]["code"] == "file_type"
    disguised = await _upload(client, h, name="invoice.pdf", data=b"MZ\x90\x00 not a pdf")
    assert disguised.json()["error"]["code"] == "file_content"
    huge = await _upload(client, h, data=PDF + b"0" * (10 * 1024 * 1024))
    assert huge.json()["error"]["code"] == "file_too_large"
    text = await _upload(client, h, name="notes.txt", data="Mkutano — minutes".encode())
    assert text.status_code == 201


async def test_restricted_documents_need_membership(client, make_user):
    await make_user("root@eranova.co.ke", role="super_admin")
    staff = await make_user("staff@eranova.co.ke", role="employee")
    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    open_doc = (await _upload(client, h, title="Handbook")).json()
    secret = (
        await _upload(client, h, title="Board minutes", category="minutes", visibility="restricted")
    ).json()

    await login(client, "staff@eranova.co.ke")
    titles = {d["title"] for d in (await client.get("/api/v1/documents")).json()["items"]}
    assert titles == {"Handbook"}
    assert (await client.get(f"/api/v1/documents/{secret['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/documents/{secret['id']}/download")).status_code == 404
    assert (await client.get(f"/api/v1/documents/{open_doc['id']}/download")).status_code == 200

    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    await client.put(
        f"/api/v1/documents/{secret['id']}/members", json={"user_ids": [str(staff.id)]}, headers=h
    )
    await login(client, "staff@eranova.co.ke")
    assert (await client.get(f"/api/v1/documents/{secret['id']}/download")).status_code == 200
    search = (await client.get("/api/v1/documents", params={"q": "board"})).json()
    assert [d["title"] for d in search["items"]] == ["Board minutes"]
