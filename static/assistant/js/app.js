"use strict";

(() => {
  const form = document.querySelector("#prompt-form");
  const prompt = document.querySelector("#prompt");
  const send = document.querySelector("#send-button");
  const clear = document.querySelector("#clear-button");
  const starters = [...document.querySelectorAll(".starter")];
  const exchanges = document.querySelector("#exchanges");
  const welcome = document.querySelector("#welcome");
  const pending = document.querySelector("#pending-indicator");
  const status = document.querySelector("#request-status");
  const error = document.querySelector("#error-notice");
  const count = document.querySelector("#character-count");
  const offlineNotice = document.querySelector("#offline-notice");
  const connection = document.querySelector("#connection-status");
  const install = document.querySelector("#install-button");
  let busy = false;
  let installPrompt = null;

  function updateCount() {
    count.textContent = `${prompt.value.length.toLocaleString("en-US")} / 4,000`;
  }

  function setBusy(value) {
    busy = value;
    send.disabled = value;
    clear.disabled = value;
    prompt.readOnly = value;
    starters.forEach((button) => { button.disabled = value; });
    pending.hidden = !value;
    form.setAttribute("aria-busy", String(value));
    send.firstChild.textContent = value ? "Thinking… " : "Send question ";
  }

  function showError(message) {
    error.textContent = message;
    error.hidden = false;
  }

  function appendMessage(container, kind, label, text) {
    const article = document.createElement("article");
    article.className = `message message-${kind}`;
    const meta = document.createElement("h3");
    meta.className = "message-meta";
    meta.textContent = label;
    const body = document.createElement("p");
    body.className = "message-body";
    body.textContent = text;
    article.append(meta, body);
    container.append(article);
  }

  function showAnswer(question, answer) {
    const exchange = document.createElement("li");
    exchange.className = "exchange";
    appendMessage(exchange, "user", "YOU", question);
    appendMessage(exchange, "assistant", "AI ASSISTANT", answer);
    exchanges.append(exchange);
    welcome.hidden = true;
  }

  async function readJson(response) {
    let data;
    try { data = await response.json(); }
    catch { throw new Error("The server returned an unexpected response. Please try again."); }
    if (!response.ok) {
      throw new Error(typeof data?.error?.message === "string" ? data.error.message : "Your question could not be sent. Please try again.");
    }
    return data;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    const question = prompt.value.trim();
    error.hidden = true;
    if (!question) {
      showError("Write a question first.");
      prompt.focus();
      return;
    }
    if (question.length > 4000) {
      showError("Please keep your question within 4,000 characters.");
      return;
    }

    setBusy(true);
    status.textContent = "Thinking about your question.";
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 40000);
    try {
      // Tokens and AI responses are always network-only, never part of the PWA cache.
      const tokenResponse = await fetch("/api/csrf/", {
        credentials: "same-origin", cache: "no-store", signal: controller.signal,
      });
      const tokenData = await readJson(tokenResponse);
      if (typeof tokenData.csrfToken !== "string" || !tokenData.csrfToken) {
        throw new Error("The request could not be verified. Please try again.");
      }
      const response = await fetch("/api/ask/", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-CSRFToken": tokenData.csrfToken },
        body: JSON.stringify({ prompt: question }), signal: controller.signal,
      });
      const data = await readJson(response);
      if (typeof data.answer !== "string" || !data.answer.trim()) {
        throw new Error("No answer was returned. Please try another question.");
      }
      showAnswer(question, data.answer);
      prompt.value = "";
      updateCount();
      status.textContent = "Answer ready. Your question and answer are in the conversation above.";
    } catch (failure) {
      const message = failure.name === "AbortError"
        ? "The answer took too long. Your question is still here; you can try again."
        : failure instanceof TypeError
          ? "We couldn't reach the server. Check your connection, then try again. Your question is still here."
          : failure.message || "Something went wrong. Please try again.";
      showError(message);
      status.textContent = "Question not sent successfully. Your draft has been kept.";
    } finally {
      window.clearTimeout(timer);
      setBusy(false);
    }
  });

  prompt.addEventListener("input", updateCount);
  prompt.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      if (!busy) form.requestSubmit();
    }
  });
  starters.forEach((button) => button.addEventListener("click", () => {
    if (busy) return;
    prompt.value = button.dataset.prompt;
    updateCount();
    error.hidden = true;
    prompt.focus();
  }));
  clear.addEventListener("click", () => {
    if (busy) return;
    exchanges.replaceChildren();
    welcome.hidden = false;
    prompt.value = "";
    error.hidden = true;
    updateCount();
    status.textContent = "Conversation cleared.";
    prompt.focus();
  });

  function updateConnection() {
    const offline = !navigator.onLine;
    offlineNotice.hidden = !offline;
    connection.classList.toggle("is-offline", offline);
    connection.lastChild.textContent = offline ? " Offline — answers need internet" : " Connection available";
    // onLine is only a hint. A real fetch determines whether sending is possible.
  }
  window.addEventListener("online", updateConnection);
  window.addEventListener("offline", updateConnection);
  updateConnection();

  const help = document.querySelector("#help-dialog");
  document.querySelector("#help-button").addEventListener("click", () => help.showModal());
  ["#close-help", "#help-done"].forEach((selector) => {
    document.querySelector(selector).addEventListener("click", () => help.close());
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    install.hidden = false;
  });
  install.addEventListener("click", async () => {
    if (!installPrompt) return;
    try {
      await installPrompt.prompt();
      await installPrompt.userChoice;
    } catch {
      showError("Your browser couldn't open installation. Use its app-install menu, or check Help for instructions.");
    } finally {
      installPrompt = null;
      install.hidden = true;
    }
  });
  window.addEventListener("appinstalled", () => {
    installPrompt = null;
    install.hidden = true;
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/serviceworker.js", { scope: "/" }).catch(() => {
        // Online questions still work if the browser cannot enable offline access.
        connection.lastChild.textContent = " Offline access unavailable in this browser";
      });
    });
  }
})();
