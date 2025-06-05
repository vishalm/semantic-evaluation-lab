#!/bin/bash

# Ollama Runner Script
# Enhanced script to manage Ollama service with optimized settings

set -e  # Exit on any error

# Color codes for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
OLLAMA_HOST="http://localhost:11434"
OLLAMA_MODEL_ID="qwen2.5:latest"
OLLAMA_SERVICE_ID="ollama"
OLLAMA_DEBUG=1
OLLAMA_VERBOSE=1
OLLAMA_CONTEXT_LENGTH=4096
OLLAMA_NUM_PARALLEL=2
OLLAMA_FLASH_ATTENTION=true
OLLAMA_KEEP_ALIVE="50m"
OLLAMA_MAX_LOADED_MODELS=3
OLLAMA_MAX_QUEUE=512

# Export environment variables
export OLLAMA_HOST
export OLLAMA_DEBUG
export OLLAMA_VERBOSE
export OLLAMA_CONTEXT_LENGTH
export OLLAMA_NUM_PARALLEL
export OLLAMA_FLASH_ATTENTION
export OLLAMA_KEEP_ALIVE
export OLLAMA_MAX_LOADED_MODELS
export OLLAMA_MAX_QUEUE

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Ollama is installed
check_ollama() {
    if ! command -v ollama &> /dev/null; then
        print_error "Ollama is not installed or not in PATH"
        echo "Install from: https://ollama.ai/"
        exit 1
    fi
    print_success "Ollama found: $(ollama --version)"
}

# Function to check if Ollama service is running
is_ollama_running() {
    if pgrep -f "ollama serve" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to start Ollama service
start_ollama() {
    print_status "Starting Ollama service with enhanced configuration..."
    
    if is_ollama_running; then
        print_warning "Ollama service is already running"
        return 0
    fi
    
    echo "Configuration:"
    echo "  Host: $OLLAMA_HOST"
    echo "  Debug: $OLLAMA_DEBUG"
    echo "  Context Length: $OLLAMA_CONTEXT_LENGTH"
    echo "  Parallel Requests: $OLLAMA_NUM_PARALLEL"
    echo "  Flash Attention: $OLLAMA_FLASH_ATTENTION"
    echo "  Keep Alive: $OLLAMA_KEEP_ALIVE"
    echo "  Max Models: $OLLAMA_MAX_LOADED_MODELS"
    echo ""
    
    # Start Ollama in background
    nohup ollama serve > ollama.log 2>&1 &
    OLLAMA_PID=$!
    
    # Wait for service to start
    print_status "Waiting for Ollama service to start..."
    sleep 3
    
    # Check if service started successfully
    if is_ollama_running; then
        print_success "Ollama service started successfully (PID: $OLLAMA_PID)"
        echo "Log file: $(pwd)/ollama.log"
    else
        print_error "Failed to start Ollama service"
        exit 1
    fi
}

# Function to stop Ollama service
stop_ollama() {
    print_status "Stopping Ollama service..."
    
    if ! is_ollama_running; then
        print_warning "Ollama service is not running"
        return 0
    fi
    
    # Kill Ollama processes
    pkill -f "ollama serve" || true
    sleep 2
    
    if ! is_ollama_running; then
        print_success "Ollama service stopped successfully"
    else
        print_error "Failed to stop Ollama service"
        exit 1
    fi
}

# Function to restart Ollama service
restart_ollama() {
    print_status "Restarting Ollama service..."
    stop_ollama
    sleep 1
    start_ollama
}

# Function to show Ollama status
status_ollama() {
    echo "=== Ollama Status ==="
    
    if is_ollama_running; then
        print_success "Ollama service is running"
        
        # Show running models
        echo ""
        print_status "Running models:"
        ollama ps 2>/dev/null || echo "Unable to fetch running models"
        
        # Show available models
        echo ""
        print_status "Available models:"
        ollama list 2>/dev/null || echo "Unable to fetch model list"
        
    else
        print_warning "Ollama service is not running"
    fi
    
    echo ""
    echo "Configuration:"
    env | grep OLLAMA_ | sort
}

# Function to run a model
run_model() {
    local model=${1:-$OLLAMA_MODEL_ID}
    
    print_status "Starting model: $model"
    
    if ! is_ollama_running; then
        print_error "Ollama service is not running. Start it first with: $0 start"
        exit 1
    fi
    
    # Check if model exists, if not try to pull it
    if ! ollama list | grep -q "$model"; then
        print_status "Model $model not found locally. Pulling from registry..."
        ollama pull "$model"
    fi
    
    print_success "Starting interactive session with $model"
    print_status "Type 'exit' or press Ctrl+C to quit"
    echo ""
    
    ollama run "$model"
}

# Function to pull a model
pull_model() {
    local model=${1:-$OLLAMA_MODEL_ID}
    
    print_status "Pulling model: $model"
    
    if ! is_ollama_running; then
        print_error "Ollama service is not running. Start it first with: $0 start"
        exit 1
    fi
    
    ollama pull "$model"
    print_success "Model $model pulled successfully"
}

# Function to show logs
show_logs() {
    if [[ -f "ollama.log" ]]; then
        print_status "Showing Ollama logs (press Ctrl+C to exit):"
        tail -f ollama.log
    else
        print_warning "Log file not found. Make sure Ollama was started with this script."
    fi
}

# Function to show help
show_help() {
    echo "Ollama Runner Script"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start                 Start Ollama service with enhanced configuration"
    echo "  stop                  Stop Ollama service"
    echo "  restart               Restart Ollama service"
    echo "  status                Show Ollama service status and configuration"
    echo "  run [MODEL]           Run a model (default: $OLLAMA_MODEL_ID)"
    echo "  pull [MODEL]          Pull a model from registry"
    echo "  logs                  Show Ollama service logs"
    echo "  help                  Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start Ollama service"
    echo "  $0 run                # Run default model ($OLLAMA_MODEL_ID)"
    echo "  $0 run llama2         # Run specific model"
    echo "  $0 status             # Check service status"
    echo ""
    echo "Configuration can be modified by editing the variables at the top of this script."
}

# Main script logic
main() {
    # Check if Ollama is installed
    check_ollama
    
    # Parse command line arguments
    case "${1:-help}" in
        "start")
            start_ollama
            ;;
        "stop")
            stop_ollama
            ;;
        "restart")
            restart_ollama
            ;;
        "status")
            status_ollama
            ;;
        "run")
            run_model "$2"
            ;;
        "pull")
            pull_model "$2"
            ;;
        "logs")
            show_logs
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"