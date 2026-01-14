Here is a **comprehensive, realistic plan** to monitor **all Claude Modular commands** (i.e., every `/project:*`, `/dev:*`, `/test:*`, `/deploy:*`, `/docs:*` invocation and similar) using **Temporal.io**, while preserving as much of your current interactive workflow in the terminal as possible.

The goal is **observability + durability** for every modular command execution — without forcing you to rewrite everything as pure code or lose the natural `/command ...` interaction style.

### Core Principles of This Setup

1. **Monitor at command invocation level** — Each slash-command becomes one Temporal **Activity** execution.
2. **Keep interactive use primary** — You still type `/project:create-feature ...` in your `claude` session. Temporal runs "in parallel/shadow" or "after-the-fact" for most cases.
3. **Two operating modes**:
   - **Passive monitoring** (low effort, high coverage) — Log + observe every command without changing your flow.
   - **Active orchestration** (higher reliability) — Selected (or all) command chains become durable workflows with auto-retry, pause/resume, signals.
4. **Minimal changes to claude-modular** — No deep forking if possible; use wrappers, hooks (if available), or CLI interception.

### Architecture Overview

```
You (terminal) 
   ↓  type /project:xxx ...
Claude Code CLI (+ claude-modular loaded)
   ↓  normal execution (file edits, git, bash, MCP calls)
   ↓
Wrapper / Interceptor  ───► Temporal Activity
                              │
                              ├─ Capture: command + args + full prompt context + Claude response + outcome (success/files changed/errors)
                              ├─ Retry / timeout / heartbeat if long-running
                              └─ Store in Temporal event history
Temporal Web UI / CLI
   ↓  full trace, search, replay, metrics per command type
```

### Step-by-Step Implementation Plan

#### Phase 1: Preparation & Infrastructure (1–3 hours)

1. Install & run Temporal locally (dev mode)
   - `brew install temporalio/brew/temporal-cli` (mac) or equivalent
   - `temporal server start-dev` → http://localhost:8080 opens Web UI
   - (Later → self-hosted or Temporal Cloud)

2. Choose language for wrappers → **TypeScript/JavaScript** (Temporal TS SDK is very clean + you likely already use Node for dev tools)

3. Create a small monorepo / folder for this monitoring project
   ```
   claude-temporal-monitor/
   ├── temporal/               # workflows + activities
   │   ├── src/
   │   │   ├── activities.ts
   │   │   ├── workflows.ts
   │   │   └── index.ts
   │   └── worker.ts
   ├── wrapper/                # interception logic
   └── package.json
   ```

#### Phase 2: Create the Core Activity – "InvokeModularCommand" (Phase 1 deliverable)

This single activity type will handle **every** modular command.

```ts
// activities.ts
import { Context } from '@temporalio/activity';
import { execa } from 'execa';          // better child_process
import { promises as fs } from 'fs';
import * as path from 'path';

export interface CommandInvocation {
  command: string;          // "/project:create-feature"
  args: string[];           // ["user-auth", "--type=service"]
  cwd: string;              // repo root
  sessionId?: string;       // if you can capture Claude session
  extraContext?: string;    // optional injected prompt
}

export interface CommandResult {
  success: boolean;
  output: string;           // Claude final answer / summary
  filesChanged: string[];   // git status --porcelain or similar
  error?: string;
  durationMs: number;
  tokenUsage?: { input: number; output: number }; // if capturable
}

export async function invokeModularCommand(
  input: CommandInvocation
): Promise<CommandResult> {
  const start = Date.now();

  // Option A: Run via claude CLI in headless-ish mode (preferred if supported)
  // claude --headless --non-interactive "/project:create-feature ..."  (check flags)
  // If no headless → simulate via pipe or temp session

  // Option B: Use child_process to run claude + capture
  const claudeProcess = await execa(
    'claude',
    [input.command, ...input.args],
    {
      cwd: input.cwd,
      reject: false,
      all: true,               // merge stdout/stderr
      env: { ...process.env }, // pass ANTHROPIC_API_KEY etc.
    }
  );

  const output = claudeProcess.all?.toString() || '';

  // Attempt to parse outcome
  const success = claudeProcess.exitCode === 0 && !output.includes('ERROR');

  // Git diff summary (optional)
  const gitDiff = await execa('git', ['status', '--porcelain'], { cwd: input.cwd });
  const filesChanged = gitDiff.stdout.split('\n').filter(Boolean);

  return {
    success,
    output,
    filesChanged,
    error: claudeProcess.exitCode !== 0 ? claudeProcess.stderr : undefined,
    durationMs: Date.now() - start,
  };
}
```

- Add retry policy in proxyActivities (5–10 attempts, exponential backoff)
- Heartbeat if command > 5 min (call activity.heartbeat())

#### Phase 3: Interception / Invocation Strategies (Choose One or Combine)

**Strategy A – Passive / Shadow Mode (Recommended Start – Easiest)**

1. Create a tiny shell wrapper script `claude-monitored`
   ```bash
   #!/usr/bin/env bash
   # claude-monitored

   TEMPORAL_WORKFLOW_ID="claude-modular-$(date +%s)"
   TEMPORAL_RUN_ID=$(temporal workflow start \
     --type commandMonitorWorkflow \
     --task-queue claude-commands \
     --workflow-id "$TEMPORAL_WORKFLOW_ID" \
     --input "'$(pwd)'" \
     --input "'$*'" \
     --format json | jq -r .RunId)

   # Run real claude in foreground
   claude "$@"

   # After finish → signal completion or just let activity finish
   ```

2. Alias in shell: `alias claude='claude-monitored'`

**Strategy B – Use Hooks if claude-modular / claude-code supports them**

From research, claude-code has `examples/hooks` → check if claude-modular can load pre/post command hooks.
If yes → post-hook sends data to Temporal via simple HTTP or SDK signal.

**Strategy C – Active Mode (for important chains)**

Define simple workflows that call sequences of activities:

```ts
// workflows.ts
export async function featureWorkflow(params: { spec: string }) {
  await workflow.executeActivity('invokeModularCommand', {
    command: '/project:plan-feature',
    args: [params.spec],
    cwd: await workflow.info().searchAttributes?.['CustomStringField']?.['cwd'],
  }, { startToCloseTimeout: '30m' });

  const approved = await workflow.condition(() => /* signaled */, '7 days');

  await workflow.executeActivity('invokeModularCommand', { command: '/dev:implement', ... });
  // etc.
}
```

Trigger manually: `temporal workflow start --type featureWorkflow ...`

#### Phase 4: Observability & Polish (Ongoing)

- Temporal Web UI filters: search by command prefix (`/project:*`), duration, failure reason
- Add custom search attributes: command category, repo path, user (you)
- Export metrics → Prometheus (command success rate, avg tokens per category)
- Add signals: `/approve`, `/redirect "use Redis instead"`, `/cancel`
- Long-term: log full Claude prompt/response if you can capture them (via --verbose or proxy)

### Effort & Rollout Timeline

| Phase                        | Effort       | Benefit Level | When to Do |
|------------------------------|--------------|---------------|------------|
| Temporal dev setup           | 30–60 min   | Base          | Now       |
| Core activity + passive wrapper | 2–4 hours | ★★★★☆        | Next      |
| Test on 5–10 real commands   | 1–2 hours   | Validation    | Immediately after |
| Add human signals + simple workflows | 4–8 hours | ★★★★★        | When passive works well |
| Full metrics / alerts        | 1–2 days    | Production    | Later     |

This gives you **progressive value**: start with visibility on every command → add durability where it hurts most.

If you can confirm whether `claude` CLI has `--headless`, `--json`, or hook support (or share a typical session log), I can refine the wrapper/activity code further. Let me know your preferred language (TS/Go/Python) if you want the examples adjusted!