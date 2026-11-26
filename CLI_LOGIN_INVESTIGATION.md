# Flagsmith CLI login route — investigation (Wed 25 Nov 2026 ~09:15 WIB)

Question from MEMORY.md: is `flagsmith login` a fallback if the phone Master-API-key paste fails again?

## Verdict: DEAD on this VM. Do not offer it.

## What was checked
- `~/.local/bin/flagsmith --version` → v2.0.0 (present at ~/.local/bin/flagsmith, not on default PATH).
- `flagsmith login --no-browser` → exits immediately: `Error: no OS keychain available to store the session. Set FLAGSMITH_API_KEY to use a Master API key instead.`
- `flagsmith auth status` → same failure: `Error: OS keychain unavailable: exec: "dbus-launch": executable file not found in $PATH`.
- `/usr/bin/dbus-launch` absent. `dbus-daemon` / `dbus-run-session` exist, but no Secret Service provider: `gnome-keyring` is not installed and `apt-cache policy gnome-keyring` shows **no candidate** — it cannot be installed.
- Binary strings confirm the CLI uses `github.com/zalando/go-keyring` (Secret Service provider + fallback provider) and gates login on `KeychainAvailable`; Flagsmith's own blog states the CLI "stores them in the OS keychain on Linux and macOS".
- Docs checked: Flagsmith "Run Flagsmith Locally with a Coding Agent" (docs.flagsmith.com) says to authenticate the CLI with an organisation API key, not `flagsmith login` — i.e. a Master key is still the entry point; there is no key-free bootstrap for Cloud. Creating a key via `POST /api/v1/organisations/<id>/master-api-keys/` itself needs an existing auth token, and the user signed up via Google (no password for `POST /api/v1/auth/login/`).

## Consequence
- The only working route to a usable Master API key remains: user creates a FRESH key on their phone at https://app.flagsmith.com/organisation/41842/settings?tab=keys and pastes the one-time value into the Secure Vault form.
- Browser-to-vault is also dead (agent.meta.ai blocked by policy_denied in both cloud environments, 25 Nov 02:52–02:54 WIB) — the cloud browser can create a key but can never store its value.
- If the phone paste fails again: retry the paste carefully (use the page's copy button, fresh key under a NEW distinct name, paste immediately into the vault form), and delete the two orphan keys ("flagsmith-master" 02:49, "flagpilot" 02:52 — values lost/unusable) in the Flagsmith UI if they cause confusion. Do not suggest CLI login, MCP, or an SDK environment key (read-only flag evaluation, cannot create experiments).

## Related files
- Helper: `~/workspace/custom-connectors/custom.flagsmith/bin/flagsmith_api.py` (REST, `Authorization: Token <key>`, test: `get projects/` — expect HTTP 200 only with a real Master key; all stored values so far return 401).
- Org: "Oyen's Org" (ID 41842), project "flagpilot" (ID 55958), free plan.
