"""Basic mode: used when no AI model is configured.

Maps a few plain requests to read-only tools so NOVA is useful without an API
key. It never performs actions and says clearly that it is not an AI model.
"""

import re
from dataclasses import dataclass


@dataclass
class Plan:
    tool: str | None
    arguments: dict
    reply: str | None = None


HELP = (
    "I'm running in basic mode because no AI model is configured, so I can only look things "
    "up. Try:\n"
    '• "my work" (your open tasks and follow-ups)\n'
    '• "overdue tasks"\n'
    '• "open tickets"\n'
    '• "business summary"\n'
    '• "search ShulePoa"\n'
    '• "sales report" (also support, delivery, marketing, traffic, product, people)\n'
    '• "status of ShulePoa"\n'
    "An administrator can enable full NOVA (drafting, actions, voice conversations) by setting "
    "NOVA_PROVIDER, NOVA_MODEL and NOVA_API_KEY on the server."
)

_REPORTS = (
    "sales",
    "support",
    "delivery",
    "marketing",
    "traffic",
    "product",
    "people",
    "executive",
)


def plan(text: str) -> Plan:
    t = text.strip().lower()
    if re.search(r"\b(help|what can you do)\b", t):
        return Plan(None, {}, HELP)
    if m := re.search(r"\b(?:status of|how is)\s+(.+?)\s*\??$", t):
        target = m.group(1).strip()
        if target not in ("business", "the business", "everything", "things"):
            return Plan("product_status", {"product": target})
    if re.search(r"\b(summary|overview|how is (the )?business|dashboard)\b", t):
        return Plan("business_summary", {"days": 30})
    for key in _REPORTS:
        if re.search(rf"\b{key}\s+report\b", t):
            return Plan("run_report", {"key": key})
    if re.search(r"\boverdue\b", t):
        return Plan(
            "list_tasks",
            {"scope": "all" if "team" in t or "all" in t else "mine", "overdue_only": True},
        )
    if re.search(r"\b(my (work|tasks|day)|what should i do|todo)\b", t):
        return Plan("my_work", {})
    if re.search(r"\b(tickets?|support queue)\b", t):
        return Plan("list_tickets", {"open_only": True})
    if m := re.search(r"\b(?:search|find|look up|lookup)\s+(?:for\s+)?(.+)$", t):
        query = m.group(1).strip(" ?.")
        if len(query) >= 2:
            return Plan("search_records", {"query": query[:100]})
    return Plan(None, {}, HELP)


def render(summary: str, data, links: list[dict]) -> str:
    """Plain-text answer built only from the tool result."""
    lines = [summary]
    if isinstance(data, dict) and "tasks" in data:
        for task in data["tasks"][:10]:
            due = f", due {task['due']}" if task.get("due") else ""
            flag = " (overdue)" if task.get("overdue") else ""
            lines.append(f"• {task['title']} ({task['project']}){due}{flag}")
        for f in data.get("follow_ups", [])[:5]:
            lines.append(f"• Follow up with {f['lead']} on {f['date']}")
    elif (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and "title" in data[0]
        and "metrics" in data[0]
    ):
        for section in data:
            if section["metrics"]:
                figures = "; ".join(
                    f"{m['label']}: {m['value'] if m['value'] is not None else '—'}"
                    for m in section["metrics"]
                )
                lines.append(f"• {section['title']}: {figures}")
            elif section["rows"]:
                lines.append(f"• {section['title']}: {len(section['rows'])} row(s)")
    elif isinstance(data, list):
        for item in data[:10]:
            label = item.get("name") or item.get("title") or item.get("subject") or ""
            extra = item.get("status") or item.get("type") or ""
            lines.append(f"• {item.get('reference', '')} {label} ({extra})".replace("  ", " "))
    lines.append("\n(Basic mode: figures come straight from Orbit records; no AI model was used.)")
    return "\n".join(lines)
