# CrabSweeper

A pull-request reviewer that combines **deterministic checks** with an **AI review**, and
reports them in a single, self-updating comment — plus labels. It ships as a portable GitHub
App: run it locally, on any VPS, or as a Databricks App.

```text
webhook ──▶ verify signature ──▶ deterministic checks ──▶ AI review ──▶ one comment + labels
              (HMAC-SHA256)        (diff heuristics)      (any OpenAI-  (marker-keyed,
                                                          compatible     edited in place)
                                                          gateway)
```

## What it does

- **Deterministic checks** (repo-agnostic, no code execution): linked issue, diff size,
  source-without-tests, leftover `TODO`/`FIXME` markers, credential-looking additions, and
  merge conflicts. Two of these (`secrets`, `mergeable`) **block**; the rest warn.
- **AI review**: the model reads the diff and the linked issue and returns a summary, kind,
  worth-it verdict, findings (`P0`–`P3`), a "before merge" checklist, and labels.
- **One comment**: keyed by a hidden `<!-- crabsweeper-review -->` marker, edited in place on
  every review (no comment spam).
- **Simple fixes only**: the model may attach a `suggestion` block the author can apply with
  one click. CrabSweeper never pushes to your branch.
- **Commands**: comment `@crabsweeper re-review` (or the configured mention) to re-run.

## Providers

Any OpenAI-compatible chat endpoint works. Two presets:

| `CRABSWEEPER_LLM_PROVIDER` | Base URL | Key env |
|---|---|---|
| `openrouter` (default) | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` or `LLM_API_KEY` |
| `opencode` (the opencode router, or any other gateway) | `LLM_BASE_URL` | `LLM_API_KEY` |

Set `LLM_MODEL` to override the model. With no key the app still posts the deterministic
review and notes that the AI half is unavailable.

### Route by diff size

Pick a cheap/free model for small diffs and a stronger one for large ones:

```bash
LLM_MODEL_SMALL=auto          # free model or auto-router
LLM_MODEL_LARGE=gpt-6-luna    # stronger model
LLM_SIZE_THRESHOLD=400        # changed lines
```

### Per-run budget

```bash
CRABSWEEPER_MAX_COST_USD=0.10   # the ceiling you want per run
LLM_MAX_OUTPUT_TOKENS=1200      # hard bound on output
CRABSWEEPER_ENFORCE_MAX_PRICE=true   # also send OpenRouter's per-request price cap
```

Output tokens and diff size are hard-bounded; the actual `usage.cost` returned by the
gateway is shown in the comment footer (`cost $0.0021`). The USD ceiling is best-effort:
without per-token prices a pre-flight estimate cannot be exact.

## Configuration

| Variable | Meaning |
|---|---|
| `GITHUB_APP_ID` | The GitHub App id |
| `GITHUB_PRIVATE_KEY` | The App private key PEM (`\n` accepted) |
| `GITHUB_PRIVATE_KEY_BASE64` | Base64 of the PEM, if you prefer |
| `GITHUB_WEBHOOK_SECRET` | The webhook secret you set on the App |
| `CRABSWEEPER_MENTION` | Trigger handle (default `@crabsweeper`) |
| `PORT` | HTTP port (default `8000`) |

## Run locally

```bash
cp .env.example .env          # fill in GITHUB_*, SMEE_URL, and one provider
uv sync --dev
./scripts/dev.sh              # starts the smee relay and the app together
```

GitHub's **Webhook URL** must be public HTTPS, so set it to your smee channel
(`https://smee.io/<channel>`, the same value as `SMEE_URL`). When hosted, it is simply
`https://your-host/webhook`. See [docs/github-app.md](docs/github-app.md) for the exact App
fields: permissions, events, and SSL verification.

## Deploy anywhere

```bash
docker build -t crabsweeper .
docker run --env-file .env -p 8000:8000 crabsweeper
```

The same image runs on a VPS behind any reverse proxy, or as a Databricks App (point the app
command at `uvicorn crabsweeper.app:app` and inject the same env).

## Development

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run vulture src --min-confidence 80
```
