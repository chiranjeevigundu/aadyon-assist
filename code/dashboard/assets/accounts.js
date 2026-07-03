function toast(m, k) {
	const t = document.getElementById("toast");
	t.className = `toast show ${k || ""}`;
	t.textContent = m;
	setTimeout(() => (t.className = "toast"), 3000);
}
async function api(method, path, body) {
	const o = { method, headers: {} };
	if (body !== undefined) {
		o.headers["Content-Type"] = "application/json";
		o.body = JSON.stringify(body);
	}
	const r = await fetchApi(path, o);
	if (r.status === 204) return null;
	const t = await r.text();
	let d;
	try {
		d = JSON.parse(t);
	} catch {
		d = t;
	}
	if (!r.ok) throw new Error(d?.detail ? `${d.detail}` : `HTTP ${r.status}`);
	return d;
}
const statusClass = (s) =>
	({ connected: "green", not_connected: "muted", error: "red" })[s] || "muted";
const provBadge = (p) =>
	({ icloud: "violet", gmail: "red", microsoft: "accent" })[p] || "muted";
const kindBadge = (k) =>
	({ deadline: "amber", bill: "red", subscription: "violet" })[k] || "muted";
const IMAP_HOSTS = {
	icloud: "imap.mail.me.com",
	gmail: "imap.gmail.com",
	microsoft: "outlook.office365.com",
};

document.getElementById("provider").onchange = (e) => {
	const p = e.target.value;
	document.getElementById("auth_type").value =
		p === "gmail"
			? "oauth_google"
			: p === "microsoft"
				? "oauth_microsoft"
				: "imap";
};

async function loadAccounts() {
	let rows;
	try {
		rows = await api("GET", "/api/email_accounts");
	} catch (e) {
		document.getElementById("list").innerHTML =
			'<span class="empty">API not reachable.</span>';
		return;
	}
	if (!rows.length) {
		document.getElementById("list").innerHTML =
			'<span class="empty">No accounts yet — add one below.</span>';
		return;
	}
	document.getElementById("list").innerHTML = rows
		.map((a) => {
			const connected = a.status === "connected";
			const syncDisc = `<button class="btn sm" data-sync="${esc(a.id)}">Sync now</button> <button class="btn ghost sm" data-disc="${esc(a.id)}">Disconnect</button>`;
			let actions;
			if (a.auth_type === "imap") {
				actions = connected
					? syncDisc
					: `<button class="btn sm" data-conn="${esc(a.id)}">Connect</button>`;
			} else if (a.auth_type === "oauth_microsoft") {
				actions = connected
					? syncDisc
					: `<button class="btn sm" data-msconn="${esc(a.id)}">Connect (Microsoft)</button>`;
			} else {
				actions = `<button class="btn sm ghost" title="Gmail OAuth ships next" disabled>Connect (Gmail soon)</button>`;
			}
			return `<div class="acct" data-id="${esc(a.id)}">
      <div class="top">
        <div><div class="who">${esc(a.email)} <span class="pill ${provBadge(a.provider)}">${esc(a.provider)}</span></div>
          <div class="meta">${esc(a.purpose || "—")} · ${esc(a.auth_type)}${a.last_sync ? ` · synced ${esc(a.last_sync.slice(0, 16).replace("T", " "))}` : ""}${a.last_error ? ` · <span style="color:var(--red)">${esc(a.last_error)}</span>` : ""}</div></div>
        <div class="row"><span class="pill ${statusClass(a.status)}">${esc(a.status)}</span>${actions}
          <button class="btn ghost sm" data-del="${esc(a.id)}">Remove</button></div>
      </div>
      <div class="connect" id="conn-${esc(a.id)}">
        <label>App-specific password for ${esc(a.email)}</label>
        <div class="row"><input type="password" id="pw-${esc(a.id)}" placeholder="xxxx-xxxx-xxxx-xxxx" style="flex:1;min-width:200px">
          <button class="btn sm" data-save="${esc(a.id)}">Save &amp; connect</button>
          <button class="btn ghost sm" data-cancel="${esc(a.id)}">Cancel</button></div>
        <div class="meta" style="margin-top:6px">Stored encrypted; verified by a test login.</div>
      </div>
      <div class="connect" id="msconn-${esc(a.id)}"></div>
    </div>`;
		})
		.join("");
	// wire
	const $$ = (s) => document.querySelectorAll(s);
	$$("[data-conn]").forEach(
		(b) =>
			(b.onclick = () =>
				document
					.getElementById(`conn-${b.dataset.conn}`)
					.classList.add("open")),
	);
	$$("[data-cancel]").forEach(
		(b) =>
			(b.onclick = () =>
				document
					.getElementById(`conn-${b.dataset.cancel}`)
					.classList.remove("open")),
	);
	$$("[data-save]").forEach(
		(b) =>
			(b.onclick = async () => {
				const id = b.dataset.save,
					pw = document.getElementById(`pw-${id}`).value.trim();
				if (!pw) {
					toast("Enter the app password", "err");
					return;
				}
				b.disabled = true;
				b.textContent = "Connecting…";
				try {
					await api("POST", `/api/email/${id}/connect`, { password: pw });
					toast("Connected ✓", "ok");
					loadAccounts();
				} catch (e) {
					toast(`Failed: ${e.message}`, "err");
					b.disabled = false;
					b.textContent = "Save & connect";
				}
			}),
	);
	$$("[data-sync]").forEach(
		(b) =>
			(b.onclick = async () => {
				b.disabled = true;
				b.textContent = "Syncing…";
				try {
					const r = await api("POST", `/api/email/${b.dataset.sync}/sync`);
					toast(`Scanned ${r.scanned}, queued ${r.queued}`, "ok");
					loadAccounts();
					loadExtractions();
				} catch (e) {
					toast(`Sync failed: ${e.message}`, "err");
				}
				b.disabled = false;
				b.textContent = "Sync now";
			}),
	);
	$$("[data-disc]").forEach(
		(b) =>
			(b.onclick = async () => {
				if (!confirm("Disconnect (forget the credentials)?")) return;
				await api("POST", `/api/email/${b.dataset.disc}/disconnect`);
				toast("Disconnected", "ok");
				loadAccounts();
			}),
	);
	$$("[data-del]").forEach(
		(b) =>
			(b.onclick = async () => {
				if (!confirm("Remove this account?")) return;
				await api("DELETE", `/api/email_accounts/${b.dataset.del}`);
				toast("Removed", "ok");
				loadAccounts();
			}),
	);
	$$("[data-msconn]").forEach(
		(b) => (b.onclick = () => msConnect(b.dataset.msconn)),
	);
}

async function msConnect(id) {
	const panel = document.getElementById(`msconn-${id}`);
	panel.classList.add("open");
	panel.innerHTML = '<div class="meta">Starting Microsoft sign-in…</div>';
	let d;
	try {
		d = await api("POST", `/api/email/${id}/ms/start`);
	} catch (e) {
		panel.innerHTML = `<div class="meta" style="color:var(--red)">${esc(e.message)}</div>`;
		return;
	}
	panel.innerHTML = `<div>1. Open <a href="${esc(d.verification_uri)}" target="_blank"><b>${esc(d.verification_uri)}</b></a><br>
    2. Enter this code: <b style="font-size:20px;letter-spacing:3px">${esc(d.user_code)}</b><br>
    3. Sign in to your university/Outlook account and approve.</div>
    <div class="meta" style="margin-top:6px" id="msst-${esc(id)}">Waiting for you to approve…</div>`;
	const deadline = Date.now() + d.expires_in * 1000;
	const tick = async () => {
		if (Date.now() > deadline) {
			const el = document.getElementById(`msst-${id}`);
			if (el) el.textContent = "Code expired — click Connect again.";
			return;
		}
		let r;
		try {
			r = await api("POST", `/api/email/${id}/ms/complete`, {
				device_code: d.device_code,
			});
		} catch (e) {
			const el = document.getElementById(`msst-${id}`);
			if (el) el.textContent = `Error: ${e.message}`;
			return;
		}
		if (r.status === "connected") {
			toast("Microsoft connected ✓", "ok");
			loadAccounts();
			return;
		}
		setTimeout(tick, (d.interval || 5) * 1000);
	};
	setTimeout(tick, (d.interval || 5) * 1000);
}

async function loadExtractions() {
	let rows;
	try {
		rows = await api("GET", "/api/email/extractions?status=pending");
	} catch (e) {
		document.getElementById("exts").innerHTML = '<span class="empty">—</span>';
		return;
	}
	if (!rows.length) {
		document.getElementById("exts").innerHTML =
			'<span class="empty">Nothing pending. Hit “Sync now” on a connected account.</span>';
		return;
	}
	document.getElementById("exts").innerHTML = rows
		.map(
			(x) => `
    <div class="ext">
      <div class="row" style="justify-content:space-between">
        <div><span class="pill ${kindBadge(x.kind)}">${esc(x.kind)}</span> <b>${esc(x.payload?.title || x.subject || "(item)")}</b></div>
        <div class="row"><button class="btn green sm" data-ok="${esc(x.id)}">Approve</button>
          <button class="btn red sm" data-no="${esc(x.id)}">Dismiss</button></div>
      </div>
      <div class="meta" style="margin-top:4px">${esc(x.summary || "")}</div>
      <div class="meta">from ${esc(x.sender || "")} · ${esc(x.account_email || "")}</div>
    </div>`,
		)
		.join("");
	document.querySelectorAll("[data-ok]").forEach(
		(b) =>
			(b.onclick = async () => {
				b.disabled = true;
				try {
					const r = await api(
						"POST",
						`/api/email/extractions/${b.dataset.ok}/approve`,
					);
					toast(`Added as ${r.applied_as}`, "ok");
					loadExtractions();
				} catch (e) {
					toast(e.message, "err");
					b.disabled = false;
				}
			}),
	);
	document.querySelectorAll("[data-no]").forEach(
		(b) =>
			(b.onclick = async () => {
				await api("POST", `/api/email/extractions/${b.dataset.no}/dismiss`);
				loadExtractions();
			}),
	);
}

document.getElementById("addBtn").onclick = async () => {
	const email = document.getElementById("email").value.trim();
	if (!email) {
		toast("Enter an email", "err");
		return;
	}
	const provider = document.getElementById("provider").value;
	try {
		await api("POST", "/api/email_accounts", {
			email,
			provider,
			purpose: document.getElementById("purpose").value.trim() || null,
			auth_type: document.getElementById("auth_type").value,
			status: "not_connected",
			imap_host: IMAP_HOSTS[provider] || null,
			imap_port: 993,
		});
		toast("Account added", "ok");
		document.getElementById("email").value = "";
		document.getElementById("purpose").value = "";
		loadAccounts();
	} catch (e) {
		toast(`Error: ${e.message}`, "err");
	}
};

loadAccounts();
loadExtractions();
