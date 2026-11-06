"""5. News Synthesizer Agent - pulls RSS headlines, summarizes, and contextualizes them."""
from src.core.base_agent import BaseAgent
from src.core.config import load_config
from src.core.mcp_client import call_mcp_tools
from src.core.state import AgentState
from src.data.news_data import format_news
from src.utils.helpers import last_user_text, topic_terms


class NewsAgent(BaseAgent):
    key = "news_agent"
    display_name = "News Synthesizer Agent"
    system_prompt = """You are the News Synthesizer Agent. Using ONLY the headlines provided, summarize the key
stories, group related items into themes, and explain why they may matter to markets or households (context,
jargon, possible second-order effects). Attribute each point to its source name. Do not invent facts that are
not in the news items, and separate what happened from your explanation of why it may matter."""

    def gather_context(self, state: AgentState) -> str:
        data = load_config()["data"]
        result = call_mcp_tools([("get_financial_news", {
            "terms": topic_terms(last_user_text(state["messages"])),
            "limit": data["max_news_items"],
        })])[0]
        context = format_news(result["items"])
        if result.get("some_feeds_failed"):
            context += "\nSome news sources are unavailable; tell the user."
        return context
