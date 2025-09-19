#!/usr/bin/env python3
"""
Scraper for cacau prices (Bahia and Pará).
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup
import requests

# Use a custom User-Agent to avoid being blocked by the site
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117 Safari/537.36"
}

def fetch_cacau_prices() -> Dict[str, object]:
    """Fetch prices for cacau from Notícias Agrícolas and return a dict with conversions."""
    url = "https://www.noticiasagricolas.com.br/widgets/cotacoes?id=96"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    tbody = soup.find("tbody")
    row = tbody.find("tr")
    cols = row.find_all("td")
    date_str = cols[0].get_text(strip=True)
    bahia_arroba = float(cols[1].get_text(strip=True).replace(".", "").replace(",", "."))
    para_arroba = float(cols[2].get_text(strip=True).replace(".", "").replace(",", "."))
    # 1 arroba = 15 kg; 1 saca = 60 kg
    bahia_kg = bahia_arroba / 15
    para_kg = para_arroba / 15
    bahia_saca = bahia_kg * 60
    para_saca = para_kg * 60
    return {
        "data": date_str,
        "bahia_arroba": bahia_arroba,
        "bahia_kg": bahia_kg,
        "bahia_saca": bahia_saca,
        "para_arroba": para_arroba,
        "para_kg": para_kg,
        "para_saca": para_saca,
    }

def update_prices_json(prices_path: Path, data: Dict[str, object], now: datetime) -> None:
    out = data.copy()
    out["ultima_atualizacao"] = now.isoformat()
    prices_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))

def update_history_json(history_path: Path, data: Dict[str, object], now: datetime) -> None:
    history: List[dict] = []
    if history_path.exists():
        history = json.loads(history_path.read_text())
    entry = {
        "data": data["data"],
        "data_consulta": now.isoformat(),
        "bahia_arroba": data["bahia_arroba"],
        "bahia_kg": data["bahia_kg"],
        "bahia_saca": data["bahia_saca"],
        "para_arroba": data["para_arroba"],
        "para_kg": data["para_kg"],
        "para_saca": data["para_saca"],
    }
    history.append(entry)
    history = history[-10:]
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2))

def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    prices_path = data_dir / "prices.json"
    history_path = data_dir / "historico.json"
    now = datetime.now()
    data = fetch_cacau_prices()
    update_prices_json(prices_path, data, now)
    update_history_json(history_path, data, now)

if __name__ == "__main__":
    main()
