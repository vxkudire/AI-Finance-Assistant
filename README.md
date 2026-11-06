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

### Application architecture
```mermaid
flowchart TD
    User([User]) --> UI["Streamlit web app<br/>src/web_app/app.py"]
    UI -->|"question + optional portfolio"| Router

    subgraph Graph["LangGraph workflow (MemorySaver: per-thread memory)"]
        Router["Router<br/>multi-intent LLM classifier + keyword fallback"]
        Router -->|"1-3 intents (parallel fan-out)"| Agents["Six specialised agents<br/>Finance Q&A, Portfolio, Market,<br/>Goal Planning, News, Tax<br/>(retrieve, gather context, LLM answer)"]
        Agents -->|"agent outputs"| Synth["Synthesizer<br/>merges answers into one reply"]
        Agents -->|"stdio tool calls<br/>(Market, Portfolio, News, Goals)"| MCPClient["MCP client bridge<br/>src/core/mcp_client.py"]
    end

    Synth -->|"answer + sources + disclaimer"| UI

    UI -->|"portfolio analysis / market overview"| Cache
    MCPClient -->|"local stdio"| MCPServer["Finance MCP server<br/>src/mcp_server.py"]
    MCPServer -->|"quotes / sector metadata / feeds"| Cache
    MCPServer -->|"future value / contributions"| Calc["Python calculators"]
    Cache["In-process Streamlit data cache<br/>quotes + history: 60s; news: 5m; sectors: 1h"]
    Cache -->|"cache miss"| YF[("yfinance")]
    Cache -->|"cache miss"| RSS[("RSS news feeds")]
    Agents -->|"chat + embeddings"| OpenAI[("OpenAI")]
    Graph -.->|"optional tracing"| LS[("LangSmith")]
    Agents -->|"top-k retrieval by namespace"| Pine[("Pinecone index<br/>finance-education")]

    KB["Knowledge base<br/>src/data/knowledge_base/*"] -->|"python -m src.rag.ingest"| Pine
    Cfg["config.yaml + env vars"] -.-> Graph
```

### AWS deployment architecture
```mermaid
flowchart LR
    Dev["Developer PC<br/>Docker + AWS CLI"] -->|docker push| ECR[("Amazon ECR<br/>ai-finance-assistant")]
    subgraph AWS["AWS region"]
        ECR -->|docker pull| EC2["EC2 instance<br/>Docker container :8080"]
        EC2 --- Cache["In-process cache<br/>per container; no Redis"]
        SM["Secrets Manager or local .env<br/>OPENAI_API_KEY<br/>PINECONE_API_KEY"] -->|"provided at runtime"| EC2
        EC2 --> CW["CloudWatch (optional)"]
        SG["Security group<br/>8080 from your IP"] -.-> EC2
    end
    Browser([Your browser]) -->|"HTTP :8080 (test)"| EC2
    EC2 -->|HTTPS| OpenAI[("OpenAI API")]
    EC2 -->|HTTPS| Pine[("Pinecone")]
    EC2 -->|HTTPS| Ext[("yfinance / RSS feeds")]
```
For a shared deployment, place an Application Load Balancer (HTTPS + ACM certificate) in front of the instance.


## Technical Stack:
### Main Components:
- **LangChain**: Provides the framework for building and managing the agents, enabling them to communicate and collaborate effectively
- **LangGraph**: Orchestrates the multi-agent workflow, enabling seamless interaction between agents
- **Model Context Protocol (MCP)**: Exposes finance data and calculation functions to the LangGraph market, portfolio, news, and goal-planning agents over local stdio
- **PineconeDB for RAG**: Provides retrieval-augmented generation capabilities, allowing agents to access a rich knowledge base for informed responses
- **PostgreSQL for Conversation History**: Serves as a persistent storage solution for conversation history, enabling context-aware interactions
- **Streamlit**: Offers a user-friendly web interface for interacting with the agents, making it accessible to a wide audience
- **OpenAI API**: Powers the natural language understanding and generation capabilities of the agents, with the flexibility to swap in other providers as needed
- **LangSmith (optional)**: Traces LangGraph workflows and model calls for latency, errors, token usage, and run inspection
- **YFinance**: Provides real-time financial data and market insights
- **RSS Feeds**: Supplies up-to-date financial news for the News Synthesizer Agent

### Deployment Components:
- **Docker**: Enables containerization of the application for consistent deployment across environments
- **AWS EC2**: Runs the Streamlit container on a virtual machine you manage
- **AWS ECR**: Provides a fully managed Docker container registry that makes it easy to store, manage, and deploy Docker container images
- **AWS IAM**: Manages access to AWS services and resources securely

## Installation
### 1. Install prerequisites and clone the repository
Install Python 3.14 and Git; the Docker image also uses Python 3.14.

```shell
git clone https://github.com/vxkudire/AI-Finance-Assistant.git
cd AI-Finance-Assistant
```

### 2. Create and activate a virtual environment
Run the commands for your operating system from the repository root.

**Windows PowerShell**
```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
```
If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and activate again.

**macOS / Linux**
```shell
python3.14 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies
With the virtual environment active:
```shell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configure API keys
Create a `.env` file in the project root using `.env.example` as a template, then add your API keys:

```env
OPENAI_API_KEY=your-openai-api-key
PINECONE_API_KEY=your-pinecone-api-key
# Optional persistent conversation storage
POSTGRES_URL=postgresql://venkat:kudire@localhost:5432/finance
# Optional persistent conversation storage for Docker containerized deployment
#POSTGRES_URL=postgresql://venkat:kudire@finance-postgres:5432/finance
# Optional LangSmith tracing. Uncomment and configure all three to enable:
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=ai-finance-assistant
POSTGRES_URL=postgresql://user:pass@localhost:5432/finance
```

The keys are needed for model calls and Pinecone retrieval. Keep `.env` local; it is ignored by Git.

### LangSmith observability (optional)
The `.env.example` template includes the LangSmith settings. Uncomment `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY=your-langsmith-api-key`, and `LANGSMITH_PROJECT=ai-finance-assistant` in your root `.env`, replacing the placeholder with an API key from your LangSmith account. Tracing is disabled by default; once enabled, LangSmith can inspect graph and model-call runs, latency, failures, and model usage in the configured project. Traces may include user prompts, assistant responses, retrieved context, and conversation identifiers, so enable this only when your data-handling requirements allow sending that information to LangSmith.

### 5. Ingest the sample knowledge base
Run this once before using the agents that rely on retrieval. It creates the configured Pinecone index if needed and uploads files from `src/data/knowledge_base/`.
```shell
python -m src.rag.ingest
```

### 6. Run PostgreSQL (optional)
If you want conversation history to persist across restarts, run a PostgreSQL instance and set `POSTGRES_URL` in `.env`. The default is `postgresql://venkat:kudire@localhost:5432/finance`. You can run PostgreSQL in a Docker container:
```shell
docker run -d --name finance-postgres -e POSTGRES_USER=venkat -e POSTGRES_PASSWORD=kudire -e POSTGRES_DB=finance -p 5432:5432 postgres:latest
```

### 7. Start the application
Choose either the command-line interface or the Streamlit web app:

**Command-line interface**
```shell
python -m src.workflow.graph
```

**Streamlit web app** (requires Google sign-in: copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add your Google OAuth client ID/secret; any user with a verified Google email can sign in (publish the OAuth consent screen to allow users beyond the Test users list); set the redirect URI to `http://localhost:8501/oauth2callback`)
```shell
streamlit run src/web_app/app.py
```
The **Portfolio** view analyzes the holdings entered in the sidebar, showing total value, concentration metrics, value by holding, sector allocation, and a holdings breakdown. Enable **Enable portfolio analysis and share with the assistant** to fetch quotes and show the dashboard; when it is off, the app does not fetch portfolio data. Use **Refresh prices** to bypass the short quote cache. Yahoo Finance quotes may be delayed. When the option is off, holdings are also excluded from assistant state and 

The **Market** view shows major index levels (S&P 500, Dow, Nasdaq, Russell 2000, VIX), a selectable index's actual daily levels over the chosen period, an optional normalized comparison of the four major stock indexes, and today's sector performance via sector ETFs. Data comes from Yahoo Finance (may be ~15 minutes delayed), is cached for 60 seconds, and can be reloaded with **Refresh data**.

Market quotes and index history are shared in a bounded 60-second cache, RSS feed responses for 5 minutes, and company sector metadata for 1 hour. Refresh buttons use a user-scoped cache version to bypass stale cached prices and portfolio metadata. Portfolio calculations run on the current holdings; failures are not cached.

Transient Yahoo Finance and RSS failures are retried up to twice with bounded backoff. A long `Retry-After` is respected without blocking the interface for the full delay. OpenAI clients use their SDK's two retries and a 30-second per-request timeout. If a service remains unavailable, the app reports missing data or asks the user to retry; knowledge-base retrieval and synthesis can fall back to general knowledge or individual agent responses. Other model providers use their own SDK retry and timeout settings.

### MCP server (optional)
The LangGraph market, portfolio, news, and goal-planning agents call the app's read-only finance functions through a local [Model Context Protocol](https://modelcontextprotocol.io) stdio server. The workflow launches the server automatically when one of those agents needs finance data; no separate MCP client configuration is needed. The standalone server is also available for external MCP clients. Finance data requires no API keys (quotes come from Yahoo Finance; news uses the feeds in `config.yaml`).

#### Protocol implementation
`src/mcp_server.py` implements an MCP server with the Python SDK's `FastMCP` API and stdio transport. Its six registered tools wrap the application's existing quote, market overview, RSS news, portfolio analysis, and savings calculator functions; the MCP layer serializes tabular market history and validates tool arguments before invoking those functions. It is read-only: it does not persist user portfolios or make trades.

See the [MCP tools API reference](docs/mcp-api.md) for each tool's arguments, validation rules, response fields, and examples.

`src/core/mcp_client.py` is the synchronous adapter used by LangGraph nodes. For each request, it launches `python -m src.mcp_server` using the current Python interpreter and repository root as the working directory, opens a `ClientSession`, initializes the MCP connection, calls the requested tool or tools, reads structured results (with a JSON text fallback), and closes the stdio session. Goal planning batches its scenario calculations in one MCP session. Tool errors and malformed results are raised to the agent; the existing agent error handling then reports unavailable live/computed data rather than treating a failed call as a successful result. Because the server is started on demand, there is no separate long-running MCP process to manage for the LangGraph workflow.

| Tool | Purpose and key arguments |
|---|---|
| `get_quotes` | Current Yahoo Finance quotes for 1–25 ticker symbols. |
| `get_market_overview` | Major-index and sector ETF quotes plus index history for `5d`, `1mo`, `3mo`, `6mo`, `1y`, or `ytd`. |
| `get_financial_news` | RSS headlines; optional keyword `terms` and `limit` (1–25, default from `config.yaml`). |
| `analyze_portfolio` | Current valuation, weights, gains/losses, concentration and sector mix for 1–50 holdings (`ticker`, positive `shares`, optional non-negative per-share `cost_basis`). |
| `project_future_value` | Savings projection from `present`, `monthly`, `annual_rate`, and `years`. |
| `required_monthly_contribution` | Monthly savings needed for `target` from `present` at `annual_rate` over `years`. |

Calculator rates are decimals (for example, `0.07` means 7%). Numeric inputs must be finite and non-negative where appropriate; calculator rates are bounded from `-0.99` through `1`, and projections are limited to 100 years. Invalid arguments produce MCP tool errors. Market quotes can be delayed; financial outputs are educational and not investment advice.

Run it from the repository root (after `pip install -r requirements.txt`):
```shell
python -m src.mcp_server
```

Tools: `get_quotes`, `get_market_overview` (indices, sector ETFs, normalized performance for `5d`/`1mo`/`3mo`/`6mo`/`1y`/`ytd`), `get_financial_news`, `analyze_portfolio`, `project_future_value`, `required_monthly_contribution`. Inputs are validated (ticker format and counts, positive finite numbers, bounded limits); invalid input returns a tool error. Rates are decimals (`0.07` = 7%).

Client configuration (for example Claude Desktop `claude_desktop_config.json`, or any MCP client that launches stdio servers). Use absolute paths; `cwd` must be the repository root, and `command` should be the Python from the virtual environment that has the dependencies:
```json
{
  "mcpServers": {
    "ai-finance-assistant": {
      "command": "C:\\path\\to\\AI-Finance-Assistant\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.mcp_server"],
      "cwd": "C:\\path\\to\\AI-Finance-Assistant"
    }
  }
}
```
If your client ignores `cwd`, use `"env": {"PYTHONPATH": "C:\\path\\to\\AI-Finance-Assistant"}` instead. Logs go to stderr; quotes may be delayed and are informational, not investment advice.
### Run tests
The unit tests do not require API keys or a Pinecone connection:
```shell
python -m pytest
```
The test command reports coverage and fails if it falls below 80%. Coverage includes the application backend and chart helpers; `src/web_app/app.py` is excluded because it is a top-level Streamlit UI entry point.


## Additional Information
Multi-agent finance education assistant built with LangGraph, Pinecone RAG, and OpenAI (swappable).
```
User -> router (LLM intent classifier, 1-3 intents) -> agent(s) in parallel -> synthesizer -> answer (+ sources, disclaimer)
                                              |-> Pinecone RAG (namespace per domain)
                                              |-> live data (yfinance quotes, RSS news) / Python calculators
```
Agent	File	Grounded by
Finance Q&A	`src/agents/finance_qa_agent.py`	RAG `finance_qa` (knowledge base: `src/data/knowledge_base/finance_qa/`) <br>
Portfolio Analysis	`src/agents/portfolio_agent.py`	holdings + yfinance + RAG `portfolio` (knowledge base: `src/data/knowledge_base/portfolio/`) <br>
Market Analysis	`src/agents/market_agent.py`	yfinance quotes <br>
Goal Planning	`src/agents/goal_planning_agent.py`	LLM extraction + Python maths + RAG `goal_planning` (knowledge base: `src/data/knowledge_base/goal_planning/`) <br>
News Synthesizer	`src/agents/news_agent.py`	RSS feeds <br>
Tax Education	`src/agents/tax_agent.py`	RAG `tax` (knowledge base: `src/data/knowledge_base/tax/`) <br>
## Swapping models
1. Everything lives in `config.yaml` -> `llm` (default for all agents).
2. For one agent only: add `model:` / `provider:` under `agents.<name>`.
3. Quick override without editing files: `LLM_MODEL=gpt-4o` or `LLM_PROVIDER=anthropic LLM_MODEL=...`
(install the matching `langchain-<provider>` package for non-OpenAI providers).
4. Changing the embedding model requires matching `embeddings.dimension` and a new/re-ingested Pinecone index.

## Adding knowledge
Drop `.md`, `.txt` or `.pdf` files into `src/data/knowledge_base/<namespace>/` and re-run `python -m src.rag.ingest`. The first Markdown heading (or filename when there is no heading) is stored as a normalized `category` metadata value. RAG callers can pass that exact category to `retrieve(query, namespaces, category=...)` to limit similarity search to matching content; leaving it unset keeps retrieval unfiltered.
Map namespaces to agents under `agents.<name>.rag_namespaces` in `config.yaml`.

## Adding an agent
1. Subclass `BaseAgent` in `src/agents/` (key, prompt, optional `gather_context`).
2. Register it in `src/agents/__init__.py`.
3. Add the intent to `Intent`/`ROUTER_PROMPT` in `src/workflow/router.py`.

## Notes
Usernames identify a single conversation in the CLI and Streamlit app. With `POSTGRES_URL` configured, enter the same username to resume it across restarts; `MemorySaver` is process-local. Usernames are not authenticated, so add login before exposing the app to multiple users.

1. yfinance data is free but can be delayed; replace `src/data/market_data.py` for a paid feed.
2. Conversation memory uses `PostgresSaver` when `POSTGRES_URL` is set (e.g. `postgresql://user:pass@localhost:5432/finance`); otherwise it falls back to the in-process `MemorySaver`.
3. Educational use only - not financial, investment, or tax advice.

## Deploying to AWS EC2

This guide deploys the app on a single EC2 instance running Docker. You build the image locally, push it to Amazon ECR, then pull, and run it on EC2. You need Docker Desktop, AWS CLI v2, and AWS credentials authorized to use ECR and EC2. The commands below use PowerShell locally and shell commands on the EC2 host.

**Important:** The app has no user authentication, and the test setup uses unencrypted HTTP. Restrict access to your own IP and only use non-sensitive sample data. Before sharing it or entering personal/financial information, add authentication and HTTPS.

### 1. Ingest the knowledge base

The app retrieves its knowledge base from Pinecone. From the project root, set `OPENAI_API_KEY` and `PINECONE_API_KEY` in your local, untracked `.env` file, then run:

```powershell
python -m src.rag.ingest
```

This creates/populates the Pinecone index configured in `config.yaml`. The deployed app uses that same index. Do not commit `.env` or put keys in the image.

### 2. Build and push the container image
First login to AWS (example profile) [install AWS CLI if not installed](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html):
```powershell
$env:AWS_PROFILE="nuvepro" # Profile is used by the AWS CLI to find credentials in ~/.aws/credentials
aws configure
```

The terminal prompts for:
- `AWS Access Key ID`
- `AWS Secret Access Key`
- `Default region name` (example: `us-east-1`)
- `Default output format` (example: `json`)

Verify the Login
```powershell
aws sts get-caller-identity
```

In PowerShell from the project root, choose the AWS region and get your account ID:

```powershell
$Region = "us-east-1"
$AccountId = aws sts get-caller-identity --query Account --output text
$Repository = "ai-finance-assistant-venkatesh.kudire"   # lowercase only
$Registry = "$AccountId.dkr.ecr.$Region.amazonaws.com"
$Tag = "v1"
$Image = "${Registry}/${Repository}:${Tag}"
```

Run `$Image` to print the full image URI; you will use that on the EC2 host when pulling/running the container.

If the identity command fails, sign in/configure the AWS CLI before continuing. Create the ECR repository once (skip this if it already exists), authenticate Docker, then build and push:

```powershell
aws ecr create-repository --repository-name $Repository --region $Region
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $Registry
docker buildx build --platform linux/amd64 --load -t "${Repository}:${Tag}" .
docker tag "${Repository}:${Tag}" $Image
docker push $Image
```
Check if the image can be run on localhost (with your `.env` and `.streamlit/secrets.toml` in the current directory):
```powershell
docker network create finance-net
docker run -d --name finance-postgres --network finance-net -e POSTGRES_USER=venkat -e POSTGRES_PASSWORD=kudire -e POSTGRES_DB=finance -p 5432:5432 postgres:latest
docker run -d --name ai-finance-assistant --network finance-net `
  --env-file .env `
  -p 8501:8080 `
  --mount "type=bind,source=$($PWD.Path)\.streamlit\secrets.toml,target=/app/.streamlit/secrets.toml,readonly" `
  ai-finance-assistant-venkatesh.kudire:v1
docker ps
```
Run the URL printed by `docker ps` in your browser (example: `http://localhost:8501`). If it works, stop the containers and continue to the EC2 deployment.

Keep this image URI for the EC2 run step. For each update, set `$Tag` to a new value (for example, `v2`), recalculate `$Image`, then run build/tag/push again.

### 3. Launch and prepare the EC2 instance

In the AWS Console (same `$Region`), launch an EC2 instance:

1. AMI: Amazon Linux 2023 (x86_64) is a good default.
2. Instance type: start with `t3.small` or `t3.medium` for testing.
3. Security group inbound rules:
   - TCP `22` from your IP (`/32`) for SSH
   - Custom TCP `8501` from your IP (`/32`) for app access
4. IAM instance profile: attach a role that allows ECR pull access (for example `AmazonEC2ContainerRegistryReadOnly`).
5. Launch and connect to the instance (EC2 Instance Connect or SSH).
```powershell
# 1. Reset permissions and clear old settings
icacls "vxkudire.pem" /reset

# 2. Grant explicit Read access to ONLY your current Windows user profile
icacls "vxkudire.pem" /grant:r "$($env:USERNAME):R"

# 3. Block all inherited permissions from other groups (System, Administrators, etc.)
icacls "vxkudire.pem" /inheritance:r

# 4. connect
ssh -i "vxkudire.pem" ec2-user@ec2-32-201-155-101.compute-1.amazonaws.com
```


On the instance, install and start Docker:
```bash
sudo dnf update -y # optional 
sudo dnf install -y docker # install Docker
sudo systemctl enable --now docker # start Docker
sudo usermod -aG docker ec2-user # add ec2-user to the docker group
newgrp docker # or log out/in to apply group change
docker --version # verify Docker is installed
```

### 4. Pull and run the containers on EC2

On your local machine, note the values of `$Region`, `$Registry`, and `$Image`. On EC2:

```bash
# check if image exists in ECR
aws ecr describe-images --repository-name ai-finance-assistant-venkatesh.kudire --region us-east-1
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 096610775205.dkr.ecr.us-east-1.amazonaws.com
docker pull 096610775205.dkr.ecr.us-east-1.amazonaws.com/ai-finance-assistant-venkatesh.kudire:v1
```

on EC2, create a Docker network for the app and Postgres to communicate:
```bash
docker network create finance-net
```

On EC2: run postgresql in a container (or install it on the host) and create the `finance` database. The app uses `POSTGRES_URL` to connect to it. Example with a local container:
```bash
docker run -d --name finance-postgres --network finance-net -e POSTGRES_USER=venkat -e POSTGRES_PASSWORD=kudire -e POSTGRES_DB=finance -p 5432:5432 postgres:latest
```

Create an environment file on EC2:

```bash
sudo mkdir -p /opt/ai-finance-assistant
sudo tee /opt/ai-finance-assistant/.env >/dev/null <<'EOF'
OPENAI_API_KEY=your-openai-key
PINECONE_API_KEY=your-pinecone-key
POSTGRES_URL=postgresql://venkat:kudire@finance-postgres:5432/finance
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=ai-finance-assistant
EOF
sudo chown ec2-user:ec2-user /opt/ai-finance-assistant/.env
sudo chmod 600 /opt/ai-finance-assistant/.env
```

Run below on local machine to copy secrets.toml to EC2. The app reads this file for Google sign-in.
```powershell
scp -i vxkudire.pem .streamlit/secrets.toml ec2-user@ec2-32-201-155-101.compute-1.amazonaws.com:~/secrets.toml
ssh -i vxkudire.pem ec2-user@ec2-32-201-155-101.compute-1.amazonaws.com "chmod 644 ~/secrets.toml"
```

The `chown` is required: `docker run --env-file` reads the file as `ec2-user`, so a root-owned `600` file fails with "permission denied". Edit it later with `sudo nano /opt/ai-finance-assistant/.env`, then recreate the container so it picks up changes.

Run the container on EC2:

```bash
docker rm -f ai-finance-assistant 2>/dev/null || true
docker run -d --name ai-finance-assistant \
  --network finance-net \
  --restart unless-stopped \
  --env-file /opt/ai-finance-assistant/.env \
  -v ~/secrets.toml:/app/.streamlit/secrets.toml:ro \
  -p 8501:8080 \
  096610775205.dkr.ecr.us-east-1.amazonaws.com/ai-finance-assistant-venkatesh.kudire:v1
```

Verify on EC2 it is healthy:

```bash
docker ps
curl -I http://localhost:8501
```

Then open `https://vxkudire.duckdns.org` in your local machine browser.
```text
Example: https://vxkudire.duckdns.org
```

### 5. Deploy an update

1. Build and push a new tag from your local machine (`v2`, `v3`, ...).
2. On EC2: `docker pull <new-image-uri>`.
3. Replace the running container:

```bash
docker stop ai-finance-assistant
docker rm ai-finance-assistant
docker run -d --name ai-finance-assistant \
  --network finance-net \
  --restart unless-stopped \
  --env-file /opt/ai-finance-assistant/.env \
  -v ~/secrets.toml:/app/.streamlit/secrets.toml:ro \
  -p 8501:8080 \
  096610775205.dkr.ecr.us-east-1.amazonaws.com/ai-finance-assistant-venkatesh.kudire:v2
```

### Cleanup and limitations

- Conversation history uses in-process `MemorySaver` and is not durable across service restarts or scaling. Keep the desired task count at `1` unless you add shared persistent checkpoint storage.
- To stop charges, terminate the EC2 instance and remove unused ECR repositories/images.
- The app needs outbound internet access to OpenAI, Pinecone, market-data, and news endpoints.
- For production, place an ALB with HTTPS in front of EC2, lock security groups, and add authentication.


# Instructions for DNS
1. Pin the EC2 instance IP with an Elastic IP. 
2. Create a free DuckDNS account and add a subdomain (example: `vxkudire.duckdns.org`).
```powershell
nslookup vxkudire.duckdns.org
```
3. Open the security group <br>
Inbound rules: 80 and 443 from anywhere (0.0.0.0/0), 22 from your IP only. You can drop public access to 8501/8080.
4. Install nginx and a certificate (on EC2)
```bash
sudo dnf install -y nginx certbot python3-certbot-nginx
sudo systemctl enable --now nginx
```
Create /etc/nginx/conf.d/streamlit.conf (replace the domain, and use the host port you mapped, e.g. 8501):
```bash
sudo tee /etc/nginx/conf.d/streamlit.conf > /dev/null <<'EOF'
server {
    listen 80;
    server_name vxkudire.duckdns.org;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}
EOF
```
Then:
```bash
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d vxkudire.duckdns.org
```
Certbot gets the Let's Encrypt certificate, enables HTTPS, and auto-renews. If certbot isn't in the dnf repos, install it with sudo pip3 install certbot certbot-nginx.
5. Update the redirect URI in `.streamlit/secrets.toml` to `https://vxkudire.duckdns.org/oauth2callback` and restart the container.
6. secrets.toml: redirect_uri = "https://vxkudire.duckdns.org/oauth2callback"
7. https://vxkudire.duckdns.org