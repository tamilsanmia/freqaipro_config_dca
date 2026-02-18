# DCA Telegram Confirmation System
## Complete Production Setup for Freqtrade

**Version:** 1.0  
**Last Updated:** February 18, 2026  
**Status:** ✅ Production Ready

---

## 🚀 Quick Start (2 Minutes)

```bash
cd /root/dca-config

# 1. Create environment file
cp config/.env.example .env

# 2. Edit .env with your Telegram credentials
nano .env

# 3. Run deployment script
bash scripts/deploy.sh

# 4. Edit config.json with exchange keys
nano config.json

# 5. Monitor
docker-compose -f docker/docker-compose-dca.yml logs -f
```

---

## 📋 Prerequisites

- Docker & Docker Compose
- Telegram Bot (from @BotFather)
- Freqtrade Account & API Keys (Binance)
- Python 3.10+

---

## 📁 Folder Structure

```
/root/dca-config/
├── config/                          # Configuration files
│   ├── .env.example                # Environment template
│   └── config.json.example         # Freqtrade config template
├── docker/                          # Docker files
│   ├── docker-compose-dca.yml      # Docker Compose configuration
│   └── Dockerfile                   # Webhook server Dockerfile
├── docs/                            # Documentation
│   ├── SETUP.md                     # Setup guide
│   ├── TELEGRAM_SETUP.md            # Telegram configuration
│   ├── TROUBLESHOOTING.md           # Troubleshooting guide
│   └── API.md                       # API documentation
├── scripts/                         # Helper scripts
│   ├── deploy.sh                    # Automated deployment
│   ├── dca_telegram_handler.py      # DCA confirmation handler
│   └── dca_webhook.py               # Webhook server
├── strategies/                      # Trading strategies
│   └── FreqAi_NoTank4h.py          # Main DCA strategy with Telegram integration
├── user_data/                       # Runtime data (created by deploy.sh)
│   ├── strategies/                  # Strategy folder
│   ├── logs/                        # Application logs
│   └── dca_confirmations.json       # DCA order history
├── README.md                        # This file
└── .env                             # Environment variables (create from .env.example)
```

---

## ⚙️ Configuration Steps

### 1. Telegram Bot Setup

1. Open Telegram → Search `@BotFather`
2. Send `/newbot`
3. Bot name: `YourTradingBot`
4. Bot username: `your_trading_bot_xyz` (must be unique)
5. **Save the API Token**

**Get Chat ID:**
1. Search `@userinfobot`
2. Send `/start`
3. Note your **User ID** or **Group ID**

**Enable Buttons:**
- Go back to `@BotFather`
- `/mybots` → Select bot → Settings → Inline buttons → ON

### 2. Exchange API Setup

1. Log in to Binance
2. Settings → API Management
3. Create a new API key
4. Enable Spot/Futures trading
5. **Save Key & Secret**

### 3. Environment Configuration

```bash
# Copy example file
cp config/.env.example .env

# Edit and add your credentials
nano .env
```

Edit these variables:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCDEFGhijklmnopqrstuvwxyz
TELEGRAM_CHAT_ID=987654321
EXCHANGE_KEY=your_binance_api_key
EXCHANGE_SECRET=your_binance_api_secret
FREQTRADE_JWT_SECRET=auto-generated (keep as is)
```

### 4. Freqtrade Configuration

```bash
# Copy example
cp config/config.json.example config.json

# Edit with your settings
nano config.json
```

Key sections:
```json
{
  "exchange": {
    "name": "binance",
    "key": "YOUR_KEY_FROM_ENV",
    "secret": "YOUR_SECRET_FROM_ENV"
  },
  "stake_currency": "USDT",
  "max_open_trades": 3,
  "trading_mode": "futures"
}
```

---

## 🚀 Deployment

### Automated Deployment

```bash
# Make script executable
chmod +x scripts/deploy.sh

# Run deployment
./scripts/deploy.sh

# Answer prompts for:
# - Telegram Bot Token
# - Telegram Chat ID
```

### Manual Deployment

```bash
# 1. Create directories
mkdir -p user_data/{logs,strategies,backtest_results}

# 2. Copy files
cp strategies/FreqAi_NoTank4h.py user_data/strategies/
cp config/config.json.example config.json

# 3. Edit configuration
nano .env
nano config.json

# 4. Build and start Docker
docker-compose -f docker/docker-compose-dca.yml build
docker-compose -f docker/docker-compose-dca.yml up -d

# 5. Verify
curl http://localhost:8080/api/v1/ping
curl http://localhost:5555/health
```

---

## 📊 Service Ports

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| Freqtrade API | 8080 | http://localhost:8080 | Trading API & WebUI |
| Webhook | 5555 | http://localhost:5555 | DCA Confirmations |

---

## 🔄 DCA Confirmation Flow

```
1. DCA triggered (profitable position)
   ↓
2. Telegram message sent with buttons
   - ✅ ACCEPT
   - ❌ DECLINE
   ↓
3. User responds (or 10-minute timeout)
   ↓
4. Decision logged in dca_confirmations.json
   ↓
5. Next candle: Order executes or skips
```

---

## 📱 Telegram Message Example

```
🔄 DCA Order Confirmation Required

Pair: BTC/USDT
DCA Order: #2
Entry Rate: 44,999.50
DCA Stake: 100.00 USDT
Current Profit: -5.50%
Time: 2026-02-18 10:45:30

⏱️ Auto-decline in 10 minutes if no response

Please confirm or decline this DCA order

[✅ ACCEPT] [❌ DECLINE]
```

---

## 📊 Monitoring

### View Logs

```bash
# All services
docker-compose -f docker/docker-compose-dca.yml logs -f

# Freqtrade only
docker logs -f freqtrade-dca

# Webhook only
docker logs -f dca-webhook
```

### Check Confirmations

```bash
# View all DCA orders
cat user_data/dca_confirmations.json | jq '.'

# View pending orders only
cat user_data/dca_confirmations.json | jq '.[] | select(.status=="pending")'

# View accepted orders
cat user_data/dca_confirmations.json | jq '.[] | select(.status=="confirmed")'

# View declined orders
cat user_data/dca_confirmations.json | jq '.[] | select(.status=="declined")'
```

### API Health Checks

```bash
# Freqtrade health
curl http://localhost:8080/api/v1/ping

# Webhook health
curl http://localhost:5555/health

# Webhook callback logs (last 10)
curl http://localhost:5555/status?limit=10
```

---

## 🛠️ Common Commands

### Start/Stop Services

```bash
# Start all services
docker-compose -f docker/docker-compose-dca.yml up -d

# Stop all services
docker-compose -f docker/docker-compose-dca.yml down

# Restart Freqtrade
docker-compose -f docker/docker-compose-dca.yml restart freqtrade-dca

# Restart Webhook
docker-compose -f docker/docker-compose-dca.yml restart dca-webhook

# View running containers
docker-compose -f docker/docker-compose-dca.yml ps
```

### Container Maintenance

```bash
# Check resource usage
docker stats freqtrade-dca dca-webhook

# View container logs (last 100 lines)
docker logs --tail 100 freqtrade-dca

# Clean up old images
docker image prune

# Full cleanup (WARNING: removes all stopped containers)
docker system prune -a
```

### Manual DCA Confirmation (Testing)

```bash
# Accept DCA order
curl -X POST http://localhost:5555/dca_button_callback \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": YOUR_USER_ID,
    "callback_data": "dca_accept_BTC/USDT_2026-02-18_10:30:00_2"
  }'

# Decline DCA order
curl -X POST http://localhost:5555/dca_button_callback \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": YOUR_USER_ID,
    "callback_data": "dca_decline_BTC/USDT_2026-02-18_10:30:00_2"
  }'
```

---

## 🔒 Security Best Practices

1. **Never commit .env or config.json to git**
   ```bash
   echo ".env" >> .gitignore
   echo "config.json" >> .gitignore
   ```

2. **Use strong JWT secrets** (auto-generated by deploy.sh)

3. **Restrict port access**
   ```bash
   # Firewall (UFW)
   sudo ufw allow from 127.0.0.1 to any port 8080
   sudo ufw allow from 127.0.0.1 to any port 5555
   ```

4. **Backup confirmations regularly**
   ```bash
   cp user_data/dca_confirmations.json backups/dca_$(date +%Y%m%d_%H%M%S).json
   ```

5. **Monitor logs for errors**
   ```bash
   docker logs freqtrade-dca 2>&1 | grep -i "error\|warning"
   ```

---

## 🚨 Troubleshooting

### Services not starting

```bash
# Check logs
docker-compose -f docker/docker-compose-dca.yml logs

# Ensure ports are free
lsof -i :8080
lsof -i :5555

# Clear and restart
docker-compose -f docker/docker-compose-dca.yml down --remove-orphans
docker-compose -f docker/docker-compose-dca.yml up -d
```

### Telegram not working

```bash
# Test bot token
curl -X GET "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"

# Test message
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=Test message"
```

### DCA buttons not appearing

- Check `@BotFather` → Bot Settings → Inline buttons (must be ON)
- Restart webhook: `docker-compose -f docker/docker-compose-dca.yml restart dca-webhook`

### Orders auto-declining immediately

- Check system time: `date`
- Verify `dca_confirmation_timeout_minutes=10` in strategy

---

## 📚 Additional Resources

- [Freqtrade Documentation](https://www.freqtrade.io/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [DCA Strategy Theory](https://en.wikipedia.org/wiki/Dollar_cost_averaging)

---

## 📝 Support & Contribution

For issues or improvements:
1. Check logs: `docker logs -f freqtrade-dca`
2. Review troubleshooting section
3. Check Telegram bot configuration

---

**Ready to start trading?** 🚀

Good luck with your DCA strategy!
