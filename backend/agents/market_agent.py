"""
NusaTerminal - Market Agent
Wrapper agent untuk mengambil dan memproses data pasar real-time.
Menyediakan top movers, watchlist, dan market overview untuk dashboard.
"""

from datetime import datetime
from typing import List, Optional, Dict
import logging

from ..services.data_service import DataService, INDONESIAN_STOCKS, COMMODITIES, INDICES, ALL_SYMBOLS
from ..services.news_service import COMPANY_TO_SYMBOL
from ..models.schemas import MarketData, MarketType

logger = logging.getLogger(__name__)


class MarketAgent:
    """
    Agent yang mengorkestrasi pengambilan data pasar.
    Digunakan oleh endpoint /api/market di main.py.
    """

    def __init__(self):
        self.data_service = DataService()

    def get_realtime_data(self, symbols: Optional[List[str]] = None) -> List[MarketData]:
        """
        Ambil data real-time untuk simbol yang diminta.
        Jika symbols=None → ambil semua saham IDX dalam watchlist default.
        """
        return self.data_service.get_market_data(symbols)

    def get_all_assets(self) -> Dict[str, List[MarketData]]:
        """
        Ambil semua aset dikelompokkan per kategori.
        Returns dict: {"stocks": [...], "commodities": [...], "indices": [...]}
        """
        all_data = self.data_service.get_all_assets()

        return {
            "stocks":      [d for d in all_data if d.market_type == MarketType.STOCK],
            "commodities": [d for d in all_data if d.market_type == MarketType.COMMODITY],
            "indices":     [d for d in all_data if d.market_type == MarketType.INDEX],
            "timestamp":   datetime.now().isoformat(),
        }

    def get_top_movers(self, limit: int = 5) -> Dict:
        """
        Ambil top gainers, top losers, dan most active volume.
        Hanya mempertimbangkan saham dengan harga > 0.
        """
        all_data = self.data_service.get_market_data()
        valid = [d for d in all_data if d.price > 0]

        if not valid:
            return {
                "gainers": [], "losers": [], "active": [],
                "timestamp": datetime.now().isoformat()
            }

        gainers = sorted(valid, key=lambda x: x.change_percent, reverse=True)[:limit]
        losers  = sorted(valid, key=lambda x: x.change_percent)[:limit]
        active  = sorted(valid, key=lambda x: x.volume, reverse=True)[:limit]

        return {
            "gainers":   gainers,
            "losers":    losers,
            "active":    active,
            "timestamp": datetime.now().isoformat(),
        }

    def get_market_overview(self) -> Dict:
        """
        Ringkasan kondisi pasar secara keseluruhan:
        - IHSG summary
        - Jumlah saham naik/turun
        - Market breadth
        """
        ihsg = self.data_service.get_market_summary()
        all_stocks = self.data_service.get_market_data()
        valid = [d for d in all_stocks if d.price > 0]

        advancing = len([d for d in valid if d.change_percent > 0])
        declining = len([d for d in valid if d.change_percent < 0])
        unchanged = len([d for d in valid if d.change_percent == 0])
        total = len(valid)

        breadth = advancing / total if total > 0 else 0.5

        return {
            "ihsg": ihsg,
            "market_breadth": {
                "advancing": advancing,
                "declining": declining,
                "unchanged": unchanged,
                "total": total,
                "breadth_ratio": round(breadth, 4),
                "sentiment": (
                    "bullish" if breadth > 0.6
                    else "bearish" if breadth < 0.4
                    else "neutral"
                ),
            },
            "timestamp": datetime.now().isoformat(),
        }

    def get_watchlist(self) -> Dict[str, List[str]]:
        """Kembalikan daftar simbol yang tersedia per kategori."""
        # Gabungkan default stocks + simbol yang sering disebut di berita
        stock_syms = set(INDONESIAN_STOCKS.keys())
        stock_syms.update(list(COMPANY_TO_SYMBOL.values()))
        # Pastikan juga memasukkan simbol lain dari ALL_SYMBOLS
        try:
            for s in ALL_SYMBOLS.keys():
                if s not in COMMODITIES and s not in INDICES:
                    stock_syms.add(s)
        except Exception:
            pass

        return {
            "stocks":      sorted(list(stock_syms)),
            "commodities": list(COMMODITIES.keys()),
            "indices":     list(INDICES.keys()),
        }

    def get_symbol_info(self, symbol: str) -> Dict:
        """Ambil informasi fundamental satu saham."""
        return self.data_service.get_symbol_info(symbol)
