# Security

## Reporting a vulnerability

Please **don't** open a public issue for security problems. Use GitHub's **private vulnerability reporting**: the repository's **Security** tab → **Report a vulnerability**. Include steps to reproduce if you can. Expect an acknowledgement within a week.

Only the latest release gets fixes.

## How KaisenOS is designed

KaisenOS is a single-user app that runs on your own computer. It has no server or accounts, and no data leaves the machine except the optional, download-only Garmin sync. The main protections, each backed by automated tests in `Fitness/tests/`:

| Area | Protection |
|---|---|
| **Data location** | All personal data lives in one per-user folder outside the code (`src/paths.py`), so it can't be committed by accident. |
| **File permissions** | The data folder is `0700` and its files `0600` (macOS/Linux). The process runs with `umask 077`, so new files are private too. |
| **Network exposure** | The server binds to `127.0.0.1` only. The launcher refuses other addresses and refuses to run as root. |
| **DNS rebinding** | Requests whose `Host` isn't `127.0.0.1`, `localhost` or `[::1]` are rejected (HTTP 421). |
| **CSRF** | Requests that change data are rejected if they come from another site (`Origin` / `Sec-Fetch-Site` checks), including "simple" requests that skip CORS preflight. |
| **Browser hardening** | A strict Content Security Policy (scripts only from the app, no `eval`, no framing), plus `X-Frame-Options: DENY`, `nosniff`, `no-referrer` and a same-origin resource policy. |
| **XSS** | The UI is React with no raw-HTML rendering. AI replies are shown as text, never as HTML (a test enforces this). |
| **SQL injection** | All queries are parameterized. The few that build column lists use fixed allow-lists (a test checks this). |
| **Input validation** | Every write goes through Pydantic schemas with types and ranges. |
| **File access** | Dashboard files are served only from the built `dist/` folder, with path-traversal checks. Backup restore accepts only backup names matching a strict pattern, inside the backups folder, after an integrity check. |
| **AI model access** | Ollama is reached only at `localhost`. `OLLAMA_HOST`, proxies, redirects and Ollama cloud models are refused. The model has no tools and can't write data: its output goes to a review screen first. |
| **Network boundary** | A test fails if network libraries are imported anywhere except the Garmin sync script and the localhost Ollama client. |
| **Secrets** | The Garmin key is read from `.env` (gitignored, `0600`) and never logged, printed or stored. Access tokens stay in memory, and TLS certificates are verified. |
| **Dependencies** | Python packages are pinned. CI runs `pip-audit` and `npm audit`, and Dependabot proposes updates. |
| **Publication safety** | `tools/check_public_repo.py` scans files and git history for databases, secrets, personal paths and emails before anything is pushed. CI runs it on every push. |

## Known limitations and residual risks

Please read these before relying on KaisenOS for sensitive data:

1. **No login.** While the app is running, any program or user account **on the same computer** that can connect to `127.0.0.1:8000` can read and change your data. Browsers on other sites are blocked (see above), but local processes aren't. Use KaisenOS on a computer only you use, and stop it when you're not using it.
2. **No encryption at rest by the app.** Databases, backups and exports are plain SQLite, JSON and CSV files protected by file permissions only. Use full-disk encryption (FileVault, BitLocker, LUKS).
3. **The Garmin API key is a plain-text file** (`.env`, `0600`). Anyone with access to your user account can read it. Garmin keys expire after 30 days to 1 year, and you can revoke one anytime in Garmin Connect.
4. **AI output can be wrong or manipulated.** Pasted notes could contain text that misleads the model (prompt injection). The impact is limited: the model can only propose entries that you review before saving, and it has no other abilities. Still, check imported numbers.
5. **Ollama is third-party software** listening on `localhost:11434`. Other local programs can also use it. Keep it updated.
6. **Inline styles are allowed by the content security policy** (the UI and charts use them). Scripts aren't.
7. **Development mode is less strict.** `npm run dev` serves the UI from a second port, and `KAISEN_DEV=1` enables the API docs page. Use `./start.sh` for normal use.
8. **Windows** gets per-account AppData protection but not the POSIX permission hardening, and the setup scripts are macOS/Linux only.
9. **No independent security audit** has been done. KaisenOS is not certified for any regulatory standard.

## Verifying it yourself

```bash
cd Fitness && .venv/bin/python3 -m pytest              # includes security + privacy tests
python3 tools/check_public_repo.py --history           # no data or secrets in the repo
```
