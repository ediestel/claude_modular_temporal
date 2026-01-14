Here are several practical **Temporal.io workflow examples** tailored to your context (monitoring and orchestrating **Claude Modular** commands via Temporal Activities in TypeScript). These build on our previous discussion: each modular command (`/project:*`, `/dev:*`, etc.) runs as a **durable Activity**, while Workflows provide sequencing, retries, human-in-the-loop gates, observability, and recovery.

All examples use the **Temporal TypeScript SDK** (current stable as of Jan 2026). They assume you've set up a basic Temporal dev server (`temporal server start-dev`) and installed the packages:

```bash
npm install @temporalio/client @temporalio/worker @temporalio/workflow @temporalio/activity @temporalio/common
```

### 1. Core Building Block: Single Command Activity (Passive Monitoring / Shadow Mode)

This is the foundation — every Claude Modular command becomes one Activity call. You can trigger it from your wrapper script or call it directly.

```ts
// activities.ts
import { Context } from '@temporalio/activity';
import { execa } from 'execa';

export interface ClaudeCommandInput {
  command: string;       // e.g. "/project:create-feature"
  args: string[];        // e.g. ["user-auth", "--with-tests"]
  cwd: string;           // repo root
  timeoutMs?: number;    // optional
}

export interface ClaudeCommandOutput {
  success: boolean;
  output: string;        // captured stdout/stderr or Claude summary
  filesChanged?: string[]; // git porcelain output
  error?: string;
  durationMs: number;
}

export async function runClaudeModularCommand(
  input: ClaudeCommandInput
): Promise<ClaudeCommandOutput> {
  const start = Date.now();
  const fullCmd = [input.command, ...input.args];

  try {
    const { all, exitCode } = await execa('claude', fullCmd, {
      cwd: input.cwd,
      all: true,                // merge stdout + stderr
      timeout: input.timeoutMs || 30 * 60 * 1000, // 30 min default
      reject: false,
    });

    const output = all?.toString() || '';
    const success = exitCode === 0 && !output.toLowerCase().includes('error');

    // Optional: capture git changes
    const gitStatus = await execa('git', ['status', '--porcelain=v1'], { cwd: input.cwd });
    const filesChanged = gitStatus.stdout.split('\n').filter(Boolean);

    return {
      success,
      output,
      filesChanged,
      durationMs: Date.now() - start,
    };
  } catch (err: any) {
    return {
      success: false,
      output: '',
      error: err.message || String(err),
      durationMs: Date.now() - start,
    };
  }
}
```

Use with proxyActivities in a Workflow for auto-retries:

```ts
const activities = proxyActivities<typeof import('./activities')>({
  startToCloseTimeout: '45m',
  retry: { maximumAttempts: 4, backoffCoefficient: 2 },
});
```

### 2. Simple Sequential Workflow: Full Feature Cycle

A basic Workflow that chains 3–4 typical Claude Modular commands with a human approval gate.

```ts
// workflows.ts
import * as wf from '@temporalio/workflow';
import { proxyActivities } from '@temporalio/workflow';
import type * as activities from './activities';

const { runClaudeModularCommand } = proxyActivities<typeof activities>({
  startToCloseTimeout: '1h',
  retry: { maximumAttempts: 5 },
});

const approveSignal = wf.defineSignal('approve');
let isApproved = false;

export async function fullFeatureWorkflow(params: {
  featureName: string;
  description: string;
  repoPath: string;
}): Promise<{ finalPR?: string; summary: string }> {
  // Step 1: Plan
  const planResult = await runClaudeModularCommand({
    command: '/project:plan-feature',
    args: [params.featureName],
    cwd: params.repoPath,
  });

  if (!planResult.success) throw new wf.ApplicationFailure('Planning failed', { nonRetryable: true });

  // Human approval gate (wait for signal)
  await wf.condition(() => isApproved, '7 days'); // auto-timeout after 1 week

  // Step 2: Implement
  await runClaudeModularCommand({
    command: '/dev:implement',
    args: [params.featureName],
    cwd: params.repoPath,
  });

  // Step 3: Tests + coverage
  await runClaudeModularCommand({
    command: '/test:generate-and-run',
    args: ['--coverage'],
    cwd: params.repoPath,
  });

  // Step 4: Commit & PR
  const prResult = await runClaudeModularCommand({
    command: '/project:commit-and-pr',
    args: [`feat: ${params.featureName} - ${params.description}`],
    cwd: params.repoPath,
  });

  return {
    finalPR: prResult.output.match(/https:\/\/github\.com\/.*\/pull\/\d+/)?.[0],
    summary: planResult.output + '\n\n' + prResult.output,
  };
}

// Signal handler
export const approve = () => { isApproved = true; };
```

Start it from CLI or script:

```bash
temporal workflow start --type fullFeatureWorkflow --task-queue claude-queue \
  --workflow-id feature-user-auth-001 --input '{"featureName":"user-auth","description":"Add JWT login","repoPath":"/path/to/repo"}'
```

### 3. Dynamic / Agentic Loop Workflow (Claude Decides Next Command)

Let Claude itself decide the next modular command in a loop (common for complex refactors).

```ts
// dynamic-feature-workflow.ts
export async function dynamicCodingWorkflow(params: {
  initialGoal: string;
  repoPath: string;
  maxSteps?: number;
}): Promise<string> {
  let history: string[] = [`Goal: ${params.initialGoal}`];
  let step = 0;
  const max = params.maxSteps ?? 15;

  while (step < max) {
    // Ask Claude what to do next (via a decider command or direct prompt)
    const decision = await runClaudeModularCommand({
      command: '/dev:decide-next-step', // assume you have or create this modular command
      args: [],
      cwd: params.repoPath,
      // extraPrompt could be passed if your wrapper supports it
    });

    if (!decision.success || decision.output.includes('DONE') || decision.output.includes('COMPLETE')) {
      break;
    }

    const nextCommand = decision.output.trim(); // e.g. "/test:generate-tests"

    const result = await runClaudeModularCommand({
      command: nextCommand,
      args: [], // can parse args from decision.output if needed
      cwd: params.repoPath,
    });

    history.push(`Step ${step + 1}: ${nextCommand} → ${result.success ? 'OK' : 'FAILED'}`);

    if (!result.success) {
      // Optional: ask Claude to fix or escalate
      await runClaudeModularCommand({ command: '/dev:handle-failure', args: [], cwd: params.repoPath });
    }

    step++;
  }

  return `Completed in ${step} steps. History:\n${history.join('\n')}`;
}
```

### 4. Human-in-the-Loop with Signals + Query

Add queries for live status (visible in Temporal UI or via CLI).

```ts
// Add to workflow
export const getStatusQuery = wf.defineQuery<string>('status');
export function status(): string {
  return `Current step: ${step} | History length: ${history.length} | Approved: ${isApproved}`;
}
```

Query it: `temporal workflow query --workflow-id <id> --query-type status`

### Quick Setup Checklist

1. Worker (run in separate terminal):

```ts
// worker.ts
import { Worker } from '@temporalio/worker';
import * as activities from './activities';
import * as wf from '@temporalio/workflow';

Worker.create({
  workflowsPath: require.resolve('./workflows'),
  activities: { runClaudeModularCommand: activities.runClaudeModularCommand },
  taskQueue: 'claude-queue',
}).then(w => w.run());
```

2. Monitor: Open http://localhost:8080 → filter by task queue or workflow ID.

3. Enhance: Add heartbeating for very long commands (`activity.heartbeat()` every 30s), custom search attributes (`command` category), or export to Prometheus.

These patterns scale from single-command tracking → full durable agents. Start with the single activity + simple sequential workflow, then add loops/signals as needed.

If you'd like Go/Python variants, more advanced MCP integration examples, or tweaks for specific claude-modular commands you use most, just say! 😊