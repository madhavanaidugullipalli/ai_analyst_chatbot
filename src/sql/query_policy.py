"""Allowed SQL operations for analytical queries."""

from __future__ import annotations

# Statement types that are never allowed
FORBIDDEN_STATEMENT_TYPES = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "TRUNCATE",
        "REPLACE",
        "MERGE",
        "GRANT",
        "REVOKE",
        "ATTACH",
        "DETACH",
        "COPY",
        "EXPORT",
        "IMPORT",
        "INSTALL",
        "LOAD",
        "PRAGMA",
        "SET",
        "RESET",
        "CALL",
        "EXECUTE",
        "TRANSACTION",
        "COMMIT",
        "ROLLBACK",
        "VACUUM",
    }
)

# Allowed root statement types
ALLOWED_STATEMENT_TYPES = frozenset({"SELECT", "WITH", "DESCRIBE", "SHOW", "EXPLAIN"})

# Forbidden function / keyword patterns (case-insensitive substring checks as backup)
FORBIDDEN_KEYWORDS = frozenset(
    {
        "ATTACH",
        "COPY",
        "INSTALL",
        "LOAD_EXTENSION",
        "READ_CSV",
        "READ_PARQUET",
        "READ_JSON",
        "GLOB",
        "PRAGMA",
    }
)
