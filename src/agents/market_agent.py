"""3. Market Analysis Agent - live quotes injected into the prompt."""
from src.core.config import load_config
from src.core.state import AgentState
from src.core.base_agent import BaseAgent
from src.data.market_data import format_quotes, get_quotes
from src.utils.helpers import extract_tickers, last_user_text


class MarketAgent(BaseAgent):
    key = "market_agent"
    display_name = "Market Analysis Agent"
    system_prompt = """You are the Market Analysis Agent. You explain what is happening in markets using the live
quote data provided: describe moves, put them in context (index vs. single stock, daily noise vs. trend) and
explain the concepts involved (volatility, valuation, volume, sectors). Quote only numbers present in the live
data and mention they may be delayed. Never predict prices or recommend trades."""

    def gather_context(self, state: AgentState) -> str:
        tickers = extract_tickers(last_user_text(state["messages"])) or load_config()["data"]["default_indices"]
        return format_quotes(get_quotes(tickers))
