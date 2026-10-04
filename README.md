# VoltSynch

Solar energy from home stations, sold in the hour the grid needs it.

Live site: [voltsynch.world](https://voltsynch.world)

## Idea

Solar output peaks at noon, when the grid needs it least. So the grid announces in advance the hours in which it buys energy. In the other hours each station's relay sends its output to a battery. When buying opens, the station sells what it stored. VoltSynch arranges the sale and keeps 10% of the price.

| Hour | Price per 1 kWh |
| --- | --- |
| Grid not buying | 0 AMD |
| Ordinary buying | about 25 AMD |
| Peak buying | 26–50 AMD |

These prices are a scenario. The regulator's (PSRC) tariff is not applied here.

## Three entrances

- **Power grid** sees how much energy stayed out of the grid at noon and how much the batteries delivered at the peak.
- **Solar station** sees its sales, its income, and the extra amount the battery earned.
- **Coordinator** sees all 30 stations together and the service's 10%.

## ML

An ML model forecasts each station's hourly generation from weather, irradiance and panel parameters. From that forecast the site works out whether the battery will be charged by the selling hour. The model does not set prices.

It is trained on 2024 and tested on 2025. Mean daylight error is 0.074 kWh, against 0.205 kWh for a "same month, same hour" baseline. The actual-vs-forecast charts add a small spread for readability.

## Data

All data is synthetic: 30 stations in Yerevan, Shirak, Lori, Gegharkunik and Syunik, hourly for 2024–2025. Annual consumption is scaled to the public figure of 7.90 TWh for 2024. No hourly data from the grid operator is used.

## Run

Requires Python 3.10 or 3.11.

```bash
pip install -r requirements.txt
python server.py
```

The site opens at http://127.0.0.1:8000, the presentation at `/presentation`.

With Docker:

```bash
docker compose up --build -d
```

`python generate_market_data.py` regenerates the data. It overwrites `data/` and deletes the trained model, so the server retrains it on the next start.

## Layout

- `server.py` — FastAPI API and the ML model
- `web/` — site and presentation
- `data/` — synthetic data
- `generate_market_data.py` — data generator
- `solar_exchange.ipynb` — notebook with the data and training
