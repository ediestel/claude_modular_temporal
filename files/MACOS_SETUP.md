# macOS Setup Guide: Temporal.io + Claude Code

Complete setup instructions for monitoring Claude Code with Temporal on macOS.

## Prerequisites  - DONE 

- macOS 12.0+ (Monterey or later) - DONE 
- Homebrew installed - DONE 
- Node.js 18+ installed - DONE 
- Claude account (Pro, Max, Teams, or Enterprise) - DONE 

---

## Step 1: Install Temporal CLI  - DONE 

```bash
# Install via Homebrew.  - DONE 
brew install temporal

# Verify installation 
temporal --version
# Expected output: temporal version 1.1.0 (or higher)
```

### Alternative: Install via cURL  - DONE 

```bash
curl -sSf https://temporal.download/cli.sh | sh

# Add to PATH
export PATH="$HOME/.temporalio/bin:$PATH"
echo 'export PATH="$HOME/.temporalio/bin:$PATH"' >> ~/.zshrc
```

---

## Step 2: Install Claude Code  - DONE 

```bash
# Install Claude Code via Homebrew
brew install claude

# Or via npm (if you prefer)
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version

# Login to Claude (first-time setup)
claude

# Follow prompts to authenticate with your Claude account
```

**Important:** You need an active Claude subscription (Pro, Max, or Teams).

---

## Step 3: Start Temporal Development Server

The Temporal dev server includes:
- Temporal Server
- Temporal Web UI (port 8233)
- Built-in database (SQLite)

```bash
# Start in a dedicated terminal window
temporal server start-dev

# Expected output:
# CLI 1.1.0
# Server 1.24.0
# UI     2.27.0
# 
# Temporal server is running at localhost:7233
# Web UI available at http://localhost:8233
```

**Keep this terminal open** - the server must run continuously.

---

## Step 4: Setup Project

```bash
# Clone or create project directory
mkdir -p ~/CLAUDE_TEMPORAL
cd ~/Desktop/CLAUDE_TEMPORAL

# Copy the demo files
# (workflows.ts, activities.ts, worker-client.ts, package.json)

# Install Node.js dependencies
npm install

# Or if using pnpm
pnpm install
```

---

## Step 5: Configure Environment

Create `.env` file:

```bash
cat > .env << 'EOF'
# Temporal Configuration
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=claude-code-llm-wrapper

# Claude Code Configuration
CLAUDE_API_KEY=your-api-key-here
CLAUDE_MAX_TOKENS=8000

# Project Configuration
PROJECT_PATH=/path/to/your/llm-wrapper-project
EOF
```

**Note:** Claude Code uses your authenticated session, so API key may not be needed.

---

## Step 6: Start the Worker

In a new terminal (keep Temporal server running):

```bash
cd ~/temporal-claude-demo

# Start the worker
npm run worker

# Expected output:
# Starting Temporal Worker for Claude Code monitoring...
# Worker created, listening on task queue: claude-code-llm-wrapper
# Worker ready to process workflows...
```

**Keep this terminal open** - the worker processes workflows.

---

## Step 7: Run Your First Workflow

In a third terminal:

```bash
cd ~/temporal-claude-demo

# Start LLM wrapper development workflow
npm run start-workflow

# Expected output:
# Connecting to Temporal...
# Starting LLM Wrapper development workflow...
# 
# Workflow started!
# Workflow ID: llm-wrapper-dev-1704123456789
# Run ID: abc123...
# 
# View in Temporal UI: http://localhost:8233/namespaces/default/workflows/llm-wrapper-dev-1704123456789
```

---

## Step 8: Monitor in Temporal UI

1. Open browser to http://localhost:8233
2. You'll see the Temporal Web UI
3. Click on your workflow to see:
   - Real-time execution status
   - Event history
   - Metrics and timing
   - Input/output data

---

## Step 9: Approve Stages (Human-in-the-Loop)

When workflow reaches an approval stage:

```bash
# Get workflow ID from output or UI
WORKFLOW_ID="llm-wrapper-dev-1704123456789"

# Approve the stage
npm run approve -- $WORKFLOW_ID

# Or reject it
npm run reject -- $WORKFLOW_ID

# Check workflow status
npm run status -- $WORKFLOW_ID
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      macOS System                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Terminal 1: Temporal Server                            │
│  ├─ Port 7233: gRPC API                                │
│  └─ Port 8233: Web UI                                  │
│                                                          │
│  Terminal 2: Worker Process                             │
│  ├─ Executes workflows                                 │
│  ├─ Runs activities                                    │
│  └─ Calls Claude Code CLI                             │
│                                                          │
│  Terminal 3: Client / Commands                          │
│  ├─ Start workflows                                    │
│  ├─ Send signals (approve/reject)                     │
│  └─ Query status                                       │
│                                                          │
│  Claude Code                                            │
│  ├─ Installed globally                                 │
│  ├─ Authenticated to your account                      │
│  └─ Called by worker activities                        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Issue: Temporal server won't start

```bash
# Check if port 7233 is in use
lsof -i :7233

# Kill process if needed
kill -9 <PID>

# Try starting again
temporal server start-dev
```

### Issue: Claude Code not authenticated

```bash
# Re-authenticate
claude

# Check authentication status
claude --version
```

### Issue: Worker can't connect to Temporal

```bash
# Verify Temporal is running
curl http://localhost:7233

# Check worker connection in logs
# Should see: "Worker created, listening on task queue..."
```

### Issue: "Command not found: temporal"

```bash
# Add to PATH
export PATH="$HOME/.temporalio/bin:$PATH"

# Or reinstall
brew uninstall temporal
brew install temporal
```

### Issue: Node.js version too old

```bash
# Update Node.js via Homebrew
brew upgrade node

# Or use nvm
nvm install 20
nvm use 20
```

---

## Production Configuration

For production use, replace dev server with:

### Option 1: Self-Hosted Temporal

```bash
# Using Docker Compose
git clone https://github.com/temporalio/docker-compose.git
cd docker-compose
docker-compose up -d

# Configure connection
export TEMPORAL_ADDRESS=localhost:7233
```

### Option 2: Temporal Cloud

```bash
# Sign up at https://temporal.io/cloud

# Configure connection
export TEMPORAL_ADDRESS=your-namespace.tmprl.cloud:7233
export TEMPORAL_NAMESPACE=your-namespace
export TEMPORAL_TLS_CERT_PATH=/path/to/cert.pem
export TEMPORAL_TLS_KEY_PATH=/path/to/key.pem
```

---

## Monitoring & Observability - UI for temporal has been installed already

### Grafana Dashboard (Optional)

```bash
# Install Prometheus
brew install prometheus

# Configure Temporal metrics export
# Edit temporal config to export metrics to Prometheus

# Install Grafana
brew install grafana
brew services start grafana

# Access Grafana: http://localhost:3000
# Import Temporal dashboard: 
# https://grafana.com/grafana/dashboards/12596
```

### Logs

```bash
# Worker logs
npm run worker 2>&1 | tee worker.log

# Temporal server logs
temporal server start-dev --log-level debug

# Claude Code logs
# Check ~/.claude/logs/
tail -f ~/.claude/logs/latest.log
```

---

## Testing the Integration

Run this quick test:

```bash
# Create test project
mkdir -p /tmp/test-llm-wrapper
cd /tmp/test-llm-wrapper
git init

# Start workflow pointing to this directory
# Edit worker-client.ts to use this path

# Monitor progress:
# 1. Terminal UI: Worker output
# 2. Web UI: http://localhost:8233
# 3. Claude Code: Activity logs

# Expected timeline:
# 0:00 - Workflow starts
# 0:01 - Scaffold stage begins
# 2:15 - Scaffold complete, tests running
# 2:20 - Tests pass, core-implementation begins
# 6:50 - Core complete, waiting for approval
# (manual approval)
# 6:55 - Streaming stage begins
# ... continues through all stages
```

---

## Next Steps

1. **Customize workflows** - Edit `workflows.ts` for your use case
2. **Add activities** - Create new activities in `activities.ts`
3. **Integrate tools** - Connect to GitHub, Slack, etc.
4. **Add monitoring** - Export metrics to Prometheus/Grafana
5. **Production deploy** - Move to Temporal Cloud or self-hosted

---

## Resources

- **Temporal Docs:** https://docs.temporal.io
- **Claude Code Docs:** https://code.claude.com/docs
- **TypeScript SDK:** https://typescript.temporal.io
- **Community:** https://community.temporal.io

---

## Cost Estimates

**Development Server (Free)**
- Temporal dev server: Free
- Temporal Web UI: Free
- Storage: Local SQLite

**Claude Code (Paid)**
- Pro: $20/month (limited usage)
- Max: $200/month (higher limits)
- Teams: Custom pricing

**Typical LLM Wrapper Development:**
- Tokens: ~50,000
- Cost: ~$0.50-$2.00
- Time: 20-120 minutes

---

## Support

- **Temporal:** https://community.temporal.io
- **Claude Code:** https://support.anthropic.com
- **Issues:** File issues in this repo

---

**You're now ready to use Temporal.io to monitor Claude Code on macOS! 🚀**
