"""Synthetic 24-hour solar, load and tariff profiles for a Yerevan prosumer site.

The shapes are deterministic for a given seed. Prices are demo time-of-use
tariffs in Armenian dram, not an official ENA schedule.
"""

from __future__ import annotations

import math
import random

from .models import (
    BatteryConfig,
    ForecastPoint,
    ForecastResponse,
    ScenarioPreset,
    ScenariosResponse,
    SiteConfig,
    TariffProfileInfo,
)

# Scales a clear-sky sine curve so a cloudless Yerevan summer day yields
# about 6.0 kWh per installed kWp (peak sun hours × a 0.84 performance ratio).
SOLAR_CALIBRATION = 0.655
PERFORMANCE_RATIO = 0.84

TARIFF_INFO: tuple[TariffProfileInfo, ...] = (
    TariffProfileInfo(
        id="standard_tou",
        title="Time-of-use",
        description=(
            "Night import is cheap, the evening peak is expensive, and the "
            "feed-in price stays below retail. The battery stores surplus and "
            "covers the peak instead of selling at noon."
        ),
    ),
    TariffProfileInfo(
        id="export_spike",
        title="Evening export spike",
        description=(
            "For four evening hours the export price rises above the retail "
            "import price. Discharge is worth more on the market than on site, "
            "so the plan sells stored energy and buys power for the load."
        ),
    ),
)


def _gauss(hour: int, center: float, sigma: float) -> float:
    x = (hour + 0.5) - center
    return math.exp(-0.5 * (x / sigma) ** 2)


def load_shape(hour: int) -> float:
    """Unitless household/small-commercial shape: night base, morning and evening peaks."""
    night = 0.42
    morning = 0.85 * _gauss(hour, 7.6, 1.35)
    midday = 0.28 * _gauss(hour, 13.2, 2.4)
    evening = 1.45 * _gauss(hour, 20.0, 1.7)
    return night + morning + midday + evening


def clear_sky_fraction(hour: int, sunrise: float, sunset: float) -> float:
    """Mid-hour clear-sky power as a fraction of the calibrated peak."""
    midpoint = hour + 0.5
    if midpoint <= sunrise or midpoint >= sunset:
        return 0.0
    position = (midpoint - sunrise) / (sunset - sunrise)
    return math.sin(math.pi * position) ** 1.2


def prices_for_hour(hour: int, profile: str) -> tuple[float, float]:
    """Return (buy, sell) in AMD per kWh.

    Same-hour buy-and-sell cycling stays unprofitable after round-trip losses
    and degradation. Shifting energy into the evening still pays.
    """
    if profile == "standard_tou":
        if hour < 7:
            return 34.0, 18.0
        if hour < 17:
            return 48.0, 24.0
        if hour < 22:
            return 76.0, 30.0
        return 44.0, 20.0
    if profile == "export_spike":
        if hour < 7:
            return 34.0, 18.0
        if hour < 17:
            return 48.0, 24.0
        if hour < 21:
            return 64.0, 76.0
        if hour < 22:
            return 70.0, 30.0
        return 44.0, 20.0
    raise ValueError(f"Unknown tariff profile '{profile}'")


def _preset(
    scenario_id: str,
    title: str,
    description: str,
    site: SiteConfig,
    battery: BatteryConfig,
) -> ScenarioPreset:
    return ScenarioPreset(
        id=scenario_id,
        title=title,
        description=description,
        site=site,
        battery=battery,
    )


SCENARIOS: dict[str, ScenarioPreset] = {
    "yerevan_summer": _preset(
        "yerevan_summer",
        "Yerevan clear summer day",
        "Rooftop PV covers the day and fills the battery. The evening peak is served from storage instead of the grid.",
        SiteConfig(
            name="Yerevan prosumer site",
            pv_capacity_kwp=8.0,
            daily_load_kwh=30.0,
            cloud_cover=0.10,
            sunrise_hour=5.7,
            sunset_hour=20.3,
            tariff_profile="standard_tou",
            seed=7,
        ),
        BatteryConfig(
            capacity_kwh=12.0,
            max_charge_kw=5.0,
            max_discharge_kw=5.0,
            soc_initial=0.35,
            degradation_amd_per_kwh=4.0,
        ),
    ),
    "cloudy_day": _preset(
        "cloudy_day",
        "Cloudy weekday",
        "Solar is too weak to fill the battery. The optimizer buys night energy and uses it when the peak tariff starts.",
        SiteConfig(
            name="Yerevan prosumer site",
            pv_capacity_kwp=8.0,
            daily_load_kwh=32.0,
            cloud_cover=0.78,
            sunrise_hour=6.4,
            sunset_hour=19.2,
            tariff_profile="standard_tou",
            seed=11,
        ),
        BatteryConfig(
            capacity_kwh=12.0,
            max_charge_kw=5.0,
            max_discharge_kw=5.0,
            soc_initial=0.30,
            degradation_amd_per_kwh=4.0,
        ),
    ),
    "evening_export_spike": _preset(
        "evening_export_spike",
        "Evening export spike",
        "A short wholesale spike pays more for exports than the site saves by self-consuming. Stored solar is sold.",
        SiteConfig(
            name="Yerevan prosumer site",
            pv_capacity_kwp=7.0,
            daily_load_kwh=26.0,
            cloud_cover=0.18,
            sunrise_hour=5.9,
            sunset_hour=20.0,
            tariff_profile="export_spike",
            seed=21,
        ),
        BatteryConfig(
            capacity_kwh=10.0,
            max_charge_kw=5.0,
            max_discharge_kw=5.0,
            soc_initial=0.40,
            degradation_amd_per_kwh=4.0,
        ),
    ),
    "pv_surplus": _preset(
        "pv_surplus",
        "Oversized PV, small battery",
        "The array outgrows both the load and the battery. Midday surplus is sold once the battery is full.",
        SiteConfig(
            name="Yerevan prosumer site",
            pv_capacity_kwp=16.0,
            daily_load_kwh=18.0,
            cloud_cover=0.08,
            sunrise_hour=5.7,
            sunset_hour=20.3,
            tariff_profile="standard_tou",
            seed=4,
        ),
        BatteryConfig(
            capacity_kwh=6.0,
            max_charge_kw=3.0,
            max_discharge_kw=3.0,
            soc_initial=0.45,
            degradation_amd_per_kwh=4.0,
        ),
    ),
}


def list_scenarios() -> ScenariosResponse:
    return ScenariosResponse(
        scenarios=list(SCENARIOS.values()),
        tariff_profiles=list(TARIFF_INFO),
    )


def resolve_case(
    scenario: str | None,
    site: SiteConfig | None,
    battery: BatteryConfig | None,
) -> tuple[str | None, str, SiteConfig, BatteryConfig]:
    """Apply a named preset, then replace site or battery when the client sends them."""
    if scenario is None and site is None:
        raise ValueError("Provide a scenario id or a site configuration")
    title = "Custom day"
    if scenario is not None:
        preset = SCENARIOS.get(scenario)
        if preset is None:
            known = ", ".join(SCENARIOS)
            raise ValueError(f"Unknown scenario '{scenario}'. Known scenarios: {known}")
        base_site = preset.site
        base_battery = preset.battery
        title = preset.title
    else:
        base_site = SiteConfig()
        base_battery = BatteryConfig()
    return scenario, title, site or base_site, battery or base_battery


def build_forecast(
    site: SiteConfig,
    *,
    scenario: str | None = None,
    scenario_title: str = "Custom day",
) -> ForecastResponse:
    rng = random.Random(site.seed)
    raw_load = []
    for hour in range(24):
        wobble = 1.0 + rng.uniform(-0.035, 0.035)
        raw_load.append(load_shape(hour) * wobble)
    load_scale = site.daily_load_kwh / sum(raw_load) if site.daily_load_kwh > 0 else 0.0

    hours: list[ForecastPoint] = []
    for hour in range(24):
        solar_noise = 1.0 + rng.uniform(-0.02, 0.02)
        weather = (1.0 - 0.90 * site.cloud_cover) * solar_noise
        fraction = clear_sky_fraction(hour, site.sunrise_hour, site.sunset_hour)
        solar = site.pv_capacity_kwp * fraction * PERFORMANCE_RATIO * SOLAR_CALIBRATION * weather
        solar = max(0.0, solar)
        load = raw_load[hour] * load_scale
        buy, sell = prices_for_hour(hour, site.tariff_profile)
        hours.append(
            ForecastPoint(
                hour=hour,
                label=f"{hour:02d}:00",
                solar_kwh=round(solar, 4),
                load_kwh=round(load, 4),
                buy_price_amd=buy,
                sell_price_amd=sell,
            )
        )
    return ForecastResponse(
        scenario=scenario,
        scenario_title=scenario_title,
        site=site,
        hours=hours,
    )
