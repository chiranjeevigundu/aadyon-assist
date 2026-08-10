// A token sitting in storage is not proof of a valid session — it may be stale
// (expired, or signed with a key this server no longer uses). Verify it before
// redirecting; otherwise a rejected token bounces /login -> / -> /login forever.
(async () => {
	const tok = getToken();
	if (!tok) return;
	try {
		const res = await fetch("/api/auth/me", {
			headers: { Authorization: `Bearer ${tok}` },
		});
		if (res.ok) {
			window.location.href = "/";
			return;
		}
	} catch {
		/* network error — fall through and let them sign in normally */
	}
	localStorage.removeItem(TOKEN_KEY);
})();

const errEl = document.getElementById("error-msg");
const loginForm = document.getElementById("login-form");
const signupForm = document.getElementById("signup-form");
const modeSub = document.getElementById("mode-sub");
const toSignup = document.getElementById("to-signup");
const toLogin = document.getElementById("to-login");

function showError(msg) {
	errEl.innerText = msg;
	errEl.style.display = "block";
}
function clearError() {
	errEl.style.display = "none";
}

toSignup.querySelector("a").addEventListener("click", () => {
	loginForm.classList.add("hidden");
	signupForm.classList.remove("hidden");
	toSignup.classList.add("hidden");
	toLogin.classList.remove("hidden");
	modeSub.innerText = "Create your finance tracker account";
	clearError();
});
toLogin.querySelector("a").addEventListener("click", () => {
	signupForm.classList.add("hidden");
	loginForm.classList.remove("hidden");
	toLogin.classList.add("hidden");
	toSignup.classList.remove("hidden");
	modeSub.innerText = "Log in to your finance tracker";
	clearError();
});

loginForm.addEventListener("submit", async (e) => {
	e.preventDefault();
	const email = document.getElementById("email").value;
	const password = document.getElementById("password").value;
	const btn = e.target.querySelector("button");

	clearError();
	btn.disabled = true;
	btn.innerText = "Logging in...";

	try {
		// No redirect loop issue here since it handles auth
		const res = await fetch("/api/auth/login", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ email, password }),
		});

		const data = await res.json();

		if (!res.ok) {
			throw new Error(data.detail || "Login failed");
		}

		setToken(data.token);
		window.location.href = "/";
	} catch (err) {
		showError(err.message);
	} finally {
		btn.disabled = false;
		btn.innerText = "Log In";
	}
});

signupForm.addEventListener("submit", async (e) => {
	e.preventDefault();
	const display_name = document.getElementById("signup-name").value;
	const email = document.getElementById("signup-email").value;
	const password = document.getElementById("signup-password").value;
	const inviteGroup = document.getElementById("invite-group");
	const invite_code = document.getElementById("signup-invite").value;
	const btn = e.target.querySelector("button");

	clearError();
	btn.disabled = true;
	btn.innerText = "Signing up...";

	try {
		const body = { email, password, display_name };
		if (!inviteGroup.classList.contains("hidden") && invite_code) {
			body.invite_code = invite_code;
		}
		const res = await fetch("/api/auth/signup", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
		});

		const data = await res.json();

		if (!res.ok) {
			const msg = data.detail || "Sign up failed";
			// This server requires an invite code — reveal the field and let them retry.
			if (/invite code/i.test(msg)) {
				inviteGroup.classList.remove("hidden");
			}
			throw new Error(msg);
		}

		setToken(data.token);
		window.location.href = "/";
	} catch (err) {
		showError(err.message);
	} finally {
		btn.disabled = false;
		btn.innerText = "Sign Up";
	}
});
