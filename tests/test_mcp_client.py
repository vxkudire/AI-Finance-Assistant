import pytest

pytest.importorskip("mcp")

from src.core.mcp_client import call_mcp_tools


def test_workflow_calls_finance_mcp_tools_in_one_session():
    results = call_mcp_tools([
        ("project_future_value", {
            "present": 1000, "monthly": 100, "annual_rate": 0, "years": 1,
        }),
        ("required_monthly_contribution", {
            "target": 1200, "present": 0, "annual_rate": 0, "years": 1,
        }),
    ])

    assert results == [
        {"future_value": 2200.0},
        {"required_monthly_contribution": 100.0},
    ]


def test_workflow_surfaces_mcp_tool_errors():
    with pytest.raises(RuntimeError, match="MCP tool 'get_quotes' failed"):
        call_mcp_tools([("get_quotes", {"tickers": ["../invalid"]})])
