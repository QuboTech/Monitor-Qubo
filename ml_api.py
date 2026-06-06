import json
import os
import time
import requests
from datetime import datetime
from config import (
    ML_API_BASE, ML_TOKEN_URL,
    ML_CLIENT_ID, ML_CLIENT_SECRET,
    TOKEN_FILE
)

_tokens: dict = {}


def _load_tokens() -> dict:
    global _tokens
    if _tokens:
        return _tokens
    refresh_env = os.environ.get("ML_REFRESH_TOKEN", "")
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE) as f:
                _tokens = json.load(f)
            return _tokens
        except Exception:
            pass
    _tokens = {"refresh_token": refresh_env, "access_token": "", "expires_at": 0}
    return _tokens


def _save_tokens(data: dict):
    global _tokens
    _tokens = data
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[ml_api] Aviso: não foi possível salvar tokens.json — {e}")


def renovar_token() -> str:
    tokens = _load_tokens()
    refresh_token = tokens.get("refresh_token") or os.environ.get("ML_REFRESH_TOKEN", "")
    if not refresh_token:
        raise RuntimeError("ML_REFRESH_TOKEN não configurado")

    resp = requests.post(ML_TOKEN_URL, data={
        "grant_type":    "refresh_token",
        "client_id":     ML_CLIENT_ID,
        "client_secret": ML_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    _save_tokens({
        "access_token":  data["access_token"],
        "refresh_token": data["refresh_token"],  # rotaciona a cada uso
        "expires_at":    time.time() + data.get("expires_in", 21600) - 300,
    })
    print(f"[ml_api] Token renovado. Expira em ~{data.get('expires_in', 21600)//3600}h")
    return data["access_token"]


def _get_token() -> str:
    tokens = _load_tokens()
    if not tokens.get("access_token") or time.time() >= tokens.get("expires_at", 0):
        return renovar_token()
    return tokens["access_token"]


def _get(path: str, params: dict = None, retries: int = 2) -> dict:
    token = _get_token()
    url = f"{ML_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 401:
                # Token expirou na prática — renovar e tentar de novo
                token = renovar_token()
                headers["Authorization"] = f"Bearer {token}"
                resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt == retries:
                print(f"[ml_api] Erro em GET {path}: {e}")
                return {}
            time.sleep(2 ** attempt)
    return {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

def get_item(item_id: str) -> dict:
    return _get(f"/items/{item_id}")


def get_visitas(item_id: str) -> int:
    ending = datetime.now().strftime("%Y-%m-%d")
    data = _get(f"/items/{item_id}/visits/time_window", {
        "last": 30, "unit": "day", "ending": ending
    })
    return data.get("total_visits", 0)


def get_reviews(item_id: str) -> tuple[int, float]:
    data = _get(f"/reviews/item/{item_id}")
    return data.get("paging", {}).get("total", 0), data.get("rating_average", 0.0)


def get_pedidos(seller_id: str, desde: str = None, offset: int = 0, limit: int = 50) -> dict:
    params = {
        "seller": seller_id,
        "sort":   "date_desc",
        "offset": offset,
        "limit":  limit,
    }
    if desde:
        params["date_created.from"] = desde
    return _get("/orders/search", params)


def buscar_itens(termo: str, limite: int = 10) -> list[dict]:
    data = _get("/sites/MLB/search", {"q": termo, "limit": limite})
    return data.get("results", [])


def get_seller_info(seller_id: str) -> dict:
    return _get(f"/users/{seller_id}")


def get_item_batch(item_ids: list[str]) -> list[dict]:
    """Busca múltiplos itens de uma vez (máx 20 por chamada)."""
    results = []
    for i in range(0, len(item_ids), 20):
        batch = item_ids[i:i+20]
        ids_str = ",".join(batch)
        data = _get(f"/items", {"ids": ids_str})
        if isinstance(data, list):
            for entry in data:
                if entry.get("code") == 200:
                    results.append(entry.get("body", {}))
    return results
