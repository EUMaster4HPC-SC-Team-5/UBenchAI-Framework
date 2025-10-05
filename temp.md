### Initial Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/EUMaster4HPC-SC-Team-5/UBenchAI-Framework.git
   cd UBenchAI-Framework
   ```

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Activate the virtual environment**:
   ```bash
   eval $(poetry env activate)
   ```

4. **Verify installation**:
   ```bash
   poetry run ubenchai --version
   poetry run ubenchai --help
   ```

## Running the Framework

The UBenchAI Framework can be run in multiple ways:

### Method 1: Via Poetry (Recommended for Development)
```bash
# Using the installed command
poetry run ubenchai server list

# With verbose logging
poetry run ubenchai -v server start --recipe llm-inference

# Run client commands
poetry run ubenchai client run --recipe stress-test
```

### Method 2: Via Python Module
```bash
# Run as a module
poetry run python -m ubenchai server list
```

### Method 3: Via main.py
```bash
# Direct execution of main.py
poetry run python main.py server list
```

### Method 4: After Shell Activation
```bash
# Activate the environment first
poetry shell

# Then run directly
ubenchai server list
ubenchai client run --recipe test
ubenchai monitor start --recipe metrics
```

## Command Reference

### Server Module
Manage containerized AI services:

```bash
# Start a service from a recipe
ubenchai server start --recipe <recipe-name> [--config <config-file>]

# Stop a running service
ubenchai server stop <service-id>

# List available/running services
ubenchai server list

# Get service status
ubenchai server status <service-id>
```

**Example:**
```bash
poetry run ubenchai server start --recipe llm-inference
```

### Client Module
Run benchmarking workloads:

```bash
# Run a client workload
ubenchai client run --recipe <recipe-name> [--overrides <overrides-file>]

# Stop a running client
ubenchai client stop <run-id>

# List available/running clients
ubenchai client list

# Get client run status
ubenchai client status <run-id>
```

**Example:**
```bash
poetry run ubenchai client run --recipe stress-test
```

### Monitor Module
Start monitoring and metrics collection:

```bash
# Start monitoring
ubenchai monitor start --recipe <recipe-name> [--targets <service1,service2>]

# Stop monitoring
ubenchai monitor stop <monitor-id>

# List monitors
ubenchai monitor list

# Show metrics
ubenchai monitor metrics <monitor-id> [--output <file>]

# Generate report
ubenchai monitor report <monitor-id> [--format html|json|pdf]
```

**Example:**
```bash
poetry run ubenchai monitor start --recipe system-metrics --targets api-server,db-server
```

### Code Formatting

The project uses Black for code formatting:

```bash
# Format all code
poetry run black src/

# Check formatting without making changes
poetry run black --check src/
```

### Working on Specific Modules


#### Server Module
```bash
# Edit server implementation
vim src/ubenchai/servers/manager.py

# Test server commands
poetry run ubenchai server start --recipe test-recipe
```

#### Client Module
```bash
# Edit client implementation
vim src/ubenchai/clients/manager.py

# Test client commands
poetry run ubenchai client run --recipe test-workload
```

#### Monitor Module
```bash
# Edit monitor implementation
vim src/ubenchai/monitors/manager.py

# Test monitor commands
poetry run ubenchai monitor start --recipe test-monitor
```

#### Reporting Module
```bash
# Add reporting functionality
vim src/ubenchai/monitors/report.py

# Test report generation
poetry run ubenchai monitor report <monitor-id> --format html
```

## Logging

The framework uses `loguru` for structured logging:

- **Default log level**: INFO
- **Verbose mode**: DEBUG (use `-v` or `--verbose` flag)
- **Log files**: Automatically created in `logs/` directory with rotation
- **Log format**: `YYYY-MM-DD HH:mm:ss | LEVEL | module:function - message`

**Example with verbose logging:**
```bash
poetry run ubenchai -v server start --recipe test
```

## Environment Variables

You can configure the framework using environment variables:

```bash
# Set log level
export UBENCHAI_LOG_LEVEL=DEBUG

# Set configuration directory
export UBENCHAI_CONFIG_DIR=/path/to/configs

# Run with environment
poetry run ubenchai server list
```

## Troubleshooting

### "Module not found" errors
```bash
# Reinstall dependencies
poetry install

# Verify installation
poetry run python -c "import ubenchai; print(ubenchai.__version__)"
```

### "Command not found: ubenchai"
```bash
# Make sure you're using poetry run
poetry run ubenchai --help

# Or activate the environment first
poetry shell
ubenchai --help
```


