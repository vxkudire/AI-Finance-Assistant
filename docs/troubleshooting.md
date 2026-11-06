# Troubleshooting

Start by running commands from the repository root with the project's virtual environment activated. For most startup and dependency issues, verify the environment first:

```shell
python --version
python -m pip install -r requirements.txt
python -m pytest
```

The application targets Python 3.14. The test suite does not require API keys or a Pinecone connection.

## Installation and startup

### `ModuleNotFoundError` or missing command

The active Python environment may not have the project dependencies installed, or the command may be using a different Python than the one used for installation.

- Activate `.venv` and run `python -m pip install -r requirements.txt`.
- On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1`, or run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- Start modules from the repository root so Python can import the `src` package.

### Configuration file not found or invalid YAML

The app loads `config.yaml` by default. If `FINANCE_AI_CONFIG` is set, it uses that path instead.

- Check that the selected file exists and contains valid YAML.
- Confirm it has the required top-level sections: `llm`, `embeddings`, `pinecone`, `rag`, `agents`, and `data`.
- Remove `FINANCE_AI_CONFIG` from the environment to use the repository's default `config.yaml`.

### Port already in use

If Streamlit cannot bind its default port, stop the other process using it or select another port:

```shell
python -m streamlit run src/web_app/app.py --server.port 8502
```

## Sign-in

### Google sign-in fails or redirects to an error

The Streamlit app requires Google OAuth configuration in `.streamlit/secrets.toml`.

- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set the Google OAuth `client_id` and `client_secret`.
- In the Google OAuth client, register the redirect URI exactly as shown in the secrets file (for local development, `http://localhost:8501/oauth2callback`). The URI must match the URL and port used by the app.
- Confirm the OAuth consent screen allows the account to sign in. For an app in testing mode, the account may need to be listed as a test user.
- Sign-in requires a verified Google email address; the app rejects accounts without one.

Keep OAuth credentials in the untracked secrets file; do not commit them.

## Model and knowledge base

### Model call fails or assistant cannot answer

- Check that `OPENAI_API_KEY` is present in the repository-root `.env` when using the configured OpenAI provider.
- Check the model/provider settings in `config.yaml`. `LLM_PROVIDER` and `LLM_MODEL` can override the default provider/model; per-agent model options in `config.yaml` take precedence for that agent.
- Verify that the selected model is available to the configured provider and that the matching LangChain provider package is installed.
- Provider errors are intentionally summarized for users. Inspect the terminal running the app for the logged failure and check provider availability and account access.

### Knowledge-base retrieval returns no results

- Run `python -m src.rag.ingest` from the repository root to upload the files under `src/data/knowledge_base/`.
- Check `PINECONE_API_KEY`, the configured Pinecone index name, and the index region/cloud settings in `config.yaml`.
- Ensure the index dimension matches the configured embedding model's output dimension. If changing embedding models, configure a compatible index and re-ingest the documents.
- If Pinecone or embeddings are unavailable, agents may still answer from general knowledge, but the answer will disclose retrieval limitations.

## Market, news, and portfolio data

### Quotes or market history are missing

Market information comes from Yahoo Finance and can be delayed or temporarily unavailable.

- Check the ticker spelling and try again later. A market closed for the day or a provider issue may affect available data.
- Use **Refresh data** in the Market view or **Refresh prices** in the Portfolio view to bypass cached results.
- If the app reports rate limiting, wait before retrying; the data layer limits retries and avoids waiting through a long `Retry-After` delay.
- Missing quotes and history are reported as unavailable data rather than being replaced with invented values.

### Portfolio view is empty or does not show holdings

- Enable **Enable portfolio analysis and share with the assistant** in the sidebar. When disabled, the app does not fetch portfolio data or pass holdings to the assistant.
- Add at least one valid ticker and a positive share count in the portfolio editor.
- Some holdings may be skipped if Yahoo Finance cannot price them. The displayed value and allocations then cover priced holdings only.
- Sector information may be unavailable even when a quote succeeds; those holdings are shown with an `Unknown` sector.

### News is empty or incomplete

News is fetched from the RSS URLs in `config.yaml`; there is no separate news API key.

- Check that configured feed URLs are reachable from the machine running the app.
- If a keyword filter finds no matches, the app falls back to general headlines. If no feed can be fetched, it reports that news is unavailable.
- Retry later for transient network or feed-provider errors.

## MCP tools

### MCP client cannot start or connect to the server

- Verify that `mcp>=1.9,<2` is installed in the Python environment used by the MCP client.
- In the client configuration, set `command` to the project's Python executable and `cwd` to the repository root. See the [MCP tools API reference](mcp-api.md) for a configuration example.
- If the client does not support a working directory, set `PYTHONPATH` to the repository root.
- The server uses stdio; do not configure it as an HTTP URL. Its logs are written to stderr so they do not corrupt the MCP protocol stream.

### MCP tool returns invalid-argument error

Check the tool's documented argument names, value types, ticker formats, and limits in the [MCP tools API reference](mcp-api.md). Calculator annual rates are decimal values (for example, `0.07` means 7%), must be between `-0.99` and `1`, and the projection horizon cannot exceed 100 years.

## Conversation history

Conversation persistence is optional. Without `POSTGRES_URL`, the app uses an in-memory checkpointer, so history is lost when the process restarts. To persist conversations, configure a reachable PostgreSQL database in `POSTGRES_URL` and ensure its connection details and database are valid.

## Tests and coverage

Run the test suite from the repository root:

```shell
python -m pytest
```

Pytest reports coverage and fails if it falls below 80%. The Streamlit UI entry point is excluded from coverage because it executes UI setup at import time. For a test failure, read the first failing assertion and traceback; tests mock external services and should not require live OpenAI, Pinecone, Yahoo Finance, or RSS access.

## Still stuck?

Capture the exact command, error message, and relevant log output. Remove API keys, OAuth secrets, database URLs/passwords, and personal prompts before sharing logs or opening an issue.
