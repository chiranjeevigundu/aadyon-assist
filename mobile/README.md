# Aadyon Assist — iPhone app

A native (Expo / React Native) client for the self-hosted Aadyon Assist backend. It reads the
same Postgres-backed API the dashboards use and renders four tabs:

- **Digital Me** — overall + four life-dimension scores (financial, visa, career, goal), each with
  its auditable sub-components, plus the life-since-birth track.
- **Tracker** — debt totals, deadlines, bills, subscriptions, recent shifts (`GET /api/summary`).
- **Agency** — read-only view of the agentic org, model-routing health, and any tasks awaiting
  your approval.
- **Settings** — set the API base URL (your Tailscale host) and test the connection.

It is **read-mostly by design.** No money, email, or filing action is ever triggered from the app
— approvals stay human-in-the-loop on the web console (`/agency`), matching golden rule #2.

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

## Build a standalone app (optional, later)

When you want it off Expo Go and onto the home screen as its own icon:

```bash
npm install -g eas-cli
eas build -p ios --profile preview   # requires an Expo account; sideload or TestFlight
```

## Layout

```
mobile/
  App.tsx                 tab navigation
  app.json                Expo config (name, icon bg, iOS ATS)
  src/
    api.ts                fetch client + persisted base URL
    theme.ts              dark "console" palette + score colours
    components.tsx        Card / Row / ScoreBadge / Screen / Loading / Error
    screens/
      DigitalMeScreen.tsx
      TrackerScreen.tsx
      AgencyScreen.tsx
      SettingsScreen.tsx
```

Endpoints used: `/api/health`, `/api/digital-me`, `/api/summary`, `/api/agency/org`,
`/api/agency/health`, `/api/agency/tasks`. All GET; nothing here writes.
