#!/bin/bash

##########################################################
# DCA Telegram Confirmation - Automated Deployment Script
##########################################################

set -e

echo "=========================================="
echo "  DCA Telegram Confirmation Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo -e "${YELLOW}Step 1: Checking prerequisites...${NC}"
for cmd in docker docker-compose python3 curl; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}Error: $cmd is not installed${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ All prerequisites found${NC}"
echo ""

# Step 2: Create directory structure
echo -e "${YELLOW}Step 2: Creating directory structure...${NC}"
mkdir -p user_data/logs
mkdir -p user_data/strategies
mkdir -p user_data/backtest_results
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Step 3: Get Telegram credentials
echo -e "${YELLOW}Step 3: Telegram Configuration${NC}"
read -p "Enter Telegram Bot Token: " BOT_TOKEN
read -p "Enter Telegram Chat ID: " CHAT_ID

# Validate token format
if [[ ! $BOT_TOKEN =~ ^[0-9]+:.*$ ]]; then
    echo -e "${RED}Error: Invalid Bot Token format${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Telegram credentials saved${NC}"
echo ""

# Step 4: Create .env file
echo -e "${YELLOW}Step 4: Creating environment file...${NC}"
if [ ! -f ".env" ]; then
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    cat > .env << EOF
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
TELEGRAM_CHAT_ID=$CHAT_ID
FREQTRADE_JWT_SECRET=$JWT_SECRET
EXCHANGE_NAME=binance
EXCHANGE_KEY=YOUR_EXCHANGE_KEY
EXCHANGE_SECRET=YOUR_EXCHANGE_SECRET
EOF
    echo -e "${GREEN}✓ .env file created${NC}"
else
    echo -e "${YELLOW}! .env file already exists, skipping${NC}"
fi
echo ""

# Step 5: Copy config template
echo -e "${YELLOW}Step 5: Setting up configuration files...${NC}"
if [ ! -f "config.json" ]; then
    echo "⚠️  config.json not found!"
    echo "Creating from template..."
    cp config/config.json.example config.json
    sed -i "s|\${TELEGRAM_BOT_TOKEN}|$BOT_TOKEN|g" config.json
    sed -i "s|\${TELEGRAM_CHAT_ID}|$CHAT_ID|g" config.json
    echo -e "${YELLOW}Please edit config.json with your exchange API keys${NC}"
else
    echo -e "${GREEN}✓ config.json found${NC}"
fi
echo ""

# Step 6: Copy strategy
echo -e "${YELLOW}Step 6: Setting up strategy...${NC}"
if [ ! -f "user_data/strategies/FreqAi_NoTank4h.py" ]; then
    cp strategies/FreqAi_NoTank4h.py user_data/strategies/
    echo -e "${GREEN}✓ Strategy copied${NC}"
else
    echo -e "${GREEN}✓ Strategy already exists${NC}"
fi
echo ""

# Step 7: Build Docker images
echo -e "${YELLOW}Step 7: Building Docker images...${NC}"
docker-compose -f docker/docker-compose-dca.yml build
echo -e "${GREEN}✓ Docker images built${NC}"
echo ""

# Step 8: Start services
echo -e "${YELLOW}Step 8: Starting services...${NC}"
export $(cat .env | xargs)
docker-compose -f docker/docker-compose-dca.yml up -d
echo -e "${GREEN}✓ Services started${NC}"
echo ""

# Step 9: Wait for services to be ready
echo -e "${YELLOW}Step 9: Waiting for services to start (30 seconds)...${NC}"
sleep 30

# Step 10: Verify services
echo -e "${YELLOW}Step 10: Verifying services...${NC}"

# Check Freqtrade
if curl -s http://localhost:8080/api/v1/ping > /dev/null; then
    echo -e "${GREEN}✓ Freqtrade API responding${NC}"
else
    echo -e "${RED}✗ Freqtrade API not responding${NC}"
    echo "  Try: docker logs -f freqtrade-dca"
fi

# Check Webhook
if curl -s http://localhost:5555/health > /dev/null; then
    echo -e "${GREEN}✓ Webhook server responding${NC}"
else
    echo -e "${RED}✗ Webhook server not responding${NC}"
    echo "  Try: docker logs -f dca-webhook"
fi

# Test Telegram
echo -e "${YELLOW}Step 11: Testing Telegram connection...${NC}"
RESPONSE=$(curl -s -X GET "https://api.telegram.org/bot${BOT_TOKEN}/getMe" | python3 -c "import sys, json; print(json.load(sys.stdin).get('ok', False))" 2>/dev/null || echo "False")
if [ "$RESPONSE" = "True" ]; then
    echo -e "${GREEN}✓ Telegram bot verified${NC}"
else
    echo -e "${RED}✗ Telegram bot token invalid${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✓ DCA Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "📊 Service URLs:"
echo "  - Freqtrade API: http://localhost:8080"
echo "  - Webhook Server: http://localhost:5555"
echo ""
echo "📋 Next Steps:"
echo "  1. Edit config.json with your Exchange API keys"
echo "  2. Verify Telegram bot is enabled in @BotFather"
echo "  3. Monitor logs: docker-compose -f docker/docker-compose-dca.yml logs -f"
echo "  4. View confirmations: cat user_data/dca_confirmations.json"
echo ""
echo "📚 Documentation: docs/"
echo ""
echo "Starting trade... Good luck! 🚀"
