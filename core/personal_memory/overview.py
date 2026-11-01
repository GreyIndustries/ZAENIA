"""Everything ZAE remembers about Grey, in one list, each item with where it came from (Phase 3 provenance).

Three stores feed it, and each item says which:
* "You told me": things Grey explicitly asked ZAE to remember (personal_memory/store.py);
* "Profile": the evidence ledger behind his long-term profile (owner_profile.py), with the evidence count and the
  latest supporting quote, and its review status (active, to confirm, conflicting);
* "Noticed": points ZAE inferred from his own words (insights.py), with the words they came from.

Reading this changes nothing and learns nothing. Sensitive ledger records stay out unless shown on purpose.
"""
from __future__ import annotations

from typing import Any


def everything(*, memory_store=None, profile=None, insights=None, limit: int = 300) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    try:
        if memory_store is None:
            from core.personal_memory.store import DEFAULT_PATH, MemoryStore
            memory_store = MemoryStore() if DEFAULT_PATH.exists() else None
        for row in memory_store.list(limit=limit) if memory_store is not None else []:
            items.append({"store": "told", "label": "You told me", "id": str(row.get("id") or row.get("key")), "about": row.get("key", ""),
                          "value": row.get("value", ""), "status": "active", "updatedAt": row.get("updated_at"),
                          "source": "Your own request to remember it", "evidence": None})
    except Exception:
        pass
    try:
        if profile is None:
            from core.personal_memory.owner_profile import owner_profile
            profile = owner_profile()
        for row in profile.records(status="all", limit=limit) if profile.available() else []:
            quote = None
            try:
                evidence = profile.explain(row["id"]).get("evidence") or []
                quote = evidence[-1]["quote"] if evidence else None
            except Exception:
                pass
            items.append({"store": "profile", "label": "Profile", "id": row["id"], "about": row["key"], "value": row["value"],
                          "status": {"candidate": "to confirm", "conflicted": "conflicting"}.get(row["status"], row["status"]),
                          "updatedAt": row.get("updatedAt"), "source": f"{row['evidence']} piece{'s' if row['evidence'] != 1 else ''} of evidence",
                          "evidence": quote})
    except Exception:
        pass
    try:
        if insights is None:
            from core.personal_memory.insights import InsightStore
            insights = InsightStore()
        for row in insights.list(limit=limit):
            items.append({"store": "noticed", "label": "Noticed", "id": row.get("id"), "about": row.get("kind", "point"), "value": row.get("text", ""),
                          "status": row.get("confidence", "tentative"), "updatedAt": row.get("last_seen"),
                          "source": "Confirmed by you" if row.get("source") == "user_confirmed" else f"Noticed {row.get('count', 1)} time(s) in your own words",
                          "evidence": row.get("evidence")})
    except Exception:
        pass
    items.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
    return {"items": items[:limit], "counts": {s: sum(1 for i in items if i["store"] == s) for s in ("told", "profile", "noticed")},
            "note": "Reference only: nothing ZAE remembers can approve an action or change a permission."}
