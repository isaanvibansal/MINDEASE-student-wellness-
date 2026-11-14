(() => {
    "use strict";

    const toggle = document.getElementById("mindAiToggle");
    const panel = document.getElementById("mindAiPanel");
    const close = document.getElementById("mindAiClose");
    const form = document.getElementById("mindAiForm");
    const input = document.getElementById("mindAiInput");
    const messages = document.getElementById("mindAiMessages");
    const historyButton = document.getElementById("mindAiHistoryButton");
    const historyPanel = document.getElementById("mindAiHistory");
    const newChatButton = document.getElementById("mindAiNewChat");
    const sendButton = document.getElementById("mindAiSend");

    if (!toggle || !panel || !form || !input || !messages) return;

    let conversationId = null;
    let sending = false;

    function scrollToBottom() {
        messages.scrollTop = messages.scrollHeight;
    }

    function addMessage(role, text, extraClass = "") {
        const wrapper = document.createElement("div");
        wrapper.className = `mind-ai-message ${role === "user" ? "is-user" : "is-assistant"} ${extraClass}`;

        const bubble = document.createElement("div");
        bubble.className = "mind-ai-bubble";
        // textContent prevents model output from being interpreted as HTML.
        bubble.textContent = text;

        wrapper.appendChild(bubble);
        messages.appendChild(wrapper);
        scrollToBottom();
        return wrapper;
    }

    function setSending(value) {
        sending = value;
        sendButton.disabled = value;
        input.disabled = value;
        sendButton.textContent = value ? "…" : "Send";
    }

    function showWelcome() {
        messages.innerHTML = "";
        addMessage(
            "assistant",
            "Hi there 🌿 I'm MindEase AI. You can talk to me about college, stress, motivation, or anything that's on your mind. What's going on today?"
        );
    }

    async function api(url, options = {}) {
        const response = await fetch(url, {
            credentials: "same-origin",
            ...options,
            headers: {
                ...(options.headers || {}),
                ...(options.body ? { "Content-Type": "application/json" } : {})
            }
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || "Something went wrong. Please try again.");
        }
        return data;
    }

    async function loadConversationList() {
        const list = document.getElementById("mindAiHistoryList");
        list.innerHTML = '<p class="mind-ai-history-empty">Loading conversations…</p>';

        try {
            const data = await api("/api/chat/history");
            list.innerHTML = "";

            if (!data.conversations.length) {
                list.innerHTML = '<p class="mind-ai-history-empty">Your saved chats will appear here.</p>';
                return;
            }

            data.conversations.forEach((item) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "mind-ai-history-item";
                button.textContent = item.title || "Conversation";
                button.addEventListener("click", () => loadConversation(item.id));
                list.appendChild(button);
            });
        } catch (error) {
            list.innerHTML = "";
            const p = document.createElement("p");
            p.className = "mind-ai-history-empty";
            p.textContent = error.message;
            list.appendChild(p);
        }
    }

    async function loadConversation(id) {
        try {
            const data = await api(`/api/chat/history/${encodeURIComponent(id)}`);
            conversationId = data.conversation_id;
            messages.innerHTML = "";

            data.messages.forEach((item) => {
                if (item.role === "user" || item.role === "assistant") {
                    addMessage(item.role, item.content);
                }
            });

            historyPanel.hidden = true;
            input.focus();
        } catch (error) {
            addMessage("assistant", error.message);
        }
    }

    async function sendMessage(text) {
        if (sending || !text.trim()) return;

        addMessage("user", text);
        input.value = "";
        setSending(true);

        const typing = addMessage("assistant", "MindEase AI is thinking…", "is-typing");

        try {
            const data = await api("/api/chat", {
                method: "POST",
                body: JSON.stringify({
                    message: text,
                    conversation_id: conversationId
                })
            });

            typing.remove();
            conversationId = data.conversation_id;
            addMessage("assistant", data.reply);
        } catch (error) {
            typing.remove();
            addMessage("assistant", error.message);
        } finally {
            setSending(false);
            input.focus();
        }
    }

    toggle.addEventListener("click", () => {
        panel.hidden = !panel.hidden;
        toggle.setAttribute("aria-expanded", String(!panel.hidden));
        if (!panel.hidden) input.focus();
    });

    close.addEventListener("click", () => {
        panel.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
    });

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        sendMessage(input.value);
    });

    newChatButton.addEventListener("click", () => {
        conversationId = null;
        historyPanel.hidden = true;
        showWelcome();
        input.focus();
    });

    historyButton.addEventListener("click", async () => {
        historyPanel.hidden = !historyPanel.hidden;
        if (!historyPanel.hidden) await loadConversationList();
    });

    document.querySelectorAll("[data-mind-ai-prompt]").forEach((button) => {
        button.addEventListener("click", () => {
            sendMessage(button.getAttribute("data-mind-ai-prompt") || "");
        });
    });

    showWelcome();
})();
