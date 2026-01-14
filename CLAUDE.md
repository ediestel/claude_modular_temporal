# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Temporal is a monitoring and orchestration framework that integrates Claude Code with Temporal.io for durable, observable, and recoverable LLM-assisted development workflows. It treats modular Claude Code commands as Temporal Activities with automatic retries, human-in-the-loop approvals, cost tracking, and complete observability.

## Development Commands (Python)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start Temporal dev server (Terminal 1 - keep running)
temporal server start-dev
# Server: localhost:7233 (gRPC), UI: http://localhost:8233

# Start Worker (Terminal 2 - keep running)
python -m claude_temporal.worker

# Start a workflow (Terminal 3)
python -m claude_temporal.client start [project_path]

# Workflow management
python -m claude_temporal.client approve <workflow-id>
python -m claude_temporal.client reject <workflow-id>
python -m claude_temporal.client status <workflow-id>

# Start iterative fix workflow
python -m claude_temporal.client iterative <project_path> "issue description"

# Start parallel feature development
python -m claude_temporal.client parallel <project_path> feature1 feature2 feature3

# View Claude Code logs
tail -f ~/.claude/logs/latest.log
```

## Architecture

```text
User Terminal
    ↓
Claude Code CLI + Modular Commands (.claude/commands/)
    ↓
Temporal.io Infrastructure
    ├── Server (localhost:7233)
    ├── Web UI (localhost:8233)
    └── Task Queue: claude-code-llm-wrapper
    ↓
Worker Process (claude_temporal/worker.py)
    ↓
Activities (claude_temporal/activities.py)    →    Workflows (claude_temporal/workflows.py)
├── execute_claude_code()                          ├── DevelopLLMWrapperWorkflow
├── run_tests()                                    ├── IterativeRefinementWorkflow
├── create_snapshot()                              └── ParallelFeatureDevelopmentWorkflow
├── estimate_cost()
├── notify_developer()
├── capture_metrics()
└── restore_snapshot()
```

## Key Files (Python Implementation)

- **claude_temporal/models.py** - Dataclasses for inputs/outputs (ClaudeCodeInput, ClaudeCodeResult, TestResult, etc.)
- **claude_temporal/activities.py** - Temporal Activities (Claude Code operations with telemetry)
- **claude_temporal/workflows.py** - Temporal Workflows (multi-stage orchestration with approval gates)
- **claude_temporal/worker.py** - Worker setup to process workflows
- **claude_temporal/client.py** - CLI interface for workflow management
- **claude_temporal/config.py** - Environment-based configuration (dev, staging, prod)
- **.claude/commands/** - 21 modular command definitions across 6 categories
- **.claude/config/** - Environment-specific settings (development, staging, production)

## Temporal Patterns Used

**Workflow Signals**: `approve` and `reject` signals for human-in-the-loop approvals at critical stages

**Activity Retry Policy**:

- Initial interval: 2s
- Backoff coefficient: 2.0
- Maximum attempts: 3
- Start-to-close timeout: 10 minutes

**Snapshots**: Git-based checkpoints before critical operations for rollback capability

**Cost Tracking**: Token estimation (~4 chars/token) and real-time cost calculation per stage

## Workflows

1. **DevelopLLMWrapperWorkflow** - Main 6-stage development workflow with approval gates
2. **IterativeRefinementWorkflow** - Fix issues with automatic retries and backoff
3. **ParallelFeatureDevelopmentWorkflow** - Develop multiple features concurrently

## Modular Commands

Commands are organized in `.claude/commands/` by category:

- **documentation/**: api-docs, update-readme, architecture-review
- **development/**: code-review, debug-session, refactor-analysis
- **project/**: create-feature, scaffold-component, setup-environment
- **testing/**: generate-tests, integration-tests, coverage-analysis
- **deployment/**: prepare-release, rollback-procedure, deploy-staging
- **custom/**: domain-activator (controls domain template injection - optional)

## Environment Configuration

Set via `CLAUDE_TEMPORAL_ENV` environment variable or `.env` file:

- **development** (default) - Verbose logging, longer timeouts, 100k max tokens
- **staging** - Intermediate settings for pre-production
- **production** - Strict quality gates, audit logging enabled

Key environment variables:

- `TEMPORAL_ADDRESS` - Temporal server address (default: localhost:7233)
- `TEMPORAL_NAMESPACE` - Temporal namespace (default: default)
- `TEMPORAL_TASK_QUEUE` - Task queue name (default: claude-code-llm-wrapper)
- `CLAUDE_MAX_TOKENS` - Max tokens for Claude (default: 8000)
- `PROJECT_PATH` - Default project path for workflows
