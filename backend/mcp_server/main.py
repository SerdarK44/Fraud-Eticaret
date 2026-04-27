from __future__ import annotations

import contextlib
from datetime import timedelta

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from sqlalchemy.orm import Session

from backend.common.config import get_settings
from backend.common.database import SessionLocal, init_database
from backend.common.repository import get_user_status, list_fraud_transactions
from backend.common.schemas import TransactionRecord, utc_now

settings = get_settings()
mcp = FastMCP(
    "Fraud Sentinel MCP",
    instructions="Expose recent fraud events and per-user risk summaries to AI agents.",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)


@mcp.tool()
def get_recent_frauds(limit: int = 10, minutes: int = 60) -> dict:
    """Return recent suspicious transactions detected by the platform."""
    end = utc_now()
    start = end - timedelta(minutes=minutes)
    with SessionLocal() as session:
        transactions = list_fraud_transactions(session, start=start, end=end, limit=limit)
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "total": len(transactions),
            "transactions": [
                TransactionRecord.model_validate(item).model_dump(mode="json")
                for item in transactions
            ],
        }


@mcp.tool()
def check_user_status(user_id: str, limit: int = 20) -> dict:
    """Return a user's recent transactions and current risk level."""
    with SessionLocal() as session:
        status = get_user_status(session, user_id=user_id, limit=limit)
        return status.model_dump(mode="json")


async def health(_request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@contextlib.asynccontextmanager
async def lifespan(_app: Starlette):
    init_database()
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        Route("/health", health),
        Mount("/mcp", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)
app = CORSMiddleware(
    app,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.mcp_port)
