"""Synthesizer: merges the outputs of the agents chosen by the router into one coherent answer."""
from langchain_core.messages import AIMessage

from src.core.llm_factory import get_llm
from src.core.state import AgentState
from src.utils.guardrails import add_disclaimer, strip_disclaimer
from src.utils.helpers import last_user_text, message_text
from src.utils.logger import get_logger

log = get_logger("synthesizer")

SYNTHESIZER_PROMPT = """You combine answers from several specialist finance-education agents into ONE reply.
- Answer the user's question directly and cover every part of it; use each specialist's content.
- Merge overlapping points, remove repetition, and resolve wording conflicts; do not invent new facts.
- Keep numbers, caveats and hypothetical-example labels from the specialists. Never give personalised
  buy/sell/hold instructions. Use clear headings or short sections when the topics differ.
- Do not mention 'agents' or the synthesis process, and do not add a disclaimer (one is appended later)."""


def _ordered(state: AgentState) -> list[dict]:
    order = {k: i for i, k in enumerate(state.get("intents", []))}
    return sorted(state.get("agent_outputs", []), key=lambda o: order.get(o["agent"], len(order)))


def _fallback(outputs: list[dict]) -> str:
    return "\n\n".join(o["content"] for o in outputs)


def synthesizer_node(state: AgentState) -> dict:
    outputs = _ordered(state)
    if not outputs:
        return {"messages": [AIMessage(content=add_disclaimer("Sorry, I could not produce an answer."))]}
    sources = sorted({s for o in outputs for s in o.get("sources", [])})
    agents = [o["agent"] for o in outputs]
    if len(outputs) == 1:                       # nothing to merge: keep the agent's answer untouched
        return {"messages": [AIMessage(content=outputs[0]["raw"], name=agents[0])],
                "active_agent": agents[0], "sources": sources}
    specialist_text = "\n\n".join(f"### {o['agent']}\n{o['content']}" for o in outputs)
    try:
        reply = get_llm("synthesizer").invoke([
            ("system", SYNTHESIZER_PROMPT),
            ("human", f"User question:\n{last_user_text(state['messages'])}\n\nSpecialist answers:\n{specialist_text}"),
        ])
        text = message_text(reply)
    except Exception as exc:
        log.warning("synthesis failed (%s); concatenating agent answers", type(exc).__name__)
        text = _fallback(outputs)
    log.info("synthesized %s", agents)
    return {"messages": [AIMessage(content=add_disclaimer(strip_disclaimer(text)), name="synthesizer")],
            "active_agent": ", ".join(agents), "sources": sources}
