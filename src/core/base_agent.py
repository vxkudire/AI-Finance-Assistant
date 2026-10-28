"""BaseAgent: the template every specialised agent extends.

Flow of run():   retrieve (Pinecone) -> gather_context (live data / calculations) -> LLM -> answer
Subclasses only define: key, display_name, system_prompt and (optionally) gather_context().
"""
from langchain_core.messages import AIMessage, SystemMessage

from src.core.config import agent_cfg
from src.core.llm_factory import get_llm
from src.core.state import AgentState
from src.rag.retriever import format_context, retrieve
from src.utils.guardrails import add_disclaimer
from src.utils.helpers import last_user_text, message_text
from src.utils.logger import get_logger

COMMON_RULES = """## Ground rules
- Your purpose is financial EDUCATION. Explain concepts; never give personalised buy/sell/hold instructions
  or promise returns.
- Prefer the retrieved knowledge-base context and live data below. If they do not cover the question, say so
  and answer from general knowledge while flagging uncertainty.
- Use plain language, define jargon once, and label any numbers you invent as hypothetical examples.
- State assumptions explicitly. Keep answers well structured and reasonably concise."""


class BaseAgent:
    key: str = "base"
    display_name: str = "Base Agent"
    system_prompt: str = "You are a helpful finance education assistant."
    use_rag: bool = True
    history_window: int = 10

    def __init__(self):
        self.llm = get_llm(self.key)
        self.namespaces: list[str] = agent_cfg(self.key).get("rag_namespaces", [])
        self.log = get_logger(f"agent.{self.key}")

    # ---- hook for subclasses -------------------------------------------------
    def gather_context(self, state: AgentState) -> str:
        """Return extra text (live quotes, news, calculations...) to inject into the prompt."""
        return ""

    # ---- internals -----------------------------------------------------------
    def _retrieve(self, query: str):
        if not (self.use_rag and self.namespaces and query):
            return []
        try:
            return retrieve(query, self.namespaces)
        except Exception as exc:  # a RAG outage must not kill the agent
            self.log.warning("RAG retrieval failed: %s", exc)
            return []

    def _live_context(self, state: AgentState) -> str:
        try:
            return self.gather_context(state)
        except Exception as exc:
            self.log.warning("gather_context failed: %s", exc)
            return "Live data was unavailable for this request; tell the user."

    def _build_prompt(self, state: AgentState, docs, live: str):
        parts = [self.system_prompt, COMMON_RULES]
        if docs:
            parts.append("## Retrieved knowledge-base context\n" + format_context(docs))
        if live:
            parts.append("## Live / computed data\n" + live)
        return [SystemMessage(content="\n\n".join(parts)), *state["messages"][-self.history_window:]]

    # ---- LangGraph node entry point -----------------------------------------
    def run(self, state: AgentState) -> dict:
        query = last_user_text(state["messages"])
        docs = self._retrieve(query)
        live = self._live_context(state)
        reply = self.llm.invoke(self._build_prompt(state, docs, live))
        sources = sorted({d.metadata.get("source", "unknown") for d in docs})
        return {
            "messages": [AIMessage(content=add_disclaimer(message_text(reply)), name=self.key)],
            "active_agent": self.key,
            "sources": sources,
        }
