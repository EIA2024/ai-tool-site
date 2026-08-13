"""Schema/validation contract tests.

SQLite (used in tests) does not enforce VARCHAR length, so a column that is
too short for the limit the tool accepts only fails on Postgres in
production. These assertions pin the DB column widths to be at least the
largest value each tool/API layer will accept.
"""

from sqlalchemy import String

from app.tool_plugins.chat_tool.models import ChatMessage, ChatSession
from app.tool_plugins.code_agent_flow_viz.models import AgentPracticeRecord
from app.tool_plugins.task_decomposer.models import TaskAnalysisHistory


def _length(column) -> int:
    col_type = column.type
    assert isinstance(col_type, String)
    assert col_type.length is not None
    return col_type.length


def test_stage_key_column_holds_tool_maximum():
    # CodeAgentFlowVizTool._save validates stage_key up to 64 chars; the
    # column must be at least that wide or Postgres raises on valid input.
    assert _length(AgentPracticeRecord.__table__.c.stage_key) >= 64


def test_chat_title_column_holds_api_maximum():
    # CreateSessionRequest caps title at 255.
    assert _length(ChatSession.__table__.c.title) >= 255


def test_analysis_columns_hold_tool_maxima():
    # AnalyzeTaskInput caps task_type at 20 and model at 64.
    assert _length(TaskAnalysisHistory.__table__.c.task_type) >= 20
    assert _length(TaskAnalysisHistory.__table__.c.model_name) >= 64
    # "low"/"medium"/"high" fit comfortably in 10.
    assert _length(TaskAnalysisHistory.__table__.c.risk_level) >= 10


def test_chat_message_role_column_holds_longest_role():
    # "assistant" is the longest valid role.
    assert _length(ChatMessage.__table__.c.role) >= len("assistant")
