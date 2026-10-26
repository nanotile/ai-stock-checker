#!/usr/bin/env python3
"""Crypto data fetcher — yfinance backend (replaces geo-blocked Binance API)."""

from typing import Dict, Optional, List
import time

_TOP_CRYPTO_BASES = [
    "BTC", "ETH", "BNB", "SOL", "XRP",
    "ADA", "DOGE", "AVAX", "DOT", "LINK",
    "UNI", "ATOM", "LTC", "ETC", "XLM",
    "NEAR", "APT", "FIL", "ARB", "OP",
    "INJ", "SUI", "AAVE", "MKR", "RENDER",
    "FET", "GRT", "PEPE", "SHIB", "TRX",
]

_LIQUID_BASES = {"BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK"}

_YF_CURRENCY_SUFFIX = {"EUR": "EUR", "USD": "USD", "CAD": "CAD"}


class BinanceFetcher:
    """Fetch crypto data via yfinance (drop-in replacement for Binance API)."""

    def __init__(self, currency: str = "USD"):
        import yfinance as yf
        self._yf = yf
        self._currency = _YF_CURRENCY_SUFFIX.get(currency.upper(), "USD")

    def _base_from(self, symbol: str) -> str:
        """Extract base coin from any format (BTCUSDT, BTC-USD, BTC-EUR)."""
        s = symbol.upper()
        for suffix in ("USDT", "-USDT", "-USD", "-EUR", "-CAD"):
            if s.endswith(suffix):
                return s[: -len(suffix)]
        return s

    def _to_yf(self, symbol: str) -> str:
        """Normalize any crypto symbol to yfinance format in portfolio currency."""
        base = self._base_from(symbol)
        return f"{base}-{self._currency}"

    @staticmethod
    def _to_binance_key(yf_symbol: str) -> str:
        """Convert yfinance symbol to Binance-style key (e.g. BTCUSDT)."""
        for suffix in ("-USD", "-EUR", "-CAD"):
            if yf_symbol.endswith(suffix):
                return yf_symbol[: -len(suffix)] + "USDT"
        return yf_symbol

    def convert_symbol(self, yf_symbol: str) -> str:
        """Convert yfinance symbol to Binance-style key. Kept for API compat."""
        return self._to_binance_key(yf_symbol)

    def get_crypto_price(self, symbol: str) -> Optional[Dict]:
        """Get price data. Accepts BTCUSDT or BTC-USD format."""
        try:
            yf_sym = self._to_yf(symbol)
            ticker = self._yf.Ticker(yf_sym)
            hist = ticker.history(period="5d")
            if hist.empty or len(hist) < 1:
                return None

            row = hist.iloc[-1]
            current_price = float(row["Close"])
            high_24h = float(row["High"])
            low_24h = float(row["Low"])
            volume_24h = float(row["Volume"])

            change_24h = 0.0
            if len(hist) >= 2:
                prev_close = float(hist.iloc[-2]["Close"])
                if prev_close > 0:
                    change_24h = ((current_price - prev_close) / prev_close) * 100

            return {
                "symbol": symbol,
                "current_price": current_price,
                "change_24h": change_24h,
                "high_24h": high_24h,
                "low_24h": low_24h,
                "volume_24h": volume_24h,
                "timestamp": int(time.time() * 1000),
                "source": "yfinance",
            }
        except Exception as e:
            print(f"[ERROR] Failed to fetch crypto data for {symbol}: {str(e)}")
            return None

    def get_multiple_prices(self, symbols: list) -> Dict[str, Dict]:
        """Get prices for multiple symbols."""
        result = {}
        for symbol in symbols:
            data = self.get_crypto_price(symbol)
            if data:
                result[symbol] = data
        return result

    @staticmethod
    def _map_interval(interval: str) -> str:
        """Map Binance-style interval to yfinance equivalent."""
        return {"4h": "1h", "1w": "1wk"}.get(interval, interval)

    @staticmethod
    def _period_for(yf_interval: str, limit: int) -> str:
        """Calculate a yfinance period that covers `limit` candles."""
        if yf_interval in ("1m",):
            return "7d"
        if yf_interval in ("5m", "15m", "30m"):
            return "60d"
        if yf_interval in ("1h", "60m", "90m"):
            days = max((limit // 24) + 5, 7)
            return f"{days}d"
        if yf_interval == "1d":
            days = limit + 15
            return f"{min(days, 729)}d" if days <= 729 else "2y"
        if yf_interval in ("1wk",):
            return "2y"
        return "6mo"

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 24) -> Optional[list]:
        """Get candlestick data. Returns list of dicts matching original format."""
        try:
            yf_sym = self._to_yf(symbol)
            yf_interval = self._map_interval(interval)
            period = self._period_for(yf_interval, limit)

            ticker = self._yf.Ticker(yf_sym)
            hist = ticker.history(period=period, interval=yf_interval)
            if hist.empty:
                return None

            hist = hist.tail(limit)

            candles = []
            for idx, row in hist.iterrows():
                ts = int(idx.timestamp() * 1000)
                candles.append({
                    "open_time": ts,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                    "close_time": ts,
                })
            return candles if candles else None
        except Exception as e:
            print(f"[ERROR] Failed to fetch klines for {symbol}: {str(e)}")
            return None

    def get_all_tickers(self, min_volume_usdt: float = 10000000) -> Dict[str, Dict]:
        """Scan top crypto pairs. Returns BTCUSDT-keyed dict for compat."""
        try:
            print(f"   🌐  Fetching top {len(_TOP_CRYPTO_BASES)} crypto pairs via yfinance ({self._currency})...")
            result = {}
            for base in _TOP_CRYPTO_BASES:
                bkey = f"{base}USDT"
                data = self.get_crypto_price(bkey)
                if not data:
                    continue
                vol_usd = data["volume_24h"] * data["current_price"]
                if vol_usd < min_volume_usdt:
                    continue
                result[bkey] = {
                    "current_price": data["current_price"],
                    "change_24h": data["change_24h"],
                    "high_24h": data["high_24h"],
                    "low_24h": data["low_24h"],
                    "volume_24h": data["volume_24h"],
                    "volume_usdt": vol_usd,
                    "trade_count_24h": 0,
                    "timestamp": data["timestamp"],
                    "source": "yfinance",
                }
            return result
        except Exception as e:
            print(f"[ERROR] Failed to fetch all tickers: {str(e)}")
            return {}

    def get_trending_coins(self, min_volume_usdt: float = 10000000, top_n: int = 20) -> List[Dict]:
        """Get trending coins by volume and price movement."""
        try:
            print("   🌐  Scanning crypto for trending coins via yfinance...")
            tickers = self.get_all_tickers(min_volume_usdt=min_volume_usdt)
            if not tickers:
                return []

            trending = []
            for bsym, data in tickers.items():
                yf_sym = self._to_yf(bsym)
                vol_usd = data.get("volume_usdt", data["volume_24h"] * data["current_price"])

                volume_score = min((vol_usd / 1_000_000_000) * 30, 30)
                change_score = min(abs(data["change_24h"]) * 0.6, 30)
                trending_score = volume_score + change_score

                trending.append({
                    "symbol": bsym,
                    "yf_symbol": yf_sym,
                    "trending_score": trending_score,
                    "trade_count_24h": 0,
                    "volume_usdt": vol_usd,
                    "change_24h": data["change_24h"],
                    "current_price": data["current_price"],
                    "high_24h": data["high_24h"],
                    "low_24h": data["low_24h"],
                })

            trending.sort(key=lambda x: x["trending_score"], reverse=True)
            return trending[:top_n]
        except Exception as e:
            print(f"[ERROR] Failed to fetch trending coins: {str(e)}")
            return []

    def analyze_breakout(self, symbol: str) -> Optional[Dict]:
        """Analyze if a coin is experiencing a breakout."""
        try:
            klines = self.get_klines(symbol, interval="1d", limit=7)
            if not klines or len(klines) < 7:
                return None

            current = klines[-1]
            prev_candles = klines[:-1]

            avg_volume = sum(c["volume"] for c in prev_candles) / len(prev_candles)
            volume_surge = (current["volume"] / avg_volume - 1) * 100 if avg_volume > 0 else 0

            prev_high = max(c["high"] for c in prev_candles)
            is_higher_high = current["high"] > prev_high

            score = 0
            if is_higher_high:
                score += 40
            if volume_surge > 50:
                score += 30
            if volume_surge > 100:
                score += 15
            if current["close"] > current["open"]:
                score += 15

            return {
                "symbol": symbol,
                "breakout_score": min(score, 100),
                "is_higher_high": is_higher_high,
                "volume_surge_pct": volume_surge,
                "current_price": current["close"],
                "prev_high": prev_high,
                "breakout_pct": ((current["high"] - prev_high) / prev_high * 100) if is_higher_high else 0,
            }
        except Exception as e:
            print(f"[ERROR] Breakout analysis failed for {symbol}: {str(e)}")
            return None

    def get_technical_indicators(self, symbol: str) -> Optional[Dict]:
        """Calculate RSI and MACD from yfinance hourly data."""
        try:
            klines = self.get_klines(symbol, interval="1h", limit=50)
            if not klines or len(klines) < 35:
                return None

            closing_prices = [c["close"] for c in klines]

            from .technical_indicators import TechnicalIndicators

            result = {}
            rsi = TechnicalIndicators.calculate_rsi(closing_prices, period=14)
            if rsi is not None:
                result["rsi"] = rsi
            macd = TechnicalIndicators.calculate_macd(closing_prices)
            if macd is not None:
                result["macd"] = macd

            return result if result else None
        except Exception as e:
            print(f"[ERROR] Failed to calculate technical indicators for {symbol}: {str(e)}")
            return None

    def check_liquidity(self, symbol: str) -> Optional[Dict]:
        """Synthetic liquidity score for known liquid pairs."""
        base = self._base_from(symbol)
        if base in _LIQUID_BASES:
            return {
                "symbol": symbol,
                "spread_pct": 0.05,
                "best_bid": 0,
                "best_ask": 0,
                "bid_depth": 0,
                "ask_depth": 0,
                "liquidity_score": 90,
                "tradeable": True,
            }
        return None

    def get_orderbook_depth(self, symbol: str, limit: int = 10) -> Optional[Dict]:
        return None

    def get_recent_trades(self, symbol: str, limit: int = 100) -> Optional[list]:
        return None

    def get_agg_trades(self, symbol: str, limit: int = 500) -> Optional[list]:
        return None

    def analyze_buy_sell_pressure(self, symbol: str, limit: int = 100) -> Optional[Dict]:
        return None

    def get_klines_extended(self, symbol: str, interval: str = "1h", limit: int = 100) -> Optional[list]:
        return None
