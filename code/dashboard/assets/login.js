if (getToken()) {
	window.location.href = "/";
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
	e.preventDefault();
	const email = document.getElementById("email").value;
	const password = document.getElementById("password").value;
	const errEl = document.getElementById("error-msg");
	const btn = e.target.querySelector("button");

	errEl.style.display = "none";
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
		errEl.innerText = err.message;
		errEl.style.display = "block";
	} finally {
		btn.disabled = false;
		btn.innerText = "Log In";
	}
});
