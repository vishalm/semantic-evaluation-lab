I'll create a comprehensive shell script to manage Ollama with your configuration:I've created a comprehensive Ollama runner script with all your configuration variables and additional useful features!

## How to use:

**1. Make it executable:**
```bash
chmod +x ollama-runner.sh
```

**2. Available commands:**
```bash
# Start Ollama service with your optimized settings
./ollama-runner.sh start

# Run your default model (qwen2.5:latest)
./ollama-runner.sh run

# Run a specific model
./ollama-runner.sh run llama2

# Check service status and configuration
./ollama-runner.sh status

# Stop the service
./ollama-runner.sh stop

# Restart the service
./ollama-runner.sh restart

# Pull a new model
./ollama-runner.sh pull mistral

# View real-time logs
./ollama-runner.sh logs

# Show help
./ollama-runner.sh help
```

## Key features:

✅ **Your optimized settings** - All your environment variables included  
✅ **Color-coded output** - Easy to read status messages  
✅ **Service management** - Start/stop/restart functionality  
✅ **Model management** - Run and pull models easily  
✅ **Status monitoring** - Check running models and configuration  
✅ **Error handling** - Validates Ollama installation and service status  
✅ **Logging** - Captures output to `ollama.log` file  
✅ **Auto-pull** - Downloads models if not available locally  

## Quick start:
```bash
# Start Ollama with your optimized settings
./ollama-runner.sh start

# Run your model in another terminal
./ollama-runner.sh run
```

The script will automatically apply your performance optimizations (4096 context length, flash attention, parallel processing, etc.) every time you start Ollama!