import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { createInterface } from "node:readline";
import { chromium } from "playwright-core";

const executablePath = process.env.ECHO_BROWSER || [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "/usr/bin/chromium", "/usr/bin/google-chrome"
].find(existsSync);
if (!executablePath) throw new Error("Set ECHO_BROWSER to an installed Chrome/Chromium executable.");
const command = process.env.ECHO_PYTHON || (process.platform === "win32" ? "py" : "python3");
const args = process.platform === "win32" && !process.env.ECHO_PYTHON ? ["-3.12"] : [];
const fixture = spawn(command, [...args, "tests/browser_fixture.py"], { stdio: ["pipe", "pipe", "pipe"] });
const lines = createInterface({ input: fixture.stdout });
let browser;
let stderr = "";
fixture.stderr.on("data", chunk => { stderr += chunk; });
try {
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Fixture startup timed out: " + stderr)), 15000);
    lines.once("line", line => { clearTimeout(timer); resolve(JSON.parse(line).url); });
    fixture.once("exit", code => { clearTimeout(timer); reject(new Error("Fixture exited " + code + stderr)); });
  });
  browser = await chromium.launch({ executablePath, headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 850 } });
  const errors = [];
  const requests = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => requests.push(request));
  await page.goto(url + "/demo");
  const widget = page.locator("echo-chat-widget");
  await widget.locator(".launcher").click();
  await widget.locator("textarea").waitFor({ state: "visible" });
  await page.waitForFunction(() => !document.querySelector("echo-chat-widget").shadowRoot.querySelector("textarea").disabled);
  assert.equal(await widget.locator("h2").textContent(), "Example Shop");
  async function send(text) {
    await widget.locator("textarea").fill(text);
    await widget.locator(".send").click();
    await widget.locator(".status").filter({ hasText: "Ready." }).waitFor();
  }
  await widget.locator("textarea").fill("What are your opening hours?");
  await widget.locator(".send").click();
  await page.waitForFunction(() => {
    const root = document.querySelector("echo-chat-widget").shadowRoot;
    const answers = root.querySelectorAll(".assistant");
    return answers[answers.length - 1].textContent === "Open Mon";
  });
  assert.equal(await widget.locator(".send").isDisabled(), true);
  await widget.locator(".status").filter({ hasText: "Ready." }).waitFor();
  assert.match(await widget.locator(".assistant").last().textContent(), /9 am to 5 pm/);
  assert.match(await widget.locator(".references").last().textContent(), /Opening hours/);
  await send("follow-up");
  assert.match(await widget.locator(".assistant").last().textContent(), /What are your opening hours/);
  await send("<img src=x onerror=alert(1)> 🌍");
  assert.equal(await widget.locator(".bubble img").count(), 0);
  assert.match(await widget.locator(".assistant").last().textContent(), /🌍/);
  await widget.locator("textarea").fill("fail");
  await widget.locator(".send").click();
  await widget.locator(".status").filter({ hasText: "could not complete" }).waitFor();
  assert.equal(await widget.locator(".send").isEnabled(), true);
  assert.equal((await widget.locator(".status").textContent()).includes("private-error"), false);
  const userMessagesBeforeRetry = await widget.locator(".user").count();
  await widget.locator(".retry").click();
  await widget.locator(".status").filter({ hasText: "Ready." }).waitFor();
  assert.equal(await widget.locator(".user").count(), userMessagesBeforeRetry);
  assert.match(await widget.locator(".assistant").last().textContent(), /Reply: fail/);
  await widget.locator(".reset").click();
  await widget.locator(".status").filter({ hasText: "New conversation" }).waitFor();
  await send("follow-up");
  assert.match(await widget.locator(".assistant").last().textContent(), /none/);
  await widget.locator("textarea").press("Escape");
  assert.equal(await widget.locator(".panel").isHidden(), true);
  await page.setViewportSize({ width: 390, height: 844 });
  await widget.locator(".launcher").click();
  const box = await widget.locator(".panel").boundingBox();
  assert.ok(box.x >= 0 && box.x + box.width <= 390);
  mkdirSync("artifacts", { recursive: true });
  await page.screenshot({ path: "artifacts/widget-mobile.png" });
  assert.equal(errors.length, 0, errors.join("\n"));
  assert.ok(requests.every(request => !JSON.stringify(request.headers()).includes("fixture-server-key")));
  assert.ok(requests.every(request => request.resourceType() !== "media"));
  console.log("PASS browser → widget → API → shared ECHO engine → provider, streaming, context, references, reset, errors, text safety, keyboard and mobile layout");
} finally {
  if (browser) await browser.close();
  fixture.stdin.end();
  const exited = new Promise(resolve => fixture.once("exit", resolve));
  await Promise.race([exited, new Promise(resolve => setTimeout(resolve, 3000))]);
  if (fixture.exitCode === null) fixture.kill();
  lines.close();
}
