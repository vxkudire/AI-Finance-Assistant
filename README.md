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
        Router["Router<br/>LLM intent classifier + keyword fallback"]
        Router --> Agents["Six specialised agents<br/>Finance Q&A, Portfolio, Market,<br/>Goal Planning, News, Tax<br/>(retrieve, gather context, LLM answer)"]
    end

    Agents -->|"answer + sources + disclaimer"| UI

    Agents -->|"chat + embeddings"| OpenAI[("OpenAI")]
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
        ECR -->|pull image| Task
        SM["Secrets Manager<br/>OPENAI_API_KEY<br/>PINECONE_API_KEY"] -->|"injected at start"| Task
        subgraph ECS["ECS cluster (Fargate)"]
            Task["Service: 1 task<br/>Streamlit container :8080"]
        end
        Task --> CW["CloudWatch Logs"]
        SG["Security group<br/>8080 from your IP"] -.-> Task
    end
    Browser([Your browser]) -->|"HTTP :8080 (test)"| Task
    Task -->|HTTPS| OpenAI[("OpenAI API")]
    Task -->|HTTPS| Pine[("Pinecone")]
    Task -->|HTTPS| Ext[("yfinance / RSS feeds")]
```
For a shared deployment, place an Application Load Balancer (HTTPS + ACM certificate) in front of the task.


## Technical Stack:
### Main Components:
- **LangChain**: Provides the framework for building and managing the agents, enabling them to communicate and collaborate effectively
- **LangGraph**: Orchestrates the multi-agent workflow, enabling seamless interaction between agents
- **PineconeDB for RAG**: Provides retrieval-augmented generation capabilities, allowing agents to access a rich knowledge base for informed responses
- **PostgreSQL for Conversation History**: Serves as a persistent storage solution for conversation history, enabling context-aware interactions
- **Streamlit**: Offers a user-friendly web interface for interacting with the agents, making it accessible to a wide audience
- **OpenAI API**: Powers the natural language understanding and generation capabilities of the agents, with the flexibility to swap in other providers as needed
- **YFinance**: Provides real-time financial data and market insights
- **RSS Feeds**: Supplies up-to-date financial news for the News Synthesizer Agent

### Deployment Components:
- **Docker**: Enables containerization of the application for consistent deployment across environments
- **AWS ECS on Fargate**: Facilitates scalable and serverless deployment of the application, ensuring high availability and performance
- **AWS ECR**: Provides a fully managed Docker container registry that makes it easy to store, manage, and deploy Docker container images
- **AWS Secrets Manager**: Securely stores and manages sensitive information such as API keys, ensuring that they are not exposed in the codebase or configuration files
- **AWS CloudWatch**: Monitors and logs application performance and operational health, providing insights for troubleshooting and optimization
- **AWS IAM**: Manages access to AWS services and resources securely

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
Usernames identify a single conversation in the CLI and Streamlit app. With `POSTGRES_URL` configured, enter the same username to resume it across restarts; `MemorySaver` is process-local. Usernames are not authenticated, so add login before exposing the app to multiple users.

1. yfinance data is free but can be delayed; replace `src/data/market_data.py` for a paid feed.
2. Conversation memory uses `PostgresSaver` when `POSTGRES_URL` is set (e.g. `postgresql://user:pass@localhost:5432/finance`); otherwise it falls back to the in-process `MemorySaver`.
3. Educational use only - not financial, investment or tax advice.

## Deploying to AWS ECS on Fargate

This guide deploys the Streamlit app as a single ECS task on AWS Fargate. Docker builds the image, Amazon ECR stores it, and ECS runs it on port `8080`. You need Docker Desktop, AWS CLI v2, and AWS credentials authorized to use ECR and create ECS resources. The commands below use PowerShell and the AWS Console.

**Important:** The app has no user authentication, and its test URL uses unencrypted HTTP. Restrict test access to your own IP and use only non-sensitive sample data. Before sharing it or entering personal/financial information, add authentication and HTTPS. Fargate, ECR storage, CloudWatch Logs, Secrets Manager, and any load balancer can incur charges.

### 1. Ingest the knowledge base

The app retrieves its knowledge base from Pinecone. From the project root, set `OPENAI_API_KEY` and `PINECONE_API_KEY` in your local, untracked `.env` file, then run:

```powershell
python -m src.rag.ingest
```

This creates/populates the Pinecone index configured in `config.yaml`. The deployed app uses that same index. Do not commit `.env` or put keys in the image.

### 2. Build and push the container image
First Login to AWS
```powershell
$env:AWS_PROFILE="nuvepro"
aws configure
```
The terminal will prompt you for four inputs. Map them exactly to your Nuvepro dashboard like this:
AWS Access Key ID [None]: <accessId>
AWS Secret Access Key [None]: <accessKey>
Default region name [None]: us-east-1
Default output format [None]: json

Verify the Login
```powershell
aws sts get-caller-identity
```

In PowerShell from the project root, choose the AWS region. Use the same region for ECR and ECS. Confirm the CLI is signed in and get your account ID:

```powershell
$Region = "us-east-1"
$AccountId = aws sts get-caller-identity --query Account --output text
$Repository = "ai-finance-assistant-VenkateshKudire"
$Registry = "$AccountId.dkr.ecr.$Region.amazonaws.com"
$Tag = "v1"
$Image = "${Registry}/${Repository}:${Tag}"
```

Run `$Image` to print the full image URI; you will paste that value into the ECS task definition.

If the identity command fails, sign in/configure the AWS CLI before continuing. Create the ECR repository once (skip this if it already exists), authenticate Docker, then build and push:

```powershell
aws ecr create-repository --repository-name $Repository --region $Region
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $Registry
docker buildx build --platform linux/amd64 --load -t "${Repository}:${Tag}" .
docker tag "${Repository}:${Tag}" $Image
docker push $Image
```

Keep the image tag for the task definition in the next step. For each update, set `$Tag` to a new value (for example, `v2`), recalculate `$Image`, then run the build, tag, and push commands again. Unique tags make it clear which image ECS is running.

### 3. Create an ECS cluster and task definition

In the AWS Console, make sure the selected region matches `$Region`, then:

1. Open **Amazon ECS → Clusters → Create cluster** and create a cluster with AWS Fargate.
2. In **Task definitions**, create a new **Fargate** task definition for **Linux/x86_64**. Start with `0.5 vCPU` and `1 GB` memory.
3. Configure a task execution role. The standard `AmazonECSTaskExecutionRolePolicy` allows ECS to pull from ECR and write logs. Create two separate plaintext secrets in AWS Secrets Manager, one for each API key. Grant the execution role `secretsmanager:GetSecretValue` for those secret ARNs; if the secrets use a customer-managed KMS key, grant the required decrypt permission as well. ECS retrieves these secrets when it starts the task.
4. Add a container named `ai-finance-assistant`, using the full ECR image URI from `$Image`. Set its port mapping to TCP `8080` and enable CloudWatch Logs.
5. In the container's **Secrets** section, map the Secrets Manager values to environment names `OPENAI_API_KEY` and `PINECONE_API_KEY`. Do not enter API keys as plain-text environment variables. Optional non-secret values such as `LLM_MODEL`, `LLM_PROVIDER`, or `LOG_LEVEL` may be set as environment variables.
6. Create the task definition. The application does not call AWS APIs itself, so it does not need application permissions in a task role.

### 4. Run the ECS service

From the cluster, choose **Create service**, select the task definition, and choose **Fargate** with desired task count `1`. For a test deployment, select a VPC with a public subnet whose route table has a route to an internet gateway, enable **Auto-assign public IP**, and attach a security group with:

- Inbound TCP port `8080` from **your current public IP address only** (CIDR `/32`).
- Outbound access to the internet, needed for OpenAI, Pinecone, market data, and news.

Create the service and wait for the task to show **Running**. In the service's **Tasks** tab, open the task's networking details and browse to `http://<task-public-ip>:8080`. This address can change whenever ECS replaces the task; update the security-group rule if your own IP changes.

For a stable, shared deployment, use an Application Load Balancer with an HTTPS listener and an ACM certificate. Allow inbound HTTPS to the load balancer, and configure the task security group to accept port `8080` only from the load balancer's security group. Because the app currently has no authentication, add an authentication layer before making it available to other users.

### 5. Deploy an update

Build and push the new image using a **new tag**. In **ECS → Task definitions**, create a new revision that uses the new image URI, then update the service to use that revision. Wait for the deployment to complete and confirm the replacement task is **Running** before removing the previous task definition revision or image.

### Cleanup and limitations

- Conversation history uses in-process `MemorySaver` and is not durable across service restarts or scaling. Keep the desired task count at `1` unless you add shared persistent checkpoint storage.
- To stop ongoing compute charges, delete the ECS service and cluster when finished. Separately remove unused ECR images/repositories, CloudWatch log groups, Secrets Manager secrets, and any load balancer; some of these may incur charges while retained.
- The app needs outbound network access to OpenAI, Pinecone, market-data, and news endpoints. It is not currently configured with persistent storage or authentication.