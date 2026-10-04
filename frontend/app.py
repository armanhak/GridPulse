"""VoltSync: one screen that answers store, use, or sell."""

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

AMBER = "#f59e0b"
EMERALD = "#10b981"
BLUE = "#3b82f6"
PURPLE = "#a78bfa"
RED = "#f87171"
GOLD = "#fbbf24"

MODE_BASELINE = "Режим 1: Обычный объект (Без системы VoltSync)"
MODE_AI = "Режим 2: VoltSync AI (Оптимальный арбитраж)"
MODE_DR = "Режим 3: Команда энергосети (Demand Response)"
MODES = (MODE_BASELINE, MODE_AI, MODE_DR)

MORNING = range(10, 15)
EVENING = range(18, 22)
NIGHT = (23, 0, 1, 2, 3, 4, 5, 6)

st.set_page_config(
    page_title="VoltSync VPP",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .stApp { background: #0e1117; color: #e7eef8; }
      header[data-testid="stHeader"] { background: transparent; }
      #MainMenu, footer, [data-testid="stDecoration"] { display: none; }
      [data-testid="stSidebar"] {
        background: #131722;
        border-right: 1px solid rgba(255, 255, 255, 0.06);
      }
      .vs-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        margin-bottom: 8px;
      }
      .vs-logo {
        font-size: 1.7rem;
        font-weight: 740;
        letter-spacing: -0.03em;
        color: #f8fafc;
        margin: 0;
      }
      .vs-sub { color: #94a3b8; margin: 4px 0 0 0; font-size: 1.02rem; }
      .vs-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        padding: 8px 14px;
        font-weight: 680;
        font-size: 0.92rem;
        white-space: nowrap;
      }
      .vs-badge-live {
        color: #6ee7b7;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.45);
        animation: vs-pulse 1.8s ease-out infinite;
      }
      .vs-badge-off {
        color: #fecaca;
        background: rgba(248, 113, 113, 0.1);
        border: 1px solid rgba(248, 113, 113, 0.35);
      }
      @keyframes vs-pulse {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.45); }
        70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
      }
      .vs-kpi, .vs-stage, .vs-bill {
        background: #131722;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 16px 16px 14px 16px;
      }
      .vs-kpi-label, .vs-stage-time { color: #94a3b8; font-size: 0.86rem; }
      .vs-kpi-value {
        font-size: 2rem;
        line-height: 1.15;
        font-weight: 740;
        color: #f8fafc;
        margin: 8px 0 8px 0;
      }
      .vs-pill {
        display: inline-block;
        border-radius: 999px;
        padding: 4px 10px;
        font-weight: 700;
        font-size: 0.86rem;
      }
      .vs-pill-good { background: rgba(16, 185, 129, 0.16); color: #6ee7b7; }
      .vs-pill-bad { background: rgba(248, 113, 113, 0.14); color: #fecaca; }
      .vs-pill-amber { background: rgba(245, 158, 11, 0.16); color: #fcd34d; }
      .vs-stage h3 { margin: 8px 0; color: #f8fafc; font-size: 1.15rem; }
      .vs-stage p { color: #cbd5e1; margin: 0; line-height: 1.45; }
      .vs-term { border-bottom: 1px dashed rgba(148, 163, 184, 0.7); cursor: help; }
      div[data-testid="stRadio"] div[role="radiogroup"] { gap: 8px; }
      div[data-testid="stRadio"] label {
        background: #131722;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 8px 12px;
      }
      .vs-bills { display: flex; gap: 16px; margin: 8px 0 16px 0; }
      .vs-bill b { display: block; font-size: 1.6rem; color: #f8fafc; margin-top: 4px; }
      .vs-note { color: #94a3b8; font-size: 0.88rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


class ApiError(Exception):
    """The VoltSync API could not return a plan."""


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


def _amd(value: float) -> str:
    return f"{value:,.0f} AMD"


def _window(hours: list[dict[str, Any]], hours_of_day: range | tuple[int, ...]) -> list[dict[str, Any]]:
    chosen = set(hours_of_day)
    return [row for row in hours if int(row["hour"]) in chosen]


def _avg_price(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return sum(float(row[key]) for row in rows) / len(rows)


def _money_story(plan: dict[str, Any], managed: bool) -> dict[str, float]:
    hours = plan["hours"]
    kpis = plan["kpis"]
    evening = _window(hours, EVENING)
    peak_saved = sum(
        max(0.0, float(row["baseline_import_kwh"]) - float(row["grid_to_load_kwh"]) - float(row["grid_to_battery_kwh"]))
        * float(row["buy_price_amd"])
        for row in evening
    )
    peak_paid = sum(float(row["baseline_import_kwh"]) * float(row["buy_price_amd"]) for row in evening)
    export_revenue = sum(
        (float(row["pv_to_grid_kwh"]) + float(row["battery_to_grid_kwh"])) * float(row["sell_price_amd"])
        for row in hours
    )
    cheap_export = sum(float(row["baseline_export_kwh"]) * float(row["sell_price_amd"]) for row in hours)
    stored = sum(float(row["pv_to_battery_kwh"]) for row in hours)
    return {
        "savings_amd": float(kpis["savings_amd"]) if managed else 0.0,
        "savings_pct": float(kpis["savings_pct"]) if managed else 0.0,
        "peak_amd": peak_saved if managed else peak_paid,
        "sales_amd": export_revenue if managed else cheap_export,
        "saved_kwh": stored if managed else 0.0,
        "bill_without": float(kpis["baseline_net_cost_amd"]),
        "bill_with": float(kpis["optimized_net_cost_amd"]),
    }


def _stage_copy(plan: dict[str, Any], mode: str) -> list[dict[str, str]]:
    hours = plan["hours"]
    morning = _window(hours, MORNING)
    evening = _window(hours, EVENING)
    night = _window(hours, NIGHT)
    midday_sell = _avg_price(morning, "sell_price_amd")
    peak_buy = _avg_price(evening, "buy_price_amd")
    night_buy = _avg_price(night, "buy_price_amd")
    morning_charge = sum(float(row["charge_kwh"]) for row in morning)
    if mode == MODE_BASELINE:
        morning_export = sum(float(row["baseline_export_kwh"]) for row in morning)
    else:
        morning_export = sum(float(row["pv_to_grid_kwh"]) + float(row["battery_to_grid_kwh"]) for row in morning)
    evening_to_load = sum(float(row["battery_to_load_kwh"]) for row in evening)
    evening_to_grid = sum(float(row["battery_to_grid_kwh"]) for row in evening)
    night_charge = sum(float(row["charge_kwh"]) for row in night)
    night_load = sum(float(row["load_kwh"]) for row in night)
    soc_hint = max((float(row["soc_pct"]) for row in morning), default=0.0)
    bess = '<span class="vs-term" title="BESS — батарея, которая переносит энергию из дешевого часа в дорогой">BESS</span>'
    soc = '<span class="vs-term" title="SoC — уровень заряда батареи, доля от ее емкости">SoC</span>'
    arb = '<span class="vs-term" title="Арбитраж — сохранить дешевую энергию и использовать или продать ее, когда тариф выше">арбитраж</span>'

    if mode == MODE_BASELINE:
        return [
            {
                "time": "Утро и полдень · 10:00–15:00",
                "title": "☀️ Излишек уходит задешево",
                "badge": "Нет зарядки",
                "badge_class": "vs-pill-bad",
                "text": (
                    f"Солнце есть, батарея простаивает. {morning_export:.1f} кВт·ч в этом окне "
                    f"ушли бы в сеть примерно по {midday_sell:.0f} AMD/кВт·ч."
                ),
            },
            {
                "time": "Вечерний пик · 18:00–22:00",
                "title": "⚡ Покупка по пиковому тарифу",
                "badge": "Переплата",
                "badge_class": "vs-pill-bad",
                "text": (
                    f"Здание покупает вечернюю нагрузку у сети около {peak_buy:.0f} AMD/кВт·ч. "
                    "Сгладить пик нечем."
                ),
            },
            {
                "time": "Ночь · 23:00–07:00",
                "title": "🌙 Дешевый час не используется",
                "badge": "Простой",
                "badge_class": "vs-pill-amber",
                "text": (
                    f"Ночная энергия стоит около {night_buy:.0f} AMD/кВт·ч, нагрузка {night_load:.1f} кВт·ч. "
                    "Запас на утро не создается."
                ),
            },
        ]
    dr = mode == MODE_DR
    evening_title = "⚡ USE и SELL под команду сети" if dr else "⚡ USE и SELL"
    evening_text = (
        f"Пиковый тариф около {peak_buy:.0f} AMD/кВт·ч. Батарея отдает зданию {evening_to_load:.1f} кВт·ч "
        f"и продает в сеть {evening_to_grid:.1f} кВт·ч."
    )
    if dr:
        evening_text += " Оператор срезал 40% нагрузки в 18:00–21:00, остаток закрывает накопитель."
    return [
        {
            "time": "Утро и полдень · 10:00–15:00",
            "title": "☀️ STORE",
            "badge": "Зарядка батареи",
            "badge_class": "vs-pill-amber",
            "text": (
                f"Солнце на пике. В {bess} уходит {morning_charge:.1f} кВт·ч вместо продажи всего излишка "
                f"по {midday_sell:.0f} AMD. Прямой сброс в этом окне: {morning_export:.1f} кВт·ч. "
                f"{soc} в окне доходит до {soc_hint:.0f}%."
            ),
        },
        {
            "time": "Вечерний пик сети · 18:00–22:00",
            "title": evening_title,
            "badge": "Максимальная выгода",
            "badge_class": "vs-pill-good",
            "text": evening_text,
        },
        {
            "time": "Ночь · 23:00–07:00",
            "title": "🌙 STANDBY / дешевый заряд",
            "badge": "Эко-режим",
            "badge_class": "vs-pill-good",
            "text": (
                f"Нагрузка {night_load:.1f} кВт·ч. Ночная энергия около {night_buy:.0f} AMD. "
                f"Батарея берет ее только под {arb}: {night_charge:.1f} кВт·ч."
            ),
        },
    ]


def chart_balance(hours: list[dict[str, Any]], managed: bool, demand_response: bool) -> go.Figure:
    labels = [row["label"] for row in hours]
    charge = [float(row["charge_kwh"]) if managed else 0.0 for row in hours]
    discharge = [float(row["discharge_kwh"]) if managed else 0.0 for row in hours]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["solar_kwh"] for row in hours],
            name="Солнечная выработка",
            mode="lines",
            line={"color": GOLD, "width": 2.4},
            fill="tozeroy",
            fillcolor="rgba(251, 191, 36, 0.18)",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["load_kwh"] for row in hours],
            name="Нагрузка здания",
            mode="lines",
            line={"color": PURPLE, "width": 2.6},
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(x=labels, y=charge, name="Зарядка накопителя", marker_color=EMERALD),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(x=labels, y=[-value for value in discharge], name="Разрядка", marker_color=RED),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["buy_price_amd"] for row in hours],
            name="Тариф сети",
            mode="lines",
            line={"color": BLUE, "width": 2.2, "dash": "dot"},
        ),
        secondary_y=True,
    )
    if demand_response:
        fig.add_vrect(
            x0="18:00",
            x1="20:00",
            fillcolor="rgba(59, 130, 246, 0.12)",
            line_width=0,
            annotation_text="Команда сети −40%",
            annotation_font_color="#bfdbfe",
        )
    fig.update_layout(
        template="plotly_dark",
        barmode="relative",
        height=460,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#131722",
        font={"color": "#e2e8f0", "family": "Segoe UI, sans-serif"},
        legend={"orientation": "h", "y": 1.12, "x": 0},
        margin={"l": 56, "r": 56, "t": 48, "b": 40},
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="кВт·ч за час", secondary_y=False, gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(title_text="Тариф, AMD/кВт·ч", secondary_y=True, gridcolor="rgba(255,255,255,0.04)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.04)")
    return fig


def _row_mode(row: dict[str, Any], managed: bool) -> str:
    if not managed:
        if float(row["baseline_export_kwh"]) > float(row["baseline_import_kwh"]):
            return "SELL"
        return "USE"
    decision = str(row["decision"])
    if decision == "idle":
        return "STANDBY"
    return decision.upper()


def _row_volume(row: dict[str, Any], managed: bool) -> float:
    if not managed:
        return max(float(row["baseline_export_kwh"]), float(row["baseline_import_kwh"]))
    decision = row["decision"]
    if decision == "store":
        return float(row["charge_kwh"])
    if decision == "sell":
        return float(row["pv_to_grid_kwh"]) + float(row["battery_to_grid_kwh"])
    if decision == "use":
        return float(row["battery_to_load_kwh"]) + float(row["pv_to_load_kwh"])
    return float(row["grid_to_load_kwh"])


def _row_tariff(row: dict[str, Any], mode_name: str) -> float:
    if mode_name == "SELL":
        return float(row["sell_price_amd"])
    return float(row["buy_price_amd"])


def billing_frame(hours: list[dict[str, Any]], managed: bool) -> pd.DataFrame:
    rows = []
    for row in hours:
        mode_name = _row_mode(row, managed)
        total = float(row["net_cost_amd"] if managed else row["baseline_net_cost_amd"])
        rows.append(
            {
                "Час": row["label"],
                "Режим (STORE / USE / SELL)": mode_name,
                "Объем (кВт·ч)": round(_row_volume(row, managed), 2),
                "Тариф (AMD)": round(_row_tariff(row, mode_name), 0),
                "Итог (AMD)": round(total, 0),
            }
        )
    return pd.DataFrame(rows)


def paint_billing(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    colors = {
        "STORE": "background-color: #3f2e12; color: #fde68a",
        "USE": "background-color: #172554; color: #dbeafe",
        "SELL": "background-color: #064e3b; color: #d1fae5",
        "STANDBY": "background-color: #1e293b; color: #e2e8f0",
    }
    column = "Режим (STORE / USE / SELL)"

    def _cell(value: str) -> str:
        return colors.get(value, "")

    return frame.style.map(_cell, subset=[column]).format(
        {
            "Объем (кВт·ч)": "{:.2f}",
            "Тариф (AMD)": "{:.0f}",
            "Итог (AMD)": "{:,.0f}",
        }
    )


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


def payload_from_state(scenario_id: str, mode: str) -> dict[str, Any]:
    return {
        "scenario": scenario_id,
        "demand_response_active": mode == MODE_DR,
        "peak_shaving_active": False,
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
    st.sidebar.markdown("### Объект")
    st.sidebar.caption("Параметры дня. Основной экран от них не зависит по структуре.")
    presets = catalog["scenarios"]
    labels = {item["id"]: item["title"] for item in presets}
    scenario_id = st.sidebar.selectbox(
        "День",
        options=[item["id"] for item in presets],
        format_func=lambda item: labels[item],
        key="scenario_id",
        on_change=_on_scenario_change,
        kwargs={"presets": presets},
        help="Готовый сутки Еревана: солнце, нагрузка здания и тариф.",
    )
    selected = next(item for item in presets if item["id"] == scenario_id)
    st.sidebar.caption(selected["description"])
    tariff_labels = {item["id"]: item["title"] for item in catalog["tariff_profiles"]}
    st.sidebar.selectbox(
        "Тариф",
        options=list(tariff_labels),
        format_func=lambda item: tariff_labels[item],
        key="tariff_profile",
        help="Книга цен в AMD. Вечерний тариф выше дневного и ночного.",
    )
    st.sidebar.slider("Мощность СЭС, кВт·пик", 0.0, 40.0, step=0.5, key="pv_capacity_kwp")
    st.sidebar.slider("Нагрузка за сутки, кВт·ч", 0.0, 120.0, step=1.0, key="daily_load_kwh")
    st.sidebar.slider("Облачность", 0.0, 1.0, step=0.01, key="cloud_cover")
    st.sidebar.slider(
        "Емкость батареи, кВт·ч",
        0.0,
        80.0,
        step=0.5,
        key="capacity_kwh",
        help="BESS — накопитель. Емкость задает, сколько энергии можно перенести на вечер.",
    )
    st.sidebar.slider("Мощность инвертора, кВт", 0.0, 40.0, step=0.5, key="power_kw")
    with st.sidebar.expander("Точнее"):
        st.slider(
            "Начальный заряд",
            0.0,
            1.0,
            step=0.01,
            key="soc_initial",
            help="SoC — доля заполнения батареи на начало суток.",
        )
        st.slider("Минимальный заряд", 0.0, 0.5, step=0.01, key="soc_min")
        st.slider("Максимальный заряд", 0.5, 1.0, step=0.01, key="soc_max")
        st.slider("Износ, AMD за кВт·ч", 0.0, 20.0, step=0.5, key="degradation_amd_per_kwh")
        st.number_input("Зерно погоды", min_value=0, max_value=10_000_000, step=1, key="seed")
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


def render_hero(mode: str) -> None:
    if mode == MODE_BASELINE:
        badge = '<div class="vs-badge vs-badge-off">Алгоритм выключен | Объект покупает сеть как получится</div>'
    else:
        badge = '<div class="vs-badge vs-badge-live">🟢 Алгоритм активен | Оптовый рынок AEX подключен</div>'
    st.markdown(
        f"""
        <div class="vs-top">
          <div>
            <h1 class="vs-logo">VoltSync VPP</h1>
            <p class="vs-sub">Интеллектуальный энергомозг: Store, Use or Sell</p>
          </div>
          {badge}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(story: dict[str, float], mode: str) -> None:
    managed = mode != MODE_BASELINE
    if not managed:
        savings_value = "0%"
    elif abs(story["savings_pct"]) < 0.05:
        savings_value = _amd(story["savings_amd"])
    else:
        savings_value = f"{story['savings_pct']:+.1f}%"
    cards = [
        (
            "Итоговая экономия",
            savings_value,
            "переплата за день" if not managed else "выгода к счету без системы",
            _amd(story["bill_without"] if not managed else story["savings_amd"]),
            "vs-pill-bad" if not managed else "vs-pill-good",
        ),
        (
            "Сэкономлено на пиковом тарифе" if managed else "Оплачено по пиковому тарифу",
            _amd(story["peak_amd"]),
            "вечернее окно 18:00–22:00",
            "батарея закрыла дорогие часы" if managed else "покупка пика напрямую у сети",
            "vs-pill-good" if managed else "vs-pill-bad",
        ),
        (
            "Заработано на продаже излишков",
            _amd(story["sales_amd"]),
            "энергия, отданная в сеть",
            "продажа в выгодный час" if managed else "сброс по низкой цене",
            "vs-pill-good" if managed else "vs-pill-amber",
        ),
        (
            "Спасено чистой энергии",
            f"{story['saved_kwh']:.1f} кВт·ч",
            "солнце, принятое батареей",
            "иначе ушло бы за гроши" if managed else "без системы этот объем не сохраняется",
            "vs-pill-good" if managed else "vs-pill-bad",
        ),
    ]
    columns = st.columns(4)
    for column, (label, value, note, pill, pill_class) in zip(columns, cards, strict=True):
        column.markdown(
            f"""
            <div class="vs-kpi">
              <div class="vs-kpi-label">{html.escape(label)}</div>
              <div class="vs-kpi-value">{html.escape(value)}</div>
              <div class="vs-note">{html.escape(note)}</div>
              <div style="margin-top:10px"><span class="vs-pill {pill_class}">{html.escape(pill)}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_stages(plan: dict[str, Any], mode: str) -> None:
    st.markdown("### Что делать с энергией в течение дня")
    columns = st.columns(3)
    for column, stage in zip(columns, _stage_copy(plan, mode), strict=True):
        column.markdown(
            f"""
            <div class="vs-stage">
              <div class="vs-stage-time">{html.escape(stage["time"])}</div>
              <h3>{html.escape(stage["title"])}</h3>
              <span class="vs-pill {stage["badge_class"]}">{html.escape(stage["badge"])}</span>
              <p style="margin-top:12px">{stage["text"]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_details(plan: dict[str, Any], mode: str, story: dict[str, float]) -> None:
    managed = mode != MODE_BASELINE
    balance_tab, billing_tab = st.tabs(
        ["📊 Энергетический баланс (24H)", "💰 Прозрачный биллинг и транзакции"]
    )
    with balance_tab:
        st.caption(
            "Золото — солнце. Фиолетовая линия — нагрузка здания. "
            "Зеленые столбцы — зарядка. Красные — разрядка на здание и в сеть. "
            "Синяя линия справа — тариф, он совпадает с разрядкой в пике."
        )
        st.plotly_chart(
            chart_balance(plan["hours"], managed, mode == MODE_DR),
            width="stretch",
            config={"displayModeBar": False},
        )
    with billing_tab:
        without = story["bill_without"]
        with_sync = story["bill_with"]
        st.markdown(
            f"""
            <div class="vs-bills">
              <div class="vs-bill">Без VoltSync<b>{html.escape(_amd(without))}</b></div>
              <div class="vs-bill">С VoltSync<b>{html.escape(_amd(with_sync))}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Отрицательный итог в таблице — час принес деньги. Положительный — час стоил денег.")
        frame = billing_frame(plan["hours"], managed)
        st.dataframe(paint_billing(frame), hide_index=True, width="stretch", height=480)


def main() -> None:
    base_url = st.sidebar.text_input("API", value=DEFAULT_API_URL, key="api_input")
    try:
        health = api_get(base_url, "/health")
    except ApiError as exc:
        st.sidebar.error("API недоступен")
        st.error(str(exc))
        st.info("Запустите API из корня проекта: `uvicorn backend.main:app --reload --port 8000`")
        return

    solver_state = "CBC готов" if health.get("solver_available") else "CBC не найден"
    st.sidebar.caption(f"{health.get('service')} {health.get('version')} · {solver_state}")

    try:
        catalog = ensure_catalog(base_url)
        scenario_id = render_sidebar(catalog)
    except ApiError as exc:
        st.error(str(exc))
        return

    if "view_mode" not in st.session_state:
        st.session_state.view_mode = MODE_AI
    render_hero(st.session_state.view_mode)
    mode = st.radio(
        "Сценарий",
        options=list(MODES),
        horizontal=True,
        label_visibility="collapsed",
        key="view_mode",
        help="Арбитраж — сохранить энергию дешево и использовать или продать ее дорого. BESS — батарея. SoC — ее уровень заряда.",
    )

    try:
        plan = api_post(base_url, "/api/v1/plan", payload_from_state(scenario_id, mode))
    except ApiError as exc:
        st.error(str(exc))
        return

    story = _money_story(plan, mode != MODE_BASELINE)
    render_kpis(story, mode)
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    render_stages(plan, mode)
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    render_details(plan, mode, story)


main()
