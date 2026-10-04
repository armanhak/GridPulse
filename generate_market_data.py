"""Рыночная синтетика биржи АРЕВ.

Закон спроса подогнан под опубликованный помесячный профиль Армении
(около 7,9 ТВт·ч за 2024 год), а не под почасовую телеметрию оператора.
Её у сети нет. Поверх формы — шум, выходные и случайные исключения.

Правило рынка:
- сеть не покупает в часы, когда спрос заметно ниже своего суточного пика;
- в окне приёма станция продаёт сразу или из батареи, обычно в те же сутки;
- сервис забирает 10% от суммы, которую платит сеть.

Запуск: python generate_market_data.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from generate_synthetic_data import plane_of_array, solar_position, split_diffuse

SEED = 42
COMMISSION = 0.10
BASE_PRICE = 25.0
ETA_C = 0.95
ETA_D = 0.95
RT = ETA_C * ETA_D
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data"

# Помесячное потребление 2024, ГВт·ч, по открытым сводкам. Год масштабируется к 7,9 ТВт·ч.
MONTH_GWH = np.array([740, 700, 600, 550, 520, 500, 630, 680, 520, 660, 740, 870], dtype=float)
ANNUAL_TWH = 7.9

# Вес часа внутри сезона. Зима: утро и вечер. Лето: день и вечер. Весна: вечер невысокий.
DIURNAL = np.array(
    [
        [0.72, 0.68, 0.66, 0.66, 0.70, 0.78, 0.92, 1.08, 1.12, 1.02, 0.96, 0.94, 0.93, 0.94, 0.98, 1.08, 1.22, 1.34, 1.40, 1.36, 1.24, 1.08, 0.92, 0.80],
        [0.70, 0.66, 0.64, 0.64, 0.68, 0.74, 0.86, 0.96, 1.00, 0.98, 0.94, 0.92, 0.90, 0.92, 0.96, 1.02, 1.10, 1.18, 1.22, 1.16, 1.06, 0.94, 0.82, 0.74],
        [0.74, 0.70, 0.68, 0.66, 0.68, 0.74, 0.84, 0.96, 1.06, 1.12, 1.16, 1.18, 1.20, 1.22, 1.24, 1.26, 1.24, 1.20, 1.14, 1.06, 0.98, 0.90, 0.82, 0.76],
        [0.72, 0.68, 0.66, 0.66, 0.70, 0.78, 0.90, 1.00, 1.04, 1.00, 0.96, 0.94, 0.92, 0.94, 0.98, 1.06, 1.16, 1.26, 1.30, 1.24, 1.12, 0.98, 0.86, 0.76],
    ]
)

REGIONS = [
    {"region_id": "yerevan", "region_name": "Ереван", "city": "Ереван", "prefix": "YE", "lat": 40.18, "lon": 44.51, "elev": 990, "t_jan": -3.5, "t_jul": 26.5, "cloud_winter": 0.58, "cloud_summer": 0.22},
    {"region_id": "shirak", "region_name": "Ширак", "city": "Гюмри", "prefix": "SH", "lat": 40.79, "lon": 43.85, "elev": 1550, "t_jan": -9.0, "t_jul": 19.5, "cloud_winter": 0.68, "cloud_summer": 0.34},
    {"region_id": "lori", "region_name": "Лори", "city": "Ванадзор", "prefix": "LO", "lat": 40.81, "lon": 44.49, "elev": 1350, "t_jan": -4.0, "t_jul": 21.0, "cloud_winter": 0.72, "cloud_summer": 0.38},
    {"region_id": "gegharkunik", "region_name": "Гегаркуник", "city": "Севан", "prefix": "GE", "lat": 40.55, "lon": 44.96, "elev": 1900, "t_jan": -6.5, "t_jul": 17.5, "cloud_winter": 0.62, "cloud_summer": 0.28},
    {"region_id": "syunik", "region_name": "Сюник", "city": "Капан", "prefix": "SY", "lat": 39.21, "lon": 46.41, "elev": 910, "t_jan": 0.5, "t_jul": 24.0, "cloud_winter": 0.60, "cloud_summer": 0.30},
]


def season_index(month: np.ndarray) -> np.ndarray:
    return np.where(np.isin(month, [12, 1, 2]), 0, np.where(np.isin(month, [3, 4, 5]), 1, np.where(np.isin(month, [6, 7, 8]), 2, 3)))


def build_demand(index: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    month = index.month.to_numpy()
    hour = index.hour.to_numpy()
    dow = index.dayofweek.to_numpy()
    shape = DIURNAL[season_index(month), hour]
    shape = shape * np.where(dow >= 5, 0.94, 1.0)
    month_gwh = MONTH_GWH * (ANNUAL_TWH * 1000 / MONTH_GWH.sum())
    demand = np.zeros(len(index))
    eps = rng.normal(0, 0.035, len(index))
    noise = np.zeros(len(index))
    noise[0] = eps[0]
    for i in range(1, len(index)):
        noise[i] = 0.82 * noise[i - 1] + eps[i]
    for mon in range(1, 13):
        mask = month == mon
        for year in index.year.unique():
            part = mask & (index.year.to_numpy() == year)
            raw = shape[part] * (1 + noise[part])
            raw = np.clip(raw, 0.35, None)
            target_mwh = month_gwh[mon - 1] * 1000 * (1.015 if year > 2024 else 1.0)
            demand[part] = raw / raw.sum() * target_mwh
    return demand


def build_acceptance(index: pd.DatetimeIndex, demand: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Сеть берёт энергию только близко к суточному пику. У границы — шум."""
    day = index.normalize()
    accepts = np.zeros(len(index), dtype=bool)
    price = np.zeros(len(index))
    codes = day.asi8
    for code in np.unique(codes):
        mask = codes == code
        block = demand[mask]
        peak = float(block.max())
        threshold = float(np.clip(0.80 + rng.normal(0, 0.025), 0.72, 0.88))
        premium_at = min(0.97, threshold + 0.12)
        take = block >= threshold * peak
        accepts[mask] = take
        base = np.full(block.shape, BASE_PRICE)
        high = block >= premium_at * peak
        span = max(peak - premium_at * peak, 1.0)
        base[high] = BASE_PRICE + 23.0 * (block[high] - premium_at * peak) / span
        price[mask] = np.clip(base, BASE_PRICE, 48.0)
    noise = rng.lognormal(0, 0.015, len(price))
    price = np.where(accepts, price * noise, 0.0)
    # Редкие исключения: локальная перегрузка днём и внеплановый вечерний выкуп.
    daytime = (index.hour >= 9) & (index.hour <= 15)
    evening = (index.hour >= 16) & (index.hour <= 22)
    accepts[daytime & accepts & (rng.random(len(accepts)) < 0.05)] = False
    accepts[evening & ~accepts & (rng.random(len(accepts)) < 0.04)] = True
    price = np.where(accepts, np.where(price > 0, price, BASE_PRICE), 0.0)
    return accepts, np.round(price, 2)


def build_weather(index: pd.DatetimeIndex, region: dict, rng: np.random.Generator) -> dict[str, np.ndarray]:
    n = len(index)
    doy = index.dayofyear.to_numpy().astype(float)
    hour = index.hour.to_numpy().astype(float)
    winter = 0.5 + 0.5 * np.cos(2 * np.pi * (doy - 15) / 365.0)
    cloud_mean = region["cloud_winter"] * winter + region["cloud_summer"] * (1 - winter)
    eps = rng.normal(0, 0.045, n)
    cloud = np.empty(n)
    cloud[0] = cloud_mean[0]
    for i in range(1, n):
        cloud[i] = 0.88 * cloud[i - 1] + 0.12 * cloud_mean[i] + eps[i]
    cloud = np.clip(cloud, 0.02, 0.98)
    # Короткоживущие плотные облака: редкие, но сильные.
    bursts = rng.random(n) < 0.035
    cloud[bursts] = np.maximum(cloud[bursts], rng.uniform(0.75, 0.98, int(bursts.sum())))

    ghi_parts, dni_parts, dhi_parts = [], [], []
    for offset in (0.25, 0.75):
        zen, _az = solar_position(doy, hour + offset, region["lat"], region["lon"])
        cos_zen = np.clip(np.cos(zen), 0.0, None)
        elev_boost = 1 + max(region["elev"] - 200, 0) * 2.5e-5
        ghi_clear = np.where(
            cos_zen > 0.04,
            1098.0 * cos_zen * np.exp(-0.057 / np.maximum(cos_zen, 0.04)) * elev_boost,
            0.0,
        )
        kt = np.clip(1 - 0.75 * cloud**2, 0.08, 1.0)
        kt = kt * np.clip(rng.lognormal(0, 0.03, n), 0.85, 1.12)
        ghi = ghi_clear * np.clip(kt, 0.05, 1.05)
        dni, dhi = split_diffuse(ghi, ghi_clear, cos_zen)
        ghi_parts.append(ghi)
        dni_parts.append(dni)
        dhi_parts.append(dhi)

    t_mean = 0.5 * (region["t_jan"] + region["t_jul"])
    t_amp = 0.5 * (region["t_jul"] - region["t_jan"])
    seasonal = t_mean + t_amp * np.cos(2 * np.pi * (doy - 200) / 365.0)
    diurnal = (5.5 + 2.0 * (1 - cloud)) * np.cos(2 * np.pi * (hour - 15) / 24.0)
    temp = seasonal + diurnal + rng.normal(0, 0.7, n)
    zen_mid, az_mid = solar_position(doy, hour + 0.5, region["lat"], region["lon"])
    return {
        "temp_c": temp,
        "cloud_cover": cloud,
        "ghi_w_m2": np.mean(ghi_parts, axis=0),
        "dni_w_m2": np.mean(dni_parts, axis=0),
        "dhi_w_m2": np.mean(dhi_parts, axis=0),
        "zen": zen_mid,
        "az": az_mid,
        "doy": doy,
    }


def station_table(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for region in REGIONS:
        for k in range(1, 7):
            pv_kw = float(np.clip(rng.lognormal(np.log(5.2), 0.32), 2.5, 14))
            hours = float(rng.uniform(1.3, 2.6))
            battery = float(np.clip(pv_kw * hours, 4, 22))
            rows.append(
                {
                    "station_id": f"{region['prefix']}-{k:02d}",
                    "region_id": region["region_id"],
                    "region_name": region["region_name"],
                    "city": region["city"],
                    "latitude": round(region["lat"] + float(rng.uniform(-0.08, 0.08)), 4),
                    "longitude": round(region["lon"] + float(rng.uniform(-0.08, 0.08)), 4),
                    "elevation_m": region["elev"],
                    "pv_kw": round(pv_kw, 2),
                    "tilt_deg": int(np.clip(rng.normal(32, 4), 20, 45)),
                    "azimuth_deg": int(np.clip(rng.normal(180, 8), 155, 205)),
                    "performance_ratio": round(float(np.clip(rng.normal(0.81, 0.025), 0.74, 0.88)), 3),
                    "battery_kwh": round(battery, 2),
                    "battery_power_kw": round(min(pv_kw, max(2.0, battery / 2)), 2),
                    "charge_efficiency": ETA_C,
                    "discharge_efficiency": ETA_D,
                    "commission_rate": COMMISSION,
                    "sells_immediately": int(rng.random() < 0.20),
                }
            )
    return pd.DataFrame(rows)


def pv_profile(weather: dict[str, np.ndarray], station: pd.Series, rng: np.random.Generator) -> np.ndarray:
    poa = plane_of_array(
        weather["zen"], weather["az"], weather["ghi_w_m2"], weather["dni_w_m2"], weather["dhi_w_m2"],
        float(station["tilt_deg"]), float(station["azimuth_deg"]),
    )
    t_cell = weather["temp_c"] + poa / 800.0 * 28.0
    soiling = 0.98 - 0.04 * np.clip(np.sin(2 * np.pi * (weather["doy"] - 80) / 365.0), 0, None)
    kw = (
        float(station["pv_kw"])
        * (poa / 1000.0)
        * (1 - 0.004 * (t_cell - 25.0))
        * float(station["performance_ratio"])
        * soiling
    )
    kw = np.clip(kw, 0.0, float(station["pv_kw"]))
    n = kw.size
    avail = np.ones(n)
    n_days = n // 24
    for day in rng.choice(n_days, size=5, replace=False):
        avail[int(day) * 24 : int(day) * 24 + 24] = 0.0
    avail[rng.random(n) < 0.0015] = 0.0
    kw *= avail * np.clip(rng.normal(1.0, 0.02, n), 0.9, 1.08)
    return np.clip(kw, 0.0, float(station["pv_kw"]))


def dispatch(pv, price, accepts, capacity, power, impatient: bool):
    n = len(pv)
    soc_min = 0.10 * capacity
    soc = 0.5 * capacity
    stored = soc - soc_min
    age_sum = stored * 0.0
    to_battery = np.zeros(n)
    pv_to_grid = np.zeros(n)
    batt_to_grid = np.zeros(n)
    curtailed = np.zeros(n)
    soc_end = np.zeros(n)
    delay_kwh = np.zeros(n)
    relay = np.empty(n, dtype=object)

    for j in range(n):
        horizon = price[j + 1 : j + 13]
        horizon_ok = accepts[j + 1 : j + 13]
        future = horizon[horizon_ok] if horizon_ok.any() else np.empty(0)
        best_future = float(future.max()) if future.size else (float(price[j]) if accepts[j] else 0.0)
        produced = float(pv[j])
        p = float(price[j])
        sell_now = bool(accepts[j]) and (impatient or p + 0.4 >= best_future * RT)
        charged = 0.0
        sold_pv = 0.0
        sold_batt = 0.0
        spilled = 0.0

        if not accepts[j]:
            room = max(0.0, (capacity - soc) / ETA_C)
            charged = min(produced, room, power)
            spilled = produced - charged
        elif sell_now:
            sold_pv = produced
            slots = 1
            for k in range(1, 6):
                if j + k < n and accepts[j + k] and abs(float(price[j + k]) - p) < 1.0:
                    slots += 1
                else:
                    break
            can = max(0.0, (soc - soc_min) * ETA_D)
            sold_batt = min(can / slots, power, can)
        else:
            room = max(0.0, (capacity - soc) / ETA_C)
            charged = min(produced, room, power)
            sold_pv = produced - charged

        taken = sold_batt / ETA_D if sold_batt else 0.0
        if taken > 0 and stored > 1e-9:
            avg_age = age_sum / stored
            delay_kwh[j] = sold_batt * max(0.0, j - avg_age)
            age_sum -= avg_age * min(taken, stored)
            stored -= min(taken, stored)
        if charged > 0:
            stored_add = charged * ETA_C
            age_sum += stored_add * j
            stored += stored_add
        soc = min(capacity, max(soc_min, soc_min + stored))
        stored = max(0.0, soc - soc_min)

        if charged > 0.01 and (sold_pv + sold_batt) > 0.01:
            mode = "charge_and_sell"
        elif charged > 0.01:
            mode = "charge"
        elif (sold_pv + sold_batt) > 0.01:
            mode = "sell"
        else:
            mode = "idle"
        to_battery[j] = charged
        pv_to_grid[j] = sold_pv
        batt_to_grid[j] = sold_batt
        curtailed[j] = spilled
        soc_end[j] = soc
        relay[j] = mode
    return to_battery, pv_to_grid, batt_to_grid, curtailed, soc_end, delay_kwh, relay


def main() -> None:
    rng = np.random.Generator(np.random.PCG64(SEED))
    index = pd.date_range("2024-01-01", "2026-01-01", freq="h", inclusive="left")
    stamp = index.strftime("%Y-%m-%d %H:%M")
    demand = build_demand(index, rng)
    accepts, price = build_acceptance(index, demand, rng)
    stations = station_table(rng)

    weather_frames = []
    weather_by_region = {}
    for region in REGIONS:
        weather = build_weather(index, region, rng)
        weather_by_region[region["region_id"]] = weather
        weather_frames.append(pd.DataFrame({
            "region_id": region["region_id"],
            "timestamp": stamp,
            "temp_c": np.round(weather["temp_c"], 1),
            "cloud_cover": np.round(weather["cloud_cover"], 3),
            "ghi_w_m2": np.round(weather["ghi_w_m2"], 1),
            "dni_w_m2": np.round(weather["dni_w_m2"], 1),
            "dhi_w_m2": np.round(weather["dhi_w_m2"], 1),
        }))

    hourly_frames = []
    for _, station in stations.iterrows():
        pv = pv_profile(weather_by_region[station["region_id"]], station, rng)
        to_batt, pv_grid, batt_grid, curtailed, soc, delay_kwh, relay = dispatch(
            pv, price, accepts,
            float(station["battery_kwh"]), float(station["battery_power_kw"]),
            bool(station["sells_immediately"]),
        )
        sold = pv_grid + batt_grid
        gross = sold * price
        no_battery = np.where(accepts, pv * price, 0.0)
        hourly_frames.append(pd.DataFrame({
            "station_id": station["station_id"],
            "region_id": station["region_id"],
            "timestamp": stamp,
            "pv_energy_kwh": np.round(pv, 3),
            "relay": relay,
            "pv_to_battery_kwh": np.round(to_batt, 3),
            "pv_to_grid_kwh": np.round(pv_grid, 3),
            "battery_to_grid_kwh": np.round(batt_grid, 3),
            "curtailed_kwh": np.round(curtailed, 3),
            "soc_kwh": np.round(soc, 3),
            "energy_sold_kwh": np.round(sold, 3),
            "grid_accepts": accepts.astype(int),
            "price_amd_per_kwh": price,
            "revenue_gross_amd": np.round(gross, 2),
            "commission_amd": np.round(gross * COMMISSION, 2),
            "revenue_amd": np.round(gross * (1 - COMMISSION), 2),
            "revenue_if_immediate_amd": np.round(no_battery * (1 - COMMISSION), 2),
            "sale_delay_kwh_h": np.round(delay_kwh, 3),
        }))

    hourly = pd.concat(hourly_frames, ignore_index=True)
    hourly["extra_profit_amd"] = (hourly["revenue_amd"] - hourly["revenue_if_immediate_amd"]).round(2)
    hourly["date"] = hourly["timestamp"].str.slice(0, 10)
    daily = hourly.groupby(["station_id", "date"], as_index=False).agg(
        pv_kwh=("pv_energy_kwh", "sum"),
        energy_sold_kwh=("energy_sold_kwh", "sum"),
        battery_discharge_kwh=("battery_to_grid_kwh", "sum"),
        curtailed_kwh=("curtailed_kwh", "sum"),
        pv_to_battery_kwh=("pv_to_battery_kwh", "sum"),
        revenue_gross_amd=("revenue_gross_amd", "sum"),
        commission_amd=("commission_amd", "sum"),
        revenue_amd=("revenue_amd", "sum"),
        revenue_if_immediate_amd=("revenue_if_immediate_amd", "sum"),
        extra_profit_amd=("extra_profit_amd", "sum"),
        sale_delay_kwh_h=("sale_delay_kwh_h", "sum"),
    )
    sold_when_refused = hourly.loc[hourly["grid_accepts"] == 0].groupby(["station_id", "date"])[["pv_to_battery_kwh", "curtailed_kwh"]].sum()
    sold_when_refused["withheld_kwh"] = sold_when_refused["pv_to_battery_kwh"] + sold_when_refused["curtailed_kwh"]
    daily = daily.merge(
        sold_when_refused[["withheld_kwh"]].reset_index(),
        on=["station_id", "date"],
        how="left",
    )
    daily["withheld_kwh"] = daily["withheld_kwh"].fillna(0).round(3)
    daily["sale_delay_h"] = np.where(
        daily["energy_sold_kwh"] > 0.05,
        daily["sale_delay_kwh_h"] / daily["energy_sold_kwh"],
        0,
    )
    daily = daily.drop(columns=["sale_delay_kwh_h"])
    for col in daily.columns:
        if col.endswith("kwh") or col.endswith("_h"):
            daily[col] = daily[col].round(3)
        elif col.endswith("amd"):
            daily[col] = daily[col].round(2)
    hourly = hourly.drop(columns=["date", "sale_delay_kwh_h"])

    prices = pd.DataFrame({
        "timestamp": stamp,
        "price_amd_per_kwh": price,
        "grid_accepts": accepts.astype(int),
        "offer": np.where(~accepts, "refuse", np.where(price > BASE_PRICE + 1, "premium", "base")),
    })
    grid = pd.DataFrame({
        "timestamp": stamp,
        "demand_mw": np.round(demand, 3),
        "grid_accepts": accepts.astype(int),
        "price_amd_per_kwh": price,
    })

    OUT.mkdir(parents=True, exist_ok=True)
    stations.to_csv(OUT / "stations.csv", index=False, encoding="utf-8-sig")
    pd.concat(weather_frames, ignore_index=True).to_csv(OUT / "weather_hourly.csv", index=False, encoding="utf-8-sig")
    prices.to_csv(OUT / "prices_hourly.csv", index=False, encoding="utf-8-sig")
    grid.to_csv(OUT / "grid_hourly.csv", index=False, encoding="utf-8-sig")
    hourly.to_csv(OUT / "station_hourly.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(OUT / "station_daily.csv", index=False, encoding="utf-8-sig")
    model_cache = ROOT / "models" / "pv_model.joblib"
    if model_cache.exists():
        model_cache.unlink()

    report = build_report(index, demand, accepts, price, stations, hourly, daily)
    (OUT / "generation_report.txt").write_text(report, encoding="utf-8")
    print(report)


def build_report(index, demand, accepts, price, stations, hourly, daily) -> str:
    year = np.asarray(index.year == 2024)
    annual_twh = demand[year].sum() / 1e6
    month = index.month.to_numpy()
    hour = index.hour.to_numpy()
    spring_noon = np.isin(month, [3, 4, 5]) & (hour >= 10) & (hour <= 15) & year
    winter_evening = np.isin(month, [12, 1, 2]) & (hour >= 18) & (hour <= 21) & year
    cap = stations.set_index("station_id")["pv_kw"]
    produced = hourly.groupby("station_id")["pv_energy_kwh"].sum()
    specific = (produced / cap / 2)
    gross = daily["revenue_gross_amd"].sum()
    commission = daily["commission_amd"].sum()
    sold = daily["energy_sold_kwh"].sum()
    delay = np.average(daily.loc[daily["energy_sold_kwh"] > 0.05, "sale_delay_h"], weights=daily.loc[daily["energy_sold_kwh"] > 0.05, "energy_sold_kwh"])
    lines = [
        "Рыночная синтетика АРЕВ",
        "Спрос синтетический. Годовой объём и помесячная форма взяты из открытых сводок, почасовой ряд оператора не использовался.",
        f"Потребление 2024 в модели: {annual_twh:.2f} ТВт·ч при ориентире {ANNUAL_TWH:.1f}",
        f"Весна, 10:00–15:00, доля часов отказа: {100 * (1 - accepts[spring_noon].mean()):.0f}%",
        f"Зима, 18:00–21:00, доля часов приёма: {100 * accepts[winter_evening].mean():.0f}%",
        f"Выработка станций, кВт·ч/кВт в год: {specific.min():.0f}–{specific.max():.0f}, среднее {specific.mean():.0f}",
        f"Продано, МВт·ч: {sold / 1000:.1f}",
        f"Срезано, потому что батарея полная и сеть не брала, МВт·ч: {daily['curtailed_kwh'].sum() / 1000:.2f}",
        f"Не отдано в сеть в часы отказа, МВт·ч: {daily['withheld_kwh'].sum() / 1000:.1f}",
        f"Валовая оплата сети, драм: {gross:,.0f}",
        f"Комиссия 10%, драм: {commission:,.0f} ({100 * commission / gross:.1f}% )",
        f"Доход станций после комиссии, драм: {daily['revenue_amd'].sum():,.0f}",
        f"Доп. доход против продажи без батареи, драм: {daily['extra_profit_amd'].sum():,.0f}",
        f"Среднее время от выработки до продажи, ч: {delay:.1f}",
        "20% станций продают в первый же час приёма, остальные ждут лучшую цену не дольше 12 часов.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
