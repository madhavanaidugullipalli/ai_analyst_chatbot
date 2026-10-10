from pathlib import Path

from src.analytics.nl_pipeline import NLAnalyticsPipeline
from src.data.data_loader import load_tabular_file
from src.data.schema_inspector import schema_from_dataframe
from src.database.database import AnalyticsDatabase
from src.database.query_executor import QueryExecutor
from src.llm.base import LLMProvider, LLMResponse
from src.llm.llm_service import LLMService

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self) -> None:
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def complete(self, system: str, user: str) -> LLMResponse:
        self.calls += 1
        if "Explain" in system or "explain" in system.lower() or "Ground every" in system:
            return LLMResponse(
                text="East and other regions appear in the totals shown in the result.",
                model="scripted",
                provider="scripted",
            )
        return LLMResponse(
            text=(
                "SELECT region, SUM(sales_amount) AS total_sales "
                "FROM sales GROUP BY region ORDER BY total_sales DESC"
            ),
            model="scripted",
            provider="scripted",
        )


def test_pipeline_ask_end_to_end():
    df = load_tabular_file(SAMPLE)
    db = AnalyticsDatabase()
    db.register_dataframe(df, "sales")
    executor = QueryExecutor(db)
    llm = LLMService(provider="scripted", provider_instance=ScriptedProvider())
    pipeline = NLAnalyticsPipeline(executor=executor, llm=llm)
    schema = schema_from_dataframe(df, "sales")

    answer = pipeline.ask(
        "What were total sales by region?",
        schema=schema,
        allowed_tables=["sales"],
    )
    assert answer.success
    assert answer.row_count == 4
    assert answer.dataframe is not None
    assert "total_sales" in answer.dataframe.columns
    assert answer.explanation
    db.close()
