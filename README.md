# Strands Agent on Ollama Cloud

A sample project that shows how to build an AI agent with [Strands Agents](https://strandsagents.com) (Python), run it on an [Ollama Cloud](https://ollama.com) model, and serve it as an HTTP API with Docker Compose.

It also shows how to switch the agent to **Anthropic (Claude API)** or **Amazon Bedrock** models.

## Contents

- [What's inside](#whats-inside)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [API](#api)
- [Configuration](#configuration)
- [Running without Docker](#running-without-docker)
- [Using Anthropic models](#using-anthropic-models)
- [Using Amazon Bedrock models](#using-amazon-bedrock-models)
- [Extending the agent with tools](#extending-the-agent-with-tools)
- [Troubleshooting](#troubleshooting)

## What's inside

```
.
├── app/
│   └── main.py           # FastAPI app + Strands agent
├── Dockerfile
├── docker-compose.yml    # Service definition; reads the API key from .env
├── requirements.txt
├── .env.example          # Template for your secrets
└── .env                  # Your secrets (gitignored, not committed)
```

How a request flows:

```
client ──POST /chat──▶ FastAPI (uvicorn :8000) ──▶ Strands Agent ──▶ OllamaModel ──HTTPS──▶ ollama.com (gemma4:31b)
```

- `app/main.py` creates an `OllamaModel` that points at `https://ollama.com` and sends your API key as a `Bearer` token.
- Each `/chat` request creates a new `Agent`. Requests are **stateless**: the agent doesn't remember earlier messages, and different callers' conversations never mix.
- The container runs with `restart: unless-stopped`. It keeps serving requests and restarts if it crashes or Docker restarts.

## Prerequisites

- Docker with Compose v2 (Docker Desktop, Colima, OrbStack, …)
- An Ollama API key, created at <https://ollama.com/settings/keys>

## Quick start

```bash
# 1. Add your key
cp .env.example .env
# edit .env and set OLLAMA_API_KEY=<your key>

# 2. Start Docker if it isn't running (Colima example)
colima start

# 3. Build and run
docker compose up -d --build

# 4. Check that it's up
docker compose ps
curl localhost:8000/health
```

To stop it: `docker compose down`. To follow the logs: `docker compose logs -f agent`.

## API

### `POST /chat`

Request:

```bash
curl -X POST localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "What is the capital of France?"}'
```

Response:

```json
{
  "response": "The capital of France is Paris.",
  "model": "gemma4:31b"
}
```

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | `prompt` is empty |
| 422 | Request body is missing `prompt` or isn't valid JSON |
| 502 | The model provider returned an error (bad key, unknown model, rate limit, …) |

### `GET /health`

Returns `{"status": "ok", "model": "<model>"}`. Use it for liveness checks.

Interactive API docs (Swagger UI) are at <http://localhost:8000/docs>.

## Configuration

All settings are environment variables, set in `docker-compose.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_API_KEY` | *(required)* | Ollama Cloud API key. Read from `.env`. |
| `OLLAMA_HOST` | `https://ollama.com` | Ollama endpoint. |
| `OLLAMA_MODEL` | `gemma4:31b` | Any model available on Ollama Cloud. |
| `SYSTEM_PROMPT` | `You are a helpful assistant.` | The agent's system prompt. |

Compose won't start if `OLLAMA_API_KEY` is unset (`${OLLAMA_API_KEY:?...}`). Keep real keys in `.env` only. `.env` is excluded by both `.gitignore` and `.dockerignore`, so it isn't committed or baked into the image.

To switch to another Ollama Cloud model, change `OLLAMA_MODEL` in `docker-compose.yml` and run `docker compose up -d`.

## Running without Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OLLAMA_API_KEY=<your key>
uvicorn app.main:app --reload --port 8000
```

## Using Anthropic models

Strands has a built-in `AnthropicModel` provider for the Claude API.

**1. Install the extra.** In `requirements.txt`, replace `strands-agents[ollama]` with:

```
strands-agents[anthropic]
```

**2. Swap the model** in `app/main.py`:

```python
from strands.models.anthropic import AnthropicModel

model = AnthropicModel(
    client_args={"api_key": os.environ["ANTHROPIC_API_KEY"]},
    model_id=os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"),
    max_tokens=16000,  # required by AnthropicModel
)
```

Everything else (`Agent(model=model, ...)`, the `/chat` endpoint) stays the same.

**3. Pass the key** through `docker-compose.yml` and add it to `.env`:

```yaml
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY in .env}
      ANTHROPIC_MODEL: claude-opus-5-5
```

Create a key at <https://platform.claude.com>.

**Model IDs:**

| Model | ID | Notes |
|-------|----|-------|
| Claude Opus 5.5 | `claude-opus-5-5` | Recommended default |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | Faster and cheaper |
| Claude Haiku 5.5 | `claude-haiku-5-5` | Fastest and cheapest, for simple tasks |

> **Note:** current Claude models reject sampling parameters such as `temperature`, `top_p` and `top_k` (HTTP 400). Don't pass them in `params`. Control reasoning depth with effort settings instead.

## Using Amazon Bedrock models

Strands uses Amazon Bedrock as its default provider (`BedrockModel`, via the Bedrock Converse API). It authenticates with standard AWS credentials, so you don't need an API key.

**1. Install.** In `requirements.txt`, replace `strands-agents[ollama]` with `strands-agents`. `boto3` is included.

**2. Swap the model** in `app/main.py`:

```python
from strands.models import BedrockModel

model = BedrockModel(
    model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-opus-5-5"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)
```

**3. Provide AWS credentials** to the container. Pick one of these in `docker-compose.yml`:

```yaml
    environment:
      AWS_REGION: us-east-1
      BEDROCK_MODEL_ID: anthropic.claude-opus-5-5
      # Option A: static keys, kept in .env
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      AWS_SESSION_TOKEN: ${AWS_SESSION_TOKEN:-}
      # Option B: use a named profile from your mounted ~/.aws
      # AWS_PROFILE: my-profile
    # volumes:
    #   - ~/.aws:/root/.aws:ro
```

**4. Turn on model access** in the Bedrock console for your account and region. The IAM principal needs `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`.

**Model IDs:** Bedrock model IDs start with `anthropic.` (for example `anthropic.claude-opus-5-5`, `anthropic.claude-sonnet-5-5`). Some regions and models must be called through a **cross-region inference profile** (for example `us.anthropic.…` or `global.anthropic.…`). Copy the exact ID or inference profile ARN from **Bedrock console → Model catalog / Cross-region inference**. If you get a `ValidationException` about on-demand throughput, you need the inference profile ID.

## Making the provider configurable (optional)

To switch providers with an environment variable instead of editing code:

```python
PROVIDER = os.getenv("MODEL_PROVIDER", "ollama")

if PROVIDER == "anthropic":
    from strands.models.anthropic import AnthropicModel
    model = AnthropicModel(
        client_args={"api_key": os.environ["ANTHROPIC_API_KEY"]},
        model_id=os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"),
        max_tokens=16000,
    )
elif PROVIDER == "bedrock":
    from strands.models import BedrockModel
    model = BedrockModel(
        model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-opus-5-5"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
else:
    from strands.models.ollama import OllamaModel
    model = OllamaModel(
        host=os.getenv("OLLAMA_HOST", "https://ollama.com"),
        model_id=os.getenv("OLLAMA_MODEL", "gemma4:31b"),
        ollama_client_args={"headers": {"Authorization": f"Bearer {os.environ['OLLAMA_API_KEY']}"}},
    )
```

Install all the extras together with `strands-agents[ollama,anthropic]`.

## Extending the agent with tools

Strands agents can call Python functions as tools:

```python
from strands import Agent, tool

@tool
def word_count(text: str) -> int:
    """Count the words in a piece of text."""
    return len(text.split())

agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, tools=[word_count], callback_handler=None)
```

Tool calling needs a model that supports it. Claude models do; on Ollama, check the model card for "tools" support.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `failed to connect to the docker API` | Docker isn't running. Run `colima start` or open Docker Desktop. |
| `Set OLLAMA_API_KEY in .env` on `compose up` | `.env` is missing or the key is empty. |
| `502 ... Unauthorized (status code: 401)` | The API key is invalid or expired. |
| `502 ... model ... not found` | The model name is wrong or not available on Ollama Cloud. Check <https://ollama.com/search?c=cloud>. |
| Container keeps restarting | Run `docker compose logs agent` to see the startup error. |
| Changes to code aren't reflected | Rebuild: `docker compose up -d --build`. |
