/**
 * Prerequisites checker for the harness CLI.
 *
 * Verifies that the system meets minimum requirements before running the harness.
 */

import { execSync } from "node:child_process";

export type PrereqResult =
  | { passed: true; version: string }
  | { passed: false; hint: string };

export function checkNode(): PrereqResult {
  let version: string;

  try {
    version = execSync("node --version", { encoding: "utf-8" }).trim();
  } catch {
    return {
      passed: false,
      hint: "Node.js is not installed or not on PATH. Install Node.js >= 20 from https://nodejs.org",
    };
  }

  const match = /^v(\d+)\./.exec(version);
  if (!match) {
    return {
      passed: false,
      hint: `Could not parse Node.js version string: "${version}". Install Node.js >= 20 from https://nodejs.org`,
    };
  }

  return parseInt(match[1], 10) >= 20
    ? { passed: true, version }
    : {
        passed: false,
        hint: `Node.js >= 20 is required, but found ${version}. Upgrade at https://nodejs.org`,
      };
}

export function checkPython(): PrereqResult {
  let raw: string;

  try {
    raw = execSync("python3 --version", { encoding: "utf-8" }).trim();
  } catch {
    return { passed: false, hint: "Install Python 3.11+" };
  }

  const match = /^Python (\d+)\.(\d+)\.(\d+)/.exec(raw);
  if (!match) {
    return { passed: false, hint: "Install Python 3.11+" };
  }

  const major = parseInt(match[1], 10);
  const minor = parseInt(match[2], 10);
  const version = `${match[1]}.${match[2]}.${match[3]}`;

  return major === 3 && minor >= 11
    ? { passed: true, version }
    : { passed: false, hint: "Install Python 3.11+" };
}

export function checkCodexCli(): PrereqResult {
  try {
    const raw = execSync("codex --version", { encoding: "utf-8" }).trim();
    return { passed: true, version: raw };
  } catch {
    return { passed: false, hint: "Install Codex CLI and authenticate" };
  }
}

export function checkOpenAiApiKey(): PrereqResult {
  return process.env.OPENAI_API_KEY
    ? { passed: true, version: "configured" }
    : { passed: false, hint: "Set OPENAI_API_KEY in your environment before running the harness" };
}

export interface NamedPrereqResult {
  name: string;
  passed: boolean;
  version?: string;
  hint?: string;
}

export function checkAll(): NamedPrereqResult[] {
  const checks: Array<[string, () => PrereqResult]> = [
    ["node", checkNode],
    ["python", checkPython],
    ["codex-cli", checkCodexCli],
    ["openai-api-key", checkOpenAiApiKey],
  ];

  return checks.map(([name, fn]) => {
    const result = fn();
    return result.passed
      ? { name, passed: true, version: result.version }
      : { name, passed: false, hint: result.hint };
  });
}
