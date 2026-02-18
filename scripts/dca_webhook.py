"""
Webhook server for handling Telegram DCA button callbacks with polling
Run this alongside Freqtrade
"""

from flask import Flask, request, jsonify
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
import requests
import threading
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dca_telegram_handler import handle_dca_callback

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store last status for monitoring
status_log = []

# Get data directory from environment or use current directory
DATA_DIR = os.getenv('DATA_DIR', '/freqtrade/user_data')

# Polling state
last_update_id = 0
polling_active = False


def show_loading_toast(callback_query_id, bot_token):
    """Show loading indicator toast to user"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_query_id,
            "text": "⏳ Processing your confirmation...",
            "show_alert": False
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Error showing loading toast: {e}")


def poll_telegram_updates():
    """Poll Telegram for callback_query updates"""
    global last_update_id, polling_active
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return
    
    polling_active = True
    logger.info("Starting Telegram polling for callback updates...")
    
    while polling_active:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            payload = {
                "offset": last_update_id + 1,
                "allowed_updates": ["callback_query"],
                "timeout": 30
            }
            
            response = requests.post(url, json=payload, timeout=45)
            result = response.json()
            
            if result.get('ok'):
                updates = result.get('result', [])
                
                for update in updates:
                    last_update_id = update['update_id']
                    
                    if 'callback_query' in update:
                        callback = update['callback_query']
                        user_id = callback['from']['id']
                        callback_data = callback.get('data', '')
                        callback_query_id = callback['id']
                        message = callback.get('message', {})
                        message_id = message.get('message_id')
                        chat_id = message.get('chat', {}).get('id')
                        
                        # Only process DCA callbacks
                        if 'dca_' in callback_data:
                            logger.info(f"🎯 CALLBACK DETECTED: {callback_data} from user {user_id}")
                            
                            # Show loading toast
                            show_loading_toast(callback_query_id, bot_token)
                            
                            # Process callback
                            result_status = handle_dca_callback(callback_data, user_id, DATA_DIR)
                            
                            # Update message with result
                            if message_id and chat_id:
                                update_message_with_result(
                                    bot_token,
                                    chat_id,
                                    message_id,
                                    result_status,
                                    callback_data
                                )
                            
                            # Log status
                            status_log.append({
                                'timestamp': datetime.now().isoformat(),
                                'user_id': user_id,
                                'callback': callback_data,
                                'result': result_status
                            })
                            
                            if len(status_log) > 1000:
                                status_log.pop(0)
            else:
                logger.error(f"Telegram API error: {result}")
        
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)
    
    logger.info("Polling stopped")


def start_polling_thread():
    """Start polling in background thread"""
    thread = threading.Thread(target=poll_telegram_updates, daemon=True)
    thread.start()
    return thread


def update_message_with_result(bot_token, chat_id, message_id, result, callback_data):
    """Update message with final result"""
    try:
        action = "accept" if "accept" in callback_data else "decline"
        
        if action == "accept":
            # Parse order ID from callback_data
            order_id = callback_data.replace("dca_accept_", "")
            new_text = f"""
✅ *DCA ORDER ACCEPTED*

📊 *Order Confirmed*
Order ID: {order_id}

✅ Status: Will execute at next candle
⏰ Time: {datetime.now().strftime('%H:%M:%S')}

🚀 Your DCA entry is queued for execution
"""
        else:
            order_id = callback_data.replace("dca_decline_", "")
            new_text = f"""
❌ *DCA ORDER DECLINED*

📊 *Order Skipped*
Order ID: {order_id}

🚫 Status: This DCA has been skipped
⏰ Time: {datetime.now().strftime('%H:%M:%S')}
⏱️ Retry: Available in 30 minutes
"""
        
        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": new_text,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload, timeout=5)
        logger.info(f"Message updated for {order_id}")
    except Exception as e:
        logger.error(f"Error updating message: {e}")


@app.route('/dca_button_callback', methods=['POST'])
def dca_button_callback():
    """
    Handle DCA button callbacks from Telegram with loading indicator
    Expected JSON: {
        "user_id": 123456, 
        "callback_data": "dca_accept_PAIR_TIMESTAMP_NUMBER",
        "callback_query_id": "telegram_query_id",
        "message_id": 123
    }
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        callback_data = data.get('callback_data')
        callback_query_id = data.get('callback_query_id')
        message_id = data.get('message_id')
        chat_id = data.get('chat_id')
        
        if not user_id or not callback_data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        logger.info(f"Received callback: {callback_data} from user {user_id}")
        
        # Show loading toast to user
        if callback_query_id:
            show_loading_toast(callback_query_id, os.getenv('TELEGRAM_BOT_TOKEN'))
        
        # Process callback
        result = handle_dca_callback(callback_data, user_id, DATA_DIR)
        
        # Update message with result if we have message_id and chat_id
        if message_id and chat_id:
            update_message_with_result(
                os.getenv('TELEGRAM_BOT_TOKEN'),
                chat_id,
                message_id,
                result,
                callback_data
            )
        
        # Log status
        status_log.append({
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'callback': callback_data,
            'result': result
        })
        
        # Keep only last 1000 entries
        if len(status_log) > 1000:
            status_log.pop(0)
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()}), 200


@app.route('/status', methods=['GET'])
def status():
    """Get recent callback status"""
    limit = request.args.get('limit', 10, type=int)
    return jsonify({
        'total_callbacks': len(status_log),
        'recent': status_log[-limit:] if status_log else []
    }), 200


@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    """Clear status logs"""
    global status_log
    count = len(status_log)
    status_log = []
    return jsonify({'message': f'Cleared {count} log entries'}), 200


if __name__ == '__main__':
    port = int(os.getenv('WEBHOOK_PORT', '5555'))
    host = os.getenv('WEBHOOK_HOST', '0.0.0.0')
    logger.info(f"Starting DCA Webhook Server on {host}:{port}")
    logger.info(f"Data directory: {DATA_DIR}")
    
    # Start polling thread
    logger.info("🔔 Starting Telegram polling thread for callbacks...")
    start_polling_thread()
    
    # Start Flask app
    app.run(host=host, port=port, debug=False, threaded=True)
