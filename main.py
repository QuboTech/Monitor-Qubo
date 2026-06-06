import os
import threading
import schedule
import time
from datetime import datetime, timedelta

from flask import Flask, jsonify, send_from_directory, redirect

import db
import coleta
from config import PORT

app = Flask(__name__, static_folder="dashboard/static", static_url_path="/static")

# ── Rotas web ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("dashboard", "index.html")


@app.route("/mobile")
def mobile():
    return send_from_directory("dashboard", "mobile.html")


@app.route("/api/dados")
def api_dados():
    dados = db.get_dashboard_data()
    return jsonify(dados)


@app.route("/api/status")
def api_status():
    dados = db.get_dashboard_data()
    proxima = None
    if dados.get("ultima_coleta"):
        try:
            ultima = datetime.fromisoformat(dados["ultima_coleta"])
            proxima = (ultima + timedelta(hours=12)).isoformat()
        except Exception:
            pass
    return jsonify({
        "status":         "ok",
        "ultima_coleta":  dados.get("ultima_coleta"),
        "proxima_coleta": proxima,
        "alertas_ativos": len([a for a in dados.get("alertas", []) if not a.get("enviado")]),
    })


@app.route("/api/coletar", methods=["POST"])
def api_coletar():
    """Dispara coleta manual (protegida por token simples)."""
    token = os.environ.get("ADMIN_TOKEN", "")
    from flask import request
    if token and request.headers.get("X-Token") != token:
        return jsonify({"error": "Unauthorized"}), 401
    threading.Thread(target=coleta.executar, daemon=True).start()
    return jsonify({"status": "coleta iniciada"})


# ── Agendador ─────────────────────────────────────────────────────────────────

_proxima_coleta: str = ""


def job_coleta():
    global _proxima_coleta
    print(f"\n[main] Iniciando coleta agendada — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    coleta.executar()
    proxima = datetime.now() + timedelta(hours=12)
    _proxima_coleta = proxima.strftime("%d/%m %H:%M")
    print(f"[main] Próxima coleta agendada para {_proxima_coleta}")


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(30)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("QUBOTECH Monitor iniciando...")
    print("=" * 50)

    # Inicializar banco e popular histórico
    db.init_db()
    db.seed_historico()
    print("[main] Banco de dados pronto.")

    # Coleta inicial imediata em background
    threading.Thread(target=job_coleta, daemon=True).start()

    # Agendar a cada 12 horas
    schedule.every(12).hours.do(job_coleta)

    # Thread do agendador
    threading.Thread(target=run_scheduler, daemon=True).start()
    print(f"[main] Agendador iniciado — coleta a cada 12h")

    # Subir Flask
    print(f"[main] Servidor web em http://0.0.0.0:{PORT}")
    print(f"[main]   Dashboard:  http://localhost:{PORT}/")
    print(f"[main]   Mobile:     http://localhost:{PORT}/mobile")
    print(f"[main]   Status API: http://localhost:{PORT}/api/status")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
