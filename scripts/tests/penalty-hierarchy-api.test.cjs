const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");
const ts = require("typescript");

const root = path.resolve(__dirname, "../..");
const source = fs.readFileSync(path.join(root, "src/app/api/admin/penalty-hierarchy/route.ts"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;

function route({ authenticated = true, hosted = false, workerError = null } = {}) {
  const calls = [], invalidations = [];
  const module = { exports: {} };
  const context = { module, exports: module.exports, URL, Set, JSON,
    process: { env: hosted ? { VERCEL: "1" } : {}, platform: "win32", cwd: () => root },
    require(name) {
      if (name === "@/lib/admin-auth") return { isAdminSession: async () => authenticated };
      if (name === "@/lib/club-penalty-takers") return { clubPenaltySlug: (name) => name.toLowerCase().replaceAll(" ", "-") };
      if (name === "next/cache") return { revalidatePath: (value) => invalidations.push(value) };
      if (name === "next/server") return { NextResponse: { json: (body, options = {}) => ({ body, status: options.status || 200 }) } };
      if (name === "node:child_process") return { execFile() {} };
      if (name === "node:util") return { promisify: () => async (...args) => {
        calls.push(args);
        if (workerError) throw { stdout: JSON.stringify(workerError) };
        return { stdout: JSON.stringify({ ok: true, report: { revision: 1, clubs: [] } }) };
      } };
      return require(name);
    } };
  vm.runInNewContext(compiled, context, { filename: "penalty-hierarchy-route.js" });
  return { ...module.exports, calls, invalidations };
}

function request(body, { origin = "http://localhost:3000", url = "http://localhost:3000/api/admin/penalty-hierarchy" } = {}) {
  return new Request(url, { method: "POST", headers: { Origin: origin, "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
const command = { action: "lock", id: "epl|Example FC", expected_revision: 0, expected_entry_hash: "known-hash", reason: "Preserve editorial judgment" };

test("unauthenticated reads and writes cannot launch the worker", async () => {
  const api = route({ authenticated: false });
  assert.equal((await api.GET(new Request("http://localhost:3000/api/admin/penalty-hierarchy"))).status, 401);
  assert.equal((await api.POST(request(command))).status, 401);
  assert.equal(api.calls.length, 0);
});
test("hosted process fails closed instead of claiming temporary persistence", async () => {
  const api = route({ hosted: true });
  assert.equal((await api.POST(request(command))).status, 503);
  assert.equal(api.calls.length, 0);
});
test("cross-origin mutations and automatic-apply API requests are rejected", async () => {
  const api = route();
  assert.equal((await api.POST(request(command, { origin: "https://attacker.example" }))).status, 403);
  assert.equal((await api.POST(request({ ...command, action: "apply_safe" }))).status, 400);
  assert.equal(api.calls.length, 0);
});
test("manual command uses a fixed worker with no shell and revalidates existing SEO routes", async () => {
  const api = route();
  const result = await api.POST(request({ ...command, reason: "Keep literal $(commands) & text" }));
  assert.equal(result.status, 200);
  const [executable, args, options] = api.calls[0];
  assert.equal(executable, "python");
  assert.equal(args[0], path.join(root, "scripts/club-penalty-hierarchy-review.py"));
  assert.equal(args[1], "--command-json");
  assert.equal(JSON.parse(args[2]).reason, "Keep literal $(commands) & text");
  assert.equal(options.shell, undefined);
  assert.equal(options.windowsHide, true);
  assert.deepEqual(api.invalidations, ["/penalty-takers", "/penalty-takers/epl", "/penalty-takers/epl/example-fc"]);
});
test("worker revision conflict is a conflict response without cache invalidation", async () => {
  const api = route({ workerError: { ok: false, conflict: true, error: "Review revision changed" } });
  assert.equal((await api.POST(request(command))).status, 409);
  assert.equal(api.invalidations.length, 0);
});
test("inspect is read-only and never adds mutation flags", async () => {
  const api = route();
  assert.equal((await api.GET(new Request("http://localhost:3000/api/admin/penalty-hierarchy"))).status, 200);
  assert.deepEqual(Array.from(api.calls[0][1]).slice(1), ["--inspect"]);
});
