@echo off
[cite_start]ECHO "=================================================" [cite: 8]
[cite_start]ECHO "           Demultiplexing Tool Launcher" [cite: 8]
[cite_start]ECHO "=================================================" [cite: 8]
[cite_start]ECHO. [cite: 8]

REM --- Check for Docker ---
[cite_start]ECHO "[STEP 1/3] Checking for Docker..." [cite: 9]
[cite_start]docker --version >nul 2>&1 [cite: 9]
[cite_start]if %errorlevel% neq 0 ( [cite: 9]
    [cite_start]ECHO "[ERROR] Docker is not installed or not running." [cite: 9]
    [cite_start]ECHO "Please start Docker Desktop and try again." [cite: 9]
    [cite_start]pause [cite: 9]
    [cite_start]exit /b 1 [cite: 9]
)
[cite_start]ECHO "[SUCCESS] Docker is running." [cite: 9]
[cite_start]ECHO. [cite: 10]

REM --- Build Web Application Image ---
[cite_start]ECHO "[STEP 2/3] Building Web Application Docker image (app.py:latest)..." [cite: 10]
[cite_start]ECHO "This may take several minutes, especially on the first run." [cite: 10]
[cite_start]ECHO "You will now see the Docker build output." [cite: 11]
docker build --no-cache -t app.py:latest -f Dockerfile .
[cite_start]if %errorlevel% neq 0 ( [cite: 13]
    [cite_start]ECHO. [cite: 13]
    [cite_start]ECHO "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" [cite: 13]
    [cite_start]ECHO "[ERROR] Failed to build the Web Application Docker image." [cite: 13]
    [cite_start]ECHO "Please review the build output above for errors." [cite: 13]
    [cite_start]ECHO "Common issues include network problems or errors in the Dockerfile." [cite: 13]
    [cite_start]ECHO "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" [cite: 13]
    [cite_start]pause [cite: 13]
    [cite_start]exit /b 1 [cite: 13]
)
[cite_start]ECHO "[SUCCESS] Web Application image built." [cite: 13]
[cite_start]ECHO. [cite: 14]

REM --- Build Demultiplexing Image (Optional) ---
[cite_start]REM The demultiplexing tool build is currently skipped because the UI feature is disabled. [cite: 14, 15]
[cite_start]REM If you create a 'demux.Dockerfile' in the future, you can re-enable this step. [cite: 15]

REM --- Run Main Application ---
[cite_start]ECHO "[STEP 3/3] Starting the main application..." [cite: 18]
[cite_start]ECHO "Data will be mounted from the 'data' subfolder." [cite: 18]
[cite_start]ECHO "The application will be available at: http://localhost:5000" [cite: 19]
[cite_start]ECHO. [cite: 19]

[cite_start]REM Create data directory if it doesn't exist [cite: 19]
[cite_start]if not exist data ( [cite: 19]
    [cite_start]mkdir data [cite: 19]
    [cite_start]ECHO "Created 'data' directory for your run folders." [cite: 19]
)

[cite_start]REM Run the main Flask app container [cite: 19]
[cite_start]REM It mounts the Docker socket to control other containers [cite: 19]
[cite_start]REM It mounts the 'data' folder for user files [cite: 19]
docker run --rm -it -p 5000:5000 --name app.py ^
-v //var/run/docker.sock:/var/run/docker.sock ^
-v "%cd%/data:/app/data" ^
app.py:latest

[cite_start]ECHO "Application has been shut down." [cite: 19]
[cite_start]pause [cite: 20]
