from dotenv import load_dotenv

load_dotenv()  # before app imports: modules read env vars at import time

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent import followup_writer
from app.agent.router import router as agent_router
from app.crm.router import router as crm_router
from app.errors import CatchUnhandledErrors
from app.intel.router import router as intel_router
from app.scheduling import followups, scheduler
from app.scheduling.router import router as scheduling_router


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
followups.set_composer(followup_writer.compose)


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler.start()          # follow-up dispatcher; SCHEDULER_ENABLED=0 turns it off
    yield
    scheduler.stop()


app = FastAPI(title="JKLU Admission Agent (PS-04)", lifespan=lifespan)

app.add_middleware(CatchUnhandledErrors)   # added first, so it sits inside CORS and crashes keep their headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router, prefix="/agent", tags=["agent"])
app.include_router(crm_router, prefix="/crm", tags=["crm"])
app.include_router(intel_router, prefix="/intel", tags=["intel"])
app.include_router(scheduling_router, prefix="/scheduling", tags=["scheduling"])


@app.get("/health")
def health():
    return {"status": "ok"}
