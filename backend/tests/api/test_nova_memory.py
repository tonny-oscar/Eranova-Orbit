from sqlalchemy import select

from app.modules.nova.models import NovaMemory
from tests.api.test_nova import answer, tool_step, use_model  # noqa: F401
from tests.conftest import login


async def _start(client, make_user, email="root@eranova.co.ke", role="super_admin"):
    await make_user(email, role=role, full_name="Tonny Bett")
    h = {"X-CSRF-Token": await login(client, email)}
    cid = (await client.post("/api/v1/nova/conversations", headers=h)).json()["id"]
    return h, cid


async def _ask(client, h, cid, text):
    r = await client.post(
        f"/api/v1/nova/conversations/{cid}/messages", json={"content": text}, headers=h
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_basic_mode_remembers_recalls_and_forgets(client, make_user, db):
    h, cid = await _start(client, make_user)
    saved = await _ask(client, h, cid, "Remember that I manage ShulePoa and HostPilot")
    assert "Remembered: I manage ShulePoa and HostPilot" in saved["message"]["content"]
    note = await db.scalar(select(NovaMemory))
    assert note.source == "told"

    recall = await _ask(client, h, cid, "What do you know about me?")
    assert "I manage ShulePoa and HostPilot" in recall["message"]["content"]

    secret = await _ask(client, h, cid, "remember my password is hunter2-123")
    assert secret["executions"][0]["status"] == "failed"
    assert "passwords" in secret["message"]["content"]

    gone = await _ask(client, h, cid, "forget HostPilot")
    assert "Forgot 1 note" in gone["message"]["content"]
    assert await db.scalar(select(NovaMemory)) is None

    await _ask(client, h, cid, "I prefer short answers with bullet points")
    learned = await db.scalar(select(NovaMemory))
    assert learned.source == "learned" and learned.category == "preference"


async def test_model_is_personalised_and_learns_within_limits(client, make_user, use_model, db):  # noqa: F811
    h, cid = await _start(client, make_user)
    await client.put(
        "/api/v1/nova/profile",
        json={
            "preferred_name": "Tonny",
            "response_style": "concise",
            "language": "sw",
            "learning_enabled": True,
        },
        headers=h,
    )
    await client.post(
        "/api/v1/nova/memories",
        json={"content": "Focus on ShulePoa first", "category": "goal"},
        headers=h,
    )
    provider = use_model(
        tool_step(
            "remember", {"content": "Prefers weekly summaries on Mondays", "category": "preference"}
        ),
        answer("Sawa Tonny."),
    )
    await _ask(client, h, cid, "I like getting a summary every Monday")
    prompt = provider.calls[0]["messages"][0]["content"]
    assert "Address the user as Tonny" in prompt
    assert "Keep answers short" in prompt and "Kiswahili" in prompt
    assert "Focus on ShulePoa first" in prompt
    learned = await db.scalar(select(NovaMemory).where(NovaMemory.source == "learned"))
    assert learned.content == "Prefers weekly summaries on Mondays"

    await client.put(
        "/api/v1/nova/profile",
        json={
            "preferred_name": "Tonny",
            "response_style": "concise",
            "language": "en",
            "learning_enabled": False,
        },
        headers=h,
    )
    provider = use_model(tool_step("remember", {"content": "Drinks tea at 4pm"}), answer("Ok."))
    reply = await _ask(client, h, cid, "I always drink tea at 4pm")
    assert reply["executions"][0]["status"] == "failed"
    assert "turned learning off" in provider.calls[0]["messages"][0]["content"]


async def test_nova_keeps_learning_from_conversation(client, make_user, use_model, db):  # noqa: F811
    h, cid = await _start(client, make_user)
    use_model(
        answer("Got it, Tonny."),
        answer(
            'Sure: {"memories": [{"content": "Is the CEO of Eranova", "category": "fact"}, '
            '{"content": "Wants a weekly summary every Monday", "category": "preference"}, '
            '{"content": "Password is hunter2", "category": "fact"}]}'
        ),
    )
    reply = await _ask(client, h, cid, "Mimi ni CEO and I want a weekly summary every Monday")
    assert reply["message"]["content"] == "Got it, Tonny."
    assert any(link["href"] == "/app/nova/memory" for link in reply["message"]["links"])
    notes = {m.content: m.source for m in await db.scalars(select(NovaMemory))}
    assert notes == {
        "Is the CEO of Eranova": "learned",
        "Wants a weekly summary every Monday": "learned",
    }

    use_model(answer("Habari."), RuntimeError("model down"))
    calm = await _ask(client, h, cid, "I am in the office until 6pm")
    assert calm["message"]["status"] == "ok"

    use_model(answer("Here is the summary."))
    await _ask(client, h, cid, "show the business summary")  # no first-person cue: no extra call


async def test_connection_test_reports_basic_mode(client, make_user):
    await _start(client, make_user)
    result = (
        await client.post(
            "/api/v1/nova/test", headers={"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
        )
    ).json()
    assert result["ok"] is False and result["mode"] == "basic"


async def test_feedback_teaches_style_and_memory_is_private(client, make_user):
    h, cid = await _start(client, make_user)
    reply = await _ask(client, h, cid, "business summary")
    mid = reply["message"]["id"]
    r = await client.post(
        f"/api/v1/nova/messages/{mid}/feedback",
        json={"rating": -1, "comment": "Use bullet points and fewer words"},
        headers=h,
    )
    assert r.status_code == 204
    notes = (await client.get("/api/v1/nova/memories")).json()
    assert notes[0]["source"] == "feedback" and "bullet points" in notes[0]["content"]
    convo = (await client.get(f"/api/v1/nova/conversations/{cid}")).json()
    assert [m["rating"] for m in convo["messages"] if m["role"] == "assistant"] == [-1]

    edited = (
        await client.patch(
            f"/api/v1/nova/memories/{notes[0]['id']}",
            json={"content": "Use short bullet points"},
            headers=h,
        )
    ).json()
    assert edited["source"] == "told"

    await make_user("other@eranova.co.ke", role="employee")
    h2 = {"X-CSRF-Token": await login(client, "other@eranova.co.ke")}
    assert (await client.get("/api/v1/nova/memories")).json() == []
    assert (
        await client.post(f"/api/v1/nova/messages/{mid}/feedback", json={"rating": 1}, headers=h2)
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/nova/memories/{notes[0]['id']}", headers=h2)
    ).status_code == 404

    h = {"X-CSRF-Token": await login(client, "root@eranova.co.ke")}
    assert (await client.delete("/api/v1/nova/memories", headers=h)).status_code == 204
    assert (await client.get("/api/v1/nova/memories")).json() == []
