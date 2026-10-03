# VoltSync VPP

24-часовой диспетчер домашней или небольшой коммерческой батареи: **store, use or sell**. Приложение строит синтетический день для площадки в Ереване (солнце, потребление, тарифы в AMD) и решает линейную программу арбитража BESS солвером CBC.

## Стек

- FastAPI — прогноз и оптимизация
- PuLP + CBC — линейная модель заряда, разряда, собственного потребления и экспорта
- Streamlit + Plotly — тёмный CleanTech-дашборд
- Docker Compose — API и дашборд из одного образа

## Запуск на сервере

Из корня репозитория:

```bash
docker compose up --build -d
```

- Дашборд: http://localhost:8501
- API и Swagger: http://localhost:8000/docs
- Проверка: http://localhost:8000/health

Остановка: `docker compose down`.

## Локальный запуск

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Второй терминал из того же каталога:

```powershell
.venv\Scripts\Activate.ps1
streamlit run frontend/app.py
```

Локально CBC приезжает с зависимостью `pulp[cbc]`. В Docker-образе дополнительно ставится системный пакет `coinor-cbc`, его и вызывает PuLP, если бинарник есть в `PATH`.

Прогон всех пресетов без сервера:

```bash
python -m backend.optimizer
```

## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/health` | Состояние сервиса и доступность CBC |
| GET | `/api/v1/scenarios` | Пресеты дня и описания тарифов |
| GET | `/api/v1/plan?scenario=yerevan_summer` | Прогноз + оптимальный план |
| POST | `/api/v1/plan` | То же, с полным переопределением site и battery |
| POST | `/api/v1/forecast` | Только 24 часа синтетики |
| POST | `/api/v1/optimize` | Оптимизация уже готового прогноза |

Пресеты: `yerevan_summer`, `cloudy_day`, `evening_export_spike`, `pv_surplus`.

Тарифы демонстрационные. Годовая экономия на дашборде — этот день, повторённый 365 раз, а не годовая симуляция.
