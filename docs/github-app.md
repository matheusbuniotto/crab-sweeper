# GitHub App settings

Create the App at **https://github.com/settings/apps/new** (personal) or the equivalent under
an organization. Everything below is a field on that form.

## Basics

| Field | Value |
|---|---|
| **GitHub App name** | `crab-sweeper` (must be globally unique) |
| **Homepage URL** | your repo URL |
| **Webhook URL** | `https://smee.io/<channel>` for local, `https://your-host/webhook` when hosted |
| **Webhook secret** | a random string; copy the same value into `GITHUB_WEBHOOK_SECRET` |
| **SSL verification** | **Enable** (leave it on) |

**SSL verification:** this is GitHub verifying the certificate of *your* webhook endpoint, not
the other way round. smee.io and any real host present valid certificates, so keep it enabled.
Only disable it if you point the webhook at a self-signed local tunnel.

## Repository permissions

| Permission | Access | Why |
|---|---|---|
| **Metadata** | Read | mandatory, always granted |
| **Pull requests** | Read and write | read the diff, post the review comment |
| **Issues** | Read and write | issue comments on PRs, and labels |
| **Contents** | Read | read repo files (reserved for later) |

`Issues: write` is what lets the App comment on and label a PR (the REST endpoints are the
`issues` ones). `Pull requests: read` covers the diff and file list.

## Subscribe to events

- **Pull request** — `opened`, `synchronize`, `ready_for_review`, `reopened`
- **Issue comment** — for `@crabsweeper re-review`

## After creating

1. **Generate a private key** — downloads a `.pem`; paste its contents into `GITHUB_PRIVATE_KEY`.
2. **Note the App ID** — top of the App page; set `GITHUB_APP_ID`.
3. **Where can this GitHub App be installed?** → **Any account**, so it plugs into other repos.
4. **Install App** → choose the repositories to review.

## Verify it works

Saving the App sends a `ping` event to the webhook. CrabSweeper answers `ignored` (expected).
Open the smee channel page to watch deliveries, then open a PR (or comment
`@crabsweeper re-review`) and the review comment should appear and update in place.
