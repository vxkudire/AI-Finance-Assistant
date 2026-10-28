"""5. News Synthesizer Agent - pulls RSS headlines, summarises and contextualises them."""
from src.core.base_agent import BaseAgent
from src.core.config import load_config
from src.core.state import AgentState
from src.data.news_data import fetch_news, format_news
from src.utils.helpers import last_user_text, topic_terms


class NewsAgent(BaseAgent):
    key = "news"
    display_name = "News Synthesizer"
    system_prompt = """You are the News Synthesizer Agent. Using ONLY the headlines provided, summarise the key
stories, group related items into themes, and explain why they matter to markets or households (context,
jargon, possible second-order effects). Attribute each point to its source name. Do not invent facts that are
not in the news items, and separate what happened from your explanation of why it may matter."""

    def gather_context(self, state: AgentState) -> str:
        data = load_config()["data"]
        items = fetch_news(data["news_feeds"], topic_terms(last_user_text(state["messages"])),
                           data["max_news_items"])
        return format_news(items)
