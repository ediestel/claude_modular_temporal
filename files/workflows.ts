/**
 * Temporal Workflow for LLM Wrapper Development with Claude Code
 * 
 * Use Case Advantages Demonstrated:
 * 1. Multi-stage development orchestration
 * 2. Automatic testing and validation
 * 3. Cost tracking across iterations
 * 4. Human-in-the-loop code reviews
 * 5. Rollback capabilities
 */

import { 
  proxyActivities, 
  sleep, 
  condition,
  defineSignal,
  setHandler,
} from '@temporalio/workflow';
import type * as activities from './activities';

const {
  executeClaudeCode,
  runTests,
  captureMetrics,
  estimateCost,
  createSnapshot,
  notifyDeveloper,
  deployToNPM,
} = proxyActivities<typeof activities>({
  startToCloseTimeout: '10 minutes',
  retry: {
    initialInterval: '2s',
    backoffCoefficient: 2,
    maximumAttempts: 3,
  },
});

// Signals for human approval
export const approveSignal = defineSignal('approve');
export const rejectSignal = defineSignal('reject');

interface DevelopmentStage {
  name: string;
  prompt: string;
  requiresApproval: boolean;
  criticalPath: boolean;
}

interface WorkflowState {
  currentStage: string;
  totalTokensUsed: number;
  totalCost: number;
  testsPassedCount: number;
  snapshots: string[];
  approved: boolean | null;
}

/**
 * Main Workflow: Develop LLM Wrapper with Full Observability
 * 
 * ADVANTAGES:
 * - Complete audit trail of all development decisions
 * - Automatic rollback if tests fail
 * - Cost tracking in real-time
 * - Pause for human review at critical points
 * - Resume development after interruptions
 */
export async function developLLMWrapperWorkflow(
  projectPath: string,
  features: string[]
): Promise<WorkflowState> {
  
  const state: WorkflowState = {
    currentStage: 'initializing',
    totalTokensUsed: 0,
    totalCost: 0,
    testsPassedCount: 0,
    snapshots: [],
    approved: null,
  };

  // Setup approval handler
  setHandler(approveSignal, () => { state.approved = true; });
  setHandler(rejectSignal, () => { state.approved = false; });

  const stages: DevelopmentStage[] = [
    {
      name: 'scaffold',
      prompt: `Create a TypeScript LLM wrapper library with:
        - Support for OpenAI, Anthropic, and local models
        - Type-safe interfaces
        - Streaming support
        - Error handling and retries
        - Cost tracking
        Setup project structure in ${projectPath}`,
      requiresApproval: false,
      criticalPath: true,
    },
    {
      name: 'core-implementation',
      prompt: `Implement core wrapper functionality:
        - Base LLMClient abstract class
        - OpenAI provider implementation
        - Anthropic provider implementation
        - Unified response format
        - Token counting utilities`,
      requiresApproval: true, // Human review before proceeding
      criticalPath: true,
    },
    {
      name: 'streaming',
      prompt: `Add streaming support:
        - Server-sent events handling
        - Async iterators for streams
        - Backpressure handling
        - Stream cancellation`,
      requiresApproval: false,
      criticalPath: true,
    },
    {
      name: 'error-handling',
      prompt: `Implement robust error handling:
        - Custom error classes for different failure types
        - Exponential backoff with jitter
        - Circuit breaker pattern
        - Request timeout handling
        - Rate limit detection and retry`,
      requiresApproval: false,
      criticalPath: false,
    },
    {
      name: 'testing',
      prompt: `Create comprehensive test suite:
        - Unit tests for each provider
        - Integration tests with mock APIs
        - Streaming tests
        - Error handling tests
        - Edge case coverage`,
      requiresApproval: false,
      criticalPath: true,
    },
    {
      name: 'documentation',
      prompt: `Generate complete documentation:
        - README with quick start guide
        - API reference for all public methods
        - Usage examples for common scenarios
        - Migration guides
        - TypeScript type documentation`,
      requiresApproval: false,
      criticalPath: false,
    },
  ];

  try {
    for (const stage of stages) {
      state.currentStage = stage.name;
      console.log(`\n=== Starting Stage: ${stage.name} ===`);

      // ADVANTAGE 1: Pre-execution cost estimation
      const costEstimate = await estimateCost({
        prompt: stage.prompt,
        complexity: stage.criticalPath ? 'high' : 'medium',
      });
      console.log(`Estimated cost: $${costEstimate.estimated}`);

      // ADVANTAGE 2: Create snapshot before risky operations
      if (stage.criticalPath) {
        const snapshotId = await createSnapshot(projectPath);
        state.snapshots.push(snapshotId);
        console.log(`Created snapshot: ${snapshotId}`);
      }

      // ADVANTAGE 3: Execute Claude Code with full telemetry
      const result = await executeClaudeCode({
        prompt: stage.prompt,
        workingDirectory: projectPath,
        maxTokens: 8000,
        temperature: 0.3,
      });

      state.totalTokensUsed += result.tokensUsed;
      state.totalCost += result.cost;

      // ADVANTAGE 4: Automatic validation after each stage
      if (stage.name !== 'documentation') {
        const testResult = await runTests(projectPath);
        
        if (!testResult.success) {
          console.error(`Tests failed in ${stage.name}:`);
          console.error(testResult.errors);
          
          // ADVANTAGE 5: Automatic rollback on failure
          if (stage.criticalPath && state.snapshots.length > 0) {
            const lastSnapshot = state.snapshots[state.snapshots.length - 1];
            console.log(`Rolling back to snapshot: ${lastSnapshot}`);
            // In real implementation, restore snapshot
            throw new Error(`Critical stage ${stage.name} failed tests`);
          }
        } else {
          state.testsPassedCount++;
        }
      }

      // ADVANTAGE 6: Human-in-the-loop approval for critical stages
      if (stage.requiresApproval) {
        await notifyDeveloper({
          stage: stage.name,
          message: `Stage "${stage.name}" complete. Review required.`,
          filesChanged: result.filesModified,
          diffUrl: result.diffUrl,
        });

        console.log(`Waiting for approval on stage: ${stage.name}`);
        
        // Wait for approval signal (max 1 hour)
        const approved = await condition(
          () => state.approved !== null,
          '1 hour'
        );

        if (!approved || state.approved === false) {
          throw new Error(`Stage ${stage.name} rejected by developer`);
        }

        state.approved = null; // Reset for next approval
        console.log(`Stage ${stage.name} approved, continuing...`);
      }

      // ADVANTAGE 7: Capture detailed metrics after each stage
      await captureMetrics({
        stage: stage.name,
        tokensUsed: result.tokensUsed,
        cost: result.cost,
        duration: result.duration,
        filesModified: result.filesModified.length,
        linesAdded: result.linesAdded,
        linesRemoved: result.linesRemoved,
        testsPass: stage.name === 'documentation' || testResult?.success,
      });

      // ADVANTAGE 8: Rate limiting and cooldown
      if (state.totalTokensUsed > 50000) {
        console.log('High token usage, cooling down for 30s...');
        await sleep('30 seconds');
      }
    }

    // ADVANTAGE 9: Final validation before publish
    console.log('\n=== Final Validation ===');
    const finalTests = await runTests(projectPath);
    
    if (!finalTests.success) {
      throw new Error('Final test suite failed');
    }

    // ADVANTAGE 10: Automated deployment tracking
    console.log('\n=== Development Complete ===');
    console.log(`Total tokens used: ${state.totalTokensUsed}`);
    console.log(`Total cost: $${state.totalCost.toFixed(2)}`);
    console.log(`Tests passed: ${state.testsPassedCount}/${stages.length - 1}`);
    
    return state;

  } catch (error) {
    // ADVANTAGE 11: Detailed error context for debugging
    await captureMetrics({
      stage: state.currentStage,
      error: error.message,
      tokensUsedBeforeFailure: state.totalTokensUsed,
      costBeforeFailure: state.totalCost,
      stackTrace: error.stack,
    });

    throw error;
  }
}

/**
 * Iterative Refinement Workflow
 * 
 * ADVANTAGE: Handle multiple iterations with feedback loops
 */
export async function iterativeRefinementWorkflow(
  projectPath: string,
  issue: string,
  maxIterations: number = 5
): Promise<void> {
  
  let iteration = 0;
  let testsPassing = false;

  while (iteration < maxIterations && !testsPassing) {
    iteration++;
    console.log(`\n=== Iteration ${iteration} ===`);

    // Create snapshot before each iteration
    const snapshotId = await createSnapshot(projectPath);

    // Ask Claude Code to fix the issue
    const result = await executeClaudeCode({
      prompt: `Fix this issue: ${issue}. 
        Previous attempts: ${iteration - 1}
        Run tests after fixing.`,
      workingDirectory: projectPath,
      maxTokens: 4000,
    });

    // Validate the fix
    const testResult = await runTests(projectPath);
    testsPassing = testResult.success;

    await captureMetrics({
      iteration,
      issue,
      tokensUsed: result.tokensUsed,
      testsPassing,
      filesModified: result.filesModified.length,
    });

    if (!testsPassing) {
      console.log(`Tests still failing. Retrying... (${iteration}/${maxIterations})`);
      // Add exponential backoff
      await sleep(`${Math.min(iteration * 5, 30)} seconds`);
    }
  }

  if (!testsPassing) {
    throw new Error(`Failed to fix issue after ${maxIterations} iterations`);
  }

  console.log(`Issue resolved in ${iteration} iteration(s)`);
}

/**
 * Parallel Feature Development Workflow
 * 
 * ADVANTAGE: Develop multiple features concurrently with isolated contexts
 */
export async function parallelFeatureDevelopment(
  projectPath: string,
  features: string[]
): Promise<void> {
  
  const featurePromises = features.map(async (feature, index) => {
    const branchName = `feature-${index}-${feature.replace(/\s+/g, '-')}`;
    
    // Create feature branch
    await executeClaudeCode({
      prompt: `Create git branch ${branchName} and switch to it`,
      workingDirectory: projectPath,
      maxTokens: 100,
    });

    // Develop feature
    const result = await executeClaudeCode({
      prompt: `Implement feature: ${feature}. Include tests.`,
      workingDirectory: projectPath,
      maxTokens: 6000,
    });

    // Run tests
    const testResult = await runTests(projectPath);
    
    await captureMetrics({
      feature,
      branch: branchName,
      tokensUsed: result.tokensUsed,
      testsPassing: testResult.success,
    });

    return {
      feature,
      branch: branchName,
      success: testResult.success,
    };
  });

  const results = await Promise.all(featurePromises);
  
  console.log('\n=== Parallel Development Results ===');
  results.forEach(r => {
    console.log(`${r.feature}: ${r.success ? '✓' : '✗'} (${r.branch})`);
  });
}
