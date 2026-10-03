"""VoltSync HTTP API."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .generator import build_forecast, list_scenarios, resolve_case
from .models import (
    ForecastResponse,
    HealthResponse,
    OptimizeRequest,
    PlanRequest,
    PlanResponse,
    ScenariosResponse,
    SiteConfig,
)
from .optimizer import OptimizationError, optimize_day, solver_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("voltsync")

app = FastAPI(
    title="VoltSync VPP",
    version=__version__,
    summary="Store, use, or sell — 24-hour battery dispatch for a prosumer site.",
    description=(
        "Generates a synthetic Yerevan day (solar, load, tariffs) and solves a "
        "linear program that dispatches a battery to cut the energy bill."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OptimizationError)
async def optimization_error_handler(_, exc: OptimizationError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc), "status": exc.status})


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "service": "VoltSync VPP",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
        "scenarios": "/api/v1/scenarios",
        "plan": "/api/v1/plan",
    }


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    solver, available = solver_status()
    return HealthResponse(
        status="ok" if available else "degraded",
        service="voltsync-vpp",
        version=__version__,
        solver=solver,
        solver_available=available,
    )


@app.get("/api/v1/scenarios", response_model=ScenariosResponse, tags=["forecast"])
def scenarios() -> ScenariosResponse:
    return list_scenarios()


@app.post("/api/v1/forecast", response_model=ForecastResponse, tags=["forecast"])
def forecast(request: PlanRequest) -> ForecastResponse:
    try:
        scenario_id, title, site, _battery = resolve_case(request.scenario, request.site, request.battery)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return build_forecast(site, scenario=scenario_id, scenario_title=title)


@app.post("/api/v1/optimize", response_model=PlanResponse, tags=["dispatch"])
def optimize(request: OptimizeRequest) -> PlanResponse:
    site = request.site or SiteConfig(
        name="Custom forecast",
        pv_capacity_kwp=0.0,
        daily_load_kwh=round(sum(point.load_kwh for point in request.hours), 4),
        cloud_cover=0.0,
        tariff_profile="standard_tou",
        seed=0,
    )
    return optimize_day(
        request.hours,
        request.battery,
        scenario=None,
        scenario_title="Custom forecast",
        site=site,
    )


@app.get("/api/v1/plan", response_model=PlanResponse, tags=["dispatch"])
def plan_from_scenario(
    scenario: str = Query(default="yerevan_summer"),
) -> PlanResponse:
    return _build_plan(PlanRequest(scenario=scenario, site=None, battery=None))


@app.post("/api/v1/plan", response_model=PlanResponse, tags=["dispatch"])
def plan(request: PlanRequest) -> PlanResponse:
    return _build_plan(request)


def _build_plan(request: PlanRequest) -> PlanResponse:
    try:
        scenario_id, title, site, battery = resolve_case(request.scenario, request.site, request.battery)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    forecast = build_forecast(site, scenario=scenario_id, scenario_title=title)
    logger.info(
        "Solving %s pv=%.1f kWp battery=%.1f kWh",
        scenario_id or "custom",
        site.pv_capacity_kwp,
        battery.capacity_kwh,
    )
    return optimize_day(
        forecast.hours,
        battery,
        scenario=scenario_id,
        scenario_title=title,
        site=site,
    )
