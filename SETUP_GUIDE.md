# 🚀 DCA Telegram Confirmation System - Complete Setup Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start (5 minutes)](#quick-start-5-minutes)
3. [Detailed Setup](#detailed-setup)
4. [Configuration](#configuration)
5. [Testing & Verification](#testing--verification)
6. [Deploying to Production](#deploying-to-production)
7. [Troubleshooting](#troubleshooting)
8. [Monitoring](#monitoring)

---

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended)
- **Docker**: v20.10+
- **Docker Compose**: v2.0+
- **Python**: 3.10+
- **Disk Space**: 2GB minimum
- **Network**: Outbound HTTPS (for Telegram API)

### Accounts & Credentials
- **Binance API Key** (for futures trading)
- **Telegram Bot Token** (create via @BotFather)
- **Telegram Chat ID** (your personal chat with the bot)

### Getting Telegram Credentials

#### 1. Create Telegram Bot
```bash
# Go to Telegram and message @BotFather
# Commands:
/newbot
# Follow prompts to create bot
# You'll receive: BOT_TOKEN
```

#### 2. Get Your Chat ID
```bash
# Message your new bot
/start

# Then run this to get your chat ID:
curl https://api.telegram.org/bot<BOT_TOKEN>/getUpdates | python3 -m json.tool
# Look for "chat"."id" value
```

---

## Quick Start (5 minutes)

### Step 1: Clone/Copy Project
```bash
# SSH into your server
ssh root@your_server

# Navigate to project directory
cd /root
```

### Step 2: Setup Environment
```bash
cd /root/dca-config

# Create .env file
cat > .env << 'EOF'
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
FREQTRADE_JWT_SECRET=f27e8a9020b54f82df881556110fb855553a7318ac867dcfa6b39c48a417cd85
EXCHANGE_NAME=binance
EXCHANGE_KEY=your_binance_api_key
EXCHANGE_SECRET=your_binance_api_secret
EOF
```

### Step 3: Update Config
```bash
# Edit trading configuration
nano user_data/config.json

# Key settings to update:
# - exchange.key: Your Binance API key
# - exchange.secret: Your Binance API secret
# - telegram.token: Your bot token
# - telegram.chat_id: Your chat ID
```

### Step 4: Start System
```bash
# Export variables
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export FREQTRADE_JWT_SECRET="f27e8a9020b54f82df881556110fb855553a7318ac867dcfa6b39c48a417cd85"

# Start both services
docker-compose -f docker/docker-compose-dca.yml up -d

# Verify
docker-compose -f docker/docker-compose-dca.yml ps
```

### Step 5: Test Telegram
```bash
# Check logs
docker logs dca-webhook -f --tail=20

# You should see:
# "Starting Telegram polling for callback updates..."
```

---

## Detailed Setup

### Directory Structure
```
/root/dca-config/
├── docker/
│   ├── docker-compose-dca.yml      # Container orchestration
│   ├── Dockerfile                  # Webhook image
│   ├── dca_webhook.py              # Webhook server
│   └── dca_telegram_handler.py      # Confirmation handler
├── scripts/
│   ├── dca_webhook.py              # Main webhook (symlink from docker/)
│   └── dca_telegram_handler.py      # Handler (symlink from docker/)
├── strategies/
│   └── FreqAi_NoTank4h.py           # Trading strategy with DCA
├── user_data/
│   ├── config.json                 # Trading configuration
│   ├── dca_confirmations.json       # Order states (auto-created)
│   ├── databases/
│   │   └── a13new.db                # SQLite trade history
│   ├── data/                        # Market data
│   ├── logs/                        # Trading logs
│   └── strategies/                  # Strategy folder
├── .env                            # Environment variables
├── .envrc                          # (Optional) direnv config
├── SETUP_GUIDE.md                  # This file
├── QUICK_REFERENCE.md              # Quick commands
└── README.md                        # Overview
```

### Installation Steps

#### 1. Install Docker & Compose
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y docker.io docker-compose

# Add user to docker group (optional, avoid sudo)
sudo usermod -aG docker $USER
newgrp docker
```

#### 2. Clone Repository
```bash
cd /root
git clone <your-repo-url> dca-config
# OR copy your setup manually
cp -r /root/dca-config .
```

#### 3. Setup Environment File
```bash
cd /root/dca-config

# Create .env with your credentials
cat > .env << 'EOF'
# Telegram Configuration
TELEGRAM_BOT_TOKEN=8570969813:AAHtfrozLhTQb8IQG_SJAO3fQoNbU8_cY5M
TELEGRAM_CHAT_ID=867228586

# Freqtrade
FREQTRADE_JWT_SECRET=f27e8a9020b54f82df881556110fb855553a7318ac867dcfa6b39c48a417cd85

# Binance Exchange
EXCHANGE_NAME=binance
EXCHANGE_KEY=your_key_here
EXCHANGE_SECRET=your_secret_here
EOF

chmod 600 .env  # Secure permissions
```

#### 4. Update config.json
```bash
# Open configuration
nano user_data/config.json

# Update these fields:
{
  "exchange": {
    "name": "binance",
    "key": "YOUR_BINANCE_KEY",
    "secret": "YOUR_BINANCE_SECRET"
  },
  "telegram": {
    "enabled": true,
    "token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  },
  "dry_run": true,  # Set to false for live trading
  "stake_currency": "USDT"
}
```

#### 5. Build Docker Images
```bash
cd /root/dca-config

docker-compose -f docker/docker-compose-dca.yml build --no-cache
```

---

## Configuration

### Environment Variables (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | ✅ | Your Telegram chat ID |
| `FREQTRADE_JWT_SECRET` | ✅ | API authentication secret (keep secure) |
| `EXCHANGE_KEY` | ✅ | Binance API key |
| `EXCHANGE_SECRET` | ✅ | Binance API secret |
| `EXCHANGE_NAME` | ✅ | Exchange (default: binance) |

### config.json Key Settings

```json
{
  "max_open_trades": 30,           // Max simultaneous positions
  "stake_currency": "USDT",        // Base currency
  "dry_run": true,                 // false = real trading
  "margin_mode": "isolated",       // Isolated margin
  "trading_mode": "futures",       // Futures trading
  "leverage": 5.0,                 // Default leverage
  
  "exchange": {
    "name": "binance",
    "key": "...",
    "secret": "...",
    "pair_whitelist": [            // Trading pairs
      "BTC/USDT", "ETH/USDT", ...
    ]
  },
  
  "telegram": {
    "enabled": true,
    "token": "...",
    "chat_id": "..."
  },
  
  "strategy": "FreqAi_NoTank4h",   // Strategy name
  
  "buy_hyperspace": {...},         // Buy parameters
  "sell_hyperspace": {...}         // Sell parameters
}
```

### Strategy Configuration

The DCA strategy has 3 configuration variables in `adjust_trade_position()`:

```python
# In FreqAi_NoTank4h.py
DCA_RSI_TRIGGER = 30        # RSI threshold for DCA
DCA_MAX_TIMES = 3           # Max DCA entries per trade
DCA_STAKE_MULTIPLIER = 1.0  # Stake size multiplier
```

---

## Testing & Verification

### 1. Health Check
```bash
# Check Freqtrade API
curl -s http://localhost:8080/api/v1/ping | python3 -m json.tool

# Output should show: {"status": "pong"}
```

### 2. Webhook Health
```bash
# Check webhook server
curl -s http://localhost:5555/health | python3 -m json.tool

# Output: {"status": "ok", "timestamp": "..."}
```

### 3. Test Telegram Message
```bash
# Send test DCA message
curl -s -X POST https://api.telegram.org/bot<TOKEN>/sendMessage \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "<CHAT_ID>",
    "text": "🚨 **DCA TEST** 🚨\n\nPair: BTC/USDT\nEntry: $45,000\nStake: $100",
    "parse_mode": "Markdown",
    "reply_markup": {
      "inline_keyboard": [[
        {"text": "✅ ACCEPT", "callback_data": "dca_accept_TEST_001"},
        {"text": "❌ DECLINE", "callback_data": "dca_decline_TEST_001"}
      ]]
    }
  }'
```

### 4. Test Button Click
```bash
# Check if webhook detects clicks
docker logs dca-webhook -f --tail=10

# You should see "🎯 CALLBACK DETECTED:" when you click button
```

### 5. Verify Confirmations
```bash
# Check saved confirmations
cat user_data/dca_confirmations.json | python3 -m json.tool

# Should show order status: pending/confirmed/declined
```

---

## Deploying to Production

### Pre-Production Checklist
- [ ] Test with `dry_run: true` for 24+ hours
- [ ] Verify all Telegram messages send correctly
- [ ] Test DCA confirmation workflow 5+ times
- [ ] Monitor logs for errors
- [ ] Check API keys are correct
- [ ] Verify trading pairs are valid
- [ ] Test with small stakes first

### Enable Live Trading
```bash
# Edit config
nano user_data/config.json

# Change this line:
"dry_run": false

# Restart Freqtrade
docker-compose -f docker/docker-compose-dca.yml restart freqtrade-dca

# Verify restart
docker logs freqtrade-dca --tail=20
```

### Monitoring In Production
```bash
# Start live monitoring
python3 monitor_dca.py

# Or view logs directly
docker logs freqtrade-dca -f --tail=50
docker logs dca-webhook -f --tail=20
```

### Backup Important Data
```bash
# Backup configuration and database
tar -czf dca-config-backup-$(date +%Y%m%d).tar.gz \
  user_data/config.json \
  user_data/databases/ \
  user_data/dca_confirmations.json

# Store backup safely
mv dca-config-backup-*.tar.gz /backup/
```

---

## Troubleshooting

### Issue: Telegram messages not sending
```bash
# Check bot token is correct
curl https://api.telegram.org/bot<TOKEN>/getMe

# Check Freqtrade logs for errors
docker logs freqtrade-dca | grep -i telegram

# Solution: Verify TOKEN and CHAT_ID in .env and config.json
```

### Issue: Button clicks not detected
```bash
# Check webhook polling is active
docker logs dca-webhook | grep -i polling

# Should see: "Starting Telegram polling for callback updates..."

# Solution: Restart webhook
docker-compose -f docker/docker-compose-dca.yml restart dca-webhook
```

### Issue: confirmations.json not updating
```bash
# Check file permissions
ls -la user_data/dca_confirmations.json

# Should be: -rw-r--r-- 

# Solution: Fix permissions
chmod 644 user_data/dca_confirmations.json

# Check Docker volume mount
docker inspect freqtrade-dca | grep -A 5 Mounts
```

### Issue: Freqtrade won't start
```bash
# Check logs
docker logs freqtrade-dca

# Common issues:
# 1. Config.json JSON syntax error
python3 -m json.tool user_data/config.json

# 2. Invalid API key
# Verify key in .env and config.json

# 3. Port already in use
netstat -tln | grep 8080
# Kill process: sudo kill <PID>

# 4. Strategy file not found
ls -la strategies/FreqAi_NoTank4h.py
```

### Issue: High CPU/Memory usage
```bash
# Check resources
docker stats

# If Freqtrade uses too much:
# - Reduce max_open_trades
# - Disable unnecessary indicators
# - Reduce update frequency

# Edit config.json:
"max_open_trades": 10,  # Lower value
"timeframe": "15m"      # Longer timeframe
```

---

## Monitoring

### Real-time Dashboard
```bash
# Start monitoring
python3 monitor_dca.py

# Shows:
# - DCA confirmations
# - System status
# - Button clicks
# - Trade activity
```

### View Logs

#### Freqtrade Logs
```bash
# Live monitoring
docker logs freqtrade-dca -f --tail=50

# Search for specific events
docker logs freqtrade-dca | grep -i "dca\|telegram\|bought\|sold"
```

#### Webhook Logs
```bash
# Live monitoring
docker logs dca-webhook -f --tail=20

# Search for callbacks
docker logs dca-webhook | grep "CALLBACK"
```

### Check Status Commands
```bash
# All containers running?
docker-compose -f docker/docker-compose-dca.yml ps

# API responding?
curl http://localhost:8080/api/v1/ping
curl http://localhost:5555/health

# Confirmations file size?
ls -lh user_data/dca_confirmations.json

# Database size?
ls -lh user_data/databases/
```

### Export Trade Data
```bash
# Get open trades
curl -s http://localhost:8080/api/v1/trades/open

# Get closed trades
curl -s http://localhost:8080/api/v1/trades

# Get performance
curl -s http://localhost:8080/api/v1/performance
```

---

## Advanced Configuration

### Custom DCA Parameters
Edit `strategies/FreqAi_NoTank4h.py`:
```python
# Line ~150: DCA trigger settings
def adjust_trade_position(self, pair, trade, current_time, current_rate, ...):
    
    DCA_RSI_TRIGGER = 30       # Lower RSI triggers DCA
    DCA_MAX_TIMES = 3          # Max 3 additional entries
    DCA_STAKE_MULTIPLIER = 1.0 # Same stake as initial
    
    # Modify these values based on backtest results
```

### Scale to Multiple Pairs
```bash
# Add pairs to config.json
"pair_whitelist": [
  "BTC/USDT",
  "ETH/USDT", 
  "SOL/USDT",
  "XRP/USDT"
  # Add more pairs here
]
```

### Increase Leverage
```bash
# Edit config.json
"leverage": 7.5  # Increase from default 5.0

# Warning: Higher leverage = Higher risk!
```

---

## Performance Tuning

### Optimize for Speed
```python
# In config.json
"timeframe": "5m",           # Faster signals
"max_open_trades": 5,        # Fewer trades to manage
"dry_run": false             # Live trading faster
```

### Optimize for Safety
```python
# In config.json
"timeframe": "1h",           # Slower signals
"max_open_trades": 2,        # Lower position count
"dry_run": true              # Test first
```

---

## Security Best Practices

### 1. Protect API Keys
```bash
# Use read-only Binance API key if possible
# Never commit .env to git
echo ".env" >> .gitignore

# Set restrictive permissions
chmod 600 .env
```

### 2. Secure Bot Token
```bash
# Rotate token periodically
# In @BotFather: /mybots > select bot > Edit Bot > Edit Token

# Immediately update .env after rotation
```

### 3. JWT Secret
```bash
# Generate new secret if needed
openssl rand -hex 32
# Update FREQTRADE_JWT_SECRET in .env
```

### 4. Backup Sensitive Data
```bash
# Encrypted backup
tar -czf - user_data/config.json .env | \
  gpg --symmetric --cipher-algo AES256 > backup.tar.gz.gpg

# Store backup securely
```

---

## Running on VPS/Cloud Server

### Recommended VPS Settings
- **CPU**: 2+ cores
- **RAM**: 4GB minimum (8GB recommended)
- **Disk**: 20GB SSD (for data and logs)
- **Bandwidth**: 100+ Mbps

### Setup on VPS
```bash
# SSH into VPS
ssh root@your_vps_ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Continue with normal setup...
```

### Keep Running 24/7
```bash
# Using systemd service
sudo cat > /etc/systemd/system/dca-trading.service << 'EOF'
[Unit]
Description=DCA Telegram Trading Bot
After=docker.service

[Service]
Type=simple
WorkingDirectory=/root/dca-config
ExecStart=docker-compose -f docker/docker-compose-dca.yml up
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable dca-trading
sudo systemctl start dca-trading

# Check status
sudo systemctl status dca-trading
```

---

## Support & Resources

### Get Help
- Check logs: `docker logs freqtrade-dca`
- View configs: `cat user_data/config.json`
- Test API: `curl http://localhost:8080/api/v1/ping`

### Quick Command Reference
```bash
# See QUICK_REFERENCE.md for common commands
cat QUICK_REFERENCE.md
```

### Update Strategy
```bash
# After modifying strategy, restart
docker-compose -f docker/docker-compose-dca.yml restart freqtrade-dca
```

---

## Next Steps

1. ✅ Complete setup using this guide
2. ✅ Test with dry_run: true
3. ✅ Verify Telegram confirmations work
4. ✅ Run strategy for 24 hours
5. ✅ Review logs and confirmations
6. ✅ Enable live trading (dry_run: false)
7. ✅ Monitor first trades carefully
8. ✅ Optimize parameters based on results

---

**Last Updated**: February 18, 2026
**Version**: 1.0
**Status**: Production Ready ✅
