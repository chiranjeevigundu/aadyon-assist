/* Net Worth dashboard — assets − liabilities, breakdown, and trend. */

const KIND_LABEL = {
	cash: "Cash",
	investment: "Investments",
	retirement: "Retirement",
	property: "Property",
	vehicle: "Vehicles",
	crypto: "Crypto",
	other: "Other",
};

function sparkline(history) {
	if (!history || history.length < 2) {
		return '<div class="muted">Take a few daily snapshots to see the trend.</div>';
	}
	const vals = history.map((h) => Number(h.net_worth));
	const min = Math.min(...vals);
	const max = Math.max(...vals);
	const span = max - min || 1;
	const w = 600;
	const h = 60;
	const pts = vals
		.map((v, i) => {
			const x = (i / (vals.length - 1)) * w;
			const y = h - ((v - min) / span) * h;
			return `${x.toFixed(1)},${y.toFixed(1)}`;
		})
		.join(" ");
	const last = vals[vals.length - 1];
	const stroke = last >= 0 ? "var(--green)" : "var(--red)";
	return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Net worth trend">
		<polyline fill="none" stroke="${stroke}" stroke-width="2" points="${pts}"></polyline>
	</svg>`;
}

function kindRows(byKind, totalAssets) {
	if (!byKind.length) return '<tr><td colspan="3" class="muted">No assets yet.</td></tr>';
	return byKind
		.map((k) => {
			const pct = totalAssets ? Math.round((Number(k.total) / totalAssets) * 100) : 0;
			return `<tr><td>${esc(KIND_LABEL[k.kind] || k.kind)}</td>
				<td class="num">${money(k.total)}</td>
				<td class="num">${pct}%</td></tr>`;
		})
		.join("");
}

function assetRows(assets) {
	if (!assets.length) return '<tr><td colspan="3" class="muted">No assets yet — add one on the Data page.</td></tr>';
	return assets
		.map(
			(a) => `<tr><td>${esc(a.name)} ${a.institution ? `<span class="muted">· ${esc(a.institution)}</span>` : ""}</td>
			<td><span class="pill">${esc(KIND_LABEL[a.kind] || a.kind)}</span></td>
			<td class="num">${money(a.value)}</td></tr>`,
		)
		.join("");
}

function debtRows(debts) {
	if (!debts.length) return '<tr><td colspan="3" class="muted">No debts. 🎉</td></tr>';
	return debts
		.map(
			(d) => `<tr><td>${esc(d.name)}</td>
			<td class="num">${d.apr != null ? `${Number(d.apr).toFixed(1)}%` : "—"}</td>
			<td class="num">${money(d.balance)}</td></tr>`,
		)
		.join("");
}

function render(d) {
	const nw = Number(d.net_worth);
	const app = document.getElementById("app");
	app.innerHTML = `
		<div class="card">
			<div class="hero">
				<div>
					<div class="label">Net worth</div>
					<div class="nw ${nw >= 0 ? "green" : "red"}">${money2(nw)}</div>
				</div>
				<div class="stats">
					<div class="stat"><span class="v up">${money(d.total_assets)}</span><span class="k">Total assets</span></div>
					<div class="stat"><span class="v down">${money(d.total_liabilities)}</span><span class="k">Total liabilities</span></div>
				</div>
				<div style="margin-left:auto">
					<button class="btn" id="snap">Snapshot today</button>
				</div>
			</div>
			<div style="margin-top:16px">${sparkline(d.history)}</div>
		</div>

		<div class="grid2">
			<div class="card">
				<h2>Assets by type</h2>
				<table><thead><tr><th>Type</th><th class="num">Value</th><th class="num">Share</th></tr></thead>
				<tbody>${kindRows(d.assets_by_kind, Number(d.total_assets))}</tbody></table>
			</div>
			<div class="card">
				<h2>Liabilities · ${d.debts.length}</h2>
				<table><thead><tr><th>Debt</th><th class="num">APR</th><th class="num">Balance</th></tr></thead>
				<tbody>${debtRows(d.debts)}</tbody></table>
			</div>
		</div>

		<div class="card">
			<h2>Holdings · ${d.assets.length}</h2>
			<table><thead><tr><th>Asset</th><th>Type</th><th class="num">Value</th></tr></thead>
			<tbody>${assetRows(d.assets)}</tbody></table>
		</div>
	`;

	document.getElementById("snap").onclick = async (e) => {
		e.target.disabled = true;
		e.target.textContent = "Saving…";
		try {
			await fetchApi("/api/networth/snapshot", { method: "POST" });
			await load();
		} catch (err) {
			e.target.disabled = false;
			e.target.textContent = "Snapshot today";
			alert("Could not save snapshot: " + err.message);
		}
	};
}

async function load() {
	const app = document.getElementById("app");
	try {
		const res = await fetchApi("/api/networth");
		if (!res.ok) throw new Error(`HTTP ${res.status}`);
		render(await res.json());
	} catch (err) {
		app.innerHTML = `<div class="card">Couldn't load net worth: ${esc(err.message)}</div>`;
	}
}

document.addEventListener("DOMContentLoaded", load);
