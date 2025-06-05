#!/usr/bin/env python3
"""
Semantic Evaluation Lab - Web UI Backend (Fixed)

A comprehensive FastAPI application that provides a user-friendly web interface
for managing the entire Semantic Evaluation Lab ecosystem.
"""

import asyncio
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
from starlette.websockets import WebSocketState

# Optional Docker import with fallback
try:
    import docker
    from docker.errors import DockerException
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    logger = None

# Import our existing components
from config import app_config
import structlog

# Initialize logger
logger = structlog.get_logger(__name__)

# FastAPI app
app = FastAPI(
    title="Semantic Evaluation Lab",
    description="Comprehensive AI Evaluation & Observability Platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(message)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message)
                else:
                    disconnected.append(connection)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Data models
class LabConfig(BaseModel):
    lab_name: str = "Semantic-Evaluation-Lab"
    lab_environment: str = "development"
    use_ollama: bool = True
    auto_run_tests: bool = False
    enable_monitoring: bool = True
    enable_debug_mode: bool = True

class TestExecution(BaseModel):
    test_type: str
    auto_run: bool = False
    parameters: Dict[str, Any] = {}

class LoadTestConfig(BaseModel):
    users: int = 1
    spawn_rate: int = 1
    run_time: str = "300s"
    target_host: str = "http://localhost:8000"

class ServiceStatus(BaseModel):
    name: str
    status: str
    health: str
    uptime: Optional[str] = None
    url: Optional[str] = None

# Helper functions
def get_docker_client():
    """Get Docker client instance."""
    if not DOCKER_AVAILABLE:
        return None
    try:
        client = docker.from_env()
        # Test connection
        client.ping()
        return client
    except DockerException as e:
        if logger:
            logger.error(f"Docker connection failed: {e}")
        return None

def check_docker_status() -> Dict[str, Any]:
    """Check if Docker is running and accessible."""
    if DOCKER_AVAILABLE:
        try:
            client = get_docker_client()
            if client is None:
                return {
                    "success": False,
                    "message": "Cannot connect to Docker daemon. Is Docker running?",
                    "error": "docker_not_running"
                }
            
            # Test with a simple command
            info = client.info()
            return {
                "success": True,
                "message": "Docker is running",
                "info": info
            }
        except DockerException as e:
            if "Cannot connect to the Docker daemon" in str(e):
                return {
                    "success": False,
                    "message": "Cannot connect to Docker daemon. Is Docker running?",
                    "error": "docker_not_running"
                }
            else:
                return {
                    "success": False,
                    "message": f"Docker check failed: {str(e)}",
                    "error": "docker_error"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}",
                "error": "unexpected_error"
            }
    else:
        # Fallback when docker library is not available
        # Check if Docker socket exists (indicates Docker is available)
        docker_socket_path = "/var/run/docker.sock"
        if os.path.exists(docker_socket_path):
            # Socket exists, assume Docker is available
            return {
                "success": True,
                "message": "Docker socket detected - Docker appears to be running"
            }
        else:
            # Try subprocess as last resort
            result = run_command("docker info")
            if result["success"]:
                return {
                    "success": True,
                    "message": "Docker is running"
                }
            elif "not found" in result["stderr"]:
                return {
                    "success": False,
                    "message": "Docker CLI not available in container. Use Docker socket or install Docker CLI.",
                    "error": "docker_cli_not_available"
                }
            elif "Cannot connect to the Docker daemon" in result["stderr"]:
                return {
                    "success": False,
                    "message": "Cannot connect to Docker daemon. Is Docker running?",
                    "error": "docker_not_running"
                }
            else:
                return {
                    "success": False,
                    "message": f"Docker check failed: {result['stderr']}",
                    "error": "docker_error"
                }

def run_command(command: str, cwd: str = None) -> Dict[str, Any]:
    """Execute a shell command and return the result."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd or os.getcwd(),
            timeout=300
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Command timed out",
            "returncode": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }

def get_service_health(service_url: str) -> str:
    """Check if a service is healthy."""
    try:
        response = requests.get(f"{service_url}/health", timeout=5)
        return "healthy" if response.status_code == 200 else "unhealthy"
    except Exception:
        return "unhealthy"

def get_docker_services() -> List[ServiceStatus]:
    """Get status of all Docker Compose services."""
    services = []
    
    if DOCKER_AVAILABLE:
        try:
            client = get_docker_client()
            if client is None:
                return services
            
            # Get all containers with the project label
            containers = client.containers.list(all=True, filters={
                "label": "com.docker.compose.project=semantic-evaluation-lab"
            })
            
            for container in containers:
                try:
                    service_name = container.labels.get("com.docker.compose.service", container.name)
                    status = "running" if container.status == "running" else "stopped"
                    
                    # Determine health based on service type and container health
                    health = "unknown"
                    url = None
                    
                    # Check container health if available
                    if hasattr(container, 'attrs') and 'State' in container.attrs:
                        health_status = container.attrs['State'].get('Health', {}).get('Status')
                        if health_status == 'healthy':
                            health = "healthy"
                        elif health_status == 'unhealthy':
                            health = "unhealthy"
                        elif status == "running":
                            # If no health check but running, test with HTTP
                            if service_name == "grafana":
                                url = "http://localhost:3000"
                                health = get_service_health("http://localhost:3000")
                            elif service_name == "prometheus":
                                url = "http://localhost:9090"
                                health = get_service_health("http://localhost:9090")
                            elif service_name == "ollama":
                                url = "http://localhost:11434"
                                health = get_service_health("http://localhost:11434/api/tags")
                            elif service_name == "metrics-exporter":
                                url = "http://localhost:8000"
                                health = get_service_health("http://localhost:8000")
                            elif service_name == "web-ui":
                                url = "http://localhost:5000"
                                health = "healthy"  # We're running, so we're healthy
                            else:
                                health = "healthy" if status == "running" else "stopped"
                    
                    services.append(ServiceStatus(
                        name=service_name,
                        status=status,
                        health=health,
                        url=url
                    ))
                    
                except Exception as e:
                    if logger:
                        logger.error(f"Error processing container {container.name}: {e}")
                    continue
                    
        except Exception as e:
            if logger:
                logger.error(f"Error getting Docker services: {e}")
    else:
        # Fallback to subprocess when docker library is not available
        try:
            result = run_command("docker-compose ps --format json")
            if result["success"]:
                lines = result["stdout"].strip().split('\n')
                for line in lines:
                    if line.strip():
                        try:
                            service_data = json.loads(line)
                            status = "running" if service_data.get("State") == "running" else "stopped"
                            
                            # Determine health based on service type
                            health = "unknown"
                            url = None
                            
                            service_name = service_data.get("Service", "")
                            if service_name == "grafana":
                                url = "http://localhost:3000"
                                health = get_service_health("http://localhost:3000")
                            elif service_name == "prometheus":
                                url = "http://localhost:9090"
                                health = get_service_health("http://localhost:9090")
                            elif service_name == "ollama":
                                url = "http://localhost:11434"
                                health = get_service_health("http://localhost:11434/api/tags")
                            elif service_name == "metrics-exporter":
                                url = "http://localhost:8000"
                                health = get_service_health("http://localhost:8000")
                            elif service_name == "web-ui":
                                url = "http://localhost:5000"
                                health = "healthy"  # We're running, so we're healthy
                            
                            services.append(ServiceStatus(
                                name=service_name,
                                status=status,
                                health=health,
                                url=url
                            ))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            if logger:
                logger.error(f"Error getting Docker services: {e}")
    
    return services

# Background task for broadcasting updates
async def broadcast_updates():
    """Background task to broadcast service updates."""
    while True:
        try:
            services = get_docker_services()
            services_data = [service.dict() for service in services]
            await manager.broadcast(json.dumps({
                "type": "service_update",
                "data": services_data
            }))
            await asyncio.sleep(10)  # Update every 10 seconds
        except Exception as e:
            logger.error(f"Error in broadcast updates: {e}")
            await asyncio.sleep(5)

# Start background task
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_updates())

# API Routes

@app.get("/")
async def root():
    """Serve the main UI."""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Semantic Evaluation Lab - Enterprise Dashboard</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-50: #f0f9ff;
            --primary-100: #e0f2fe;
            --primary-200: #bae6fd;
            --primary-500: #0ea5e9;
            --primary-600: #0284c7;
            --primary-700: #0369a1;
            --primary-800: #075985;
            --primary-900: #0c4a6e;
            
            --gray-50: #f8fafc;
            --gray-100: #f1f5f9;
            --gray-200: #e2e8f0;
            --gray-300: #cbd5e1;
            --gray-400: #94a3b8;
            --gray-500: #64748b;
            --gray-600: #475569;
            --gray-700: #334155;
            --gray-800: #1e293b;
            --gray-900: #0f172a;
            
            --success-50: #f0fdf4;
            --success-500: #22c55e;
            --success-600: #16a34a;
            
            --warning-50: #fffbeb;
            --warning-500: #f59e0b;
            --warning-600: #d97706;
            
            --error-50: #fef2f2;
            --error-500: #ef4444;
            --error-600: #dc2626;
            
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
        }
        
        * {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, var(--gray-50) 0%, var(--gray-100) 100%);
            min-height: 100vh;
            margin: 0;
            padding: 0;
        }
        
        .enterprise-gradient {
            background: linear-gradient(135deg, var(--primary-800) 0%, var(--primary-900) 50%, var(--gray-900) 100%);
        }
        
        .enterprise-card {
            background: white;
            border: 1px solid var(--gray-200);
            border-radius: 12px;
            box-shadow: var(--shadow-sm);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .enterprise-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
            border-color: var(--primary-200);
        }
        
        .enterprise-button {
            background: var(--primary-600);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-weight: 500;
            font-size: 14px;
            transition: all 0.2s ease;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        .enterprise-button:hover {
            background: var(--primary-700);
            transform: translateY(-1px);
            box-shadow: var(--shadow-md);
        }
        
        .enterprise-button:active {
            transform: translateY(0);
        }
        
        .enterprise-nav-tab {
            background: transparent;
            color: rgba(255, 255, 255, 0.8);
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-weight: 500;
            font-size: 14px;
            transition: all 0.2s ease;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            white-space: nowrap;
        }
        
        .enterprise-nav-tab:hover {
            background: rgba(255, 255, 255, 0.1);
            color: white;
        }
        
        .enterprise-nav-tab.active {
            background: white;
            color: var(--primary-700);
            box-shadow: var(--shadow-sm);
        }
        
        .enterprise-status-card {
            border-radius: 8px;
            padding: 16px;
            margin: 16px 0;
            border-left: 4px solid;
            backdrop-filter: blur(10px);
        }
        
        .enterprise-status-card.loading {
            background: var(--primary-50);
            border-left-color: var(--primary-500);
            color: var(--primary-800);
        }
        
        .enterprise-status-card.success {
            background: var(--success-50);
            border-left-color: var(--success-500);
            color: var(--success-800);
        }
        
        .enterprise-status-card.error {
            background: var(--error-50);
            border-left-color: var(--error-500);
            color: var(--error-800);
        }
        
        .enterprise-status-card.warning {
            background: var(--warning-50);
            border-left-color: var(--warning-500);
            color: var(--warning-800);
        }
        
        .enterprise-metric-card {
            background: white;
            border: 1px solid var(--gray-200);
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            box-shadow: var(--shadow-sm);
            transition: all 0.3s ease;
        }
        
        .enterprise-metric-card:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }
        
        .enterprise-metric-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary-600);
            margin-bottom: 8px;
        }
        
        .enterprise-metric-label {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .enterprise-section-header {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--gray-900);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .enterprise-section-subtitle {
            font-size: 1rem;
            color: var(--gray-600);
            margin-bottom: 24px;
        }
        
        .loading-spinner {
            border: 2px solid var(--gray-200);
            border-radius: 50%;
            border-top: 2px solid var(--primary-600);
            width: 16px;
            height: 16px;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .enterprise-grid {
            display: grid;
            gap: 24px;
        }
        
        .enterprise-grid.cols-1 { grid-template-columns: 1fr; }
        .enterprise-grid.cols-2 { grid-template-columns: repeat(2, 1fr); }
        .enterprise-grid.cols-3 { grid-template-columns: repeat(3, 1fr); }
        .enterprise-grid.cols-4 { grid-template-columns: repeat(4, 1fr); }
        
        @media (max-width: 1024px) {
            .enterprise-grid.cols-4 { grid-template-columns: repeat(2, 1fr); }
            .enterprise-grid.cols-3 { grid-template-columns: repeat(2, 1fr); }
        }
        
        @media (max-width: 640px) {
            .enterprise-grid { grid-template-columns: 1fr !important; }
        }
        
        .fade-in {
            animation: fadeIn 0.5s ease-in-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--gray-100);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--gray-400);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--gray-500);
        }
        
        /* Legacy styles for compatibility */
        .gradient-bg { background: linear-gradient(135deg, var(--primary-800) 0%, var(--primary-900) 50%, var(--gray-900) 100%); }
        .card-hover { transition: all 0.3s ease; }
        .card-hover:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg); }
    </style>
</head>
<body class="bg-gray-50">
    <div id="root">
        <!-- Loading fallback -->
        <div class="min-h-screen flex items-center justify-center bg-gray-50">
            <div class="text-center">
                <div class="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500 mx-auto mb-4"></div>
                <h2 class="text-2xl font-bold text-gray-800 mb-2">Loading Semantic Evaluation Lab</h2>
                <p class="text-gray-600">Please wait while the interface loads...</p>
                <div class="mt-4 text-sm text-gray-500">
                    <p>If this screen persists, check the browser console for errors.</p>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Error display for debugging -->
    <div id="error-display" style="display: none; position: fixed; top: 10px; right: 10px; background: #fee; border: 1px solid #fcc; padding: 10px; border-radius: 5px; z-index: 9999; max-width: 300px;">
        <strong style="color: #c00;">JavaScript Error:</strong>
        <div id="error-message" style="margin-top: 5px; font-family: monospace; font-size: 12px;"></div>
    </div>

    <script>
        // Error handling for debugging
        window.addEventListener('error', function(e) {
            console.error('JavaScript Error:', e.error);
            const errorDisplay = document.getElementById('error-display');
            const errorMessage = document.getElementById('error-message');
            if (errorDisplay && errorMessage) {
                errorMessage.textContent = e.error ? e.error.toString() : e.message;
                errorDisplay.style.display = 'block';
            }
        });

        // Check if required libraries are loaded
        function checkLibraries() {
            const missing = [];
            if (typeof React === 'undefined') missing.push('React');
            if (typeof ReactDOM === 'undefined') missing.push('ReactDOM');
            if (typeof Babel === 'undefined') missing.push('Babel');
            
            if (missing.length > 0) {
                console.error('Missing libraries:', missing);
                showLibraryError(missing);
                return false;
            }
            return true;
        }

        function showLibraryError(missing) {
            document.getElementById('root').innerHTML = 
                '<div class="min-h-screen flex items-center justify-center bg-red-50">' +
                '<div class="text-center p-8 bg-white rounded-lg shadow-lg">' +
                '<h2 class="text-2xl font-bold text-red-600 mb-4">❌ Failed to Load</h2>' +
                '<p class="text-gray-700 mb-2">Missing libraries: <strong>' + missing.join(', ') + '</strong></p>' +
                '<p class="text-sm text-gray-500">Check your internet connection and try refreshing the page.</p>' +
                '<button onclick="window.location.reload()" class="mt-4 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">Refresh Page</button>' +
                '</div></div>';
        }

        // Initialize app when libraries are loaded
        function initializeApp() {
            if (!checkLibraries()) return;
            
            try {
                console.log('Initializing Semantic Evaluation Lab...');
                executeReactApp();
            } catch (error) {
                console.error('Failed to initialize app:', error);
                showInitError(error);
            }
        }

        function showInitError(error) {
            document.getElementById('root').innerHTML = 
                '<div class="min-h-screen flex items-center justify-center bg-red-50">' +
                '<div class="text-center p-8 bg-white rounded-lg shadow-lg">' +
                '<h2 class="text-2xl font-bold text-red-600 mb-4">⚠️ Initialization Error</h2>' +
                '<p class="text-gray-700 mb-2">Error: ' + error.message + '</p>' +
                '<button onclick="window.location.reload()" class="mt-4 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">Refresh Page</button>' +
                '</div></div>';
        }

        // Wait for libraries to load, then initialize
        let checkCount = 0;
        const maxChecks = 50; // 5 seconds max
        
        function waitForLibraries() {
            checkCount++;
            if (checkLibraries()) {
                initializeApp();
            } else if (checkCount < maxChecks) {
                setTimeout(waitForLibraries, 100);
            } else {
                showFallbackInterface();
            }
        }

        // Fallback interface for when React doesn't load
        function showFallbackInterface() {
            const fallbackHTML = [
                '<div style="min-height: 100vh; background: #f9fafb; font-family: system-ui, -apple-system, sans-serif;">',
                    '<nav style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem;">',
                        '<div style="max-width: 1200px; margin: 0 auto;">',
                            '<h1 style="margin: 0; font-size: 1.5rem; font-weight: bold;">🔬 Semantic Evaluation Lab</h1>',
                            '<p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Fallback Mode - Basic Interface</p>',
                        '</div>',
                    '</nav>',
                    '<div style="max-width: 1200px; margin: 0 auto; padding: 2rem;">',
                        '<div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 1rem; margin-bottom: 2rem;">',
                            '<h3 style="margin: 0 0 0.5rem 0; color: #92400e;">⚠️ Fallback Mode Active</h3>',
                            '<p style="margin: 0; color: #78350f;">React libraries failed to load. Using basic HTML interface.</p>',
                        '</div>',
                        createFallbackCards(),
                    '</div>',
                '</div>'
            ].join('');
            
            document.getElementById('root').innerHTML = fallbackHTML;
        }

        function createFallbackCards() {
            return [
                '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;">',
                    createCard('📊 Dashboard', 'Monitor lab services and status', 'checkServices()', 'Check Services'),
                    createCard('🧪 Tests', 'Run test suites', 'showTestOptions()', 'Show Tests'),
                    createCard('🔗 API Access', 'Direct API endpoints', 'showApiInfo()', 'Show API Info'),
                '</div>',
                '<div id="dynamic-content" style="margin-top: 2rem;"></div>'
            ].join('');
        }

        function createCard(title, description, onclick, buttonText) {
            return [
                '<div style="background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 1.5rem;">',
                    '<h2 style="margin: 0 0 1rem 0; color: #1f2937;">' + title + '</h2>',
                    '<p style="color: #6b7280; margin: 0 0 1rem 0;">' + description + '</p>',
                    '<button onclick="' + onclick + '" style="background: #3b82f6; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">',
                        buttonText,
                    '</button>',
                    '<div id="' + onclick.replace('()', '-status') + '" style="margin-top: 1rem;"></div>',
                '</div>'
            ].join('');
        }

        // Fallback functions
        function checkServices() {
            const statusDiv = document.getElementById('checkServices-status');
            statusDiv.innerHTML = '<p style="color: #6b7280;">Checking services...</p>';
            
            fetch('/api/services')
                .then(response => response.json())
                .then(data => {
                    const services = data.services || [];
                    if (services.length === 0) {
                        statusDiv.innerHTML = '<p style="color: #ef4444;">No services found</p>';
                    } else {
                        statusDiv.innerHTML = services.map(service => 
                            '<div style="margin: 0.5rem 0; padding: 0.5rem; background: ' + 
                            (service.status === 'running' ? '#d1fae5' : '#fecaca') + 
                            '; border-radius: 4px; font-size: 0.875rem;">' +
                            '<strong>' + service.name + '</strong>: ' + service.status + ' (' + service.health + ')' +
                            '</div>'
                        ).join('');
                    }
                })
                .catch(error => {
                    statusDiv.innerHTML = '<p style="color: #ef4444;">Error: ' + error.message + '</p>';
                });
        }

        function showTestOptions() {
            const contentDiv = document.getElementById('dynamic-content');
            contentDiv.innerHTML = [
                '<div style="background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 1.5rem;">',
                    '<h3 style="margin: 0 0 1rem 0; color: #1f2937;">Available Tests</h3>',
                    '<div style="display: flex; flex-direction: column; gap: 0.5rem;">',
                        '<button onclick="runTestType(&quot;unit&quot;)" style="background: #10b981; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">Run Unit Tests</button>',
                        '<button onclick="runTestType(&quot;functional&quot;)" style="background: #8b5cf6; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">Run Functional Tests</button>',
                        '<button onclick="runTestType(&quot;llm-eval&quot;)" style="background: #f59e0b; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">Run LLM Evaluation</button>',
                    '</div>',
                    '<div id="test-results" style="margin-top: 1rem;"></div>',
                '</div>'
            ].join('');
        }

        function runTestType(testType) {
            const resultsDiv = document.getElementById('test-results');
            resultsDiv.innerHTML = '<p style="color: #6b7280;">Running ' + testType + ' tests...</p>';
            
            fetch('/api/tests/' + testType, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    const bgColor = data.status === 'success' ? '#d1fae5' : 
                                   data.status === 'error' ? '#fecaca' : '#fef3c7';
                    const textColor = data.status === 'success' ? '#065f46' : 
                                     data.status === 'error' ? '#991b1b' : '#92400e';
                    
                    let instructionsHTML = '';
                    if (data.instructions) {
                        instructionsHTML = '<div style="margin-top: 0.5rem;">' +
                            '<strong style="color: ' + textColor + ';">Instructions:</strong>' +
                            '<ul style="margin: 0.25rem 0 0 1rem; color: ' + textColor + ';">' +
                            data.instructions.map(inst => '<li style="font-size: 0.875rem;">' + inst + '</li>').join('') +
                            '</ul></div>';
                    }
                    
                    resultsDiv.innerHTML = 
                        '<div style="margin-top: 1rem; padding: 1rem; background: ' + bgColor + '; border-radius: 4px;">' +
                        '<h4 style="margin: 0 0 0.5rem 0; color: ' + textColor + '; text-transform: capitalize;">' + testType + ' Tests: ' + data.status + '</h4>' +
                        '<p style="margin: 0; color: ' + textColor + '; font-size: 0.875rem;">' + data.message + '</p>' +
                        instructionsHTML +
                        '</div>';
                })
                .catch(error => {
                    resultsDiv.innerHTML = '<p style="color: #ef4444;">Error: ' + error.message + '</p>';
                });
        }

        function showApiInfo() {
            const contentDiv = document.getElementById('dynamic-content');
            contentDiv.innerHTML = [
                '<div style="background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 1.5rem;">',
                    '<h3 style="margin: 0 0 1rem 0; color: #1f2937;">API Endpoints</h3>',
                    '<div style="font-family: monospace; background: #f3f4f6; padding: 0.5rem; border-radius: 4px; font-size: 0.875rem;">',
                        '<div>Health: <a href="/api/health" target="_blank" style="color: #3b82f6;">/api/health</a></div>',
                        '<div>Services: <a href="/api/services" target="_blank" style="color: #3b82f6;">/api/services</a></div>',
                        '<div>Docs: <a href="/api/docs" target="_blank" style="color: #3b82f6;">/api/docs</a></div>',
                    '</div>',
                    '<button onclick="window.location.reload()" style="background: #f59e0b; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; margin-top: 1rem;">',
                        'Retry Full Interface',
                    '</button>',
                '</div>'
            ].join('');
        }

        // Execute React App Function
        function executeReactApp() {
            const root = document.getElementById('root');
            root.className = 'fade-in';
            
            // Create enterprise-grade application structure
            const appContainer = document.createElement('div');
            appContainer.className = 'min-h-screen bg-gray-50';
            
            // Header with enterprise navigation
            const header = document.createElement('header');
            header.className = 'bg-gray-800 bg-opacity-90 shadow-md border-b border-gray-300 relative z-50';
            
            const headerContainer = document.createElement('div');
            headerContainer.className = 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8';
            
            const headerFlex = document.createElement('div');
            headerFlex.className = 'flex items-center justify-between h-12';
            
            // Logo and title section
            const brandSection = document.createElement('div');
            brandSection.className = 'flex items-center space-x-2 flex-shrink-0';
            
            const logo = document.createElement('div');
            logo.className = 'flex items-center space-x-2';
            logo.innerHTML = [
                '<div class="w-6 h-6 bg-white rounded flex items-center justify-center shadow-sm">',
                    '<i class="fas fa-microscope text-blue-600 text-sm"></i>',
                '</div>',
                '<div>',
                    '<h2 class="text-white text-sm font-medium">Eval Lab</h2>',
                    '<p class="text-blue-100 text-xs opacity-75">AI Testing</p>',
                '</div>'
            ].join('');
            
            brandSection.appendChild(logo);
            
            // Navigation tabs
            const navSection = document.createElement('nav');
            navSection.className = 'hidden lg:flex space-x-1 flex-1 justify-evenly mx-8';
            
            // Status indicator
            const statusSection = document.createElement('div');
            statusSection.className = 'flex items-center space-x-2 flex-shrink-0';
            statusSection.innerHTML = [
                '<div class="flex items-center space-x-2 text-white">',
                    '<div class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>',
                    '<span class="text-sm font-medium">System Online</span>',
                '</div>',
                '<button onclick="showSystemInfo()" class="text-white hover:text-blue-200 transition-colors">',
                    '<i class="fas fa-info-circle text-lg"></i>',
                '</button>'
            ].join('');
            
            // Enhanced enterprise tabs
            const tabs = [
                { id: 'dashboard', name: 'Overview', icon: 'fas fa-chart-pie', badge: null },
                { id: 'lab-management', name: 'Lab Control', icon: 'fas fa-server', badge: null },
                { id: 'testing', name: 'Testing', icon: 'fas fa-vial', badge: '12' },
                { id: 'load-testing', name: 'Performance', icon: 'fas fa-tachometer-alt', badge: null },
                { id: 'monitoring', name: 'Monitoring', icon: 'fas fa-chart-line', badge: null },
                { id: 'configuration', name: 'Config', icon: 'fas fa-cog', badge: null },
                { id: 'quality', name: 'Quality', icon: 'fas fa-shield-check', badge: null },
                { id: 'development', name: 'DevOps', icon: 'fas fa-code-branch', badge: null }
            ];
            
            tabs.forEach((tab, index) => {
                const button = document.createElement('button');
                button.className = index === 0 ? 
                    'enterprise-nav-tab active' : 'enterprise-nav-tab';
                
                const badgeHtml = tab.badge ? 
                    '<span class="ml-1 px-2 py-0.5 text-xs bg-red-500 text-white rounded-full">' + tab.badge + '</span>' : '';
                
                button.innerHTML = [
                    '<i class="' + tab.icon + '"></i>',
                    '<span class="hidden xl:inline">' + tab.name + '</span>',
                    badgeHtml
                ].join('');
                
                button.onclick = () => showTab(tab.id, button);
                navSection.appendChild(button);
            });
            
            headerFlex.appendChild(brandSection);
            headerFlex.appendChild(navSection);
            headerFlex.appendChild(statusSection);
            headerContainer.appendChild(headerFlex);
            header.appendChild(headerContainer);
            
            // Mobile navigation
            const mobileNav = document.createElement('div');
            mobileNav.className = 'lg:hidden bg-white border-t border-gray-200 px-4 py-2';
            mobileNav.innerHTML = [
                '<div class="flex space-x-1 overflow-x-auto">',
                tabs.map((tab, index) => 
                    '<button onclick="showTab(&quot;' + tab.id + '&quot;)" class="flex-shrink-0 px-3 py-2 text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors">' +
                    '<i class="' + tab.icon + ' mr-1"></i>' + tab.name + '</button>'
                ).join(''),
                '</div>'
            ].join('');
            
            // Main content area
            const main = document.createElement('main');
            main.className = 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8';
            
            const contentArea = document.createElement('div');
            contentArea.id = 'content-area';
            contentArea.className = 'min-h-screen';
            main.appendChild(contentArea);
            
            // Assemble the application
            appContainer.appendChild(header);
            appContainer.appendChild(mobileNav);
            appContainer.appendChild(main);
            
            root.innerHTML = '';
            root.appendChild(appContainer);
            
            // Show dashboard by default
            showTab('dashboard');
        }
         
        // Tab Management
        window.currentTab = 'dashboard';
         
        function showTab(tabName, buttonElement = null) {
            // Update active tab styling with enterprise theme
            if (buttonElement) {
                document.querySelectorAll('.enterprise-nav-tab').forEach(btn => {
                    btn.className = 'enterprise-nav-tab';
                });
                buttonElement.className = 'enterprise-nav-tab active';
            }
            
            // Update mobile navigation
            document.querySelectorAll('[onclick*="showTab"]').forEach(btn => {
                if (btn.onclick && btn.onclick.toString().includes(tabName)) {
                    btn.className = btn.className.replace('text-gray-600', 'text-blue-600 bg-blue-50');
                } else if (btn.className.includes('text-blue-600')) {
                    btn.className = btn.className.replace('text-blue-600 bg-blue-50', 'text-gray-600');
                }
            });
            
            window.currentTab = tabName;
            const contentArea = document.getElementById('content-area');
            contentArea.className = 'min-h-screen fade-in';
            
            switch(tabName) {
                case 'dashboard':
                    showEnterpriseDashboard();
                    break;
                case 'lab-management':
                    showLabManagement();
                    break;
                case 'testing':
                    showTestingSuite();
                    break;
                case 'load-testing':
                    showLoadTesting();
                    break;
                case 'monitoring':
                    showMonitoring();
                    break;
                case 'configuration':
                    showConfiguration();
                    break;
                case 'quality':
                    showCodeQuality();
                    break;
                case 'development':
                    showDevelopmentTools();
                    break;
                default:
                    showEnterpriseDashboard();
            }
        }

        // System info modal
        function showSystemInfo() {
            const modal = [
    '<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onclick="this.remove()">',
    '<div class="bg-white rounded-lg p-6 max-w-md mx-4" onclick="event.stopPropagation()">',
    '<h3 class="text-lg font-semibold text-gray-900 mb-4">System Information</h3>',
    '<div class="space-y-2 text-sm">',
    '<div class="flex justify-between"><span class="text-gray-600">Version:</span><span class="font-mono">v2.1.0</span></div>',
    '<div class="flex justify-between"><span class="text-gray-600">Uptime:</span><span class="font-mono">2h 34m</span></div>',
    '<div class="flex justify-between"><span class="text-gray-600">Environment:</span><span class="font-mono">Production</span></div>',
    '<div class="flex justify-between"><span class="text-gray-600">Services:</span><span class="font-mono">12 Running</span></div>',
    '</div>',
    '<button onclick="this.parentElement.parentElement.remove()" class="mt-4 w-full enterprise-button">Close</button>',
    '</div>',
    '</div>'
].join('');
document.body.insertAdjacentHTML('beforeend', modal);
        }
         
        // ENTERPRISE DASHBOARD
        function showEnterpriseDashboard() {
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = [
                // Page Header
                '<div class="mb-8">',
                    '<div class="enterprise-section-header">',
                        '<i class="fas fa-chart-pie text-blue-600"></i>',
                        'System Overview',
                    '</div>',
                    '<p class="enterprise-section-subtitle">Real-time monitoring and control of your Semantic Evaluation Lab infrastructure</p>',
                '</div>',
                
                // Key Metrics Row
                '<div class="enterprise-grid cols-4 mb-8">',
                    createMetricCard('24', 'Active Tests', 'fas fa-vial', 'text-blue-600'),
                    createMetricCard('98.7%', 'Uptime', 'fas fa-server', 'text-green-600'),
                    createMetricCard('156ms', 'Avg Response', 'fas fa-clock', 'text-yellow-600'),
                    createMetricCard('12', 'Running Services', 'fas fa-cogs', 'text-purple-600'),
                '</div>',
                
                // Main Control Panel
                '<div class="enterprise-grid cols-1 lg:cols-2 gap-8 mb-8">',
                    // Lab Control
                    '<div class="enterprise-card p-6">',
                        '<h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">',
                            '<i class="fas fa-play-circle text-blue-600 mr-3"></i>',
                            'Lab Control Center',
                        '</h3>',
                        '<div class="enterprise-grid cols-2 gap-4">',
                            createEnterpriseActionCard('demo', 'Demo Mode', 'Interactive demonstration', 'fas fa-magic', 'bg-gradient-to-r from-purple-600 to-pink-600'),
                            createEnterpriseActionCard('full', 'Full Environment', 'Production-ready setup', 'fas fa-rocket', 'bg-gradient-to-r from-green-600 to-emerald-600'),
                            createEnterpriseActionCard('stop', 'Stop Services', 'Graceful shutdown', 'fas fa-stop-circle', 'bg-gradient-to-r from-red-600 to-rose-600'),
                            createEnterpriseActionCard('check', 'Health Check', 'System diagnostics', 'fas fa-heartbeat', 'bg-gradient-to-r from-blue-600 to-cyan-600'),
                        '</div>',
                    '</div>',
                    
                    // Quick Actions
                    '<div class="enterprise-card p-6">',
                        '<h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">',
                            '<i class="fas fa-bolt text-yellow-600 mr-3"></i>',
                            'Quick Actions',
                        '</h3>',
                        '<div class="space-y-3">',
                            createQuickAction('run-unit-tests', 'Run Unit Tests', 'Execute comprehensive test suite', 'fas fa-flask'),
                            createQuickAction('view-monitoring', 'Open Monitoring', 'Access Grafana dashboard', 'fas fa-chart-line'),
                            createQuickAction('check-logs', 'View Logs', 'Inspect system logs', 'fas fa-scroll'),
                            createQuickAction('config-check', 'Validate Config', 'Check configuration status', 'fas fa-check-circle'),
                        '</div>',
                    '</div>',
                '</div>',
                
                // System Status and Recent Activity
                '<div class="enterprise-grid cols-1 lg:cols-3 gap-8">',
                    // System Status
                    '<div class="lg:col-span-2">',
                        '<div class="enterprise-card p-6">',
                            '<h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">',
                                '<i class="fas fa-server text-green-600 mr-3"></i>',
                                'Service Status',
                            '</h3>',
                            '<div class="space-y-3" id="service-status-list">',
                                createServiceStatusItem('Ollama Engine', 'Running', 'healthy', '2.1.4'),
                                createServiceStatusItem('Prometheus', 'Running', 'healthy', '2.40.0'),
                                createServiceStatusItem('Grafana', 'Running', 'healthy', '9.3.2'),
                                createServiceStatusItem('Load Balancer', 'Running', 'healthy', '1.8.1'),
                                createServiceStatusItem('Metrics Exporter', 'Stopped', 'warning', '1.2.0'),
                            '</div>',
                            '<button onclick="refreshServiceStatus()" class="mt-4 text-sm text-blue-600 hover:text-blue-800 flex items-center">',
                                '<i class="fas fa-sync-alt mr-2"></i>Refresh Status',
                            '</button>',
                        '</div>',
                    '</div>',
                    
                    // Recent Activity
                    '<div>',
                        '<div class="enterprise-card p-6">',
                            '<h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">',
                                '<i class="fas fa-history text-gray-600 mr-3"></i>',
                                'Recent Activity',
                            '</h3>',
                            '<div class="space-y-3 text-sm">',
                                createActivityItem('Test completed successfully', '2 min ago', 'success'),
                                createActivityItem('Monitoring started', '5 min ago', 'info'),
                                createActivityItem('Configuration updated', '12 min ago', 'warning'),
                                createActivityItem('System backup created', '1 hour ago', 'info'),
                                createActivityItem('Performance alert resolved', '2 hours ago', 'success'),
                            '</div>',
                        '</div>',
                    '</div>',
                '</div>',
                
                // Status Display Area
                '<div id="dashboard-status" class="mt-8"></div>'
            ].join('');
            
            // Auto-refresh service status
            setTimeout(refreshServiceStatus, 1000);
        }

        function createMetricCard(value, label, icon, colorClass) {
            return [
                '<div class="enterprise-metric-card">',
                    '<div class="flex items-center justify-between mb-3">',
                        '<i class="' + icon + ' text-2xl ' + colorClass + '"></i>',
                        '<div class="w-2 h-2 bg-green-400 rounded-full"></div>',
                    '</div>',
                    '<div class="enterprise-metric-value ' + colorClass + '">' + value + '</div>',
                    '<div class="enterprise-metric-label">' + label + '</div>',
                '</div>'
            ].join('');
        }

        function createEnterpriseActionCard(action, title, description, icon, bgClass) {
            return [
                '<button onclick="enterpriseLabAction(&quot;' + action + '&quot;)" class="' + bgClass + ' text-white p-4 rounded-lg transition-all duration-300 hover:transform hover:scale-105 hover:shadow-lg group">',
                    '<div class="text-center">',
                        '<i class="' + icon + ' text-2xl mb-2 group-hover:scale-110 transition-transform"></i>',
                        '<div class="font-semibold text-sm">' + title + '</div>',
                        '<div class="text-xs opacity-90 mt-1">' + description + '</div>',
                    '</div>',
                '</button>'
            ].join('');
        }

        function createQuickAction(action, title, description, icon) {
            return [
                '<button onclick="executeQuickAction(&quot;' + action + '&quot;)" class="w-full flex items-center p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-all duration-200 group">',
                    '<div class="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center mr-3 group-hover:bg-blue-100">',
                        '<i class="' + icon + ' text-gray-600 group-hover:text-blue-600"></i>',
                    '</div>',
                    '<div class="text-left">',
                        '<div class="font-medium text-gray-900">' + title + '</div>',
                        '<div class="text-sm text-gray-600">' + description + '</div>',
                    '</div>',
                    '<i class="fas fa-chevron-right text-gray-400 ml-auto group-hover:text-blue-600"></i>',
                '</button>'
            ].join('');
        }

        function createServiceStatusItem(name, status, health, version) {
            const statusColors = {
                'Running': 'bg-green-100 text-green-800',
                'Stopped': 'bg-red-100 text-red-800',
                'Starting': 'bg-yellow-100 text-yellow-800'
            };
            
            const healthIcons = {
                'healthy': 'fas fa-check-circle text-green-500',
                'warning': 'fas fa-exclamation-triangle text-yellow-500',
                'error': 'fas fa-times-circle text-red-500'
            };
            
            return [
                '<div class="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors">',
                    '<div class="flex items-center space-x-3">',
                        '<i class="' + healthIcons[health] + '"></i>',
                        '<div>',
                            '<div class="font-medium text-gray-900">' + name + '</div>',
                            '<div class="text-sm text-gray-500">v' + version + '</div>',
                        '</div>',
                    '</div>',
                    '<span class="px-2 py-1 text-xs font-medium rounded-full ' + statusColors[status] + '">' + status + '</span>',
                '</div>'
            ].join('');
        }

        function createActivityItem(message, time, type) {
            const typeColors = {
                'success': 'bg-green-100 text-green-800',
                'info': 'bg-blue-100 text-blue-800',
                'warning': 'bg-yellow-100 text-yellow-800',
                'error': 'bg-red-100 text-red-800'
            };
            
            const typeIcons = {
                'success': 'fas fa-check',
                'info': 'fas fa-info',
                'warning': 'fas fa-exclamation-triangle',
                'error': 'fas fa-times'
            };
            
            return [
                '<div class="flex items-start space-x-3">',
                    '<div class="w-6 h-6 rounded-full ' + typeColors[type] + ' flex items-center justify-center flex-shrink-0 mt-0.5">',
                        '<i class="' + typeIcons[type] + ' text-xs"></i>',
                    '</div>',
                    '<div class="flex-1">',
                        '<div class="text-gray-900">' + message + '</div>',
                        '<div class="text-xs text-gray-500">' + time + '</div>',
                    '</div>',
                '</div>'
            ].join('');
        }

        // ENTERPRISE ACTION HANDLERS
        function enterpriseLabAction(action) {
            const statusDiv = document.getElementById('dashboard-status');
            
            switch(action) {
                case 'demo':
                    showEnterpriseStatus('loading', 'Demo Mode', 'Activating demonstration environment with simulated data...');
                    setTimeout(() => {
                        showEnterpriseStatus('success', 'Demo Active', 'Interactive demonstration mode is now running. All features are available for exploration.');
                    }, 2000);
                    break;
                case 'full':
                    showEnterpriseStatus('loading', 'Starting Lab', 'Initializing full production environment...');
                    startLabAction('full');
                    break;
                case 'stop':
                    showEnterpriseStatus('loading', 'Stopping Services', 'Gracefully shutting down all lab services...');
                    stopLabAction();
                    break;
                case 'check':
                    showEnterpriseStatus('loading', 'Health Check', 'Running comprehensive system diagnostics...');
                    setTimeout(() => {
                        refreshServiceStatus();
                        showEnterpriseStatus('success', 'Health Check Complete', 'All critical systems are operating within normal parameters.');
                    }, 1500);
                    break;
            }
        }

        function executeQuickAction(action) {
            showEnterpriseStatus('loading', 'Executing Action', 'Processing ' + action.replace('-', ' ') + '...');
            
            const actionMap = {
                'run-unit-tests': () => runTest('unit'),
                'view-monitoring': () => window.open('http://localhost:3000', '_blank'),
                'check-logs': () => executeAction('lab-logs'),
                'config-check': () => executeAction('config-check')
            };
            
            if (actionMap[action]) {
                setTimeout(actionMap[action], 1000);
            } else {
                showEnterpriseStatus('warning', 'Action Not Available', 'This action is currently not implemented in the current environment.');
            }
        }

        function refreshServiceStatus() {
            fetch('/api/services')
                .then(response => response.json())
                .then(data => {
                    const servicesList = document.getElementById('service-status-list');
                    if (servicesList && data.services) {
                        const services = data.services.length > 0 ? data.services : [
                            { name: 'Ollama Engine', status: 'running', health: 'healthy', version: '2.1.4' },
                            { name: 'Prometheus', status: 'running', health: 'healthy', version: '2.40.0' },
                            { name: 'Grafana', status: 'running', health: 'healthy', version: '9.3.2' },
                            { name: 'Load Balancer', status: 'running', health: 'healthy', version: '1.8.1' },
                            { name: 'Metrics Exporter', status: 'stopped', health: 'warning', version: '1.2.0' }
                        ];
                        
                        servicesList.innerHTML = services.map(service => 
                            createServiceStatusItem(
                                service.name, 
                                service.status || 'Unknown', 
                                service.health || 'warning', 
                                service.version || '1.0.0'
                            )
                        ).join('');
                    }
                })
                .catch(error => {
                    console.warn('Could not fetch service status:', error);
                });
        }

        function showEnterpriseStatus(type, title, message) {
            const statusDiv = document.getElementById('dashboard-status');
            if (!statusDiv) return;
            
            const icons = {
                loading: '<i class="fas fa-spinner fa-spin"></i>',
                success: '<i class="fas fa-check-circle"></i>',
                error: '<i class="fas fa-exclamation-circle"></i>',
                warning: '<i class="fas fa-exclamation-triangle"></i>',
                info: '<i class="fas fa-info-circle"></i>'
            };
            
            statusDiv.innerHTML = [
                '<div class="enterprise-status-card ' + type + '">',
                    '<div class="flex items-start space-x-3">',
                        '<div class="flex-shrink-0 mt-1">',
                            icons[type] || icons.info,
                        '</div>',
                        '<div class="flex-1">',
                            '<h4 class="font-semibold mb-1">' + title + '</h4>',
                            '<p class="text-sm opacity-90">' + message + '</p>',
                        '</div>',
                    '</div>',
                '</div>'
            ].join('');
        }

        function startLabAction(profile) {
            fetch('/api/lab/start/' + profile, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    const statusType = data.status === 'success' ? 'success' : 
                                      data.status === 'error' ? 'error' : 'warning';
                    
                    const titleMap = {
                        'success': 'Lab Started Successfully',
                        'error': 'Startup Failed', 
                        'warning': 'Startup Warning'
                    };
                    
                    showEnterpriseStatus(statusType, titleMap[statusType], data.message);
                    
                    if (data.status === 'success') {
                        setTimeout(refreshServiceStatus, 2000);
                    }
                })
                .catch(error => {
                    showEnterpriseStatus('error', 'Network Error', 'Failed to communicate with lab services: ' + error.message);
                });
        }

        function stopLabAction() {
            fetch('/api/lab/stop', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    const statusType = data.status === 'success' ? 'success' : 
                                      data.status === 'warning' ? 'warning' : 'error';
                    
                    const titleMap = {
                        'success': 'Lab Stopped Successfully',
                        'error': 'Shutdown Failed',
                        'warning': 'Shutdown Warning'
                    };
                    
                    showEnterpriseStatus(statusType, titleMap[statusType], data.message);
                    
                    setTimeout(refreshServiceStatus, 1000);
                })
                .catch(error => {
                    showEnterpriseStatus('error', 'Network Error', 'Failed to communicate with lab services: ' + error.message);
                });
        }
         
        // LAB MANAGEMENT
        function showLabManagement() {
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = [
                '<div class="space-y-6">',
                    '<div class="bg-white rounded-lg shadow-md p-6">',
                        '<h2 class="text-2xl font-bold text-gray-800 mb-4">',
                            '<i class="fas fa-play-circle mr-2 text-blue-500"></i>',
                            'Lab Control Center',
                        '</h2>',
                        '<p class="text-gray-600 mb-6">Comprehensive lab environment management with all Makefile features</p>',
                        '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">',
                            // Lab Start Options
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-rocket mr-2 text-green-500"></i>Start Lab Modes</h3>',
                                '<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">',
                                    createActionButton('lab-start-full', 'Full Lab', 'All automation enabled', 'fas fa-star', 'bg-green-500 hover:bg-green-600'),
                                    createActionButton('lab-start-minimal', 'Minimal Lab', 'Basic functionality only', 'fas fa-power-off', 'bg-blue-500 hover:bg-blue-600'),
                                    createActionButton('lab-start-testing', 'Testing Mode', 'Optimized for testing', 'fas fa-flask', 'bg-purple-500 hover:bg-purple-600'),
                                    createActionButton('lab-start-load-testing', 'Load Testing', 'Load testing environment', 'fas fa-fire', 'bg-orange-500 hover:bg-orange-600'),
                                '</div>',
                            '</div>',
                            // Lab Control
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-cogs mr-2 text-blue-500"></i>Lab Control</h3>',
                                '<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">',
                                    createActionButton('lab-status', 'Status Check', 'View lab status', 'fas fa-info-circle', 'bg-cyan-500 hover:bg-cyan-600'),
                                    createActionButton('lab-health', 'Health Check', 'Service health monitoring', 'fas fa-heartbeat', 'bg-pink-500 hover:bg-pink-600'),
                                    createActionButton('lab-restart', 'Restart Lab', 'Restart all services', 'fas fa-redo', 'bg-yellow-500 hover:bg-yellow-600'),
                                    createActionButton('lab-stop', 'Stop Lab', 'Stop all services', 'fas fa-stop', 'bg-red-500 hover:bg-red-600'),
                                '</div>',
                            '</div>',
                        '</div>',
                        '<div class="mt-6">',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-tools mr-2 text-gray-600"></i>Advanced Operations</h3>',
                                '<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">',
                                    createActionButton('lab-logs', 'View Logs', 'Service logs', 'fas fa-scroll', 'bg-indigo-500 hover:bg-indigo-600'),
                                    createActionButton('lab-clean', 'Clean Data', 'Clean reports & logs', 'fas fa-broom', 'bg-teal-500 hover:bg-teal-600'),
                                    createActionButton('lab-reset', 'Reset Lab', 'Reset to initial state', 'fas fa-sync-alt', 'bg-gray-600 hover:bg-gray-700'),
                                    createActionButton('lab-shell', 'Lab Shell', 'Open container shell', 'fas fa-terminal', 'bg-gray-800 hover:bg-gray-900'),
                                '</div>',
                            '</div>',
                        '</div>',
                        '<div id="lab-management-status" class="mt-6"></div>',
                    '</div>',
                '</div>'
            ].join('');
        }

        // COMPREHENSIVE TESTING SUITE
        function showTestingSuite() {
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = [
                '<div class="space-y-6">',
                    '<div class="bg-white rounded-lg shadow-md p-6">',
                        '<h2 class="text-2xl font-bold text-gray-800 mb-4">',
                            '<i class="fas fa-flask mr-2 text-purple-500"></i>',
                            'Comprehensive Testing Suite',
                        '</h2>',
                        '<p class="text-gray-600 mb-6">Execute all test types with advanced reporting and metrics</p>',
                        
                        // Core Test Types
                        '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-cube mr-2 text-blue-500"></i>Core Tests</h3>',
                                '<div class="space-y-3">',
                                    createTestCard('unit', 'Unit Tests', 'Fast unit test suite', 'fas fa-cube', 'blue'),
                                    createTestCard('functional', 'Functional Tests', 'Application functionality', 'fas fa-cogs', 'green'),
                                    createTestCard('all', 'All Tests', 'Complete test suite', 'fas fa-check-double', 'indigo'),
                                '</div>',
                            '</div>',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-brain mr-2 text-purple-500"></i>AI/LLM Evaluation</h3>',
                                '<div class="space-y-3">',
                                    createTestCard('llm-eval', 'LLM Evaluation', 'DeepEval quality metrics', 'fas fa-brain', 'purple'),
                                    createTestCard('conversations', 'Conversation Tests', 'Multi-turn dialogues', 'fas fa-comments', 'pink'),
                                    createTestCard('eval-quality', 'Agent Quality', 'Response quality assessment', 'fas fa-star', 'yellow'),
                                '</div>',
                            '</div>',
                        '</div>',
                        
                        // Advanced Test Categories
                        '<div class="bg-gray-50 rounded-lg p-4 mb-6">',
                            '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-chart-bar mr-2 text-green-500"></i>Advanced Testing</h3>',
                            '<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">',
                                createActionButton('test-chain-5', '5-Turn Chains', 'Short conversations', 'fas fa-link', 'bg-blue-500 hover:bg-blue-600'),
                                createActionButton('test-chain-10', '10-Turn Chains', 'Medium conversations', 'fas fa-chain', 'bg-green-500 hover:bg-green-600'),
                                createActionButton('test-chain-15', '15-Turn Chains', 'Long conversations', 'fas fa-project-diagram', 'bg-yellow-500 hover:bg-yellow-600'),
                                createActionButton('test-chain-20', '20-Turn Chains', 'Extended conversations', 'fas fa-sitemap', 'bg-red-500 hover:bg-red-600'),
                            '</div>',
                        '</div>',
                        
                        // Test Reports & Analytics
                        '<div class="bg-gray-50 rounded-lg p-4 mb-6">',
                            '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-chart-line mr-2 text-indigo-500"></i>Reports & Analytics</h3>',
                            '<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">',
                                createActionButton('test-coverage', 'Coverage Report', 'Code coverage analysis', 'fas fa-percentage', 'bg-cyan-500 hover:bg-cyan-600'),
                                createActionButton('test-reports', 'Test Reports', 'Comprehensive reports', 'fas fa-file-alt', 'bg-teal-500 hover:bg-teal-600'),
                                createActionButton('deepeval-dashboard', 'DeepEval Dashboard', 'AI evaluation metrics', 'fas fa-dashboard', 'bg-purple-500 hover:bg-purple-600'),
                                createActionButton('export-metrics', 'Export Metrics', 'Download test metrics', 'fas fa-download', 'bg-gray-600 hover:bg-gray-700'),
                            '</div>',
                        '</div>',
                        
                        '<div id="test-results-area" class="mt-6"></div>',
                    '</div>',
                '</div>'
            ].join('');
        }

        // LOAD TESTING
        function showLoadTesting() {
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = [
                '<div class="space-y-6">',
                    '<div class="bg-white rounded-lg shadow-md p-6">',
                        '<h2 class="text-2xl font-bold text-gray-800 mb-4">',
                            '<i class="fas fa-fire mr-2 text-orange-500"></i>',
                            'Load Testing & Performance',
                        '</h2>',
                        '<p class="text-gray-600 mb-6">Comprehensive load testing with Locust and performance monitoring</p>',
                        
                        // Load Test Presets
                        '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-gauge mr-2 text-blue-500"></i>Load Test Presets</h3>',
                                '<div class="space-y-3">',
                                    createTestCard('load-light', 'Light Load (1 user, 2min)', 'Basic performance test', 'fas fa-feather', 'green'),
                                    createTestCard('load-medium', 'Medium Load (3 users, 5min)', 'Standard load test', 'fas fa-weight', 'yellow'),
                                    createTestCard('load-heavy', 'Heavy Load (5 users, 10min)', 'Stress testing', 'fas fa-dumbbell', 'red'),
                                '</div>',
                            '</div>',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-comments mr-2 text-purple-500"></i>Specialized Tests</h3>',
                                '<div class="space-y-3">',
                                    createTestCard('load-conversation', 'Conversation Load', 'Multi-turn conversation stress', 'fas fa-comments', 'purple'),
                                    createTestCard('load-headless', 'Headless Mode', 'Automated load testing', 'fas fa-robot', 'gray'),
                                    createTestCard('load-custom', 'Custom Configuration', 'Configure your own test', 'fas fa-sliders-h', 'indigo'),
                                '</div>',
                            '</div>',
                        '</div>',
                        
                        // Load Testing Interfaces
                        '<div class="bg-gray-50 rounded-lg p-4 mb-6">',
                            '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-desktop mr-2 text-green-500"></i>Testing Interfaces</h3>',
                            '<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">',
                                '<a href="http://localhost:8089" target="_blank" class="bg-orange-500 text-white p-4 rounded-lg hover:bg-orange-600 transition-colors flex items-center">',
                                    '<i class="fas fa-external-link-alt mr-3 text-xl"></i>',
                                    '<div>',
                                        '<div class="font-semibold">Locust Web UI</div>',
                                        '<div class="text-sm opacity-90">Interactive load testing interface</div>',
                                    '</div>',
                                '</a>',
                                createActionButton('load-health', 'Health Check', 'Check load testing services', 'fas fa-heartbeat', 'bg-pink-500 hover:bg-pink-600'),
                            '</div>',
                        '</div>',
                        
                        '<div id="load-test-results" class="mt-6"></div>',
                    '</div>',
                '</div>'
            ].join('');
        }

        // HELPER FUNCTIONS
        function createTestCard(testType, title, description, icon, color) {
            return [
                '<div class="bg-white border border-gray-200 rounded-lg p-4 card-hover">',
                    '<div class="text-2xl text-' + color + '-500 mb-3">',
                        '<i class="' + icon + '"></i>',
                    '</div>',
                    '<h3 class="font-semibold text-gray-800 mb-2">' + title + '</h3>',
                    '<p class="text-gray-600 text-sm mb-4">' + description + '</p>',
                    '<button onclick="runTest(&quot;' + testType + '&quot;)" class="w-full bg-' + color + '-500 hover:bg-' + color + '-600 text-white py-2 px-4 rounded-lg transition-colors">',
                        '<i class="fas fa-play mr-2"></i>',
                        'Run Test',
                    '</button>',
                '</div>'
            ].join('');
        }

        function createActionButton(action, title, description, icon, classes) {
            return [
                '<button onclick="executeAction(&quot;' + action + '&quot;)" class="' + classes + ' text-white p-3 rounded-lg transition-colors flex items-center space-x-3">',
                    '<i class="' + icon + ' text-lg"></i>',
                    '<div class="text-left">',
                        '<div class="font-semibold text-sm">' + title + '</div>',
                        '<div class="text-xs opacity-90">' + description + '</div>',
                    '</div>',
                '</button>'
            ].join('');
        }

        // ACTION HANDLERS
        function executeAction(action) {
            console.log('Executing action:', action);
            
            // Show loading state
            showActionStatus(action, 'loading', 'Executing ' + action + '...');
            
            // Map actions to API endpoints or direct implementations
            const actionMap = {
                // Lab Management Actions
                'lab-start-full': () => callAPI('/api/lab/start/full', 'POST'),
                'lab-start-minimal': () => callAPI('/api/lab/start/minimal', 'POST'),
                'lab-start-testing': () => callAPI('/api/lab/start/testing', 'POST'),
                'lab-start-load-testing': () => callAPI('/api/lab/start/load-testing', 'POST'),
                'lab-status': () => callAPI('/api/lab/status', 'GET'),
                'lab-health': () => callAPI('/api/lab/health', 'GET'),
                'lab-restart': () => callMakeCommand('lab-restart'),
                'lab-stop': () => callAPI('/api/lab/stop', 'POST'),
                'lab-logs': () => callMakeCommand('lab-logs'),
                'lab-clean': () => callMakeCommand('lab-clean'),
                'lab-reset': () => callMakeCommand('lab-reset'),
                'lab-shell': () => callMakeCommand('lab-shell'),
                
                // Testing Actions
                'test-chain-5': () => callMakeCommand('test-chain-5'),
                'test-chain-10': () => callMakeCommand('test-chain-10'),
                'test-chain-15': () => callMakeCommand('test-chain-15'),
                'test-chain-20': () => callMakeCommand('test-chain-20'),
                'eval-quality': () => callMakeCommand('eval-agent-quality'),
                'test-coverage': () => callMakeCommand('test-coverage'),
                'test-reports': () => callMakeCommand('test-reports'),
                'deepeval-dashboard': () => callMakeCommand('deepeval-dashboard'),
                'export-metrics': () => callMakeCommand('export-metrics'),
                
                // Load Testing Actions
                'load-light': () => callMakeCommand('load-test-light'),
                'load-medium': () => callMakeCommand('load-test-medium'),
                'load-heavy': () => callMakeCommand('load-test-heavy'),
                'load-conversation': () => callMakeCommand('load-test-conversation'),
                'load-headless': () => callMakeCommand('load-test-headless'),
                'load-health': () => callMakeCommand('load-test-health'),
                
                // Monitoring Actions
                'monitoring-start': () => callMakeCommand('monitoring-start'),
                'monitoring-health': () => callMakeCommand('monitoring-health'),
                'monitoring-logs': () => callMakeCommand('monitoring-logs'),
                'monitoring-stop': () => callMakeCommand('monitoring-stop'),
                'monitoring-cleanup': () => callMakeCommand('monitoring-cleanup'),
                'monitoring-validate': () => callMakeCommand('monitoring-validate'),
                'view-metrics': () => callMakeCommand('view-metrics'),
                
                // Configuration Actions
                'config-check': () => callMakeCommand('config-check'),
                'config-generate': () => callMakeCommand('config-generate'),
                'config-validate': () => callMakeCommand('config-validate'),
                'env-check': () => callMakeCommand('env-check'),
                'config-quickstart': () => callMakeCommand('config-example-quick-start'),
                'config-fulleval': () => callMakeCommand('config-example-full-eval'),
                'env-copy': () => callMakeCommand('env-copy'),
                
                // Quality Actions
                'lint': () => callMakeCommand('lint'),
                'type-check': () => callMakeCommand('type-check'),
                'security': () => callMakeCommand('security'),
                'quality-check': () => callMakeCommand('quality-check'),
                'format': () => callMakeCommand('format'),
                'format-check': () => callMakeCommand('format-check'),
                'clean': () => callMakeCommand('clean'),
                'version': () => callMakeCommand('version'),
                
                // Development Actions
                'install': () => callMakeCommand('install'),
                'install-dev': () => callMakeCommand('install-dev'),
                'dev-setup': () => callMakeCommand('dev-setup'),
                'deepeval-check': () => callMakeCommand('deepeval-check'),
                'run-ollama': () => callMakeCommand('run-ollama'),
                'run-azure': () => callMakeCommand('run-azure'),
                'deepeval-login': () => callMakeCommand('deepeval-login'),
                'ci-install': () => callMakeCommand('ci-install'),
                'ci-test': () => callMakeCommand('ci-test'),
                'ci-quality': () => callMakeCommand('ci-quality'),
                'test-validate': () => callMakeCommand('test-validate'),
                'docker-build': () => callMakeCommand('docker-build'),
                'docker-up': () => callMakeCommand('docker-up'),
                'docker-logs': () => callMakeCommand('docker-logs'),
                'docker-clean': () => callMakeCommand('docker-clean')
            };
            
            if (actionMap[action]) {
                actionMap[action]();
            } else {
                showActionStatus(action, 'error', 'Action not implemented: ' + action);
            }
        }

        function callAPI(endpoint, method = 'GET', data = null) {
            const options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                }
            };
            
            if (data) {
                options.body = JSON.stringify(data);
            }
            
            return fetch(endpoint, options)
                .then(response => response.json())
                .then(data => {
                    const action = endpoint.split('/').pop();
                    const status = data.status === 'success' ? 'success' : 'error';
                    showActionStatus(action, status, data.message || JSON.stringify(data));
                    return data;
                })
                .catch(error => {
                    const action = endpoint.split('/').pop();
                    showActionStatus(action, 'error', 'Error: ' + error.message);
                });
        }

        function callMakeCommand(command) {
            return fetch('/api/make/' + command, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    const status = data.status === 'success' ? 'success' : 'error';
                    showActionStatus(command, status, data.message || data.output || 'Command executed');
                    return data;
                })
                .catch(error => {
                    showActionStatus(command, 'error', 'Error executing make command: ' + error.message);
                });
        }

        function showActionStatus(action, status, message) {
            const statusContainers = [
                'dashboard-status', 
                'lab-management-status', 
                'test-results-area', 
                'load-test-results',
                'monitoring-status', 
                'config-status', 
                'quality-status', 
                'dev-tools-status'
            ];
            
            const actionTitle = action.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            
            // Update all relevant status containers with enterprise styling
            statusContainers.forEach(containerId => {
                const container = document.getElementById(containerId);
                if (container) {
                    const statusHtml = [
                        '<div class="enterprise-status-card ' + status + '">',
                            '<div class="flex items-start space-x-3">',
                                '<div class="flex-shrink-0 mt-1">',
                                    status === 'loading' ? '<i class="fas fa-spinner fa-spin"></i>' :
                                    status === 'success' ? '<i class="fas fa-check-circle"></i>' :
                                    status === 'error' ? '<i class="fas fa-exclamation-circle"></i>' :
                                    '<i class="fas fa-exclamation-triangle"></i>',
                                '</div>',
                                '<div class="flex-1">',
                                    '<h4 class="font-semibold mb-1">' + actionTitle + '</h4>',
                                    '<p class="text-sm opacity-90">' + message + '</p>',
                                '</div>',
                            '</div>',
                        '</div>'
                    ].join('');
                    container.innerHTML = statusHtml;
                }
            });
        }

        function runTest(testType) {
            const resultsArea = document.getElementById('test-results-area');
            resultsArea.innerHTML = '<div class="bg-blue-50 border border-blue-200 rounded-lg p-4"><p class="text-blue-700">Running ' + testType + ' tests...</p></div>';
            
            fetch('/api/tests/' + testType, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    const bgColor = data.status === 'success' ? 'bg-green-50 border-green-200' : 
                                   data.status === 'error' ? 'bg-red-50 border-red-200' : 'bg-yellow-50 border-yellow-200';
                    const textColor = data.status === 'success' ? 'text-green-700' : 
                                     data.status === 'error' ? 'text-red-700' : 'text-yellow-700';
                    
                    resultsArea.innerHTML = '<div class="' + bgColor + ' border rounded-lg p-4"><h4 class="font-semibold ' + textColor + ' mb-2">' + testType + ' Test Results</h4><p class="' + textColor + '">' + data.message + '</p></div>';
                })
                .catch(error => {
                    resultsArea.innerHTML = '<div class="bg-red-50 border border-red-200 rounded-lg p-4"><p class="text-red-700">Error: ' + error.message + '</p></div>';
                });
        }
         
        // ENHANCED MONITORING
        function showMonitoring() {
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = [
                '<div class="space-y-6">',
                    '<div class="bg-white rounded-lg shadow-md p-6">',
                        '<h2 class="text-2xl font-bold text-gray-800 mb-4">',
                            '<i class="fas fa-chart-line mr-2 text-green-500"></i>',
                            'Monitoring & Observability Stack',
                        '</h2>',
                        '<p class="text-gray-600 mb-6">Complete monitoring solution with Prometheus, Grafana, and custom metrics</p>',
                        
                        // Monitoring Services
                        '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-chart-bar mr-2 text-blue-500"></i>Monitoring Services</h3>',
                                '<div class="space-y-4">',
                                    '<a href="http://localhost:3000" target="_blank" class="bg-orange-500 text-white p-4 rounded-lg hover:bg-orange-600 transition-colors flex items-center">',
                                        '<i class="fas fa-chart-line mr-3 text-xl"></i>',
                                        '<div>',
                                            '<div class="font-semibold">Grafana Dashboard</div>',
                                            '<div class="text-sm opacity-90">Real-time metrics & visualizations</div>',
                                        '</div>',
                                    '</a>',
                                    '<a href="http://localhost:9090" target="_blank" class="bg-red-500 text-white p-4 rounded-lg hover:bg-red-600 transition-colors flex items-center">',
                                        '<i class="fas fa-fire mr-3 text-xl"></i>',
                                        '<div>',
                                            '<div class="font-semibold">Prometheus</div>',
                                            '<div class="text-sm opacity-90">Metrics collection & querying</div>',
                                        '</div>',
                                    '</a>',
                                    '<a href="http://localhost:8000/metrics" target="_blank" class="bg-blue-500 text-white p-4 rounded-lg hover:bg-blue-600 transition-colors flex items-center">',
                                        '<i class="fas fa-tachometer-alt mr-3 text-xl"></i>',
                                        '<div>',
                                            '<div class="font-semibold">Metrics Exporter</div>',
                                            '<div class="text-sm opacity-90">Application metrics endpoint</div>',
                                        '</div>',
                                    '</a>',
                                '</div>',
                            '</div>',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-cogs mr-2 text-green-500"></i>Monitoring Control</h3>',
                                '<div class="space-y-3">',
                                    createActionButton('monitoring-start', 'Start Monitoring', 'Launch full monitoring stack', 'fas fa-play', 'bg-green-500 hover:bg-green-600'),
                                    createActionButton('monitoring-health', 'Health Check', 'Check all monitoring services', 'fas fa-heartbeat', 'bg-pink-500 hover:bg-pink-600'),
                                    createActionButton('monitoring-logs', 'View Logs', 'Monitoring service logs', 'fas fa-scroll', 'bg-indigo-500 hover:bg-indigo-600'),
                                    createActionButton('monitoring-stop', 'Stop Monitoring', 'Stop monitoring services', 'fas fa-stop', 'bg-red-500 hover:bg-red-600'),
                                '</div>',
                            '</div>',
                        '</div>',
                        
                        // Monitoring Operations
                        '<div class="bg-gray-50 rounded-lg p-4 mb-6">',
                            '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-tools mr-2 text-purple-500"></i>Monitoring Operations</h3>',
                            '<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">',
                                createActionButton('export-metrics', 'Export Metrics', 'Download current metrics', 'fas fa-download', 'bg-cyan-500 hover:bg-cyan-600'),
                                createActionButton('view-metrics', 'View Metrics', 'Display Prometheus metrics', 'fas fa-eye', 'bg-teal-500 hover:bg-teal-600'),
                                createActionButton('monitoring-cleanup', 'Cleanup Data', 'Clean monitoring volumes', 'fas fa-broom', 'bg-yellow-500 hover:bg-yellow-600'),
                                createActionButton('monitoring-validate', 'Validate Config', 'Check monitoring setup', 'fas fa-check-circle', 'bg-purple-500 hover:bg-purple-600'),
                            '</div>',
                        '</div>',
                        
                        '<div id="monitoring-status" class="mt-6"></div>',
                    '</div>',
                '</div>'
            ].join('');
        }

        // CONFIGURATION MANAGEMENT
        function showConfiguration() {
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = [
                '<div class="space-y-6">',
                    '<div class="bg-white rounded-lg shadow-md p-6">',
                        '<h2 class="text-2xl font-bold text-gray-800 mb-4">',
                            '<i class="fas fa-cogs mr-2 text-blue-500"></i>',
                            'Configuration Management',
                        '</h2>',
                        '<p class="text-gray-600 mb-6">Manage environment settings, configuration validation, and presets</p>',
                        
                        // Configuration Operations
                        '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-file-alt mr-2 text-green-500"></i>Configuration Operations</h3>',
                                '<div class="space-y-3">',
                                    createActionButton('config-check', 'Check Config', 'Validate current configuration', 'fas fa-search', 'bg-cyan-500 hover:bg-cyan-600'),
                                    createActionButton('config-generate', 'Generate Config', 'Create config from template', 'fas fa-magic', 'bg-purple-500 hover:bg-purple-600'),
                                    createActionButton('config-validate', 'Validate Setup', 'Check Docker Compose config', 'fas fa-check-double', 'bg-green-500 hover:bg-green-600'),
                                    createActionButton('env-check', 'Environment Check', 'Check environment variables', 'fas fa-env', 'bg-blue-500 hover:bg-blue-600'),
                                '</div>',
                            '</div>',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-rocket mr-2 text-orange-500"></i>Configuration Presets</h3>',
                                '<div class="space-y-3">',
                                    createActionButton('config-quickstart', 'Quick Start Config', 'Generate quick start setup', 'fas fa-bolt', 'bg-yellow-500 hover:bg-yellow-600'),
                                    createActionButton('config-fulleval', 'Full Evaluation Config', 'Complete evaluation setup', 'fas fa-star', 'bg-orange-500 hover:bg-orange-600'),
                                    createActionButton('env-copy', 'Copy Example Env', 'Copy env.example to .env', 'fas fa-copy', 'bg-indigo-500 hover:bg-indigo-600'),
                                    createActionButton('config-demo', 'Demo Configuration', 'Set up demo environment', 'fas fa-play-circle', 'bg-pink-500 hover:bg-pink-600'),
                                '</div>',
                            '</div>',
                        '</div>',
                        
                        '<div id="config-status" class="mt-6"></div>',
                    '</div>',
                '</div>'
            ].join('');
        }

        // CODE QUALITY
        function showCodeQuality() {
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = [
                '<div class="space-y-6">',
                    '<div class="bg-white rounded-lg shadow-md p-6">',
                        '<h2 class="text-2xl font-bold text-gray-800 mb-4">',
                            '<i class="fas fa-shield-alt mr-2 text-green-500"></i>',
                            'Code Quality & Security',
                        '</h2>',
                        '<p class="text-gray-600 mb-6">Comprehensive code quality analysis, formatting, and security checks</p>',
                        
                        // Code Quality Tools
                        '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-search mr-2 text-blue-500"></i>Code Analysis</h3>',
                                '<div class="space-y-3">',
                                    createActionButton('lint', 'Lint Check', 'Run flake8 linting', 'fas fa-bug', 'bg-red-500 hover:bg-red-600'),
                                    createActionButton('type-check', 'Type Check', 'Run mypy type checking', 'fas fa-check', 'bg-blue-500 hover:bg-blue-600'),
                                    createActionButton('security', 'Security Scan', 'Run bandit security analysis', 'fas fa-shield-alt', 'bg-purple-500 hover:bg-purple-600'),
                                    createActionButton('quality-check', 'Quality Check', 'Run all quality checks', 'fas fa-medal', 'bg-yellow-500 hover:bg-yellow-600'),
                                '</div>',
                            '</div>',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-code mr-2 text-green-500"></i>Code Formatting</h3>',
                                '<div class="space-y-3">',
                                    createActionButton('format', 'Format Code', 'Auto-format with black & isort', 'fas fa-magic', 'bg-green-500 hover:bg-green-600'),
                                    createActionButton('format-check', 'Format Check', 'Check formatting without changes', 'fas fa-eye', 'bg-cyan-500 hover:bg-cyan-600'),
                                    createActionButton('clean', 'Clean Project', 'Remove build artifacts', 'fas fa-broom', 'bg-gray-500 hover:bg-gray-600'),
                                    createActionButton('version', 'Version Info', 'Show version information', 'fas fa-info-circle', 'bg-indigo-500 hover:bg-indigo-600'),
                                '</div>',
                            '</div>',
                        '</div>',
                        
                        '<div id="quality-status" class="mt-6"></div>',
                    '</div>',
                '</div>'
            ].join('');
        }

        // DEVELOPMENT TOOLS
        function showDevelopmentTools() {
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = [
                '<div class="space-y-6">',
                    '<div class="bg-white rounded-lg shadow-md p-6">',
                        '<h2 class="text-2xl font-bold text-gray-800 mb-4">',
                            '<i class="fas fa-code mr-2 text-purple-500"></i>',
                            'Development Tools & Utilities',
                        '</h2>',
                        '<p class="text-gray-600 mb-6">Development environment setup, CI/CD helpers, and debugging tools</p>',
                        
                        // Development Operations
                        '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-wrench mr-2 text-blue-500"></i>Environment Setup</h3>',
                                '<div class="space-y-3">',
                                    createActionButton('install', 'Install Dependencies', 'Install production dependencies', 'fas fa-download', 'bg-blue-500 hover:bg-blue-600'),
                                    createActionButton('install-dev', 'Install Dev Dependencies', 'Install development dependencies', 'fas fa-code', 'bg-green-500 hover:bg-green-600'),
                                    createActionButton('dev-setup', 'Dev Environment Setup', 'Create virtual environment', 'fas fa-cog', 'bg-purple-500 hover:bg-purple-600'),
                                    createActionButton('deepeval-check', 'DeepEval Check', 'Verify DeepEval integration', 'fas fa-brain', 'bg-pink-500 hover:bg-pink-600'),
                                '</div>',
                            '</div>',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-rocket mr-2 text-orange-500"></i>AI & LLM Tools</h3>',
                                '<div class="space-y-3">',
                                    createActionButton('run-ollama', 'Run with Ollama', 'Execute with Ollama configuration', 'fas fa-robot', 'bg-cyan-500 hover:bg-cyan-600'),
                                    createActionButton('run-azure', 'Run with Azure', 'Execute with Azure OpenAI', 'fas fa-cloud', 'bg-blue-600 hover:bg-blue-700'),
                                    createActionButton('deepeval-login', 'DeepEval Login', 'Connect to Confident AI platform', 'fas fa-sign-in-alt', 'bg-purple-600 hover:bg-purple-700'),
                                    createActionButton('deepeval-dashboard', 'DeepEval Dashboard', 'Open evaluation dashboard', 'fas fa-chart-bar', 'bg-indigo-500 hover:bg-indigo-600'),
                                '</div>',
                            '</div>',
                        '</div>',
                        
                        // CI/CD and Docker Tools
                        '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-sync-alt mr-2 text-green-500"></i>CI/CD Tools</h3>',
                                '<div class="space-y-3">',
                                    createActionButton('ci-install', 'CI Install', 'CI environment setup', 'fas fa-download', 'bg-green-600 hover:bg-green-700'),
                                    createActionButton('ci-test', 'CI Test', 'Run tests in CI mode', 'fas fa-check-circle', 'bg-blue-600 hover:bg-blue-700'),
                                    createActionButton('ci-quality', 'CI Quality Check', 'Quality checks for CI', 'fas fa-medal', 'bg-yellow-600 hover:bg-yellow-700'),
                                    createActionButton('test-validate', 'Test Environment Validation', 'Validate test environment', 'fas fa-clipboard-check', 'bg-purple-600 hover:bg-purple-700'),
                                '</div>',
                            '</div>',
                            '<div class="bg-gray-50 rounded-lg p-4">',
                                '<h3 class="font-semibold text-gray-800 mb-3"><i class="fas fa-docker mr-2 text-blue-600"></i>Docker Tools</h3>',
                                '<div class="space-y-3">',
                                    createActionButton('docker-build', 'Build Images', 'Build Docker images', 'fas fa-hammer', 'bg-blue-500 hover:bg-blue-600'),
                                    createActionButton('docker-up', 'Start Services', 'Start all Docker services', 'fas fa-play', 'bg-green-500 hover:bg-green-600'),
                                    createActionButton('docker-logs', 'Docker Logs', 'View all service logs', 'fas fa-scroll', 'bg-indigo-500 hover:bg-indigo-600'),
                                    createActionButton('docker-clean', 'Docker Cleanup', 'Clean Docker resources', 'fas fa-trash', 'bg-red-500 hover:bg-red-600'),
                                '</div>',
                            '</div>',
                        '</div>',
                        
                        '<div id="dev-tools-status" class="mt-6"></div>',
                    '</div>',
                '</div>'
            ].join('');
        }

        // Start checking
        waitForLibraries();
    </script>
</body>
</html>
    """)

@app.get("/favicon.ico")
async def favicon():
    """Serve a simple favicon to prevent 404 errors."""
    return HTMLResponse(
        content="",
        status_code=204,
        headers={"Content-Type": "image/x-icon"}
    )

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/api/services")
async def get_services():
    """Get the status of all services."""
    services = get_docker_services()
    return {"services": [service.dict() for service in services]}

@app.post("/api/lab/start/{profile}")
async def start_lab(profile: str, background_tasks: BackgroundTasks):
    """Start the lab with specified profile."""
    valid_profiles = ["dev", "full", "testing", "monitoring", "load-testing", "demo"]
    if profile not in valid_profiles:
        raise HTTPException(status_code=400, detail=f"Invalid profile. Must be one of: {valid_profiles}")
    
    # Demo mode - simulate success without Docker
    if profile == "demo":
        await asyncio.sleep(2)  # Simulate startup time
        return {
            "status": "success",
            "message": f"Demo lab started successfully! (Simulated)",
            "profile": profile,
            "demo_mode": True,
            "services_simulated": [
                {"name": "ollama", "status": "running", "health": "healthy"},
                {"name": "prometheus", "status": "running", "health": "healthy"},
                {"name": "grafana", "status": "running", "health": "healthy"},
                {"name": "metrics-exporter", "status": "running", "health": "healthy"}
            ]
        }
    
    # Use docker-compose directly instead of make commands
    profile_map = {
        "dev": "dev",
        "full": "all", 
        "testing": "testing",
        "monitoring": "monitoring",
        "load-testing": "load-testing"
    }
    
    # Check if Docker is running first
    docker_check = check_docker_status()
    if not docker_check["success"]:
        if docker_check["error"] == "docker_not_running":
            return {
                "status": "error",
                "message": "Docker is not running. Please start Docker Desktop and try again.",
                "error": "docker_not_running",
                "instructions": [
                    "1. Start Docker Desktop application",
                    "2. Wait for Docker to fully start",
                    "3. Try starting the lab again",
                    "4. Or try 'Demo' mode for UI testing without Docker"
                ]
            }
        elif docker_check["error"] == "docker_cli_not_available":
            return {
                "status": "warning",
                "message": "Docker CLI not available in container, but Docker socket detected. Lab management from container is limited.",
                "error": "docker_cli_not_available",
                "instructions": [
                    "1. Try 'Demo' mode for UI testing",
                    "2. Or start lab services from host system using 'docker-compose up'",
                    "3. Container can still monitor running services"
                ]
            }
        else:
            return {
                "status": "error", 
                "message": docker_check["message"],
                "error": docker_check["error"]
            }
    
    compose_profile = profile_map[profile]
    command = f"docker-compose --profile {compose_profile} up -d"
    result = run_command(command)
    
    if result["success"]:
        return {"status": "success", "message": f"Lab started with {profile} profile", "output": result["stdout"]}
    else:
        # Parse the error for better user feedback
        error_msg = result["stderr"]
        if "Cannot connect to the Docker daemon" in error_msg:
            return {
                "status": "warning",
                "message": "Docker daemon is not running. Please start Docker Desktop.",
                "error": "docker_not_running"
            }
        elif "missing separator" in error_msg:
            return {
                "status": "error", 
                "message": "Configuration error detected. Using simplified startup method.",
                "error": "config_error"
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to start lab: {error_msg[:500]}...",
                "error": "general_error"
            }

@app.post("/api/lab/stop")
async def stop_lab():
    """Stop all lab services."""
    # Check if Docker is running first
    docker_check = check_docker_status()
    if not docker_check["success"]:
        if docker_check["error"] == "docker_not_running":
            return {
                "status": "warning",
                "message": "Docker is not running. No services to stop.",
                "error": "docker_not_running",
                "info": "Lab services are already stopped (Docker not running)"
            }
        else:
            return {
                "status": "error", 
                "message": docker_check["message"],
                "error": docker_check["error"]
            }
    
    command = "docker-compose down"
    result = run_command(command)
    
    if result["success"]:
        return {"status": "success", "message": "Lab stopped successfully", "output": result["stdout"]}
    else:
        # Parse the error for better user feedback
        error_msg = result["stderr"]
        if "Cannot connect to the Docker daemon" in error_msg:
            return {
                "status": "warning",
                "message": "Docker daemon is not running. Services were already stopped.",
                "error": "docker_not_running"
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to stop lab: {error_msg[:500]}...",
                "error": "general_error"
            }

@app.get("/api/lab/status")
async def get_lab_status():
    """Get comprehensive lab status."""
    # Get Docker services
    services = get_docker_services()
    
    # Get lab configuration
    config = {
        "lab_name": os.getenv("LAB_NAME", "Semantic-Evaluation-Lab"),
        "lab_environment": os.getenv("LAB_ENVIRONMENT", "development"),
        "use_ollama": os.getenv("USE_OLLAMA", "true").lower() == "true",
        "auto_run_tests": os.getenv("AUTO_RUN_TESTS", "false").lower() == "true",
        "enable_monitoring": os.getenv("ENABLE_MONITORING", "true").lower() == "true"
    }
    
    return {
        "services": [service.dict() for service in services],
        "config": config,
        "timestamp": datetime.now().isoformat()
    }

def run_tests_directly(test_type: str) -> Dict[str, Any]:
    """Run tests directly within the container using pytest."""
    test_commands = {
        "unit": "pytest tests/unit/ -v --tb=short",
        "functional": "pytest tests/functional/ -v --tb=short", 
        "llm-eval": "pytest tests/llm_evaluation/ -v --tb=short -m 'llm_eval or deepeval'",
        "conversations": "pytest tests/llm_evaluation/test_conversation_chains.py -v --tb=short",
        "all": "pytest tests/ -v --tb=short"
    }
    
    if test_type == "load":
        return {
            "success": False,
            "message": "Load testing requires docker-compose. Use the host system to run load tests.",
            "instructions": [
                "From host system, run: make auto-load-test-medium",
                "Or access Locust web UI: docker-compose --profile load-test up -d",
                "Then open http://localhost:8089"
            ]
        }
    
    if test_type not in test_commands:
        return {
            "success": False,
            "message": f"Invalid test type. Must be one of: {list(test_commands.keys())}"
        }
    
    # Ensure test directories exist
    run_command("mkdir -p test-reports logs htmlcov")
    
    command = test_commands[test_type]
    
    # Add reporting options for better output
    if test_type != "load":
        command += f" --junitxml=test-reports/{test_type}-test-results.xml"
        if test_type == "all":
            command += " --cov=. --cov-report=html:htmlcov --cov-report=term-missing"
    
    return run_command(command)

@app.post("/api/tests/{test_type}")
async def run_test(test_type: str, background_tasks: BackgroundTasks):
    """Run a specific test type."""
    valid_test_types = ["unit", "functional", "llm-eval", "conversations", "load", "all"]
    
    if test_type not in valid_test_types:
        raise HTTPException(status_code=400, detail=f"Invalid test type. Must be one of: {valid_test_types}")
    
    # Check if we can run make commands (docker-compose available)
    make_check = run_command("which make && which docker-compose")
    
    if make_check["success"]:
        # Use make commands if docker-compose is available
        test_commands = {
            "unit": "auto-test-unit",
            "functional": "auto-test-functional", 
            "llm-eval": "auto-test-llm-eval",
            "conversations": "auto-test-conversations",
            "load": "auto-load-test-medium",
            "all": "auto-test-all"
        }
        command = f"make {test_commands[test_type]}"
        result = run_command(command)
    else:
        # Fallback to direct pytest execution
        result = run_tests_directly(test_type)
    
    if result["success"]:
        return {
            "status": "success", 
            "message": f"{test_type} tests completed successfully", 
            "output": result["stdout"],
            "fallback_mode": not make_check["success"]
        }
    else:
        error_message = result.get("message", f"Failed to run {test_type} tests")
        return {
            "status": "error", 
            "message": error_message, 
            "error": result.get("stderr", result.get("error", "Unknown error")),
            "instructions": result.get("instructions"),
            "fallback_mode": not make_check["success"]
        }

@app.post("/api/load-test")
async def run_load_test(config: LoadTestConfig):
    """Run load test with custom configuration."""
    env_vars = f"LOCUST_USERS={config.users} LOCUST_SPAWN_RATE={config.spawn_rate} LOCUST_RUN_TIME={config.run_time}"
    command = f"{env_vars} make auto-load-test-medium"
    
    result = run_command(command)
    
    if result["success"]:
        return {"status": "success", "message": "Load test started", "config": config.dict()}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start load test: {result['stderr']}")

@app.post("/api/make/{command}")
async def execute_make_command(command: str):
    """Execute a make command with comprehensive validation and enhanced feedback."""
    
    # Comprehensive list of all available make commands from the Makefile
    valid_commands = {
        # Lab automation commands
        "lab-start", "lab-start-full", "lab-start-minimal", "lab-start-testing", 
        "lab-start-load-testing", "lab-stop", "lab-restart", "lab-status", "lab-health",
        "lab-logs", "lab-logs-app", "lab-logs-tests", "lab-logs-monitoring", 
        "lab-shell", "lab-clean", "lab-reset",
        
        # Auto-test commands
        "auto-test-setup", "auto-test-run", "auto-test-unit", "auto-test-functional",
        "auto-test-llm-eval", "auto-test-conversations", "auto-test-all", "auto-test-reports",
        
        # Auto-load testing commands
        "auto-load-test-light", "auto-load-test-medium", "auto-load-test-heavy",
        "auto-load-test-conversation",
        
        # Configuration management
        "config-check", "config-generate", "config-validate", "config-example-quick-start",
        "config-example-full-eval", "env-copy", "env-check",
        
        # Monitoring automation
        "monitoring-auto-start", "monitoring-health-check", "monitoring-start", 
        "monitoring-stop", "monitoring-logs", "monitoring-status", "monitoring-restart",
        "monitoring-setup", "monitoring-dev", "monitoring-full", "monitoring-cleanup",
        "monitoring-health", "monitoring-validate",
        
        # Testing commands
        "test", "test-unit", "test-functional", "test-llm-eval", "test-llm-eval-ollama",
        "test-llm-eval-openai", "test-deepeval", "test-deepeval-ollama", "test-coverage",
        "test-coverage-xml", "test-reports", "test-env-check", "test-validate",
        
        # Conversation chain testing
        "test-conversation-chains", "test-conversation-chains-ollama", 
        "test-conversation-chains-with-metrics", "test-chain-5", "test-chain-10",
        "test-chain-15", "test-chain-20", "test-dynamic-conversations",
        "test-dynamic-conversations-ollama", "test-dynamic-5", "test-dynamic-10",
        "test-dynamic-15", "test-dynamic-20", "test-conversation-comparison",
        
        # LLM evaluation workflows
        "eval-agent-quality", "eval-agent-workflow", "eval-dataset", "eval-integration",
        
        # Code quality
        "lint", "type-check", "security", "format", "format-check", "quality-check",
        "clean", "version",
        
        # Installation and development
        "install", "install-dev", "dev-setup", "run-ollama", "run-azure", "run-ollama-script",
        
        # DeepEval commands
        "deepeval-login", "deepeval-dashboard", "deepeval-check",
        
        # CI/CD helpers
        "ci-install", "ci-test", "ci-test-llm", "ci-quality",
        
        # Load testing with Locust
        "load-test-start", "load-test-headless", "load-test-stop", "load-test-light",
        "load-test-medium", "load-test-heavy", "load-test-health",
        
        # Web UI commands
        "web-ui-start", "web-ui-stop", "web-ui-logs", "web-ui-health", "web-ui-demo",
        
        # Docker commands
        "docker-build", "docker-build-dev", "docker-up", "docker-down", "docker-logs",
        "docker-shell", "docker-clean",
        
        # Reporting
        "generate-stability-report", "export-metrics", "view-metrics", "clean-logs",
        
        # Aliases (common shortcuts)
        "ls", "lsf", "lst", "lsl", "lx", "lr", "lh", "cc", "at", "ata",
        "mon", "mon-stop", "mon-logs", "mon-health", "lt-start", "lt-stop",
        "lt-light", "lt-medium", "lt-heavy", "lt-health", "ui", "ui-stop",
        "ui-logs", "ui-demo"
    }
    
    if command not in valid_commands:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid make command: {command}. Available commands: {', '.join(sorted(valid_commands))}"
        )
    
    # Check if make is available
    make_check = run_command("which make")
    if not make_check["success"]:
        return {
            "status": "error",
            "message": "Make is not available in this environment",
            "error": "make_not_available",
            "instructions": [
                "1. Make commands require the host system or a container with make installed",
                "2. Try using the equivalent API endpoints where available",
                "3. Or run commands directly from the host system using: make " + command
            ]
        }
    
    # Special handling for certain commands that need environment setup
    command_prefix = ""
    if command in ["test-llm-eval", "test-deepeval", "auto-test-llm-eval"]:
        # Check if OPENAI_API_KEY is set for LLM evaluation tests
        if not os.getenv("OPENAI_API_KEY"):
            return {
                "status": "warning",
                "message": f"LLM evaluation command '{command}' requires OPENAI_API_KEY",
                "error": "missing_api_key",
                "instructions": [
                    "1. Set OPENAI_API_KEY environment variable",
                    "2. Or configure Ollama for local LLM evaluation",
                    "3. Or try unit tests instead: make test-unit"
                ]
            }
    
    # Add proper directory context and error handling
    full_command = f"cd {os.getcwd()} && make {command}"
    
    result = run_command(full_command)
    
    if result["success"]:
        return {
            "status": "success",
            "message": f"Make command '{command}' executed successfully",
            "output": result["stdout"],
            "command": command
        }
    else:
        # Enhanced error parsing for better user feedback
        error_msg = result["stderr"]
        
        if "No such file or directory" in error_msg:
            return {
                "status": "error",
                "message": f"Makefile or required files not found for command: {command}",
                "error": "file_not_found",
                "instructions": [
                    "1. Ensure you're in the correct project directory",
                    "2. Check that Makefile exists in the current directory",
                    "3. Verify all required dependencies are installed"
                ]
            }
        elif "Permission denied" in error_msg:
            return {
                "status": "error",
                "message": f"Permission denied executing command: {command}",
                "error": "permission_denied",
                "instructions": [
                    "1. Check file permissions",
                    "2. Ensure Docker daemon is accessible if using Docker commands",
                    "3. Try running from the host system if in a container"
                ]
            }
        elif "Command not found" in error_msg:
            return {
                "status": "error",
                "message": f"Required tools not found for command: {command}",
                "error": "dependencies_missing",
                "instructions": [
                    "1. Install missing dependencies (docker, docker-compose, python, etc.)",
                    "2. Check your PATH environment variable",
                    "3. Try: make install-dev to install development dependencies"
                ]
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to execute make command: {command}",
                "error": error_msg[:500] + "..." if len(error_msg) > 500 else error_msg,
                "command": command,
                "instructions": [
                    "1. Check the error details above",
                    "2. Try running the command manually: make " + command,
                    "3. Check if all prerequisites are met",
                    "4. View logs with: make lab-logs"
                ]
            }

@app.get("/api/make/help")
async def get_make_help():
    """Get comprehensive help for all available make commands."""
    result = run_command("make help")
    
    if result["success"]:
        return {
            "status": "success",
            "help_output": result["stdout"],
            "message": "Make help retrieved successfully"
        }
    else:
        return {
            "status": "error", 
            "message": "Could not retrieve make help",
            "error": result["stderr"]
        }

@app.get("/api/logs/{service}")
async def get_service_logs(service: str, lines: int = 100):
    """Get logs for a specific service."""
    command = f"docker-compose logs --tail={lines} {service}"
    result = run_command(command)
    
    if result["success"]:
        return {"logs": result["stdout"], "service": service}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {result['stderr']}")

@app.get("/api/config")
async def get_configuration():
    """Get current lab configuration."""
    config = {}
    
    # Read from environment variables
    env_vars = [
        "LAB_NAME", "LAB_ENVIRONMENT", "USE_OLLAMA", "AUTO_RUN_TESTS",
        "ENABLE_MONITORING", "OLLAMA_MODEL_ID", "LOCUST_USERS", "LOCUST_SPAWN_RATE"
    ]
    
    for var in env_vars:
        config[var] = os.getenv(var, "")
    
    return {"config": config}

@app.post("/api/config")
async def update_configuration(config: dict):
    """Update lab configuration."""
    try:
        # In a real implementation, you would update the .env file
        # For now, we'll just return the received config
        return {"status": "success", "message": "Configuration updated", "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            await manager.send_personal_message(f"Echo: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(
        "web_ui:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="info"
    )