#!/usr/bin/env python3
"""
Real-time DCA Confirmation Monitoring Dashboard
Watches for:
1. Freqtrade DCA triggers
2. Telegram confirmation messages
3. User button clicks (webhook callbacks)
4. Order confirmation status updates
"""

import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
import threading

# Color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RED = '\033[91m'
RESET = '\033[0m'
BRIGHT = '\033[1m'

# State tracking
last_freqtrade_log = 0
last_webhook_log = 0
last_confirmations_mod = 0
monitored_orders = {}


def get_freqtrade_logs():
    """Get recent Freqtrade logs"""
    try:
        result = subprocess.run(
            ['docker', 'logs', 'freqtrade-dca', '--tail=50'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout
    except:
        return ""


def get_webhook_logs():
    """Get recent webhook logs"""
    try:
        result = subprocess.run(
            ['docker', 'logs', 'dca-webhook', '--tail=30'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout
    except:
        return ""


def load_confirmations():
    """Load current confirmations from JSON"""
    try:
        path = Path('/root/dca-config/user_data/dca_confirmations.json')
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}


def monitor_freqtrade():
    """Monitor Freqtrade for DCA triggers"""
    logs = get_freqtrade_logs()
    
    # Look for DCA-related messages
    if 'DCA' in logs or 'adjust_trade_position' in logs or 'Telegram' in logs:
        print(f"\n{GREEN}📊 FREQTRADE DCA ACTIVITY DETECTED{RESET}")
        
        # Show relevant lines
        for line in logs.split('\n'):
            if any(keyword in line for keyword in ['DCA', 'adjust_trade', 'telegram', 'trade', 'Sold', 'Bought']):
                if 'DEBUG' not in line:  # Skip debug spam
                    print(f"  {line[:120]}")


def monitor_telegram():
    """Monitor for Telegram messages sent"""
    logs = get_freqtrade_logs()
    
    if 'sendMessage' in logs or 'Telegram' in logs or 'sent' in logs.lower():
        print(f"\n{BLUE}💬 TELEGRAM MESSAGE ACTIVITY{RESET}")
        
        for line in logs.split('\n'):
            if 'telegram' in line.lower() or 'sent' in line.lower():
                if any(x not in line for x in ['DEBUG', 'DEBUG']):
                    print(f"  {line[:120]}")


def monitor_webhooks():
    """Monitor webhook for button clicks"""
    logs = get_webhook_logs()
    
    # Look for callback detections
    if 'CALLBACK DETECTED' in logs or 'accepted' in logs or 'declined' in logs:
        print(f"\n{YELLOW}🔘 TELEGRAM BUTTON CLICKS DETECTED{RESET}")
        
        for line in logs.split('\n'):
            if 'CALLBACK' in line or 'accepted' in line or 'declined' in line:
                if 'INFO' in line or '🎯' in line:
                    print(f"  {line[-100:]}")


def monitor_confirmations():
    """Monitor confirmation file for status changes"""
    confirmations = load_confirmations()
    
    if not confirmations:
        return
    
    print(f"\n{BRIGHT}{BLUE}📋 CURRENT DCA CONFIRMATIONS{RESET}")
    print(f"{'─' * 80}")
    
    confirmed_count = 0
    pending_count = 0
    declined_count = 0
    
    for order_id, details in confirmations.items():
        status = details.get('status', '?')
        pair = details.get('pair', '?')
        entry = details.get('entry_rate', 0)
        stake = details.get('stake', 0)
        
        if status == 'confirmed':
            confirmed_count += 1
            symbol = f"{GREEN}✅{RESET}"
        elif status == 'pending':
            pending_count += 1
            symbol = f"{YELLOW}⏳{RESET}"
        elif status == 'declined':
            declined_count += 1
            symbol = f"{RED}❌{RESET}"
        else:
            symbol = "❓"
        
        timestamp = details.get('timestamp', '')[:19]
        
        print(f"{symbol} {pair:12} @ ${entry:>10.2f} | ${stake:>7.2f} USDT | [{status:9}] {timestamp}")
    
    print(f"{'─' * 80}")
    print(f"{GREEN}Confirmed:{RESET} {confirmed_count}  {YELLOW}Pending:{RESET} {pending_count}  {RED}Declined:{RESET} {declined_count}")


def show_dashboard():
    """Display full monitoring dashboard"""
    while True:
        # Clear screen on Unix
        subprocess.run(['clear'], capture_output=True)
        
        print(f"\n{BRIGHT}{'='*80}{RESET}")
        print(f"{BRIGHT}🚀 REAL-TIME DCA CONFIRMATION MONITORING{RESET}")
        print(f"{BRIGHT}{'='*80}{RESET}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Monitor all sources
        monitor_freqtrade()
        monitor_telegram()
        monitor_webhooks()
        monitor_confirmations()
        
        # Status checks
        print(f"\n{BRIGHT}🔍 SYSTEM STATUS{RESET}")
        try:
            ft_result = subprocess.run(['curl', '-s', 'http://localhost:8080/api/v1/ping'], 
                                      capture_output=True, text=True, timeout=2)
            ft_status = "✅ Running" if ft_result.returncode == 0 else "❌ Error"
        except:
            ft_status = "❌ Unavailable"
        
        try:
            wh_result = subprocess.run(['curl', '-s', 'http://localhost:5555/health'],
                                      capture_output=True, text=True, timeout=2)
            wh_status = "✅ Running" if wh_result.returncode == 0 else "❌ Error"
        except:
            wh_status = "❌ Unavailable"
        
        print(f"  Freqtrade:  {ft_status}")
        print(f"  Webhook:    {wh_status}")
        
        print(f"\n{BRIGHT}{'='*80}{RESET}")
        print(f"Refreshing in 5 seconds... (Press Ctrl+C to exit)")
        print(f"{'='*80}{RESET}\n")
        
        time.sleep(5)


if __name__ == '__main__':
    try:
        show_dashboard()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}📊 Monitoring stopped{RESET}")
