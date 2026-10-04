"""VoltSync: one synthetic day, one battery, two bills."""

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

EMERALD = "#10b981"
BLUE = "#3b82f6"
PURPLE = "#a78bfa"
RED = "#f87171"
GOLD = "#fbbf24"
SLATE = "#94a3b8"

DECISION_RU = {
    "store": "Сохранить",
    "use": "Потребить",
    "sell": "Продать",
    "idle": "Пауза",
}

SCENARIO_RU = {
    "yerevan_summer": (
        "Ясный летний день, Ереван",
        "Крыша закрывает день и наполняет батарею. Вечерняя нагрузка берется из накопителя.",
    ),
    "cloudy_day": (
        "Облачный будний день",
        "Солнца мало. План докупает дешевую ночную энергию и отдает ее, когда тариф выше.",
    ),
    "evening_export_spike": (
        "Вечерний скачок цены продажи",
        "Вечером продажа дороже, чем экономия на своем потреблении. Запас уходит в сеть.",
    ),
    "pv_surplus": (
        "Большая СЭС, маленькая батарея",
        "Массив больше и нагрузки, и батареи. Полуденный излишек продается, когда накопитель полон.",
    ),
}

TARIFF_RU = {
    "standard_tou": "Тариф по времени суток",
    "export_spike": "Вечерний скачок продажи",
}

st.set_page_config(page_title="VoltSync", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """
    <style>
      .stApp { background: #0e1117; color: #e7eef8; }
      header[data-testid="stHeader"] { background: transparent; }
      #MainMenu, footer, [data-testid="stDecoration"] { display: none; }
      [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
      .vs-kicker { color: #94a3b8; font-size: 0.92rem; margin: 0 0 4px 0; }
      .vs-logo {
        font-size: 1.7rem; font-weight: 740; letter-spacing: -0.03em;
        color: #f8fafc; margin: 0;
      }
      .vs-sub { color: #cbd5e1; margin: 6px 0 0 0; font-size: 1.02rem; max-width: 46rem; }
      .vs-meta { color: #94a3b8; margin: 8px 0 0 0; font-size: 0.92rem; }
      .vs-card, .vs-stage {
        background: #131722; border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px; padding: 16px 16px 14px 16px; height: 100%;
      }
      .vs-label { color: #94a3b8; font-size: 0.86rem; }
      .vs-value {
        font-size: 1.7rem; line-height: 1.15; font-weight: 740;
        color: #f8fafc; margin: 8px 0;
      }
      .vs-card p, .vs-stage p { color: #cbd5e1; margin: 0; line-height: 1.45; }
      .vs-stage h3 { margin: 8px 0; color: #f8fafc; font-size: 1.05rem; }
      .vs-pill {
        display: inline-block; border-radius: 999px; padding: 4px 10px;
        font-weight: 700; font-size: 0.82rem;
      }
      .vs-pill-good { background: rgba(16, 185, 129, 0.16); color: #6ee7b7; }
      .vs-pill-bad { background: rgba(248, 113, 113, 0.14); color: #fecaca; }
      .vs-pill-amber { background: rgba(245, 158, 11, 0.16); color: #fcd34d; }
      .vs-pill-blue { background: rgba(59, 130, 246, 0.16); color: #bfdbfe; }
      .vs-note { color: #94a3b8; font-size: 0.9rem; line-height: 1.45; }
      .vs-bridge { width: 100%; border-collapse: collapse; margin-top: 4px; }
      .vs-bridge td { padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,0.06); color: #e2e8f0; }
      .vs-bridge td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
      .vs-bridge tr:last-child td { border-bottom: 0; font-weight: 740; color: #f8fafc; }
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
    sign = "−" if value < 0 else ""
    return f"{sign}{abs(value):,.0f} AMD".replace(",", " ")


def _signed_amd(value: int) -> str:
    if value > 0:
        return f"+{_amd(value)}"
    return _amd(value)


def _scenario_copy(scenario_id: str, fallback_title: str, fallback_text: str) -> tuple[str, str]:
    return SCENARIO_RU.get(scenario_id, (fallback_title, fallback_text))


def _gap_sentence(amount: int, actor: str, baseline: str) -> str:
    if amount > 0:
        return f"{actor} дешевле, чем {baseline}, на {_amd(amount)}."
    if amount < 0:
        return f"{actor} дороже, чем {baseline}, на {_amd(abs(amount))}."
    return f"{actor} совпадает со счетом «{baseline}»."


def _rows_for_block(hours: list[dict[str, Any]], block: dict[str, Any]) -> list[dict[str, Any]]:
    start = int(block["start_hour"])
    end = int(block["end_hour"])
    return [row for row in hours if start <= int(row["hour"]) <= end]


def _block_badge(decision: str, rows: list[dict[str, Any]]) -> str:
    if decision == "store":
        return f"{sum(float(row['charge_kwh']) for row in rows):.1f} кВт·ч"
    if decision == "sell":
        sold = sum(float(row["pv_to_grid_kwh"]) + float(row["battery_to_grid_kwh"]) for row in rows)
        return f"{sold:.1f} кВт·ч в сеть"
    if decision == "use":
        return f"{sum(float(row['battery_to_load_kwh']) for row in rows):.1f} кВт·ч зданию"
    return "без цикла"


def _block_sentence(decision: str, rows: list[dict[str, Any]]) -> str:
    charge = sum(float(row["charge_kwh"]) for row in rows)
    pv_battery = sum(float(row["pv_to_battery_kwh"]) for row in rows)
    grid_battery = sum(float(row["grid_to_battery_kwh"]) for row in rows)
    battery_load = sum(float(row["battery_to_load_kwh"]) for row in rows)
    battery_grid = sum(float(row["battery_to_grid_kwh"]) for row in rows)
    pv_grid = sum(float(row["pv_to_grid_kwh"]) for row in rows)
    pv_load = sum(float(row["pv_to_load_kwh"]) for row in rows)
    grid_load = sum(float(row["grid_to_load_kwh"]) for row in rows)
    if decision == "store":
        if pv_battery < 0.05:
            return f"В батарею уходит {charge:.1f} кВт·ч из сети."
        if grid_battery < 0.05:
            return f"В батарею уходит {charge:.1f} кВт·ч от солнца."
        return (
            f"В батарею уходит {charge:.1f} кВт·ч: {pv_battery:.1f} от солнца и "
            f"{grid_battery:.1f} из сети."
        )
    if decision == "sell":
        sold = battery_grid + pv_grid
        if battery_grid < 0.05:
            return f"В сеть уходит {sold:.1f} кВт·ч напрямую от солнца."
        if pv_grid < 0.05:
            return f"В сеть уходит {sold:.1f} кВт·ч из батареи."
        return (
            f"В сеть уходит {sold:.1f} кВт·ч: {battery_grid:.1f} из батареи и "
            f"{pv_grid:.1f} напрямую от солнца."
        )
    if decision == "use":
        if battery_load >= 0.05:
            return (
                f"Здание получает {battery_load:.1f} кВт·ч из батареи. "
                f"Живое солнце закрывает еще {pv_load:.1f} кВт·ч."
            )
        return f"Живое солнце закрывает {pv_load:.1f} кВт·ч. Батарея в этом окне не разряжается."
    return f"Батарея стоит. Здание покупает {grid_load:.1f} кВт·ч."


def _bridge_amounts(comparison: dict[str, Any], delta: int) -> list[tuple[str, int]]:
    """Signed contributions that add up to the two rounded bills."""
    amounts = [
        int(round(float(comparison["import_delta_amd"]))),
        int(round(float(comparison["export_delta_amd"]))),
        -int(round(float(comparison["wear_delta_amd"]))),
    ]
    amounts[-1] += delta - sum(amounts)
    return [
        ("Покупка у сети", amounts[0]),
        ("Продажа в сеть", amounts[1]),
        ("Износ батареи", amounts[2]),
    ]


def chart_balance(
    hours: list[dict[str, Any]],
    self_hours: list[dict[str, Any]],
    demand_response: bool,
) -> go.Figure:
    labels = [row["label"] for row in hours]
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.66, 0.34],
        vertical_spacing=0.08,
        specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["solar_kwh"] for row in hours],
            name="Солнечная выработка",
            mode="lines",
            line={"color": GOLD, "width": 2.2},
            fill="tozeroy",
            fillcolor="rgba(251, 191, 36, 0.16)",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["load_kwh"] for row in hours],
            name="Нагрузка здания",
            mode="lines",
            line={"color": PURPLE, "width": 2.4},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[row["charge_kwh"] for row in hours],
            name="Зарядка",
            marker_color=EMERALD,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[-float(row["discharge_kwh"]) for row in hours],
            name="Разрядка",
            marker_color=RED,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["soc_pct"] for row in hours],
            name="Заряд плана",
            mode="lines",
            line={"color": EMERALD, "width": 2.4},
        ),
        row=2,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["soc_pct"] for row in self_hours],
            name="Заряд самопотребления",
            mode="lines",
            line={"color": SLATE, "width": 2.0, "dash": "dash"},
        ),
        row=2,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[row["buy_price_amd"] for row in hours],
            name="Тариф покупки",
            mode="lines",
            line={"color": BLUE, "width": 2.0, "dash": "dot"},
        ),
        row=2,
        col=1,
        secondary_y=True,
    )
    if demand_response:
        fig.add_vrect(
            x0="18:00",
            x1="21:00",
            fillcolor="rgba(59, 130, 246, 0.12)",
            line_width=0,
            annotation_text="Нагрузка −40%",
            annotation_position="top left",
            annotation_font_color="#bfdbfe",
            row=1,
            col=1,
        )
    fig.update_layout(
        template="plotly_dark",
        barmode="relative",
        height=560,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#131722",
        font={"color": "#e2e8f0", "family": "Segoe UI, sans-serif"},
        legend={"orientation": "h", "y": 1.14, "x": 0},
        margin={"l": 56, "r": 56, "t": 48, "b": 40},
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="кВт·ч за час", row=1, col=1, gridcolor="rgba(255,255,255,0.06)")
    fig.update_yaxes(
        title_text="Заряд, %",
        range=[0, 100],
        row=2,
        col=1,
        secondary_y=False,
        gridcolor="rgba(255,255,255,0.06)",
    )
    fig.update_yaxes(
        title_text="Тариф, AMD/кВт·ч",
        row=2,
        col=1,
        secondary_y=True,
        gridcolor="rgba(255,255,255,0.04)",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.04)")
    return fig


def billing_frame(plan: dict[str, Any]) -> pd.DataFrame:
    wear_rate = float(plan["battery"]["degradation_amd_per_kwh"])
    rows: list[dict[str, Any]] = []
    for row in plan["hours"]:
        charge = float(row["charge_kwh"])
        discharge = float(row["discharge_kwh"])
        purchase = (float(row["grid_to_load_kwh"]) + float(row["grid_to_battery_kwh"])) * float(row["buy_price_amd"])
        sale = (float(row["pv_to_grid_kwh"]) + float(row["battery_to_grid_kwh"])) * float(row["sell_price_amd"])
        wear = wear_rate * (charge + discharge)
        rows.append(
            {
                "Час": row["label"],
                "Решение": DECISION_RU.get(str(row["decision"]), str(row["decision"])),
                "Заряд батареи, %": float(row["soc_pct"]),
                "Заряд, кВт·ч": charge,
                "В здание, кВт·ч": float(row["battery_to_load_kwh"]),
                "В сеть, кВт·ч": float(row["pv_to_grid_kwh"]) + float(row["battery_to_grid_kwh"]),
                "Покупка, AMD": purchase,
                "Продажа, AMD": sale,
                "Износ, AMD": wear,
                "Итог, AMD": purchase - sale + wear,
            }
        )
    frame = pd.DataFrame(rows)
    totals = {"Час": "Сутки", "Решение": ""}
    for column in frame.columns:
        if column in {"Час", "Решение"}:
            continue
        if column == "Заряд батареи, %":
            totals[column] = float("nan")
            continue
        totals[column] = float(frame[column].sum())
    return pd.concat([frame, pd.DataFrame([totals])], ignore_index=True)


def paint_billing(frame: pd.DataFrame) -> pd.io.formats.style.Styler:
    colors = {
        "Сохранить": "background-color: #3f2e12; color: #fde68a",
        "Потребить": "background-color: #172554; color: #dbeafe",
        "Продать": "background-color: #064e3b; color: #d1fae5",
        "Пауза": "background-color: #1e293b; color: #e2e8f0",
    }

    def _cell(value: str) -> str:
        return colors.get(value, "")

    money = ["Покупка, AMD", "Продажа, AMD", "Износ, AMD", "Итог, AMD"]
    energy = ["Заряд, кВт·ч", "В здание, кВт·ч", "В сеть, кВт·ч"]
    return (
        frame.style.map(_cell, subset=["Решение"])
        .format({column: "{:,.0f}" for column in money}, na_rep="—")
        .format({column: "{:.2f}" for column in energy}, na_rep="—")
        .format({"Заряд батареи, %": "{:.0f}"}, na_rep="—")
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


def payload_from_state(scenario_id: str) -> dict[str, Any]:
    return {
        "scenario": scenario_id,
        "demand_response_active": bool(st.session_state.demand_response),
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


def render_header(title: str) -> None:
    st.markdown(
        f"""
        <p class="vs-kicker">Синтетический день · демонстрационный тариф</p>
        <h1 class="vs-logo">VoltSync</h1>
        <p class="vs-sub">Диспетчер одной батареи на сутки: сохранить, потребить или продать.</p>
        <p class="vs-meta">{html.escape(title)}. Это не тариф ЭСА и не подключенный рынок.</p>
        """,
        unsafe_allow_html=True,
    )


def render_controls(catalog: dict[str, Any]) -> str:
    presets = catalog["scenarios"]
    day, solar, battery = st.columns([1.3, 1, 1])
    with day:
        scenario_id = st.selectbox(
            "День",
            options=[item["id"] for item in presets],
            format_func=lambda item: _scenario_copy(item, item, "")[0],
            key="scenario_id",
            on_change=_on_scenario_change,
            kwargs={"presets": presets},
        )
    with solar:
        st.slider("Мощность СЭС, кВт", 0.0, 40.0, step=0.5, key="pv_capacity_kwp")
    with battery:
        st.slider(
            "Емкость батареи, кВт·ч",
            0.0,
            80.0,
            step=0.5,
            key="capacity_kwh",
            help="Сколько энергии можно перенести на другой час.",
        )
    selected = next(item for item in presets if item["id"] == scenario_id)
    _title, description = _scenario_copy(scenario_id, selected["title"], selected["description"])
    st.caption(description)
    with st.expander("Точнее"):
        tariff_labels = {item["id"]: TARIFF_RU.get(item["id"], item["title"]) for item in catalog["tariff_profiles"]}
        st.selectbox(
            "Тариф",
            options=list(tariff_labels),
            format_func=lambda item: tariff_labels[item],
            key="tariff_profile",
            help="Демонстрационная книга цен в драмах. Вечерний тариф выше дневного и ночного.",
        )
        st.slider("Нагрузка за сутки, кВт·ч", 0.0, 120.0, step=1.0, key="daily_load_kwh")
        st.slider("Облачность", 0.0, 1.0, step=0.01, key="cloud_cover")
        st.slider("Мощность инвертора, кВт", 0.0, 40.0, step=0.5, key="power_kw")
        st.slider("Начальный заряд", 0.0, 1.0, step=0.01, key="soc_initial", help="Доля емкости на начало суток.")
        st.slider("Минимальный заряд", 0.0, 0.5, step=0.01, key="soc_min")
        st.slider("Максимальный заряд", 0.5, 1.0, step=0.01, key="soc_max")
        st.slider("Износ, AMD за кВт·ч", 0.0, 20.0, step=0.5, key="degradation_amd_per_kwh")
        st.slider("КПД заряда", 0.70, 1.0, step=0.01, key="charge_efficiency")
        st.slider("КПД разряда", 0.70, 1.0, step=0.01, key="discharge_efficiency")
        st.slider("Восход", 4.0, 9.0, step=0.1, key="sunrise_hour")
        st.slider("Закат", 16.0, 22.0, step=0.1, key="sunset_hour")
        st.number_input("Зерно погоды", min_value=0, max_value=10_000_000, step=1, key="seed")
    st.checkbox(
        "Команда сети: снизить нагрузку на 40% с 18:00 до 21:00",
        key="demand_response",
        help="Плата за снижение показана отдельно и не входит в экономию диспетчера.",
    )
    return scenario_id


def render_command(plan: dict[str, Any]) -> None:
    hours = plan["hours"]
    active = [block for block in plan["blocks"] if block["decision"] != "idle"]
    soc_at_peak = float(hours[17]["soc_pct"]) if len(hours) > 17 else 0.0
    if active:
        first = active[0]
        rows = _rows_for_block(hours, first)
        window = str(first["label"]).replace("-", "–")
        title = f"{window} · {DECISION_RU.get(first['decision'], first['decision'])}"
        text = _block_sentence(first["decision"], rows)
    else:
        title = "Батарея не диспетчируется"
        text = "Цены этих суток не окупают цикл."
    st.markdown(
        f"""
        <div class="vs-card">
          <div class="vs-label">Первое действие плана</div>
          <div class="vs-value">{html.escape(title)}</div>
          <p>{html.escape(text)} К 18:00 заряд батареи {soc_at_peak:.0f}%.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    if not active:
        return
    rows_of_blocks = [active[index : index + 3] for index in range(0, len(active), 3)]
    for group in rows_of_blocks:
        columns = st.columns(3)
        for column, block in zip(columns, group):
            rows = _rows_for_block(hours, block)
            decision = str(block["decision"])
            pill = {
                "store": "vs-pill-amber",
                "use": "vs-pill-blue",
                "sell": "vs-pill-good",
            }.get(decision, "vs-pill-amber")
            column.markdown(
                f"""
                <div class="vs-stage">
                  <div class="vs-label">{html.escape(str(block["label"]).replace("-", "–"))}</div>
                  <h3>{html.escape(DECISION_RU.get(decision, decision))}</h3>
                  <span class="vs-pill {pill}">{html.escape(_block_badge(decision, rows))}</span>
                  <p style="margin-top:12px">{html.escape(_block_sentence(decision, rows))}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


def render_money(plan: dict[str, Any]) -> None:
    comparison = plan["comparison"]
    self_bill = int(round(float(comparison["self_consumption"]["net_cost_amd"])))
    optimal_bill = int(round(float(comparison["optimized"]["net_cost_amd"])))
    no_battery = int(round(float(comparison["no_battery"]["net_cost_amd"])))
    delta = self_bill - optimal_bill
    battery_gap = no_battery - self_bill
    pill = "vs-pill-good" if delta > 0 else "vs-pill-amber" if delta == 0 else "vs-pill-bad"
    pill_text = (
        "дешевле самопотребления"
        if delta > 0
        else "тот же счет"
        if delta == 0
        else "дороже самопотребления"
    )
    left, middle, right = st.columns(3)
    left.markdown(
        f"""
        <div class="vs-card">
          <div class="vs-label">Самопотребление</div>
          <div class="vs-value">{html.escape(_amd(self_bill))}</div>
          <p>Та же батарея забирает только лишнее солнце и отдает его зданию.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    middle.markdown(
        f"""
        <div class="vs-card">
          <div class="vs-label">Разница плана</div>
          <div class="vs-value">{html.escape(_signed_amd(delta))}</div>
          <span class="vs-pill {pill}">{html.escape(pill_text)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    right.markdown(
        f"""
        <div class="vs-card">
          <div class="vs-label">Оптимальный план</div>
          <div class="vs-value">{html.escape(_amd(optimal_bill))}</div>
          <p>Заряд и разряд идут в часы с лучшей ценой. Износ уже в сумме.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bridge = _bridge_amounts(comparison, delta)
    bridge_rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{html.escape(_signed_amd(amount))}</td></tr>"
        for label, amount in bridge
    )
    bridge_rows += f"<tr><td>Итого к самопотреблению</td><td>{html.escape(_signed_amd(delta))}</td></tr>"
    import_delta = float(comparison["dispatch_import_kwh_delta"])
    co2 = float(comparison["dispatch_co2_delta_kg"])
    if import_delta > 0.05:
        carbon = (
            f"Относительно самопотребления план берет из сети больше на {import_delta:.1f} кВт·ч, "
            f"около {co2:.1f} кг CO2. Ночная зарядка дешевле, но не чище."
        )
    elif import_delta < -0.05:
        carbon = (
            f"Относительно самопотребления план берет из сети меньше на {abs(import_delta):.1f} кВт·ч, "
            f"около {abs(co2):.1f} кг CO2."
        )
    else:
        carbon = "Импорт из сети почти не меняется относительно самопотребления."
    carbon += " Коэффициент 0,21 кг/кВт·ч — иллюстрация для энергосистемы Армении, не паспорт объекта."
    st.markdown(
        f"""
        <div class="vs-card" style="margin-top:14px">
          <div class="vs-label">Из чего сложилась разница. Плюс значит, что план выгоднее.</div>
          <table class="vs-bridge">{bridge_rows}</table>
          <p class="vs-note" style="margin-top:12px">
            {html.escape(_gap_sentence(battery_gap, "Самопотребление", "объект без батареи"))}
            Емкость накопителя и перенос по часам здесь разделены.
            {html.escape("Отрицательный счет значит, что сутки принесли деньги." if self_bill < 0 or optimal_bill < 0 else "")}
            {html.escape(carbon)}
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_demand_response(plan: dict[str, Any]) -> None:
    if not plan.get("demand_response_active"):
        return
    curtailed = float(plan["demand_response_curtailed_kwh"])
    compensation = float(plan["demand_response_compensation_amd"])
    st.markdown(
        f"""
        <div class="vs-card" style="margin-top:14px">
          <div class="vs-label">Команда сети, 18:00–21:00</div>
          <p style="margin-top:8px">
            Нагрузка снижена на 40%, это {curtailed:.1f} кВт·ч.
            Демонстрационная плата за снижение: {html.escape(_amd(compensation))},
            по тарифу покупки этих часов. Оба счета на экране уже посчитаны на этой сниженной нагрузке.
            Плата в них не входит.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_details(plan: dict[str, Any]) -> None:
    balance_tab, billing_tab = st.tabs(["Энергетический баланс", "Почасовой счет"])
    with balance_tab:
        st.caption(
            "Сверху солнце, нагрузка, заряд и разряд оптимального плана. "
            "Снизу заряд батареи: сплошная линия — план, пунктир — самопотребление. "
            "Точки — тариф покупки. Модель линейная: КПД, мощность инвертора и износ уже в счете."
        )
        st.plotly_chart(
            chart_balance(plan["hours"], plan["self_consumption_hours"], bool(plan["demand_response_active"])),
            width="stretch",
            config={"displayModeBar": False},
        )
    with billing_tab:
        st.caption("Итог часа = покупка − продажа + износ. Отрицательный итог значит, что час принес деньги.")
        frame = billing_frame(plan)
        shown = paint_billing(frame)
        st.dataframe(shown, hide_index=True, width="stretch", height=520)
        table_total = float(frame.iloc[:-1]["Итог, AMD"].sum())
        bill = float(plan["comparison"]["optimized"]["net_cost_amd"])
        if abs(table_total - bill) >= 1:
            st.caption(
                f"Сумма строк {_amd(table_total)}. Счет сверху {_amd(bill)}. "
                "Расхождение — округление каждого часа."
            )


def connection_box(health: dict[str, Any] | None) -> None:
    with st.expander("Подключение"):
        if health is not None:
            solver = "солвер CBC доступен" if health.get("solver_available") else "солвер CBC не найден"
            st.caption(f"{health.get('service')} {health.get('version')} · {solver}")
        st.text_input("Адрес API", key="api_input")


def main() -> None:
    if "api_input" not in st.session_state:
        st.session_state.api_input = DEFAULT_API_URL
    if "demand_response" not in st.session_state:
        st.session_state.demand_response = False
    base_url = str(st.session_state.api_input)
    try:
        health = api_get(base_url, "/health")
    except ApiError as exc:
        st.error(str(exc))
        st.info("Запустите API из корня проекта: `uvicorn backend.main:app --reload --port 8000`")
        connection_box(None)
        return

    try:
        catalog = ensure_catalog(base_url)
    except ApiError as exc:
        st.error(str(exc))
        connection_box(health)
        return

    presets = catalog["scenarios"]
    selected = next(item for item in presets if item["id"] == st.session_state.get("scenario_id", presets[0]["id"]))
    title, _description = _scenario_copy(selected["id"], selected["title"], selected["description"])
    render_header(title)
    scenario_id = render_controls(catalog)
    try:
        plan = api_post(base_url, "/api/v1/plan", payload_from_state(scenario_id))
    except ApiError as exc:
        st.error(str(exc))
        connection_box(health)
        return

    render_command(plan)
    render_money(plan)
    render_demand_response(plan)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    render_details(plan)
    connection_box(health)


main()
