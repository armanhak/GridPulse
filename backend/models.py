"""Pydantic contracts for the VoltSync API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Decision = Literal["store", "use", "sell", "idle"]
TARIFF_PROFILES = ("standard_tou", "export_spike")


class SiteConfig(BaseModel):
    """Weather, PV and load assumptions for one 24-hour day."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="Yerevan prosumer site", max_length=120)
    pv_capacity_kwp: float = Field(default=8.0, ge=0.0, le=500.0)
    daily_load_kwh: float = Field(default=30.0, ge=0.0, le=5000.0)
    cloud_cover: float = Field(default=0.12, ge=0.0, le=1.0)
    sunrise_hour: float = Field(default=5.8, ge=0.0, le=12.0)
    sunset_hour: float = Field(default=20.2, ge=12.0, le=24.0)
    tariff_profile: str = Field(default="standard_tou")
    seed: int = Field(default=7, ge=0, le=10_000_000)

    @model_validator(mode="after")
    def _check_daylight_and_tariff(self) -> SiteConfig:
        if self.sunrise_hour >= self.sunset_hour:
            raise ValueError("sunrise_hour must be earlier than sunset_hour")
        if self.tariff_profile not in TARIFF_PROFILES:
            allowed = ", ".join(TARIFF_PROFILES)
            raise ValueError(f"tariff_profile must be one of: {allowed}")
        return self


class BatteryConfig(BaseModel):
    """AC-coupled battery limits. State of charge is a fraction of nameplate capacity."""

    model_config = ConfigDict(extra="forbid")

    capacity_kwh: float = Field(default=12.0, ge=0.0, le=5000.0)
    max_charge_kw: float = Field(default=5.0, ge=0.0, le=2000.0)
    max_discharge_kw: float = Field(default=5.0, ge=0.0, le=2000.0)
    charge_efficiency: float = Field(default=0.95, gt=0.0, le=1.0)
    discharge_efficiency: float = Field(default=0.95, gt=0.0, le=1.0)
    soc_min: float = Field(default=0.10, ge=0.0, le=1.0)
    soc_max: float = Field(default=0.95, ge=0.0, le=1.0)
    soc_initial: float = Field(default=0.40, ge=0.0, le=1.0)
    degradation_amd_per_kwh: float = Field(
        default=4.0,
        ge=0.0,
        le=100.0,
        description="Wear cost applied to each kWh charged and each kWh discharged.",
    )

    @model_validator(mode="after")
    def _check_soc_window(self) -> BatteryConfig:
        if self.soc_min > self.soc_max:
            raise ValueError("soc_min must be less than or equal to soc_max")
        if not self.soc_min <= self.soc_initial <= self.soc_max:
            raise ValueError("soc_initial must lie between soc_min and soc_max")
        return self


class ForecastPoint(BaseModel):
    """One hour of exogenous data. Energy is kWh during that hour."""

    model_config = ConfigDict(extra="forbid")

    hour: int = Field(ge=0, le=23)
    label: str
    solar_kwh: float = Field(ge=0.0)
    load_kwh: float = Field(ge=0.0)
    buy_price_amd: float = Field(ge=0.0)
    sell_price_amd: float = Field(ge=0.0)


class ForecastResponse(BaseModel):
    scenario: str | None
    scenario_title: str
    site: SiteConfig
    hours: list[ForecastPoint]


class HourSchedule(BaseModel):
    hour: int
    label: str
    solar_kwh: float
    load_kwh: float
    buy_price_amd: float
    sell_price_amd: float
    pv_to_load_kwh: float
    pv_to_battery_kwh: float
    pv_to_grid_kwh: float
    pv_curtailed_kwh: float
    grid_to_load_kwh: float
    grid_to_battery_kwh: float
    battery_to_load_kwh: float
    battery_to_grid_kwh: float
    charge_kwh: float
    discharge_kwh: float
    soc_kwh: float
    soc_pct: float
    decision: Decision
    reason: str
    net_cost_amd: float
    baseline_import_kwh: float
    baseline_export_kwh: float
    baseline_net_cost_amd: float


class ScheduleBlock(BaseModel):
    start_hour: int
    end_hour: int
    label: str
    decision: Decision
    text: str


class CostBreakdown(BaseModel):
    """One bill: imports, exports and battery wear, in AMD."""

    import_cost_amd: float
    export_revenue_amd: float
    wear_amd: float
    net_cost_amd: float
    import_kwh: float
    export_kwh: float


class PlanComparison(BaseModel):
    """Rooftop bill under three policies for the same day and the same battery.

    no_battery exports surplus immediately and buys every deficit.
    self_consumption uses the battery only as a solar buffer for the building.
    optimized is the linear program. Dispatch value is the software: the gap
    between self-consumption and the optimal plan, not the value of owning a battery.
    """

    no_battery: CostBreakdown
    self_consumption: CostBreakdown
    optimized: CostBreakdown
    battery_value_amd: float
    dispatch_value_amd: float
    import_delta_amd: float
    export_delta_amd: float
    wear_delta_amd: float
    dispatch_import_kwh_delta: float
    dispatch_co2_delta_kg: float


class SelfConsumptionHour(BaseModel):
    """Greedy solar self-consumption for one hour, on the same battery limits."""

    hour: int
    label: str
    charge_kwh: float
    discharge_kwh: float
    soc_kwh: float
    soc_pct: float
    grid_import_kwh: float
    grid_export_kwh: float
    net_cost_amd: float


class Kpis(BaseModel):
    optimized_net_cost_amd: float
    baseline_net_cost_amd: float
    savings_amd: float
    savings_pct: float
    illustrative_annual_savings_amd: float
    grid_import_kwh: float
    grid_export_kwh: float
    baseline_import_kwh: float
    baseline_export_kwh: float
    solar_kwh: float
    load_kwh: float
    charged_kwh: float
    discharged_kwh: float
    cycles: float
    self_sufficiency_pct: float
    curtailed_kwh: float
    co2_delta_kg: float
    hours_store: int
    hours_use: int
    hours_sell: int
    hours_idle: int
    max_grid_import_kw: float
    baseline_max_grid_import_kw: float


class SellerSale(BaseModel):
    """One hour of energy sold by the prosumer into the pool or the grid."""

    model_config = ConfigDict(extra="forbid")

    hour: int = Field(ge=0, le=23)
    volume_kwh: float = Field(ge=0.0)
    price_amd: float = Field(ge=0.0)
    revenue_amd: float = Field(ge=0.0)


class BuyerHourlyCost(BaseModel):
    """One hour of the commercial buyer's bill, before and after the pool."""

    model_config = ConfigDict(extra="forbid")

    hour: int = Field(ge=0, le=23)
    consumed_kwh: float = Field(ge=0.0)
    covered_by_storage_kwh: float = Field(ge=0.0)
    grid_bought_kwh: float = Field(ge=0.0)
    baseline_cost_amd: float = Field(ge=0.0)
    optimized_cost_amd: float = Field(ge=0.0)


class PlanResponse(BaseModel):
    """Day-ahead dispatch for one site, plus a separate seller/buyer settlement sketch."""

    scenario: str | None
    scenario_title: str
    summary: str
    solver: str
    model: str
    solve_time_ms: float
    battery: BatteryConfig
    site: SiteConfig
    kpis: Kpis
    comparison: PlanComparison
    blocks: list[ScheduleBlock]
    hours: list[HourSchedule]
    self_consumption_hours: list[SelfConsumptionHour]
    demand_response_active: bool = False
    demand_response_curtailed_kwh: float = 0.0
    demand_response_compensation_amd: float = 0.0
    peak_shaving_active: bool = False
    seller_total_solar_kwh: float = 0.0
    seller_total_sold_kwh: float = 0.0
    seller_revenue_amd: float = 0.0
    seller_success_fee_amd: float = 0.0
    seller_net_profit_amd: float = 0.0
    seller_sales_log: list[SellerSale] = Field(default_factory=list)
    buyer_total_consumed_kwh: float = 0.0
    buyer_covered_by_storage_kwh: float = 0.0
    buyer_grid_bought_kwh: float = 0.0
    buyer_baseline_cost_amd: float = 0.0
    buyer_optimized_cost_amd: float = 0.0
    buyer_savings_amd: float = 0.0
    buyer_hourly_costs: list[BuyerHourlyCost] = Field(default_factory=list)


class PlanRequest(BaseModel):
    """Preset scenario, with optional full overrides for site and battery."""

    model_config = ConfigDict(extra="forbid")

    scenario: str | None = "yerevan_summer"
    site: SiteConfig | None = None
    battery: BatteryConfig | None = None
    demand_response_active: bool = False
    peak_shaving_active: bool = False


class OptimizeRequest(BaseModel):
    """Optimize an already built 24-hour forecast."""

    model_config = ConfigDict(extra="forbid")

    battery: BatteryConfig = Field(default_factory=BatteryConfig)
    site: SiteConfig | None = None
    hours: list[ForecastPoint]
    demand_response_active: bool = False
    peak_shaving_active: bool = False

    @model_validator(mode="after")
    def _check_horizon(self) -> OptimizeRequest:
        if [point.hour for point in self.hours] != list(range(24)):
            raise ValueError("hours must contain hours 0 through 23 in order")
        return self


class ScenarioPreset(BaseModel):
    id: str
    title: str
    description: str
    site: SiteConfig
    battery: BatteryConfig


class TariffProfileInfo(BaseModel):
    id: str
    title: str
    description: str


class ScenariosResponse(BaseModel):
    scenarios: list[ScenarioPreset]
    tariff_profiles: list[TariffProfileInfo]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    solver: str
    solver_available: bool
