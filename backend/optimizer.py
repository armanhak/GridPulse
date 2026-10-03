"""24-hour BESS dispatch as a linear program.

The battery can, in each hour, store solar or grid energy, cover the on-site
load, or sell to the grid. PuLP builds the model and CBC solves it.

Objective
    Maximize export revenue minus import cost minus battery wear.

Constraints
    * PV is split between load, battery, export and curtailment.
    * Load is served by PV, the battery or the grid.
    * Charge and discharge respect inverter power.
    * State of charge stays inside the usable window.
    * The day ends with at least the starting state of charge, so the plan
      cannot book a saving by emptying the battery.

Charge and discharge are separate non-negative flows. Round-trip losses and
the wear term make doing both in the same hour unprofitable for the tariffs
shipped with the app. The formulation stays linear: no binary variables.
"""

from __future__ import annotations

import time
from collections import Counter

import pulp

from .models import (
    BatteryConfig,
    BuyerHourlyCost,
    ForecastPoint,
    HourSchedule,
    Kpis,
    PlanResponse,
    ScheduleBlock,
    SellerSale,
    SiteConfig,
)

# Illustrative operating factor for the Armenian generation mix
# (nuclear, hydro and gas). Used only to show the carbon side of a price-driven plan.
GRID_CO2_KG_PER_KWH = 0.21
DECISION_EPS_KWH = 0.05
SOLVER_NAME = "CBC"
PLATFORM_FEE_RATE = 0.15
PEAK_SHAVING_PRICE_AMD = 50.0
# Soft penalty so a physical shortfall stays feasible, but grid consumption
# above the threshold is used only when solar and the battery cannot cover the load.
PEAK_SHAVING_PENALTY_AMD = 5_000.0
DEMAND_RESPONSE_HOURS = frozenset(range(18, 21))
DEMAND_RESPONSE_KEEP = 0.60


class OptimizationError(Exception):
    """The dispatch model has no optimal solution."""

    def __init__(self, message: str, status: str | None = None) -> None:
        super().__init__(message)
        self.status = status


def _solver() -> pulp.COIN_CMD:
    """CBC via PuLP's COIN_CMD interface.

    PuLP 4 renamed PULP_CBC_CMD to COIN_CMD. The binary comes from the
    ``pulp[cbc]`` extra locally and from the ``coinor-cbc`` package in Docker.
    """
    solver = pulp.COIN_CMD(msg=False, timeLimit=10, randomSeed=1)
    if not solver.available():
        raise OptimizationError(
            "CBC solver is not available. Install coinor-cbc, or install PuLP with the cbc extra.",
            status="SolverUnavailable",
        )
    return solver


def solver_status() -> tuple[str, bool]:
    try:
        ready = bool(pulp.COIN_CMD(msg=False).available())
    except (OSError, pulp.PulpSolverError):
        return SOLVER_NAME, False
    return SOLVER_NAME, ready


def _clean(value: float | None, tolerance: float = 1e-6) -> float:
    if value is None or abs(value) < tolerance:
        return 0.0
    return float(value)


def _classify(
    charge: float,
    battery_to_load: float,
    exported: float,
    pv_to_load: float,
) -> str:
    controllable = {
        "store": charge,
        "use": battery_to_load,
        "sell": exported,
    }
    best_energy = max(controllable.values())
    if best_energy >= DECISION_EPS_KWH:
        return max(controllable, key=controllable.get)
    if pv_to_load >= DECISION_EPS_KWH:
        return "use"
    return "idle"


def _reason(
    decision: str,
    *,
    buy: float,
    sell: float,
    pv_to_load: float,
    pv_to_battery: float,
    pv_to_grid: float,
    grid_to_load: float,
    grid_to_battery: float,
    battery_to_load: float,
    battery_to_grid: float,
    charge: float,
) -> str:
    export = pv_to_grid + battery_to_grid
    if decision == "store":
        if pv_to_battery >= grid_to_battery:
            return (
                f"Store {charge:.1f} kWh, mostly solar surplus, and keep it for a higher-value hour."
            )
        return (
            f"Store {charge:.1f} kWh bought from the grid at {buy:.0f} AMD/kWh."
        )
    if decision == "sell":
        if battery_to_grid >= pv_to_grid and battery_to_grid >= DECISION_EPS_KWH:
            return (
                f"Sell {export:.1f} kWh. Battery export earns {sell:.0f} AMD/kWh, "
                f"more than covering the load at {buy:.0f}."
            )
        return (
            f"Sell {export:.1f} kWh of solar that does not fit the load or the battery "
            f"at {sell:.0f} AMD/kWh."
        )
    if decision == "use":
        if battery_to_load >= DECISION_EPS_KWH:
            return (
                f"Use {battery_to_load:.1f} kWh from the battery instead of buying at {buy:.0f} AMD/kWh."
            )
        return f"Use on-site solar to cover {pv_to_load:.1f} kWh of load."
    return f"Hold the battery. The site buys {grid_to_load:.1f} kWh at {buy:.0f} AMD/kWh."


def _block_text(decision: str, rows: list[HourSchedule]) -> str:
    charge = sum(row.charge_kwh for row in rows)
    pv_batt = sum(row.pv_to_battery_kwh for row in rows)
    grid_batt = sum(row.grid_to_battery_kwh for row in rows)
    batt_load = sum(row.battery_to_load_kwh for row in rows)
    batt_grid = sum(row.battery_to_grid_kwh for row in rows)
    pv_grid = sum(row.pv_to_grid_kwh for row in rows)
    pv_load = sum(row.pv_to_load_kwh for row in rows)
    grid_load = sum(row.grid_to_load_kwh for row in rows)
    if decision == "store":
        text = (
            f"Store {charge:.1f} kWh ({pv_batt:.1f} kWh from solar, {grid_batt:.1f} kWh from the grid)."
        )
        exported = pv_grid + batt_grid
        if exported >= 0.2:
            text += f" Another {exported:.1f} kWh is sold in the same window."
        return text
    if decision == "sell":
        text = (
            f"Sell {pv_grid + batt_grid:.1f} kWh "
            f"({batt_grid:.1f} kWh from the battery, {pv_grid:.1f} kWh directly from solar)."
        )
        if charge >= 0.2:
            text += f" The battery also stores {charge:.1f} kWh in this window."
        return text
    if decision == "use":
        if batt_load >= DECISION_EPS_KWH:
            return (
                f"Use {batt_load:.1f} kWh from the battery on site"
                + (f" and {pv_load:.1f} kWh of live solar." if pv_load >= DECISION_EPS_KWH else ".")
            )
        return f"Use {pv_load:.1f} kWh of live solar on site. The battery holds."
    return f"Hold. The site buys {grid_load:.1f} kWh and the battery is not dispatched."


def _blocks(rows: list[HourSchedule]) -> list[ScheduleBlock]:
    if not rows:
        return []
    grouped: list[list[HourSchedule]] = [[rows[0]]]
    for row in rows[1:]:
        if row.decision == grouped[-1][0].decision:
            grouped[-1].append(row)
        else:
            grouped.append([row])
    blocks: list[ScheduleBlock] = []
    for group in grouped:
        start = group[0].hour
        end = group[-1].hour
        blocks.append(
            ScheduleBlock(
                start_hour=start,
                end_hour=end,
                label=f"{start:02d}:00-{end + 1:02d}:00",
                decision=group[0].decision,
                text=_block_text(group[0].decision, group),
            )
        )
    return blocks


def _apply_demand_response(hours: list[ForecastPoint]) -> list[ForecastPoint]:
    """Cut 40% of the commercial load during the evening peak window 18:00–21:00."""
    adjusted: list[ForecastPoint] = []
    for point in hours:
        if point.hour not in DEMAND_RESPONSE_HOURS:
            adjusted.append(point)
            continue
        adjusted.append(
            point.model_copy(update={"load_kwh": round(point.load_kwh * DEMAND_RESPONSE_KEEP, 4)})
        )
    return adjusted


def _settle_roles(
    schedule: list[HourSchedule],
    battery: BatteryConfig,
) -> dict[str, float | list[SellerSale] | list[BuyerHourlyCost]]:
    """Split one pool dispatch into a seller invoice and a buyer bill.

    The seller owns the PV array and the battery. Energy delivered to the
    buyer's load or exported to the grid is sold at the wholesale price.
    Without VoltSync the seller would only be paid for the instantaneous
    surplus export. The platform keeps 15% of that extra benefit.

    The buyer, without VoltSync, buys the whole load at the retail tariff.
    With the pool, residual grid energy stays on the retail tariff and energy
    from solar or storage is settled at the wholesale price.
    """
    sales: list[SellerSale] = []
    buyer_hours: list[BuyerHourlyCost] = []
    passive_export_revenue = 0.0
    grid_purchase_cost = 0.0
    wear_cost = 0.0

    for row in schedule:
        volume = (
            row.pv_to_grid_kwh
            + row.battery_to_grid_kwh
            + row.pv_to_load_kwh
            + row.battery_to_load_kwh
        )
        revenue = volume * row.sell_price_amd
        sales.append(
            SellerSale(
                hour=row.hour,
                volume_kwh=round(volume, 3),
                price_amd=round(row.sell_price_amd, 2),
                revenue_amd=round(revenue, 2),
            )
        )
        passive_export_revenue += row.baseline_export_kwh * row.sell_price_amd
        grid_purchase_cost += row.grid_to_battery_kwh * row.buy_price_amd
        wear_cost += (row.charge_kwh + row.discharge_kwh) * battery.degradation_amd_per_kwh

        baseline_cost = row.load_kwh * row.buy_price_amd
        optimized_cost = row.grid_to_load_kwh * row.buy_price_amd + (
            row.pv_to_load_kwh + row.battery_to_load_kwh
        ) * row.sell_price_amd
        buyer_hours.append(
            BuyerHourlyCost(
                hour=row.hour,
                consumed_kwh=round(row.load_kwh, 3),
                covered_by_storage_kwh=round(row.battery_to_load_kwh, 3),
                grid_bought_kwh=round(row.grid_to_load_kwh, 3),
                baseline_cost_amd=round(baseline_cost, 2),
                optimized_cost_amd=round(optimized_cost, 2),
            )
        )

    seller_revenue = round(sum(item.revenue_amd for item in sales), 2)
    passive_export_revenue = round(passive_export_revenue, 2)
    grid_purchase_cost = round(grid_purchase_cost, 2)
    wear_cost = round(wear_cost, 2)
    operating_profit = seller_revenue - grid_purchase_cost - wear_cost
    additional_benefit = max(0.0, operating_profit - passive_export_revenue)
    success_fee = round(PLATFORM_FEE_RATE * additional_benefit, 2)
    net_profit = round(operating_profit - success_fee, 2)

    buyer_baseline = round(sum(item.baseline_cost_amd for item in buyer_hours), 2)
    buyer_optimized = round(sum(item.optimized_cost_amd for item in buyer_hours), 2)
    return {
        "seller_total_solar_kwh": round(sum(row.solar_kwh for row in schedule), 3),
        "seller_total_sold_kwh": round(sum(item.volume_kwh for item in sales), 3),
        "seller_revenue_amd": seller_revenue,
        "seller_success_fee_amd": success_fee,
        "seller_net_profit_amd": net_profit,
        "seller_sales_log": sales,
        "buyer_total_consumed_kwh": round(sum(row.load_kwh for row in schedule), 3),
        "buyer_covered_by_storage_kwh": round(
            sum(item.covered_by_storage_kwh for item in buyer_hours), 3
        ),
        "buyer_grid_bought_kwh": round(sum(item.grid_bought_kwh for item in buyer_hours), 3),
        "buyer_baseline_cost_amd": buyer_baseline,
        "buyer_optimized_cost_amd": buyer_optimized,
        "buyer_savings_amd": round(buyer_baseline - buyer_optimized, 2),
        "buyer_hourly_costs": buyer_hours,
    }


def _summary(kpis: Kpis, blocks: list[ScheduleBlock]) -> str:
    active = [block for block in blocks if block.decision != "idle"]
    schedule = " ".join(f"{block.label} {block.decision}." for block in active)
    if kpis.baseline_net_cost_amd <= 0:
        pct_text = "the site is already a net exporter without the battery"
    else:
        pct_text = f"{kpis.savings_pct:.0f}% below the no-battery bill"
    text = (
        f"VoltSync stores for {kpis.hours_store} h, uses stored or on-site energy for "
        f"{kpis.hours_use} h and sells for {kpis.hours_sell} h. "
        f"Net cost is {kpis.optimized_net_cost_amd:,.0f} AMD versus "
        f"{kpis.baseline_net_cost_amd:,.0f} AMD with no battery "
        f"({kpis.savings_amd:,.0f} AMD saved, {pct_text}). "
        f"The battery cycles {kpis.cycles:.2f} times."
    )
    if schedule:
        text += f" Dispatch windows: {schedule}"
    if kpis.co2_delta_kg > 0.05:
        text += (
            f" Grid imports rise by enough to add about {kpis.co2_delta_kg:.1f} kg CO2, "
            "because the battery buys night energy. The bill falls anyway."
        )
    elif kpis.co2_delta_kg < -0.05:
        text += f" The same plan avoids about {abs(kpis.co2_delta_kg):.1f} kg of grid CO2."
    return text


def optimize_day(
    hours: list[ForecastPoint],
    battery: BatteryConfig,
    *,
    scenario: str | None = None,
    scenario_title: str = "Custom day",
    site: SiteConfig | None = None,
    demand_response_active: bool = False,
    peak_shaving_active: bool = False,
) -> PlanResponse:
    """Solve one day and return the schedule, KPIs and seller/buyer accounts."""
    if [point.hour for point in hours] != list(range(24)):
        raise OptimizationError("Forecast must contain hours 0 through 23 in order", status="InvalidForecast")
    if demand_response_active:
        hours = _apply_demand_response(hours)
        scenario_title = f"{scenario_title} · DR 18:00–21:00"

    capacity = battery.capacity_kwh
    initial = battery.soc_initial * capacity
    energy_min = battery.soc_min * capacity
    energy_max = battery.soc_max * capacity
    max_charge = 0.0 if capacity == 0.0 else battery.max_charge_kw
    max_discharge = 0.0 if capacity == 0.0 else battery.max_discharge_kw
    eta_c = battery.charge_efficiency
    eta_d = battery.discharge_efficiency
    wear = battery.degradation_amd_per_kwh

    problem = pulp.LpProblem("voltsync_bess_arbitrage", pulp.LpMaximize)
    index = list(range(24))

    pv_load = problem.add_variable_dicts("pv_load", index, lowBound=0)
    pv_batt = problem.add_variable_dicts("pv_batt", index, lowBound=0)
    pv_grid = problem.add_variable_dicts("pv_grid", index, lowBound=0)
    pv_curt = problem.add_variable_dicts("pv_curt", index, lowBound=0)
    grid_load = problem.add_variable_dicts("grid_load", index, lowBound=0)
    grid_batt = problem.add_variable_dicts("grid_batt", index, lowBound=0)
    batt_load = problem.add_variable_dicts("batt_load", index, lowBound=0)
    batt_grid = problem.add_variable_dicts("batt_grid", index, lowBound=0)

    soc: dict[int, pulp.LpVariable] = {
        0: problem.add_variable("soc_0", lowBound=initial, upBound=initial),
    }
    for hour in range(1, 25):
        soc[hour] = problem.add_variable(f"soc_{hour}", lowBound=energy_min, upBound=energy_max)

    profit_terms = []
    for hour, point in enumerate(hours):
        problem += (
            pv_load[hour] + pv_batt[hour] + pv_grid[hour] + pv_curt[hour] == point.solar_kwh,
            f"pv_balance_{hour}",
        )
        problem += (
            pv_load[hour] + grid_load[hour] + batt_load[hour] == point.load_kwh,
            f"load_balance_{hour}",
        )
        problem += pv_batt[hour] + grid_batt[hour] <= max_charge, f"charge_power_{hour}"
        problem += batt_load[hour] + batt_grid[hour] <= max_discharge, f"discharge_power_{hour}"
        if peak_shaving_active and point.buy_price_amd > PEAK_SHAVING_PRICE_AMD:
            peak_slack = problem.add_variable(f"peak_slack_{hour}", lowBound=0)
            problem += grid_load[hour] <= peak_slack, f"peak_shave_{hour}"
            profit_terms.append(-PEAK_SHAVING_PENALTY_AMD * peak_slack)
        problem += (
            soc[hour + 1]
            == soc[hour]
            + eta_c * (pv_batt[hour] + grid_batt[hour])
            - (batt_load[hour] + batt_grid[hour]) / eta_d,
            f"soc_dynamics_{hour}",
        )
        exported = pv_grid[hour] + batt_grid[hour]
        imported = grid_load[hour] + grid_batt[hour]
        charged = pv_batt[hour] + grid_batt[hour]
        discharged = batt_load[hour] + batt_grid[hour]
        profit_terms.append(
            point.sell_price_amd * exported
            - point.buy_price_amd * imported
            - wear * (charged + discharged)
        )

    # Do not liquidate the starting inventory. Ending higher is allowed and
    # shows up as leftover stored energy, not as fake bill savings.
    problem += soc[24] >= initial, "terminal_soc"
    problem += pulp.lpSum(profit_terms)

    started = time.perf_counter()
    try:
        stats = problem.solve(_solver())
    except pulp.PulpSolverError as exc:
        raise OptimizationError(str(exc), status="SolverUnavailable") from exc
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if stats.status != pulp.LpSolveStatus.Optimal or not stats.has_solution:
        raise OptimizationError(
            "The battery cannot follow these limits over 24 hours. "
            "Relax the power limit, the state-of-charge window, or the starting charge.",
            status=stats.status_str,
        )

    schedule: list[HourSchedule] = []
    for hour, point in enumerate(hours):
        flows = {
            "pv_to_load": _clean(pv_load[hour].varValue),
            "pv_to_battery": _clean(pv_batt[hour].varValue),
            "pv_to_grid": _clean(pv_grid[hour].varValue),
            "pv_curtailed": _clean(pv_curt[hour].varValue),
            "grid_to_load": _clean(grid_load[hour].varValue),
            "grid_to_battery": _clean(grid_batt[hour].varValue),
            "battery_to_load": _clean(batt_load[hour].varValue),
            "battery_to_grid": _clean(batt_grid[hour].varValue),
        }
        charge = flows["pv_to_battery"] + flows["grid_to_battery"]
        discharge = flows["battery_to_load"] + flows["battery_to_grid"]
        exported = flows["pv_to_grid"] + flows["battery_to_grid"]
        imported = flows["grid_to_load"] + flows["grid_to_battery"]
        end_kwh = _clean(soc[hour + 1].varValue)
        decision = _classify(charge, flows["battery_to_load"], exported, flows["pv_to_load"])

        baseline_export = max(0.0, point.solar_kwh - point.load_kwh)
        baseline_import = max(0.0, point.load_kwh - point.solar_kwh)
        baseline_cost = point.buy_price_amd * baseline_import - point.sell_price_amd * baseline_export
        net_cost = (
            point.buy_price_amd * imported
            - point.sell_price_amd * exported
            + wear * (charge + discharge)
        )
        soc_pct = 0.0 if capacity == 0.0 else 100.0 * end_kwh / capacity
        schedule.append(
            HourSchedule(
                hour=hour,
                label=point.label,
                solar_kwh=round(point.solar_kwh, 3),
                load_kwh=round(point.load_kwh, 3),
                buy_price_amd=round(point.buy_price_amd, 2),
                sell_price_amd=round(point.sell_price_amd, 2),
                pv_to_load_kwh=round(flows["pv_to_load"], 3),
                pv_to_battery_kwh=round(flows["pv_to_battery"], 3),
                pv_to_grid_kwh=round(flows["pv_to_grid"], 3),
                pv_curtailed_kwh=round(flows["pv_curtailed"], 3),
                grid_to_load_kwh=round(flows["grid_to_load"], 3),
                grid_to_battery_kwh=round(flows["grid_to_battery"], 3),
                battery_to_load_kwh=round(flows["battery_to_load"], 3),
                battery_to_grid_kwh=round(flows["battery_to_grid"], 3),
                charge_kwh=round(charge, 3),
                discharge_kwh=round(discharge, 3),
                soc_kwh=round(end_kwh, 3),
                soc_pct=round(soc_pct, 2),
                decision=decision,
                reason=_reason(
                    decision,
                    buy=point.buy_price_amd,
                    sell=point.sell_price_amd,
                    pv_to_load=flows["pv_to_load"],
                    pv_to_battery=flows["pv_to_battery"],
                    pv_to_grid=flows["pv_to_grid"],
                    grid_to_load=flows["grid_to_load"],
                    grid_to_battery=flows["grid_to_battery"],
                    battery_to_load=flows["battery_to_load"],
                    battery_to_grid=flows["battery_to_grid"],
                    charge=charge,
                ),
                net_cost_amd=round(net_cost, 2),
                baseline_import_kwh=round(baseline_import, 3),
                baseline_export_kwh=round(baseline_export, 3),
                baseline_net_cost_amd=round(baseline_cost, 2),
            )
        )

    counts = Counter(row.decision for row in schedule)
    solar_total = sum(row.solar_kwh for row in schedule)
    load_total = sum(row.load_kwh for row in schedule)
    import_total = sum(row.grid_to_load_kwh + row.grid_to_battery_kwh for row in schedule)
    export_total = sum(row.pv_to_grid_kwh + row.battery_to_grid_kwh for row in schedule)
    baseline_import = sum(row.baseline_import_kwh for row in schedule)
    baseline_export = sum(row.baseline_export_kwh for row in schedule)
    optimized_cost = sum(row.net_cost_amd for row in schedule)
    baseline_cost = sum(row.baseline_net_cost_amd for row in schedule)
    savings = baseline_cost - optimized_cost
    if baseline_cost > 1e-6:
        savings_pct = 100.0 * savings / baseline_cost
    else:
        savings_pct = 0.0
    charged = sum(row.charge_kwh for row in schedule)
    discharged = sum(row.discharge_kwh for row in schedule)
    served_locally = sum(row.pv_to_load_kwh + row.battery_to_load_kwh for row in schedule)
    self_sufficiency = 0.0 if load_total <= 1e-9 else 100.0 * served_locally / load_total
    optimized_peak = max((row.grid_to_load_kwh + row.grid_to_battery_kwh) for row in schedule)
    baseline_peak = max(row.baseline_import_kwh for row in schedule)
    kpis = Kpis(
        optimized_net_cost_amd=round(optimized_cost, 2),
        baseline_net_cost_amd=round(baseline_cost, 2),
        savings_amd=round(savings, 2),
        savings_pct=round(savings_pct, 2),
        illustrative_annual_savings_amd=round(savings * 365.0, 2),
        grid_import_kwh=round(import_total, 3),
        grid_export_kwh=round(export_total, 3),
        baseline_import_kwh=round(baseline_import, 3),
        baseline_export_kwh=round(baseline_export, 3),
        solar_kwh=round(solar_total, 3),
        load_kwh=round(load_total, 3),
        charged_kwh=round(charged, 3),
        discharged_kwh=round(discharged, 3),
        cycles=round(0.0 if capacity == 0.0 else discharged / capacity, 3),
        self_sufficiency_pct=round(self_sufficiency, 2),
        curtailed_kwh=round(sum(row.pv_curtailed_kwh for row in schedule), 3),
        co2_delta_kg=round((import_total - baseline_import) * GRID_CO2_KG_PER_KWH, 3),
        hours_store=counts["store"],
        hours_use=counts["use"],
        hours_sell=counts["sell"],
        hours_idle=counts["idle"],
        max_grid_import_kw=round(optimized_peak, 3),
        baseline_max_grid_import_kw=round(baseline_peak, 3),
    )
    plan_blocks = _blocks(schedule)
    resolved_site = site or SiteConfig()
    accounts = _settle_roles(schedule, battery)
    return PlanResponse(
        scenario=scenario,
        scenario_title=scenario_title,
        summary=_summary(kpis, plan_blocks),
        solver=SOLVER_NAME,
        model="LP",
        solve_time_ms=round(elapsed_ms, 1),
        battery=battery,
        site=resolved_site,
        kpis=kpis,
        blocks=plan_blocks,
        hours=schedule,
        demand_response_active=demand_response_active,
        peak_shaving_active=peak_shaving_active,
        seller_total_solar_kwh=accounts["seller_total_solar_kwh"],
        seller_total_sold_kwh=accounts["seller_total_sold_kwh"],
        seller_revenue_amd=accounts["seller_revenue_amd"],
        seller_success_fee_amd=accounts["seller_success_fee_amd"],
        seller_net_profit_amd=accounts["seller_net_profit_amd"],
        seller_sales_log=accounts["seller_sales_log"],
        buyer_total_consumed_kwh=accounts["buyer_total_consumed_kwh"],
        buyer_covered_by_storage_kwh=accounts["buyer_covered_by_storage_kwh"],
        buyer_grid_bought_kwh=accounts["buyer_grid_bought_kwh"],
        buyer_baseline_cost_amd=accounts["buyer_baseline_cost_amd"],
        buyer_optimized_cost_amd=accounts["buyer_optimized_cost_amd"],
        buyer_savings_amd=accounts["buyer_savings_amd"],
        buyer_hourly_costs=accounts["buyer_hourly_costs"],
    )


def _print_plan(plan: PlanResponse) -> None:
    print(f"\n=== {plan.scenario_title} ({plan.solve_time_ms:.0f} ms, {plan.solver}) ===")
    print(plan.summary)
    print(
        f"solar {plan.kpis.solar_kwh:.1f} kWh | load {plan.kpis.load_kwh:.1f} kWh | "
        f"import {plan.kpis.grid_import_kwh:.1f} vs baseline {plan.kpis.baseline_import_kwh:.1f}"
    )
    print(
        f"seller sold {plan.seller_total_sold_kwh:.1f} kWh | "
        f"revenue {plan.seller_revenue_amd:.0f} | fee {plan.seller_success_fee_amd:.0f} | "
        f"net {plan.seller_net_profit_amd:.0f}"
    )
    print(
        f"buyer load {plan.buyer_total_consumed_kwh:.1f} kWh | "
        f"storage {plan.buyer_covered_by_storage_kwh:.1f} | "
        f"bill {plan.buyer_optimized_cost_amd:.0f} vs {plan.buyer_baseline_cost_amd:.0f} | "
        f"saved {plan.buyer_savings_amd:.0f}"
    )
    print("hour decision  charge  disch  soc%   import  export  cost")
    for row in plan.hours:
        print(
            f"{row.label}  {row.decision:<6}  {row.charge_kwh:6.2f}  {row.discharge_kwh:5.2f}  "
            f"{row.soc_pct:5.1f}  {row.grid_to_load_kwh + row.grid_to_battery_kwh:6.2f}  "
            f"{row.pv_to_grid_kwh + row.battery_to_grid_kwh:6.2f}  {row.net_cost_amd:8.1f}"
        )


if __name__ == "__main__":
    from .generator import SCENARIOS, build_forecast

    failed = False
    for scenario_id, preset in SCENARIOS.items():
        forecast = build_forecast(preset.site, scenario=scenario_id, scenario_title=preset.title)
        plan = optimize_day(
            forecast.hours,
            preset.battery,
            scenario=scenario_id,
            scenario_title=preset.title,
            site=preset.site,
        )
        _print_plan(plan)
        if plan.kpis.savings_amd < -0.05:
            print("ERROR: savings below baseline")
            failed = True
        if abs(sum(item.volume_kwh for item in plan.seller_sales_log) - plan.seller_total_sold_kwh) > 0.05:
            print("ERROR: seller sales log does not match sold volume")
            failed = True
        if abs(sum(item.revenue_amd for item in plan.seller_sales_log) - plan.seller_revenue_amd) > 0.1:
            print("ERROR: seller sales log does not match revenue")
            failed = True
        if plan.seller_success_fee_amd < -0.01 or plan.seller_success_fee_amd > plan.seller_revenue_amd + 0.05:
            print("ERROR: seller success fee is outside 0..revenue")
            failed = True
        if abs(
            plan.buyer_savings_amd - (plan.buyer_baseline_cost_amd - plan.buyer_optimized_cost_amd)
        ) > 0.1:
            print("ERROR: buyer savings do not match the two bills")
            failed = True
        if abs(sum(item.baseline_cost_amd for item in plan.buyer_hourly_costs) - plan.buyer_baseline_cost_amd) > 0.1:
            print("ERROR: buyer hourly baseline does not match the bill")
            failed = True
        if abs(plan.buyer_total_consumed_kwh - plan.kpis.load_kwh) > 0.05:
            print("ERROR: buyer consumption does not match site load")
            failed = True
        for row in plan.hours:
            if row.charge_kwh > 0.05 and row.discharge_kwh > 0.05:
                print(f"ERROR: simultaneous charge and discharge at {row.label}")
                failed = True
            balance_pv = (
                row.pv_to_load_kwh
                + row.pv_to_battery_kwh
                + row.pv_to_grid_kwh
                + row.pv_curtailed_kwh
            )
            balance_load = row.pv_to_load_kwh + row.grid_to_load_kwh + row.battery_to_load_kwh
            if abs(balance_pv - row.solar_kwh) > 0.02 or abs(balance_load - row.load_kwh) > 0.02:
                print(f"ERROR: energy balance broken at {row.label}")
                failed = True
    summer = SCENARIOS["yerevan_summer"]
    base_forecast = build_forecast(summer.site, scenario="yerevan_summer", scenario_title=summer.title)
    base_plan = optimize_day(
        base_forecast.hours,
        summer.battery,
        scenario="yerevan_summer",
        scenario_title=summer.title,
        site=summer.site,
    )
    dr_plan = optimize_day(
        base_forecast.hours,
        summer.battery,
        scenario="yerevan_summer",
        scenario_title=summer.title,
        site=summer.site,
        demand_response_active=True,
    )
    for hour in DEMAND_RESPONSE_HOURS:
        expected = round(base_plan.hours[hour].load_kwh * DEMAND_RESPONSE_KEEP, 3)
        actual = dr_plan.hours[hour].load_kwh
        if abs(actual - expected) > 0.05:
            print(f"ERROR: demand response did not cut hour {hour}: {actual} vs {expected}")
            failed = True
    peak_plan = optimize_day(
        base_forecast.hours,
        summer.battery,
        scenario="yerevan_summer",
        scenario_title=summer.title,
        site=summer.site,
        peak_shaving_active=True,
    )
    for row in peak_plan.hours:
        if row.buy_price_amd > PEAK_SHAVING_PRICE_AMD and row.grid_to_load_kwh > 0.15:
            print(f"ERROR: peak shaving still buys {row.grid_to_load_kwh} kWh at {row.label}")
            failed = True
    if failed:
        raise SystemExit(1)
    print("\nAll scenarios solved with a feasible, balanced dispatch.")
