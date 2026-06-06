import os

# ── Mercado Livre ─────────────────────────────────────────────────────────────
ML_CLIENT_ID     = os.environ.get("ML_CLIENT_ID",     "")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET", "")
ML_SELLER_ID     = os.environ.get("ML_SELLER_ID",     "")
ML_REDIRECT_URI  = os.environ.get("ML_REDIRECT_URI",  "https://www.qubotech.com.br")

ML_API_BASE      = "https://api.mercadolibre.com"
ML_TOKEN_URL     = f"{ML_API_BASE}/oauth/token"

# ── Twilio WhatsApp ───────────────────────────────────────────────────────────
TWILIO_SID        = os.environ.get("TWILIO_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
WHATSAPP_FROM     = "whatsapp:+14155238886"   # Twilio sandbox
WHATSAPP_TO       = os.environ.get("WHATSAPP_TO", "")

# ── Banco de dados ────────────────────────────────────────────────────────────
# No Render com disco persistente, use /data/qubotech.db
# Localmente, salva na raiz do projeto
DB_PATH    = os.environ.get("DB_PATH",    "/data/qubotech.db" if os.path.exists("/data") else "qubotech.db")
TOKEN_FILE = os.environ.get("TOKEN_FILE", "/data/tokens.json"  if os.path.exists("/data") else "tokens.json")

# ── Coleta ────────────────────────────────────────────────────────────────────
COLETA_INTERVALO_HORAS = 12
RENDER_PING_INTERVAL   = 14   # minutos — usar UptimeRobot em /api/status

# ── Servidor web ──────────────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 5000))
