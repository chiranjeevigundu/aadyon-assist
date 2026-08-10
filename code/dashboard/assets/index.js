// Shared helpers ($, esc, money2) come from base.js. This page formats money with
// two decimals, i.e. base.js `money2`.
// --- form field definitions (friendly labels, no raw column names) ---
const BILL_FIELDS = [
	{
		name: "name",
		label: "Name",
		type: "text",
		required: true,
		placeholder: "e.g. Rent",
	},
	{
		name: "amount",
		label: "Amount",
		type: "money",
		required: true,
		placeholder: "0.00",
	},
	{
		name: "due_day",
		label: "Day of month due",
		type: "number",
		step: "1",
		placeholder: "1-31",
	},
	{
		name: "frequency",
		label: "Frequency",
		type: "select",
		options: [
			{ value: "monthly", label: "Monthly" },
			{ value: "weekly", label: "Weekly" },
			{ value: "quarterly", label: "Quarterly" },
			{ value: "yearly", label: "Yearly" },
		],
	},
	{
		name: "category",
		label: "Category",
		type: "text",
		placeholder: "Optional — e.g. housing",
	},
	{ name: "autopay", label: "On autopay", type: "checkbox" },
	{ name: "active", label: "Active", type: "checkbox" },
];
const SUB_FIELDS = [
	{
		name: "name",
		label: "Name",
		type: "text",
		required: true,
		placeholder: "e.g. Netflix",
	},
	{
		name: "amount",
		label: "Amount",
		type: "money",
		required: true,
		placeholder: "0.00",
	},
	{
		name: "billing_cycle",
		label: "Billing cycle",
		type: "select",
		options: [
			{ value: "monthly", label: "Monthly" },
			{ value: "yearly", label: "Yearly" },
			{ value: "weekly", label: "Weekly" },
		],
	},
	{ name: "renews_on", label: "Next renewal", type: "date" },
	{ name: "category", label: "Category", type: "text" },
	{ name: "active", label: "Active", type: "checkbox" },
];
const DEADLINE_FIELDS = [
	{
		name: "title",
		label: "What's due",
		type: "text",
		required: true,
		placeholder: "e.g. Pay property tax",
	},
	{ name: "due_date", label: "Due date", type: "date", required: true },
	{
		name: "status",
		label: "Status",
		type: "select",
		options: [
			{ value: "open", label: "Open" },
			{ value: "blocked", label: "Blocked" },
			{ value: "done", label: "Done" },
		],
	},
	{ name: "category", label: "Category", type: "text" },
	{ name: "notes", label: "Notes", type: "textarea" },
];

function rowActions(kind, id, name) {
	return `<td><div class="row-actions">
		<button class="icon-btn" data-edit="${kind}" data-id="${esc(id)}" title="Edit">Edit</button>
		<button class="icon-btn danger" data-del="${kind}" data-id="${esc(id)}" data-name="${esc(name)}" title="Delete">Delete</button>
	</div></td>`;
}

function dlClass(days) {
	if (days == null) return "muted";
	if (days <= 7) return "red";
	if (days <= 21) return "amber";
	return "green";
}
function utilClass(p) {
	if (p == null) return "muted";
	if (p >= 90) return "red";
	if (p >= 50) return "amber";
	return "green";
}
function utilColor(p) {
	if (p >= 90) return "var(--red)";
	if (p >= 50) return "var(--amber)";
	return "var(--green)";
}

let _data = {};
async function load() {
	const app = document.getElementById("app");
	let d;
	try {
		d = await (await fetchApi("/api/summary")).json();
		_data = d;
	} catch (e) {
		app.innerHTML =
			'<div class="card"><div class="empty">Could not load your data. Check your connection and refresh.</div></div>';
		return;
	}
	app.innerHTML = "";

	// --- Top deadline hero ---
	const next = (d.deadlines || [])[0];
	if (next) {
		const days = next.days_left;
		app.append(
			$(`<div class="card"><div class="hero">
      <div><div class="count ${dlClass(days)}">${days == null ? "—" : days}</div><div class="label">days left</div></div>
      <div style="flex:1;min-width:220px">
        <div style="font-size:17px;font-weight:600">${esc(next.title)}</div>
        <div class="sub" style="color:var(--muted);margin-top:4px">Due ${esc(next.due_date)} ·
          <span class="pill ${next.status === "blocked" ? "amber" : "muted"}">${esc(next.status)}</span></div>
        ${next.blocked_on ? `<div style="margin-top:6px;color:var(--amber)">⛔ Blocked on: ${esc(next.blocked_on)}</div>` : ""}
        ${next.notes ? `<div style="margin-top:6px;color:var(--muted);font-size:13px">${esc(next.notes)}</div>` : ""}
      </div></div></div>`),
		);
	}

	// --- All deadlines ---
	const dls = d.deadlines || [];
	const dlRows = dls
		.map(
			(x) => `<tr>
      <td>${esc(x.title)}</td><td>${esc(x.due_date)}</td>
      <td class="num"><span class="pill ${dlClass(x.days_left)}">${x.days_left == null ? "—" : `${x.days_left}d`}</span></td>
      <td><span class="pill ${x.status === "blocked" ? "amber" : "muted"}">${esc(x.status)}</span></td>
      <td>${esc(x.blocked_on || "")}</td>${rowActions("deadlines", x.id, x.title)}</tr>`,
		)
		.join("");
	app.append(
		$(`<div class="card">
      <div class="section-head"><h2>Deadlines</h2><button class="btn small" data-add="deadlines">+ Add deadline</button></div>
    ${dls.length ? `<table><thead><tr><th>Item</th><th>Due</th><th>Left</th><th>Status</th><th>Blocked on</th><th></th></tr></thead><tbody>${dlRows}</tbody></table>` : '<div class="empty">No deadlines yet.</div>'}</div>`),
	);

	// --- Debts ---
	const t = d.debt_totals || {};
	const debtRows = (d.debts || [])
		.map((x) => {
			const u = x.utilization_pct;
			return `<tr>
      <td>${esc(x.name)} ${x.priority_rank ? `<span class="pill muted">#${x.priority_rank}</span>` : ""}</td>
      <td class="num">${money2(x.balance)}</td>
      <td class="num">${Number(x.apr).toFixed(2)}%</td>
      <td class="num">${money2(x.min_payment)}</td>
      <td class="num">${money2(x.est_monthly_interest)}</td>
      <td>${u == null ? '<span class="empty">—</span>' : `<span class="pill ${utilClass(u)}">${u}%</span><div class="bar"><span style="width:${Math.min(u, 100)}%;background:${utilColor(u)}"></span></div>`}</td>
    </tr>`;
		})
		.join("");
	app.append(
		$(`<div class="card"><h2>Debts · payoff order</h2>
    <div class="stats" style="margin-bottom:14px">
      <div class="stat"><span class="v">${money2(t.total_debt)}</span><span class="k">Total debt</span></div>
      <div class="stat"><span class="v">${money2(t.total_min_payments)}</span><span class="k">Monthly minimums</span></div>
      <div class="stat"><span class="v" style="color:var(--red)">${money2(t.est_monthly_interest)}</span><span class="k">Interest / month</span></div>
      <div class="stat"><span class="v" style="color:var(--red)">${money2(t.est_annual_interest)}</span><span class="k">Interest / year</span></div>
    </div>
    <table><thead><tr><th>Debt</th><th class="num">Balance</th><th class="num">APR</th><th class="num">Min</th><th class="num">Int/mo</th><th>Utilization</th></tr></thead>
    <tbody>${debtRows || '<tr><td colspan=6 class="empty">No debts.</td></tr>'}</tbody></table></div>`),
	);

	// --- Bills / Subscriptions / Shifts ---
	const section = (title, rows, head, body, addKind, addLabel) =>
		`<div class="card">
      <div class="section-head"><h2>${title}</h2>${addKind ? `<button class="btn small" data-add="${addKind}">+ ${addLabel}</button>` : ""}</div>
      ${rows.length ? `<table><thead>${head}</thead><tbody>${body}</tbody></table>` : `<div class="empty">Nothing here yet.</div>`}</div>`;
	const wrap = $('<div class="grid2"></div>');
	wrap.append(
		$(
			section(
				"Bills",
				d.bills || [],
				'<tr><th>Name</th><th class="num">Amount</th><th>Due</th><th></th></tr>',
				(d.bills || [])
					.map(
						(b) =>
							`<tr><td>${esc(b.name)}</td><td class="num">${money2(b.amount)}</td><td>${b.due_day ? `day ${b.due_day}` : esc(b.frequency)}</td>${rowActions("bills", b.id, b.name)}</tr>`,
					)
					.join(""),
				"bills",
				"Add bill",
			),
		),
	);
	wrap.append(
		$(
			section(
				"Subscriptions",
				d.subscriptions || [],
				'<tr><th>Name</th><th class="num">Amount</th><th>Renews</th><th></th></tr>',
				(d.subscriptions || [])
					.map(
						(s) =>
							`<tr><td>${esc(s.name)}</td><td class="num">${money2(s.amount)}</td><td>${esc(s.renews_on || s.billing_cycle)}</td>${rowActions("subscriptions", s.id, s.name)}</tr>`,
					)
					.join(""),
				"subscriptions",
				"Add subscription",
			),
		),
	);
	app.append(wrap);

	app.append(
		$(
			section(
				"Recent shifts",
				d.shifts || [],
				'<tr><th>Date</th><th>Employer</th><th class="num">Hours</th><th class="num">Est. pay</th><th>Status</th></tr>',
				(d.shifts || [])
					.map(
						(s) =>
							`<tr><td>${esc(s.shift_date)}</td><td>${esc(s.employer)}</td><td class="num">${s.hours ?? "—"}</td><td class="num">${money2(s.est_pay)}</td><td><span class="pill muted">${esc(s.status)}</span></td></tr>`,
					)
					.join(""),
			),
		),
	);
}
load();

/* ---- add / edit / delete, delegated so it survives every re-render ---- */
const TRACKER_FIELDS = {
	bills: { fields: BILL_FIELDS, noun: "bill", list: () => _data.bills || [] },
	subscriptions: {
		fields: SUB_FIELDS,
		noun: "subscription",
		list: () => _data.subscriptions || [],
	},
	deadlines: {
		fields: DEADLINE_FIELDS,
		noun: "deadline",
		list: () => _data.deadlines || [],
	},
};

document.addEventListener("click", async (e) => {
	const addBtn = e.target.closest("[data-add]");
	const editBtn = e.target.closest("[data-edit]");
	const delBtn = e.target.closest("[data-del]");
	if (!addBtn && !editBtn && !delBtn) return;

	if (addBtn) {
		const kind = addBtn.getAttribute("data-add");
		const spec = TRACKER_FIELDS[kind];
		if (!spec) return;
		const values = await openForm({
			title: `Add ${spec.noun}`,
			fields: spec.fields,
			values: { active: true },
			submitLabel: `Add ${spec.noun}`,
		});
		if (!values) return;
		try {
			await apiCreate(kind, values);
			toast(`${spec.noun[0].toUpperCase() + spec.noun.slice(1)} added`);
			await load();
		} catch (err) {
			toast(`Could not add ${spec.noun}: ${err.message}`, "err");
		}
		return;
	}

	if (editBtn) {
		const kind = editBtn.getAttribute("data-edit");
		const id = editBtn.getAttribute("data-id");
		const spec = TRACKER_FIELDS[kind];
		if (!spec) return;
		const row = spec.list().find((r) => String(r.id) === String(id)) || {};
		const values = await openForm({
			title: `Edit ${spec.noun}`,
			fields: spec.fields,
			values: row,
		});
		if (!values) return;
		try {
			await apiUpdate(kind, id, values);
			toast("Saved");
			await load();
		} catch (err) {
			toast(`Could not save: ${err.message}`, "err");
		}
		return;
	}

	const kind = delBtn.getAttribute("data-del");
	const id = delBtn.getAttribute("data-id");
	const name = delBtn.getAttribute("data-name") || "this item";
	if (!TRACKER_FIELDS[kind]) return;
	if (!(await confirmAction(`Delete "${name}"? This can't be undone.`))) return;
	try {
		await apiDelete(kind, id);
		toast("Deleted");
		await load();
	} catch (err) {
		toast(`Could not delete: ${err.message}`, "err");
	}
});
