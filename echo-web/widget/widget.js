(() => {
  "use strict";
  const script = document.currentScript;
  const site = script?.dataset.site;
  if (!site || !/^[a-z][a-z0-9-]{1,62}$/.test(site)) return;
  const api = new URL(script.dataset.api || ".", script.src).href.replace(/\/$/, "");
  if (!/^https?:$/.test(new URL(api).protocol)) return;
  const endpoint = `${api}/v1/sites/${encodeURIComponent(site)}`;
  const host = document.createElement("echo-chat-widget");
  host.dataset.site = site;
  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  if (script.nonce) style.nonce = script.nonce;
  style.textContent = `
    :host{all:initial;--accent:#167089;font:15px/1.5 system-ui,sans-serif;color:#172832}
    *{box-sizing:border-box}button,textarea{font:inherit}button{cursor:pointer}button:disabled{cursor:wait;opacity:.55}
    button:focus-visible,textarea:focus-visible{outline:3px solid #f1ae32;outline-offset:3px}
    .launcher{position:fixed;right:22px;bottom:22px;z-index:2147483000;border:0;border-radius:28px;padding:15px 23px;background:var(--accent);color:white;box-shadow:0 6px 24px #12283233}
    .panel{position:fixed;right:22px;bottom:90px;width:380px;height:min(570px,75dvh);z-index:2147483000;background:#fff;border:1px solid #ccd9df;border-radius:18px;box-shadow:0 12px 48px #12283233;display:flex;flex-direction:column;overflow:hidden}
    [hidden]{display:none!important}header{display:flex;align-items:center;gap:10px;padding:15px 17px;background:#f0f6f8;border-bottom:1px solid #dce7eb}h2{font-size:16px;margin:0;flex:1}
    .plain{border:0;background:transparent;color:#294652;padding:7px;border-radius:6px}.messages{flex:1;overflow:auto;padding:16px;min-height:80px;overscroll-behavior:contain}
    .bubble{white-space:pre-wrap;overflow-wrap:anywhere;margin:0 0 12px;padding:10px 13px;border-radius:12px;background:#eef4f6}.user{background:#e3f0f2;margin-left:30px}.assistant{margin-right:15px}
    .references{display:block;font-size:12px;color:#465f6b;margin-top:9px}.status{min-height:24px;font-size:12px;color:#475f6c;padding:0 16px 6px}
    form{display:flex;align-items:end;gap:8px;padding:12px;border-top:1px solid #dce7eb}textarea{resize:none;flex:1;min-width:0;border:1px solid #a7bec9;border-radius:8px;padding:9px;color:#172832;background:#fff}
    .send{border:0;border-radius:8px;background:var(--accent);color:white;padding:10px 14px}.footer{font-size:11px;color:#566b75;padding:0 14px 9px}
    @media(max-width:440px){.panel{right:10px;left:10px;bottom:82px;width:auto;height:70dvh}.launcher{right:12px;bottom:14px}}
    @media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
  `;
  shadow.append(style);
  const surface = document.createElement("div");
  surface.innerHTML = `
    <button class="launcher" type="button" aria-expanded="false" aria-controls="echo-panel">Chat</button>
    <section class="panel" id="echo-panel" role="dialog" aria-label="Website assistant" hidden>
      <header><h2>Website assistant</h2><button class="plain reset" type="button">New chat</button><button class="plain close" type="button" aria-label="Close chat">✕</button></header>
      <div class="messages" role="log" aria-live="polite" aria-relevant="additions text"></div>
      <div class="status" role="status"></div>
      <form><textarea aria-label="Your message" placeholder="Ask a question…" maxlength="4000" rows="2" required></textarea><button class="send" type="submit">Send</button></form>
      <div class="footer">AI answers can be mistaken. Confirm important details with the business.</div>
    </section>`;
  shadow.append(surface);
  document.body.append(host);
  const launcher = shadow.querySelector(".launcher");
  const panel = shadow.querySelector(".panel");
  const heading = shadow.querySelector("h2");
  const log = shadow.querySelector(".messages");
  const status = shadow.querySelector(".status");
  const input = shadow.querySelector("textarea");
  const send = shadow.querySelector(".send");
  const reset = shadow.querySelector(".reset");
  let token = null;
  let busy = false;
  let config = null;
  let controller = null;

  function bubble(role, text) {
    const element = document.createElement("div");
    element.className = `bubble ${role}`;
    element.textContent = text;
    log.append(element);
    log.scrollTop = log.scrollHeight;
    return element;
  }
  function setBusy(value) {
    busy = value;
    send.disabled = value || !config;
    input.disabled = value || !config;
    reset.disabled = value || !config;
  }
  function close() {
    panel.hidden = true;
    launcher.setAttribute("aria-expanded", "false");
    launcher.focus();
  }
  launcher.addEventListener("click", () => {
    if (!panel.hidden) return close();
    panel.hidden = false;
    launcher.setAttribute("aria-expanded", "true");
    if (config) input.focus();
  });
  shadow.querySelector(".close").addEventListener("click", close);
  panel.addEventListener("keydown", event => { if (event.key === "Escape") close(); });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (!busy) shadow.querySelector("form").requestSubmit();
    }
  });

  async function request(path, options = {}) {
    const response = await fetch(endpoint + path, { mode: "cors", credentials: "omit", ...options });
    if (!response.ok) {
      if (response.status === 401) token = null;
      const body = await response.json().catch(() => ({}));
      throw new Error(body.error || `Chat request failed (${response.status}).`);
    }
    return response;
  }

  reset.addEventListener("click", async () => {
    if (busy) return;
    setBusy(true);
    try {
      if (token) await request("/sessions/current", { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
      token = null;
      log.replaceChildren();
      bubble("assistant", config.branding.greeting);
      status.textContent = "New conversation.";
    } catch (error) { status.textContent = error.message; }
    finally { setBusy(false); input.focus(); }
  });

  shadow.querySelector("form").addEventListener("submit", async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (busy || !config || !message) return;
    setBusy(true);
    bubble("user", message);
    input.value = "";
    const answer = bubble("assistant", "");
    status.textContent = "Thinking…";
    controller = new AbortController();
    let reader = null;
    try {
      if (!token) {
        const response = await request("/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}", signal: controller.signal });
        token = (await response.json()).session_token;
      }
      const response = await request("/messages", {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message }), signal: controller.signal
      });
      if (!response.headers.get("Content-Type")?.includes("text/event-stream") || !response.body) throw new Error("The server returned an invalid chat response.");
      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let complete = false;
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        let boundary;
        while ((boundary = buffer.indexOf("\n\n")) >= 0) {
          const block = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const kind = block.split("\n").find(line => line.startsWith("event: "))?.slice(7);
          const line = block.split("\n").find(item => item.startsWith("data: "));
          if (!line) continue;
          const data = JSON.parse(line.slice(6));
          if (kind === "delta") { answer.textContent += data.text; status.textContent = "Replying…"; }
          if (kind === "error") throw new Error(data.message);
          if (kind === "done") {
            complete = true;
            if (data.references?.length) {
              const references = document.createElement("span");
              references.className = "references";
              references.textContent = "References: " + data.references.map(item => item.title).join(", ");
              answer.append(references);
            }
          }
          log.scrollTop = log.scrollHeight;
        }
      }
      if (!complete) throw new Error("Connection ended before the reply was complete.");
      status.textContent = "Ready.";
    } catch (error) {
      status.textContent = error.name === "AbortError" ? "Reply stopped." : error.message;
      if (!answer.textContent) answer.textContent = "This reply could not be completed. Please try again.";
    } finally {
      if (reader) { await reader.cancel().catch(() => {}); reader.releaseLock(); }
      controller = null;
      setBusy(false);
      if (!panel.hidden) input.focus();
    }
  });
  window.addEventListener("pagehide", () => controller?.abort());
  setBusy(false);
  request("/config").then(response => response.json()).then(value => {
    if (!value.enabled_capabilities.includes("chat")) throw new Error("Chat is currently disabled.");
    config = value;
    heading.textContent = value.branding.name;
    panel.setAttribute("aria-label", `${value.branding.name} assistant`);
    launcher.textContent = `Chat with ${value.branding.name}`;
    if (/^#[0-9a-f]{6}$/i.test(value.branding.accent)) host.style.setProperty("--accent", value.branding.accent);
    bubble("assistant", value.branding.greeting);
    setBusy(false);
  }).catch(error => { status.textContent = error.message; });
})();
