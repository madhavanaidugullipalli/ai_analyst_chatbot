# AI Data Analyst

AI-powered natural-language analytics platform: upload structured data, ask questions in plain language, inspect validated SQL, view DuckDB results, charts, insights, and exportable reports — with optional auth/workspaces.

## Status: Phases 1–10

| Phase | Feature | Status |
|------|---------|--------|
| 1 | Upload, profile, DuckDB SQL | Done |
| 2 | LLM NL→SQL + explanations (Ollama/Gemini) | Done |
| 3 | SQLGlot policy, audit logs, tests | Done |
| 4 | Plotly charts + CSV/Excel export | Done |
| 5 | Conversational follow-ups + clarification | Done |
| 6 | Automated insights + data quality | Done |
| 7 | Markdown / HTML / Excel reports | Done |
| 8 | Multi-dataset + optional Postgres import | Done |
| 9 | Auth, workspaces, roles, saved queries | Done |
| 10 | Docker, FastAPI API, docs | Done |

## Quick start

### 1. Clone & Set Up Virtual Environment

**Windows (PowerShell):**
```powershell
git clone https://github.com/madhavanaidugullipalli/ai_analyst_chatbot.git
cd ai_analyst_chatbot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

**Linux / macOS (Bash):**
```bash
git clone https://github.com/madhavanaidugullipalli/ai_analyst_chatbot.git
cd ai_analyst_chatbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Run Application

```bash
streamlit run app.py
```

1. Continue as **guest** or register an account.
2. Click **Load sample sales data**.
3. Open **Ask** and try: `What were total sales by region?`
4. Explore **Insights**, **Reports**, and **Sources**.

### LLM setup

- **Ollama:** install Ollama, pull a model (`ollama pull llama3.2`), set `LLM_PROVIDER=ollama`.
- **Gemini:** set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY` in `.env`.
- **None:** SQL tab still works without an LLM.

### Optional API

```powershell
uvicorn api.main:app --reload --port 8000
```

- `GET /health`
- `POST /datasets/sample`
- `POST /ask` `{ "question": "..." }`
- `POST /sql/execute` `{ "sql": "SELECT ..." }`

### Docker

```powershell
docker compose up --build
```

## Tests

```powershell
pytest -q
```

## Security

- LLM output is never executed until SQLGlot validation + table allowlisting.
- DML/DDL and dangerous DuckDB features are rejected.
- Uploads are size/extension-checked; app metadata uses PBKDF2 password hashes.
- Secrets live in `.env` only.

See `docs/architecture.md` and `docs/security.md`.
