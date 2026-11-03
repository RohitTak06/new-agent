"""Prove that contracts/tools.py routes to the real services when USE_REAL_* = 1.

Every stub is replaced with a function that raises, so any call that still
reaches a stub fails loudly. Needs Postgres up, migrated and seeded.

    cd backend
    python -m scripts.check_tools
"""
from dotenv import load_dotenv

load_dotenv()

import os  # noqa: E402

from app.contracts import stubs, tools  # noqa: E402
from app.contracts.models import LeadProfile  # noqa: E402

CHECKED = ["search_knowledge", "score_lead", "upsert_lead", "get_lead"]


def _trap(name: str):
    def fail(*_args, **_kwargs):
        raise AssertionError(f"{name} reached the STUB")
    return fail


def main() -> None:
    """Call each intel/crm tool through tools.py and show where it ran."""
    for flag in ("USE_REAL_INTEL", "USE_REAL_CRM"):
        print(f"{flag}={os.getenv(flag)}")
        assert os.getenv(flag) == "1", f"{flag} must be 1 in .env"
    for name in CHECKED:
        setattr(stubs, name, _trap(name))

    kb = tools.search_knowledge("What is the B.Tech CSE tuition fee?")
    print("search_knowledge ->", kb.answer_found, [c.source for c in kb.chunks][:3])

    profile = LeadProfile(
        name="Tools Check (synthetic)",
        email="tools.check@example.test",
        program_interest="B.Tech CSE",
        twelfth_percent=91.0,
    )
    score = tools.score_lead(profile)
    print("score_lead       ->", score.score, score.tier, score.reasons[:2])

    lead = tools.upsert_lead(profile)  # matched by email, so reruns update one row
    print("upsert_lead      -> id", lead.id, lead.profile.name, lead.status)

    fetched = tools.get_lead(lead.id)
    print("get_lead         -> id", fetched.id, fetched.profile.email)
    print("OK: all calls ran against the real services")


if __name__ == "__main__":
    main()
