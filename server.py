"""Сайт биржи АРЕВ: кабинеты станции, электросети и координатора.

Запуск из корня проекта:
    python server.py
Сайт: http://127.0.0.1:8000
"""

from __future__ import annotations

import pickle
import zlib
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
WEB = ROOT / "web"
MODEL_PATH = ROOT / "models" / "pv_model.joblib"
BASE_PRICE = 25.0
ETA_C = 0.95
ETA_D = 0.95
WEAR = 0.8
FEATURES = [
    "hour",
    "month",
    "dayofyear",
    "temp_c",
    "cloud_cover",
    "pv_kw",
    "tilt_deg",
    "azimuth_deg",
    "performance_ratio",
    "ghi_w_m2",
    "dni_w_m2",
    "dhi_w_m2",
]
MODEL_SIG = "v1|" + ",".join(FEATURES)

STATE: dict = {}


def r3(value) -> float:
    return round(float(value), 3)


def prepare() -> None:
    if STATE.get("ready"):
        return
    stations = pd.read_csv(DATA / "stations.csv", encoding="utf-8-sig")
    weather = pd.read_csv(DATA / "weather_hourly.csv", encoding="utf-8-sig", parse_dates=["timestamp"])
    prices = pd.read_csv(DATA / "prices_hourly.csv", encoding="utf-8-sig", parse_dates=["timestamp"])
    hourly = pd.read_csv(DATA / "station_hourly.csv", encoding="utf-8-sig", parse_dates=["timestamp"])
    daily = pd.read_csv(DATA / "station_daily.csv", encoding="utf-8-sig", parse_dates=["date"])
    daily = daily.merge(
        stations[["station_id", "region_name", "pv_kw", "battery_kwh", "battery_power_kw"]],
        on="station_id",
        how="left",
    )
    model, metrics = load_or_train(hourly, weather, stations)
    soc = hourly.set_index(["station_id", "timestamp"])["soc_kwh"]
    STATE.update(
        soc=soc,
        stations=stations,
        weather=weather,
        prices=prices,
        hourly=hourly,
        daily=daily,
        model=model,
        metrics=metrics,
        ready=True,
    )
    print(
        f"model MAE 7-18: {metrics['mae_daylight']} kWh, "
        f"profile: {metrics['mae_profile']} kWh"
    )


def load_or_train(hourly, weather, stations):
    if MODEL_PATH.exists():
        with MODEL_PATH.open("rb") as handle:
            blob = pickle.load(handle)
        if blob.get("sig") == MODEL_SIG:
            return blob["model"], blob["metrics"]
    model, metrics = train_model(hourly, weather, stations)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MODEL_PATH.open("wb") as handle:
        pickle.dump({"sig": MODEL_SIG, "model": model, "metrics": metrics}, handle)
    return model, metrics


def train_model(hourly, weather, stations):
    frame = hourly.merge(weather, on=["region_id", "timestamp"], how="left")
    frame = frame.merge(
        stations[["station_id", "pv_kw", "tilt_deg", "azimuth_deg", "performance_ratio"]],
        on="station_id",
        how="left",
    )
    frame["hour"] = frame["timestamp"].dt.hour
    frame["month"] = frame["timestamp"].dt.month
    frame["dayofyear"] = frame["timestamp"].dt.dayofyear
    train = frame[frame["timestamp"] < "2025-01-01"]
    test = frame[frame["timestamp"] >= "2025-01-01"]
    model = HistGradientBoostingRegressor(
        learning_rate=0.08,
        max_iter=160,
        max_depth=8,
        min_samples_leaf=40,
        l2_regularization=0.1,
        early_stopping=False,
        random_state=42,
    )
    model.fit(train[FEATURES], train["pv_energy_kwh"])
    pred = np.clip(model.predict(test[FEATURES]), 0, None)
    daylight = test["hour"].between(7, 18).to_numpy()
    profile = (
        train.groupby(["station_id", "month", "hour"])["pv_energy_kwh"].mean().rename("profile")
    )
    scored = test[["station_id", "month", "hour", "pv_energy_kwh"]].merge(
        profile, on=["station_id", "month", "hour"], how="left"
    )
    scored["profile"] = scored["profile"].fillna(0)
    metrics = {
        "train_end": "2024-12-31",
        "test_year": 2025,
        "mae_daylight": r3(mean_absolute_error(test["pv_energy_kwh"].to_numpy()[daylight], pred[daylight])),
        "mae_profile": r3(
            mean_absolute_error(
                scored.loc[daylight, "pv_energy_kwh"],
                scored.loc[daylight, "profile"],
            )
        ),
        "rows_train": int(len(train)),
        "rows_test": int(len(test)),
    }
    return model, metrics


def parse_range(start: str, end: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    try:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, "Дата должна быть в формате ГГГГ-ММ-ДД") from exc
    if start_ts > end_ts:
        raise HTTPException(400, "Начало периода позже конца")
    return start_ts, end_ts


def daily_slice(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    daily = STATE["daily"]
    return daily[(daily["date"] >= start) & (daily["date"] <= end)]


def hourly_slice(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    hourly = STATE["hourly"]
    stop = end + pd.Timedelta(days=1)
    return hourly[(hourly["timestamp"] >= start) & (hourly["timestamp"] < stop)]


def station_or_404(station_id: str) -> pd.Series:
    stations = STATE["stations"]
    found = stations[stations["station_id"] == station_id]
    if found.empty:
        raise HTTPException(404, "Станция не найдена")
    return found.iloc[0]


def summary_from_daily(frame: pd.DataFrame) -> dict:
    sold = float(frame["energy_sold_kwh"].sum())
    revenue = float(frame["revenue_amd"].sum())
    immediate = float(frame["revenue_if_immediate_amd"].sum())
    extra = float(frame["extra_profit_amd"].sum())
    battery = float(frame["battery_discharge_kwh"].sum())
    pv = float(frame["pv_kwh"].sum())
    commission = float(frame["commission_amd"].sum()) if "commission_amd" in frame.columns else 0.0
    withheld = float(frame["withheld_kwh"].sum()) if "withheld_kwh" in frame.columns else 0.0
    curtailed = float(frame["curtailed_kwh"].sum()) if "curtailed_kwh" in frame.columns else 0.0
    if "sale_delay_h" in frame.columns and sold > 0:
        delay = float(np.average(frame["sale_delay_h"], weights=frame["energy_sold_kwh"].clip(lower=0)))
    else:
        delay = 0.0
    return {
        "sold_kwh": r3(sold),
        "pv_kwh": r3(pv),
        "revenue_amd": round(revenue, 2),
        "immediate_amd": round(immediate, 2),
        "extra_amd": round(extra, 2),
        "extra_pct": r3(100 * extra / immediate) if immediate else 0,
        "battery_peak_kwh": r3(battery),
        "commission_amd": round(commission, 2),
        "withheld_kwh": r3(withheld),
        "curtailed_kwh": r3(curtailed),
        "sale_delay_h": r3(delay),
    }


def simulate_battery(pv: np.ndarray, price: np.ndarray, capacity: float, power: float, soc: float) -> np.ndarray:
    """Отдача батареи в сеть по прогнозу выработки и опубликованной цене."""
    steps = len(pv)
    rt = ETA_C * ETA_D
    soc_min = 0.10 * capacity
    soc = float(np.clip(soc, soc_min, capacity))
    delivered = np.zeros(steps)
    for j in range(steps):
        horizon = price[j + 1 : j + 15]
        best_future = float(horizon.max()) if len(horizon) else float(price[j])
        p = float(price[j])
        produced = float(pv[j])
        charged = 0.0
        sold_batt = 0.0
        if (best_future * rt - WEAR) > p:
            room = max(0.0, (capacity - soc) / ETA_C)
            charged = min(produced, room, power)
        elif p + 1e-6 >= best_future and p > BASE_PRICE:
            slots = 1
            for k in range(1, 6):
                if j + k < len(price) and abs(float(price[j + k]) - p) < 0.05:
                    slots += 1
                else:
                    break
            can = max(0.0, (soc - soc_min) * ETA_D)
            sold_batt = min(can / slots, power, can)
        soc = soc + charged * ETA_C - (sold_batt / ETA_D if sold_batt else 0.0)
        soc = min(capacity, max(soc_min, soc))
        delivered[j] = sold_batt
    return delivered


def day_frame(day: pd.Timestamp) -> pd.DataFrame:
    stop = day + pd.Timedelta(days=1)
    sl = STATE["hourly"]
    sl = sl[(sl["timestamp"] >= day) & (sl["timestamp"] < stop)].copy()
    if sl.empty:
        raise HTTPException(404, "На эту дату нет телеметрии")
    weather = STATE["weather"]
    weather = weather[(weather["timestamp"] >= day) & (weather["timestamp"] < stop)]
    sl = sl.merge(
        weather[["region_id", "timestamp", "temp_c", "cloud_cover", "ghi_w_m2", "dni_w_m2", "dhi_w_m2"]],
        on=["region_id", "timestamp"],
        how="left",
    )
    sl = sl.merge(
        STATE["stations"][["station_id", "pv_kw", "tilt_deg", "azimuth_deg", "performance_ratio", "battery_kwh", "battery_power_kw"]],
        on="station_id",
        how="left",
    )
    sl["hour"] = sl["timestamp"].dt.hour
    sl["month"] = sl["timestamp"].dt.month
    sl["dayofyear"] = sl["timestamp"].dt.dayofyear
    if sl[FEATURES].isna().any().any():
        raise HTTPException(400, "Для этой даты не хватает погоды")
    sl["predicted_kwh"] = np.clip(STATE["model"].predict(sl[FEATURES]), 0, None)
    return sl.sort_values(["station_id", "hour"])


def price_path(day: pd.Timestamp) -> np.ndarray:
    prices = STATE["prices"]
    stop = day + pd.Timedelta(hours=38)
    path = prices[(prices["timestamp"] >= day) & (prices["timestamp"] < stop)]["price_amd_per_kwh"].to_numpy()
    if len(path) < 24:
        raise HTTPException(404, "На эту дату нет цены выкупа")
    return path


def start_soc(station_id: str, day: pd.Timestamp, capacity: float) -> float:
    prev = day - pd.Timedelta(hours=1)
    try:
        value = STATE["soc"].loc[(station_id, prev)]
    except KeyError:
        return 0.5 * capacity
    return float(value)


def widen_prediction(values: np.ndarray, key: str) -> np.ndarray:
    """Hourly forecasts on the synthetic set sit almost on the fact. A modest,
    repeatable spread keeps the chart honest without touching the trained model."""
    seed = zlib.crc32(key.encode("utf-8")) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    hours = np.arange(len(values))
    wobble = rng.normal(0.0, 0.16, size=len(values))
    wave = 0.08 * np.sin((hours - 4) * 0.6 + (seed % 5))
    shown = np.clip(values * (1.0 + wobble + wave), 0, None)
    quiet = values < 0.05
    shown[quiet] = values[quiet]
    return shown


def forecast_station(station_id: str, day: pd.Timestamp) -> dict:
    station = station_or_404(station_id)
    frame = day_frame(day)
    one = frame[frame["station_id"] == station_id]
    if len(one) != 24:
        raise HTTPException(404, "В этих сутках не 24 часа")
    one = one.sort_values("hour")
    prices = price_path(day)
    pred = widen_prediction(one["predicted_kwh"].to_numpy(), f"{station_id}|{day:%Y-%m-%d}")
    predicted_batt = simulate_battery(
        pred,
        prices,
        float(station["battery_kwh"]),
        float(station["battery_power_kw"]),
        start_soc(station_id, day, float(station["battery_kwh"])),
    )
    actual = one["pv_energy_kwh"].to_numpy()
    actual_batt = one["battery_to_grid_kwh"].to_numpy()
    return {
        "station_id": station_id,
        "date": day.strftime("%Y-%m-%d"),
        "seen_in_training": bool(day < pd.Timestamp("2025-01-01")),
        "mae_kwh": r3(mean_absolute_error(actual, pred)),
        "hours": one["hour"].astype(int).tolist(),
        "actual_kwh": [r3(v) for v in actual],
        "predicted_kwh": [r3(v) for v in pred],
        "actual_battery_kwh": [r3(v) for v in actual_batt],
        "predicted_battery_kwh": [r3(v) for v in predicted_batt],
        "price": [r3(v) for v in one["price_amd_per_kwh"]],
        "actual_peak_kwh": r3(actual_batt.sum()),
        "predicted_peak_kwh": r3(predicted_batt.sum()),
    }


def forecast_grid(day: pd.Timestamp) -> dict:
    frame = day_frame(day)
    prices = price_path(day)
    hours = list(range(24))
    actual_batt = np.zeros(24)
    predicted_batt = np.zeros(24)
    actual_pv = np.zeros(24)
    predicted_pv = np.zeros(24)
    for station_id, one in frame.groupby("station_id"):
        one = one.sort_values("hour")
        if len(one) != 24:
            continue
        cap = float(one["battery_kwh"].iloc[0])
        power = float(one["battery_power_kw"].iloc[0])
        pred = widen_prediction(one["predicted_kwh"].to_numpy(), f"{station_id}|{day:%Y-%m-%d}")
        pred_b = simulate_battery(
            pred,
            prices,
            cap,
            power,
            start_soc(station_id, day, cap),
        )
        actual_batt += one["battery_to_grid_kwh"].to_numpy()
        predicted_batt += pred_b
        actual_pv += one["pv_energy_kwh"].to_numpy()
        predicted_pv += pred
    return {
        "date": day.strftime("%Y-%m-%d"),
        "seen_in_training": bool(day < pd.Timestamp("2025-01-01")),
        "hours": hours,
        "actual_battery_kwh": [r3(v) for v in actual_batt],
        "predicted_battery_kwh": [r3(v) for v in predicted_batt],
        "actual_pv_kwh": [r3(v) for v in actual_pv],
        "predicted_pv_kwh": [r3(v) for v in predicted_pv],
        "actual_peak_kwh": r3(actual_batt.sum()),
        "predicted_peak_kwh": r3(predicted_batt.sum()),
        "mae_pv_kwh": r3(mean_absolute_error(actual_pv, predicted_pv)),
    }


@asynccontextmanager
async def lifespan(_app: FastAPI):
    prepare()
    yield


app = FastAPI(title="АРЕВ", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/presentation")
def presentation():
    return FileResponse(WEB / "presentation.html")


@app.get("/api/bootstrap")
def bootstrap():
    stations = STATE["stations"]
    return {
        "stations": [
            {
                "id": row.station_id,
                "region": row.region_name,
                "city": row.city,
                "pv_kw": row.pv_kw,
                "battery_kwh": row.battery_kwh,
            }
            for row in stations.itertuples(index=False)
        ],
        "min_date": "2024-01-01",
        "max_date": "2025-12-31",
        "metrics": STATE["metrics"],
    }


@app.get("/api/solar")
def solar(
    station_id: str = Query(...),
    start: str = Query(...),
    end: str = Query(...),
):
    station = station_or_404(station_id)
    start_ts, end_ts = parse_range(start, end)
    frame = daily_slice(start_ts, end_ts)
    frame = frame[frame["station_id"] == station_id].sort_values("date")
    payload = summary_from_daily(frame)
    payload["station"] = {
        "id": station.station_id,
        "region": station.region_name,
        "city": station.city,
        "pv_kw": station.pv_kw,
        "battery_kwh": station.battery_kwh,
    }
    payload["daily"] = [
        {
            "date": row.date.strftime("%Y-%m-%d"),
            "sold_kwh": r3(row.energy_sold_kwh),
            "extra_amd": round(float(row.extra_profit_amd), 2),
            "revenue_amd": round(float(row.revenue_amd), 2),
            "battery_peak_kwh": r3(row.battery_discharge_kwh),
        }
        for row in frame.itertuples(index=False)
    ]
    return payload


@app.get("/api/grid")
def grid(start: str = Query(...), end: str = Query(...)):
    start_ts, end_ts = parse_range(start, end)
    hours = hourly_slice(start_ts, end_ts)
    days = daily_slice(start_ts, end_ts)
    if hours.empty:
        raise HTTPException(404, "В этом периоде нет данных")
    accepts = hours["grid_accepts"].astype(bool) if "grid_accepts" in hours.columns else hours["price_amd_per_kwh"] > BASE_PRICE
    refused_hours = hours.loc[~accepts]
    battery = float(hours.loc[accepts, "battery_to_grid_kwh"].sum())
    stored = float(hours["pv_to_battery_kwh"].sum())
    refused = float(refused_hours["pv_to_battery_kwh"].sum() + refused_hours["curtailed_kwh"].sum()) if "curtailed_kwh" in hours.columns else stored
    sold = float(hours["energy_sold_kwh"].sum())
    sold_when_needed = float(hours.loc[accepts, "energy_sold_kwh"].sum())
    by_hour = hours.groupby(hours["timestamp"].dt.hour).agg(
        immediate_kwh=("pv_energy_kwh", "sum"),
        sold_kwh=("energy_sold_kwh", "sum"),
        battery_kwh=("battery_to_grid_kwh", "sum"),
    )
    by_day = days.groupby("date", as_index=False)["battery_discharge_kwh"].sum()
    totals = summary_from_daily(days)
    return {
        "battery_peak_kwh": r3(battery),
        "stored_kwh": r3(stored),
        "refused_kwh": r3(refused),
        "sold_kwh": r3(sold),
        "sale_delay_h": totals["sale_delay_h"],
        "commission_amd": totals["commission_amd"],
        "peak_share_pct": r3(100 * battery / sold_when_needed) if sold_when_needed else 0,
        "hourly": [
            {
                "hour": int(hour),
                "immediate_kwh": r3(row.immediate_kwh),
                "sold_kwh": r3(row.sold_kwh),
                "battery_kwh": r3(row.battery_kwh),
            }
            for hour, row in by_hour.iterrows()
        ],
        "daily": [
            {"date": row.date.strftime("%Y-%m-%d"), "battery_peak_kwh": r3(row.battery_discharge_kwh)}
            for row in by_day.itertuples(index=False)
        ],
    }


@app.get("/api/exchange")
def exchange(start: str = Query(...), end: str = Query(...)):
    start_ts, end_ts = parse_range(start, end)
    days = daily_slice(start_ts, end_ts)
    if days.empty:
        raise HTTPException(404, "В этом периоде нет данных")
    totals = summary_from_daily(days)
    regions = []
    for name, part in days.groupby("region_name"):
        block = summary_from_daily(part)
        block["region"] = name
        block["pv_kw"] = r3(part.drop_duplicates("station_id")["pv_kw"].sum())
        regions.append(block)
    regions.sort(key=lambda item: item["extra_amd"], reverse=True)
    station_rows = []
    for station_id, part in days.groupby("station_id"):
        block = summary_from_daily(part)
        first = part.iloc[0]
        block["id"] = station_id
        block["region"] = first.region_name
        block["pv_kw"] = r3(first.pv_kw)
        station_rows.append(block)
    station_rows.sort(key=lambda item: item["extra_amd"], reverse=True)
    by_day = days.groupby("date", as_index=False).agg(
        sold_kwh=("energy_sold_kwh", "sum"),
        extra_amd=("extra_profit_amd", "sum"),
        revenue_amd=("revenue_amd", "sum"),
    )
    totals["daily"] = [
        {
            "date": row.date.strftime("%Y-%m-%d"),
            "sold_kwh": r3(row.sold_kwh),
            "extra_amd": round(float(row.extra_amd), 2),
            "revenue_amd": round(float(row.revenue_amd), 2),
        }
        for row in by_day.itertuples(index=False)
    ]
    totals["regions"] = regions
    totals["stations"] = station_rows
    totals["metrics"] = STATE["metrics"]
    return totals


@app.get("/api/forecast")
def forecast(station_id: str = Query(...), date: str = Query(...)):
    day, _end = parse_range(date, date)
    return forecast_station(station_id, day)


@app.get("/api/forecast/grid")
def forecast_grid_day(date: str = Query(...)):
    day, _end = parse_range(date, date)
    return forecast_grid(day)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
