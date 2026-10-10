from src.sql.sql_validator import validate_sql


def test_allow_select():
    outcome = validate_sql(
        "SELECT region, SUM(sales_amount) FROM sales GROUP BY region",
        allowed_tables={"sales"},
    )
    assert outcome.ok
    assert "LIMIT" in outcome.normalized_sql.upper()


def test_reject_drop():
    outcome = validate_sql("DROP TABLE sales", allowed_tables={"sales"})
    assert not outcome.ok


def test_reject_unauthorized_table():
    outcome = validate_sql("SELECT * FROM secrets", allowed_tables={"sales"})
    assert not outcome.ok
    assert "unauthorized" in outcome.message.lower()


def test_reject_multi_statement():
    outcome = validate_sql(
        "SELECT 1; SELECT 2",
        allowed_tables={"sales"},
    )
    assert not outcome.ok


def test_reject_copy():
    outcome = validate_sql("COPY sales TO 'out.csv'", allowed_tables={"sales"})
    assert not outcome.ok
