#!/usr/bin/env python3
"""
Run the integrated FastAPI + React application
This script builds the frontend (if needed) and starts the backend server
"""
import os
import sys
import subprocess
from pathlib import Path

# Get the root directory
ROOT_DIR = Path(__file__).parent
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_DIR = ROOT_DIR / "backend"
DIST_DIR = FRONTEND_DIR / "dist"

def build_frontend():
    """Build the React frontend"""
    print("Building React frontend...")
    print("=" * 50)

    # Check if node_modules exists
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print("Installing frontend dependencies...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=FRONTEND_DIR,
            shell=True
        )
        if result.returncode != 0:
            print("✗ Failed to install dependencies!")
            return False

    # Build the frontend
    print("Running production build...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND_DIR,
        shell=True
    )

    if result.returncode == 0:
        print("✓ Frontend build completed successfully!")
        print(f"Build output location: {DIST_DIR}")
        return True
    else:
        print("✗ Frontend build failed!")
        return False

def run_integrated_server():
    """Run the integrated FastAPI server"""
    print("\nStarting PDF Processor (Integrated Mode)...")
    print("=" * 50)

    # Check if frontend is built
    if not DIST_DIR.exists():
        print("Frontend not built. Building now...")
        if not build_frontend():
            print("\nBuild failed. Cannot start integrated service.")
            sys.exit(1)
    else:
        print("✓ Frontend build found")

    # Change to backend directory
    os.chdir(BACKEND_DIR)

    # Check for virtual environment
    venv_python = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        python_cmd = str(venv_python)
        print(f"Using virtual environment: {venv_python}")
    else:
        python_cmd = sys.executable
        print(f"Using system Python: {python_cmd}")

    print("\n" + "=" * 50)
    print("Integrated service starting on http://localhost:8000")
    print("Frontend and API both accessible from this single port")
    print("API Documentation: http://localhost:8000/docs")
    print("Press Ctrl+C to stop")
    print("=" * 50 + "\n")

    # Run the server
    try:
        subprocess.run([python_cmd, "run.py"])
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        sys.exit(0)

if __name__ == "__main__":
    run_integrated_server()
