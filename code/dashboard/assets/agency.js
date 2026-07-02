function toast(m, k) {
	const t = document.getElementById("toast");
	t.className = "toast show " + (k || "");
	t.textContent = m;
	setTimeout(() => (t.className = "toast"), 2600);
}
async function api(method, path, body) {
	const o = { method, headers: {} };
	if (body !== undefined) {
		o.headers["Content-Type"] = "application/json";
		o.body = JSON.stringify(body);
	}
	const r = await fetchApi(path, o);
	const t = await r.text();
	let d;
	try {
		d = JSON.parse(t);
	} catch {
		d = t;
	}
	if (!r.ok) throw new Error((d && d.detail) || "HTTP " + r.status);
	return d;
}
const statusClass = (s) =>
	({
		queued: "muted",
		running: "accent",
		awaiting_approval: "amber",
		blocked: "red",
		failed: "red",
		done: "green",
		approved: "green",
		cancelled: "muted",
	})[s] || "muted";

async function loadHealth() {
	const h = await api("GET", "/api/agency/health");
	const routes = (h.routes || [])
		.map(
			(r) =>
				`<span class="pill">${esc(r.tier)} → ${esc(r.provider)}/${esc(r.model_id)}</span>`,
		)
		.join(" ");
	document.getElementById("health").innerHTML =
		`<span><span class="dot ${h.openrouter_key_set ? "ok" : "bad"}"></span>OpenRouter key ${h.openrouter_key_set ? "set" : '<b style="color:var(--red)">missing</b>'}</span>
     <span><span class="dot ${h.ollama_reachable ? "ok" : "bad"}"></span>Ollama ${h.ollama_reachable ? "reachable" : "offline"}</span>
     <span style="flex:1"></span>${routes}` +
		(h.openrouter_key_set
			? ""
			: `<div class="meta" style="color:var(--amber);width:100%;margin-top:8px">Add <code>OPENROUTER_API_KEY</code> to <code>.env</code> (or secrets/openrouter_api_key.txt) and restart to let agents run. Until then, tasks will show <b>blocked</b>.</div>`);
}

async function loadOrg() {
	const o = await api("GET", "/api/agency/org");
	const teams = (o.teams || [])
		.map((t) => {
			const lead = t.lead
				? `<div class="emp"><b>${esc(t.lead.name)}</b> <span class="pill violet">lead</span><div class="t">${esc(t.lead.title || "")} · ${esc(t.lead.model_tier)}</div></div>`
				: "";
			const emps = (t.employees || [])
				.map(
					(e) =>
						`<div class="emp">${esc(e.name)}<div class="t">${esc(e.title || "")} · ${esc(e.model_tier)}</div></div>`,
				)
				.join("");
			return `<div class="team"><div class="tn">${esc(t.team.name)} <span class="pill">${esc(t.team.dimension || "")}</span></div><div class="mi">${esc(t.team.mission || "")}</div>${lead}${emps}</div>`;
		})
		.join("");
	document.getElementById("org").innerHTML =
		`<div class="ceo">${o.ceo ? esc(o.ceo.name) + " · " + esc(o.ceo.title || "CEO") : "No CEO"}</div><div class="teams">${teams}</div>`;
}

const openTasks = new Set();
async function loadTasks() {
	const ts = await api("GET", "/api/agency/tasks");
	if (!ts.length) {
		document.getElementById("tasks").innerHTML =
			'<span class="empty">No tasks yet. Ask the CEO above.</span>';
		return;
	}
	document.getElementById("tasks").innerHTML = ts
		.map((t) => {
			const open = openTasks.has(t.id) ? "open" : "";
			const who = [t.team_name, t.agent_name].filter(Boolean).join(" · ");
			const actions = [];
			if (t.status === "queued")
				actions.push(
					`<button class="btn ghost sm" data-run="${t.id}">Run now</button>`,
				);
			if (t.status === "awaiting_approval") {
				actions.push(
					`<button class="btn green sm" data-ok="${t.id}">Approve</button>`,
				);
				actions.push(
					`<button class="btn red sm" data-no="${t.id}">Reject</button>`,
				);
			}
			return `<div class="task ${open}" data-id="${t.id}">
      <div class="top" data-toggle="${t.id}">
        <div><span class="ti">${esc(t.title)}</span> <span class="pill ${statusClass(t.status)}">${esc(t.status)}</span> <span class="pill">${esc(t.kind)}</span></div>
        <div class="meta">${esc(who || "unassigned")}</div>
      </div>
      <div class="body">
        ${t.description ? `<div class="meta">${esc(t.description)}</div>` : ""}
        ${t.error ? `<div class="result" style="color:var(--red)">${esc(t.error)}</div>` : ""}
        ${t.result ? `<div class="result">${esc(t.result)}</div>` : ""}
        <div style="margin-top:8px;display:flex;gap:8px">${actions.join("")}</div>
        <div class="runs" id="runs-${t.id}"></div>
      </div></div>`;
		})
		.join("");
	// wire events
	document.querySelectorAll("[data-toggle]").forEach(
		(e) =>
			(e.onclick = async () => {
				const id = e.dataset.toggle;
				const card = e.closest(".task");
				card.classList.toggle("open");
				if (card.classList.contains("open")) {
					openTasks.add(id);
					loadRuns(id);
				} else openTasks.delete(id);
			}),
	);
	document.querySelectorAll("[data-run]").forEach(
		(b) =>
			(b.onclick = async (ev) => {
				ev.stopPropagation();
				b.disabled = true;
				b.textContent = "Running…";
				try {
					await api("POST", "/api/agency/tasks/" + b.dataset.run + "/run");
					toast("Task ran", "");
				} catch (e) {
					toast(e.message, "");
				}
				loadTasks();
			}),
	);
	document.querySelectorAll("[data-ok]").forEach(
		(b) =>
			(b.onclick = async (ev) => {
				ev.stopPropagation();
				await api("POST", "/api/agency/tasks/" + b.dataset.ok + "/approve");
				toast("Approved", "");
				loadTasks();
			}),
	);
	document.querySelectorAll("[data-no]").forEach(
		(b) =>
			(b.onclick = async (ev) => {
				ev.stopPropagation();
				await api("POST", "/api/agency/tasks/" + b.dataset.no + "/reject");
				toast("Rejected", "");
				loadTasks();
			}),
	);
	// restore open run logs
	openTasks.forEach((id) => {
		const c = document.querySelector(`.task[data-id="${id}"]`);
		if (c) {
			c.classList.add("open");
			loadRuns(id);
		}
	});
}
async function loadRuns(id) {
	try {
		const runs = await api("GET", "/api/agency/runs?task_id=" + id);
		const box = document.getElementById("runs-" + id);
		if (!box) return;
		box.innerHTML = runs.length
			? '<div class="meta" style="margin-top:8px">Run log</div>' +
				runs
					.map(
						(r) =>
							`<div class="run"><b>${esc(r.agent_name || "agent")}</b> · step ${r.step} · ${esc(r.role)}${r.tool_name ? " · " + esc(r.tool_name) : ""} <span class="pill">${esc(r.provider || "")}/${esc(r.model || "")}</span><div>${esc((r.content || "").slice(0, 600))}</div></div>`,
					)
					.join("")
			: "";
	} catch (e) {}
}

document.getElementById("askBtn").onclick = async () => {
	const goal = document.getElementById("goal").value.trim();
	if (!goal) {
		toast("Type a goal first", "");
		return;
	}
	document.getElementById("askBtn").disabled = true;
	try {
		const r = await api("POST", "/api/agency/ask", { goal });
		document.getElementById("askNote").textContent =
			"Queued for the CEO — watch the task queue below.";
		document.getElementById("goal").value = "";
		loadTasks();
	} catch (e) {
		toast("Error: " + e.message, "");
	}
	document.getElementById("askBtn").disabled = false;
};

async function refresh() {
	try {
		await Promise.all([loadHealth(), loadOrg(), loadTasks()]);
	} catch (e) {
		document
			.querySelector("main")
			.insertAdjacentHTML(
				"afterbegin",
				'<div class="card">API not reachable. Is the stack up?</div>',
			);
	}
}
refresh();
setInterval(loadTasks, 6000); // live-update the queue
