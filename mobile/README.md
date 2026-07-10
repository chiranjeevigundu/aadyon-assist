# Aadyon Assist — iPhone app

A native (Expo / React Native) client for the self-hosted Aadyon Assist backend. You **log in**
(multi-user; JWT stored on-device), then get five tabs:

- **Assistant** — a chat "Aadyon Assist" that reads your Digital Me and can **directly update your own
  records** (deadlines, bills, debts, subscriptions, milestones, profile) via natural language.
  Talks to `POST /api/assistant/chat`.
- **Digital Me** — overall + four life-dimension scores (financial, visa, career, goal), each with
  its auditable sub-components, plus the life-since-birth track.
- **Tracker** — debt totals, deadlines, bills, subscriptions, recent shifts (`GET /api/summary`).
- **Agency** — view of the agentic org, model-routing health, and any tasks awaiting your approval.
- **Settings** — your account (log out), the API base URL, and a connection test.

**Action boundary:** the assistant edits *your own data* directly, but anything with a real-world
side effect — money, email, filings — comes back as a **proposal you approve** (never
auto-executed), matching golden rule #2. On first launch, create an account or sign in; the token
is sent as `Authorization: Bearer` on every request and cleared on logout or a 401.

## Run it (development, via Expo Go)

You need [Node 18+](https://nodejs.org) and the **Expo Go** app on your iPhone.

```bash
cd mobile
npm install
npx expo start
```

Scan the QR code with the iPhone Camera app to open it in Expo Go.

### Connecting over Tailscale

The phone and the Mini-A must be on the **same tailnet**. In the app's **Settings** tab, set the
API base URL to your server, e.g.:

```
http://mini-a.t<your-tailnet>.ts.net:8000
```

(or the `100.x.y.z` Tailscale IP). Tap **Test connection** — it calls `GET /api/health`.

To skip that first-launch step entirely, bake your URL in at build time via
`EXPO_PUBLIC_API_BASE`: put it in `mobile/.env` (gitignored — tailnet hostnames stay out of
git) for local `expo start`, and set it once per EAS environment for cloud builds:

```bash
eas env:create --environment production --name EXPO_PUBLIC_API_BASE \
  --value http://<host>.<your-tailnet>.ts.net:8000 --visibility plaintext --scope project
```

`src/api.ts` prefers it over `app.json`'s `defaultApiBase` (localhost); the Settings tab
still overrides both at runtime.

For `npx expo start` itself to reach your laptop, run Expo over the tailnet too if the phone isn't
on the same LAN:

```bash
npx expo start --tunnel       # or --host tunnel
```

## One backend change you may need: CORS

The API currently has no CORS middleware (the dashboards are same-origin). A native app makes
cross-origin requests, so add this to `code/api/app/main.py` inside `create_app()` **before**
returning `app`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # safe: the API is already Tailscale-only (golden rule #3)
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then add the import to `requirements.txt`? — not needed; `fastapi`/`starlette` already ship it.
This keeps the app private: it stays reachable only over Tailscale, never the public internet.
(On iOS, plain-`http://` requests are allowed because `NSAllowsArbitraryLoads` is set in
`app.json` — fine for a tailnet-only backend.)

## Gmail OAuth (one-time Google Cloud setup)

Gmail scopes aren't allowed in Google's device-code flow, so the sign-in runs **on the phone**
(authorization-code + PKCE via `expo-auth-session`); the backend exchanges the one-time code and
stores only the encrypted refresh token. To enable it:

1. In [Google Cloud Console](https://console.cloud.google.com) create (or pick) a project, enable
   the **Gmail API**, and configure the OAuth consent screen (External + your account as a test
   user is fine for personal use).
2. Create an OAuth client of type **iOS** (Credentials → Create credentials → OAuth client ID).
   Bundle ID: `me.aadyon.assist`. Copy the client ID
   (`<number>-<hash>.apps.googleusercontent.com`).
3. On the server, set `GOOGLE_CLIENT_ID=<that id>` in `.env` and restart the api container
   (iOS clients have no secret; leave `GOOGLE_CLIENT_SECRET` empty).
4. In `app.json`, add the reversed client ID as a URL scheme so the sign-in can bounce back into
   the app, then rebuild (EAS build — this is a native change):

   ```json
   "scheme": "com.googleusercontent.apps.<number>-<hash>"
   ```

5. In the app: add a Gmail account (auth `OAuth · Google`) → **Connect (Google)** → sign in and
   consent. Read-only scope (`gmail.readonly`); sync works everywhere afterwards, including the
   web dashboard.

## Build a standalone app (optional, later)

When you want it off Expo Go and onto the home screen as its own icon:

```bash
npm install -g eas-cli
eas init                             # links the app to YOUR Expo account/project
eas build -p ios --profile preview   # sideload or TestFlight
```

(`app.json` carries this project's EAS `projectId`/`owner`; if you forked this repo, run
`eas init` to swap in your own.)

## Layout

```
mobile/
  App.tsx                 auth gate + tab navigation
  app.json                Expo config (name, icon bg, iOS ATS)
  src/
    api.ts                fetch client + persisted base URL + JWT token + auth/assistant calls
    theme.ts              dark "console" palette + score colours
    components.tsx        Card / Row / ScoreBadge / Screen / Loading / Error
    screens/
      LoginScreen.tsx     sign in / sign up
      AssistantScreen.tsx chat with Aadyon Assist (reads + writes your data)
      DigitalMeScreen.tsx
      TrackerScreen.tsx
      AgencyScreen.tsx
      SettingsScreen.tsx  account + API URL + log out
```

Endpoints used: `POST /api/auth/{signup,login}`, `GET /api/auth/me`, `POST /api/assistant/chat`,
`/api/health`, `/api/digital-me`, `/api/summary`, `/api/agency/*`. Every request carries the
bearer token; a 401 drops you back to the login screen.
