"""
AI Data Analyst — full platform (Phases 1–10).

Natural-language analytics, validated SQL, charts, insights, reports,
multi-dataset / optional Postgres sources, auth & workspaces.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from src.analytics.data_quality import analyze_data_quality
from src.analytics.insights import generate_insights
from src.analytics.nl_pipeline import NLAnalyticsPipeline
from src.analytics.visualization import (
    build_plotly_figure,
    chart_options_for_df,
    recommend_chart,
)
from src.conversation.conversation_manager import ConversationManager
from src.data.data_loader import DataLoadError, load_tabular_file
from src.data.data_profiler import profile_summary_text
from src.data.schema_inspector import schema_prompt_text
from src.database.dataset_registry import DatasetRegistry
from src.database.query_executor import QueryExecutor
from src.llm.llm_service import LLMService
from src.reports.report_generator import ReportGenerator, ReportPayload
from src.security.access_control import Permission, Role
from src.security.audit import audit
from src.security.file_validation import validate_upload
from src.workspace.auth_service import AuthService, User
from src.workspace.workspace_service import WorkspaceService

st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _init_state() -> None:
    defaults = {
        "auth": AuthService(),
        "workspaces": None,
        "user": None,
        "guest": False,
        "workspace_id": None,
        "workspace_role": Role.OWNER.value,
        "registry": DatasetRegistry(),
        "executor": None,
        "conversation": ConversationManager(),
        "llm": LLMService(),
        "pipeline": None,
        "last_result": None,
        "last_sql": "",
        "last_answer": None,
        "nl_history": [],
        "insights_cache": None,
        "quality_cache": None,
        "gemini_user_api_key": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.workspaces is None:
        st.session_state.workspaces = st.session_state.auth.workspaces
    if st.session_state.executor is None:
        st.session_state.executor = QueryExecutor(st.session_state.registry.db)


def _refresh_pipeline() -> None:
    st.session_state.pipeline = NLAnalyticsPipeline(
        executor=st.session_state.executor,
        llm=st.session_state.llm,
        conversation=st.session_state.conversation,
        max_sql_attempts=settings.max_sql_attempts,
    )


def _active_entry():
    return st.session_state.registry.get_active()


def _active_df():
    return st.session_state.registry.get_active_df()


def _register_dataset(
    df: pd.DataFrame,
    name: str,
    table_name: str = "data",
    source_type: str = "upload",
) -> None:
    entry = st.session_state.registry.register(
        df, name=name, table_name=table_name, source_type=source_type
    )
    st.session_state.executor = QueryExecutor(st.session_state.registry.db)
    st.session_state.last_result = None
    st.session_state.last_sql = ""
    st.session_state.last_answer = None
    st.session_state.insights_cache = None
    st.session_state.quality_cache = None
    _refresh_pipeline()

    user: User | None = st.session_state.user
    ws_id = st.session_state.workspace_id
    if user and ws_id and not st.session_state.guest:
        try:
            st.session_state.workspaces.require_permission(
                ws_id, user.id, Permission.UPLOAD
            )
            st.session_state.workspaces.register_dataset_meta(
                workspace_id=ws_id,
                owner_id=user.id,
                name=name,
                table_name=entry.table_name,
                row_count=entry.rows,
                column_count=entry.columns,
                source_type=source_type,
            )
            audit(
                "dataset.register",
                user_id=user.id,
                workspace_id=ws_id,
                details={"table": entry.table_name, "rows": entry.rows},
            )
        except PermissionError as exc:
            st.warning(str(exc))


def _load_sample() -> None:
    path = settings.sample_dataset
    df = load_tabular_file(path)
    _register_dataset(df, name=path.name, table_name="sales", source_type="sample")


def _render_result_block(result_df: pd.DataFrame, key_prefix: str) -> None:
    st.dataframe(result_df, use_container_width=True)
    c1, c2 = st.columns(2)
    csv_bytes = result_df.to_csv(index=False).encode("utf-8")
    c1.download_button(
        "Export CSV",
        data=csv_bytes,
        file_name="query_results.csv",
        mime="text/csv",
        key=f"{key_prefix}_csv",
    )
    xlsx_buf = __import__("io").BytesIO()
    result_df.to_excel(xlsx_buf, index=False, engine="openpyxl")
    c2.download_button(
        "Export Excel",
        data=xlsx_buf.getvalue(),
        file_name="query_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{key_prefix}_xlsx",
    )

    options = chart_options_for_df(result_df)
    choice = st.selectbox("Chart type", options, index=0, key=f"{key_prefix}_chart")
    if choice == "none":
        return
    chart_type = recommend_chart(result_df) if choice == "auto" else choice
    fig = build_plotly_figure(result_df, chart_type=chart_type)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_plotly")
    else:
        st.caption("No chart recommended for this result shape.")


def _auth_gate() -> bool:
    """Return True when the user may use the app."""
    if not settings.auth_enabled:
        st.session_state.guest = True
        return True
    if st.session_state.user is not None or st.session_state.guest:
        return True

    st.title("AI Data Analyst")
    st.caption("Sign in to use a private workspace, or continue as guest for local exploration.")

    tab_login, tab_register, tab_guest = st.tabs(["Login", "Register", "Guest"])
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Sign in", type="primary"):
            try:
                user = st.session_state.auth.login(email, password)
                st.session_state.user = user
                st.session_state.guest = False
                spaces = st.session_state.workspaces.list_workspaces(user.id)
                if spaces:
                    st.session_state.workspace_id = spaces[0].id
                    st.session_state.workspace_role = spaces[0].role
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    with tab_register:
        email = st.text_input("Email", key="reg_email")
        name = st.text_input("Display name", key="reg_name")
        password = st.text_input("Password (min 8 chars)", type="password", key="reg_password")
        if st.button("Create account", type="primary"):
            try:
                user = st.session_state.auth.register(email, password, name)
                st.session_state.user = user
                st.session_state.guest = False
                spaces = st.session_state.workspaces.list_workspaces(user.id)
                if spaces:
                    st.session_state.workspace_id = spaces[0].id
                    st.session_state.workspace_role = spaces[0].role
                st.success("Account created.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    with tab_guest:
        if settings.allow_guest_mode:
            st.info("Guest mode keeps data in this browser session only (no account persistence).")
            if st.button("Continue as guest"):
                st.session_state.guest = True
                st.session_state.user = None
                st.rerun()
        else:
            st.warning("Guest mode is disabled.")
    return False


def _sidebar() -> None:
    st.sidebar.title("AI Data Analyst")
    st.sidebar.caption("Phases 1–10 · Full platform")

    if st.session_state.user:
        st.sidebar.markdown(
            f"**{st.session_state.user.display_name}**  \n`{st.session_state.user.email}`"
        )
        spaces = st.session_state.workspaces.list_workspaces(st.session_state.user.id)
        if spaces:
            labels = {f"{w.name} ({w.role})": w for w in spaces}
            choice = st.sidebar.selectbox("Workspace", list(labels.keys()))
            selected = labels[choice]
            st.session_state.workspace_id = selected.id
            st.session_state.workspace_role = selected.role
        if st.sidebar.button("Logout"):
            audit("user.logout", user_id=st.session_state.user.id)
            st.session_state.user = None
            st.session_state.guest = False
            st.session_state.workspace_id = None
            st.rerun()
    elif st.session_state.guest:
        st.sidebar.info("Guest session")
        if settings.auth_enabled and st.sidebar.button("Sign in instead"):
            st.session_state.guest = False
            st.rerun()

    st.sidebar.subheader("Datasets")
    tables = st.session_state.registry.list_tables()
    if tables:
        active = st.sidebar.selectbox(
            "Active table",
            tables,
            index=tables.index(st.session_state.registry.active_table)
            if st.session_state.registry.active_table in tables
            else 0,
        )
        if active != st.session_state.registry.active_table:
            st.session_state.registry.set_active(active)
            st.session_state.insights_cache = None
            st.session_state.quality_cache = None
            _refresh_pipeline()

    uploaded = st.sidebar.file_uploader(
        "Upload CSV or Excel",
        type=["csv", "xlsx", "xls"],
        help=f"Max {settings.max_upload_mb} MB",
    )
    if uploaded is not None:
        check = validate_upload(uploaded.name, uploaded.size)
        if not check.ok:
            st.sidebar.error(check.message)
        elif st.sidebar.button("Load uploaded file", type="primary"):
            try:
                data = uploaded.getvalue()
                df = load_tabular_file(data, filename=uploaded.name, size_bytes=len(data))
                stem = Path(uploaded.name).stem
                _register_dataset(df, name=uploaded.name, table_name=stem or "data")
                st.sidebar.success(f"Loaded {uploaded.name}")
            except DataLoadError as exc:
                st.sidebar.error(str(exc))

    if st.sidebar.button("Load sample sales data"):
        try:
            _load_sample()
            st.sidebar.success("Sample dataset loaded.")
        except DataLoadError as exc:
            st.sidebar.error(str(exc))

    entry = _active_entry()
    if entry:
        st.sidebar.markdown(
            f"**Active:** `{entry.name}`  \n"
            f"Table: `{entry.table_name}`  \n"
            f"{entry.rows:,} rows × {entry.columns} cols"
        )

    st.sidebar.markdown("---")
    st.sidebar.subheader("LLM")
    provider_choice = st.sidebar.selectbox(
        "Provider",
        options=["gemini", "none", "ollama"],
        index=["gemini", "none", "ollama"].index(
            st.session_state.llm.provider_name
            if st.session_state.llm.provider_name in {"gemini", "none", "ollama"}
            else "gemini"
        ),
    )
    user_api_key = st.session_state.get("gemini_user_api_key", "")
    if provider_choice != st.session_state.llm.provider_name:
        st.session_state.llm = LLMService(
            provider=provider_choice,
            api_key=user_api_key if provider_choice == "gemini" else None,
        )
        _refresh_pipeline()

    if provider_choice == "gemini" and not st.session_state.llm.available:
        input_key = st.sidebar.text_input(
            "Gemini API Key",
            type="password",
            value=user_api_key,
            help="Get a free key from https://aistudio.google.com/",
            key="sidebar_gemini_key",
        )
        if input_key and input_key != user_api_key:
            st.session_state.gemini_user_api_key = input_key
            st.session_state.llm = LLMService(provider="gemini", api_key=input_key)
            _refresh_pipeline()
            st.rerun()

    if st.sidebar.button("Refresh LLM status"):
        st.session_state.llm = LLMService(
            provider=st.session_state.llm.provider_name,
            api_key=st.session_state.get("gemini_user_api_key"),
        )
        _refresh_pipeline()
        st.rerun()

    llm = st.session_state.llm
    if llm.available:
        st.sidebar.success(llm.status_message)
    else:
        st.sidebar.warning(llm.status_message)


def _tab_ask() -> None:
    if _active_entry() is None:
        st.info("Load a dataset from the sidebar to start asking questions.")
        return
    if st.session_state.pipeline is None:
        _refresh_pipeline()

    llm = st.session_state.llm
    if not llm.available:
        st.warning(f"{llm.status_message}\n\nYou can still use the **Query** tab.")

    for item in st.session_state.nl_history:
        with st.chat_message("user"):
            st.write(item["question"])
        with st.chat_message("assistant"):
            st.write(item["explanation"])
            if item.get("sql"):
                with st.expander("Generated SQL"):
                    st.code(item["sql"], language="sql")
            if item.get("success") and item.get("dataframe") is not None:
                st.dataframe(item["dataframe"], use_container_width=True)

    question = st.chat_input("Ask a question about your dataset…")
    st.caption(
        "Try: `What were total sales by region?` · "
        "`Which product generated the highest revenue?` · "
        "`Show the same for the South region` (follow-up)"
    )
    if st.button("Clear conversation"):
        st.session_state.conversation.reset()
        st.session_state.nl_history = []
        st.session_state.last_answer = None
        _refresh_pipeline()
        st.rerun()

    if question:
        entry = _active_entry()
        with st.spinner("Generating SQL and running analysis…"):
            answer = st.session_state.pipeline.ask(
                question,
                schema=entry.schema,
                allowed_tables=st.session_state.registry.list_tables(),
                schema_text=st.session_state.registry.combined_schema_text(),
            )
        st.session_state.last_answer = answer
        st.session_state.nl_history.append(
            {
                "question": question,
                "explanation": answer.explanation or answer.error,
                "sql": answer.validated_sql or answer.sql,
                "success": answer.success,
                "dataframe": answer.dataframe if answer.success else None,
            }
        )
        if answer.success:
            st.session_state.last_result = answer.query
            st.session_state.last_sql = answer.validated_sql or answer.sql
        user = st.session_state.user
        if user and st.session_state.workspace_id and not st.session_state.guest:
            st.session_state.workspaces.save_conversation_turn(
                st.session_state.workspace_id, user.id, "user", question
            )
            st.session_state.workspaces.save_conversation_turn(
                st.session_state.workspace_id,
                user.id,
                "assistant",
                answer.explanation or answer.error,
                sql=answer.validated_sql or answer.sql,
            )
        st.rerun()

    answer = st.session_state.last_answer
    if answer is None:
        return

    st.markdown("---")
    st.subheader("Latest analysis")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Status", "Success" if answer.success else "Failed")
    m2.metric("LLM attempts", answer.llm_attempts)
    m3.metric("Duration (ms)", answer.duration_ms)
    m4.metric("Rows", answer.row_count if answer.success else "—")
    st.markdown("**Explanation**")
    st.write(answer.explanation or answer.error)
    if answer.validated_sql or answer.sql:
        with st.expander("SQL preview", expanded=True):
            st.code(answer.validated_sql or answer.sql, language="sql")
    if answer.success and answer.dataframe is not None:
        st.subheader("Results")
        _render_result_block(answer.dataframe, key_prefix="ask_latest")
        if st.session_state.user and st.session_state.workspace_id:
            title = st.text_input("Save query as", value=answer.question[:80])
            if st.button("Save to workspace"):
                st.session_state.workspaces.save_query(
                    st.session_state.workspace_id,
                    st.session_state.user.id,
                    title or "Saved query",
                    answer.validated_sql or answer.sql,
                    question=answer.question,
                )
                st.success("Saved.")
    elif not answer.success:
        st.error(answer.error or "Analysis failed.")


def _tab_overview() -> None:
    entry = _active_entry()
    if entry is None:
        st.info("Upload a dataset or load the sample sales data from the sidebar.")
        return
    profile = entry.profile
    st.markdown(profile_summary_text(profile))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{profile['rows']:,}")
    c2.metric("Columns", profile["columns"])
    c3.metric("Missing values", f"{profile['missing_values']:,}")
    c4.metric("Duplicate rows", f"{profile['duplicate_rows']:,}")
    st.subheader("Preview")
    st.dataframe(_active_df().head(20), use_container_width=True)
    st.subheader("Schema")
    st.code(schema_prompt_text(entry.schema), language="text")
    if len(st.session_state.registry.entries) > 1:
        st.subheader("Registered tables")
        st.write(", ".join(st.session_state.registry.list_tables()))


def _tab_profile() -> None:
    entry = _active_entry()
    if entry is None:
        st.info("Load a dataset to see its profile.")
        return
    profile = entry.profile
    st.write(
        f"Numeric: {', '.join(profile['numeric_columns']) or '—'}  \n"
        f"Categorical: {', '.join(profile['categorical_columns']) or '—'}  \n"
        f"Datetime: {', '.join(profile['datetime_columns']) or '—'}"
    )
    details = pd.DataFrame(profile["column_details"])
    show_cols = [
        c
        for c in [
            "name",
            "inferred_type",
            "dtype",
            "missing_count",
            "missing_pct",
            "unique_count",
            "min",
            "max",
            "mean",
            "median",
        ]
        if c in details.columns
    ]
    st.dataframe(details[show_cols], use_container_width=True, hide_index=True)


def _tab_query() -> None:
    if _active_entry() is None:
        st.info("Load a dataset before running SQL.")
        return
    table = st.session_state.registry.active_table
    default_sql = st.session_state.last_sql or f'SELECT * FROM "{table}" LIMIT 20;'
    sql = st.text_area("SQL (read-only SELECT)", value=default_sql, height=160)
    if st.button("Run query", type="primary"):
        result = st.session_state.executor.execute(
            sql, allowed_tables=st.session_state.registry.list_tables()
        )
        st.session_state.last_result = result
        st.session_state.last_sql = sql
    result = st.session_state.last_result
    if result is None:
        return
    m1, m2, m3 = st.columns(3)
    m1.metric("Status", "Success" if result.success else "Failed")
    m2.metric("Duration (ms)", result.duration_ms)
    m3.metric("Rows", result.row_count if result.success else "—")
    if result.validated_sql:
        with st.expander("Validated SQL", expanded=True):
            st.code(result.validated_sql, language="sql")
    if not result.success:
        st.error(result.error)
        return
    if result.truncated:
        st.warning(f"Results truncated to {settings.max_result_rows:,} rows.")
    _render_result_block(result.dataframe, key_prefix="manual_query")


def _tab_insights() -> None:
    df = _active_df()
    entry = _active_entry()
    if df is None or entry is None:
        st.info("Load a dataset to generate insights.")
        return
    if st.button("Refresh insights", type="primary") or st.session_state.insights_cache is None:
        st.session_state.insights_cache = generate_insights(df, entry.profile)
        st.session_state.quality_cache = analyze_data_quality(df)

    insights = st.session_state.insights_cache
    quality = st.session_state.quality_cache

    st.subheader("Data quality")
    st.metric("Quality score", f"{quality['score']}/100")
    st.json(quality["checks"])
    if quality["issues"]:
        st.dataframe(pd.DataFrame(quality["issues"]), use_container_width=True)
    else:
        st.success("No major data-quality issues detected.")
    st.caption("Issues are reported only — cleaning requires your explicit action.")

    st.subheader("Automated insights")
    for line in insights["summary"]:
        st.write(f"- {line}")

    st.subheader("Suggested questions")
    for q in insights["suggested_questions"]:
        if st.button(q, key=f"sug_{hash(q)}"):
            st.session_state._pending_question = q
            st.info(f"Switch to **Ask** and submit: {q}")

    for block in insights.get("category_comparisons", []):
        if "table" in block:
            st.subheader("Category comparison")
            st.dataframe(block["table"], use_container_width=True)
            fig = build_plotly_figure(block["table"], chart_type="bar")
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="insights_cat_plotly")
            break

    for block in insights.get("trends", []):
        if "table" in block:
            st.subheader("Trend")
            st.dataframe(block["table"], use_container_width=True)
            fig = build_plotly_figure(block["table"], chart_type="line")
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="insights_trend_plotly")
            break


def _tab_reports() -> None:
    entry = _active_entry()
    if entry is None:
        st.info("Load a dataset and run an analysis first.")
        return
    answer = st.session_state.last_answer
    title = st.text_input("Report title", value="Analytical Report")
    question = st.text_input(
        "Business question",
        value=(answer.question if answer else ""),
    )
    include_insights = st.checkbox("Include automated insights", value=True)
    if st.button("Generate report", type="primary"):
        insights_list = []
        follow_ups = []
        if include_insights:
            cached = st.session_state.insights_cache or generate_insights(
                _active_df(), entry.profile
            )
            insights_list = cached.get("summary", [])
            follow_ups = cached.get("suggested_questions", [])
        payload = ReportPayload(
            title=title,
            question=question,
            dataset_name=entry.name,
            table_name=entry.table_name,
            sql=(answer.validated_sql or answer.sql) if answer else st.session_state.last_sql,
            explanation=(answer.explanation if answer else ""),
            dataframe=(
                answer.dataframe
                if answer and answer.dataframe is not None
                else (
                    st.session_state.last_result.dataframe
                    if st.session_state.last_result and st.session_state.last_result.success
                    else None
                )
            ),
            profile_summary=profile_summary_text(entry.profile),
            insights=insights_list,
            follow_ups=follow_ups,
        )
        gen = ReportGenerator()
        paths = gen.save(payload)
        st.success("Report generated.")
        for fmt, path in paths.items():
            data = path.read_bytes()
            mime = {
                "md": "text/markdown",
                "html": "text/html",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }[fmt]
            st.download_button(
                f"Download {fmt.upper()}",
                data=data,
                file_name=path.name,
                mime=mime,
                key=f"dl_{fmt}",
            )
        user = st.session_state.user
        if user and st.session_state.workspace_id and not st.session_state.guest:
            for fmt, path in paths.items():
                st.session_state.workspaces.save_report_meta(
                    st.session_state.workspace_id,
                    user.id,
                    title,
                    str(path),
                    fmt,
                )


def _tab_sources() -> None:
    st.subheader("Multiple datasets")
    st.write(
        "Upload several files from the sidebar — they register as separate DuckDB tables. "
        "Natural-language questions can reference any registered table."
    )
    if st.session_state.registry.entries:
        rows = [
            {
                "table": e.table_name,
                "name": e.name,
                "source": e.source_type,
                "rows": e.rows,
                "columns": e.columns,
                "active": e.table_name == st.session_state.registry.active_table,
            }
            for e in st.session_state.registry.entries.values()
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("PostgreSQL source (optional)")
    if not settings.postgres_enabled:
        st.info(
            "Set `POSTGRES_ENABLED=true` and `POSTGRES_DSN=postgresql://user:pass@host/db` "
            "in `.env` to enable."
        )
        return
    try:
        from src.database.postgres_source import PostgresSource, PostgresSourceError

        src = PostgresSource()
        st.json(src.connection_summary())
        tables = src.list_tables()
        names = [t.full_name for t in tables]
        pick = st.selectbox("Table to import", names) if names else None
        if pick and st.button("Import table into DuckDB"):
            schema, table = pick.split(".", 1)
            df = src.fetch_table(table, schema=schema)
            _register_dataset(df, name=pick, table_name=table, source_type="postgres")
            st.success(f"Imported {pick} ({len(df):,} rows).")
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))


def _tab_workspace() -> None:
    if st.session_state.guest or not st.session_state.user:
        st.info("Sign in to manage workspaces, members, saved queries, and reports.")
        return
    user = st.session_state.user
    ws_id = st.session_state.workspace_id
    st.write(f"Role in current workspace: **{st.session_state.workspace_role}**")

    new_name = st.text_input("Create workspace")
    if st.button("Create") and new_name.strip():
        ws = st.session_state.workspaces.create_workspace(new_name.strip(), user.id)
        st.session_state.workspace_id = ws.id
        st.session_state.workspace_role = ws.role
        st.success(f"Created {ws.name}")
        st.rerun()

    st.subheader("Invite member")
    email = st.text_input("Member email")
    role = st.selectbox(
        "Role",
        [Role.VIEWER.value, Role.ANALYST.value, Role.ADMINISTRATOR.value],
    )
    if st.button("Add member") and email and ws_id:
        try:
            st.session_state.workspaces.add_member(ws_id, user.id, email, role)
            st.success("Member updated.")
        except (ValueError, PermissionError) as exc:
            st.error(str(exc))

    if ws_id:
        st.subheader("Saved queries")
        saved = st.session_state.workspaces.list_saved_queries(ws_id)
        if saved:
            st.dataframe(pd.DataFrame(saved), use_container_width=True)
        st.subheader("Saved reports")
        reports = st.session_state.workspaces.list_reports(ws_id)
        if reports:
            st.dataframe(pd.DataFrame(reports), use_container_width=True)
        st.subheader("Registered dataset metadata")
        meta = st.session_state.workspaces.list_datasets(ws_id)
        if meta:
            st.dataframe(pd.DataFrame(meta), use_container_width=True)


def main() -> None:
    _init_state()
    if not _auth_gate():
        return
    _sidebar()
    if st.session_state.pipeline is None and _active_entry() is not None:
        _refresh_pipeline()

    st.title("AI Data Analyst")
    st.caption(
        "Natural-language analytics with validated SQL, charts, insights, reports, "
        "and workspace controls."
    )

    tabs = st.tabs(
        [
            "Ask",
            "Overview",
            "Profile",
            "Query",
            "Insights",
            "Reports",
            "Sources",
            "Workspace",
        ]
    )
    with tabs[0]:
        _tab_ask()
    with tabs[1]:
        _tab_overview()
    with tabs[2]:
        _tab_profile()
    with tabs[3]:
        _tab_query()
    with tabs[4]:
        _tab_insights()
    with tabs[5]:
        _tab_reports()
    with tabs[6]:
        _tab_sources()
    with tabs[7]:
        _tab_workspace()


if __name__ == "__main__":
    main()
