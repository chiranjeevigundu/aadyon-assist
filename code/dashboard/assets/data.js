// Shared helper esc() comes from base.js.
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
let META = [],
	current = null,
	rows = [],
	editing = null;
const REF = {}; // cache of referenced-table rows for FK dropdowns

function toast(msg, kind) {
	const t = document.getElementById("toast");
	t.className = `toast show ${kind || ""}`;
	t.textContent = msg;
	setTimeout(() => (t.className = "toast"), 2800);
}

async function api(method, path, body) {
	const opt = { method, headers: {} };
	if (body !== undefined) {
		opt.headers["Content-Type"] = "application/json";
		opt.body = JSON.stringify(body);
	}
	const r = await fetchApi(path, opt);
	if (r.status === 204) return null;
	const txt = await r.text();
	let data;
	try {
		data = JSON.parse(txt);
	} catch {
		data = txt;
	}
	if (!r.ok)
		throw new Error(
			data?.detail ? JSON.stringify(data.detail) : `HTTP ${r.status}`,
		);
	return data;
}

function inputType(t) {
	if (t === "date") return "date";
	if (t === "time without time zone") return "time";
	if (t === "boolean") return "checkbox";
	if (["integer", "bigint", "smallint"].includes(t)) return "int";
	if (["numeric", "double precision", "real"].includes(t)) return "num";
	return "text";
}
function optionLabel(r) {
	const base =
		r.employer ||
		r.name ||
		r.title ||
		r.full_name ||
		r.role ||
		(r.id ? `${String(r.id).slice(0, 8)}…` : "(row)");
	return r.role && r.employer ? `${base} · ${r.role}` : base;
}
// A referenced row is selectable unless its status marks it clearly inactive.
// (Keeps job 'offer'/'ended' out, but allows queued/running tasks, active agents, etc.)
const _INACTIVE = [
	"ended",
	"cancelled",
	"done",
	"rejected",
	"inactive",
	"archived",
	"offer",
];
function isActiveRef(r) {
	return r.status == null ? true : !_INACTIVE.includes(r.status);
}
async function ensureRef(table) {
	if (!REF[table]) {
		try {
			REF[table] = await api("GET", `/api/${table}`);
		} catch {
			REF[table] = [];
		}
	}
}
async function ensureRefsFor(m) {
	for (const c of m.columns) {
		if (c.references) await ensureRef(c.references);
	}
}
function refLabel(table, id) {
	const rows = REF[table] || [];
	const r = rows.find((x) => String(x.id) === String(id));
	return r ? optionLabel(r) : id;
}

async function loadEntities() {
	META = await api("GET", "/api/entities");
	const side = document.getElementById("side");
	for (const e of META) {
		const b = document.createElement("button");
		b.className = "navbtn";
		b.dataset.table = e.table;
		b.innerHTML = `<span>${esc(e.table)}</span><span class="ct" id="ct-${esc(e.table)}">·</span>`;
		b.onclick = () => selectEntity(e.table);
		side.append(b);
	}
	if (META.length) selectEntity(META[0].table);
}
function metaFor(table) {
	return META.find((m) => m.table === table);
}

async function selectEntity(table) {
	current = table;
	document
		.querySelectorAll(".navbtn")
		.forEach((b) => b.classList.toggle("active", b.dataset.table === table));
	const m = metaFor(table);
	const main = document.getElementById("main");
	main.innerHTML = '<div class="empty">Loading…</div>';
	try {
		rows = await api("GET", `/api/${table}`);
		await ensureRefsFor(m);
	} catch (e) {
		main.innerHTML = `<div class="empty">Could not load. ${esc(e.message)}</div>`;
		return;
	}
	const ct = document.getElementById(`ct-${table}`);
	if (ct) ct.textContent = rows.length;
	if (table === "work_schedule") {
		initSchedule();
		renderScheduleEditor(m);
	} else {
		renderTable(m);
	}
}

function initSchedule() {
	const jobs = (REF.jobs || []).filter(isActiveRef);
	let jid = SCHED.job_id;
	if (!jid || !jobs.some((j) => String(j.id) === String(jid)))
		jid = jobs.length ? jobs[0].id : "";
	if (jid) loadJobSlots(jid);
	else
		SCHED = {
			job_id: "",
			days: { 0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: [] },
		};
}

// ---- Weekly schedule editor (multiple days, multiple time slots per day) ----
let SCHED = {
	job_id: "",
	days: { 0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: [] },
};

function timeToMin(t) {
	if (!t) return null;
	const p = String(t).split(":");
	return +p[0] * 60 + +(p[1] || 0);
}
function computeHours(start, end) {
	const a = timeToMin(start),
		b = timeToMin(end);
	if (a == null || b == null) return null;
	let d = b - a;
	if (d < 0) d += 24 * 60; // overnight slot
	return Math.round((d / 60) * 100) / 100;
}
function loadJobSlots(jobId) {
	const days = { 0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: [] };
	rows
		.filter((r) => String(r.job_id) === String(jobId))
		.forEach((r) => {
			const fmt = (t) => (t ? String(t).slice(0, 5) : "");
			(days[r.day_of_week] = days[r.day_of_week] || []).push({
				start: fmt(r.start_time),
				end: fmt(r.end_time),
				hours: r.hours,
			});
		});
	SCHED = { job_id: jobId, days };
}

function renderScheduleEditor(m) {
	const main = document.getElementById("main");
	const jobs = (REF.jobs || []).filter(isActiveRef);
	const jobOpts = ['<option value="">— pick a job —</option>']
		.concat(
			jobs.map(
				(j) =>
					`<option value="${esc(j.id)}" ${String(j.id) === String(SCHED.job_id) ? "selected" : ""}>${esc(optionLabel(j))}</option>`,
			),
		)
		.join("");

	let weekTotal = 0;
	const dayBlocks = WEEKDAYS.map((dn, di) => {
		const slots = SCHED.days[di] || [];
		const slotRows = slots
			.map((s, ix) => {
				const h = s.hours != null ? s.hours : "";
				if (typeof h === "number") weekTotal += h;
				else if (h !== "") weekTotal += Number(h) || 0;
				return `<div class="slot" data-day="${di}" data-idx="${ix}">
        <input type="time" data-f="start" value="${esc(s.start || "")}" title="start">
        <span class="dash">–</span>
        <input type="time" data-f="end" value="${esc(s.end || "")}" title="end">
        <input type="number" step="0.25" min="0" data-f="hours" value="${esc(h)}" placeholder="hrs" title="hours">
        <button class="btn danger sm" data-act="rm" data-day="${di}" data-idx="${ix}">✕</button>
      </div>`;
			})
			.join("");
		return `<div class="dayblock">
      <div class="dayhead"><span>${dn}</span>
        <button class="btn ghost sm" data-act="add" data-day="${di}">+ slot</button></div>
      ${slots.length ? slotRows : '<div class="noslot">— off —</div>'}
    </div>`;
	}).join("");

	main.innerHTML = `
    <div class="bar">
      <div><h2>work schedule</h2><div class="meta">Recurring weekly hours per job. Add multiple days &amp; multiple slots per day.</div></div>
      <div><a href="#" onclick="selectEntity('work_schedule');return false">Refresh</a></div>
    </div>
    <div class="schedtop">
      <label>Job &nbsp;<select id="schedJob">${jobOpts}</select></label>
      <span class="meta">Weekly total: <b id="weekTotal">${weekTotal}</b> h</span>
    </div>
    ${
			jobs.length
				? `<div class="week">${dayBlocks}</div>
      <div class="foot2">
        <button class="btn" id="schedSave">Save schedule</button>
        <span class="meta">Saving replaces this job's existing schedule rows.</span>
      </div>`
				: '<div class="empty">No active jobs. Add one in the <b>jobs</b> tab first.</div>'
		}`;

	const jobSel = document.getElementById("schedJob");
	if (jobSel)
		jobSel.onchange = () => {
			loadJobSlots(jobSel.value);
			renderScheduleEditor(m);
		};
	const saveBtn = document.getElementById("schedSave");
	if (saveBtn) saveBtn.onclick = saveSchedule;

	main.querySelectorAll("[data-act]").forEach(
		(b) =>
			(b.onclick = () => {
				const day = +b.dataset.day;
				if (b.dataset.act === "add") {
					(SCHED.days[day] = SCHED.days[day] || []).push({
						start: "",
						end: "",
						hours: "",
					});
					renderScheduleEditor(m);
				} else if (b.dataset.act === "rm") {
					SCHED.days[day].splice(+b.dataset.idx, 1);
					renderScheduleEditor(m);
				}
			}),
	);
	main.querySelectorAll(".slot input").forEach(
		(inp) =>
			(inp.oninput = () => {
				const wrap = inp.closest(".slot");
				const day = +wrap.dataset.day,
					idx = +wrap.dataset.idx,
					f = inp.dataset.f;
				const slot = SCHED.days[day][idx];
				slot[f] = inp.value;
				if (f === "start" || f === "end") {
					const h = computeHours(slot.start, slot.end);
					if (h != null) {
						slot.hours = h;
						const hi = wrap.querySelector('[data-f="hours"]');
						if (hi) hi.value = h;
					}
				}
				let t = 0;
				Object.values(SCHED.days).forEach((arr) =>
					arr.forEach((s) => {
						t += Number(s.hours) || 0;
					}),
				);
				const wt = document.getElementById("weekTotal");
				if (wt) wt.textContent = Math.round(t * 100) / 100;
			}),
	);
}

async function saveSchedule() {
	if (!SCHED.job_id) {
		toast("Pick a job first", "err");
		return;
	}
	const desired = [];
	for (const di of Object.keys(SCHED.days)) {
		for (const s of SCHED.days[di]) {
			const hours =
				s.hours !== "" && s.hours != null
					? Number(s.hours)
					: computeHours(s.start, s.end);
			if (!hours || hours <= 0) continue; // skip empty/invalid slots
			desired.push({
				job_id: SCHED.job_id,
				day_of_week: Number(di),
				start_time: s.start || null,
				end_time: s.end || null,
				hours,
				active: true,
			});
		}
	}
	const existing = rows.filter(
		(r) => String(r.job_id) === String(SCHED.job_id),
	);
	try {
		for (const d of desired) await api("POST", "/api/work_schedule", d); // add new first
		for (const r of existing) await api("DELETE", `/api/work_schedule/${r.id}`); // then remove old
		toast(
			"Schedule saved (" +
				desired.length +
				" slot" +
				(desired.length === 1 ? "" : "s") +
				")",
			"ok",
		);
		await selectEntity("work_schedule");
	} catch (e) {
		toast(`Error: ${e.message}`, "err");
		selectEntity("work_schedule");
	}
}

function fmtCell(v, c) {
	if (v == null || v === "") return '<span class="pill">—</span>';
	if (c.type === "boolean") return v ? "✓" : "✗";
	if (c.name === "day_of_week") return esc(WEEKDAYS[v] ?? v);
	if (c.references) return esc(refLabel(c.references, v));
	return esc(v);
}

function renderTable(m) {
	const main = document.getElementById("main");
	const singleton = m.table === "profile";
	const canAdd = !(singleton && rows.length >= 1);
	const cols = m.columns;
	const head = `${cols
		.map(
			(c) =>
				`<th>${esc(c.name)}${c.required ? '<span class="req">req</span>' : ""}${c.references ? '<span class="fk">fk</span>' : ""}</th>`,
		)
		.join("")}<th></th>`;
	const body = rows
		.map((r) => {
			const tds = cols
				.map((c) => `<td><div class="cell">${fmtCell(r[c.name], c)}</div></td>`)
				.join("");
			return `<tr>${tds}<td class="actions">
      <button class="btn ghost sm" onclick='openEdit(${JSON.stringify(r.id)})'>Edit</button>
      <button class="btn danger sm" onclick='del(${JSON.stringify(r.id)})'>Delete</button></td></tr>`;
		})
		.join("");
	main.innerHTML = `
    <div class="bar">
      <div><h2>${esc(m.table)}</h2><div class="meta">${rows.length} row(s) · ordered by ${esc(m.order_by)}</div></div>
      <div>${canAdd ? `<button class="btn" onclick="openAdd()">+ Add ${esc(m.table.replace(/s$/, ""))}</button>` : '<span class="meta">singleton — one row max</span>'}</div>
    </div>
    ${rows.length ? `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>` : '<div class="empty">No rows yet. Click “Add”.</div>'}`;
}

function fieldHtml(c, val) {
	const kind = inputType(c.type);
	const v = val == null ? "" : val;
	const lbl = `<label>${esc(c.name)} <span style="opacity:.6">${esc(c.type)}</span>${c.required ? '<span class="req">required</span>' : ""}</label>`;
	if (c.managed)
		return `<div class="field">${lbl}<div class="ro">${esc(v || "—")}</div></div>`;
	let input;
	if (c.references) {
		// Show only active referenced rows, but always keep the current selection visible.
		const choices = (REF[c.references] || []).filter(
			(r) => isActiveRef(r) || String(r.id) === String(val),
		);
		const opts = ['<option value="">— select —</option>']
			.concat(
				choices.map(
					(r) =>
						`<option value="${esc(r.id)}" ${String(r.id) === String(val) ? "selected" : ""}>${esc(optionLabel(r))}${isActiveRef(r) ? "" : " (inactive)"}</option>`,
				),
			)
			.join("");
		const hint = choices.length
			? ""
			: `<div class="ro" style="margin-top:4px">No active ${esc(c.references)} — add or activate one first.</div>`;
		input = `<select data-name="${esc(c.name)}" data-kind="text">${opts}</select>${hint}`;
	} else if (c.name === "day_of_week") {
		const opts = WEEKDAYS.map(
			(d, i) =>
				`<option value="${i}" ${String(i) === String(val) ? "selected" : ""}>${i} · ${d}</option>`,
		).join("");
		input = `<select data-name="${esc(c.name)}" data-kind="num">${opts}</select>`;
	} else if (kind === "checkbox") {
		input = `<input type="checkbox" data-name="${esc(c.name)}" data-kind="bool" ${val ? "checked" : ""}>`;
	} else if (c.name === "notes" || c.name === "bio") {
		input = `<textarea data-name="${esc(c.name)}" data-kind="text">${esc(v)}</textarea>`;
	} else if (kind === "date") {
		input = `<input type="date" data-name="${esc(c.name)}" data-kind="text" value="${esc(v)}">`;
	} else if (kind === "time") {
		input = `<input type="time" step="1" data-name="${esc(c.name)}" data-kind="text" value="${esc(v)}">`;
	} else if (kind === "int") {
		input = `<input type="number" step="1" data-name="${esc(c.name)}" data-kind="num" value="${esc(v)}">`;
	} else if (kind === "num") {
		input = `<input type="number" step="any" data-name="${esc(c.name)}" data-kind="num" value="${esc(v)}">`;
	} else {
		input = `<input type="text" data-name="${esc(c.name)}" data-kind="text" value="${esc(v)}">`;
	}
	return `<div class="field">${lbl}${input}</div>`;
}

async function openAdd() {
	const m = metaFor(current);
	editing = null;
	await ensureRefsFor(m);
	document.getElementById("drawerTitle").textContent =
		`Add ${m.table.replace(/s$/, "")}`;
	const writable = m.columns.filter((c) => c.writable);
	document.getElementById("form").innerHTML = writable
		.map((c) => fieldHtml(c, ""))
		.join("");
	openDrawer();
}
async function openEdit(id) {
	const m = metaFor(current);
	editing = rows.find((r) => r.id === id);
	await ensureRefsFor(m);
	document.getElementById("drawerTitle").textContent =
		`Edit ${m.table.replace(/s$/, "")}`;
	const order = m.columns
		.filter((c) => c.writable)
		.concat(m.columns.filter((c) => c.managed));
	document.getElementById("form").innerHTML = order
		.map((c) => fieldHtml(c, editing[c.name]))
		.join("");
	openDrawer();
}

function readForm() {
	const out = {};
	document.querySelectorAll("#form [data-name]").forEach((el) => {
		const name = el.dataset.name,
			kind = el.dataset.kind;
		if (kind === "bool") {
			out[name] = el.checked;
			return;
		}
		const raw = el.value;
		if (raw === "") {
			out[name] = editing ? null : undefined;
			return;
		}
		out[name] = kind === "num" ? Number(raw) : raw;
	});
	Object.keys(out).forEach((k) => {
		if (out[k] === undefined) delete out[k];
	});
	return out;
}

async function save() {
	const m = metaFor(current);
	const payload = readForm();
	try {
		if (editing) {
			await api("PATCH", `/api/${m.table}/${editing.id}`, payload);
			toast("Saved", "ok");
		} else {
			await api("POST", `/api/${m.table}`, payload);
			toast("Created", "ok");
		}
		// referenced lists may have changed (e.g. new job) — drop cache
		REF[m.table] = undefined;
		closeDrawer();
		selectEntity(current);
	} catch (e) {
		toast(`Error: ${e.message}`, "err");
	}
}
async function del(id) {
	const m = metaFor(current);
	if (
		!confirm(`Delete this ${m.table.replace(/s$/, "")}? This cannot be undone.`)
	)
		return;
	try {
		await api("DELETE", `/api/${m.table}/${id}`);
		REF[m.table] = undefined;
		toast("Deleted", "ok");
		selectEntity(current);
	} catch (e) {
		toast(`Error: ${e.message}`, "err");
	}
}

function openDrawer() {
	document.getElementById("scrim").classList.add("open");
	document.getElementById("drawer").classList.add("open");
}
function closeDrawer() {
	document.getElementById("scrim").classList.remove("open");
	document.getElementById("drawer").classList.remove("open");
	editing = null;
}
document.addEventListener("keydown", (e) => {
	if (e.key === "Escape") closeDrawer();
});

loadEntities().catch((_e) => {
	document.getElementById("main").innerHTML =
		'<div class="empty">API not reachable. Is the stack up?</div>';
});
