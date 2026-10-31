"""The ONLY place the agent imports tools from.

Each tool calls the stub by default. When USE_REAL_<MODULE>=1 is set in .env,
it calls the real function from that module's service.py instead.
Real functions must keep the exact same signature and return type as the stub.
"""
import importlib
import os

from app.contracts import stubs


def _resolve(flag: str, module: str, name: str):
    def call(*args, **kwargs):
        if os.getenv(flag) == "1":
            fn = getattr(importlib.import_module(module), name)
        else:
            fn = getattr(stubs, name)
        return fn(*args, **kwargs)

    call.__name__ = name
    call.__doc__ = getattr(stubs, name).__doc__
    return call


# Guru
search_knowledge = _resolve("USE_REAL_INTEL", "app.intel.service", "search_knowledge")
score_lead = _resolve("USE_REAL_INTEL", "app.intel.service", "score_lead")

# Dev
upsert_lead = _resolve("USE_REAL_CRM", "app.crm.service", "upsert_lead")
get_lead = _resolve("USE_REAL_CRM", "app.crm.service", "get_lead")
request_approval = _resolve("USE_REAL_CRM", "app.crm.service", "request_approval")

# Riya
get_slots = _resolve("USE_REAL_SCHEDULING", "app.scheduling.service", "get_slots")
book_slot = _resolve("USE_REAL_SCHEDULING", "app.scheduling.service", "book_slot")
send_message = _resolve("USE_REAL_SCHEDULING", "app.scheduling.service", "send_message")
schedule_followup = _resolve("USE_REAL_SCHEDULING", "app.scheduling.service", "schedule_followup")
