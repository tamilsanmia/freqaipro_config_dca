import logging
import os
import warnings
from datetime import datetime, timezone
import json
from pathlib import Path

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)
import talib.abstract as ta

import numpy as np
from pandas import DataFrame
from typing import Optional
from freqtrade.persistence import Trade
import requests
from freqtrade.strategy import (
    IStrategy,
    informative,  # @informative decorator
    # Hyperopt Parameters
    BooleanParameter,
    DecimalParameter,
    IntParameter,
    stoploss_from_open,
)
from scipy.signal import argrelextrema
import pandas as pd

warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)


class FreqAi_NoTank4h(IStrategy):
    exit_profit_only = True
    trailing_stop = False
    position_adjustment_enable = True
    ignore_roi_if_entry_signal = True
    max_entry_position_adjustment = 2
    max_dca_multiplier = 1
    process_only_new_candles = True
    can_short = True
    use_exit_signal = True
    startup_candle_count: int = 200
    stoploss = -0.99
    use_custom_stoploss = True
    timeframe = "15m"
    informative_timeframe = "4h"

    # DCA
    initial_safety_order_trigger = DecimalParameter(
        low=-0.02, high=-0.01, default=-0.018, decimals=3, space="entry", optimize=True, load=True
    )
    max_safety_orders = IntParameter(1, 6, default=3, space="entry", optimize=True)
    safety_order_step_scale = DecimalParameter(
        low=1.05, high=1.5, default=1.25, decimals=2, space="entry", optimize=True, load=True
    )
    safety_order_volume_scale = DecimalParameter(
        low=1.1, high=2, default=1.4, decimals=1, space="entry", optimize=True, load=True
    )

    # Custom Functions
    increment = DecimalParameter(
        low=1.0005, high=1.002, default=1.001, decimals=4, space="entry", optimize=True, load=True
    )
    last_entry_price = None
    
    # DCA Confirmation tracking
    dca_pending_confirmations = {}
    dca_confirmed_orders = {}
    dca_declined_orders = set()
    dca_confirmation_timeout_minutes = 10  # Auto-decline after 10 minutes without response

    # Protections
    cooldown_lookback = IntParameter(2, 48, default=1, space="protection", optimize=True)
    stop_duration = IntParameter(12, 200, default=4, space="protection", optimize=True)
    use_stop_protection = BooleanParameter(default=True, space="protection", optimize=True)

    minimal_roi = {
        "0": 0.5,
        "60": 0.45,
        "120": 0.4,
        "240": 0.3,
        "360": 0.25,
        "720": 0.2,
        "1440": 0.15,
        "2880": 0.1,
        "3600": 0.05,
        "7200": 0.02,
    }

    plot_config = {
        "main_plot": {},
        "subplots": {
            "extrema": {
                "&s-extrema": {"color": "#f53580", "type": "line"},
                "&s-minima_sort_threshold": {"color": "#4ae747", "type": "line"},
                "&s-maxima_sort_threshold": {"color": "#5b5e4b", "type": "line"},
            },
            "min_max": {
                "maxima": {"color": "#a29db9", "type": "line"},
                "minima": {"color": "#ac7fc", "type": "line"},
                "maxima_check": {"color": "#a29db9", "type": "line"},
                "minima_check": {"color": "#ac7fc", "type": "line"},
            },
        },
    }

    @property
    def protections(self):
        prot = []
        prot.append(
            {"method": "CooldownPeriod", "stop_duration_candles": self.cooldown_lookback.value}
        )
        if self.use_stop_protection.value:
            prot.append(
                {
                    "method": "StoplossGuard",
                    "lookback_period_candles": 24 * 3,
                    "trade_limit": 2,
                    "stop_duration_candles": self.stop_duration.value,
                    "only_per_pair": False,
                }
            )
        return prot

    def custom_stake_amount(
            self,
            pair: str,
            current_time: datetime,
            current_rate: float,
            proposed_stake: float,
            min_stake: Optional[float],
            max_stake: float,
            leverage: float,
            entry_tag: Optional[str],
            side: str,
            **kwargs,
    ) -> float:
        return (proposed_stake * 0.3) / self.max_dca_multiplier

    def custom_entry_price(
            self,
            pair: str,
            trade: Optional["Trade"],
            current_time: datetime,
            proposed_rate: float,
            entry_tag: Optional[str],
            side: str,
            **kwargs,
    ) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(
            pair=pair, timeframe=self.timeframe
        )
        entry_price = (dataframe["close"].iloc[-1] + dataframe["open"].iloc[-1] + proposed_rate) / 3
        if proposed_rate < entry_price:
            entry_price = proposed_rate

        logger.info(
            f"{pair} Using Entry Price: {entry_price} | close: {dataframe['close'].iloc[-1]} open: {dataframe['open'].iloc[-1]} proposed_rate: {proposed_rate}"
        )

        if self.last_entry_price is not None and abs(entry_price - self.last_entry_price) < 0.0005:
            entry_price *= self.increment.value
            logger.info(
                f"{pair} Incremented entry price: {entry_price} based on previous entry price : {self.last_entry_price}."
            )

        self.last_entry_price = entry_price

        return entry_price

    def confirm_trade_exit(
            self,
            pair: str,
            trade: Trade,
            order_type: str,
            amount: float,
            rate: float,
            time_in_force: str,
            exit_reason: str,
            current_time: datetime,
            **kwargs,
    ) -> bool:
        if exit_reason == "partial_exit" and trade.calc_profit_ratio(rate) < 0:
            logger.info(f"{trade.pair} partial exit is below 0")
            self.dp.send_msg(f"{trade.pair} partial exit is below 0")
            return False
        if exit_reason == "trailing_stop_loss" and trade.calc_profit_ratio(rate) < 0:
            logger.info(f"{trade.pair} trailing stop price is below 0")
            self.dp.send_msg(f"{trade.pair} trailing stop price is below 0")
            return False
        return True

    def adjust_trade_position(
            self,
            trade: Trade,
            current_time: datetime,
            current_rate: float,
            current_profit: float,
            min_stake: Optional[float],
            max_stake: float,
            current_entry_rate: float,
            current_exit_rate: float,
            current_entry_profit: float,
            current_exit_profit: float,
            **kwargs,
    ) -> Optional[float]:
        filled_entries = trade.select_filled_orders(trade.entry_side)
        count_of_entries = trade.nr_of_successful_entries

        if current_profit > 0.25 and trade.nr_of_successful_exits == 0:
            return -(trade.stake_amount / 4)
        if current_profit > 0.40 and trade.nr_of_successful_exits == 1:
            return -(trade.stake_amount / 3)

        if current_profit > -0.15 and trade.nr_of_successful_entries == 1:
            return None
        if current_profit > -0.3 and trade.nr_of_successful_entries == 2:
            return None
        if current_profit > -0.6 and trade.nr_of_successful_entries == 3:
            return None

        if count_of_entries <= self.max_safety_orders.value:
            try:
                base_stake = filled_entries[0].cost
                total_stake = base_stake / 0.3
                dca_stake = (total_stake * 0.7) / self.max_safety_orders.value
                dca_order_number = count_of_entries + 1
                
                # Create unique DCA order ID
                dca_order_id = f"{trade.pair}_{trade.open_date}_{dca_order_number}"

                file_status = self._get_dca_confirmation_status(dca_order_id)
                if file_status == "declined":
                    self.dca_declined_orders.add(dca_order_id)
                    self._clear_dca_confirmation(dca_order_id)
                    logger.info(f"DCA order {dca_order_id} was declined (file)")
                    return None
                if file_status == "confirmed":
                    self._clear_dca_confirmation(dca_order_id)
                    logger.info(f"DCA order {dca_order_id} confirmed (file), executing...")
                    return dca_stake
                if file_status == "pending":
                    return None
                
                # Check if already declined
                if dca_order_id in self.dca_declined_orders:
                    logger.info(f"DCA order {dca_order_id} was declined by user")
                    return None
                
                # Check if already confirmed
                if dca_order_id in self.dca_confirmed_orders:
                    logger.info(f"DCA order {dca_order_id} confirmed, executing...")
                    self.dca_confirmed_orders.pop(dca_order_id)
                    return dca_stake
                
                # Send DCA confirmation request if not already pending
                if dca_order_id not in self.dca_pending_confirmations:
                    self._send_dca_confirmation(
                        trade.pair, 
                        dca_order_number, 
                        current_rate, 
                        dca_stake, 
                        current_profit,
                        dca_order_id
                    )
                    timestamp = current_time
                    if timestamp is not None and timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    self.dca_pending_confirmations[dca_order_id] = {
                        'pair': trade.pair,
                        'order_number': dca_order_number,
                        'entry_rate': current_rate,
                        'stake': dca_stake,
                        'profit': current_profit,
                        'timestamp': timestamp
                    }
                    logger.info(f"DCA confirmation pending for {dca_order_id}")
                
                return None  # Wait for confirmation
            except Exception as e:
                logger.warning(f"Error in DCA execution: {str(e)}")
                return None
        return None

    def _get_dca_confirmation_status(self, dca_order_id: str) -> str:
        path = Path(os.getenv("DCA_CONFIRMATIONS_PATH", "/freqtrade/user_data/dca_confirmations.json"))
        if not path.exists():
            return ""
        try:
            data = json.loads(path.read_text())
        except Exception as e:
            logger.warning(f"Failed to read DCA confirmations: {e}")
            return ""
        if dca_order_id not in data:
            return ""
        return str(data[dca_order_id].get("status", ""))

    def _clear_dca_confirmation(self, dca_order_id: str) -> None:
        path = Path(os.getenv("DCA_CONFIRMATIONS_PATH", "/freqtrade/user_data/dca_confirmations.json"))
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
        except Exception as e:
            logger.warning(f"Failed to read DCA confirmations: {e}")
            return
        if dca_order_id not in data:
            return
        data.pop(dca_order_id, None)
        try:
            path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.warning(f"Failed to write DCA confirmations: {e}")

    def _send_dca_confirmation(self, pair: str, order_number: int, entry_rate: float, 
                               stake: float, profit: float, dca_order_id: str) -> None:
        """Send Telegram message with Accept/Decline buttons for DCA confirmation"""
        try:
            bot_token = os.getenv("DCA_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            if not bot_token or not chat_id:
                logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set; cannot send DCA confirmation")
                return

            message = (
                f"🔄 *DCA Order Confirmation Required*\n\n"
                f"Pair: {pair}\n"
                f"DCA Order: #{order_number}\n"
                f"Entry Rate: {entry_rate:.8f}\n"
                f"DCA Stake: {stake:.8f}\n"
                f"Current Profit: {profit:.2%}\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"⏱️ *Auto-decline in {self.dca_confirmation_timeout_minutes} minutes if no response*\n\n"
                f"*Please confirm or decline this DCA order*"
            )

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Accept DCA", "callback_data": f"dca_accept_{dca_order_id}"},
                            {"text": "❌ Decline DCA", "callback_data": f"dca_decline_{dca_order_id}"}
                        ]
                    ]
                }
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(
                f"DCA confirmation request sent for {dca_order_id} "
                f"(auto-decline in {self.dca_confirmation_timeout_minutes}min)"
            )
                
        except Exception as e:
            logger.error(f"Failed to send DCA confirmation: {str(e)}")

    def dca_button_handler(self, update, context) -> None:
        """Handle DCA confirmation button clicks from Telegram"""
        query = update.callback_query
        query.answer()
        
        callback_data = query.data
        
        if callback_data.startswith('dca_accept_'):
            dca_order_id = callback_data.replace('dca_accept_', '')
            self.dca_confirmed_orders[dca_order_id] = True
            self.dca_pending_confirmations.pop(dca_order_id, None)
            
            message_text = f"✅ *DCA Order Confirmed*\nOrder ID: `{dca_order_id}`\n\nDCA will execute at next candle."
            query.edit_message_text(text=message_text, parse_mode='markdown')
            logger.info(f"DCA order {dca_order_id} ACCEPTED by user")
            
        elif callback_data.startswith('dca_decline_'):
            dca_order_id = callback_data.replace('dca_decline_', '')
            self.dca_declined_orders.add(dca_order_id)
            self.dca_pending_confirmations.pop(dca_order_id, None)
            
            message_text = f"❌ *DCA Order Declined*\nOrder ID: `{dca_order_id}`\n\nThis DCA order has been skipped."
            query.edit_message_text(text=message_text, parse_mode='markdown')
            logger.info(f"DCA order {dca_order_id} DECLINED by user")

    def bot_loop_start(self, **kwargs) -> None:
        """Initialize Telegram button handlers on bot start"""
        try:
            if hasattr(self, 'dp') and self.dp:
                logger.info("DCA confirmation system initialized")
        except Exception as e:
            logger.warning(f"Error initializing DCA confirmation: {str(e)}")

    def _cleanup_old_confirmations(self) -> None:
        """Clean up and auto-decline DCA confirmations older than timeout period"""
        from datetime import timedelta
        current_time = datetime.now(timezone.utc)
        expired_ids = []
        auto_declined_ids = []


        for dca_id, details in list(self.dca_pending_confirmations.items()):
            timestamp = details.get('timestamp')
            if timestamp is None:
                continue
            # Convert timestamp to timezone-aware UTC datetime
            try:
                if isinstance(timestamp, str):
                    # Try ISO format first
                    try:
                        timestamp_dt = datetime.fromisoformat(timestamp)
                    except Exception:
                        # Fallback: try parsing as float seconds
                        timestamp_dt = datetime.utcfromtimestamp(float(timestamp))
                    if timestamp_dt.tzinfo is None:
                        timestamp_dt = timestamp_dt.replace(tzinfo=timezone.utc)
                elif hasattr(timestamp, 'tzinfo'):
                    timestamp_dt = timestamp
                    if timestamp_dt.tzinfo is None:
                        timestamp_dt = timestamp_dt.replace(tzinfo=timezone.utc)
                else:
                    # Fallback: treat as UNIX timestamp
                    timestamp_dt = datetime.utcfromtimestamp(float(timestamp)).replace(tzinfo=timezone.utc)
            except Exception:
                continue
            time_elapsed = current_time - timestamp_dt

            # Auto-decline after timeout without response
            if time_elapsed > timedelta(minutes=self.dca_confirmation_timeout_minutes):
                auto_declined_ids.append(dca_id)
                self.dca_declined_orders.add(dca_id)
                logger.warning(
                    f"DCA order {dca_id} auto-declined due to no confirmation within "
                    f"{self.dca_confirmation_timeout_minutes} minutes"
                )

            # Clean up very old confirmations (1 hour)
            if time_elapsed > timedelta(hours=1):
                expired_ids.append(dca_id)
                logger.info(f"Cleaning up expired DCA confirmation: {dca_id}")

        # Remove auto-declined orders from pending
        for dca_id in auto_declined_ids:
            self.dca_pending_confirmations.pop(dca_id, None)

        # Remove very old confirmations
        for dca_id in expired_ids:
            self.dca_pending_confirmations.pop(dca_id, None)
            self.dca_confirmed_orders.pop(dca_id, None)
            self.dca_declined_orders.discard(dca_id)

    def leverage(
            self,
            pair: str,
            current_time: "datetime",
            current_rate: float,
            proposed_leverage: float,
            max_leverage: float,
            side: str,
            **kwargs,
    ) -> float:
        window_size = 50
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        historical_close_prices = dataframe["close"].tail(window_size)
        historical_high_prices = dataframe["high"].tail(window_size)
        historical_low_prices = dataframe["low"].tail(window_size)

        atr_values = ta.ATR(
            historical_high_prices, historical_low_prices, historical_close_prices, timeperiod=14
        )
        current_atr = atr_values[-1] if len(atr_values) > 0 else 0.0

        target_leverage = 7.5 if current_atr < (current_rate * 0.03) else 5.0
        return max(min(target_leverage, max_leverage), 1.0)

    def custom_stoploss(
            self,
            pair: str,
            trade: Trade,
            current_time: datetime,
            current_rate: float,
            current_profit: float,
            **kwargs,
    ) -> float:
        if trade.nr_of_successful_entries > 1:
            return stoploss_from_open(-0.30, current_profit)
        return self.stoploss

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, '1h') for pair in pairs]
        informative_pairs += [(pair, self.informative_timeframe) for pair in pairs]
        return informative_pairs

    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe["rsi"] = ta.RSI(dataframe)
        dataframe["DI_values"] = ta.PLUS_DI(dataframe) - ta.MINUS_DI(dataframe)
        dataframe["DI_cutoff"] = 0

        maxima = np.zeros(len(dataframe))
        minima = np.zeros(len(dataframe))

        maxima[argrelextrema(dataframe["close"].values, np.greater, order=5)] = 1
        minima[argrelextrema(dataframe["close"].values, np.less, order=5)] = 1

        dataframe["maxima"] = maxima
        dataframe["minima"] = minima

        dataframe["&s-extrema"] = 0
        min_peaks = argrelextrema(dataframe["close"].values, np.less, order=5)[0]
        max_peaks = argrelextrema(dataframe["close"].values, np.greater, order=5)[0]
        dataframe.loc[min_peaks, "&s-extrema"] = -1
        dataframe.loc[max_peaks, "&s-extrema"] = 1

        murrey_math_levels = calculate_murrey_math_levels(dataframe)
        for level, value in murrey_math_levels.items():
            dataframe[level] = value

        dataframe["mmlextreme_oscillator"] = 100 * (
                (dataframe["close"] - dataframe["[4/8]P"])
                / (dataframe["[+3/8]P"] - dataframe["[-3/8]P"])
        )
        dataframe["DI_catch"] = np.where(dataframe["DI_values"] > dataframe["DI_cutoff"], 0, 1)

        dataframe["minima_sort_threshold"] = dataframe["close"].rolling(window=10).min()
        dataframe["maxima_sort_threshold"] = dataframe["close"].rolling(window=10).max()

        dataframe["min_threshold_mean"] = dataframe["minima_sort_threshold"].expanding().mean()
        dataframe["max_threshold_mean"] = dataframe["maxima_sort_threshold"].expanding().mean()

        dataframe["maxima_check"] = (
            dataframe["maxima"].rolling(4).apply(lambda x: int((x != 1).all()), raw=True).fillna(0)
        )
        dataframe["minima_check"] = (
            dataframe["minima"].rolling(4).apply(lambda x: int((x != 1).all()), raw=True).fillna(0)
        )

        return dataframe

    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe["rsi"] = ta.RSI(dataframe)
        dataframe["DI_values"] = ta.PLUS_DI(dataframe) - ta.MINUS_DI(dataframe)
        dataframe["DI_cutoff"] = 0

        maxima = np.zeros(len(dataframe))
        minima = np.zeros(len(dataframe))

        maxima[argrelextrema(dataframe["close"].values, np.greater, order=5)] = 1
        minima[argrelextrema(dataframe["close"].values, np.less, order=5)] = 1

        dataframe["maxima"] = maxima
        dataframe["minima"] = minima

        dataframe["&s-extrema"] = 0
        min_peaks = argrelextrema(dataframe["close"].values, np.less, order=5)[0]
        max_peaks = argrelextrema(dataframe["close"].values, np.greater, order=5)[0]
        dataframe.loc[min_peaks, "&s-extrema"] = -1
        dataframe.loc[max_peaks, "&s-extrema"] = 1

        murrey_math_levels = calculate_murrey_math_levels(dataframe)
        for level, value in murrey_math_levels.items():
            dataframe[level] = value

        dataframe["mmlextreme_oscillator"] = 100 * (
                (dataframe["close"] - dataframe["[4/8]P"])
                / (dataframe["[+3/8]P"] - dataframe["[-3/8]P"])
        )
        dataframe["DI_catch"] = np.where(dataframe["DI_values"] > dataframe["DI_cutoff"], 0, 1)

        dataframe["minima_sort_threshold"] = dataframe["close"].rolling(window=10).min()
        dataframe["maxima_sort_threshold"] = dataframe["close"].rolling(window=10).max()

        dataframe["min_threshold_mean"] = dataframe["minima_sort_threshold"].expanding().mean()
        dataframe["max_threshold_mean"] = dataframe["maxima_sort_threshold"].expanding().mean()

        dataframe["maxima_check"] = (
            dataframe["maxima"].rolling(4).apply(lambda x: int((x != 1).all()), raw=True).fillna(0)
        )
        dataframe["minima_check"] = (
            dataframe["minima"].rolling(4).apply(lambda x: int((x != 1).all()), raw=True).fillna(0)
        )

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Clean up old DCA confirmations
        self._cleanup_old_confirmations()

        dataframe["rsi"] = ta.RSI(dataframe)
        dataframe["DI_values"] = ta.PLUS_DI(dataframe) - ta.MINUS_DI(dataframe)
        dataframe["DI_cutoff"] = 0

        maxima = np.zeros(len(dataframe))
        minima = np.zeros(len(dataframe))

        maxima[argrelextrema(dataframe["close"].values, np.greater, order=5)] = 1
        minima[argrelextrema(dataframe["close"].values, np.less, order=5)] = 1

        dataframe["maxima"] = maxima
        dataframe["minima"] = minima

        dataframe["&s-extrema"] = 0
        min_peaks = argrelextrema(dataframe["close"].values, np.less, order=5)[0]
        max_peaks = argrelextrema(dataframe["close"].values, np.greater, order=5)[0]
        dataframe.loc[min_peaks, "&s-extrema"] = -1
        dataframe.loc[max_peaks, "&s-extrema"] = 1

        murrey_math_levels = calculate_murrey_math_levels(dataframe)
        for level, value in murrey_math_levels.items():
            dataframe[level] = value

        dataframe["mmlextreme_oscillator"] = 100 * (
                (dataframe["close"] - dataframe["[4/8]P"])
                / (dataframe["[+3/8]P"] - dataframe["[-3/8]P"])
        )
        dataframe["DI_catch"] = np.where(dataframe["DI_values"] > dataframe["DI_cutoff"], 0, 1)

        dataframe["minima_sort_threshold"] = dataframe["close"].rolling(window=10).min()
        dataframe["maxima_sort_threshold"] = dataframe["close"].rolling(window=10).max()

        dataframe["min_threshold_mean"] = dataframe["minima_sort_threshold"].expanding().mean()
        dataframe["max_threshold_mean"] = dataframe["maxima_sort_threshold"].expanding().mean()

        dataframe["maxima_check"] = (
            dataframe["maxima"].rolling(4).apply(lambda x: int((x != 1).all()), raw=True).fillna(0)
        )
        dataframe["minima_check"] = (
            dataframe["minima"].rolling(4).apply(lambda x: int((x != 1).all()), raw=True).fillna(0)
        )

        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        # ========== 1H ENTRIES ==========
        # Conditions for long entry on 1H
        df.loc[
            (
                (df["DI_catch_1h"] == 1)  # DI_catch condition
                & (df["maxima_check_1h"] == 1)  # maxima_check condition
                & (df["&s-extrema_1h"] < 0)  # extrema condition
                & (df["minima_1h"].shift(1) == 1)  # prior minima condition
                & (df["volume_1h"] > 0)  # Volume greater than 0
                & (df["rsi_1h"] < 30)  # RSI below 30 (extra filter to limit entries)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "1H_Minima")

        df.loc[
            (
                (df["minima_check_1h"] == 0)  # minima_check condition
                & (df["volume_1h"] > 0)  # Volume greater than 0
                & (df["rsi_1h"] < 30)  # RSI below 30 (extra filter to limit entries)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "1H_Minima_Full_Send")

        df.loc[
            (
                (df["DI_catch_1h"] == 1)  # DI_catch condition
                & (df["minima_check_1h"] == 0)  # minima_check condition
                & (df["minima_check_1h"].shift(5) == 1)  # prior minima_check condition
                & (df["volume_1h"] > 0)  # Volume greater than 0
                & (df["rsi_1h"] < 30)  # RSI below 30 (extra filter to limit entries)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "1H_Minima_Check")

        # Conditions for short entry on 1H
        df.loc[
            (
                (df["DI_catch_1h"] == 1)  # DI_catch condition
                & (df["minima_check_1h"] == 1)  # minima_check condition
                & (df["&s-extrema_1h"] > 0)  # extrema condition
                & (df["maxima_1h"].shift(1) == 1)  # prior maxima condition
                & (df["volume_1h"] > 0)  # Volume greater than 0
                & (df["rsi_1h"] > 70)  # RSI above 70 (extra filter to limit entries)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "1H_Maxima")

        df.loc[
            (
                (df["maxima_check_1h"] == 0)  # maxima_check condition
                & (df["volume_1h"] > 0)  # Volume greater than 0
                & (df["rsi_1h"] > 70)  # RSI above 70 (extra filter to limit entries)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "1H_Maxima_Full_Send")

        df.loc[
            (
                (df["DI_catch_1h"] == 1)  # DI_catch condition
                & (df["maxima_check_1h"] == 0)  # maxima_check condition
                & (df["maxima_check_1h"].shift(5) == 1)  # prior maxima_check condition
                & (df["volume_1h"] > 0)  # Volume greater than 0
                & (df["rsi_1h"] > 70)  # RSI above 70 (extra filter to limit entries)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "1H_Maxima_Check")

        # ========== 4H ENTRIES ==========
        # Conditions for long entry on 4H
        df.loc[
            (
                (df["DI_catch_4h"] == 1)  # DI_catch condition
                & (df["maxima_check_4h"] == 1)  # maxima_check condition
                & (df["&s-extrema_4h"] < 0)  # extrema condition
                & (df["minima_4h"].shift(1) == 1)  # prior minima condition
                & (df["volume_4h"] > 0)  # Volume greater than 0
                & (df["rsi_4h"] < 30)  # RSI below 30 (extra filter to limit entries)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "4H_Minima")

        df.loc[
            (
                (df["minima_check_4h"] == 0)  # minima_check condition
                & (df["volume_4h"] > 0)  # Volume greater than 0
                & (df["rsi_4h"] < 30)  # RSI below 30 (extra filter to limit entries)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "4H_Minima_Full_Send")

        df.loc[
            (
                (df["DI_catch_4h"] == 1)  # DI_catch condition
                & (df["minima_check_4h"] == 0)  # minima_check condition
                & (df["minima_check_4h"].shift(5) == 1)  # prior minima_check condition
                & (df["volume_4h"] > 0)  # Volume greater than 0
                & (df["rsi_4h"] < 30)  # RSI below 30 (extra filter to limit entries)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "4H_Minima_Check")

        # Conditions for short entry on 4H
        df.loc[
            (
                (df["DI_catch_4h"] == 1)  # DI_catch condition
                & (df["minima_check_4h"] == 1)  # minima_check condition
                & (df["&s-extrema_4h"] > 0)  # extrema condition
                & (df["maxima_4h"].shift(1) == 1)  # prior maxima condition
                & (df["volume_4h"] > 0)  # Volume greater than 0
                & (df["rsi_4h"] > 70)  # RSI above 70 (extra filter to limit entries)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "4H_Maxima")

        df.loc[
            (
                (df["maxima_check_4h"] == 0)  # maxima_check condition
                & (df["volume_4h"] > 0)  # Volume greater than 0
                & (df["rsi_4h"] > 70)  # RSI above 70 (extra filter to limit entries)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "4H_Maxima_Full_Send")

        df.loc[
            (
                (df["DI_catch_4h"] == 1)  # DI_catch condition
                & (df["maxima_check_4h"] == 0)  # maxima_check condition
                & (df["maxima_check_4h"].shift(5) == 1)  # prior maxima_check condition
                & (df["volume_4h"] > 0)  # Volume greater than 0
                & (df["rsi_4h"] > 70)  # RSI above 70 (extra filter to limit entries)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "4H_Maxima_Check")

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df.loc[((df["maxima_check"] == 0) & (df["volume"] > 0)), ["exit_long", "exit_tag"]] = (
            1,
            "Maxima Check",
        )
        df.loc[
            (
                    (df["DI_catch"] == 1)
                    & (df["&s-extrema"] > 0)
                    & (df["maxima"].shift(1) == 1)
                    & (df["volume"] > 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "Maxima")
        df.loc[((df["maxima_check"] == 0) & (df["volume"] > 0)), ["exit_long", "exit_tag"]] = (
            1,
            "Maxima Full Send",
        )

        df.loc[((df["minima_check"] == 0) & (df["volume"] > 0)), ["exit_short", "exit_tag"]] = (
            1,
            "Minima Check",
        )
        df.loc[
            (
                    (df["DI_catch"] == 1)
                    & (df["&s-extrema"] < 0)
                    & (df["minima"].shift(1) == 1)
                    & (df["volume"] > 0)
            ),
            ["exit_short", "exit_tag"],
        ] = (1, "Minima")
        df.loc[((df["minima_check"] == 0) & (df["volume"] > 0)), ["exit_short", "exit_tag"]] = (
            1,
            "Minima Full Send",
        )

        return df


def calculate_murrey_math_levels(df, window_size=64):
    rolling_max_H = df["high"].rolling(window=window_size).max()
    rolling_min_L = df["low"].rolling(window=window_size).min()
    max_H = rolling_max_H
    min_L = rolling_min_L
    def calculate_fractal(v2):
        fractal = 0
        if 25000 < v2 <= 250000:
            fractal = 100000
        elif 2500 < v2 <= 25000:
            fractal = 10000
        elif 250 < v2 <= 2500:
            fractal = 1000
        elif 25 < v2 <= 250:
            fractal = 100
        elif 12.5 < v2 <= 25:
            fractal = 12.5
        elif 6.25 < v2 <= 12.5:
            fractal = 12.5
        elif 3.125 < v2 <= 6.25:
            fractal = 3.125
        elif 1.5625 < v2 <= 3.125:
            fractal = 3.125
        elif 0.390625 < v2 <= 1.5625:
            fractal = 1.5625
        elif 0 < v2 <= 0.390625:
            fractal = 0.1953125
        return fractal

    def calculate_x_values(v1, v2, mn, mx):
        dmml = (v2 - v1) / 8
        x_values = []
        midpoints = [mn + i * dmml for i in range(8)]
        for i in range(7):
            x_i = (midpoints[i] + midpoints[i + 1]) / 2
            x_values.append(x_i)
        finalH = max(x_values)
        return x_values, finalH

    def calculate_y_values(x_values, mn):
        y_values = []
        for x in x_values:
            if x > 0:
                y = mn
            else:
                y = 0
            y_values.append(y)
        return y_values

    def calculate_mml(mn, finalH, mx):
        dmml = ((finalH - final_l) / 8) * 1.0699
        mml = (float([mx][0]) * 0.99875) + (dmml * 3)
        ml = []
        for i in range(0, 16):
            calc = mml - (dmml * (i))
            ml.append(calc)
        murrey_math_levels = {
            "[-3/8]P": ml[14],
            "[-2/8]P": ml[13],
            "[-1/8]P": ml[12],
            "[0/8]P": ml[11],
            "[1/8]P": ml[10],
            "[2/8]P": ml[9],
            "[3/8]P": ml[8],
            "[4/8]P": ml[7],
            "[5/8]P": ml[6],
            "[6/8]P": ml[5],
            "[7/8]P": ml[4],
            "[8/8]P": ml[3],
            "[+1/8]P": ml[2],
            "[+2/8]P": ml[1],
            "[+3/8]P": ml[0],
        }
        return mml, murrey_math_levels

    for i in range(len(df)):
        mn = np.min(min_L.iloc[: i + 1])
        mx = np.max(max_H.iloc[: i + 1])
        x_values, final_h = calculate_x_values(mn, mx, mn, mx)
        y_values = calculate_y_values(x_values, mn)
        final_l = np.min(y_values)
        mml, murrey_math_levels = calculate_mml(final_l, final_h, mx)
        for level, value in murrey_math_levels.items():
            df.at[df.index[i], level] = value

    return df
