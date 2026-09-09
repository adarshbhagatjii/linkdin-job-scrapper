#!/bin/bash

# run.sh - LinkedIn Job Scraper Launcher with Virtual Environment

echo "=========================================="
echo "💼 LinkedIn Job Scraper Application"
echo "=========================================="
echo ""

# Colors for better output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to kill process on a port
kill_port() {
    if check_port $1; then
        echo -e "${YELLOW}⚠️  Port $1 is in use. Killing the process...${NC}"
        lsof -ti:$1 | xargs kill -9 2>/dev/null
        sleep 2
        echo -e "${GREEN}✅ Port $1 freed${NC}"
    fi
}

# Function to print section header
print_section() {
    echo ""
    echo "=========================================="
    echo -e "${CYAN}$1${NC}"
    echo "=========================================="
    echo ""
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 is not installed. Please install Python 3.8+${NC}"
    exit 1
fi

# Get Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✅ Python version: ${PYTHON_VERSION}${NC}"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3 is not installed. Please install pip${NC}"
    exit 1
fi

# ─── Virtual Environment Setup ──────────────────────────────────────────────

print_section "📦 Virtual Environment Setup"

# Check if .venv exists
if [ -d ".venv" ]; then
    echo -e "${GREEN}✅ Virtual environment already exists${NC}"
else
    echo -e "${YELLOW}🔧 Creating virtual environment...${NC}"
    python3 -m venv .venv
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to create virtual environment${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Virtual environment created successfully${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}🔌 Activating virtual environment...${NC}"
source .venv/bin/activate

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to activate virtual environment${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Virtual environment activated${NC}"
echo -e "${BLUE}🐍 Python: $(which python3)${NC}"
echo -e "${BLUE}📦 pip: $(which pip3)${NC}"

# Upgrade pip
echo -e "${BLUE}⬆️  Upgrading pip...${NC}"
pip3 install --upgrade pip > /dev/null 2>&1
echo -e "${GREEN}✅ pip upgraded${NC}"

# ─── Install Dependencies ──────────────────────────────────────────────────

print_section "📦 Installing Dependencies"

echo -e "${BLUE}Installing Python packages from requirements.txt...${NC}"
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    deactivate
    exit 1
fi

echo -e "${GREEN}✅ All dependencies installed successfully${NC}"

# ─── Install Playwright Browsers ──────────────────────────────────────────

print_section "🌐 Playwright Setup"

echo -e "${BLUE}Checking Playwright browsers...${NC}"

# Check if Playwright is installed
if python3 -c "import playwright" 2>/dev/null; then
    echo -e "${BLUE}Installing Playwright Chromium browser...${NC}"
    playwright install chromium
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to install Playwright browsers${NC}"
        deactivate
        exit 1
    fi
    echo -e "${GREEN}✅ Playwright browsers installed successfully${NC}"
else
    echo -e "${RED}❌ Playwright not installed. Please check requirements.txt${NC}"
    deactivate
    exit 1
fi

# ─── Kill Existing Services ──────────────────────────────────────────────────

print_section "🔄 Service Management"

# Kill any existing processes on ports 8000 and 8080
kill_port 8000
kill_port 8080

# ─── Start Services ──────────────────────────────────────────────────────────

print_section "🚀 Starting Services"

# Start the API server
echo -e "${BLUE}🚀 Starting FastAPI server on port 8000...${NC}"
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 > api.log 2>&1 &
API_PID=$!

echo -e "${YELLOW}⏳ Waiting for API server to start...${NC}"
sleep 3

# Check if API is running
if ! check_port 8000; then
    echo -e "${RED}❌ Failed to start API server${NC}"
    echo -e "${YELLOW}API Log:${NC}"
    tail -20 api.log
    kill $API_PID 2>/dev/null
    deactivate
    exit 1
fi

echo -e "${GREEN}✅ API server is running (PID: $API_PID)${NC}"
echo -e "${BLUE}📡 API: http://localhost:8000${NC}"

# Start HTTP server for frontend
echo -e "${BLUE}🚀 Starting HTTP server for frontend on port 8080...${NC}"
python3 -m http.server 8080 > http.log 2>&1 &
HTTP_PID=$!

echo -e "${YELLOW}⏳ Waiting for HTTP server to start...${NC}"
sleep 2

# Check if HTTP server is running
if check_port 8080; then
    echo -e "${GREEN}✅ HTTP frontend server is running (PID: $HTTP_PID)${NC}"
    echo -e "${BLUE}🌐 Frontend: http://localhost:8080${NC}"
else
    echo -e "${RED}❌ Failed to start HTTP server${NC}"
    kill $API_PID 2>/dev/null
    kill $HTTP_PID 2>/dev/null
    deactivate
    exit 1
fi

# ─── Open Browser ──────────────────────────────────────────────────────────

print_section "🌐 Opening Browser"

echo -e "${BLUE}Opening application in your browser...${NC}"
sleep 2

# Try to open browser on different OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open http://localhost:8080
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8080
    else
        echo -e "${YELLOW}⚠️  Please open http://localhost:8080 in your browser${NC}"
    fi
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows (Git Bash/Cygwin)
    start http://localhost:8080 2>/dev/null || echo -e "${YELLOW}⚠️  Please open http://localhost:8080 in your browser${NC}"
else
    echo -e "${YELLOW}⚠️  Please open http://localhost:8080 in your browser${NC}"
fi

# ─── Display Information ──────────────────────────────────────────────────

echo ""
echo "=========================================="
echo -e "${GREEN}✅ Application is running!${NC}"
echo "=========================================="
echo -e "${BLUE}🌐 Frontend:${NC} http://localhost:8080"
echo -e "${BLUE}📡 API Server:${NC} http://localhost:8000"
echo -e "${BLUE}📚 API Docs:${NC} http://localhost:8000/docs"
echo -e "${BLUE}🔍 Health Check:${NC} http://localhost:8000/health"
echo "=========================================="
echo -e "${BLUE}📁 Virtual Environment:${NC} .venv/"
echo "=========================================="
echo ""
echo -e "${YELLOW}💡 To activate virtual environment manually:${NC}"
echo -e "    source .venv/bin/activate"
echo ""
echo -e "${YELLOW}💡 To run API server manually:${NC}"
echo -e "    source .venv/bin/activate"
echo -e "    uvicorn app:app --host 0.0.0.0 --port 8000"
echo ""
echo -e "${YELLOW}💡 To run frontend server manually:${NC}"
echo -e "    python3 -m http.server 8080"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the application${NC}"
echo ""

# ─── Save PID to file for cleanup ──────────────────────────────────────────

echo $API_PID > api.pid
echo $HTTP_PID > http.pid

# ─── Trap Ctrl+C to kill processes ────────────────────────────────────────

cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down...${NC}"
    
    if [ -f api.pid ]; then
        kill $(cat api.pid) 2>/dev/null
        rm api.pid 2>/dev/null
    fi
    
    if [ -f http.pid ]; then
        kill $(cat http.pid) 2>/dev/null
        rm http.pid 2>/dev/null
    fi
    
    kill $API_PID 2>/dev/null
    kill $HTTP_PID 2>/dev/null
    
    deactivate 2>/dev/null
    
    echo -e "${GREEN}✅ Application stopped${NC}"
    exit
}

# Set trap
trap cleanup INT TERM

# Wait for both processes
wait $API_PID $HTTP_PID
