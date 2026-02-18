"""
DCA Telegram Confirmation Handler for Freqtrade
Handles Accept/Decline buttons for DCA orders
"""

import json
import logging
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class DCAConfirmationManager:
    """Manages DCA order confirmations via Telegram"""
    
    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        self.confirmations_file = self.data_dir / "dca_confirmations.json"
        self.load_confirmations()
    
    def load_confirmations(self) -> Dict[str, Any]:
        """Load existing DCA confirmations from disk"""
        if self.confirmations_file.exists():
            try:
                with open(self.confirmations_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load confirmations: {e}")
                return {}
        return {}
    
    def save_confirmations(self, data: Dict[str, Any]) -> bool:
        """Save DCA confirmations to disk"""
        try:
            with open(self.confirmations_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Failed to save confirmations: {e}")
            return False
    
    def add_pending_confirmation(self, dca_id: str, details: Dict[str, Any]) -> bool:
        """Add a pending DCA confirmation"""
        try:
            confirmations = self.load_confirmations()
            confirmations[dca_id] = {
                **details,
                'status': 'pending',
                'timestamp': datetime.now().isoformat(),
                'timeout_minutes': 10
            }
            return self.save_confirmations(confirmations)
        except Exception as e:
            logger.error(f"Error adding pending confirmation: {e}")
            return False
    
    def confirm_dca_order(self, dca_id: str) -> bool:
        """Mark DCA order as confirmed"""
        try:
            confirmations = self.load_confirmations()
            if dca_id in confirmations:
                confirmations[dca_id]['status'] = 'confirmed'
                confirmations[dca_id]['confirmed_at'] = datetime.now().isoformat()
                return self.save_confirmations(confirmations)
            return False
        except Exception as e:
            logger.error(f"Error confirming order: {e}")
            return False
    
    def decline_dca_order(self, dca_id: str, reason: str = "User declined") -> bool:
        """Mark DCA order as declined"""
        try:
            confirmations = self.load_confirmations()
            if dca_id in confirmations:
                confirmations[dca_id]['status'] = 'declined'
                confirmations[dca_id]['reason'] = reason
                confirmations[dca_id]['declined_at'] = datetime.now().isoformat()
                return self.save_confirmations(confirmations)
            return False
        except Exception as e:
            logger.error(f"Error declining order: {e}")
            return False
    
    def get_confirmation_status(self, dca_id: str) -> str:
        """Get status of a specific DCA order"""
        try:
            confirmations = self.load_confirmations()
            if dca_id in confirmations:
                return confirmations[dca_id].get('status', 'unknown')
            return 'not_found'
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return 'error'


def handle_dca_callback(callback_data: str, user_id: int, data_dir: str = ".") -> Dict[str, Any]:
    """
    Handle callback from Telegram button clicks
    Called by Freqtrade RPC telegram module
    """
    manager = DCAConfirmationManager(data_dir)
    
    response = {
        'success': False,
        'message': '',
        'action': None
    }
    
    try:
        if callback_data.startswith('dca_accept_'):
            dca_id = callback_data.replace('dca_accept_', '')
            
            if manager.confirm_dca_order(dca_id):
                response['success'] = True
                response['action'] = 'accept'
                response['message'] = f"✅ DCA Order Confirmed\nOrder ID: {dca_id}\nWill execute at next candle"
                logger.info(f"DCA {dca_id} accepted by user {user_id}")
            else:
                response['message'] = f"❌ Error confirming DCA {dca_id}"
        
        elif callback_data.startswith('dca_decline_'):
            dca_id = callback_data.replace('dca_decline_', '')
            
            if manager.decline_dca_order(dca_id):
                response['success'] = True
                response['action'] = 'decline'
                response['message'] = f"❌ DCA Order Declined\nOrder ID: {dca_id}\nThis DCA order has been skipped"
                logger.info(f"DCA {dca_id} declined by user {user_id}")
            else:
                response['message'] = f"❌ Error declining DCA {dca_id}"
        
        else:
            response['message'] = "Unknown DCA action"
    
    except Exception as e:
        logger.error(f"Error in DCA callback handler: {e}")
        response['message'] = f"Error processing callback: {str(e)}"
    
    return response
