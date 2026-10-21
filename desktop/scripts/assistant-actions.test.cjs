// Pure validation tests. No browser, server, stored tasks, or live API calls.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const ts = require("typescript");

function compile(source, modules = {}) {
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../src/core", source), "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const exports = {};
  vm.runInNewContext(code, { exports, require: name => {
    if (!(name in modules)) throw new Error(`Unexpected dependency ${name}`);
    return modules[name];
  }, Date, Intl });
  return exports;
}

const tasks = compile("taskModel.ts");
const actions = compile("assistantActions.ts", { "./taskModel": tasks });
const task = { kind: "task.create", title: "Create task", parameters: { title: "Finish report", priority: "High", deadline: "2026-10-19T09:00:00-07:00" } };
const event = { kind: "calendar.create", title: "Schedule: Team review", parameters: { title: "Team review", date: "2026-10-19", time: "09:00", recurrence: "weekly" } };
let checks = 0;
function check(run) { run(); checks++; }

check(() => assert.ok(actions.parseAssistantProposal(task)));
check(() => assert.ok(actions.parseAssistantProposal(event)));
check(() => assert.ok(actions.parseAssistantProposal({ ...task, parameters: { ...task.parameters, deadline: null } })));
check(() => assert.ok(actions.parseAssistantProposal({ ...event, title: `Schedule: ${"x".repeat(200)}`, parameters: { ...event.parameters, title: "x".repeat(200) } })));

for (const bad of [
  null, "Create task", { ...task, kind: "shell.run" }, { ...task, path: "/api/files" },
  { ...task, parameters: { ...task.parameters, path: "/api/files" } },
  { ...task, parameters: { ...task.parameters, title: "" } },
  { ...task, parameters: { ...task.parameters, title: "x".repeat(181) } },
  { ...task, parameters: { ...task.parameters, priority: "Urgent" } },
  { ...task, parameters: { ...task.parameters, deadline: "2026-10-19T09:00:00" } },
  { ...task, parameters: { ...task.parameters, deadline: "2026-02-30T09:00:00Z" } },
  { ...task, parameters: { title: "Missing deadline", priority: "High" } },
  { ...event, parameters: { ...event.parameters, date: "2026-02-30" } },
  { ...event, parameters: { ...event.parameters, time: "24:00" } },
  { ...event, parameters: { ...event.parameters, recurrence: "hourly" } },
  { ...event, parameters: { ...event.parameters, channels: ["email"] } },
]) check(() => assert.equal(actions.parseAssistantProposal(bad), null));

const receipt = { task: { id: "saved-task-1", title: "Finish report", priority: "High", deadline: "2026-10-19T16:00:00Z", status: "Pending", archived: false, createdAt: "2026-10-16T20:00:00Z", updatedAt: "2026-10-16T20:00:00Z", history: [] } };
check(() => assert.match(actions.confirmedAssistantAction(task, receipt), /Created task/));
for (const change of [{ title: "Another task" }, { deadline: null }, { priority: "Low" }, { id: "" }, { archived: true }, { history: null }]) {
  check(() => assert.equal(actions.confirmedAssistantAction(task, { task: { ...receipt.task, ...change } }), null));
}
check(() => assert.equal(actions.confirmedAssistantAction(task, { ok: true }), null));

const savedEvent = { event: { id: "app-123", title: "Team review", start: "2026-10-19T09:00:00-07:00", recurrence: "weekly", channels: ["console"] } };
check(() => assert.match(actions.confirmedAssistantAction(event, savedEvent), /Pacific time, repeating weekly/));
for (const change of [{ start: "2026-10-19T09:00:00Z" }, { channels: ["phone"] }, { recurrence: "daily" }, { id: "" }, { title: "Another event" }, { start: "2026-10-19T09:00:00" }]) {
  check(() => assert.equal(actions.confirmedAssistantAction(event, { event: { ...savedEvent.event, ...change } }), null));
}
const midnight = { ...event, parameters: { ...event.parameters, time: "00:00" } };
check(() => assert.match(actions.confirmedAssistantAction(midnight, { event: { ...savedEvent.event, start: "2026-10-19T00:00:00-07:00" } }), /00:00 Pacific time/));

// Apply-time expiry uses Pacific wall time even when the browser's clock is supplied in UTC or another offset.
const at = (date, time) => ({ ...event, parameters: { ...event.parameters, date, time } });
const now = new Date("2026-10-19T16:00:30Z"); // 09:00:30 Pacific.
check(() => assert.equal(actions.assistantProposalExpired(at("2026-10-18", "23:59"), now), true));
check(() => assert.equal(actions.assistantProposalExpired(at("2026-10-19", "08:59"), now), true));
check(() => assert.equal(actions.assistantProposalExpired(at("2026-10-19", "09:00"), now), true));
check(() => assert.equal(actions.assistantProposalExpired(at("2026-10-19", "09:01"), now), false));
check(() => assert.equal(actions.assistantProposalExpired(at("2026-10-20", "00:00"), now), false));
check(() => assert.equal(actions.assistantProposalExpired(at("2026-10-19", "09:01"), new Date("2026-10-20T01:00:30+09:00")), false));
check(() => assert.equal(actions.assistantProposalExpired(at("2026-10-19", "23:45"), new Date("2026-10-20T06:30:00Z")), false));
check(() => assert.equal(actions.assistantProposalExpired(at("2026-10-19", "23:29"), new Date("2026-10-20T06:30:00Z")), true));
check(() => assert.equal(actions.assistantProposalExpired(at("2026-12-19", "09:01"), new Date("2026-12-19T17:00:30Z")), false));
check(() => assert.equal(actions.assistantProposalExpired(task, new Date("2099-10-19T16:00:00Z")), false));
const memory = { kind: "memory.remember", title: "Remember personal information", parameters: { key: "favorite color", value: "blue", category: "preference" } };
const forget = { kind: "memory.forget", title: "Forget personal memory", parameters: { key: "favorite color" } };
check(() => assert.ok(actions.parseAssistantProposal(memory)));
check(() => assert.ok(actions.parseAssistantProposal(forget)));
for (const bad of [
  { ...memory, parameters: { ...memory.parameters, key: "" } },
  { ...memory, parameters: { ...memory.parameters, key: "x".repeat(121) } },
  { ...memory, parameters: { ...memory.parameters, value: "x".repeat(801) } },
  { ...memory, parameters: { ...memory.parameters, category: "grant" } },
  { ...memory, parameters: { ...memory.parameters, operation: "shell.run" } },
  { ...forget, parameters: { key: "favorite color", value: "anything" } },
]) check(() => assert.equal(actions.parseAssistantProposal(bad), null));
const memoryReceipt = { memory: { id: "test-memory", key: "favorite color", value: "blue", category: "preference", source: "explicit_owner" } };
check(() => assert.match(actions.confirmedAssistantAction(memory, memoryReceipt), /Saved the personal memory/));
for (const change of [{ id: "" }, { key: "other key" }, { value: "red" }, { category: "fact" }, { source: "inferred" }])
  check(() => assert.equal(actions.confirmedAssistantAction(memory, { memory: { ...memoryReceipt.memory, ...change } }), null));
check(() => assert.match(actions.confirmedAssistantAction(forget, { forgotten: true, key: "favorite color" }), /Removed/));
check(() => assert.match(actions.confirmedAssistantAction(forget, { forgotten: false, key: "favorite color" }), /No saved/));
check(() => assert.equal(actions.confirmedAssistantAction(forget, { forgotten: true, key: "wrong" }), null));
check(() => assert.equal(actions.confirmedAssistantAction(forget, { forgotten: "true", key: "favorite color" }), null));
check(() => assert.equal(actions.assistantProposalExpired(memory, now), false));

const inboxParser = compile("followThrough.ts", { react: {}, "./bridge": {} });
const notice = { id: `ft-${"a".repeat(32)}`, title: "Inspection", message: "Inspection starts within 15 minutes.", dueAt: "2026-10-19T16:00:00Z", snoozedUntil: null, canInterrupt: true, canSpeak: false };
const inbox = { notifications: [notice], unreadCount: 1, workerRunning: true };
check(() => assert.equal(inboxParser.parseInbox(inbox).notifications[0].id, notice.id));
for (const change of [{ id: "../../execute" }, { canSpeak: "true" }, { canInterrupt: 1 }, { dueAt: "invalid" }, { snoozedUntil: "invalid" }, { message: "x".repeat(2001) }])
  check(() => assert.throws(() => inboxParser.parseInbox({ ...inbox, notifications: [{ ...notice, ...change }] })));
for (const change of [{ notifications: "anything" }, { unreadCount: -1 }, { workerRunning: "yes" }])
  check(() => assert.throws(() => inboxParser.parseInbox({ ...inbox, ...change })));
console.log(`PASS: ${checks} frontend proposal, receipt, and inbox validation checks; no server/API calls.`);
