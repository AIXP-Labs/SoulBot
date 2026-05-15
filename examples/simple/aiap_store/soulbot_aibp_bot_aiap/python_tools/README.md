# AIBP Bot python_tools

Email tools for soulbot_aibp_bot — provides email send/receive, AIBP message parsing/building, trust management, thread management, and GDPR data erasure.

## Quick Start

### 1. Install dependencies

```bash
cd soulbot_aibp_bot_aiap/python_tools
pip install -r requirements.lock
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:
- `AIBP_EMAIL_ADDRESS` — your bot's email (e.g., `aibot-mybot@gmail.com`)
- `AIBP_EMAIL_PASSWORD` — Gmail App Password / QQ authorization code / 163 authorization code
- `AIBP_BOT_NAME` — bot display name
- `AIBP_OPERATOR` — operator organization name

For Gmail OAuth2 (recommended):
1. Google Cloud Console → APIs & Services → Credentials → Create OAuth 2.0 Client ID (Desktop)
2. Download JSON → save as `python_tools/credentials.json`
3. Set `AIBP_AUTH_METHOD=oauth2_gmail` in `.env`
4. Run: `python email_auth.py --init` (opens browser for authorization)

### 3. Verify

```bash
python email_inbox.py --health
```

Expected: `{"status": "healthy", "checks": {"config": ..., "sqlite": ..., "imap": ..., "smtp": ...}}`

### 4. Run via SoulBot

```
User: "Check inbox"
→ Engine Router → soulbot_aibp_bot [node mode]
→ InboxPipeline: python email_inbox.py --check-unseen
→ Display AIBP messages
```

## Tools

| Tool | CLI | Purpose |
|------|-----|---------|
| `email_inbox.py` | `--check-unseen` / `--mark-read --uid X` / `--health` / `--backup` / `--startup-check` | Inbox operations |
| `email_send.py` | `--stdin` | Send email (JSON via stdin) |
| `email_validate.py` | `--address X` | Validate AIBP address |
| `email_auth.py` | `--init` / `--status` / `--revoke` | Gmail OAuth2 |
| `aibp_parser.py` | `--stdin` | Parse AIBP email (JSON via stdin) |
| `aibp_builder.py` | `--stdin` | Build AIBP email (JSON via stdin) |
| `trust_check.py` | `--agent X --required-level Y` / `--set-level` / `--get` / `--block` / `--record` / `--decay` / `--list` | Trust management |
| `thread_manager.py` | `--create` / `--get` / `--add-message` / `--close` / `--list` / `--find` | Thread management |
| `data_erasure.py` | `--agent X --confirm` / `--dry-run` | GDPR data erasure |

## Email Providers

| Provider | Auth | Notes |
|----------|------|-------|
| Gmail | App Password or OAuth2 | Recommended: OAuth2 (`email_auth.py --init`) |
| Outlook | OAuth2 (Phase 5) | Basic Auth ends 2026-04-30 |
| QQ | Authorization code | Not login password. Settings → Account Security → Generate |
| 163/126 | Authorization code | SMTP port 465 (not 994) |
| Custom domain | Password | Set `AIBP_IMAP_HOST` / `AIBP_SMTP_HOST` in `.env` |

## Architecture

```
AISOP (.aisop.json)          python_tools/
┌─────────────────┐          ┌──────────────────┐
│ main.aisop.json │ ──cmd──→ │ email_inbox.py   │
│ messaging       │ ──cmd──→ │ aibp_builder.py  │
│ trust           │ ──cmd──→ │ trust_check.py   │
│ ...             │          │ thread_manager.py│
└─────────────────┘          └──────────────────┘
        │                            │
        └── AI writes L1 body ──→ builder ASSERT validates
                                     │
                                 email_send.py sends
```

AI writes the complete email body (greeting + content + sign-off + AI disclosure + closing seal). `aibp_builder.py` validates required elements via ASSERT — rejects if missing. Max 3 attempts before rejection.

## Closing Seal

Every AIBP message must end with:
```
Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIBP V1.0.0. www.aibp.dev
```

## Tests

```bash
cd python_tools
pip install pytest pytest-mock
python -m pytest tests/ -v
# 107 tests, ~1 second
```

## License

Apache-2.0
