"""Single-endpoint FastAPI adapter for the unchanged horse-racing optimizer.

Run locally: uvicorn app:app --reload
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from arbitrage_optimizer import maximize_guaranteed_profit, minimize_bets_with_arbitrage

WEB_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Race Arbitrage Studio",
    description="One calculation endpoint plus a local static frontend.",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem: dict[str, Any]
    mode: Literal["both", "max_profit", "min_bets"] = "both"
    minimum_profit: str = "0.01"
    tie_break: Literal["max_profit", "none"] = "max_profit"
    time_limit: float = Field(default=12, gt=0, le=60)


@app.post("/api/calculate")
async def calculate(request: CalculationRequest) -> dict[str, Any]:
    """Run one or both original functions; all financial inputs remain exact strings."""

    def solve() -> dict[str, Any]:
        results: dict[str, Any] = {}
        if request.mode in {"both", "max_profit"}:
            results["max_profit"] = maximize_guaranteed_profit(
                request.problem, time_limit=request.time_limit
            )
        if request.mode in {"both", "min_bets"}:
            results["min_bets"] = minimize_bets_with_arbitrage(
                request.problem,
                minimum_profit=request.minimum_profit,
                tie_break=request.tie_break,
                time_limit=request.time_limit,
            )
        return {"results": results}

    try:
        # scipy.optimize.milp is CPU-bound; don't block the server event loop.
        return await run_in_threadpool(solve)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        # The optimizer refuses to return a result without proven optimality.
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
