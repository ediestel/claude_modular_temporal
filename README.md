# Claude Temporal

A monitoring and orchestration framework that integrates Claude Code (extended with claude_modular - https://github.com/oxygen-fragment/claude-modular) with [Temporal.io](https://temporal.io) for durable, observable, and recoverable LLM-assisted development workflows.

## Overview

Claude Temporal treats modular Claude Code commands as Temporal Activities with:
- **Automatic retries** with exponential backoff
- **Human-in-the-loop approvals** at critical stages
- **Cost tracking** in real-time
- **Git-based snapshots** for rollback capability
- **Complete observability** through Temporal's Web UI

## Features

- **Multi-stage Development Workflows** - Orchestrate complex development tasks across multiple stages
- **Pluggable Notification Services** - Console, Slack, Webhook, or custom notification backends
- **Auto-detecting Test Runners** - Supports npm/Jest, pytest, cargo, and go test
- **Configurable Stage Definitions** - Customize workflow stages via templates
- **Parallel Feature Development** - Develop multiple features concurrently on isolated branches
- **Iterative Refinement** - Automatically retry fixes until tests pass

## Modular Commands (claude_modular)

Claude Temporal includes a modular command system in `.claude/commands/` that provides reusable, structured prompts for common development tasks. These commands can be invoked as slash commands within Claude Code.

### Command Categories

| Category | Commands | Description |
|----------|----------|-------------|
| **documentation** | `api-docs`, `update-readme`, `architecture-review` | Generate and maintain documentation |
| **development** | `code-review`, `debug-session`, `refactor-analysis` | Development workflow automation |
| **project** | `create-feature`, `scaffold-component`, `setup-environment` | Project scaffolding and setup |
| **testing** | `generate-tests`, `integration-tests`, `coverage-analysis` | Test generation and analysis |
| **deployment** | `prepare-release`, `rollback-procedure`, `deploy-staging` | Deployment automation |
| **custom** | `domain-activator` | Domain-specific template injection |

### Using Modular Commands

Invoke commands using the slash command syntax in Claude Code:

```bash
# Documentation commands
/documentation:api-docs           # Generate API documentation
/documentation:update-readme      # Update README with latest changes
/documentation:architecture-review # Review system architecture

# Development commands
/development:code-review          # Comprehensive code review
/development:debug-session        # Interactive debugging session
/development:refactor-analysis    # Analyze code for refactoring

# Project commands
/project:create-feature <name>    # Create new feature with full scaffolding
/project:scaffold-component       # Generate component boilerplate
/project:setup-environment        # Configure development environment

# Testing commands
/testing:generate-tests           # Generate unit and integration tests
/testing:integration-tests        # Create integration test suite
/testing:coverage-analysis        # Analyze test coverage

# Deployment commands
/deployment:prepare-release       # Prepare release artifacts
/deployment:rollback-procedure    # Document rollback steps
/deployment:deploy-staging        # Deploy to staging environment
```

### Command Structure

Each command is a markdown file with structured instructions:

```markdown
# Command Name

<instructions>
  <context>
    Description of what this command does and when to use it.
  </context>

  <requirements>
    - Prerequisites for running this command
  </requirements>

  <execution>
    1. Step-by-step execution plan
    2. What actions will be taken
  </execution>

  <validation>
    - [ ] Checklist of success criteria
  </validation>

  <examples>
    Usage examples with expected output
  </examples>
</instructions>
```

### Creating Custom Commands

1. Create a new `.md` file in the appropriate category folder:
   ```bash
   touch .claude/commands/development/my-command.md
   ```

2. Follow the command structure template above

3. Use the command with:
   ```bash
   /development:my-command
   ```

### Directory Structure

```
.claude/
├── commands/
│   ├── custom/
│   │   └── domain-activator.xml
│   ├── deployment/
│   │   ├── deploy-staging.md
│   │   ├── prepare-release.md
│   │   └── rollback-procedure.md
│   ├── development/
│   │   ├── code-review.md
│   │   ├── debug-session.md
│   │   └── refactor-analysis.md
│   ├── documentation/
│   │   ├── api-docs.md
│   │   ├── architecture-review.md
│   │   └── update-readme.md
│   ├── project/
│   │   ├── create-feature.md
│   │   ├── scaffold-component.md
│   │   └── setup-environment.md
│   └── testing/
│       ├── coverage-analysis.md
│       ├── generate-tests.md
│       └── integration-tests.md
├── config/
│   ├── development.json
│   ├── production.json
│   ├── settings.json
│   └── staging.json
├── hooks/
│   └── UserPromptSubmit/
│       └── domain_dynamic_injector.py
└── tests/
    └── test_domain_dynamic_injector.py
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Terminal                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Claude Temporal Client (CLI)                              │
│                    python -m claude_temporal.client                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Temporal.io Infrastructure                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ Server          │  │ Web UI          │  │ Task Queue                  │  │
│  │ localhost:7233  │  │ localhost:8233  │  │ claude-code-llm-wrapper     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Worker Process                                       │
│                    python -m claude_temporal.worker                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
┌──────────────────────────────┐            ┌──────────────────────────────────┐
│         Activities           │            │           Workflows              │
│  ├─ execute_claude_code()    │            │  ├─ DevelopLLMWrapperWorkflow    │
│  ├─ run_tests()              │            │  ├─ IterativeRefinementWorkflow  │
│  ├─ create_snapshot()        │            │  └─ ParallelFeatureDevelopment   │
│  ├─ estimate_cost()          │            │                                  │
│  ├─ notify_developer()       │            │                                  │
│  ├─ capture_metrics()        │            │                                  │
│  └─ restore_snapshot()       │            │                                  │
└──────────────────────────────┘            └──────────────────────────────────┘
```

## Requirements

- Python 3.10+
- [Temporal CLI](https://docs.temporal.io/cli) or Temporal Server
- [Claude Code CLI](https://claude.ai/code) installed and authenticated
- Git

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/ediestel/claude_modular_temporal.git
cd claude_modular_temporal
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Temporal CLI (if not already installed)

```bash
# macOS
brew install temporal

# Or download from https://docs.temporal.io/cli
```

### 4. Verify Claude Code is Installed

```bash
claude --version
```

## Quick Start

### Terminal 1: Start Temporal Server

```bash
temporal server start-dev
```

This starts:
- gRPC server on `localhost:7233`
- Web UI on `http://localhost:8233`

### Terminal 2: Start the Worker

```bash
python -m claude_temporal.worker
```

### Terminal 3: Start a Workflow

```bash
# Start the main development workflow
python -m claude_temporal.client start /path/to/project

# Or with specific features
python -m claude_temporal.client start /path/to/project --features openai anthropic streaming
```

### Terminal 4: Monitor and Approve

Open http://localhost:8233 to view workflow progress, or use CLI:

```bash
# Check status
python -m claude_temporal.client status <workflow-id>

# Approve a stage waiting for review
python -m claude_temporal.client approve <workflow-id>

# Reject a stage
python -m claude_temporal.client reject <workflow-id>
```

---

# User Manual

## Table of Contents

1. [Workflows](#workflows)
2. [CLI Commands](#cli-commands)
3. [Configuration](#configuration)
4. [Notification Services](#notification-services)
5. [Test Runners](#test-runners)
6. [Stage Configuration](#stage-configuration)
7. [Environment Variables](#environment-variables)
8. [Monitoring & Observability](#monitoring--observability)
9. [Troubleshooting](#troubleshooting)

---

## Workflows

### DevelopLLMWrapperWorkflow

The main workflow for developing an LLM wrapper library. Executes 6 stages:

| Stage | Description | Approval Required |
|-------|-------------|-------------------|
| scaffold | Create project structure | No |
| core-implementation | Implement base classes and providers | **Yes** |
| streaming | Add streaming support | No |
| error-handling | Implement retry logic, circuit breakers | No |
| testing | Create comprehensive test suite | No |
| documentation | Generate README and API docs | No |

**Usage:**

```bash
python -m claude_temporal.client start /path/to/project
```

**Workflow Behavior:**
- Creates git snapshots before critical stages
- Runs tests after each stage (except documentation)
- Rolls back to last snapshot if critical stage fails
- Waits up to 1 hour for human approval
- Tracks token usage and costs

### IterativeRefinementWorkflow

Automatically fixes issues through multiple iterations until tests pass.

**Usage:**

```bash
python -m claude_temporal.client iterative /path/to/project "Fix the authentication bug in login.py"
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--max-iterations` | 5 | Maximum retry attempts |

**Workflow Behavior:**
- Creates snapshot before each iteration
- Applies exponential backoff between retries (5s, 10s, 15s... up to 30s)
- Fails if tests don't pass after max iterations

### ParallelFeatureDevelopmentWorkflow

Develops multiple features concurrently on separate git branches.

**Usage:**

```bash
python -m claude_temporal.client parallel /path/to/project "user-auth" "api-caching" "dark-mode"
```

**Workflow Behavior:**
- Creates a branch for each feature: `feature-0-user-auth`, `feature-1-api-caching`, etc.
- Runs all feature implementations concurrently
- Tests each feature independently
- Reports success/failure for each feature

---

## CLI Commands

### `start` - Start Development Workflow

```bash
python -m claude_temporal.client start [PROJECT_PATH] [OPTIONS]
```

**Arguments:**
- `PROJECT_PATH` - Path to project directory (default: current directory)

**Options:**
- `--features` - Features to implement (default: openai anthropic streaming error-handling)

**Example:**
```bash
python -m claude_temporal.client start ./my-project --features openai anthropic
```

### `iterative` - Start Iterative Fix Workflow

```bash
python -m claude_temporal.client iterative PROJECT_PATH ISSUE [OPTIONS]
```

**Arguments:**
- `PROJECT_PATH` - Path to project directory
- `ISSUE` - Description of the issue to fix

**Options:**
- `--max-iterations` - Maximum retry attempts (default: 5)

**Example:**
```bash
python -m claude_temporal.client iterative ./my-project "TypeError in utils.py line 42" --max-iterations 3
```

### `parallel` - Start Parallel Feature Development

```bash
python -m claude_temporal.client parallel PROJECT_PATH FEATURES...
```

**Arguments:**
- `PROJECT_PATH` - Path to project directory
- `FEATURES` - One or more feature names to implement

**Example:**
```bash
python -m claude_temporal.client parallel ./my-project search-api user-profiles notifications
```

### `approve` - Approve Workflow Stage

```bash
python -m claude_temporal.client approve WORKFLOW_ID
```

Sends an approval signal to a workflow waiting for human review.

### `reject` - Reject Workflow Stage

```bash
python -m claude_temporal.client reject WORKFLOW_ID
```

Sends a rejection signal, causing the workflow to fail.

### `status` - Query Workflow Status

```bash
python -m claude_temporal.client status WORKFLOW_ID
```

**Output:**
```
Workflow State:
  ID: llm-wrapper-dev-1705234567890
  Status: RUNNING
  Started: 2024-01-14 12:34:56
  Task Queue: claude-code-llm-wrapper

Workflow Progress:
  Current Stage: core-implementation
  Total Tokens: 15234
  Total Cost: $0.1523
  Tests Passed: 1
  Snapshots: 2
```

---

## Configuration

### Configuration Files

Configuration is loaded from environment variables and `.env` file.

Create a `.env` file in your project root:

```env
# Environment: development, staging, production
CLAUDE_TEMPORAL_ENV=development

# Temporal settings
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=claude-code-llm-wrapper

# Claude settings
CLAUDE_MAX_TOKENS=100000
CLAUDE_TEMPERATURE=0.3
CLAUDE_TIMEOUT=1800

# Notifications
NOTIFICATION_TYPE=console
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx
SLACK_CHANNEL=#dev-notifications

# Metrics
METRICS_FILE=/tmp/claude-code-metrics.jsonl
```

### Environment Presets

| Setting | Development | Staging | Production |
|---------|-------------|---------|------------|
| `max_tokens` | 100,000 | 8,000 | 8,000 |
| `temperature` | 0.3 | 0.3 | 0.2 |
| `timeout` | 30 min | 10 min | 10 min |

---

## Notification Services

Claude Temporal supports multiple notification backends for human-in-the-loop approvals.

### Console (Default)

Prints notifications to stdout:

```env
NOTIFICATION_TYPE=console
```

### Slack

Send notifications to a Slack channel:

```env
NOTIFICATION_TYPE=slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX
SLACK_CHANNEL=#claude-notifications
```

### Webhook

Send notifications to any HTTP endpoint:

```env
NOTIFICATION_TYPE=webhook
NOTIFICATION_WEBHOOK_URL=https://your-server.com/webhook
```

Payload format:
```json
{
  "stage": "core-implementation",
  "message": "Stage 'core-implementation' complete. Review required.",
  "files_changed": ["src/client.ts", "src/provider.ts"],
  "diff_url": null
}
```

### Composite (Multiple Services)

In code, you can combine multiple notification services:

```python
from claude_temporal.notification import (
    ConsoleNotificationService,
    SlackNotificationService,
    CompositeNotificationService,
    SlackConfig,
)

service = CompositeNotificationService([
    ConsoleNotificationService(),
    SlackNotificationService(SlackConfig(
        webhook_url="https://hooks.slack.com/...",
        channel="#notifications"
    )),
])
```

---

## Test Runners

Claude Temporal automatically detects and uses the appropriate test framework.

### Supported Frameworks

| Framework | Detection | Command |
|-----------|-----------|---------|
| npm/Jest | `package.json` exists | `npm test -- --json --coverage` |
| pytest | `pytest.ini`, `pyproject.toml`, `setup.py`, or `tests/` dir | `pytest --tb=short -q` |
| Cargo | `Cargo.toml` exists | `cargo test` |
| Go | `go.mod` exists | `go test -v ./...` |

### Manual Selection

In code, you can explicitly select a test runner:

```python
from claude_temporal.test_runner import get_test_runner

# Auto-detect
runner = get_test_runner()

# Or specify explicitly
runner = get_test_runner("pytest")
runner = get_test_runner("npm")
runner = get_test_runner("cargo")
runner = get_test_runner("go")
```

---

## Stage Configuration

Stages are configurable via templates. You can customize prompts, skip stages, or create entirely new workflows.

### Default Stage Templates

```python
from claude_temporal.stages import create_stage_config, get_default_stages

# Get default LLM wrapper stages
stages = get_default_stages("llm-wrapper")

# Or API development stages
stages = get_default_stages("api")

# Or frontend stages
stages = get_default_stages("frontend")
```

### Custom Stage Configuration

```python
from claude_temporal.stages import StageConfig, StageTemplate

config = StageConfig(
    stages=[
        StageTemplate(
            name="setup",
            prompt_template="Initialize project in {project_path}",
            requires_approval=False,
            critical_path=True,
        ),
        StageTemplate(
            name="implementation",
            prompt_template="Implement the main feature",
            requires_approval=True,
            critical_path=True,
        ),
    ],
    skip_stages=["documentation"],  # Skip specific stages
    custom_prompts={
        "testing": "Write unit tests with 90% coverage",  # Override prompts
    },
)

stages = config.get_stages(project_path="/path/to/project")
```

### Stage Template Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | str | required | Stage identifier |
| `prompt_template` | str | required | Prompt with `{project_path}` placeholder |
| `requires_approval` | bool | False | Wait for human approval |
| `critical_path` | bool | True | Create snapshot and rollback on failure |
| `skip_tests` | bool | False | Skip test validation |
| `max_tokens` | int | 8000 | Token limit for Claude |
| `temperature` | float | 0.3 | Claude temperature setting |

---

## Environment Variables

### Temporal Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal server address |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace |
| `TEMPORAL_TASK_QUEUE` | `claude-code-llm-wrapper` | Task queue name |
| `TEMPORAL_UI_BASE_URL` | `http://localhost:8233` | Web UI URL |

### Claude Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_TEMPORAL_ENV` | `development` | Environment preset |
| `CLAUDE_MAX_TOKENS` | varies | Maximum tokens per request |
| `CLAUDE_TEMPERATURE` | varies | Temperature setting |
| `CLAUDE_TIMEOUT` | varies | Execution timeout (seconds) |

### Worker Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKER_MAX_ACTIVITIES` | `5` | Max concurrent activities |
| `WORKER_MAX_WORKFLOWS` | `10` | Max concurrent workflows |

### Notification Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTIFICATION_TYPE` | `console` | Notification backend |
| `SLACK_WEBHOOK_URL` | - | Slack webhook URL |
| `SLACK_CHANNEL` | - | Slack channel |
| `NOTIFICATION_WEBHOOK_URL` | - | Custom webhook URL |

### Other

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_PATH` | - | Default project path |
| `METRICS_FILE` | `/tmp/claude-code-metrics.jsonl` | Metrics output file |

---

## Monitoring & Observability

### Temporal Web UI

Access the Temporal Web UI at http://localhost:8233 to:

- View running and completed workflows
- Inspect workflow history and events
- See activity inputs and outputs
- Monitor task queue health
- Debug failed workflows

### Metrics File

Claude Temporal writes metrics to a JSONL file (default: `/tmp/claude-code-metrics.jsonl`):

```json
{"stage": "scaffold", "tokens_used": 2345, "cost": 0.0234, "duration_ms": 45000, "files_modified": 5, "lines_added": 234, "lines_removed": 0, "tests_pass": true, "error": null, "timestamp": "2024-01-14T12:34:56.789"}
{"stage": "core-implementation", "tokens_used": 5678, "cost": 0.0567, "duration_ms": 120000, "files_modified": 8, "lines_added": 456, "lines_removed": 23, "tests_pass": true, "error": null, "timestamp": "2024-01-14T12:36:56.789"}
```

### Analyzing Metrics

```bash
# View all metrics
cat /tmp/claude-code-metrics.jsonl | jq .

# Calculate total cost
cat /tmp/claude-code-metrics.jsonl | jq -s 'map(.cost) | add'

# Find failed stages
cat /tmp/claude-code-metrics.jsonl | jq 'select(.tests_pass == false)'
```

### Claude Code Logs

View Claude Code execution logs:

```bash
tail -f ~/.claude/logs/latest.log
```

---

## Troubleshooting

### Common Issues

#### "Temporal server not running"

```
Error: Connection refused to localhost:7233
```

**Solution:** Start the Temporal server:
```bash
temporal server start-dev
```

#### "Claude CLI not found"

```
Error: FileNotFoundError: claude
```

**Solution:** Install Claude Code CLI:
```bash
# Follow instructions at https://claude.ai/code
```

#### "Workflow approval timeout"

```
Error: Approval timeout for stage core-implementation
```

**Solution:** Approve the workflow within 1 hour:
```bash
python -m claude_temporal.client approve <workflow-id>
```

#### "Tests failing after stage"

```
Error: Critical stage core-implementation failed tests
```

**Solution:** The workflow automatically rolls back to the last snapshot. Check the test output in Temporal UI and fix the issue before retrying.

#### "No test framework detected"

```
Error: No supported test framework detected
```

**Solution:** Ensure your project has one of:
- `package.json` (npm)
- `pytest.ini`, `pyproject.toml`, or `setup.py` (pytest)
- `Cargo.toml` (Rust)
- `go.mod` (Go)

### Debug Mode

Enable verbose logging:

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Or in Python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Getting Help

1. Check the [Temporal documentation](https://docs.temporal.io)
2. View workflow history in Temporal UI
3. Check Claude Code logs: `~/.claude/logs/latest.log`
4. Review metrics: `cat /tmp/claude-code-metrics.jsonl | jq .`

---

## API Reference

### Models

```python
from claude_temporal import (
    ClaudeCodeInput,    # Input for Claude Code execution
    ClaudeCodeResult,   # Result with telemetry
    TestResult,         # Test execution results
    CostEstimate,       # Pre-execution cost estimate
    WorkflowState,      # Current workflow state
    NotificationParams, # Notification parameters
    MetricsData,        # Observability metrics
    FeatureResult,      # Parallel feature result
)
```

### Activities

```python
from claude_temporal import (
    execute_claude_code,  # Run Claude Code CLI
    run_tests,            # Execute test suite
    create_snapshot,      # Create git snapshot
    restore_snapshot,     # Restore to snapshot
    estimate_cost,        # Estimate execution cost
    notify_developer,     # Send notification
    capture_metrics,      # Record metrics
)
```

### Workflows

```python
from claude_temporal import (
    DevelopLLMWrapperWorkflow,        # Main development workflow
    IterativeRefinementWorkflow,      # Fix issues iteratively
    ParallelFeatureDevelopmentWorkflow,  # Parallel feature dev
)
```

### Utilities

```python
from claude_temporal import (
    # Git operations
    GitOperations,

    # Notification services
    NotificationService,
    ConsoleNotificationService,
    SlackNotificationService,
    get_notification_service,

    # Test runners
    TestRunner,
    AutoDetectTestRunner,
    get_test_runner,

    # Configuration
    get_config,
    load_config,
)
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit: `git commit -m "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [Temporal.io](https://temporal.io) - Durable execution platform
- [Claude Code](https://claude.ai/code) - AI coding assistant
- [Anthropic](https://anthropic.com) - Claude AI

---

Built with Claude Opus 4.5
