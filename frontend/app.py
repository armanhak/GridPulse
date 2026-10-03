"""VoltSync dashboard: a 24-hour store / use / sell dispatch."""

from __future__ import annotations

import html
import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

DEFAULT_API_URL = os.environ.get("VOLTSYNC_API_URL", "http://localhost:8000")

DECISION_COLOR = {
    "store": "#2ee6a6",
    "use": "#7aa2ff",
    "sell": "#f5c542",
    "idle": "#5c6b82",
}
DECISION_LABEL = {
    "store": "Store",
    "use": "Use",
    "sell": "Sell",
    "idle": "Idle",
}

st.set_page_config(
    page_title="VoltSync VPP",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stApp {
        background:
          radial-gradient(1100px 520px at 8% -10%, rgba(46, 230, 166, 0.16), transparent 55%),
          radial-gradient(900px 480px at 100% 0%, rgba(122, 162, 255, 0.14), transparent 50%),
          #0b1220;
        color: #e7eef8;
      }
      header[data-testid="stHeader"] {
        background: transparent;
      }
      [data-testid="stSidebar"] {
        background: #10192b;
        border-right: 1px solid rgba(255, 255, 255, 0.06);
      }
      div[data-testid="stMetric"] {
        background: rgba(18, 26, 43, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 14px;
        padding: 14px 16px 10px 16px;
      }
      .vs-hero {
        padding: 8px 2px 0 2px;
      }
      .vs-kicker {
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #2ee6a6;
        font-size: 0.78rem;
        font-weight: 650;
        margin-bottom: 6px;
      }
      .vs-title {
        font-size: 2.1rem;
        line-height: 1.1;
        font-weight: 720;
        margin: 0;
        color: #f4f8ff;
      }
      .vs-sub {
        color: #9aadc4;
        margin-top: 6px;
        font-size: 1.02rem;
      }
      .vs-summary {
        background: linear-gradient(180deg, rgba(18, 32, 48, 0.95), rgba(14, 22, 38, 0.95));
        border: 1px solid rgba(46, 230, 166, 0.28);
        border-radius: 16px;
        padding: 16px 18px;
        color: #d7e6f5;
        line-height: 1.45;
        margin: 8px 0 16px 0;
      }
      .vs-block {
        border-radius: 12px;
        padding: 10px 12px;
        margin-bottom: 8px;
        background: #121a2b;
        border: 1px solid rgba(255, 255, 255, 0.05);
      }
      .vs-block b { color: #f4f8ff; }
      .vs-note {
        color: #8ea0b8;
        font-size: 0.86rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


class ApiError(Exception):
    """The VoltSync API could not return a plan."""


def api_get(base_url: str, path: str) -> Any:
    try:
        response = requests.get(f"{base_url.rstrip('/')}{path}", timeout=20)
    except requests.RequestException as exc:
        raise ApiError(f"Cannot reach the API at {base_url}. {exc}") from exc
    if response.status_code >= 400:
        raise ApiError(_error_text(response))
    return response.json()


def api_post(base_url: str, path: str, payload: dict[str, Any]) -> Any:
    try:
        response = requests.post(f"{base_url.rstrip('/')}{path}", json=payload, timeout=30)
    except requests.RequestException as exc:
        raise ApiError(f"Cannot reach the API at {base_url}. {exc}") from exc
    if response.status_code >= 400:
        raise ApiError(_error_text(response))
    return response.json()


def _error_text(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"API returned HTTP {response.status_code}."
    detail = body.get("detail", body)
    return f"API returned HTTP {response.status_code}: {detail}"


def _layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16, 25, 43, 0.72)",
        font={"color": "#d5e2f2", "family": "Segoe UI, sans-serif", "size": 13},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0,
            "bgcolor": "rgba(0,0,0,0)",
        },
        margin={"l": 52, "r": 48, "t": 48, "b": 42},
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False, showline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False, showline=False)
    return fig


def chart_decisions(hours: list[dict[str, Any]]) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=[row["label"] for row in hours],
            y=[1] * len(hours),
            marker_color=[DECISION_COLOR[row["decision"]] for row in hours],
            text=[DECISION_LABEL[row["decision"]] for row in hours],
            textposition="inside",
            hovertext=[row["reason"] for row in hours],
            hoverinfo="text",
            name="Decision",
        )
    )
    fig.update_yaxes(visible=False, range=[0, 1])
    fig.update_layout(bargap=0.18, showlegend=False)
    return _layout(fig, 168)


def chart_energy(hours: list[dict[str, Any]]) -> go.Figure:
    labels = [row["label"] for row in hours]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["solar_kwh"] for row in hours],
            name="Solar",
            mode="lines",
            line={"color": "#f5c542", "width": 2.5},
            fill="tozeroy",
            fillcolor="rgba(245, 197, 66, 0.18)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["load_kwh"] for row in hours],
            name="Load",
            mode="lines",
            line={"color": "#7aa2ff", "width": 2.5},
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[row["charge_kwh"] for row in hours],
            name="Charge",
            marker_color="rgba(46, 230, 166, 0.85)",
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[-row["discharge_kwh"] for row in hours],
            name="Discharge",
            marker_color="rgba(255, 139, 123, 0.9)",
        )
    )
    fig.update_layout(barmode="relative")
    fig.update_yaxes(title_text="kWh in the hour")
    return _layout(fig, 420)


def chart_soc_prices(hours: list[dict[str, Any]], battery: dict[str, Any]) -> go.Figure:
    labels = ["start"] + [row["label"] for row in hours]
    soc = [round(battery["soc_initial"] * 100.0, 2)] + [row["soc_pct"] for row in hours]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=soc,
            name="State of charge",
            mode="lines",
            line={"color": "#c9a6ff", "width": 3, "shape": "hv"},
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=[row["label"] for row in hours],
            y=[row["buy_price_amd"] for row in hours],
            name="Buy price",
            mode="lines",
            line={"color": "#ff8b7b", "width": 2, "dash": "dot"},
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(
            x=[row["label"] for row in hours],
            y=[row["sell_price_amd"] for row in hours],
            name="Sell price",
            mode="lines",
            line={"color": "#2ee6a6", "width": 2, "dash": "dot"},
        ),
        secondary_y=True,
    )
    fig.add_hline(
        y=battery["soc_min"] * 100.0,
        line_dash="dash",
        line_color="rgba(255,255,255,0.25)",
        annotation_text="SOC min",
        annotation_font_color="#8ea0b8",
    )
    fig.add_hline(
        y=battery["soc_max"] * 100.0,
        line_dash="dash",
        line_color="rgba(255,255,255,0.25)",
        annotation_text="SOC max",
        annotation_font_color="#8ea0b8",
    )
    fig.update_yaxes(title_text="State of charge %", secondary_y=False, range=[0, 100])
    fig.update_yaxes(title_text="AMD / kWh", secondary_y=True)
    return _layout(fig, 420)


def chart_grid(hours: list[dict[str, Any]]) -> go.Figure:
    labels = [row["label"] for row in hours]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[row["baseline_import_kwh"] for row in hours],
            name="Import, no battery",
            marker_color="rgba(255, 139, 123, 0.45)",
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[row["grid_to_load_kwh"] + row["grid_to_battery_kwh"] for row in hours],
            name="Import, VoltSync",
            marker_color="#ff8b7b",
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[-row["baseline_export_kwh"] for row in hours],
            name="Export, no battery",
            marker_color="rgba(46, 230, 166, 0.35)",
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[-(row["pv_to_grid_kwh"] + row["battery_to_grid_kwh"]) for row in hours],
            name="Export, VoltSync",
            marker_color="#2ee6a6",
        )
    )
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="kWh  ·  import up, export down")
    return _layout(fig, 400)


def schedule_frame(hours: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for row in hours:
        rows.append(
            {
                "Hour": row["label"],
                "Decision": DECISION_LABEL[row["decision"]],
                "Why": row["reason"],
                "Solar kWh": row["solar_kwh"],
                "Load kWh": row["load_kwh"],
                "Buy AMD": row["buy_price_amd"],
                "Sell AMD": row["sell_price_amd"],
                "Charge kWh": row["charge_kwh"],
                "Discharge kWh": row["discharge_kwh"],
                "SOC %": row["soc_pct"],
                "Grid import kWh": round(row["grid_to_load_kwh"] + row["grid_to_battery_kwh"], 3),
                "Grid export kWh": round(row["pv_to_grid_kwh"] + row["battery_to_grid_kwh"], 3),
                "Net cost AMD": row["net_cost_amd"],
            }
        )
    return pd.DataFrame(rows)


def paint_decision(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    colors = {
        "Store": "background-color: #123f36; color: #d8fff3",
        "Use": "background-color: #1a2d52; color: #e4ecff",
        "Sell": "background-color: #433812; color: #fff3c4",
        "Idle": "background-color: #243044; color: #d5e2f2",
    }

    def _cell(value: str) -> str:
        return colors.get(value, "")

    return frame.style.map(_cell, subset=["Decision"])


def apply_preset(preset: dict[str, Any]) -> None:
    site = preset["site"]
    battery = preset["battery"]
    st.session_state.pv_capacity_kwp = float(site["pv_capacity_kwp"])
    st.session_state.daily_load_kwh = float(site["daily_load_kwh"])
    st.session_state.cloud_cover = float(site["cloud_cover"])
    st.session_state.sunrise_hour = float(site["sunrise_hour"])
    st.session_state.sunset_hour = float(site["sunset_hour"])
    st.session_state.tariff_profile = site["tariff_profile"]
    st.session_state.seed = int(site["seed"])
    st.session_state.capacity_kwh = float(battery["capacity_kwh"])
    st.session_state.power_kw = float(battery["max_charge_kw"])
    st.session_state.soc_initial = float(battery["soc_initial"])
    st.session_state.soc_min = float(battery["soc_min"])
    st.session_state.soc_max = float(battery["soc_max"])
    st.session_state.charge_efficiency = float(battery["charge_efficiency"])
    st.session_state.discharge_efficiency = float(battery["discharge_efficiency"])
    st.session_state.degradation_amd_per_kwh = float(battery["degradation_amd_per_kwh"])


def payload_from_state(scenario_id: str) -> dict[str, Any]:
    return {
        "scenario": scenario_id,
        "site": {
            "name": "Yerevan prosumer site",
            "pv_capacity_kwp": float(st.session_state.pv_capacity_kwp),
            "daily_load_kwh": float(st.session_state.daily_load_kwh),
            "cloud_cover": float(st.session_state.cloud_cover),
            "sunrise_hour": float(st.session_state.sunrise_hour),
            "sunset_hour": float(st.session_state.sunset_hour),
            "tariff_profile": st.session_state.tariff_profile,
            "seed": int(st.session_state.seed),
        },
        "battery": {
            "capacity_kwh": float(st.session_state.capacity_kwh),
            "max_charge_kw": float(st.session_state.power_kw),
            "max_discharge_kw": float(st.session_state.power_kw),
            "charge_efficiency": float(st.session_state.charge_efficiency),
            "discharge_efficiency": float(st.session_state.discharge_efficiency),
            "soc_min": float(st.session_state.soc_min),
            "soc_max": float(st.session_state.soc_max),
            "soc_initial": float(st.session_state.soc_initial),
            "degradation_amd_per_kwh": float(st.session_state.degradation_amd_per_kwh),
        },
    }


def render_sidebar(catalog: dict[str, Any]) -> str:
    st.sidebar.markdown("### Site and battery")
    presets = catalog["scenarios"]
    labels = {item["id"]: item["title"] for item in presets}
    scenario_id = st.sidebar.selectbox(
        "Day",
        options=[item["id"] for item in presets],
        format_func=lambda item: labels[item],
        key="scenario_id",
        on_change=_on_scenario_change,
        kwargs={"presets": presets},
    )
    selected = next(item for item in presets if item["id"] == scenario_id)
    st.sidebar.caption(selected["description"])

    tariff_labels = {item["id"]: item["title"] for item in catalog["tariff_profiles"]}
    st.sidebar.selectbox(
        "Tariff",
        options=list(tariff_labels),
        format_func=lambda item: tariff_labels[item],
        key="tariff_profile",
    )
    st.sidebar.slider("PV array (kWp)", 0.0, 40.0, step=0.5, key="pv_capacity_kwp")
    st.sidebar.slider("Daily load (kWh)", 0.0, 120.0, step=1.0, key="daily_load_kwh")
    st.sidebar.slider("Cloud cover", 0.0, 1.0, step=0.01, key="cloud_cover")
    st.sidebar.slider("Battery capacity (kWh)", 0.0, 80.0, step=0.5, key="capacity_kwh")
    st.sidebar.slider("Inverter power (kW)", 0.0, 40.0, step=0.5, key="power_kw")
    st.sidebar.slider("Starting state of charge", 0.0, 1.0, step=0.01, key="soc_initial")
    st.sidebar.slider("Wear (AMD per kWh moved)", 0.0, 20.0, step=0.5, key="degradation_amd_per_kwh")
    st.sidebar.number_input("Weather seed", min_value=0, max_value=10_000_000, step=1, key="seed")

    with st.sidebar.expander("Battery limits"):
        st.slider("Minimum SOC", 0.0, 0.5, step=0.01, key="soc_min")
        st.slider("Maximum SOC", 0.5, 1.0, step=0.01, key="soc_max")
        st.slider("Charge efficiency", 0.70, 1.0, step=0.01, key="charge_efficiency")
        st.slider("Discharge efficiency", 0.70, 1.0, step=0.01, key="discharge_efficiency")
        st.slider("Sunrise hour", 4.0, 9.0, step=0.1, key="sunrise_hour")
        st.slider("Sunset hour", 16.0, 22.0, step=0.1, key="sunset_hour")
    return scenario_id


def _on_scenario_change(presets: list[dict[str, Any]]) -> None:
    selected = next(item for item in presets if item["id"] == st.session_state.scenario_id)
    apply_preset(selected)


def ensure_catalog(base_url: str) -> dict[str, Any]:
    if st.session_state.get("api_url") != base_url or "catalog" not in st.session_state:
        catalog = api_get(base_url, "/api/v1/scenarios")
        st.session_state.catalog = catalog
        st.session_state.api_url = base_url
        if "scenario_id" not in st.session_state:
            st.session_state.scenario_id = catalog["scenarios"][0]["id"]
            apply_preset(catalog["scenarios"][0])
    return st.session_state.catalog


def render_plan(plan: dict[str, Any]) -> None:
    kpis = plan["kpis"]
    st.markdown(
        f"""
        <div class="vs-hero">
          <div class="vs-kicker">VoltSync VPP · {plan["scenario_title"]}</div>
          <h1 class="vs-title">Store, use, or sell?</h1>
          <p class="vs-sub">24-hour battery dispatch for a Yerevan prosumer. Solved as a linear program with {plan["solver"]} in {plan["solve_time_ms"]:.0f} ms.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="vs-summary">{html.escape(plan["summary"])}</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saved vs no battery", f"{kpis['savings_amd']:,.0f} AMD", f"{kpis['savings_pct']:.0f}%")
    c2.metric(
        "If this day repeated",
        f"{kpis['illustrative_annual_savings_amd']:,.0f} AMD",
        "365 identical days",
    )
    c3.metric("Self-sufficiency", f"{kpis['self_sufficiency_pct']:.0f}%", f"{kpis['cycles']:.2f} battery cycles")
    co2 = kpis["co2_delta_kg"]
    c4.metric(
        "Grid CO₂ vs no battery",
        f"{co2:+.1f} kg",
        "negative means less CO₂",
        delta_color="off",
    )

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Store", f"{kpis['hours_store']} h")
    d2.metric("Use", f"{kpis['hours_use']} h")
    d3.metric("Sell", f"{kpis['hours_sell']} h")
    d4.metric("Idle", f"{kpis['hours_idle']} h")

    st.plotly_chart(chart_decisions(plan["hours"]), width="stretch", config={"displayModeBar": False})

    left, right = st.columns([1.15, 0.85])
    with left:
        st.subheader("What the battery does")
        for block in plan["blocks"]:
            color = DECISION_COLOR[block["decision"]]
            st.markdown(
                f"""
                <div class="vs-block" style="border-left: 4px solid {color}">
                  <b>{block["label"]} · {DECISION_LABEL[block["decision"]]}</b><br/>
                  {block["text"]}
                </div>
                """,
                unsafe_allow_html=True,
            )
    with right:
        st.subheader("Day totals")
        totals = pd.DataFrame(
            [
                ("Solar generation", f"{kpis['solar_kwh']:.1f} kWh"),
                ("Site load", f"{kpis['load_kwh']:.1f} kWh"),
                ("Energy charged", f"{kpis['charged_kwh']:.1f} kWh"),
                ("Energy discharged", f"{kpis['discharged_kwh']:.1f} kWh"),
                ("Grid import", f"{kpis['grid_import_kwh']:.1f} kWh"),
                ("Grid import, no battery", f"{kpis['baseline_import_kwh']:.1f} kWh"),
                ("Grid export", f"{kpis['grid_export_kwh']:.1f} kWh"),
                ("Grid export, no battery", f"{kpis['baseline_export_kwh']:.1f} kWh"),
                ("Peak import", f"{kpis['max_grid_import_kw']:.1f} kW"),
                ("Peak import, no battery", f"{kpis['baseline_max_grid_import_kw']:.1f} kW"),
                ("Net cost", f"{kpis['optimized_net_cost_amd']:,.0f} AMD"),
                ("Net cost, no battery", f"{kpis['baseline_net_cost_amd']:,.0f} AMD"),
                ("Curtailed solar", f"{kpis['curtailed_kwh']:.1f} kWh"),
            ],
            columns=["Metric", "Value"],
        )
        st.dataframe(totals, hide_index=True, width="stretch", height=460)

    st.plotly_chart(chart_energy(plan["hours"]), width="stretch", config={"displayModeBar": False})
    st.plotly_chart(
        chart_soc_prices(plan["hours"], plan["battery"]),
        width="stretch",
        config={"displayModeBar": False},
    )
    st.plotly_chart(chart_grid(plan["hours"]), width="stretch", config={"displayModeBar": False})

    frame = schedule_frame(plan["hours"])
    st.subheader("Hourly schedule")
    st.dataframe(paint_decision(frame), hide_index=True, width="stretch", height=480)
    st.download_button(
        "Download schedule CSV",
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name="voltsync_schedule.csv",
        mime="text/csv",
    )
    with st.expander("How the decision is made"):
        st.markdown(
            """
            Each hour the linear program splits rooftop solar between the load, the battery and the grid,
            and decides whether the battery charges or discharges. The objective is export revenue minus
            import cost minus a wear charge on every kilowatt-hour moved.

            The battery cannot finish the day emptier than it started, so a saving is not just spent inventory.
            **Store** means the hour is dominated by charging. **Use** means the battery covers the load,
            or live solar does when the battery is idle. **Sell** means energy is exported.
            Doing both charge and discharge in one hour wastes a round trip, so the optimum keeps them apart.

            Tariffs are a demo time-of-use book in AMD, not an official utility schedule.
            The annual figure repeats this single day 365 times.
            """
        )
    with st.expander("API response"):
        st.json(plan)


def main() -> None:
    base_url = st.sidebar.text_input("API", value=DEFAULT_API_URL, key="api_input")
    try:
        health = api_get(base_url, "/health")
    except ApiError as exc:
        st.sidebar.error("API offline")
        st.error(str(exc))
        st.info("Start the API from the project root: `uvicorn backend.main:app --reload --port 8000`")
        return

    solver_state = "CBC ready" if health.get("solver_available") else "CBC missing"
    st.sidebar.success(f"{health.get('service')} {health.get('version')} · {solver_state}")

    try:
        catalog = ensure_catalog(base_url)
        scenario_id = render_sidebar(catalog)
        plan = api_post(base_url, "/api/v1/plan", payload_from_state(scenario_id))
    except ApiError as exc:
        st.error(str(exc))
        return

    render_plan(plan)
    st.markdown(
        '<p class="vs-note">VoltSync VPP · GreenTech Armenia · Energy storage · synthetic Yerevan day</p>',
        unsafe_allow_html=True,
    )


main()
