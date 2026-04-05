#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..");
const pathSeparator = process.platform === "win32" ? ";" : ":";

function candidateCommands() {
  if (process.env.PERSONAL_AGENT_TOOLKIT_PYTHON) {
    return [[process.env.PERSONAL_AGENT_TOOLKIT_PYTHON]];
  }
  const candidates = [["python"]];
  if (process.platform === "win32") {
    candidates.push(["py", "-3"]);
  }
  candidates.push(["python3"]);
  return candidates;
}

function buildEnv() {
  const env = { ...process.env };
  env.PYTHONPATH = env.PYTHONPATH
    ? `${packageRoot}${pathSeparator}${env.PYTHONPATH}`
    : packageRoot;
  return env;
}

function findPython(env) {
  for (const commandParts of candidateCommands()) {
    const probe = spawnSync(commandParts[0], [...commandParts.slice(1), "--version"], {
      encoding: "utf8",
      env,
      stdio: "pipe",
    });
    if (probe.status === 0) {
      return commandParts;
    }
  }
  return null;
}

function main() {
  const env = buildEnv();
  const python = findPython(env);
  if (!python) {
    console.error(
      [
        "personal-agent-toolkit requires Python 3.11+.",
        "Install Python and rerun, or set PERSONAL_AGENT_TOOLKIT_PYTHON to your interpreter path.",
      ].join("\n"),
    );
    process.exit(1);
  }

  const args = [...python.slice(1), "-m", "personal_agent_toolkit", ...process.argv.slice(2)];
  const result = spawnSync(python[0], args, {
    cwd: process.cwd(),
    env,
    stdio: "inherit",
  });

  if (result.error) {
    console.error(`failed to start Python: ${result.error.message}`);
    process.exit(1);
  }
  process.exit(result.status === null ? 1 : result.status);
}

main();
