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
                            health = get_service_health("http://localhost:11434")
                        elif service_name == "metrics-exporter":
                            url = "http://localhost:8000"
                            health = get_service_health("http://localhost:8000")
                        
                        services.append(ServiceStatus(
                            name=service_name,
                            status=status,
                            health=health,
                            url=url
                        ))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
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
    </style>
</head>
<body class="bg-gray-50">
    <div id="root"></div>
    <script type="text/babel">
        const { useState, useEffect } = React;

        // Main App Component
        function App() {
            const [activeTab, setActiveTab] = useState('dashboard');
            const [services, setServices] = useState([]);
            const [labConfig, setLabConfig] = useState({
                lab_name: 'Semantic-Evaluation-Lab',
                lab_environment: 'development',
                use_ollama: true,
                auto_run_tests: false,
                enable_monitoring: true,
                enable_debug_mode: true
            });
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

            // API calls
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

            const startLab = async (profile = 'dev') => {
                return await apiCall(`/lab/start/${profile}`, 'POST');
            };

            const stopLab = async () => {
                return await apiCall('/lab/stop', 'POST');
            };

            return (
                <div className="min-h-screen bg-gray-50">
                    <Navigation activeTab={activeTab} setActiveTab={setActiveTab} />
                    <main className="container mx-auto px-4 py-6">
                        {activeTab === 'dashboard' && <Dashboard services={services} startLab={startLab} stopLab={stopLab} />}
                        {activeTab === 'tests' && <TestManager />}
                        {activeTab === 'load-testing' && <LoadTesting />}
                        {activeTab === 'monitoring' && <Monitoring />}
                        {activeTab === 'config' && <Configuration labConfig={labConfig} setLabConfig={setLabConfig} />}
                        {activeTab === 'logs' && <LogViewer />}
                    </main>
                </div>
            );
        }

        // Navigation Component
        function Navigation({ activeTab, setActiveTab }) {
            const tabs = [
                { id: 'dashboard', name: 'Dashboard', icon: 'fas fa-tachometer-alt' },
                { id: 'tests', name: 'Tests', icon: 'fas fa-flask' },
                { id: 'load-testing', name: 'Load Testing', icon: 'fas fa-fire' },
                { id: 'monitoring', name: 'Monitoring', icon: 'fas fa-chart-line' },
                { id: 'config', name: 'Configuration', icon: 'fas fa-cog' },
                { id: 'logs', name: 'Logs', icon: 'fas fa-file-alt' }
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
                                                ? 'bg-white text-purple-700 shadow-md' 
                                                : 'text-white hover:bg-white hover:bg-opacity-20'
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

        // Dashboard Component
        function Dashboard({ services, startLab, stopLab }) {
            const [loading, setLoading] = useState(false);

            const getServiceColor = (service) => {
                if (service.status === 'running' && service.health === 'healthy') return 'green';
                if (service.status === 'running') return 'yellow';
                return 'red';
            };

            const handleLabAction = async (action, profile = null) => {
                setLoading(true);
                try {
                    if (action === 'start') {
                        await startLab(profile);
                    } else {
                        await stopLab();
                    }
                } finally {
                    setLoading(false);
                }
            };

            return (
                <div className="space-y-6">
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
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <button
                            onClick={() => handleLabAction('start', 'full')}
                            disabled={loading}
                            className="bg-green-500 hover:bg-green-600 text-white p-4 rounded-lg card-hover disabled:opacity-50"
                        >
                            <i className="fas fa-play text-2xl mb-2"></i>
                            <div className="font-semibold">Start Full Lab</div>
                            <div className="text-sm opacity-90">All services + automation</div>
                        </button>
                        
                        <button
                            onClick={() => handleLabAction('start', 'dev')}
                            disabled={loading}
                            className="bg-blue-500 hover:bg-blue-600 text-white p-4 rounded-lg card-hover disabled:opacity-50"
                        >
                            <i className="fas fa-code text-2xl mb-2"></i>
                            <div className="font-semibold">Start Dev Lab</div>
                            <div className="text-sm opacity-90">Development mode</div>
                        </button>
                        
                        <button
                            onClick={() => handleLabAction('start', 'testing')}
                            disabled={loading}
                            className="bg-purple-500 hover:bg-purple-600 text-white p-4 rounded-lg card-hover disabled:opacity-50"
                        >
                            <i className="fas fa-flask text-2xl mb-2"></i>
                            <div className="font-semibold">Start Testing</div>
                            <div className="text-sm opacity-90">Testing optimized</div>
                        </button>
                        
                        <button
                            onClick={() => handleLabAction('stop')}
                            disabled={loading}
                            className="bg-red-500 hover:bg-red-600 text-white p-4 rounded-lg card-hover disabled:opacity-50"
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
                                            <div className={`w-3 h-3 rounded-full bg-${getServiceColor(service)}-500`}></div>
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
            const [activeTests, setActiveTests] = useState([]);
            const [testHistory, setTestHistory] = useState([]);

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
                            />
                            <TestCard 
                                title="Functional Tests"
                                description="Test application functionality"
                                icon="fas fa-cogs"
                                color="green"
                                endpoint="/tests/functional"
                            />
                            <TestCard 
                                title="LLM Evaluation"
                                description="DeepEval quality metrics"
                                icon="fas fa-brain"
                                color="purple"
                                endpoint="/tests/llm-eval"
                            />
                            <TestCard 
                                title="Conversation Chains"
                                description="Multi-turn conversation tests"
                                icon="fas fa-comments"
                                color="indigo"
                                endpoint="/tests/conversations"
                            />
                            <TestCard 
                                title="Load Tests"
                                description="Performance and load testing"
                                icon="fas fa-fire"
                                color="red"
                                endpoint="/tests/load"
                            />
                            <TestCard 
                                title="All Tests"
                                description="Run complete test suite"
                                icon="fas fa-list-check"
                                color="gray"
                                endpoint="/tests/all"
                            />
                        </div>
                    </div>
                </div>
            );
        }

        function TestCard({ title, description, icon, color, endpoint }) {
            const [running, setRunning] = useState(false);

            const runTest = async () => {
                setRunning(true);
                try {
                    const response = await fetch(`/api${endpoint}`, { method: 'POST' });
                    const result = await response.json();
                    console.log('Test result:', result);
                } finally {
                    setRunning(false);
                }
            };

            return (
                <div className="bg-gray-50 rounded-lg p-4 card-hover">
                    <div className={`text-2xl text-${color}-500 mb-3`}>
                        <i className={icon}></i>
                    </div>
                    <h3 className="font-semibold text-gray-800 mb-2">{title}</h3>
                    <p className="text-gray-600 text-sm mb-4">{description}</p>
                    <button
                        onClick={runTest}
                        disabled={running}
                        className={`w-full bg-${color}-500 hover:bg-${color}-600 text-white py-2 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                        {running ? (
                            <>
                                <i className="fas fa-spinner fa-spin mr-2"></i>
                                Running...
                            </>
                        ) : (
                            <>
                                <i className="fas fa-play mr-2"></i>
                                Run Test
                            </>
                        )}
                    </button>
                </div>
            );
        }

        // Load Testing Component
        function LoadTesting() {
            return (
                <div className="bg-white rounded-lg shadow-md p-6">
                    <h2 className="text-2xl font-bold text-gray-800 mb-4">
                        <i className="fas fa-fire mr-2 text-red-500"></i>
                        Load Testing
                    </h2>
                    <p className="text-gray-600">Configure and execute load tests with real-time monitoring</p>
                    {/* Load testing interface will be implemented here */}
                </div>
            );
        }

        // Monitoring Component
        function Monitoring() {
            return (
                <div className="space-y-6">
                    <div className="bg-white rounded-lg shadow-md p-6">
                        <h2 className="text-2xl font-bold text-gray-800 mb-4">
                            <i className="fas fa-chart-line mr-2 text-green-500"></i>
                            Monitoring & Observability
                        </h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="bg-gray-50 p-4 rounded-lg">
                                <h3 className="font-semibold mb-2">Grafana Dashboard</h3>
                                <p className="text-gray-600 text-sm mb-3">Real-time metrics and visualizations</p>
                                <a 
                                    href="http://localhost:3000" 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="bg-orange-500 text-white py-2 px-4 rounded-lg inline-flex items-center hover:bg-orange-600"
                                >
                                    <i className="fas fa-external-link-alt mr-2"></i>
                                    Open Grafana
                                </a>
                            </div>
                            <div className="bg-gray-50 p-4 rounded-lg">
                                <h3 className="font-semibold mb-2">Prometheus</h3>
                                <p className="text-gray-600 text-sm mb-3">Metrics collection and querying</p>
                                <a 
                                    href="http://localhost:9090" 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="bg-red-500 text-white py-2 px-4 rounded-lg inline-flex items-center hover:bg-red-600"
                                >
                                    <i className="fas fa-external-link-alt mr-2"></i>
                                    Open Prometheus
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }

        // Configuration Component
        function Configuration({ labConfig, setLabConfig }) {
            return (
                <div className="bg-white rounded-lg shadow-md p-6">
                    <h2 className="text-2xl font-bold text-gray-800 mb-4">
                        <i className="fas fa-cog mr-2 text-gray-500"></i>
                        Lab Configuration
                    </h2>
                    <p className="text-gray-600">Manage environment variables and lab settings</p>
                    {/* Configuration interface will be implemented here */}
                </div>
            );
        }

        // Log Viewer Component
        function LogViewer() {
            return (
                <div className="bg-white rounded-lg shadow-md p-6">
                    <h2 className="text-2xl font-bold text-gray-800 mb-4">
                        <i className="fas fa-file-alt mr-2 text-blue-500"></i>
                        Live Logs
                    </h2>
                    <p className="text-gray-600">Real-time log monitoring and analysis</p>
                    {/* Log viewer interface will be implemented here */}
                </div>
            );
        }

        // Render the app
        ReactDOM.render(<App />, document.getElementById('root'));
    </script>
</body>
</html>
    """)

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
    valid_profiles = ["dev", "full", "testing", "monitoring", "load-testing"]
    if profile not in valid_profiles:
        raise HTTPException(status_code=400, detail=f"Invalid profile. Must be one of: {valid_profiles}")
    
    # Use docker-compose directly instead of make commands
    profile_map = {
        "dev": "dev",
        "full": "all", 
        "testing": "testing",
        "monitoring": "monitoring",
        "load-testing": "load-testing"
    }
    
    compose_profile = profile_map[profile]
    command = f"docker-compose --profile {compose_profile} up -d"
    result = run_command(command)
    
    if result["success"]:
        return {"status": "success", "message": f"Lab started with {profile} profile", "output": result["stdout"]}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start lab: {result['stderr']}")

@app.post("/api/lab/stop")
async def stop_lab():
    """Stop all lab services."""
    command = "docker-compose down"
    result = run_command(command)
    
    if result["success"]:
        return {"status": "success", "message": "Lab stopped", "output": result["stdout"]}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to stop lab: {result['stderr']}")

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

@app.post("/api/tests/{test_type}")
async def run_test(test_type: str, background_tasks: BackgroundTasks):
    """Run a specific test type."""
    test_commands = {
        "unit": "auto-test-unit",
        "functional": "auto-test-functional", 
        "llm-eval": "auto-test-llm-eval",
        "conversations": "auto-test-conversations",
        "load": "auto-load-test-medium",
        "all": "auto-test-all"
    }
    
    if test_type not in test_commands:
        raise HTTPException(status_code=400, detail=f"Invalid test type. Must be one of: {list(test_commands.keys())}")
    
    command = f"make {test_commands[test_type]}"
    result = run_command(command)
    
    if result["success"]:
        return {"status": "success", "message": f"{test_type} tests started", "output": result["stdout"]}
    else:
        return {"status": "error", "message": f"Failed to start {test_type} tests", "error": result["stderr"]}

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