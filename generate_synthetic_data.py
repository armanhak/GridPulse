"""Синтетика домашней солнечной биржи для хакатона Green Tech Academy.

Локальное время Армении (UTC+4, без перехода на летнее).
Нагрузки сети, импорта и состава генерации здесь нет: покупатель
их не раскрывает. Единственный сигнал от покупателя — опубликованная
почасовая цена выкупа.

Период: 2024-01-01 .. 2025-12-31.
Зерно генератора: 42.

Выход в каталоге data/:
  stations.csv         паспорта станций
  weather_hourly.csv   погода региона, признаки для прогноза выработки
  prices_hourly.csv    цена выкупа, одна на всю страну
  station_hourly.csv   выработка, реле, батарея, продажа, доход
  station_daily.csv    дневные итоги и доп. доход против мгновенной продажи
  generation_report.txt
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
TZ_HOURS = 4.0
BASE_PRICE_AMD = 25.0
WEAR_AMD_PER_KWH = 0.8
ETA_C = 0.95
ETA_D = 0.95
SOC_MIN_FRAC = 0.10
N_STATIONS_PER_REGION = 6

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data"

REGIONS = [
    {
        "region_id": "yerevan",
        "region_name": "Ереван",
        "city": "Ереван",
        "prefix": "YE",
        "lat": 40.18,
        "lon": 44.51,
        "elev": 990,
        "t_jan": -3.5,
        "t_jul": 26.5,
        "cloud_winter": 0.58,
        "cloud_summer": 0.20,
    },
    {
        "region_id": "shirak",
        "region_name": "Ширак",
        "city": "Гюмри",
        "prefix": "SH",
        "lat": 40.79,
        "lon": 43.85,
        "elev": 1550,
        "t_jan": -9.0,
        "t_jul": 19.5,
        "cloud_winter": 0.68,
        "cloud_summer": 0.32,
    },
    {
        "region_id": "lori",
        "region_name": "Лори",
        "city": "Ванадзор",
        "prefix": "LO",
        "lat": 40.81,
        "lon": 44.49,
        "elev": 1350,
        "t_jan": -4.0,
        "t_jul": 21.0,
        "cloud_winter": 0.72,
        "cloud_summer": 0.36,
    },
    {
        "region_id": "gegharkunik",
        "region_name": "Гегаркуник",
        "city": "Севан",
        "prefix": "GE",
        "lat": 40.55,
        "lon": 44.96,
        "elev": 1900,
        "t_jan": -6.5,
        "t_jul": 17.5,
        "cloud_winter": 0.62,
        "cloud_summer": 0.26,
    },
    {
        "region_id": "syunik",
        "region_name": "Сюник",
        "city": "Капан",
        "prefix": "SY",
        "lat": 39.21,
        "lon": 46.41,
        "elev": 910,
        "t_jan": 0.5,
        "t_jul": 24.0,
        "cloud_winter": 0.60,
        "cloud_summer": 0.28,
    },
]


def timestamps() -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", "2026-01-01", freq="h", inclusive="left")


def solar_position(
    doys: np.ndarray,
    hours: np.ndarray,
    lat_deg: float,
    lon_deg: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Зенит и азимут солнца. Азимут: 0° север, 180° юг."""
    lat = np.deg2rad(lat_deg)
    gamma = 2 * np.pi / 365.0 * (doys - 1 + (hours - 12) / 24.0)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * np.cos(gamma)
        - 0.032077 * np.sin(gamma)
        - 0.014615 * np.cos(2 * gamma)
        - 0.040849 * np.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * np.cos(gamma)
        + 0.070257 * np.sin(gamma)
        - 0.006758 * np.cos(2 * gamma)
        + 0.000907 * np.sin(2 * gamma)
        - 0.002697 * np.cos(3 * gamma)
        + 0.00148 * np.sin(3 * gamma)
    )
    time_offset = eqtime + 4 * lon_deg - 60 * TZ_HOURS
    ha_deg = (hours * 60 + time_offset) / 4.0 - 180.0
    ha = np.deg2rad(ha_deg)
    cos_zen = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(ha)
    cos_zen = np.clip(cos_zen, -1.0, 1.0)
    zen = np.arccos(cos_zen)

    # Азимут от севера по часовой. atan2 устойчивее acos у зенита.
    east = -np.sin(ha) * np.cos(decl)
    north = np.sin(decl) * np.cos(lat) - np.cos(decl) * np.sin(lat) * np.cos(ha)
    az = np.arctan2(east, north)
    az = np.where(az < 0, az + 2 * np.pi, az)
    return zen, az


def plane_of_array(
    zen: np.ndarray,
    az: np.ndarray,
    ghi: np.ndarray,
    dni: np.ndarray,
    dhi: np.ndarray,
    tilt_deg: float,
    azimuth_deg: float,
) -> np.ndarray:
    tilt = np.deg2rad(tilt_deg)
    az_panel = np.deg2rad(azimuth_deg)
    cos_aoi = np.cos(zen) * np.cos(tilt) + np.sin(zen) * np.sin(tilt) * np.cos(
        az - az_panel
    )
    cos_aoi = np.clip(cos_aoi, 0.0, None)
    beam = dni * cos_aoi
    sky = dhi * (1 + np.cos(tilt)) / 2
    ground = ghi * 0.2 * (1 - np.cos(tilt)) / 2
    poa = beam + sky + ground
    poa = np.where(zen < np.deg2rad(90), poa, 0.0)
    return np.clip(poa, 0.0, None)


def split_diffuse(ghi: np.ndarray, ghi_clear: np.ndarray, cos_zen: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    clear = np.maximum(ghi_clear, 1e-6)
    kt = np.clip(np.where(ghi_clear > 20, ghi / clear, 0.0), 0.0, 1.0)
    fd = np.where(
        kt <= 0.22,
        1.0 - 0.09 * kt,
        np.where(
            kt <= 0.80,
            0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4,
            0.165,
        ),
    )
    fd = np.clip(fd, 0.165, 1.0)
    dhi = ghi * fd
    cos_safe = np.maximum(cos_zen, 0.08)
    dni = np.where(cos_zen > 0.08, (ghi - dhi) / cos_safe, 0.0)
    return np.clip(dni, 0.0, 1100.0), np.clip(dhi, 0.0, None)


def build_prices(index: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    """Цена, которую покупатель публикует на час. Не нагрузка сети."""
    month = index.month.to_numpy()
    hour = index.hour.to_numpy()
    price = np.full(len(index), BASE_PRICE_AMD)

    evening = np.isin(hour, [18, 19, 20, 21])
    price[evening & np.isin(month, [12, 1, 2])] = 40.0
    price[evening & np.isin(month, [11, 3])] = 35.0
    price[evening & np.isin(month, [7, 8])] = 38.0
    price[evening & np.isin(month, [4, 5, 6, 9, 10])] = 32.0

    price[np.isin(month, [7, 8]) & np.isin(hour, [15, 16, 17])] = 33.0
    price[np.isin(month, [12, 1, 2]) & np.isin(hour, [7, 8])] = 32.0

    day_code = index.normalize().asi8
    unique_days = np.unique(day_code)
    scarce_days = set(rng.choice(unique_days, size=48, replace=False).tolist())
    scarce = np.fromiter((code in scarce_days for code in day_code), dtype=bool, count=len(day_code))
    price[scarce & np.isin(hour, [19, 20, 21])] = 48.0

    offer = np.where(price > BASE_PRICE_AMD, "increased", "base")
    return pd.DataFrame(
        {
            "timestamp": index.strftime("%Y-%m-%d %H:%M"),
            "price_amd_per_kwh": price,
            "offer": offer,
        }
    )


def build_weather(
    index: pd.DatetimeIndex,
    region: dict,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    n = len(index)
    doy = index.dayofyear.to_numpy().astype(float)
    hour = index.hour.to_numpy().astype(float)
    month_angle = 2 * np.pi * (doy - 15) / 365.0
    winter_weight = 0.5 + 0.5 * np.cos(month_angle)

    cloud_mean = (
        region["cloud_winter"] * winter_weight
        + region["cloud_summer"] * (1 - winter_weight)
    )
    eps = rng.normal(0.0, 0.04, n)
    cloud = np.empty(n)
    cloud[0] = cloud_mean[0]
    for i in range(1, n):
        cloud[i] = 0.90 * cloud[i - 1] + 0.10 * cloud_mean[i] + eps[i]
    cloud = np.clip(cloud, 0.02, 0.98)

    n_days = n // 24
    for _ in range(28):
        start_day = int(rng.integers(0, n_days - 2))
        length = int(rng.integers(8, 36))
        start = start_day * 24
        cloud[start : start + length] = np.maximum(
            cloud[start : start + length], rng.uniform(0.82, 0.96)
        )

    # Два отсчёта внутри часа, чтобы рассвет не был одной точкой.
    ghi_parts = []
    dni_parts = []
    dhi_parts = []
    for offset in (0.25, 0.75):
        hours = hour + offset
        zen, _az = solar_position(doy, hours, region["lat"], region["lon"])
        cos_zen = np.clip(np.cos(zen), 0.0, None)
        elev_boost = 1 + max(region["elev"] - 200, 0) * 2.5e-5
        ghi_clear = np.where(
            cos_zen > 0.04,
            1098.0 * cos_zen * np.exp(-0.057 / np.maximum(cos_zen, 0.04)) * elev_boost,
            0.0,
        )
        trans = np.clip(1 - 0.75 * cloud**2, 0.08, 1.0)
        ghi = ghi_clear * trans
        dni, dhi = split_diffuse(ghi, ghi_clear, cos_zen)
        ghi_parts.append(ghi)
        dni_parts.append(dni)
        dhi_parts.append(dhi)

    ghi = np.mean(ghi_parts, axis=0)
    dni = np.mean(dni_parts, axis=0)
    dhi = np.mean(dhi_parts, axis=0)

    t_mean = 0.5 * (region["t_jan"] + region["t_jul"])
    t_amp = 0.5 * (region["t_jul"] - region["t_jan"])
    seasonal = t_mean + t_amp * np.cos(2 * np.pi * (doy - 200) / 365.0)
    diurnal = (5.5 + 2.0 * (1 - cloud)) * np.cos(2 * np.pi * (hour - 15) / 24.0)
    t_eps = rng.normal(0.0, 0.6, n)
    temp = np.empty(n)
    temp[0] = seasonal[0] + diurnal[0]
    for i in range(1, n):
        temp[i] = (
            0.75 * temp[i - 1]
            + 0.25 * (seasonal[i] + diurnal[i])
            + t_eps[i]
        )

    # Положение солнца на середину часа — для перевода радиации в мощность панели.
    zen_mid, az_mid = solar_position(doy, hour + 0.5, region["lat"], region["lon"])

    return {
        "temp_c": temp,
        "cloud_cover": cloud,
        "ghi_w_m2": ghi,
        "dni_w_m2": dni,
        "dhi_w_m2": dhi,
        "zen": zen_mid,
        "az": az_mid,
        "doy": doy,
    }


def station_table(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for region in REGIONS:
        for k in range(1, N_STATIONS_PER_REGION + 1):
            pv_kw = float(rng.choice([3.0, 4.0, 5.0, 5.0, 6.0, 8.0, 10.0]))
            battery_kwh = float(rng.choice([5.0, 8.0, 10.0, 10.0, 15.0]))
            rows.append(
                {
                    "station_id": f"{region['prefix']}-{k:02d}",
                    "region_id": region["region_id"],
                    "region_name": region["region_name"],
                    "city": region["city"],
                    "latitude": round(region["lat"] + float(rng.uniform(-0.08, 0.08)), 4),
                    "longitude": round(region["lon"] + float(rng.uniform(-0.08, 0.08)), 4),
                    "elevation_m": region["elev"],
                    "pv_kw": pv_kw,
                    "tilt_deg": int(rng.integers(25, 41)),
                    "azimuth_deg": int(rng.integers(165, 196)),
                    "performance_ratio": round(float(rng.uniform(0.76, 0.86)), 3),
                    "battery_kwh": battery_kwh,
                    "battery_power_kw": round(min(pv_kw, max(2.5, battery_kwh / 2)), 2),
                    "charge_efficiency": ETA_C,
                    "discharge_efficiency": ETA_D,
                    "wear_amd_per_kwh": WEAR_AMD_PER_KWH,
                    "soc_min_frac": SOC_MIN_FRAC,
                }
            )
    return pd.DataFrame(rows)


def pv_profile(
    weather: dict[str, np.ndarray],
    station: pd.Series,
    rng: np.random.Generator,
) -> np.ndarray:
    poa = plane_of_array(
        weather["zen"],
        weather["az"],
        weather["ghi_w_m2"],
        weather["dni_w_m2"],
        weather["dhi_w_m2"],
        float(station["tilt_deg"]),
        float(station["azimuth_deg"]),
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
    for day in rng.choice(n_days, size=4, replace=False):
        avail[int(day) * 24 : int(day) * 24 + 24] = 0.0
    avail[rng.random(n) < 0.002] = 0.0
    kw = kw * avail * rng.normal(1.0, 0.02, n)
    return np.clip(kw, 0.0, float(station["pv_kw"]))


def dispatch(
    pv: np.ndarray,
    price: np.ndarray,
    battery_kwh: float,
    battery_power_kw: float,
) -> dict[str, np.ndarray]:
    """Реле знает цену на 14 часов вперёд и не заряжается из сети."""
    n = pv.size
    rt = ETA_C * ETA_D
    cap = battery_kwh
    soc_min = SOC_MIN_FRAC * cap
    soc = 0.5 * cap
    power = battery_power_kw

    to_battery = np.zeros(n)
    pv_to_grid = np.zeros(n)
    batt_to_grid = np.zeros(n)
    soc_end = np.zeros(n)
    relay = np.empty(n, dtype=object)

    for j in range(n):
        horizon = price[j + 1 : j + 15]
        best_future = float(horizon.max()) if horizon.size else float(price[j])
        p = float(price[j])
        produced = float(pv[j])
        store = (best_future * rt - WEAR_AMD_PER_KWH) > p

        charged = 0.0
        sold_pv = 0.0
        sold_batt = 0.0

        if store:
            room = max(0.0, (cap - soc) / ETA_C)
            charged = min(produced, room, power)
            sold_pv = produced - charged
        else:
            sold_pv = produced
            if p + 1e-6 >= best_future and p > BASE_PRICE_AMD:
                slots = 1
                for k in range(1, 6):
                    if j + k < n and abs(float(price[j + k]) - p) < 0.05:
                        slots += 1
                    else:
                        break
                can = max(0.0, (soc - soc_min) * ETA_D)
                sold_batt = min(can / slots, power, can)

        soc = soc + charged * ETA_C - (sold_batt / ETA_D if sold_batt else 0.0)
        soc = min(cap, max(soc_min, soc))

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
        soc_end[j] = soc
        relay[j] = mode

    return {
        "pv_to_battery_kwh": to_battery,
        "pv_to_grid_kwh": pv_to_grid,
        "battery_to_grid_kwh": batt_to_grid,
        "soc_kwh": soc_end,
        "relay": relay,
    }


def check_solar_geometry() -> None:
    morn = solar_position(np.array([173.0]), np.array([9.5]), 40.18, 44.51)
    noon = solar_position(np.array([173.0]), np.array([13.0]), 40.18, 44.51)
    aft = solar_position(np.array([173.0]), np.array([16.5]), 40.18, 44.51)
    morn_az, noon_az, aft_az = (float(np.rad2deg(item[1][0])) for item in (morn, noon, aft))
    noon_zen = float(np.rad2deg(noon[0][0]))
    if not (70 < morn_az < 120 and 160 < noon_az < 200 and 230 < aft_az < 290):
        raise SystemExit(f"плохой азимут: утро {morn_az:.0f}, полдень {noon_az:.0f}, день {aft_az:.0f}")
    if not (10 < noon_zen < 25):
        raise SystemExit(f"плохой зенит в полдень 21 июня: {noon_zen:.1f}")


def main() -> None:
    check_solar_geometry()
    rng = np.random.Generator(np.random.PCG64(SEED))
    index = timestamps()
    stamp = index.strftime("%Y-%m-%d %H:%M")
    price_df = build_prices(index, rng)
    price = price_df["price_amd_per_kwh"].to_numpy()

    stations = station_table(rng)
    weather_frames = []
    hourly_frames = []
    weather_by_region: dict[str, dict[str, np.ndarray]] = {}

    for region in REGIONS:
        weather = build_weather(index, region, rng)
        weather_by_region[region["region_id"]] = weather
        weather_frames.append(
            pd.DataFrame(
                {
                    "region_id": region["region_id"],
                    "timestamp": stamp,
                    "temp_c": np.round(weather["temp_c"], 1),
                    "cloud_cover": np.round(weather["cloud_cover"], 3),
                    "ghi_w_m2": np.round(weather["ghi_w_m2"], 1),
                    "dni_w_m2": np.round(weather["dni_w_m2"], 1),
                    "dhi_w_m2": np.round(weather["dhi_w_m2"], 1),
                }
            )
        )

    for _, station in stations.iterrows():
        weather = weather_by_region[station["region_id"]]
        pv = pv_profile(weather, station, rng)
        flow = dispatch(
            pv,
            price,
            float(station["battery_kwh"]),
            float(station["battery_power_kw"]),
        )
        sold = flow["pv_to_grid_kwh"] + flow["battery_to_grid_kwh"]
        hourly_frames.append(
            pd.DataFrame(
                {
                    "station_id": station["station_id"],
                    "region_id": station["region_id"],
                    "timestamp": stamp,
                    "pv_energy_kwh": np.round(pv, 3),
                    "relay": flow["relay"],
                    "pv_to_battery_kwh": np.round(flow["pv_to_battery_kwh"], 3),
                    "pv_to_grid_kwh": np.round(flow["pv_to_grid_kwh"], 3),
                    "battery_to_grid_kwh": np.round(flow["battery_to_grid_kwh"], 3),
                    "soc_kwh": np.round(flow["soc_kwh"], 3),
                    "energy_sold_kwh": np.round(sold, 3),
                    "price_amd_per_kwh": price,
                    "revenue_amd": np.round(sold * price, 2),
                    "revenue_if_immediate_amd": np.round(pv * price, 2),
                }
            )
        )

    weather_df = pd.concat(weather_frames, ignore_index=True)
    hourly = pd.concat(hourly_frames, ignore_index=True)
    hourly["date"] = hourly["timestamp"].str.slice(0, 10)
    increased = hourly["price_amd_per_kwh"] > BASE_PRICE_AMD
    daily = (
        hourly.assign(
            sold_increased=np.where(increased, hourly["energy_sold_kwh"], 0.0),
            pv_increased=np.where(increased, hourly["pv_energy_kwh"], 0.0),
        )
        .groupby(["station_id", "date"], as_index=False)
        .agg(
            pv_kwh=("pv_energy_kwh", "sum"),
            energy_sold_kwh=("energy_sold_kwh", "sum"),
            sold_at_increased_price_kwh=("sold_increased", "sum"),
            pv_generated_at_increased_price_kwh=("pv_increased", "sum"),
            battery_discharge_kwh=("battery_to_grid_kwh", "sum"),
            revenue_amd=("revenue_amd", "sum"),
            revenue_if_immediate_amd=("revenue_if_immediate_amd", "sum"),
        )
    )
    daily["extra_profit_amd"] = (
        daily["revenue_amd"] - daily["revenue_if_immediate_amd"]
    ).round(2)
    for col in (
        "pv_kwh",
        "energy_sold_kwh",
        "sold_at_increased_price_kwh",
        "pv_generated_at_increased_price_kwh",
        "battery_discharge_kwh",
        "revenue_amd",
        "revenue_if_immediate_amd",
    ):
        daily[col] = daily[col].round(3 if col.endswith("kwh") else 2)
    hourly = hourly.drop(columns=["date"])

    cap = stations.set_index("station_id")["pv_kw"]
    specific_year = hourly.groupby("station_id")["pv_energy_kwh"].sum() / cap / 2
    if not (1200 <= float(specific_year.median()) <= 2000):
        raise SystemExit(
            f"нереалистичная выработка {float(specific_year.median()):.0f} кВт·ч/кВт в год"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    stations.to_csv(OUT / "stations.csv", index=False, encoding="utf-8-sig")
    weather_df.to_csv(OUT / "weather_hourly.csv", index=False, encoding="utf-8-sig")
    price_df.to_csv(OUT / "prices_hourly.csv", index=False, encoding="utf-8-sig")
    hourly.to_csv(OUT / "station_hourly.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(OUT / "station_daily.csv", index=False, encoding="utf-8-sig")

    report = build_report(index, stations, weather_df, price_df, hourly, daily)
    (OUT / "generation_report.txt").write_text(report, encoding="utf-8")
    print(report)


def build_report(
    index: pd.DatetimeIndex,
    stations: pd.DataFrame,
    weather: pd.DataFrame,
    prices: pd.DataFrame,
    hourly: pd.DataFrame,
    daily: pd.DataFrame,
) -> str:
    cap = stations.set_index("station_id")["pv_kw"]
    produced = hourly.groupby("station_id")["pv_energy_kwh"].sum()
    specific = (produced / cap.loc[produced.index]).rename("kwh_per_kwp")
    by_region = (
        stations.assign(specific=stations["station_id"].map(specific))
        .groupby("region_name")["specific"]
        .mean()
    )
    night = hourly["timestamp"].str.slice(11, 13).isin(["00", "01", "02", "03", "22", "23"])
    night_kwh = hourly.loc[night, "pv_energy_kwh"].sum()
    revenue = daily["revenue_amd"].sum()
    baseline = daily["revenue_if_immediate_amd"].sum()
    extra = revenue - baseline
    sold_inc = daily["sold_at_increased_price_kwh"].sum()
    pv_inc = daily["pv_generated_at_increased_price_kwh"].sum()
    sold = daily["energy_sold_kwh"].sum()
    pv = daily["pv_kwh"].sum()

    # Контроль геометрии: полдень 21 июня в Ереване.
    june = index[(index.month == 6) & (index.day == 21) & (index.hour == 13)][0]
    yerevan = next(r for r in REGIONS if r["region_id"] == "yerevan")
    zen, az = solar_position(
        np.array([float(june.dayofyear)]),
        np.array([13.5]),
        yerevan["lat"],
        yerevan["lon"],
    )

    lines = [
        "Синтетические данные домашней солнечной биржи",
        "Локальное время Армении, UTC+4. Нагрузки сети в файлах нет.",
        f"Период: {index[0]:%Y-%m-%d %H:%M} — {index[-1]:%Y-%m-%d %H:%M}",
        f"Станций: {len(stations)}  Регионов: {stations['region_id'].nunique()}",
        f"Почасовых строк станций: {len(hourly)}",
        "",
        "Обычная цена выкупа: 25 драм/кВт·ч (синтетическая, не тариф КРОУ).",
        "Повышенная цена публикуется вечером, зимним утром и в жару днём.",
        "48 случайных суток: 48 драм/кВт·ч в 19:00–21:00.",
        "",
        f"Зенит солнца, Ереван, 21 июня 13:30: {np.rad2deg(zen[0]):.1f}°",
        f"Азимут солнца (180 = юг): {np.rad2deg(az[0]):.1f}°",
        f"Выработка ночью (22–03), кВт·ч суммарно: {night_kwh:.1f}",
        "",
        "Годовая сумма GHI, кВт·ч/м2:",
    ]
    ghi_year = weather.groupby("region_id")["ghi_w_m2"].sum() / 1000 / 2
    name_by_id = {region["region_id"]: region["region_name"] for region in REGIONS}
    for region_id, value in ghi_year.items():
        lines.append(f"  {name_by_id[region_id]}: {value:.0f}")
    lines.append("")
    lines.append("Годовая выработка, кВт·ч на 1 кВт панели:")
    per_year = specific / 2
    for name, value in by_region.items():
        lines.append(f"  {name}: {value / 2:.0f}")
    lines += [
        f"  минимум станции: {per_year.min():.0f}",
        f"  максимум станции: {per_year.max():.0f}",
        "",
        f"Выработано, МВт·ч: {pv / 1000:.1f}",
        f"Продано в сеть, МВт·ч: {sold / 1000:.1f}",
        f"Потери на батарее, МВт·ч: {(pv - sold) / 1000:.1f}",
        f"Продано в часы повышенной цены, МВт·ч: {sold_inc / 1000:.1f}",
        f"Из них выработано прямо в эти часы, МВт·ч: {pv_inc / 1000:.1f}",
        f"Доход станций, драм: {revenue:,.0f}",
        f"Доход если продавать сразу, драм: {baseline:,.0f}",
        f"Дополнительный доход от переноса, драм: {extra:,.0f}",
        f"Дополнительный доход, %: {100 * extra / baseline:.2f}",
        "",
        "Файлы: stations.csv, weather_hourly.csv, prices_hourly.csv,",
        "station_hourly.csv, station_daily.csv",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
