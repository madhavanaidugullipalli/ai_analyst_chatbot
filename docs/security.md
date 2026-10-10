# Security

## Controls

| Control | Where |
|---------|--------|
| SQL allowlist / forbid DML | `src/sql/query_policy.py`, `sql_validator.py` |
| Table sandbox | DatasetRegistry allowlist per execute |
| Upload limits | `file_validation.py` |
| Password hashing | PBKDF2-SHA256 in `passwords.py` |
| RBAC | `access_control.py` + workspace membership |
| Audit trail | `logs/audit.log` via `audit.py` |
| Secrets | `.env` / environment variables |

## Roles

- **Owner** — full workspace control
- **Administrator** — members + sources
- **Analyst** — upload + analyze
- **Viewer** — query + reports only

## Important

Prompt engineering is **not** the security boundary. Every query is parsed and policy-checked before DuckDB execution. For production multi-user deployments, change `SESSION_SECRET`, disable guest mode if needed, and put the app behind HTTPS.
