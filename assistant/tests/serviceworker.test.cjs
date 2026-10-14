const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../../static/assistant/js/serviceworker.js"), "utf8");

function worker({ online = true, names = [] } = {}) {
  const handlers = {};
  const writes = [];
  const deletes = [];
  const fetches = [];
  const shell = new Response("public shell");
  const cached = new Map([["/", shell], ["/static/assistant/css/app.css", new Response("stylesheet")]]);
  const cache = {
    addAll: async (urls) => { writes.push(...urls); },
    match: async (request) => cached.get(typeof request === "string" ? request : new URL(request.url).pathname),
  };
  const sandbox = {
    URL,
    self: {
      location: { origin: "https://assistant.example" },
      addEventListener: (type, handler) => { handlers[type] = handler; },
      skipWaiting: async () => {},
      clients: { claim: async () => {} },
    },
    caches: {
      open: async () => cache,
      keys: async () => names,
      delete: async (name) => { deletes.push(name); return true; },
    },
    fetch: async (request) => {
      fetches.push(request);
      if (!online) throw new TypeError("offline");
      return new Response("fresh network");
    },
  };
  vm.runInNewContext(source, sandbox);
  async function lifecycle(type) {
    let work;
    handlers[type]({ waitUntil: (promise) => { work = promise; } });
    await work;
  }
  async function request(pathname, { method = "GET", mode = "cors", origin = "https://assistant.example" } = {}) {
    let result;
    handlers.fetch({ request: { url: origin + pathname, method, mode }, respondWith: (promise) => { result = promise; } });
    return result ? await result : undefined;
  }
  return { writes, deletes, fetches, lifecycle, request };
}

test("installation caches only the public shell and named local assets", async () => {
  const sw = worker();
  await sw.lifecycle("install");
  assert.ok(sw.writes.includes("/"));
  assert.ok(sw.writes.includes("/static/assistant/js/app.js"));
  assert.ok(sw.writes.includes("/static/assistant/img/icon-512.png"));
  assert.ok(sw.writes.every((url) => url === "/" || url.startsWith("/static/")));
});

test("activation removes only old caches belonging to this assistant", async () => {
  const sw = worker({ names: ["ai-assistant-shell-old", "ai-assistant-shell-v1", "unrelated-app"] });
  await sw.lifecycle("activate");
  assert.deepEqual(sw.deletes, ["ai-assistant-shell-old"]);
});

test("AI, CSRF, non-GET, and other-origin requests bypass the worker", async () => {
  const sw = worker();
  for (const [url, options] of [
    ["/api/csrf/", {}], ["/api/ask/", { method: "POST" }],
    ["/other", { method: "POST" }], ["/", { origin: "https://other.example" }],
  ]) assert.equal(await sw.request(url, options), undefined);
  assert.equal(sw.fetches.length, 0);
  assert.equal(sw.writes.length, 0);
});

test("online navigation goes to the network without caching its response", async () => {
  const sw = worker();
  const response = await sw.request("/?view=example", { mode: "navigate" });
  assert.equal(await response.text(), "fresh network");
  assert.equal(sw.fetches.length, 1);
  assert.equal(sw.writes.length, 0);
});

test("offline navigation falls back to the public shell", async () => {
  const sw = worker({ online: false });
  const response = await sw.request("/", { mode: "navigate" });
  assert.equal(await response.text(), "public shell");
});

test("cached presentation assets load offline; unnamed assets are not intercepted", async () => {
  const sw = worker({ online: false });
  const response = await sw.request("/static/assistant/css/app.css");
  assert.equal(await response.text(), "stylesheet");
  assert.equal(await sw.request("/static/private-data.json"), undefined);
  assert.equal(sw.fetches.length, 0);
});
