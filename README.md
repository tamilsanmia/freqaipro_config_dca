# DCA Telegram Confirmation System
## Complete Production Setup for Freqtrade

**Version:** 2.0 - Dual-Bot Configuration  
**Last Updated:** February 18, 2026  
**Status:** ✅ Production Ready & Tested

### 🆕 Latest Features
- **Dual Telegram Bots**: Separate DCA confirmation & trade alert bots
- **Dual Timeframe Entries**: 1h + 4h separated entry signals
- **Webhook System**: Direct Telegram API callbacks for DCA approval
- **Persistent Volume**: Database accessible on host filesystem
- **Explicit Command Configuration**: All args hardcoded for consistency

---

## 🚀 Quick Start (5 Minutes)

```bash
cd /root/dca-trading

# 1. Setup environment with both bot tokens
cp .env.example .env
nano .env  # Add DCA_BOT_TOKEN and ALERT_BOT_TOKEN

# 2. Verify config.json has your exchange keys
nano user_data/config.json

# 3. Deploy
docker compose -f docker/docker-compose-dca.yml --env-file .env up -d --build

# 4. Verify health (wait 30 seconds for startup)
curl http://localhost:8001/api/v1/ping           # Should return {"status":"pong"}
curl http://localhost:5555/health                # Should return {"status":"ok",...}

# 5. Monitor
docker logs freqtrade-dca -f
```

---

## 📋 Prerequisites

- Docker & Docker Compose (both services)
- **2 Telegram Bots** (created from @BotFather):
  - DCA Confirmation Bot: receives webhook callbacks for order approval
  - Alert Bot: sends trade entry/exit notifications
- Binance API Keys (Futures trading enabled)
- Python 3.10+ (for direct development; Docker handles this)

### Telegram Setup - Dual Bot Configuration

**Bot 1: DCA Confirmation Bot**
- Purpose: Receives callback buttons for manual DCA approval
- Setup: `@BotFather` → `/newbot` → Name it "DCA_ConfirmBot"
- Inline buttons: Enable in BotFather
- Token: Save as `DCA_BOT_TOKEN` in .env

**Bot 2: Alert Bot**
- Purpose: Sends trade entry/exit notifications automatically
- Setup: `@BotFather` → `/newbot` → Name it "TradeAlertBot"
- Token: Save as `ALERT_BOT_TOKEN` in .env

**Chat ID:**
1. Create a Telegram group or use personal chat
2. Add both bots to the group (or your personal chat)
3. Message `@userinfobot` to get your chat ID
4. Save as `TELEGRAM_CHAT_ID` in .env (for groups, will be negative)

---

## 📁 Folder Structure

```
/root/dca-trading/
├── docker/
│   ├── docker-compose-dca.yml      # Dual-service orchestration
│   ├── Dockerfile                  # Webhook server image
│   ├── dca_webhook.py              # Webhook callback handler
│   └── dca_telegram_handler.py      # DCA approval handler
├── user_data/
│   ├── config.json                 # Freqtrade main config
│   ├── .env                        # Environment vars (DCA_BOT_TOKEN, ALERT_BOT_TOKEN)
│   ├── tradesv3.sqlite             # SQLite database (on host volume)
│   ├── strategies/
│   │   └── FreqAi_NoTank4h.py      # Main strategy (dual 1h/4h entries)
│   ├── logs/
│   ├── data/
│   ├── backtest_results/
│   └── hyperopts/
├── README.md                       # This file
├── SETUP_GUIDE.md                  # Detailed setup instructions
├── .env                            # Environment variables (creates from template)
└── .gitignore                      # Excludes secrets and database
```

---

## ⚙️ Configuration Steps

### 1. Telegram Bots Setup

**Create DCA Confirmation Bot:**
1. Telegram → `@BotFather` → `/newbot`
2. Name: `DCA_ConfirmBot`
3. Save the token → Add to `.env` as `DCA_BOT_TOKEN`
4. `/mybots` → Select bot → Settings → Buttons → Inline buttons: **ON**

**Create Alert Bot:**
1. Telegram → `@BotFather` → `/newbot`
2. Name: `TradeAlertBot`
3. Save the token → Add to `.env` as `ALERT_BOT_TOKEN`

**Get Chat ID (for both bots):**
1. Create Telegram group or use personal chat
2. Add both bots to the group
3. Message `@userinfobot` → `/start`
4. Note the ID → Add to `.env` as `TELEGRAM_CHAT_ID` (negative for groups)

### 2. Exchange API Setup

1. Log in to Binance
2. Settings → API Management → Create API Key
3. Enable **Futures** trading
4. ✅ Enable IP restrictions for security
5. Save Key & Secret → Add to `user_data/config.json`

### 3. Environment Configuration

```bash
# Copy template
cp .env.example .env

# Edit with your credentials
nano .env
```

Required variables:
```env
# Telegram Bots (REQUIRED - different tokens!)
DCA_BOT_TOKEN=8393793378:AAGLeJWdcnI8Uuq8...
ALERT_BOT_TOKEN=8167537377:AAG89NTbpOOD...
TELEGRAM_CHAT_ID=-1003644445285

# Freqtrade
FREQTRADE_JWT_SECRET=f27e8a9020b54f82df881556110fb855553a7318ac867dcfa6b39c48a417cd85

# Authorized users (for Telegram commands)
AUTHORIZED_USERS=["867228586","2130016467"]
```

### 4. Freqtrade Configuration

Edit `user_data/config.json`:
```json
{
  "exchange": {
    "name": "binance",
    "key": "your_api_key_here",
    "secret": "your_api_secret_here"
  },
  "stake_currency": "USDT",
  "dry_run": true,
  "trading_mode": "futures",
  "margin_mode": "isolated",
  "max_open_trades": 30,
  "strategy_path": "user_data/strategies/",
  "strategy": "FreqAi_NoTank4h",
  "telegram": {
    "enabled": true,
    "token": "{{ will be set from ALERT_BOT_TOKEN env var }}",
    "chat_id": "{{ will be set from TELEGRAM_CHAT_ID env var }}"
  }
}
```

---

## 🚀 Deployment

### Quick Deployment

```bash
cd /root/dca-trading

# 1. Build and start services
docker compose -f docker/docker-compose-dca.yml --env-file .env up -d --build

# 2. Wait 30 seconds for services to spin up
sleep 30

# 3. Verify Freqtrade API (port 8001)
curl http://localhost:8001/api/v1/ping
# Expected: {"status":"pong"}

# 4. Verify Webhook health (port 5555)
curl http://localhost:5555/health
# Expected: {"status":"ok","timestamp":"..."}

# 5. Check container health
docker ps --format "table {{.Names}}\t{{.Status}}"
# Expected: HEALTHY for both freqtrade-dca and dca-webhook
```

### Detailed Deployment

```bash
# 1. Create environment file
cd /root/dca-trading
cp .env.example .env
nano .env  # Add both bot tokens, chat ID, JWT secret

# 2. Update config
nano user_data/config.json  # Add Binance API keys

# 3. Build images (first time only)
docker compose -f docker/docker-compose-dca.yml build

# 4. Start services with explicit args (logs, db location, config, strategy)
docker compose -f docker/docker-compose-dca.yml --env-file .env up -d

# 5. Tail logs
docker logs -f freqtrade-dca

# 6. Stop services
docker compose -f docker/docker-compose-dca.yml down
```

### Docker Command Configuration

The `docker-compose-dca.yml` uses explicit Freqtrade command args:
```yaml
command: >
  trade
  --logfile /freqtrade/user_data/logs/freqtrade.log
  --db-url sqlite:////freqtrade/user_data/tradesv3.sqlite
  --config /freqtrade/user_data/config.json
  --strategy FreqAi_NoTank4h
```

This ensures:
- ✅ Logfile written to host volume
- ✅ Database accessible on host (not locked in container)
- ✅ Explicit config path prevents relative path issues
- ✅ Strategy name hardcoded for consistency

---

## 📊 Service Ports & Endpoints

| Service | Host Port | Container Port | URL | Purpose |
|---------|-----------|-----------------|-----|---------|
| Freqtrade API | 8001 | 8080 | http://localhost:8001 | REST API & WebUI |
| Freqtrade WebSocket | 8001 | 8080 | ws://localhost:8001 | Real-time updates |
| Webhook Handler | 5555 | 5555 | http://localhost:5555 | DCA callbacks |
| Webhook Health | 5555 | 5555 | http://localhost:5555/health | Health check |

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
