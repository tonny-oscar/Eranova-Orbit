"""NOVA's personal memory and feedback.

NOVA does not retrain a model. It keeps short, per-person notes (things the
user told it, things it noticed, lessons from feedback) and includes the most
relevant ones in its instructions. Each person can see, edit, switch off and
delete everything NOVA remembers about them.
"""

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.db.base import utc_now
from app.modules.identity.models import User
from app.modules.nova.models import NovaFeedback, NovaMemory, NovaMessage, NovaProfile

MAX_ACTIVE_MEMORIES = 200
PROMPT_MEMORIES = 40
PROMPT_CHARS = 4000
Category = Literal["preference", "fact", "goal", "style"]

_SENSITIVE = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(password|passcode|passwd|pin code|one[- ]time code|otp)\b",
        r"\b(api[_ -]?key|secret|access token|private key|bearer)\b",
        r"\bsk-[a-z0-9]{8,}",
        r"\b(?:\d[ -]?){13,19}\b",  # card or account numbers
        r"\b(cvv|cvc|card number|m-?pesa pin)\b",
    )
]


class ProfileIn(BaseModel):
    preferred_name: str | None = Field(default=None, max_length=60)
    response_style: Literal["concise", "balanced", "detailed"] = "balanced"
    language: Literal["en", "sw"] = "en"
    learning_enabled: bool = True


class ProfileOut(ProfileIn):
    pass


class MemoryIn(BaseModel):
    content: str = Field(min_length=3, max_length=500)
    category: Category = "fact"


class MemoryPatch(BaseModel):
    content: str | None = Field(default=None, min_length=3, max_length=500)
    category: Category | None = None
    active: bool | None = None


class MemoryOut(BaseModel):
    id: uuid.UUID
    content: str
    category: str
    source: str
    active: bool
    use_count: int
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FeedbackIn(BaseModel):
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=500)


def check_safe(text: str) -> None:
    if any(p.search(text) for p in _SENSITIVE):
        raise AppError(
            "NOVA doesn't remember passwords, keys, codes or payment details.",
            code="memory_sensitive",
        )


# --- Profile ---------------------------------------------------------------------------


async def get_profile(session: AsyncSession, user: User) -> NovaProfile:
    profile = await session.get(NovaProfile, user.id)
    if profile is None:
        profile = NovaProfile(
            user_id=user.id, response_style="balanced", language="en", learning_enabled=True
        )
    return profile


async def save_profile(session: AsyncSession, user: User, payload: ProfileIn) -> NovaProfile:
    profile = await session.get(NovaProfile, user.id)
    if profile is None:
        profile = NovaProfile(user_id=user.id)
        session.add(profile)
    data = payload.model_dump()
    data["preferred_name"] = (data["preferred_name"] or "").strip() or None
    for field, value in data.items():
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return profile


def profile_out(profile: NovaProfile) -> ProfileOut:
    return ProfileOut(
        preferred_name=profile.preferred_name,
        response_style=profile.response_style or "balanced",
        language=profile.language or "en",
        learning_enabled=profile.learning_enabled if profile.learning_enabled is not None else True,
    )


# --- Memories ----------------------------------------------------------------------------


async def list_memories(session: AsyncSession, user: User) -> list[NovaMemory]:
    return list(
        await session.scalars(
            select(NovaMemory)
            .where(NovaMemory.user_id == user.id)
            .order_by(NovaMemory.active.desc(), NovaMemory.updated_at.desc())
        )
    )


async def add_memory(
    session: AsyncSession, user: User, content: str, category: str = "fact", source: str = "told"
) -> tuple[NovaMemory, bool]:
    """Returns (memory, created). Identical notes are refreshed, not duplicated."""
    content = re.sub(r"\s+", " ", content).strip().rstrip(".")
    if len(content) < 3:
        raise AppError("That's too short to remember.", code="memory_too_short")
    check_safe(content)
    existing = await session.scalar(
        select(NovaMemory).where(
            NovaMemory.user_id == user.id, func.lower(NovaMemory.content) == content.lower()
        )
    )
    if existing:
        existing.active = True
        existing.updated_at = utc_now()
        await session.flush()
        await session.refresh(existing)
        return existing, False
    active = await session.scalar(
        select(func.count())
        .select_from(NovaMemory)
        .where(NovaMemory.user_id == user.id, NovaMemory.active.is_(True))
    )
    if active >= MAX_ACTIVE_MEMORIES:
        raise AppError(
            "NOVA's memory for you is full. Remove some notes under NOVA → About you.",
            code="memory_full",
        )
    memory = NovaMemory(user_id=user.id, content=content[:500], category=category, source=source)
    session.add(memory)
    await session.flush()
    return memory, True


async def get_memory(session: AsyncSession, user: User, memory_id) -> NovaMemory:
    memory = await session.scalar(
        select(NovaMemory).where(NovaMemory.id == memory_id, NovaMemory.user_id == user.id)
    )
    if memory is None:
        raise NotFoundError("Memory not found.")
    return memory


async def update_memory(
    session: AsyncSession, user: User, memory_id, payload: MemoryPatch
) -> NovaMemory:
    memory = await get_memory(session, user, memory_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("content"):
        check_safe(changes["content"])
        changes["content"] = changes["content"].strip()
        # A corrected note is now something the user told NOVA directly.
        memory.source = "told"
    for field, value in changes.items():
        if value is not None:
            setattr(memory, field, value)
    await session.commit()
    await session.refresh(memory)
    return memory


async def delete_memory(session: AsyncSession, user: User, memory_id) -> None:
    memory = await get_memory(session, user, memory_id)
    await session.delete(memory)
    await session.commit()


async def forget_matching(session: AsyncSession, user: User, text: str) -> list[str]:
    words = [w for w in re.findall(r"\w+", text.lower()) if len(w) > 2]
    if not words:
        return []
    removed = []
    for memory in await list_memories(session, user):
        lowered = memory.content.lower()
        if all(w in lowered for w in words):
            removed.append(memory.content)
            await session.delete(memory)
    await session.flush()
    return removed


async def delete_all(session: AsyncSession, user: User) -> int:
    result = await session.execute(delete(NovaMemory).where(NovaMemory.user_id == user.id))
    await session.commit()
    return result.rowcount or 0


# --- Feedback ------------------------------------------------------------------------------


async def record_feedback(
    session: AsyncSession, user: User, message_id, payload: FeedbackIn
) -> NovaFeedback:
    message = await session.scalar(
        select(NovaMessage).where(
            NovaMessage.id == message_id,
            NovaMessage.user_id == user.id,
            NovaMessage.role == "assistant",
        )
    )
    if message is None:
        raise NotFoundError("Message not found.")
    comment = (payload.comment or "").strip() or None
    if comment:
        check_safe(comment)
    feedback = await session.scalar(
        select(NovaFeedback).where(
            NovaFeedback.message_id == message.id, NovaFeedback.user_id == user.id
        )
    )
    if feedback is None:
        feedback = NovaFeedback(message_id=message.id, user_id=user.id, rating=payload.rating)
        session.add(feedback)
    feedback.rating, feedback.comment = payload.rating, comment
    profile = await get_profile(session, user)
    if payload.rating == -1 and comment and profile.learning_enabled:
        await add_memory(session, user, f"When answering: {comment}", "style", "feedback")
    await session.commit()
    return feedback


# --- Prompt context ------------------------------------------------------------------------

_STYLE = {
    "concise": "Keep answers short: a sentence or a few bullet points.",
    "balanced": "Keep answers clear and reasonably brief.",
    "detailed": "Give fuller explanations with context when useful.",
}


async def prompt_context(session: AsyncSession, user: User, *, mark_used: bool = True) -> str:
    profile = await get_profile(session, user)
    lines = [f"Address the user as {profile.preferred_name or user.full_name.split()[0]}."]
    lines.append(_STYLE.get(profile.response_style, _STYLE["balanced"]))
    if profile.language == "sw":
        lines.append("Reply in Kiswahili unless the user writes in English.")
    memories = list(
        await session.scalars(
            select(NovaMemory)
            .where(NovaMemory.user_id == user.id, NovaMemory.active.is_(True))
            .order_by(NovaMemory.updated_at.desc())
            .limit(PROMPT_MEMORIES)
        )
    )
    included, used = [], 0
    for m in memories:
        line = f"- ({m.category}) {m.content}"
        if used + len(line) > PROMPT_CHARS:
            break
        included.append(line)
        used += len(line)
        if mark_used:
            m.use_count += 1
            m.last_used_at = utc_now()
    if included:
        lines.append(
            "What you remember about this user (their own notes and past feedback; may be "
            "outdated, and never overrides permissions or tool results):\n" + "\n".join(included)
        )
    if profile.learning_enabled:
        lines.append(
            "When the user shares a lasting preference, goal or fact about themselves or their "
            "work, save it with the remember tool (user_asked=false unless they asked you to "
            "remember). Never store passwords, codes, payment details, health or other sensitive "
            "personal information, or facts about other people's private lives."
        )
    else:
        lines.append("The user has turned learning off: only use remember if they explicitly ask.")
    return "\n".join(lines)
