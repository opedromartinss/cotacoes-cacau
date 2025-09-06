import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests
from bs4 import BeautifulSoup


def parse_price(text: str) -> float:
    """
    Convert a price string from the Notícias Agrícolas widget into a float.

    The widget uses the Brazilian formatting for numbers where a period
    separates thousands and a comma separates decimals (e.g. "1.920,00").
    This helper removes any thousand separators and replaces the comma
    with a dot before casting to float.

    Args:
        text: A string representing a currency value.

    Returns:
        A float representation of the price.
    """
    if not text:
        return 0.0
    cleaned = text.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def is_market_open(now: datetime) -> bool:
    """
    Determine if the commodity market is open based on the current date and time.

    The market is considered open on weekdays (Monday to Friday) between
    08:00 and 17:00 local time. Note that this check uses the server's
    timezone; on GitHub Actions this will be UTC, but for Brazilian
    markets you may wish to adjust the timezone accordingly. For our
    purposes the same rules used on the café site apply here.

    Args:
        now: A datetime object representing the current time.

    Returns:
        True if within market hours on a weekday, False otherwise.
    """
    # Monday=0, Sunday=6
    return now.weekday() < 5 and 8 <= now.hour < 17


def fetch_cacau_prices(url: str) -> Dict[str, float]:
    """
    Fetch cacao prices from the Notícias Agrícolas widget and return
    a dictionary with prices for Bahia and Pará in different units.

    The widget presents prices for Bahia in arrobas (15 kg) and for
    Pará typically in kilograms. We compute price per arroba and per
    saca (60 kg) for each region.

    Args:
        url: The URL of the Notícias Agrícolas widget for cacao.

    Returns:
        A dictionary with price data for Bahia and Pará keyed by region
        and unit (arroba, kg, saca).
    """
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.find_all("tr")
    price_bahia_arroba = None
    price_para_kg = None
    price_para_arroba = None
    for row in rows:
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if not cells or len(cells) < 2:
            continue
        name = cells[0].lower()
        price_text = cells[1]
        if "bahia" in name:
            # Price is given per arroba (15 kg)
            price_bahia_arroba = parse_price(price_text)
        elif "pará" in name or "para" in name:
            # Determine unit from name string
            if "/kg" in name or " kg" in name:
                price_para_kg = parse_price(price_text)
            elif "/arroba" in name or "arroba" in name:
                price_para_arroba = parse_price(price_text)
            else:
                # If no unit specified, assume arroba
                price_para_arroba = parse_price(price_text)
    # Compute Bahia conversions
    price_bahia_kg = None
    price_bahia_saca = None
    if price_bahia_arroba is not None:
        price_bahia_kg = price_bahia_arroba / 15.0
        price_bahia_saca = price_bahia_kg * 60.0
    # Compute Pará conversions
    if price_para_arroba is not None:
        price_para_kg = price_para_arroba / 15.0
    elif price_para_kg is not None:
        price_para_arroba = price_para_kg * 15.0
    else:
        price_para_kg = None
    price_para_saca = None
    if price_para_kg is not None:
        price_para_saca = price_para_kg * 60.0
    return {
        "bahia": {
            "arroba": price_bahia_arroba,
            "kg": price_bahia_kg,
            "saca": price_bahia_saca,
        },
        "para": {
            "arroba": price_para_arroba,
            "kg": price_para_kg,
            "saca": price_para_saca,
        },
    }


def update_prices_json(prices: Dict[str, Dict[str, float]], now: datetime) -> None:
    """
    Write the latest cacao prices to ``data/prices.json``.

    The JSON structure mirrors the one used for the café site but
    includes only the ``cacau`` field. Date and time strings are
    included for informational purposes, and a boolean flag indicates
    whether the market is currently open.

    Args:
        prices: Nested dictionary with price data for Bahia and Pará.
        now: Current datetime used for timestamps.
    """
    data = {
        "ultima_atualizacao": now.isoformat(),
        "data_formatada": now.strftime("%d/%m/%Y"),
        "hora_formatada": now.strftime("%H:%M:%S"),
        "pregao_aberto": is_market_open(now),
        "fonte": "raspagem_automatizada",
        "cacau": {
            "bahia": {
                "preco": prices["bahia"]["arroba"],
                "unidade": "arroba",
                "peso_kg": 15,
                "moeda": "BRL",
                "preco_kg": prices["bahia"]["kg"],
                "preco_saca": prices["bahia"]["saca"],
            },
            "para": {
                "preco": prices["para"]["arroba"],
                "unidade": "arroba",
                "peso_kg": 15,
                "moeda": "BRL",
                "preco_kg": prices["para"]["kg"],
                "preco_saca": prices["para"]["saca"],
            },
        },
    }
    out_path = Path(__file__).resolve().parent / "data" / "prices.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_history_json(prices: Dict[str, Dict[str, float]], now: datetime) -> None:
    """
    Update the ``data/precos.json`` file with the latest prices.

    This function appends two records (one for Bahia and one for
    Pará) representing the closing prices for the current day. If
    entries already exist for today's date, they are removed before
    appending the new ones. The history is truncated to the last 10
    days by unique date.

    Args:
        prices: Dictionary containing price information per region.
        now: Current datetime used for timestamps and date strings.
    """
    hist_path = Path(__file__).resolve().parent / "data" / "precos.json"
    registros: List[Dict] = []
    if hist_path.exists():
        try:
            with hist_path.open("r", encoding="utf-8") as f:
                registros = json.load(f)
        except Exception:
            registros = []
    # Remove any records for today's date and cacau product
    hoje_str = now.strftime("%Y-%m-%d")
    filtrados = [r for r in registros if not (r.get("referente_a") == hoje_str and r.get("produto") == "cacau")]
    # Append today's data for Bahia and Pará
    filtrados.append({
        "produto": "cacau",
        "tipo": "bahia",
        "valor": prices["bahia"]["arroba"],
        "referente_a": hoje_str,
        "coletado_em": now.isoformat(),
        "unidade": "arroba",
    })
    filtrados.append({
        "produto": "cacau",
        "tipo": "para",
        "valor": prices["para"]["arroba"],
        "referente_a": hoje_str,
        "coletado_em": now.isoformat(),
        "unidade": "arroba",
    })
    # Keep only the last 10 unique dates
    # Group by date
    seen_dates = []
    result = []
    for item in sorted(filtrados, key=lambda r: (r["referente_a"], r["tipo"]), reverse=True):
        date = item["referente_a"]
        if date not in seen_dates:
            seen_dates.append(date)
        if len(seen_dates) <= 10:
            result.append(item)
    # Order result by date desc then type (bahia, para)
    result.sort(key=lambda r: (r["referente_a"], 0 if r["tipo"] == "bahia" else 1), reverse=True)
    # Write to file
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    with hist_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def main() -> None:
    """
    Entry point for the script. Fetch prices, update JSON files.

    This function orchestrates the price retrieval from the widget, the
    transformation into structured data, and the persistence into the
    ``data`` directory. It is intended to be executed by a GitHub
    Actions workflow or manually.
    """
    now = datetime.utcnow()
    widget_url = "https://www.noticiasagricolas.com.br/widgets/cotacoes?id=96"
    prices = fetch_cacau_prices(widget_url)
    update_prices_json(prices, now)
    update_history_json(prices, now)


if __name__ == "__main__":
    main()