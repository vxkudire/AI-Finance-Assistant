from .finance_qa_agent import FinanceQAAgent
from .goal_planning_agent import GoalPlanningAgent
from .market_agent import MarketAgent
from .news_agent import NewsAgent
from .portfolio_agent import PortfolioAgent
from .tax_agent import TaxAgent

AGENT_CLASSES = {
    "finance_qa_agent": FinanceQAAgent,
    "portfolio_agent": PortfolioAgent,
    "market_agent": MarketAgent,
    "goal_planning_agent": GoalPlanningAgent,
    "news_agent": NewsAgent,
    "tax_agent": TaxAgent,
}
