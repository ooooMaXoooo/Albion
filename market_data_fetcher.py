import requests
from typing import List, Dict, Tuple
from datetime import datetime, timedelta, timezone

BASE_URL_PRICES = "https://europe.albion-online-data.com/api/v2/stats/prices"
BASE_URL_CHARTS = "https://europe.albion-online-data.com/api/v2/stats/charts"

HEADERS = {
    'User-Agent': 'Albion-Trading-Empire-SaaS/1.0',
    'Accept-Encoding': 'gzip, deflate'
}

def parse_api_date(date_str: str) -> datetime:
    try:
        if not date_str or date_str.startswith("0001"):
            return datetime.min.replace(tzinfo=timezone.utc)
        
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)

def calculate_vwap_and_volume(chart_data: dict) -> Tuple[int, int]:
    if 'data' not in chart_data or not chart_data['data']:
        return 0, 0
        
    prices = chart_data['data'].get('prices_avg', [])
    volumes = chart_data['data'].get('item_count', [])
    
    recent_prices = prices[-3:]
    recent_volumes = volumes[-3:]
    
    total_volume = sum(recent_volumes)
    if total_volume == 0:
        return 0, 0
        
    total_value = sum(p * v for p, v in zip(recent_prices, recent_volumes))
    return int(total_value / total_volume), total_volume

def fetch_market_prices(api_item_ids: List[str], cities: List[str]) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, int]], Dict[str, Dict[str, int]]]:
    unique_ids = list(set(api_item_ids))
    
    buying_prices = {item_id: {} for item_id in unique_ids}
    selling_prices = {item_id: {} for item_id in unique_ids}
    selling_volumes = {item_id: {} for item_id in unique_ids}
    
    locations_str = ",".join(cities)
    
    all_prices_data = []
    all_charts_data = []
    
    CHUNK_SIZE = 60
    
    for i in range(0, len(unique_ids), CHUNK_SIZE):
        chunk = unique_ids[i:i + CHUNK_SIZE]
        items_str = ",".join(chunk)
        
        try:
            url_prices = f"{BASE_URL_PRICES}/{items_str}.json?locations={locations_str}&qualities=1"
            resp_prices = requests.get(url_prices, headers=HEADERS, timeout=15)
            resp_prices.raise_for_status()
            all_prices_data.extend(resp_prices.json())
        except Exception as e:
            print(f"⚠️ Erreur Prices API (Lot {i//CHUNK_SIZE + 1}) : {e}")

        try:
            url_charts = f"{BASE_URL_CHARTS}/{items_str}.json?locations={locations_str}&qualities=1&time-scale=24"
            resp_charts = requests.get(url_charts, headers=HEADERS, timeout=15)
            resp_charts.raise_for_status()
            all_charts_data.extend(resp_charts.json())
        except Exception as e:
            print(f"⚠️ Erreur Charts API (Lot {i//CHUNK_SIZE + 1}) : {e}")

    chart_map = {}
    for entry in all_charts_data:
        item = entry.get('item_id')
        loc = entry.get('location')
        quality = entry.get('quality', 1)
        
        if quality != 1: continue
            
        if item and loc:
            vwap, volume = calculate_vwap_and_volume(entry)
            chart_map[(item, loc)] = (vwap, volume)

    now = datetime.now(timezone.utc)
    
    MAX_AGE_HOURS = 48
    MIN_VOLUME = 3      
    
    for entry in all_prices_data:
        item = entry.get('item_id')
        loc = entry.get('city')
        quality = entry.get('quality', 1)
        
        if quality != 1 or not item or not loc:
            continue
            
        sell_price = entry.get('sell_price_min', 0)
        date_str = entry.get('sell_price_min_date', '')
        sell_date = parse_api_date(date_str)
        
        is_fresh = (now - sell_date) <= timedelta(hours=MAX_AGE_HOURS)
        if not is_fresh:
            sell_price = 0  
            
        vwap, volume = chart_map.get((item, loc), (0, 0))
        is_liquid = volume >= MIN_VOLUME
        if not is_liquid:
            vwap = 0  
            
        if sell_price > 0:
            buying_prices[item][loc] = sell_price
            
        if sell_price > 0 and vwap > 0:
            selling_prices[item][loc] = min(sell_price, vwap)
            selling_volumes[item][loc] = max(1, int(volume / 3))

    return buying_prices, selling_prices, selling_volumes