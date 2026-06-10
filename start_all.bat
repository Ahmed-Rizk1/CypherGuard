@echo off
echo ==============================================
echo 🛡️ SecureNet SOC - Start All Services 🛡️
echo ==============================================
echo Activating virtual environment and starting microservices...

start "API Gateway (Port 8000)" cmd /k "call .venv\Scripts\activate.bat && python gateway\main.py"
start "Feature Extractor (Port 8001)" cmd /k "call .venv\Scripts\activate.bat && python extractor\main.py"
start "ML Engine (Port 8002)" cmd /k "call .venv\Scripts\activate.bat && python ml_engine\main.py"
start "LLM Analyzer (Port 8003)" cmd /k "call .venv\Scripts\activate.bat && python llm_analyzer\main.py"
start "Firewall Controller (Port 8004)" cmd /k "call .venv\Scripts\activate.bat && python firewall\main.py"
start "Mobile Gateway (Port 8005)" cmd /k "call .venv\Scripts\activate.bat && python mobile_gateway\main.py"
start "Decision Engine (Port 8006)" cmd /k "call .venv\Scripts\activate.bat && python control_plane\decision_engine.py"

echo Starting React Dashboard...
start "SOC React Dashboard" cmd /k "cd soc-frontend && npm run dev"

echo.
echo All services are starting up in the background!
echo 1. Wait 5 seconds for the React Dashboard to build.
echo 2. Open your browser and go to http://localhost:5173
echo 3. To launch an attack simulation, open a new terminal, activate .venv, and run:
echo    python simulator\attack.py
echo ==============================================
pause
