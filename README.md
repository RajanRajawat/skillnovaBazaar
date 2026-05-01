# SkillNova Bazaar

SkillNova Bazaar now runs as a plain `HTML/CSS/JavaScript` frontend with a separate `FastAPI` backend. The frontend can be hosted independently on Vercel or a static server, while the backend exposes only `/api/*`.

## Project Structure

```text
/
|-- App/
|   |-- frontend/
|   |   |-- index.html
|   |   |-- styles.css
|   |   |-- api.js
|   |   |-- charts.js
|   |   `-- app.js
|   `-- backend/
|       |-- app.py
|       |-- routes/
|       |   `-- api.py
|       |-- services/
|       |   |-- market_data.py
|       |   |-- news_service.py
|       |   |-- pattern_detector.py
|       |   |-- prediction_engine.py
|       |   `-- web_search.py
|       |-- models/
|       |   |-- pattern_definitions.py
|       |   `-- unknown_store.py
|       |-- config/
|       |   `-- settings.py
|       `-- data/
|           |-- instruments_seed.json
|           `-- unknown_patterns.json
|-- requirements.txt
|-- .env.example
`-- README.md
```

## Run Locally

Start the backend:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn App.backend.app:app --host 127.0.0.1 --port 8000 --reload
```

Serve the frontend separately:

```powershell
cd App/frontend
python -m http.server 3000
```

Open `http://127.0.0.1:3000`.

You can also start the backend module directly:

```powershell
.\.venv\Scripts\python.exe -m App.backend.app
```

## Configuration

Copy `.env.example` to `.env` and fill in only the values you need.

- `CORS_ALLOW_ORIGINS` should include your frontend origins, or `*` while you are still wiring deployment.
- `MONGO_URI` is required for authentication and should point at your MongoDB cluster.
- `MONGO_DB_NAME` is used when the Mongo URI does not already include a database name.
- `JWT_SECRET` signs bearer tokens for login sessions.
- `NEWSAPI_KEY` or `NEWS_API_KEY` enables NewsAPI headlines.
- Without a news API key, the app falls back to Google News RSS.
- `SERPAPI_KEY` or `BING_SEARCH_API_KEY` enables runtime pattern-name discovery.
- `MARKET_PROVIDER=offline` forces deterministic fallback market data.

## Authentication

The frontend now uses protected client-side routes:

- `#/login`
- `#/register`
- `#/app`

The backend exposes:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

Existing market, pattern, and news endpoints require `Authorization: Bearer <token>`. Password hashes are stored in MongoDB and are never returned in API responses.

## Deploy

Deploy the backend to Render from the repo root using the included `render.yaml`.

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn App.backend.app:app --host 0.0.0.0 --port $PORT`
- Health check: `/api/health`
- Default CORS regex already allows `https://*.vercel.app`

Deploy the frontend to Vercel with `App/frontend` as the project root.

- Vercel will pick up [`App/frontend/vercel.json`](App/frontend/vercel.json)
- The frontend uses `http://127.0.0.1:8000/api` locally and `/api` when deployed
- `vercel.json` rewrites `/api/*` to the Render backend so the browser can stay on the Vercel origin
- Render backend URL is `https://skillnovabazaar.onrender.com`, and `App/frontend/vercel.json` rewrites `/api/*` there

Render note: `App/backend/data/unknown_patterns.json` and `.yfinance_cache` are file-backed. On Render they are ephemeral unless you add persistent storage or move that state to an external database/store.

## API Endpoints

- `GET /api/health` returns service status and detector coverage.
- `GET /api/instruments?q=RELIANCE` searches equities, indices, futures, and options.
- `GET /api/market-data?symbol=NIFTY50&range=6mo&interval=1d` returns OHLCV candles and quote data.
- `POST /api/analyze` returns candles, detected patterns, prediction, news, and master pattern data.
- `GET /api/patterns` returns the encoded patterns plus runtime discovered or unknown patterns.
- `PUT /api/patterns/unknown/{id}` renames an unknown pattern.

## Notes

The frontend remains framework-free and the backend keeps the existing market-data, news, pattern-detection, and prediction logic. Financial predictions are model outputs, not investment advice.
