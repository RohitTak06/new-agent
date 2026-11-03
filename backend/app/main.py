from dotenv import load_dotenv

load_dotenv()  # before app imports: modules read env vars at import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.router import router as agent_router
from app.crm.router import router as crm_router
from app.intel.router import router as intel_router
from app.scheduling.router import router as scheduling_router

app = FastAPI(title="JKLU Admission Agent (PS-04)")

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
