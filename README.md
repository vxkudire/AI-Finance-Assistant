# AI-Finance-Assistant
The AI Finance Assistant represents a significant opportunity to democratize financial education, helping millions of beginners take their first steps toward financial security. By combining cutting-edge AI technology with sound financial principles, this system can transform how people learn about and engage with investing.

## Agent Architecture:
The system consists of six specialized agents:
1.	Finance Q&A Agent: Handles general financial education queries
2.	Portfolio Analysis Agent: Reviews and analyzes user portfolios
3.	Market Analysis Agent: Provides real-time market insights
4.	Goal Planning Agent: Assists with financial goal setting and planning
5.	News Synthesizer Agent: Summarizes and contextualizes financial news
6.	Tax Education Agent: Explains tax concepts and account types


## Installation
### 1. Clone the repository
```bash
git clone https://github.com/vxkudire/AI-Finance-Assistant.git
cd AI-Finance-Assistant
py -3.12 -m venv .venv312
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\.venv\Scripts\Activate.ps1
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\.venv312\Scripts\Activate.ps1
```

### 2. Install dependencies

With `uv` (recommended):
```bash
uv sync
```
with pip:
```bash
pip install -r requirements.txt
```
> **Note for pip users:** Since you're not using `uv`, replace `uv run python` with just `python` in all the usage commands below. For example:
> 
> ```bash
> python -m src.workflow.main
> ```
> It's also recommended to use a virtual environment:
>
> ```bash
> python -m venv .venv
> source .venv/bin/activate   # Linux/macOS
> .venv\Scripts\activate      # Windows
> pip install -r requirements.txt
> ```

### 3. Configure environment variables
Edit `.env` and add your keys:

```env
OPENAI_API_KEY=sk-...your-key-here...
PINECONE_API_KEY=sk-...your-key-here...
```

### 4. Run the application
#### 4.1 Ingest the knowledge base
```bash
python -m src.rag.ingest          # creates the index and loads the sample knowledge base
```
#### 4.2 Run the workflow graph on CLI
```bash
python -m src.workflow.graph
```
#### 4.3 Run the Streamlit web app
```bash
streamlit run src/web_app/app.py
```


# AI Finance Assistant
Multi-agent finance education assistant built with LangGraph, Pinecone RAG and OpenAI (swappable).
```
User -> router (LLM intent classifier) -> one of 6 agents -> answer (+ sources, disclaimer)
                                              |-> Pinecone RAG (namespace per domain)
                                              |-> live data (yfinance quotes, RSS news) / Python calculators
```
Agent	File	Grounded by
Finance Q&A	`src/agents/finance_qa_agent.py`	RAG `finance_qa`
Portfolio Analysis	`src/agents/portfolio_agent.py`	holdings + yfinance + RAG `portfolio`
Market Analysis	`src/agents/market_agent.py`	yfinance quotes
Goal Planning	`src/agents/goal_planning_agent.py`	LLM extraction + Python maths + RAG `goal_planning`
News Synthesizer	`src/agents/news_agent.py`	RSS feeds
Tax Education	`src/agents/tax_agent.py`	RAG `tax`
Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add OPENAI_API_KEY and PINECONE_API_KEY
python -m src.rag.ingest        # creates the Pinecone index (first run) and loads src/data/knowledge_base
streamlit run src/web_app/app.py     # or: python -m src.workflow.graph   (CLI)
pytest                          # unit tests (no API keys needed)
```
## Swapping models`
1. Everything lives in `config.yaml` -> `llm` (default for all agents).
2. ne agent only: add `model:` / `provider:` under `agents.<name>`.
3. Quick override without editing files: `LLM_MODEL=gpt-4o` or `LLM_PROVIDER=anthropic LLM_MODEL=...`
(install the matching `langchain-<provider>` package for non-OpenAI providers).
4. Changing the embedding model requires matching `embeddings.dimension` and a new/re-ingested Pinecone index.

## Adding knowledge
Drop `.md`, `.txt` or `.pdf` files into `src/data/knowledge_base/<namespace>/` and re-run `python -m src.rag.ingest`.
Map namespaces to agents under `agents.<name>.rag_namespaces` in `config.yaml`.

## Adding an agent
1. Subclass `BaseAgent` in `src/agents/` (key, prompt, optional `gather_context`).
2. Register it in `src/agents/__init__.py`.
3. Add the intent to `RouteDecision`/`ROUTER_PROMPT` in `src/workflow/router.py`.

## Notes
1. yfinance data is free but can be delayed; replace `src/data/market_data.py` for a paid feed.
2. `MemorySaver` keeps conversation memory in-process; use a SQLite/Postgres checkpointer for persistence.
3. Educational use only - not financial, investment or tax advice.