## Meteomatics API quickstart

This repo includes a small Python script to fetch weather data from the Meteomatics Weather API and print a concise summary of the response.

API docs: [Getting started with the Meteomatics Weather API](https://www.meteomatics.com/en/api/getting-started/)

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set credentials via environment variables (recommended):

```bash
export METEOMATICS_USERNAME="kist_raul"
export METEOMATICS_PASSWORD="6DtjdFQ9V5DpHe90pW60"
```

### Fetch 24h hourly data for Berlin (default)

```bash
python scripts/fetch_meteomatics.py
```

This will:

- Request parameters `t_2m:C,precip_1h:mm,wind_speed_10m:ms`
- Time range: now (UTC) to now+24h at hourly steps
- Location: Berlin (52.520551, 13.461804)
- Save raw JSON to `data/meteomatics_<timestamp>.json`
- Print a summary with counts, time range, min/max values, and a few samples

### Customizing the request

```bash
python scripts/fetch_meteomatics.py \
  --lat 40.7128 \
  --lon -74.0060 \
  --hours 12 \
  --interval PT30M \
  --parameters t_2m:C,precip_1h:mm,wind_speed_10m:ms \
  --out data/nyc_12h.json
```

You can also pass credentials explicitly:

```bash
python scripts/fetch_meteomatics.py --username your_username --password your_password
```

### Notes

- The script uses HTTP Basic Auth against `https://api.meteomatics.com`.
- Time range is constructed relative to current UTC, rounded to the hour.
- Response parsing expects Meteomatics JSON shape with `data → coordinates → dates`.

## Web map (Google Maps + Meteomatics CSV)

A lightweight web app under `web/` visualizes Meteomatics CSV data on Google Maps as either a heatmap or colored circles.

### Run locally

```bash
cd /Users/raul.kist/Code/rkist/nasa-weather
python3 -m http.server 8080
# then open http://localhost:8080/web/
```

Default CSV URL is `../data/saopaulo_20251001_20251002_0p05deg.csv`. You can change the URL and click "Load CSV", then select parameter, timestamp, and view mode.

The map uses the provided Google Maps API key embedded in `web/index.html`.


