#!/usr/bin/env python3
"""
Semantic Evaluation Lab - Web UI Backend

A comprehensive FastAPI application that provides a user-friendly web interface
for managing the entire Semantic Evaluation Lab ecosystem.

Features:
- Lab service management (start/stop/status)
- Real-time test execution and monitoring
- Configuration management
- Load testing interface
- Monitoring dashboard integration
- Real-time logs and metrics
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
    <title>Semantic Evaluation Lab</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .card-hover { transition: all 0.3s ease; }
        .card-hover:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .tab-btn-active { background: white !important; color: #6b46c1 !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important; }
        .tab-btn-inactive { color: white; }
        .tab-btn-inactive:hover { background: rgba(255, 255, 255, 0.2); }
        .status-green { background-color: #10b981; }
        .status-yellow { background-color: #f59e0b; }
        .status-red { background-color: #ef4444; }
        .bg-success { background-color: #d1fae5; border-color: #10b981; color: #065f46; }
        .bg-warning { background-color: #fef3c7; border-color: #f59e0b; color: #92400e; }
        .bg-error { background-color: #fecaca; border-color: #ef4444; color: #991b1b; }
        .bg-info { background-color: #dbeafe; border-color: #3b82f6; color: #1e40af; }
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
            </div>
        </div>
    </div>

    <script type="text/babel">
        const { useState, useEffect } = React;

        // Color utility functions
        function getStatusColor(service) {
            if (service.status === 'running' && service.health === 'healthy') return 'status-green';
            if (service.status === 'running') return 'status-yellow';
            return 'status-red';
        }

        function getAlertClass(type) {
            switch(type) {
                case 'success': return 'bg-success';
                case 'warning': return 'bg-warning';
                case 'error': return 'bg-error';
                default: return 'bg-info';
            }
        }

        function getButtonClass(color, disabled = false) {
            const baseClass = "py-2 px-4 rounded-lg transition-colors";
            const disabledClass = disabled ? " opacity-50 cursor-not-allowed" : "";
            
            switch(color) {
                case 'blue': return `bg-blue-500 hover:bg-blue-600 text-white ${baseClass}${disabledClass}`;
                case 'green': return `bg-green-500 hover:bg-green-600 text-white ${baseClass}${disabledClass}`;
                case 'purple': return `bg-purple-500 hover:bg-purple-600 text-white ${baseClass}${disabledClass}`;
                case 'red': return `bg-red-500 hover:bg-red-600 text-white ${baseClass}${disabledClass}`;
                case 'orange': return `bg-orange-500 hover:bg-orange-600 text-white ${baseClass}${disabledClass}`;
                case 'indigo': return `bg-indigo-500 hover:bg-indigo-600 text-white ${baseClass}${disabledClass}`;
                case 'gray': return `bg-gray-500 hover:bg-gray-600 text-white ${baseClass}${disabledClass}`;
                default: return `bg-blue-500 hover:bg-blue-600 text-white ${baseClass}${disabledClass}`;
            }
        }

        // API utility
        const apiCall = async (endpoint, method = 'GET', body = null) => {
            try {
                const options = {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                };
                if (body) options.body = JSON.stringify(body);
                
                const response = await fetch(`/api${endpoint}`, options);
                return await response.json();
            } catch (error) {
                console.error('API call failed:', error);
                return { error: error.message };
            }
        };

        // Main App Component
        function App() {
            const [activeTab, setActiveTab] = useState('dashboard');
            const [services, setServices] = useState([]);
            const [ws, setWs] = useState(null);

            // WebSocket connection
            useEffect(() => {
                const websocket = new WebSocket(`ws://${window.location.host}/ws`);
                
                websocket.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    if (data.type === 'service_update') {
                        setServices(data.data);
                    }
                };

                setWs(websocket);

                return () => {
                    websocket.close();
                };
            }, []);

            return (
                <div className="min-h-screen bg-gray-50">
                    <Navigation activeTab={activeTab} setActiveTab={setActiveTab} />
                    <main className="container mx-auto px-4 py-6">
                        {activeTab === 'dashboard' && <Dashboard services={services} />}
                        {activeTab === 'tests' && <TestManager />}
                        {activeTab === 'monitoring' && <Monitoring />}
                    </main>
                </div>
            );
        }

        // Navigation Component
        function Navigation({ activeTab, setActiveTab }) {
            const tabs = [
                { id: 'dashboard', name: 'Dashboard', icon: 'fas fa-tachometer-alt' },
                { id: 'tests', name: 'Tests', icon: 'fas fa-flask' },
                { id: 'monitoring', name: 'Monitoring', icon: 'fas fa-chart-line' }
            ];

            return (
                <nav className="gradient-bg shadow-lg">
                    <div className="container mx-auto px-4">
                        <div className="flex items-center justify-between h-16">
                            <div className="flex items-center space-x-4">
                                <h1 className="text-white text-xl font-bold">
                                    <i className="fas fa-microscope mr-2"></i>
                                    Semantic Evaluation Lab
                                </h1>
                            </div>
                            <div className="flex space-x-1">
                                {tabs.map(tab => (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`px-4 py-2 rounded-lg transition-all duration-200 flex items-center space-x-2 ${
                                            activeTab === tab.id 
                                                ? 'tab-btn-active' 
                                                : 'tab-btn-inactive'
                                        }`}
                                    >
                                        <i className={tab.icon}></i>
                                        <span className="hidden md:inline">{tab.name}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                </nav>
            );
        }

        // Alert Component
        function Alert({ message, type, onClose }) {
            if (!message) return null;

            return (
                <div className={`rounded-lg p-4 border ${getAlertClass(type)}`}>
                    <div className="flex">
                        <div className="flex-shrink-0">
                            <i className={`fas ${
                                type === 'success' ? 'fa-check-circle' :
                                type === 'warning' ? 'fa-exclamation-triangle' :
                                type === 'error' ? 'fa-times-circle' :
                                'fa-info-circle'
                            }`}></i>
                        </div>
                        <div className="ml-3 flex-1">
                            {typeof message === 'string' ? <p>{message}</p> : message}
                        </div>
                        {onClose && (
                            <div className="ml-auto pl-3">
                                <button 
                                    onClick={onClose}
                                    className="text-gray-400 hover:text-gray-600"
                                >
                                    <i className="fas fa-times"></i>
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            );
        }

        // Dashboard Component
        function Dashboard({ services }) {
            const [loading, setLoading] = useState(false);
            const [alertMessage, setAlertMessage] = useState(null);
            const [alertType, setAlertType] = useState('info');

            const showAlert = (message, type = 'info', duration = 5000) => {
                setAlertMessage(message);
                setAlertType(type);
                setTimeout(() => setAlertMessage(null), duration);
            };

            const handleLabAction = async (action, profile = null) => {
                setLoading(true);
                setAlertMessage(null);
                try {
                    let result;
                    if (action === 'start') {
                        result = await apiCall(`/lab/start/${profile}`, 'POST');
                    } else {
                        result = await apiCall('/lab/stop', 'POST');
                    }

                    if (result.status === 'success') {
                        showAlert(`✅ ${result.message}`, 'success');
                    } else if (result.status === 'error') {
                        if (result.error === 'docker_not_running') {
                            showAlert(
                                React.createElement('div', null,
                                    React.createElement('div', { className: 'font-semibold mb-2' }, '🐳 Docker Required'),
                                    React.createElement('div', { className: 'mb-2' }, result.message),
                                    result.instructions && React.createElement('ul', { className: 'list-disc list-inside text-sm' },
                                        result.instructions.map((instruction, index) => 
                                            React.createElement('li', { key: index }, instruction)
                                        )
                                    )
                                ), 
                                'warning', 
                                10000
                            );
                        } else {
                            showAlert(`❌ ${result.message}`, 'error');
                        }
                    } else if (result.status === 'warning') {
                        showAlert(`⚠️ ${result.message}`, 'warning', 7000);
                    }
                } catch (error) {
                    showAlert(`❌ Network error: ${error.message}`, 'error');
                } finally {
                    setLoading(false);
                }
            };

            return (
                <div className="space-y-6">
                    <Alert 
                        message={alertMessage} 
                        type={alertType} 
                        onClose={() => setAlertMessage(null)} 
                    />

                    {/* Header */}
                    <div className="bg-white rounded-lg shadow-md p-6">
                        <h2 className="text-2xl font-bold text-gray-800 mb-4">
                            <i className="fas fa-home mr-2 text-blue-500"></i>
                            Lab Dashboard
                        </h2>
                        <p className="text-gray-600">
                            Monitor and control your Semantic Evaluation Lab environment
                        </p>
                    </div>

                    {/* Quick Actions */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                        <button
                            onClick={() => handleLabAction('start', 'demo')}
                            disabled={loading}
                            className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white p-4 rounded-lg card-hover disabled:opacity-50 border-2 border-purple-300"
                        >
                            <i className="fas fa-magic text-2xl mb-2"></i>
                            <div className="font-semibold">Demo Mode</div>
                            <div className="text-sm opacity-90">UI Demo (No Docker)</div>
                        </button>
                        
                        <button
                            onClick={() => handleLabAction('start', 'full')}
                            disabled={loading}
                            className={getButtonClass('green', loading) + " p-4 card-hover"}
                        >
                            <i className="fas fa-play text-2xl mb-2"></i>
                            <div className="font-semibold">Start Full Lab</div>
                            <div className="text-sm opacity-90">All services</div>
                        </button>
                        
                        <button
                            onClick={() => handleLabAction('start', 'dev')}
                            disabled={loading}
                            className={getButtonClass('blue', loading) + " p-4 card-hover"}
                        >
                            <i className="fas fa-code text-2xl mb-2"></i>
                            <div className="font-semibold">Start Dev Lab</div>
                            <div className="text-sm opacity-90">Development mode</div>
                        </button>
                        
                        <button
                            onClick={() => handleLabAction('start', 'testing')}
                            disabled={loading}
                            className={getButtonClass('purple', loading) + " p-4 card-hover"}
                        >
                            <i className="fas fa-flask text-2xl mb-2"></i>
                            <div className="font-semibold">Start Testing</div>
                            <div className="text-sm opacity-90">Testing optimized</div>
                        </button>
                        
                        <button
                            onClick={() => handleLabAction('stop')}
                            disabled={loading}
                            className={getButtonClass('red', loading) + " p-4 card-hover"}
                        >
                            <i className="fas fa-stop text-2xl mb-2"></i>
                            <div className="font-semibold">Stop Lab</div>
                            <div className="text-sm opacity-90">All services</div>
                        </button>
                    </div>

                    {/* Service Status */}
                    <div className="bg-white rounded-lg shadow-md p-6">
                        <h3 className="text-xl font-semibold text-gray-800 mb-4">
                            <i className="fas fa-server mr-2 text-blue-500"></i>
                            Service Status
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {services.length === 0 ? (
                                <div className="col-span-full text-center text-gray-500 py-8">
                                    <i className="fas fa-info-circle text-4xl mb-4"></i>
                                    <p>No services running. Start the lab to see service status.</p>
                                </div>
                            ) : (
                                services.map(service => (
                                    <div key={service.name} className="bg-gray-50 rounded-lg p-4 card-hover">
                                        <div className="flex items-center justify-between mb-2">
                                            <h4 className="font-medium text-gray-800">{service.name}</h4>
                                            <div className={`w-3 h-3 rounded-full ${getStatusColor(service)}`}></div>
                                        </div>
                                        <div className="text-sm text-gray-600">
                                            <div>Status: <span className="font-medium">{service.status}</span></div>
                                            <div>Health: <span className="font-medium">{service.health}</span></div>
                                            {service.url && (
                                                <a 
                                                    href={service.url} 
                                                    target="_blank" 
                                                    rel="noopener noreferrer"
                                                    className="text-blue-500 hover:text-blue-700 inline-flex items-center mt-2"
                                                >
                                                    <i className="fas fa-external-link-alt mr-1"></i>
                                                    Open
                                                </a>
                                            )}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Quick Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="bg-white rounded-lg shadow-md p-6">
                            <div className="flex items-center">
                                <div className="text-3xl text-green-500">
                                    <i className="fas fa-check-circle"></i>
                                </div>
                                <div className="ml-4">
                                    <div className="text-xl font-semibold text-gray-800">
                                        {services.filter(s => s.status === 'running').length}
                                    </div>
                                    <div className="text-gray-600">Active Services</div>
                                </div>
                            </div>
                        </div>
                        
                        <div className="bg-white rounded-lg shadow-md p-6">
                            <div className="flex items-center">
                                <div className="text-3xl text-blue-500">
                                    <i className="fas fa-heart"></i>
                                </div>
                                <div className="ml-4">
                                    <div className="text-xl font-semibold text-gray-800">
                                        {services.filter(s => s.health === 'healthy').length}
                                    </div>
                                    <div className="text-gray-600">Healthy Services</div>
                                </div>
                            </div>
                        </div>
                        
                        <div className="bg-white rounded-lg shadow-md p-6">
                            <div className="flex items-center">
                                <div className="text-3xl text-purple-500">
                                    <i className="fas fa-clock"></i>
                                </div>
                                <div className="ml-4">
                                    <div className="text-xl font-semibold text-gray-800">
                                        {new Date().toLocaleTimeString()}
                                    </div>
                                    <div className="text-gray-600">Current Time</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }

        // Test Manager Component
        function TestManager() {
            const [testHistory, setTestHistory] = useState([]);
            const [selectedTest, setSelectedTest] = useState(null);

            const addTestResult = (testType, result) => {
                const timestamp = new Date().toISOString();
                const testEntry = {
                    id: Date.now(),
                    type: testType,
                    timestamp,
                    result,
                    status: result.status
                };
                
                setTestHistory(prev => [testEntry, ...prev.slice(0, 9)]);
            };

            return (
                <div className="space-y-6">
                    <div className="bg-white rounded-lg shadow-md p-6">
                        <h2 className="text-2xl font-bold text-gray-800 mb-4">
                            <i className="fas fa-flask mr-2 text-purple-500"></i>
                            Test Management
                        </h2>
                        <p className="text-gray-600 mb-6">Execute and monitor test suites</p>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            <TestCard 
                                title="Unit Tests"
                                description="Run unit test suite"
                                icon="fas fa-cube"
                                color="blue"
                                endpoint="/tests/unit"
                                onResult={(result) => addTestResult('unit', result)}
                            />
                            <TestCard 
                                title="Functional Tests"
                                description="Test application functionality"
                                icon="fas fa-cogs"
                                color="green"
                                endpoint="/tests/functional"
                                onResult={(result) => addTestResult('functional', result)}
                            />
                            <TestCard 
                                title="LLM Evaluation"
                                description="DeepEval quality metrics"
                                icon="fas fa-brain"
                                color="purple"
                                endpoint="/tests/llm-eval"
                                onResult={(result) => addTestResult('llm-eval', result)}
                            />
                        </div>
                    </div>

                    {/* Test History */}
                    <div className="bg-white rounded-lg shadow-md p-6">
                        <h3 className="text-xl font-semibold text-gray-800 mb-4">
                            <i className="fas fa-history mr-2 text-blue-500"></i>
                            Recent Test Runs
                        </h3>
                        <div className="space-y-3 max-h-96 overflow-y-auto">
                            {testHistory.length === 0 ? (
                                <div className="text-center text-gray-500 py-8">
                                    <i className="fas fa-clock text-4xl mb-4 text-gray-300"></i>
                                    <p>No tests run yet. Click a test card to get started!</p>
                                </div>
                            ) : (
                                testHistory.map(test => (
                                    <div
                                        key={test.id}
                                        className={`p-3 rounded-lg border-l-4 cursor-pointer hover:bg-gray-50 transition-colors ${
                                            test.status === 'success' ? 'border-green-500 bg-green-50' :
                                            test.status === 'error' ? 'border-red-500 bg-red-50' :
                                            'border-yellow-500 bg-yellow-50'
                                        }`}
                                        onClick={() => setSelectedTest(test)}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center space-x-3">
                                                <i className={`fas ${
                                                    test.status === 'success' ? 'fa-check-circle text-green-500' :
                                                    test.status === 'error' ? 'fa-times-circle text-red-500' :
                                                    'fa-exclamation-triangle text-yellow-500'
                                                }`}></i>
                                                <div>
                                                    <span className="font-medium capitalize">{test.type} Tests</span>
                                                    <div className="text-sm text-gray-500">
                                                        {new Date(test.timestamp).toLocaleTimeString()}
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    </div>

    <script>
        // Simple tab management
        window.currentTab = 'dashboard';
        
        function showTab(tabName) {
            window.currentTab = tabName;
            // Redirect to appropriate content
            console.log('Tab changed to:', tabName);
        }
        
        // Simple test runner
        async function runTest(testType) {
            try {
                const response = await fetch('/api/tests/' + testType, { method: 'POST' });
                const data = await response.json();
                alert('Test result: ' + data.message);
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        // Lab management
        async function startLab(profile) {
            try {
                const response = await fetch('/api/lab/start/' + profile, { method: 'POST' });
                const data = await response.json();
                alert('Lab result: ' + data.message);
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        async function stopLab() {
            try {
                const response = await fetch('/api/lab/stop', { method: 'POST' });
                const data = await response.json();
                alert('Lab result: ' + data.message);
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
    </script>

    <!-- Render the React app -->
    <script>
        ReactDOM.render(React.createElement(App), document.getElementById('root'));
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