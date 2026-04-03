#!/bin/bash
# MediTutor AI — Mac/Linux Setup & Start Script

set -e

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
BLUE="\033[34m"
RESET="\033[0m"

echo -e "${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║     MediTutor AI — Mac/Linux Setup       ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Check Python ──────────────────────────────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python 3 not found. Install via: brew install python3 (Mac) or sudo apt install python3 (Linux)${RESET}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✅ Python $PYTHON_VERSION found${RESET}"

# ── Setup .env ────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Created .env — please edit it and add your API keys, then re-run this script.${RESET}"
    echo ""
    echo "  Edit with:  nano .env"
    echo "  Then run:   bash setup.sh"
    exit 0
fi

# ── Backend venv ──────────────────────────────────────────────────────────────
echo -e "\n${BOLD}[1/4] Setting up backend...${RESET}"
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo -e "${GREEN}✅ Backend dependencies installed${RESET}"
deactivate
cd ..

# ── Frontend venv ─────────────────────────────────────────────────────────────
echo -e "\n${BOLD}[2/4] Setting up frontend...${RESET}"
cd frontend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo -e "${GREEN}✅ Frontend dependencies installed${RESET}"
deactivate
cd ..

echo -e "\n${BOLD}[3/4] Checking API keys...${RESET}"
source .env 2>/dev/null || true

if [ -z "$GROQ_API_KEY" ] || [ "$GROQ_API_KEY" = "your_groq_api_key_here" ]; then
    echo -e "${YELLOW}⚠️  GROQ_API_KEY not set in .env${RESET}"
else
    echo -e "${GREEN}✅ Groq API key found${RESET}"
fi

if [ -z "$HUGGINGFACE_API_KEY" ] || [ "$HUGGINGFACE_API_KEY" = "your_huggingface_token_here" ]; then
    echo -e "${YELLOW}⚠️  HUGGINGFACE_API_KEY not set in .env${RESET}"
else
    echo -e "${GREEN}✅ HuggingFace API key found${RESET}"
fi

echo -e "\n${BOLD}[4/4] Setup complete!${RESET}"
echo ""
echo -e "${BOLD}To start the app, run in TWO separate terminals:${RESET}"
echo ""
echo -e "  ${GREEN}Terminal 1 (Backend):${RESET}"
echo -e "    cd backend && source venv/bin/activate"
echo -e "    uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo -e "  ${GREEN}Terminal 2 (Frontend):${RESET}"
echo -e "    cd frontend && source venv/bin/activate"
echo -e "    streamlit run app.py"
echo ""
echo -e "  ${BLUE}Then open: http://localhost:8501${RESET}"
echo ""

# ── OR: offer to start both now ───────────────────────────────────────────────
read -p "Start both services now in background? (y/N): " START_NOW
if [[ "$START_NOW" =~ ^[Yy]$ ]]; then
    echo "Starting backend on port 8000..."
    cd backend && source venv/bin/activate
    uvicorn main:app --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    deactivate
    cd ..

    sleep 3

    echo "Starting frontend on port 8501..."
    cd frontend && source venv/bin/activate
    streamlit run app.py &
    FRONTEND_PID=$!
    deactivate
    cd ..

    echo -e "\n${GREEN}✅ Both services started!${RESET}"
    echo -e "  Backend PID:  $BACKEND_PID"
    echo -e "  Frontend PID: $FRONTEND_PID"
    echo -e "\n  ${BLUE}Open: http://localhost:8501${RESET}"
    echo ""
    echo "  To stop: kill $BACKEND_PID $FRONTEND_PID"
fi
