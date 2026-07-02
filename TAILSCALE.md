# Remote access to Aadyon Assist via Tailscale

The app runs on the laptop at `localhost:8000`. Tailscale lets you reach it securely
from your other devices (phone, another laptop) **anywhere**, without exposing it to the
public internet. Only devices signed into *your* Tailscale account can connect.

## One-time setup

### 1. On the host machine
1. Install Tailscale: https://tailscale.com/download
2. Open Tailscale and **sign in** (Google/GitHub/Microsoft/email — your choice).
3. Make sure the app is running: `just up`.
4. Publish it to your tailnet over HTTPS:
   ```bash
   tailscale serve --bg 8000
   ```
   It prints your private URL, which looks like `https://<host-name>.<your-tailnet>.ts.net`.
   First run may take a few seconds to provision the HTTPS certificate.

### 2. On your phone / other devices
1. Install the **Tailscale** app and sign in with the **same account**.
2. Open the `https://<host-name>.<your-tailnet>.ts.net` URL from step 1 in any browser.
   That's it — you get the full Digital Me / Tracker / Data / Agency app.

## Day to day
- The host must be **on and awake** to serve. The compose services restart automatically
  (`restart: unless-stopped`) and Tailscale runs as a background service, so after the
  one-time setup it "just works" whenever the machine is on.
- To stop remote access: `tailscale serve reset`.
- Check status anytime: `tailscale serve status`.

## Security notes
- This uses `tailscale serve` (private to your tailnet) — **not** `tailscale funnel`
  (which would make it public). Do not run funnel.
- The API requires a **JWT login** (multi-user, DB-level row isolation), and Tailscale adds
  network isolation on top. Keep your Tailscale account secure (enable 2FA).
- Never expose this publicly (no funnel, no port-forwarding) — it holds your personal
  financial and immigration data.

## Troubleshooting
- `tailscale: command not found` → install Tailscale and reopen the terminal.
- URL loads but shows "API not reachable" → the stack isn't up; run `just up`.
- HTTPS cert error on first load → wait ~30s and retry; ensure HTTPS is enabled for your
  tailnet (Tailscale admin console → DNS → "HTTPS Certificates").
