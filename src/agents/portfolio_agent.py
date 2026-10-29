"""2. Portfolio Analysis Agent - computes real metrics in Python, LLM explains them."""
from src.core.base_agent import BaseAgent
from src.core.state import AgentState
from src.data.portfolio import analyze_portfolio, format_portfolio_report


class PortfolioAgent(BaseAgent):
    key = "portfolio_agent"
    display_name = "Portfolio Analysis Agent"
    system_prompt = """You are the Portfolio Analysis Agent. You review a user's holdings for EDUCATIONAL purposes:
diversification, concentration risk, sector/asset mix, and gain/loss. Walk through the computed metrics, explain
what they mean, and describe general principles (e.g. why concentration raises risk, what rebalancing is).
Do NOT tell the user what to buy or sell; present considerations and trade-offs instead."""

    def gather_context(self, state: AgentState) -> str:
        holdings = state.get("portfolio")
        if not holdings:
            return ("NO PORTFOLIO WAS PROVIDED. Ask the user to supply holdings (ticker, shares, optional "
                    "cost basis per share) and meanwhile explain generally how portfolios are reviewed.")
        return format_portfolio_report(analyze_portfolio(holdings))
