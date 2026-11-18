import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { apiRequest } from "../app/lib/api.ts";
import { createMemorySessionManager } from "../app/lib/session.ts";

test("apiRequest sends JSON body and X-Actor-Email header and parses response", async () => {
  let receivedActor = "";
  let receivedMethod = "";
  const server = http.createServer((req, res) => {
    receivedActor = String(req.headers["x-actor-email"] ?? "");
    receivedMethod = String(req.method ?? "");
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true }));
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const port = (server.address() as { port: number }).port;

  try {
    const res = await apiRequest<{ ok: boolean }>("/api/departments", {
      method: "POST",
      body: { ping: 1 },
      baseUrl: `http://127.0.0.1:${port}`,
      actorEmail: "tsh.co@tshorg.vn",
    });
    assert.equal(res.ok, true);
    assert.equal(receivedActor, "tsh.co@tshorg.vn");
    assert.equal(receivedMethod, "POST");
  } finally {
    server.close();
  }
});

test("apiRequest surfaces backend detail error message on non-2xx HTTP status", async () => {
  const server = http.createServer((_req, res) => {
    res.writeHead(403, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ detail: "Chỉ Chủ sở hữu mới có quyền" }));
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const port = (server.address() as { port: number }).port;

  try {
    await assert.rejects(
      () =>
        apiRequest("/api/m07/users", {
          baseUrl: `http://127.0.0.1:${port}`,
        }),
      /Chỉ Chủ sở hữu mới có quyền/,
    );
  } finally {
    server.close();
  }
});

test("session manager rotates session ID cleanly on wipe", () => {
  const mgr = createMemorySessionManager();
  const first = mgr.getOrInitSessionId();
  const second = mgr.rotateSessionId();
  assert.notEqual(first, second);
  assert.equal(mgr.getOrInitSessionId(), second);
});

