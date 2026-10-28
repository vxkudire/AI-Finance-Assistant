"""4. Goal Planning Agent - LLM extracts goal parameters, Python does the maths, LLM explains."""
from typing import Optional

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from src.core.base_agent import BaseAgent
from src.core.config import agent_cfg
from src.core.state import AgentState
from src.utils.calculators import future_value, required_monthly_contribution


class GoalParams(BaseModel):
    goal_name: Optional[str] = Field(None, description="e.g. retirement, house down payment")
    target_amount: Optional[float] = Field(None, description="target in dollars")
    years: Optional[float] = Field(None, description="years until the goal")
    current_savings: float = Field(0, description="amount already saved")
    monthly_contribution: Optional[float] = Field(None, description="what the user can save per month")
    expected_annual_return: Optional[float] = Field(None, description="decimal, e.g. 0.06; only if user stated it")


class GoalPlanningAgent(BaseAgent):
    key = "goal_planning"
    display_name = "Goal Planning"
    system_prompt = """You are the Goal Planning Agent. You help users set SMART financial goals (emergency fund,
down payment, education, retirement) and understand the savings needed. Use the computed scenarios exactly as
given, explain the trade-off between time, contribution and return, and note that returns are illustrative
assumptions, not guarantees. If target amount or timeframe is missing, ask for it."""

    def gather_context(self, state: AgentState) -> str:
        extractor = self.llm.with_structured_output(GoalParams)
        p: GoalParams = extractor.invoke([
            SystemMessage(content="Extract financial-goal parameters from the conversation. "
                                  "Use null for anything the user has not stated. Do not guess."),
            *state["messages"][-6:],
        ])
        if not (p.target_amount and p.years):
            return "Missing target amount and/or timeframe. Ask the user for them (and current savings)."

        default_rate = agent_cfg(self.key).get("default_annual_return", 0.06)
        scenarios = ({"user-stated return": p.expected_annual_return} if p.expected_annual_return is not None
                     else {"conservative": 0.03, "moderate": default_rate, "aggressive": 0.08})
        lines = [f"Goal: {p.goal_name or 'unnamed'} | target ${p.target_amount:,.0f} in {p.years:g} years | "
                 f"current savings ${p.current_savings:,.0f}",
                 "Scenarios (illustrative annual returns, compounded monthly):"]
        for label, rate in scenarios.items():
            need = required_monthly_contribution(p.target_amount, p.current_savings, rate, p.years)
            line = f"- {label} ({rate:.1%}): required monthly contribution = ${need:,.0f}"
            if p.monthly_contribution is not None:
                fv = future_value(p.current_savings, p.monthly_contribution, rate, p.years)
                line += f"; saving ${p.monthly_contribution:,.0f}/month would reach ${fv:,.0f}"
            lines.append(line)
        return "\n".join(lines)
