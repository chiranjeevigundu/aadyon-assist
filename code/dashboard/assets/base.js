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
	window.location.href = "/login";
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

// Consistent top-right nav across pages. Any <nav data-nav> is filled with the
// full link set, with the current page marked active. Keeps every page in sync.
const NAV_LINKS = [
	["/", "Digital Me"],
	["/tracker", "Tracker"],
	["/agency", "Agency"],
	["/assistant", "Assistant"],
	["/data", "Data"],
	["/accounts", "Accounts"],
	["/docs", "API"],
];
function renderNav() {
	const here = location.pathname.replace(/\/+$/, "") || "/";
	const html = NAV_LINKS.map(([href, label]) => {
		const ext = href === "/docs" ? ' target="_blank"' : "";
		const active = (href === "/" ? here === "/" : here === href)
			? ' class="active"'
			: "";
		return `<a href="${href}"${ext}${active}>${label}</a>`;
	}).join("");
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
