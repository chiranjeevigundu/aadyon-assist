/* Aadyon Assist — shared front-end helpers used by every dashboard page. */

// --- PWA: make the dashboard installable as a home-screen app (iOS/Android) ---
// Injected here (rather than in every page's <head>) so all pages stay in sync.
// On iOS: Safari → Share → Add to Home Screen gives a fullscreen, chrome-less
// icon. Works over plain http on the tailnet; no app store or Apple account.
(function installPwaTags() {
	const head = document.head || document.getElementsByTagName("head")[0];
	if (!head) return;
	// Let content fill the screen edge-to-edge so env(safe-area-inset-*) resolves;
	// base.css then pads for the notch / home indicator so nothing is clipped.
	const vp = head.querySelector('meta[name="viewport"]');
	if (vp && !/viewport-fit/.test(vp.getAttribute("content") || "")) {
		vp.setAttribute(
			"content",
			`${vp.getAttribute("content")}, viewport-fit=cover`,
		);
	}
	if (head.querySelector('link[rel="manifest"]')) return;
	const tags = [
		["link", { rel: "manifest", href: "/static/manifest.webmanifest" }],
		["link", { rel: "apple-touch-icon", href: "/static/assets/icon-180.png" }],
		[
			"link",
			{ rel: "icon", type: "image/png", href: "/static/assets/icon-192.png" },
		],
		["meta", { name: "apple-mobile-web-app-capable", content: "yes" }],
		["meta", { name: "mobile-web-app-capable", content: "yes" }],
		[
			"meta",
			{
				name: "apple-mobile-web-app-status-bar-style",
				content: "black-translucent",
			},
		],
		["meta", { name: "apple-mobile-web-app-title", content: "Aadyon" }],
		["meta", { name: "theme-color", content: "#0b0f17" }],
	];
	for (const [tag, attrs] of tags) {
		const e = document.createElement(tag);
		for (const k in attrs) e.setAttribute(k, attrs[k]);
		head.appendChild(e);
	}
})();

function el(h) {
	const t = document.createElement("template");
	t.innerHTML = h.trim();
	return t.content.firstChild;
}
function esc(s) {
	return (s == null ? "" : String(s)).replace(
		/[&<>"]/g,
		(c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
	);
}
function money(n) {
	return n == null
		? "—"
		: `$${Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}
function money2(n) {
	return n == null
		? "—"
		: "$" +
				Number(n).toLocaleString("en-US", {
					minimumFractionDigits: 2,
					maximumFractionDigits: 2,
				});
}
function num(n) {
	return n == null ? "—" : Number(n).toLocaleString("en-US");
}
// Back-compat alias: pages historically used `$` as the element-from-HTML helper.
const $ = el;

// --- Auth ---
const TOKEN_KEY = "aadyon.token";
function getToken() {
	return localStorage.getItem(TOKEN_KEY);
}
function setToken(t) {
	localStorage.setItem(TOKEN_KEY, t);
}
function logout() {
	localStorage.removeItem(TOKEN_KEY);
	// Guard against a redirect loop: if we're already on the login page there is
	// nowhere to send the user, and navigating again would re-run this on load.
	if (location.pathname.replace(/\/+$/, "") !== "/login") {
		window.location.href = "/login";
	}
}

async function fetchApi(url, options = {}) {
	const token = getToken();
	const headers = { ...options.headers };
	if (token) headers.Authorization = `Bearer ${token}`;
	if (
		!headers["Content-Type"] &&
		options.body &&
		typeof options.body === "string"
	) {
		headers["Content-Type"] = "application/json";
	}

	const res = await fetch(url, { ...options, headers });
	if (res.status === 401) {
		logout();
		throw new Error("Unauthorized");
	}
	return res;
}

// --- App config (public, non-sensitive UI flags) ---
// Cached for the page's lifetime; drives which chrome we render.
let _appConfig = null;
async function appConfig() {
	if (_appConfig) return _appConfig;
	try {
		const res = await fetch("/api/app-config");
		_appConfig = res.ok ? await res.json() : {};
	} catch {
		_appConfig = {};
	}
	return _appConfig;
}

// Consistent top-right nav across pages. Any <nav data-nav> is filled with the
// product link set; developer surfaces (raw table console, API docs) are appended
// only when the server reports DEV_MODE, so a normal deployment stays clean.
const NAV_LINKS = [
	["/", "Net Worth"],
	["/tracker", "Tracker"],
	["/assistant", "Assistant"],
	["/accounts", "Accounts"],
];
const DEV_NAV_LINKS = [
	["/data", "Data"],
	["/docs", "API"],
];
async function renderNav() {
	const cfg = await appConfig();
	const links = cfg.dev_mode ? NAV_LINKS.concat(DEV_NAV_LINKS) : NAV_LINKS;
	const here = location.pathname.replace(/\/+$/, "") || "/";
	const html = links
		.map(([href, label]) => {
			const ext = href === "/docs" ? ' target="_blank"' : "";
			const dev = DEV_NAV_LINKS.some(([h]) => h === href)
				? ' data-dev="1" title="Developer tool (DEV_MODE)"'
				: "";
			const active = (href === "/" ? here === "/" : here === href)
				? ' class="active"'
				: "";
			return `<a href="${href}"${ext}${active}${dev}>${label}</a>`;
		})
		.join("");
	document.querySelectorAll("[data-nav]").forEach((n) => {
		n.innerHTML = html;
	});

	// Add logout link to the header
	const headerSub = document.querySelector("header .sub:last-child");
	if (headerSub && !document.querySelector(".logout-btn")) {
		const logoutBtn = document.createElement("a");
		logoutBtn.href = "#";
		logoutBtn.className = "logout-btn";
		logoutBtn.innerText = "Logout";
		logoutBtn.onclick = (e) => {
			e.preventDefault();
			logout();
		};
		headerSub.appendChild(document.createTextNode(" · "));
		headerSub.appendChild(logoutBtn);
	}
}
document.addEventListener("DOMContentLoaded", renderNav);

/* ------------------------------------------------------------------ toasts */
// Reuses the singleton .toast/.show styles already in base.css.
let _toastTimer = null;
function toast(msg, kind = "ok") {
	let t = document.querySelector("body > .toast");
	if (!t) {
		t = document.createElement("div");
		t.className = "toast";
		document.body.appendChild(t);
	}
	t.className = `toast ${kind}`;
	t.textContent = msg;
	// reflow so the transition replays when a toast is already showing
	void t.offsetWidth;
	t.classList.add("show");
	clearTimeout(_toastTimer);
	_toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
}

/* ------------------------------------------------------- reusable form modal
 * openForm({ title, fields, values, submitLabel }) -> Promise<object|null>
 * A field: { name, label, type, required, options, step, placeholder, help }
 *   type: text | number | money | date | select | checkbox | textarea
 * Resolves with the collected values, or null if the user cancels. Pages own the
 * save call, so this stays a pure input widget with no API knowledge.
 */
function openForm({ title, fields, values = {}, submitLabel = "Save" }) {
	return new Promise((resolve) => {
		const wrap = document.createElement("div");
		wrap.className = "modal-backdrop";

		const body = fields
			.map((f) => {
				const v = values[f.name] ?? "";
				const req = f.required ? " required" : "";
				const id = `f_${f.name}`;
				let input;
				if (f.type === "select") {
					input = `<select id="${id}"${req}>${(f.options || [])
						.map(
							(o) =>
								`<option value="${esc(o.value ?? o)}"${
									String(v) === String(o.value ?? o) ? " selected" : ""
								}>${esc(o.label ?? o)}</option>`,
						)
						.join("")}</select>`;
				} else if (f.type === "checkbox") {
					input = `<input type="checkbox" id="${id}"${v ? " checked" : ""}>`;
				} else if (f.type === "textarea") {
					input = `<textarea id="${id}" rows="3"${req} placeholder="${esc(f.placeholder || "")}">${esc(v)}</textarea>`;
				} else {
					const t =
						f.type === "money" || f.type === "number"
							? "number"
							: f.type === "date"
								? "date"
								: "text";
					const step =
						f.type === "money"
							? ' step="0.01"'
							: f.step
								? ` step="${f.step}"`
								: "";
					input = `<input type="${t}" id="${id}"${req}${step} value="${esc(v)}" placeholder="${esc(f.placeholder || "")}">`;
				}
				return `<div class="form-row${f.type === "checkbox" ? " inline" : ""}">
					<label for="${id}">${esc(f.label)}${f.required ? ' <span class="req">*</span>' : ""}</label>
					${input}
					${f.help ? `<div class="help">${esc(f.help)}</div>` : ""}
				</div>`;
			})
			.join("");

		wrap.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}">
			<h3>${esc(title)}</h3>
			<form class="modal-form">${body}
				<div class="modal-actions">
					<button type="button" class="btn ghost" data-cancel>Cancel</button>
					<button type="submit" class="btn">${esc(submitLabel)}</button>
				</div>
			</form>
		</div>`;

		const close = (result) => {
			document.removeEventListener("keydown", onKey);
			wrap.remove();
			resolve(result);
		};
		const onKey = (e) => {
			if (e.key === "Escape") close(null);
		};
		document.addEventListener("keydown", onKey);
		wrap.addEventListener("click", (e) => {
			if (e.target === wrap) close(null);
		});
		wrap.querySelector("[data-cancel]").onclick = () => close(null);
		wrap.querySelector("form").onsubmit = (e) => {
			e.preventDefault();
			const out = {};
			for (const f of fields) {
				const el2 = wrap.querySelector(`#f_${f.name}`);
				if (!el2) continue;
				// `emptyAs` is for columns that are NOT NULL with a default: a
				// blank box there means "the default", not "null".
				const blank = f.emptyAs !== undefined ? f.emptyAs : null;
				if (f.type === "checkbox") out[f.name] = el2.checked;
				else if (f.type === "money" || f.type === "number")
					out[f.name] = el2.value === "" ? blank : Number(el2.value);
				else out[f.name] = el2.value === "" ? blank : el2.value;
			}
			close(out);
		};

		document.body.appendChild(wrap);
		const first = wrap.querySelector("input,select,textarea");
		if (first) first.focus();
	});
}

/* --------------------------------------------------------- confirm + delete */
function confirmAction(message) {
	return new Promise((resolve) => {
		const wrap = document.createElement("div");
		wrap.className = "modal-backdrop";
		wrap.innerHTML = `<div class="modal narrow" role="dialog" aria-modal="true">
			<h3>Are you sure?</h3>
			<p class="confirm-msg">${esc(message)}</p>
			<div class="modal-actions">
				<button type="button" class="btn ghost" data-no>Cancel</button>
				<button type="button" class="btn danger" data-yes>Delete</button>
			</div>
		</div>`;
		const close = (v) => {
			wrap.remove();
			resolve(v);
		};
		wrap.addEventListener("click", (e) => {
			if (e.target === wrap) close(false);
		});
		wrap.querySelector("[data-no]").onclick = () => close(false);
		wrap.querySelector("[data-yes]").onclick = () => close(true);
		document.body.appendChild(wrap);
		wrap.querySelector("[data-yes]").focus();
	});
}

/* ------------------------------------------------------------- CRUD helpers */
// Thin wrappers over the generic entity API so pages read declaratively.
/* Turn an error response into something worth showing a user. The API returns
 * {"detail": "..."}; anything else falls back to the status line. */
async function apiError(res) {
	const body = await res.text();
	try {
		const d = JSON.parse(body).detail;
		if (d) return new Error(String(d).trim());
	} catch {
		/* not JSON — fall through */
	}
	return new Error(body.trim() || `HTTP ${res.status}`);
}

async function apiCreate(entity, payload) {
	// Drop blank optional fields rather than POSTing explicit nulls: several
	// columns are NOT NULL with a default, and a null would violate them.
	// PATCH keeps its nulls, where clearing a field is the intent.
	const body = Object.fromEntries(
		Object.entries(payload).filter(([, v]) => v !== null),
	);
	const res = await fetchApi(`/api/${entity}`, {
		method: "POST",
		body: JSON.stringify(body),
	});
	if (!res.ok) throw await apiError(res);
	return res.json();
}
async function apiUpdate(entity, id, payload) {
	const res = await fetchApi(`/api/${entity}/${id}`, {
		method: "PATCH",
		body: JSON.stringify(payload),
	});
	if (!res.ok) throw await apiError(res);
	return res.json();
}
async function apiDelete(entity, id) {
	const res = await fetchApi(`/api/${entity}/${id}`, { method: "DELETE" });
	if (!res.ok) throw await apiError(res);
}

/* Wire add/edit/delete for one entity. Kept generic so both assets and debts
 * (and any future entity on this page) share one code path. */
function wireCrud(entity, noun, fields, rows, sel, reload) {
	const byId = Object.fromEntries(rows.map((r) => [String(r.id), r]));

	const addBtn = document.getElementById(sel.add);
	if (addBtn)
		addBtn.onclick = async () => {
			const values = await openForm({
				title: `Add ${noun}`,
				fields,
				submitLabel: `Add ${noun}`,
			});
			if (!values) return;
			try {
				await apiCreate(entity, values);
				toast(`${noun[0].toUpperCase() + noun.slice(1)} added`);
				await reload();
			} catch (err) {
				toast(`Could not add ${noun}: ${err.message}`, "err");
			}
		};

	for (const btn of document.querySelectorAll(`[${sel.edit}]`)) {
		btn.onclick = async () => {
			const id = btn.getAttribute(sel.edit);
			const values = await openForm({
				title: `Edit ${noun}`,
				fields,
				values: byId[id] || {},
			});
			if (!values) return;
			try {
				await apiUpdate(entity, id, values);
				toast("Saved");
				await reload();
			} catch (err) {
				toast(`Could not save: ${err.message}`, "err");
			}
		};
	}

	for (const btn of document.querySelectorAll(`[${sel.del}]`)) {
		btn.onclick = async () => {
			const id = btn.getAttribute(sel.del);
			const name = btn.getAttribute("data-name") || `this ${noun}`;
			if (!(await confirmAction(`Delete "${name}"? This can't be undone.`)))
				return;
			try {
				await apiDelete(entity, id);
				toast("Deleted");
				await reload();
			} catch (err) {
				toast(`Could not delete: ${err.message}`, "err");
			}
		};
	}
}

/* Page bootstrap lives in each page's own script — base.js is shared by every
 * page and must not fetch page-specific data. (The net worth loader used to live
 * here, which made every page request /api/networth and raced the real loader on
 * /tracker.) */
