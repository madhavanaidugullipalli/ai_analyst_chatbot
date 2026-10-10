# Architecture

```
User → Streamlit (app.py)  or  FastAPI (api/main.py)
         │
         ├─ Auth / Workspace (SQLite app DB)
         ├─ DatasetRegistry → DuckDB (analytical)
         ├─ NLAnalyticsPipeline
         │     ├─ ConversationManager (follow-ups)
         │     ├─ LLMService (Ollama | Gemini)
         │     ├─ SQLGenerator → SQLValidator (SQLGlot)
         │     └─ QueryExecutor
         ├─ Insights / Data quality
         ├─ Visualization (Plotly)
         └─ ReportGenerator (MD / HTML / XLSX)
```

## Data separation

| Store | Purpose |
|-------|---------|
| DuckDB (session) | Analytical tables from uploads / sample / Postgres import |
| SQLite `data/app.db` | Users, workspaces, members, dataset metadata, saved queries, reports |

## Request flow (Ask)

1. Auth gate (or guest).
2. Enrich follow-up questions with prior SQL/context.
3. LLM proposes SQL from schema + history.
4. Validator enforces read-only policy and allowed tables.
5. DuckDB executes; results never come from LLM guesses.
6. LLM (or fallback) explains grounded in the result preview.
7. UI shows SQL, table, chart; optional report export.
