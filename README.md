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
    end

    Synth -->|"answer + sources + disclaimer"| UI

    Agents -->|"chat + embeddings"| OpenAI[("OpenAI")]
    Graph -.->|"optional tracing"| LS[("LangSmith")]
    Agents -->|"top-k retrieval by namespace"| Pine[("Pinecone index<br/>finance-education")]
    Agents -->|"quotes (Portfolio, Market)"| YF[("yfinance")]
    Agents -->|"headlines (News)"| RSS[("RSS news feeds")]
    Agents -->|"calculations (Goal Planning)"| Calc["Python calculators"]

    KB["Knowledge base<br/>src/data/knowledge_base/*"] -->|"python -m src.rag.ingest"| Pine
    Cfg["config.yaml + env vars"] -.-> Graph
```

### AWS deployment architecture
```mermaid
flowchart LR
    Dev["Developer PC<br/>Docker + AWS CLI"] -->|docker push| ECR[("Amazon ECR<br/>ai-finance-assistant")]
    subgraph AWS["AWS region"]
        ECR -->|docker pull| EC2["EC2 instance<br/>Docker container :8080"]
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
- **AWS Secrets Manager (optional)**: Stores API keys securely instead of plain-text files on the instance
- **AWS CloudWatch (optional)**: Monitors and logs instance and application health
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
Create a `.env` file in the project root (there is no `.env.example`) and add your API keys:

```env
OPENAI_API_KEY=your-openai-api-key
PINECONE_API_KEY=your-pinecone-api-key
# Optional LangSmith tracing. Uncomment and configure all three to enable:
# LANGSMITH_TRACING=true
# LANGSMITH_API_KEY=your-langsmith-api-key
# LANGSMITH_PROJECT=ai-finance-assistant
POSTGRES_URL=postgresql://user:pass@localhost:5432/finance
```

The keys are needed for model calls and Pinecone retrieval. Keep `.env` local; it is ignored by Git.

### LangSmith observability (optional)
Set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT` in the process environment or root `.env` to send graph and model-call traces to LangSmith. Tracing is disabled by default; once enabled, LangSmith can inspect workflow runs, latency, failures, and model usage in the configured project. Traces may include user prompts, assistant responses, retrieved context, and conversation identifiers, so enable this only when your data-handling requirements allow sending that information to LangSmith.

### 5. Ingest the sample knowledge base
Run this once before using the agents that rely on retrieval. It creates the configured Pinecone index if needed and uploads files from `src/data/knowledge_base/`.
```shell
python -m src.rag.ingest
```

### 6. Start the application
Choose either the command-line interface or the Streamlit web app:

**Command-line interface**
```shell
python -m src.workflow.graph
```

**Streamlit web app** (requires Google sign-in: copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and add your Google OAuth client ID/secret and the emails allowed to sign in under `[access] allowed_emails` (or `ALLOWED_EMAILS`; empty means nobody); set the redirect URI to `http://localhost:8501/oauth2callback`)
```shell
streamlit run src/web_app/app.py
```

### Run tests
The unit tests do not require API keys or a Pinecone connection:
```shell
python -m pytest
```


# AI Finance Assistant
Multi-agent finance education assistant built with LangGraph, Pinecone RAG and OpenAI (swappable).
```
User -> router (LLM intent classifier, 1-3 intents) -> agent(s) in parallel -> synthesizer -> answer (+ sources, disclaimer)
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
## Swapping models
1. Everything lives in `config.yaml` -> `llm` (default for all agents).
2. For one agent only: add `model:` / `provider:` under `agents.<name>`.
3. Quick override without editing files: `LLM_MODEL=gpt-4o` or `LLM_PROVIDER=anthropic LLM_MODEL=...`
(install the matching `langchain-<provider>` package for non-OpenAI providers).
4. Changing the embedding model requires matching `embeddings.dimension` and a new/re-ingested Pinecone index.

## Adding knowledge
Drop `.md`, `.txt` or `.pdf` files into `src/data/knowledge_base/<namespace>/` and re-run `python -m src.rag.ingest`.
Map namespaces to agents under `agents.<name>.rag_namespaces` in `config.yaml`.

## Adding an agent
1. Subclass `BaseAgent` in `src/agents/` (key, prompt, optional `gather_context`).
2. Register it in `src/agents/__init__.py`.
3. Add the intent to `Intent`/`ROUTER_PROMPT` in `src/workflow/router.py`.

## Notes
Usernames identify a single conversation in the CLI and Streamlit app. With `POSTGRES_URL` configured, enter the same username to resume it across restarts; `MemorySaver` is process-local. Usernames are not authenticated, so add login before exposing the app to multiple users.

1. yfinance data is free but can be delayed; replace `src/data/market_data.py` for a paid feed.
2. Conversation memory uses `PostgresSaver` when `POSTGRES_URL` is set (e.g. `postgresql://user:pass@localhost:5432/finance`); otherwise it falls back to the in-process `MemorySaver`.
3. Educational use only - not financial, investment or tax advice.

## Deploying to AWS EC2

This guide deploys the app on a single EC2 instance running Docker. You build the image locally, push it to Amazon ECR, then pull and run it on EC2. You need Docker Desktop, AWS CLI v2, and AWS credentials authorized to use ECR and EC2. The commands below use PowerShell locally and shell commands on the EC2 host.

**Important:** The app has no user authentication, and the test setup uses unencrypted HTTP. Restrict access to your own IP and only use non-sensitive sample data. Before sharing it or entering personal/financial information, add authentication and HTTPS.

### 1. Ingest the knowledge base

The app retrieves its knowledge base from Pinecone. From the project root, set `OPENAI_API_KEY` and `PINECONE_API_KEY` in your local, untracked `.env` file, then run:

```powershell
python -m src.rag.ingest
```

This creates/populates the Pinecone index configured in `config.yaml`. The deployed app uses that same index. Do not commit `.env` or put keys in the image.

### 2. Build and push the container image
First login to AWS (example profile):
```powershell
$env:AWS_PROFILE="nuvepro"
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

Keep this image URI for the EC2 run step. For each update, set `$Tag` to a new value (for example, `v2`), recalculate `$Image`, then run build/tag/push again.

### 3. Launch and prepare the EC2 instance

In the AWS Console (same `$Region`), launch an EC2 instance:

1. AMI: Amazon Linux 2023 (x86_64) is a good default.
2. Instance type: start with `t3.small` or `t3.medium` for testing.
3. Security group inbound rules:
   - TCP `22` from your IP (`/32`) for SSH
   - TCP `8080` from your IP (`/32`) for app access
4. IAM instance profile: attach a role that allows ECR pull access (for example `AmazonEC2ContainerRegistryReadOnly`).
5. Launch and connect to the instance (EC2 Instance Connect or SSH).

On the instance, install and start Docker:

```bash
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
newgrp docker
```

### 4. Pull and run the container on EC2

On your local machine, note the values of `$Region`, `$Registry`, and `$Image`. On EC2:

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker pull <your-image-uri>
```

Create an environment file on EC2:

```bash
sudo mkdir -p /opt/ai-finance-assistant
sudo tee /opt/ai-finance-assistant/.env >/dev/null <<'EOF'
OPENAI_API_KEY=your-openai-key
PINECONE_API_KEY=your-pinecone-key
# Optional LangSmith tracing. Uncomment and configure all three to enable:
# LANGSMITH_TRACING=true
# LANGSMITH_API_KEY=your-langsmith-api-key
# LANGSMITH_PROJECT=ai-finance-assistant
POSTGRES_URL=******localhost:5432/finance
EOF
sudo chmod 600 /opt/ai-finance-assistant/.env
```

Run the container:

```bash
docker run -d --name ai-finance-assistant \
  --restart unless-stopped \
  --env-file /opt/ai-finance-assistant/.env \
  -p 8080:8080 \
  <your-image-uri>
```

Verify it is healthy:

```bash
docker ps
curl -I http://localhost:8080
```

Then open `http://<ec2-public-ip>:8080` in your browser.

### 5. Deploy an update

1. Build and push a new tag from your local machine (`v2`, `v3`, ...).
2. On EC2: `docker pull <new-image-uri>`.
3. Replace the running container:

```bash
docker stop ai-finance-assistant
docker rm ai-finance-assistant
docker run -d --name ai-finance-assistant \
  --restart unless-stopped \
  --env-file /opt/ai-finance-assistant/.env \
  -p 8080:8080 \
  <new-image-uri>
```

### Cleanup and limitations

- Conversation history uses in-process `MemorySaver` and is not durable across service restarts or scaling. Keep the desired task count at `1` unless you add shared persistent checkpoint storage.
- To stop charges, terminate the EC2 instance and remove unused ECR repositories/images.
- The app needs outbound internet access to OpenAI, Pinecone, market-data, and news endpoints.
- For production, place an ALB with HTTPS in front of EC2, lock security groups, and add authentication.