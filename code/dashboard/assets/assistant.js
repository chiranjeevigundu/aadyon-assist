// Assistant Web UI logic
const domList = document.getElementById("convList");
const domHist = document.getElementById("chatHistory");
const domInput = document.getElementById("chatInput");
const domSend = document.getElementById("sendBtn");
const domNew = document.getElementById("newChatBtn");

let activeCid = null;

function toast(msg, isErr) {
	const t = document.getElementById("toast");
	t.textContent = msg;
	t.className = `toast show ${isErr ? "err" : "ok"}`;
	setTimeout(() => {
		t.className = "toast";
	}, 3000);
}

function formatDate(iso) {
	const d = new Date(iso);
	if (Number.isNaN(d)) return "";
	return (
		d.toLocaleDateString() +
		" " +
		d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
	);
}

async function loadConversations() {
	try {
		const res = await fetchApi("/api/assistant/conversations");
		const list = await res.json();

		if (!list || list.length === 0) {
			domList.innerHTML = `<div class="empty" style="text-align:center;margin-top:20px">No conversations yet</div>`;
			return;
		}

		domList.innerHTML = list
			.map(
				(c) => `
            <div class="conv-item ${c.id === activeCid ? "active" : ""}" data-id="${c.id}">
                <div class="conv-title">${esc(c.title || "New Conversation")}</div>
                <div class="conv-date">${formatDate(c.updated_at)}</div>
            </div>
        `,
			)
			.join("");

		// Attach clicks
		domList.querySelectorAll(".conv-item").forEach((el) => {
			el.addEventListener("click", () => selectConversation(el.dataset.id));
		});
	} catch (e) {
		domList.innerHTML = `<div class="empty" style="text-align:center;margin-top:20px;color:var(--red)">Failed to load</div>`;
	}
}

async function selectConversation(cid) {
	activeCid = cid;
	loadConversations(); // Re-render to update active styling

	domHist.innerHTML = `<div class="empty" style="text-align:center;margin-top:20px">Loading messages...</div>`;

	try {
		const res = await fetchApi(`/api/assistant/conversations/${cid}/messages`);
		const msgs = await res.json();

		if (msgs.length === 0) {
			domHist.innerHTML = `<div class="empty" style="text-align:center;margin-top:20px">Send a message to start!</div>`;
			return;
		}

		domHist.innerHTML = msgs.map((m) => renderMessage(m)).join("");
		scrollToBottom();
	} catch (e) {
		domHist.innerHTML = `<div class="empty" style="text-align:center;margin-top:20px;color:var(--red)">Failed to load messages</div>`;
	}
}

function renderMessage(m) {
	if (m.tool_name) {
		return `
        <div class="msg assistant">
            <div class="tool-call">
                <span class="pill muted" style="margin-right:6px">Tool</span> ${esc(m.tool_name)}
            </div>
        </div>`;
	}

	if (m.role === "system") return ""; // Hide system prompts

	const isUser = m.role === "user";
	return `
    <div class="msg ${isUser ? "user" : "assistant"}">
        <div class="msg-bubble">${esc(m.content)}</div>
    </div>`;
}

function scrollToBottom() {
	domHist.scrollTop = domHist.scrollHeight;
}

// Handle sending messages (streaming)
async function sendMessage() {
	const text = domInput.value.trim();
	if (!text) return;

	domInput.value = "";
	domInput.style.height = "48px";
	domSend.disabled = true;

	// Optimistic UI for user message
	if (domHist.querySelector(".empty")) domHist.innerHTML = "";
	domHist.insertAdjacentHTML(
		"beforeend",
		renderMessage({ role: "user", content: text }),
	);
	scrollToBottom();

	// Setup assistant response bubble for streaming
	const bubbleId = `ast_${Date.now()}`;
	domHist.insertAdjacentHTML(
		"beforeend",
		`
        <div class="msg assistant" id="container_${bubbleId}">
            <div class="msg-bubble" id="${bubbleId}"><span class="empty">Thinking...</span></div>
        </div>
    `,
	);
	scrollToBottom();

	const payload = { message: text };
	if (activeCid) payload.conversation_id = activeCid;

	try {
		const token = getToken();
		const res = await fetch("/api/assistant/chat/stream", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				...(token ? { Authorization: `Bearer ${token}` } : {}),
			},
			body: JSON.stringify(payload),
		});

		if (!res.ok) throw new Error(`HTTP ${res.status}`);

		const reader = res.body.getReader();
		const decoder = new TextDecoder("utf-8");

		let done = false;
		let responseText = "";
		let firstChunk = true;

		const bubble = document.getElementById(bubbleId);

		while (!done) {
			const { value, done: doneReading } = await reader.read();
			done = doneReading;

			if (value) {
				const chunk = decoder.decode(value, { stream: true });
				const lines = chunk.split("\n");

				for (const line of lines) {
					if (line.startsWith("data: ")) {
						const dataStr = line.slice(6).trim();
						if (!dataStr) continue;

						try {
							const data = JSON.parse(dataStr);

							if (data.error) {
								bubble.innerHTML = `<span style="color:var(--red)">${esc(data.error)}</span>`;
								toast(`Error: ${data.error}`, true);
								break;
							}

							// Capture Conversation ID if it's new
							if (data.conversation_id && !activeCid) {
								activeCid = data.conversation_id;
								loadConversations();
							}

							if (data.tool) {
								const toolHtml = `
                                <div class="tool-call">
                                    <span class="pill muted" style="margin-right:6px">Tool</span> ${esc(data.tool)}
                                </div>`;
								document
									.getElementById(`container_${bubbleId}`)
									.insertAdjacentHTML("beforebegin", toolHtml);
							}

							if (data.chunk) {
								if (firstChunk) {
									bubble.innerHTML = "";
									firstChunk = false;
								}
								responseText += data.chunk;
								bubble.innerHTML = esc(responseText);
							}

							scrollToBottom();
						} catch (e) {
							console.error("Parse error chunk", dataStr, e);
						}
					}
				}
			}
		}
	} catch (err) {
		toast(`Failed to send message: ${err.message}`, true);
		const bubble = document.getElementById(bubbleId);
		if (bubble)
			bubble.innerHTML = `<span style="color:var(--red)">Failed to send message.</span>`;
	}

	domSend.disabled = false;
	domInput.focus();
}

// Auto-resize textarea
domInput.addEventListener("input", function () {
	this.style.height = "48px";
	this.style.height = `${this.scrollHeight}px`;
});

// Enter to send (Shift+Enter for newline)
domInput.addEventListener("keydown", (e) => {
	if (e.key === "Enter" && !e.shiftKey) {
		e.preventDefault();
		sendMessage();
	}
});

domSend.addEventListener("click", sendMessage);

domNew.addEventListener("click", () => {
	activeCid = null;
	loadConversations();
	domHist.innerHTML = `<div class="empty" style="text-align:center;margin-top:40px">Send a message to start a new conversation.</div>`;
	domInput.focus();
});

// Init
loadConversations();
