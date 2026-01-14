/**
 * Temporal Worker - Executes workflows and activities
 * Run this in a separate terminal: node worker.js
 */

import { Worker, NativeConnection } from '@temporalio/worker';
import * as activities from './activities';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

async function runWorker() {
  console.log('Starting Temporal Worker for Claude Code monitoring...');

  try {
    // Connect to Temporal server
    const connection = await NativeConnection.connect({
      address: 'localhost:7233',
    });

    // Create worker
    const worker = await Worker.create({
      connection,
      namespace: 'default',
      taskQueue: 'claude-code-llm-wrapper',
      workflowsPath: join(__dirname, 'workflows'),
      activities,
      maxConcurrentActivityTaskExecutions: 5,
      maxConcurrentWorkflowTaskExecutions: 10,
    });

    console.log('Worker created, listening on task queue: claude-code-llm-wrapper');
    console.log('Worker ready to process workflows...\n');

    // Run the worker
    await worker.run();

  } catch (error) {
    console.error('Worker failed:', error);
    process.exit(1);
  }
}

runWorker();

/**
 * Client - Starts workflows
 * Use this to trigger development workflows
 */

import { Client } from '@temporalio/client';

export async function startLLMWrapperDevelopment() {
  console.log('Connecting to Temporal...');

  const client = new Client({
    connection: await NativeConnection.connect({
      address: 'localhost:7233',
    }),
  });

  console.log('Starting LLM Wrapper development workflow...\n');

  const handle = await client.workflow.start('developLLMWrapperWorkflow', {
    args: [
      '/path/to/llm-wrapper-project',
      ['openai', 'anthropic', 'streaming', 'error-handling'],
    ],
    taskQueue: 'claude-code-llm-wrapper',
    workflowId: `llm-wrapper-dev-${Date.now()}`,
  });

  console.log(`Workflow started!`);
  console.log(`Workflow ID: ${handle.workflowId}`);
  console.log(`Run ID: ${handle.firstExecutionRunId}`);
  console.log(`\nView in Temporal UI: http://localhost:8233/namespaces/default/workflows/${handle.workflowId}\n`);

  // Wait for result (or use handle.result() for blocking)
  console.log('Workflow running... Use Temporal UI to monitor progress.');
  console.log('To approve stages, use the approval client.\n');

  return handle;
}

/**
 * Approval Client - Send approval signals
 */
export async function sendApproval(workflowId: string, approved: boolean) {
  const client = new Client({
    connection: await NativeConnection.connect({
      address: 'localhost:7233',
    }),
  });

  const handle = client.workflow.getHandle(workflowId);

  if (approved) {
    await handle.signal('approve');
    console.log(`✓ Sent approval signal to workflow ${workflowId}`);
  } else {
    await handle.signal('reject');
    console.log(`✗ Sent rejection signal to workflow ${workflowId}`);
  }
}

/**
 * Query workflow state
 */
export async function queryWorkflowState(workflowId: string) {
  const client = new Client({
    connection: await NativeConnection.connect({
      address: 'localhost:7233',
    }),
  });

  const handle = client.workflow.getHandle(workflowId);
  const description = await handle.describe();

  console.log('\nWorkflow State:');
  console.log('Status:', description.status.name);
  console.log('Started:', new Date(description.startTime));
  console.log('History length:', description.historyLength);

  return description;
}

// CLI Interface
if (import.meta.url === `file://${process.argv[1]}`) {
  const command = process.argv[2];

  switch (command) {
    case 'start':
      startLLMWrapperDevelopment()
        .then(() => process.exit(0))
        .catch(err => {
          console.error(err);
          process.exit(1);
        });
      break;

    case 'approve':
      const workflowId = process.argv[3];
      if (!workflowId) {
        console.error('Usage: node client.js approve <workflow-id>');
        process.exit(1);
      }
      sendApproval(workflowId, true)
        .then(() => process.exit(0))
        .catch(err => {
          console.error(err);
          process.exit(1);
        });
      break;

    case 'reject':
      const wfId = process.argv[3];
      if (!wfId) {
        console.error('Usage: node client.js reject <workflow-id>');
        process.exit(1);
      }
      sendApproval(wfId, false)
        .then(() => process.exit(0))
        .catch(err => {
          console.error(err);
          process.exit(1);
        });
      break;

    case 'status':
      const statusWfId = process.argv[3];
      if (!statusWfId) {
        console.error('Usage: node client.js status <workflow-id>');
        process.exit(1);
      }
      queryWorkflowState(statusWfId)
        .then(() => process.exit(0))
        .catch(err => {
          console.error(err);
          process.exit(1);
        });
      break;

    default:
      console.log('Usage:');
      console.log('  node client.js start                    - Start development workflow');
      console.log('  node client.js approve <workflow-id>    - Approve current stage');
      console.log('  node client.js reject <workflow-id>     - Reject current stage');
      console.log('  node client.js status <workflow-id>     - Query workflow state');
      process.exit(1);
  }
}
