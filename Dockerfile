FROM python:3.12-slim-bookworm

# CBC is the solver PuLP calls for the battery dispatch LP.
RUN apt-get update \
    && apt-get install -y --no-install-recommends coinor-cbc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY .streamlit ./.streamlit

EXPOSE 8000 8501

# Compose overrides this command per service (api or dashboard).
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
