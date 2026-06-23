# Remote access to Aadyon Assist via Tailscale

The app runs on the laptop at `localhost:8000`. Tailscale lets you reach it securely
from your other devices (phone, another laptop) **anywhere**, without exposing it to the
public internet. Only devices signed into *your* Tailscale account can connect.

## One-time setup

### 1. On the laptop (the host)
1. Install Tailscale: https://tailscale.com/download (Windows).
2. Open Tailscale and **sign in** (Google/GitHub/Microsoft/email — your choice).
3. Make sure the app is running: double-click `run.bat` (it also auto-starts at login).
4. Double-click **`tailscale-serve.bat`**. It publishes `localhost:8000` to your tailnet
   over HTTPS and prints your private URL, which looks like:
   `https://<laptop-name>.<your-tailnet>.ts.net`
   - First run may take a few seconds to provision the HTTPS certificate.

### 2. On your phone / other devices
1. Install the **Tailscale** app and sign in with the **same account**.
2. Open the `https://<laptop-name>.<your-tailnet>.ts.net` URL from step 1 in any browser.
   That's it — you get the full Digital Me / Tracker / Data / Agency app.

## Day to day
- The laptop must be **on and awake** to serve. The Docker stack auto-starts at login
  (`start-aadyon.bat` in your Startup folder) and Tailscale runs as a background service,
  so after the one-time setup it "just works" whenever the laptop is on.
- To stop remote access: double-click **`tailscale-stop.bat`** (runs `tailscale serve reset`).
- Check status anytime: `tailscale serve status`.

## Security notes
- This uses `tailscale serve` (private to your tailnet) — **not** `tailscale funnel`
  (which would make it public). Do not run funnel.
- The API itself still has **no login**, so anyone with access to your tailnet devices
  can use it. Keep your Tailscale account secure (enable 2FA). If you ever want a second
  layer, we can add HTTP basic auth in front of the API.
- Never expose this publicly (no funnel, no port-forwarding) — it holds your financial and
  immigration data.

## Troubleshooting
- `tailscale: command not found` → install Tailscale and reopen the terminal.
- URL loads but shows "API not reachable" → the stack isn't up; run `run.bat`.
- HTTPS cert error on first load → wait ~30s and retry; ensure HTTPS is enabled for your
  tailnet (Tailscale admin console → DNS → "HTTPS Certificates").
