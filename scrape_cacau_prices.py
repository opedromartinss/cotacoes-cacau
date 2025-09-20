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

# Determine if the commodity market is currently open.
# For simplicity we assume the same trading hours as the coffee market:
# Monday through Friday between 8:00 and 17:00 local time.
def is_market_open() -> bool:
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    hour = now.hour
    # Market open Monday-Friday 8-17 inclusive
    return 0 <= weekday <= 4 and 8 <= hour <= 17

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
    """
    Write the latest cacao prices to ``prices.json`` in the format expected
    by the site.

    The output JSON includes the ISO timestamp of the update as well as
    localized date and time strings (``data_formatada`` and
    ``hora_formatada``).  Prices for Bahia and Pará are provided under
    a nested ``cacau`` object with standardized keys so that
    ``data-loader.js`` on precodocacau.com can parse them directly.
    """
    # Meta information
    out: Dict[str, object] = {
        "ultima_atualizacao": now.isoformat(),
        "data_formatada": now.strftime("%d/%m/%Y"),
        "hora_formatada": now.strftime("%H:%M:%S"),
        "pregao_aberto": is_market_open(),
        "fonte": "Notícias Agrícolas",
    }
    # Nested price objects (arroba is the base unit for cacau)
    bahia_obj = {
        "preco": data["bahia_arroba"],
        "unidade": "arroba",
        "peso_kg": 15,
        "moeda": "BRL",
    }
    para_obj = {
        "preco": data["para_arroba"],
        "unidade": "arroba",
        "peso_kg": 15,
        "moeda": "BRL",
    }
    out["cacau"] = {
        "bahia": bahia_obj,
        "para": para_obj,
    }
    prices_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))

def update_history_json(history_path: Path, data: Dict[str, object], now: datetime) -> None:
    """
    Append the latest cacao prices to the historical JSON file.

    Two records are created for each update: one for Bahia and one for Pará.
    Each record mirrors the original structure with fields for reference date
    (``referente_a``), collection timestamp (``coletado_em``), product name,
    type (region), price value in arrobas, measurement unit and currency.  The
    history retains only the 20 most recent records to avoid unlimited growth.
    """
    history: List[dict] = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text())
        except json.JSONDecodeError:
            history = []

    base_timestamp = now.isoformat()
    # Record for Bahia
    bahia_entry = {
        "referente_a": data["data"],
        "coletado_em": base_timestamp,
        "produto": "cacau",
        "tipo": "bahia",
        "valor": data["bahia_arroba"],
        "unidade": "arroba",
        "moeda": "BRL",
    }
    # Record for Pará
    para_entry = {
        "referente_a": data["data"],
        "coletado_em": base_timestamp,
        "produto": "cacau",
        "tipo": "para",
        "valor": data["para_arroba"],
        "unidade": "arroba",
        "moeda": "BRL",
    }

    history.append(bahia_entry)
    history.append(para_entry)
    # Keep only last 20 records
    history = history[-20:]
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
