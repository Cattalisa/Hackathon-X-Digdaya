import sys
import os

# Add root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.data_service import DataService

ds = DataService()
print("Total emiten tersimpan:", len(ds.get_all_symbols()))
print("Data Market BBCA.JK:", ds.get_market_data(["BBCA.JK"]))
