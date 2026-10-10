from src.llm.base import LLMProvider, LLMResponse
from src.llm.llm_service import LLMService
from src.sql.sql_generator import SQLGenerator, extract_sql


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def complete(self, system: str, user: str) -> LLMResponse:
        text = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return LLMResponse(text=text, model="fake", provider="fake")


def test_extract_sql_from_fence():
    text = "Sure!\n```sql\nSELECT region FROM sales\n```\nHope that helps."
    assert extract_sql(text).upper().startswith("SELECT")


def test_extract_cannot_answer():
    text = "CANNOT_ANSWER: no satisfaction column"
    assert extract_sql(text).startswith("CANNOT_ANSWER")


def test_generate_valid_sql():
    provider = FakeProvider(
        [
            "SELECT region, SUM(sales_amount) AS total FROM sales GROUP BY region",
        ]
    )
    llm = LLMService(provider="fake", provider_instance=provider)
    gen = SQLGenerator(llm, max_attempts=2)
    result = gen.generate(
        schema_text="Table: sales\nColumns:\n  - region: VARCHAR\n  - sales_amount: DOUBLE",
        question="Total sales by region",
        allowed_tables={"sales"},
    )
    assert result.ok
    assert "sales" in result.sql.lower()
    assert result.attempts == 1


def test_generate_retries_on_bad_sql():
    provider = FakeProvider(
        [
            "DROP TABLE sales",
            "SELECT region FROM sales",
        ]
    )
    llm = LLMService(provider="fake", provider_instance=provider)
    gen = SQLGenerator(llm, max_attempts=3)
    result = gen.generate(
        schema_text="Table: sales\nColumns:\n  - region: VARCHAR",
        question="List regions",
        allowed_tables={"sales"},
    )
    assert result.ok
    assert result.attempts == 2


def test_cannot_answer():
    provider = FakeProvider(["CANNOT_ANSWER: no NPS column in schema"])
    llm = LLMService(provider="fake", provider_instance=provider)
    gen = SQLGenerator(llm)
    result = gen.generate(
        schema_text="Table: sales\nColumns:\n  - region: VARCHAR",
        question="What is customer satisfaction?",
        allowed_tables={"sales"},
    )
    assert not result.ok
    assert result.cannot_answer
