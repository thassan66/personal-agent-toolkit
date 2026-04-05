#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");

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

function hasPython() {
  for (const commandParts of candidateCommands()) {
    const probe = spawnSync(commandParts[0], [...commandParts.slice(1), "--version"], {
      encoding: "utf8",
      stdio: "pipe",
    });
    if (probe.status === 0) {
      return true;
    }
  }
  return false;
}

if (!hasPython()) {
  console.warn(
    [
      "[personal-agent-toolkit] Python 3.11+ was not detected during npm install.",
      "[personal-agent-toolkit] The npm package is a thin launcher around the Python CLI.",
      "[personal-agent-toolkit] Install Python and rerun, or set PERSONAL_AGENT_TOOLKIT_PYTHON.",
    ].join("\n"),
  );
}
