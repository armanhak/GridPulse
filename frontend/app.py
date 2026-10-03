"""VoltSync dashboard: dispatcher, seller, and buyer on one simulated day."""

from __future__ import annotations

import html
import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

DEFAULT_API_URL = os.environ.get("VOLTSYNC_API_URL", "http://localhost:8000")

AMBER = "#f5c542"
EMERALD = "#2ee6a6"
INDIGO = "#6366f1"
GRID = "#c5d4e8"

SALES_HOUR = "Час суток (00:00–23:00)"
SALES_VOLUME = "Объем сброса (кВт·ч)"
SALES_PRICE = "Цена продажи (AMD/кВт·ч)"
SALES_REVENUE = "Начислено за час (AMD)"

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
          radial-gradient(1100px 520px at 8% -10%, rgba(245, 197, 66, 0.12), transparent 55%),
          radial-gradient(900px 480px at 100% 0%, rgba(99, 102, 241, 0.16), transparent 50%),
          #0b1220;
        color: #e7eef8;
      }
      header[data-testid="stHeader"] { background: transparent; }
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
      .stTabs [data-baseweb="tab-list"] { gap: 8px; }
      .stTabs [data-baseweb="tab"] {
        background: #121a2b;
        border-radius: 12px 12px 0 0;
        color: #9aadc4;
        padding: 10px 16px;
      }
      .stTabs [aria-selected="true"] {
        color: #f4f8ff;
        border-bottom: 2px solid #2ee6a6;
      }
      .vs-hero { padding: 4px 2px 8px 2px; }
      .vs-kicker {
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #2ee6a6;
        font-size: 0.78rem;
        font-weight: 650;
        margin-bottom: 6px;
      }
      .vs-title {
        font-size: 2.05rem;
        line-height: 1.1;
        font-weight: 720;
        margin: 0;
        color: #f4f8ff;
      }
      .vs-sub { color: #9aadc4; margin-top: 6px; font-size: 1.02rem; }
      .vs-note { color: #8ea0b8; font-size: 0.86rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


class ApiError(Exception):
    """The VoltSync API could not return a plan."""


def _init_role_flags() -> None:
    if "demand_response_active" not in st.session_state:
        st.session_state.demand_response_active = False
    if "peak_shaving_active" not in st.session_state:
        st.session_state.peak_shaving_active = False


def api_get(base_url: str, path: str) -> Any:
    try:
        response = requests.get(f"{base_url.rstrip('/')}{path}", timeout=20)
    except requests.exceptions.RequestException as exc:
        raise ApiError(f"Нет связи с API по адресу {base_url}. {exc}") from exc
    if response.status_code >= 400:
        raise ApiError(_error_text(response))
    return response.json()


def api_post(base_url: str, path: str, payload: dict[str, Any]) -> Any:
    try:
        response = requests.post(f"{base_url.rstrip('/')}{path}", json=payload, timeout=30)
    except requests.exceptions.RequestException as exc:
        raise ApiError(f"Нет связи с API по адресу {base_url}. {exc}") from exc
    if response.status_code >= 400:
        raise ApiError(_error_text(response))
    return response.json()


def _error_text(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"API вернул HTTP {response.status_code}."
    detail = body.get("detail", body)
    return f"API вернул HTTP {response.status_code}: {detail}"


def _layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
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
        margin={"l": 56, "r": 28, "t": 48, "b": 42},
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zeroline=False, showline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.18)")
    return fig


def _mark_demand_response(fig: go.Figure, active: bool) -> None:
    if not active:
        return
    fig.add_vrect(
        x0="18:00",
        x1="20:00",
        fillcolor="rgba(99, 102, 241, 0.14)",
        line_width=0,
        annotation_text="DR −40%",
        annotation_position="top left",
        annotation_font_color="#c7d2fe",
    )


def chart_balance(hours: list[dict[str, Any]], demand_response: bool) -> go.Figure:
    labels = [row["label"] for row in hours]
    battery = [
        (row["battery_to_load_kwh"] + row["battery_to_grid_kwh"]) - row["charge_kwh"] for row in hours
    ]
    grid = [
        (row["grid_to_load_kwh"] + row["grid_to_battery_kwh"])
        - (row["pv_to_grid_kwh"] + row["battery_to_grid_kwh"])
        for row in hours
    ]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["solar_kwh"] for row in hours],
            name="Солнце",
            mode="lines",
            line={"color": AMBER, "width": 2.6},
            fill="tozeroy",
            fillcolor="rgba(245, 197, 66, 0.16)",
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=battery,
            name="Батарея",
            marker_color=EMERALD,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=grid,
            name="Сеть",
            mode="lines",
            line={"color": GRID, "width": 2.2, "dash": "dot"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["load_kwh"] for row in hours],
            name="Нагрузка",
            mode="lines",
            line={"color": INDIGO, "width": 2.6},
        )
    )
    fig.update_layout(barmode="overlay")
    fig.update_yaxes(title_text="кВт·ч за час")
    _mark_demand_response(fig, demand_response)
    return _layout(fig, 440)


def chart_spot_prices(hours: list[dict[str, Any]], demand_response: bool) -> go.Figure:
    labels = [row["label"] for row in hours]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["sell_price_amd"] for row in hours],
            name="Оптовая спотовая цена",
            mode="lines",
            line={"color": AMBER, "width": 2.8},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["buy_price_amd"] for row in hours],
            name="Розничный тариф",
            mode="lines",
            line={"color": INDIGO, "width": 2, "dash": "dot"},
        )
    )
    arb_x: list[str] = []
    arb_y: list[float] = []
    arb_text: list[str] = []
    for row in hours:
        if row["decision"] == "store":
            arb_x.append(row["label"])
            arb_y.append(row["buy_price_amd"])
            arb_text.append("Арбитраж: заряд")
        elif row["decision"] == "sell":
            arb_x.append(row["label"])
            arb_y.append(row["sell_price_amd"])
            arb_text.append("Арбитраж: продажа")
    fig.add_trace(
        go.Scatter(
            x=arb_x,
            y=arb_y,
            name="Точки активации арбитража",
            mode="markers",
            marker={
                "size": 12,
                "color": EMERALD,
                "symbol": "diamond",
                "line": {"width": 1, "color": "#f4f8ff"},
            },
            text=arb_text,
            hovertemplate="%{text}<br>%{x}: %{y:.0f} AMD/кВт·ч<extra></extra>",
        )
    )
    fig.add_hline(
        y=50,
        line_dash="dash",
        line_color="rgba(245, 197, 66, 0.55)",
        annotation_text="Порог пик-шейвинга 50 AMD",
        annotation_position="top left",
        annotation_font_color=AMBER,
    )
    fig.update_yaxes(title_text="AMD / кВт·ч")
    _mark_demand_response(fig, demand_response)
    return _layout(fig, 420)


def chart_soc(hours: list[dict[str, Any]], battery: dict[str, Any], demand_response: bool) -> go.Figure:
    labels = [row["label"] for row in hours]
    start_kwh = float(battery["soc_initial"]) * float(battery["capacity_kwh"])
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=["старт", *labels],
            y=[round(start_kwh, 3), *[row["soc_kwh"] for row in hours]],
            name="Заряд накопителя",
            mode="lines",
            line={"color": EMERALD, "width": 3, "shape": "hv"},
            fill="tozeroy",
            fillcolor="rgba(46, 230, 166, 0.14)",
        )
    )
    usable_min = float(battery["soc_min"]) * float(battery["capacity_kwh"])
    usable_max = float(battery["soc_max"]) * float(battery["capacity_kwh"])
    fig.add_hrect(
        y0=usable_min,
        y1=usable_max,
        fillcolor="rgba(46, 230, 166, 0.05)",
        line_width=0,
    )
    fig.update_yaxes(title_text="кВт·ч")
    _mark_demand_response(fig, demand_response)
    return _layout(fig, 380)


def chart_cumulative_revenue(sales: list[dict[str, Any]]) -> go.Figure:
    labels = [f"{int(row['hour']):02d}:00" for row in sales]
    running = 0.0
    cumulative: list[float] = []
    for row in sales:
        running += float(row["revenue_amd"])
        cumulative.append(round(running, 2))
    peak = max(cumulative) if cumulative else 0.0
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=cumulative,
            name="Накопленный доход",
            mode="lines+markers",
            line={"color": EMERALD, "width": 3},
            marker={"size": 6, "color": EMERALD},
            fill="tozeroy",
            fillcolor="rgba(46, 230, 166, 0.14)",
        )
    )
    if peak > 0 and cumulative:
        last = labels[-1]
        fig.add_trace(
            go.Scatter(
                x=[last],
                y=[cumulative[-1]],
                name="Итог суток",
                mode="markers",
                marker={"size": 14, "color": AMBER, "symbol": "diamond"},
            )
        )
    fig.update_yaxes(title_text="AMD")
    return _layout(fig, 400)


def chart_buyer_costs(costs: list[dict[str, Any]], demand_response: bool) -> go.Figure:
    labels = [f"{int(row['hour']):02d}:00" for row in costs]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[row["baseline_cost_amd"] for row in costs],
            name="До VoltSync",
            marker_color=INDIGO,
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[row["optimized_cost_amd"] for row in costs],
            name="После VoltSync",
            marker_color=EMERALD,
        )
    )
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="AMD за час")
    _mark_demand_response(fig, demand_response)
    return _layout(fig, 440)


def sales_frame(sales: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                SALES_HOUR: f"{int(row['hour']):02d}:00",
                SALES_VOLUME: row["volume_kwh"],
                SALES_PRICE: row["price_amd"],
                SALES_REVENUE: row["revenue_amd"],
            }
            for row in sales
        ]
    )


def paint_sales(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    peak = float(frame[SALES_REVENUE].max()) if not frame.empty else 0.0

    def _row(row: pd.Series) -> list[str]:
        if peak > 0 and abs(float(row[SALES_REVENUE]) - peak) < 0.011:
            return ["background-color: #14532d; color: #ecfdf5; font-weight: 650"] * len(row)
        return [""] * len(row)

    return frame.style.apply(_row, axis=1).format(
        {
            SALES_VOLUME: "{:.2f}",
            SALES_PRICE: "{:.0f}",
            SALES_REVENUE: "{:,.0f}",
        }
    )


def dispatcher_view(plan: dict[str, Any]) -> dict[str, float | str]:
    hours = plan["hours"]
    kpis = plan["kpis"]
    pool_power_kw = float(plan["site"]["pv_capacity_kwp"]) + float(plan["battery"]["max_discharge_kw"])
    green_saved_kwh = sum(float(row["pv_to_battery_kwh"]) for row in hours)
    overload_kw = max(0.0, float(kpis["baseline_max_grid_import_kw"]) - float(kpis["max_grid_import_kw"]))
    avoided_import_kwh = max(0.0, float(kpis["baseline_import_kwh"]) - float(kpis["grid_import_kwh"]))
    if overload_kw >= 0.05 or float(kpis["self_sufficiency_pct"]) >= 70.0:
        status = "Сбалансировано"
    else:
        status = "Опора на сеть"
    if plan.get("demand_response_active"):
        status = f"{status} · DR"
    if plan.get("peak_shaving_active"):
        status = f"{status} · пик-шейвинг"
    return {
        "pool_power_kw": pool_power_kw,
        "status": status,
        "green_saved_kwh": green_saved_kwh,
        "overload_kw": overload_kw,
        "avoided_import_kwh": avoided_import_kwh,
    }


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
        "demand_response_active": bool(st.session_state.demand_response_active),
        "peak_shaving_active": bool(st.session_state.peak_shaving_active),
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
    st.sidebar.markdown("### Площадка и батарея")
    presets = catalog["scenarios"]
    labels = {item["id"]: item["title"] for item in presets}
    scenario_id = st.sidebar.selectbox(
        "День",
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
        "Тариф",
        options=list(tariff_labels),
        format_func=lambda item: tariff_labels[item],
        key="tariff_profile",
    )
    st.sidebar.slider("Мощность СЭС (кВт·пик)", 0.0, 40.0, step=0.5, key="pv_capacity_kwp")
    st.sidebar.slider("Суточная нагрузка (кВт·ч)", 0.0, 120.0, step=1.0, key="daily_load_kwh")
    st.sidebar.slider("Облачность", 0.0, 1.0, step=0.01, key="cloud_cover")
    st.sidebar.slider("Ёмкость накопителя (кВт·ч)", 0.0, 80.0, step=0.5, key="capacity_kwh")
    st.sidebar.slider("Мощность инвертора (кВт)", 0.0, 40.0, step=0.5, key="power_kw")
    st.sidebar.slider("Начальный заряд", 0.0, 1.0, step=0.01, key="soc_initial")
    st.sidebar.slider("Износ (AMD за кВт·ч)", 0.0, 20.0, step=0.5, key="degradation_amd_per_kwh")
    st.sidebar.number_input("Зерно погоды", min_value=0, max_value=10_000_000, step=1, key="seed")

    with st.sidebar.expander("Пределы батареи"):
        st.slider("Минимальный SOC", 0.0, 0.5, step=0.01, key="soc_min")
        st.slider("Максимальный SOC", 0.5, 1.0, step=0.01, key="soc_max")
        st.slider("КПД заряда", 0.70, 1.0, step=0.01, key="charge_efficiency")
        st.slider("КПД разряда", 0.70, 1.0, step=0.01, key="discharge_efficiency")
        st.slider("Восход", 4.0, 9.0, step=0.1, key="sunrise_hour")
        st.slider("Закат", 16.0, 22.0, step=0.1, key="sunset_hour")
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


def _require_roles(plan: dict[str, Any]) -> bool:
    required = ("seller_revenue_amd", "buyer_hourly_costs", "seller_sales_log")
    if all(key in plan for key in required):
        return True
    st.error("API вернул план без кабинетов продавца и покупателя. Перезапустите backend.")
    return False


def render_dispatcher(plan: dict[str, Any]) -> None:
    view = dispatcher_view(plan)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Суммарная мощность пула (кВт)", f"{view['pool_power_kw']:.1f}")
    c2.metric("Общий статус балансировки", str(view["status"]))
    c3.metric("Спасено от сброса (кВт·ч)", f"{view['green_saved_kwh']:.1f}")
    c4.metric(
        "Предотвращенные потери перегрузки",
        f"{view['overload_kw']:.1f} кВт",
        f"{view['avoided_import_kwh']:.1f} кВт·ч импорта",
    )
    st.caption(
        "Спасенная зеленая энергия — солнце, принятое накопителем пула. "
        "Потери перегрузки — насколько пиковый импорт ниже дня без батареи. "
        "Батарея на графике: разряд выше нуля, заряд ниже. Сеть: импорт выше нуля, экспорт ниже."
    )

    st.subheader("Суточный баланс мощностей")
    st.plotly_chart(
        chart_balance(plan["hours"], bool(plan.get("demand_response_active"))),
        width="stretch",
        config={"displayModeBar": False},
    )
    st.subheader("Оптовые спотовые цены и арбитраж")
    st.plotly_chart(
        chart_spot_prices(plan["hours"], bool(plan.get("demand_response_active"))),
        width="stretch",
        config={"displayModeBar": False},
    )
    st.subheader("Уровень заряда накопителя пула")
    st.plotly_chart(
        chart_soc(plan["hours"], plan["battery"], bool(plan.get("demand_response_active"))),
        width="stretch",
        config={"displayModeBar": False},
    )

    st.subheader("Пульт Demand Response")
    active = bool(st.session_state.demand_response_active)
    if active:
        st.success("Команда оператора сети активна: нагрузка снижена на 40% в окне 18:00–21:00.")
    st.button(
        "Эмулировать команду оператора сети (Сброс нагрузки на 40% в вечерний пик 18:00–21:00)",
        type="primary",
        disabled=active,
        on_click=_activate_demand_response,
    )
    if active:
        st.button("Снять команду оператора", on_click=_clear_demand_response)


def _activate_demand_response() -> None:
    st.session_state.demand_response_active = True


def _clear_demand_response() -> None:
    st.session_state.demand_response_active = False


def render_seller(plan: dict[str, Any]) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Сгенерировано солнцем (кВт·ч)", f"{plan['seller_total_solar_kwh']:.1f}")
    c2.metric("Продано в сеть по высокой цене (кВт·ч)", f"{plan['seller_total_sold_kwh']:.1f}")
    c3.metric("Валовый доход (AMD)", f"{plan['seller_revenue_amd']:,.0f}")
    c4.metric("Комиссия сервиса VoltSync (15%) (AMD)", f"{plan['seller_success_fee_amd']:,.0f}")
    c5.metric("Чистая прибыль владельца (AMD)", f"{plan['seller_net_profit_amd']:,.0f}")
    wear_amd = float(plan["battery"]["degradation_amd_per_kwh"]) * sum(
        float(row["charge_kwh"]) + float(row["discharge_kwh"]) for row in plan["hours"]
    )
    grid_charge_amd = sum(
        float(row["grid_to_battery_kwh"]) * float(row["buy_price_amd"]) for row in plan["hours"]
    )
    st.caption(
        "Объем продаж — энергия солнца и накопителя, отданная в сеть и пул. "
        f"Комиссия 15% считается с дополнительной выгоды сверх пассивного сброса излишка. "
        f"Чистая прибыль = {plan['seller_revenue_amd']:,.0f} − комиссия {plan['seller_success_fee_amd']:,.0f} "
        f"− закупка в накопитель {grid_charge_amd:,.0f} − износ {wear_amd:,.0f} AMD. "
        "Зеленым отмечены часы с наибольшим начислением."
    )
    st.subheader("История продаж")
    frame = sales_frame(plan["seller_sales_log"])
    st.dataframe(paint_sales(frame), hide_index=True, width="stretch", height=480)
    st.subheader("Накопление дохода за сутки")
    st.plotly_chart(
        chart_cumulative_revenue(plan["seller_sales_log"]),
        width="stretch",
        config={"displayModeBar": False},
    )


def render_buyer(plan: dict[str, Any]) -> None:
    baseline = float(plan["buyer_baseline_cost_amd"])
    optimized = float(plan["buyer_optimized_cost_amd"])
    savings = float(plan["buyer_savings_amd"])
    savings_pct = 0.0 if baseline <= 1e-9 else 100.0 * savings / baseline
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Потреблено объектом (кВт·ч)", f"{plan['buyer_total_consumed_kwh']:.1f}")
    c2.metric("Закрыто накопителем (кВт·ч)", f"{plan['buyer_covered_by_storage_kwh']:.1f}")
    c3.metric("Счет за электричество без VoltSync (AMD)", f"{baseline:,.0f}")
    c4.metric(
        "Итоговый счет к оплате с VoltSync (AMD)",
        f"{optimized:,.0f}",
        f"{optimized - baseline:,.0f}",
        delta_color="inverse",
    )
    c5.metric("Экономия на вечернем пике (AMD)", f"{savings:,.0f}", f"{savings_pct:.0f}%")
    direct_solar = max(
        0.0,
        float(plan["buyer_total_consumed_kwh"])
        - float(plan["buyer_covered_by_storage_kwh"])
        - float(plan["buyer_grid_bought_kwh"]),
    )
    st.caption(
        f"Без VoltSync весь объем покупается по тарифу сети. С VoltSync остаток "
        f"{plan['buyer_grid_bought_kwh']:.1f} кВт·ч берется из сети, "
        f"{direct_solar:.1f} кВт·ч закрывает прямое солнце, накопитель срезает дорогой пик. "
        "Энергия пула считается по оптовой цене."
    )
    st.toggle(
        "Автоматический пик-шейвинг (Запрет потребления из сети при цене выше 50 AMD)",
        key="peak_shaving_active",
    )
    if plan.get("peak_shaving_active"):
        st.info(
            "Пик-шейвинг включен: при тарифе выше 50 AMD объект не покупает энергию из сети, "
            "пока солнце и накопитель закрывают нагрузку."
        )
    else:
        st.caption(
            "На ясном летнем дне пул и так закрывает часы дороже 50 AMD. "
            "Переключатель меняет диспетчеризацию, когда вечерняя продажа выгоднее собственного потребления "
            "(сценарий Evening export spike): нагрузка уходит с сети на накопитель."
        )
    st.subheader("Стоимость закупки: до и после")
    st.plotly_chart(
        chart_buyer_costs(plan["buyer_hourly_costs"], bool(plan.get("demand_response_active"))),
        width="stretch",
        config={"displayModeBar": False},
    )


def render_plan(plan: dict[str, Any]) -> None:
    if not _require_roles(plan):
        return
    title = html.escape(str(plan["scenario_title"]))
    solver = html.escape(str(plan["solver"]))
    st.markdown(
        f"""
        <div class="vs-hero">
          <div class="vs-kicker">VoltSync VPP · {title}</div>
          <h1 class="vs-title">Диспетчер, продавец и покупатель</h1>
          <p class="vs-sub">Один суточный план пула для трех кабинетов. Решено солвером {solver} за {plan["solve_time_ms"]:.0f} мс.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    dispatcher, seller, buyer = st.tabs(
        [
            "⚡ Диспетчер VPP (Сеть)",
            "☀️️ Кабинет Продавца (Генерация)",
            "🏢 Кабинет Покупателя (Потребление)",
        ]
    )
    with dispatcher:
        render_dispatcher(plan)
    with seller:
        render_seller(plan)
    with buyer:
        render_buyer(plan)


def main() -> None:
    _init_role_flags()
    base_url = st.sidebar.text_input("API", value=DEFAULT_API_URL, key="api_input")
    try:
        health = api_get(base_url, "/health")
    except ApiError as exc:
        st.sidebar.error("API недоступен")
        st.error(str(exc))
        st.info("Запустите API из корня проекта: `uvicorn backend.main:app --reload --port 8000`")
        return

    solver_state = "CBC готов" if health.get("solver_available") else "CBC не найден"
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
        '<p class="vs-note">VoltSync VPP · три роли одного пула · синтетический день Еревана</p>',
        unsafe_allow_html=True,
    )


main()
