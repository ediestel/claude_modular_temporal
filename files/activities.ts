/**
 * Temporal Activities for Claude Code Integration
 * These are the actual operations that interact with Claude Code CLI
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';

const execAsync = promisify(exec);

interface ClaudeCodeResult {
  output: string;
  tokensUsed: number;
  cost: number;
  duration: number;
  filesModified: string[];
  linesAdded: number;
  linesRemoved: number;
  diffUrl?: string;
}

interface CostEstimate {
  estimated: number;
  model: string;
  tokensEstimate: number;
}

interface MetricsData {
  [key: string]: any;
  timestamp?: string;
}

/**
 * Execute Claude Code with detailed telemetry
 * 
 * ADVANTAGE: Captures all execution metadata automatically
 */
export async function executeClaudeCode(params: {
  prompt: string;
  workingDirectory: string;
  maxTokens?: number;
  temperature?: number;
}): Promise<ClaudeCodeResult> {
  
  const startTime = Date.now();
  const { prompt, workingDirectory, maxTokens = 8000, temperature = 0.3 } = params;

  console.log(`\n[Activity] Executing Claude Code...`);
  console.log(`Directory: ${workingDirectory}`);
  console.log(`Prompt: ${prompt.substring(0, 100)}...`);

  try {
    // Store git state before changes
    const beforeFiles = await getGitStatus(workingDirectory);

    // Execute Claude Code
    // In production, use actual Claude Code CLI
    const command = `cd ${workingDirectory} && echo "${prompt}" | claude --json`;
    
    const { stdout, stderr } = await execAsync(command, {
      env: {
        ...process.env,
        CLAUDE_MAX_TOKENS: maxTokens.toString(),
        CLAUDE_TEMPERATURE: temperature.toString(),
      },
      maxBuffer: 10 * 1024 * 1024, // 10MB buffer
    });

    // Parse Claude Code output (mock structure for demo)
    const output = stdout || stderr;
    
    // Get git changes after execution
    const afterFiles = await getGitStatus(workingDirectory);
    const filesModified = getChangedFiles(beforeFiles, afterFiles);

    // Calculate git stats
    const gitDiff = await getGitDiff(workingDirectory);
    const stats = parseGitStats(gitDiff);

    // Estimate tokens and cost (in production, parse from Claude Code output)
    const tokensUsed = estimateTokens(prompt + output);
    const cost = calculateCost(tokensUsed, 'claude-sonnet-4-5');

    const duration = Date.now() - startTime;

    const result: ClaudeCodeResult = {
      output,
      tokensUsed,
      cost,
      duration,
      filesModified,
      linesAdded: stats.additions,
      linesRemoved: stats.deletions,
    };

    console.log(`[Activity] Completed in ${duration}ms`);
    console.log(`Tokens: ${tokensUsed}, Cost: $${cost.toFixed(4)}`);
    console.log(`Files modified: ${filesModified.length}`);

    return result;

  } catch (error) {
    console.error(`[Activity] Failed:`, error.message);
    throw new Error(`Claude Code execution failed: ${error.message}`);
  }
}

/**
 * Run test suite with detailed results
 * 
 * ADVANTAGE: Automatic validation after each change
 */
export async function runTests(projectPath: string): Promise<{
  success: boolean;
  totalTests: number;
  passed: number;
  failed: number;
  duration: number;
  errors: string[];
  coverage?: number;
}> {
  
  console.log(`\n[Activity] Running tests in ${projectPath}...`);
  const startTime = Date.now();

  try {
    // Run npm test (adjust for your test framework)
    const { stdout, stderr } = await execAsync(
      'npm test -- --json --coverage',
      { cwd: projectPath }
    );

    const duration = Date.now() - startTime;

    // Parse test results (adjust parsing based on your test framework)
    const result = parseTestResults(stdout);

    console.log(`[Activity] Tests completed in ${duration}ms`);
    console.log(`Passed: ${result.passed}/${result.totalTests}`);

    return {
      ...result,
      duration,
      success: result.failed === 0,
    };

  } catch (error) {
    // Tests failed
    return {
      success: false,
      totalTests: 0,
      passed: 0,
      failed: 1,
      duration: Date.now() - startTime,
      errors: [error.message],
    };
  }
}

/**
 * Estimate cost before execution
 * 
 * ADVANTAGE: Budget control and cost awareness
 */
export async function estimateCost(params: {
  prompt: string;
  complexity: 'low' | 'medium' | 'high';
}): Promise<CostEstimate> {
  
  const { prompt, complexity } = params;
  
  // Base token estimate from prompt
  const promptTokens = estimateTokens(prompt);
  
  // Estimate completion tokens based on complexity
  const completionMultiplier = {
    low: 2,
    medium: 4,
    high: 8,
  };
  
  const estimatedCompletionTokens = promptTokens * completionMultiplier[complexity];
  const totalTokens = promptTokens + estimatedCompletionTokens;
  
  const cost = calculateCost(totalTokens, 'claude-sonnet-4-5');
  
  return {
    estimated: cost,
    model: 'claude-sonnet-4-5',
    tokensEstimate: totalTokens,
  };
}

/**
 * Create project snapshot for rollback capability
 * 
 * ADVANTAGE: Safe experimentation with instant rollback
 */
export async function createSnapshot(projectPath: string): Promise<string> {
  
  const snapshotId = `snapshot-${Date.now()}`;
  console.log(`\n[Activity] Creating snapshot: ${snapshotId}`);

  try {
    // Create git stash or commit
    await execAsync('git add -A', { cwd: projectPath });
    await execAsync(`git commit -m "Snapshot: ${snapshotId}" --allow-empty`, {
      cwd: projectPath,
    });

    console.log(`[Activity] Snapshot created: ${snapshotId}`);
    return snapshotId;

  } catch (error) {
    console.warn(`Failed to create snapshot: ${error.message}`);
    return snapshotId; // Return ID anyway for tracking
  }
}

/**
 * Notify developer with context
 * 
 * ADVANTAGE: Human-in-the-loop with rich context
 */
export async function notifyDeveloper(params: {
  stage: string;
  message: string;
  filesChanged: string[];
  diffUrl?: string;
}): Promise<void> {
  
  console.log(`\n[Activity] Notifying developer...`);
  console.log(`Stage: ${params.stage}`);
  console.log(`Message: ${params.message}`);
  console.log(`Files changed: ${params.filesChanged.join(', ')}`);
  
  // In production, integrate with:
  // - Slack API
  // - Email service
  // - GitHub notifications
  // - Custom webhook
  
  // Mock notification
  await new Promise(resolve => setTimeout(resolve, 100));
  
  console.log(`[Activity] Notification sent`);
}

/**
 * Capture metrics to monitoring system
 * 
 * ADVANTAGE: Complete observability and analytics
 */
export async function captureMetrics(data: MetricsData): Promise<void> {
  
  const metrics = {
    ...data,
    timestamp: new Date().toISOString(),
  };

  console.log(`\n[Activity] Capturing metrics:`, metrics);

  // In production, send to:
  // - Prometheus Pushgateway
  // - Datadog
  // - CloudWatch
  // - Custom metrics endpoint

  // Mock metrics storage
  const metricsFile = '/tmp/claude-code-metrics.jsonl';
  await fs.appendFile(
    metricsFile,
    JSON.stringify(metrics) + '\n',
    'utf-8'
  );

  console.log(`[Activity] Metrics captured`);
}

/**
 * Deploy to NPM (example integration)
 * 
 * ADVANTAGE: End-to-end automation
 */
export async function deployToNPM(params: {
  projectPath: string;
  version: string;
  tag?: string;
}): Promise<void> {
  
  console.log(`\n[Activity] Deploying to NPM...`);
  console.log(`Version: ${params.version}`);

  const { projectPath, version, tag = 'latest' } = params;

  try {
    // Update version in package.json
    await execAsync(`npm version ${version} --no-git-tag-version`, {
      cwd: projectPath,
    });

    // Publish to NPM
    await execAsync(`npm publish --tag ${tag}`, {
      cwd: projectPath,
    });

    console.log(`[Activity] Successfully published ${version} to NPM`);

  } catch (error) {
    throw new Error(`NPM deployment failed: ${error.message}`);
  }
}

// Helper functions

async function getGitStatus(cwd: string): Promise<string> {
  try {
    const { stdout } = await execAsync('git status --short', { cwd });
    return stdout;
  } catch {
    return '';
  }
}

async function getGitDiff(cwd: string): Promise<string> {
  try {
    const { stdout } = await execAsync('git diff --stat', { cwd });
    return stdout;
  } catch {
    return '';
  }
}

function getChangedFiles(before: string, after: string): string[] {
  const beforeFiles = new Set(before.split('\n').map(line => line.split(' ').pop()));
  const afterFiles = after.split('\n').map(line => line.split(' ').pop());
  return afterFiles.filter(f => f && !beforeFiles.has(f));
}

function parseGitStats(diff: string): { additions: number; deletions: number } {
  // Parse git diff --stat output
  const match = diff.match(/(\d+) insertions?.*?(\d+) deletions?/);
  return {
    additions: match ? parseInt(match[1]) : 0,
    deletions: match ? parseInt(match[2]) : 0,
  };
}

function estimateTokens(text: string): number {
  // Rough estimate: ~4 characters per token
  return Math.ceil(text.length / 4);
}

function calculateCost(tokens: number, model: string): number {
  // Pricing as of 2025 (adjust as needed)
  const pricing: Record<string, { input: number; output: number }> = {
    'claude-sonnet-4-5': { input: 0.003, output: 0.015 }, // per 1K tokens
    'claude-opus-4': { input: 0.015, output: 0.075 },
  };

  const rates = pricing[model] || pricing['claude-sonnet-4-5'];
  // Assume 50/50 split input/output for simplicity
  const cost = (tokens / 1000) * ((rates.input + rates.output) / 2);
  return cost;
}

function parseTestResults(output: string): {
  totalTests: number;
  passed: number;
  failed: number;
  errors: string[];
} {
  // Mock parsing - adjust based on your test framework
  try {
    const json = JSON.parse(output);
    return {
      totalTests: json.numTotalTests || 0,
      passed: json.numPassedTests || 0,
      failed: json.numFailedTests || 0,
      errors: json.testResults?.map((t: any) => t.message) || [],
    };
  } catch {
    return {
      totalTests: 0,
      passed: 0,
      failed: 0,
      errors: ['Failed to parse test results'],
    };
  }
}
