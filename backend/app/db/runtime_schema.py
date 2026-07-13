from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _column_names(engine: Engine, table_name: str) -> set[str]:
    inspector = inspect(engine)
    return {column["name"] for column in inspector.get_columns(table_name)}


def ensure_runtime_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        analysis_job_columns = _column_names(engine, "analysis_jobs") if inspect(engine).has_table("analysis_jobs") else set()
        if "asset_impact_summary" not in analysis_job_columns:
            conn.execute(text("ALTER TABLE analysis_jobs ADD COLUMN asset_impact_summary TEXT DEFAULT ''"))
        if "asset_impact_details" not in analysis_job_columns:
            conn.execute(text("ALTER TABLE analysis_jobs ADD COLUMN asset_impact_details JSON DEFAULT '{}'"))

        agent_execution_columns = _column_names(engine, "agent_executions") if inspect(engine).has_table("agent_executions") else set()
        if "retry_count" not in agent_execution_columns:
            conn.execute(text("ALTER TABLE agent_executions ADD COLUMN retry_count INTEGER DEFAULT 1"))
