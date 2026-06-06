import sqlite3
import json
from datetime import datetime, date
from config import DB_PATH


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots_proprios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coletado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            item_id TEXT,
            titulo TEXT,
            preco REAL,
            status TEXT,
            visitas_30d INTEGER,
            total_vendido INTEGER,
            estoque_total INTEGER,
            reviews_count INTEGER,
            reviews_nota REAL,
            em_promocao INTEGER,
            preco_promocao REAL
        );

        CREATE TABLE IF NOT EXISTS snapshots_variacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coletado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            item_id TEXT,
            variation_id TEXT,
            cor TEXT,
            estoque INTEGER,
            vendido INTEGER,
            preco REAL
        );

        CREATE TABLE IF NOT EXISTS snapshots_concorrentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coletado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            item_id TEXT,
            vendedor_id TEXT,
            vendedor_nome TEXT,
            titulo TEXT,
            preco REAL,
            total_vendido INTEGER,
            reviews_count INTEGER,
            reviews_nota REAL,
            frete_gratis INTEGER,
            tipo_anuncio TEXT,
            posicao_busca INTEGER,
            termo_busca TEXT
        );

        CREATE TABLE IF NOT EXISTS pedidos (
            order_id TEXT PRIMARY KEY,
            date_created DATETIME,
            item_id TEXT,
            variation_id TEXT,
            quantidade INTEGER,
            preco_unitario REAL,
            total_amount REAL,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS historico_mensal (
            mes TEXT PRIMARY KEY,
            receita REAL,
            unidades INTEGER,
            pedidos INTEGER
        );

        CREATE TABLE IF NOT EXISTS alertas_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enviado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            tipo TEXT,
            mensagem TEXT,
            enviado INTEGER DEFAULT 0
        );
        """)


def seed_historico():
    historico = {
        "2025-12": {"receita": 86.13,    "unidades": 1,  "pedidos": 1},
        "2026-01": {"receita": 811.13,   "unidades": 9,  "pedidos": 9},
        "2026-02": {"receita": 1014.37,  "unidades": 9,  "pedidos": 9},
        "2026-03": {"receita": 639.40,   "unidades": 18, "pedidos": 16},
        "2026-04": {"receita": 1073.39,  "unidades": 52, "pedidos": 50},
        "2026-05": {"receita": 443.19,   "unidades": 21, "pedidos": 19},
        "2026-06": {"receita": 19.39,    "unidades": 1,  "pedidos": 1},
    }
    with _conn() as c:
        for mes, dados in historico.items():
            c.execute(
                "INSERT OR IGNORE INTO historico_mensal (mes, receita, unidades, pedidos) VALUES (?,?,?,?)",
                (mes, dados["receita"], dados["unidades"], dados["pedidos"])
            )


# ── Inserts ───────────────────────────────────────────────────────────────────

def inserir_snapshot_proprio(dados: dict):
    with _conn() as c:
        c.execute("""
            INSERT INTO snapshots_proprios
            (item_id, titulo, preco, status, visitas_30d, total_vendido,
             estoque_total, reviews_count, reviews_nota, em_promocao, preco_promocao)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            dados.get("item_id"), dados.get("titulo"), dados.get("preco"),
            dados.get("status"), dados.get("visitas_30d"), dados.get("total_vendido"),
            dados.get("estoque_total"), dados.get("reviews_count"), dados.get("reviews_nota"),
            1 if dados.get("em_promocao") else 0, dados.get("preco_promocao")
        ))


def inserir_variacoes(item_id: str, variacoes: list[dict]):
    with _conn() as c:
        for v in variacoes:
            c.execute("""
                INSERT INTO snapshots_variacoes
                (item_id, variation_id, cor, estoque, vendido, preco)
                VALUES (?,?,?,?,?,?)
            """, (
                item_id, v.get("variation_id"), v.get("cor"),
                v.get("estoque"), v.get("vendido"), v.get("preco")
            ))


def inserir_snapshot_concorrente(dados: dict):
    with _conn() as c:
        c.execute("""
            INSERT INTO snapshots_concorrentes
            (item_id, vendedor_id, vendedor_nome, titulo, preco, total_vendido,
             reviews_count, reviews_nota, frete_gratis, tipo_anuncio, posicao_busca, termo_busca)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            dados.get("item_id"), dados.get("vendedor_id"), dados.get("vendedor_nome"),
            dados.get("titulo"), dados.get("preco"), dados.get("total_vendido"),
            dados.get("reviews_count"), dados.get("reviews_nota"),
            1 if dados.get("frete_gratis") else 0,
            dados.get("tipo_anuncio"), dados.get("posicao_busca"), dados.get("termo_busca")
        ))


def inserir_pedido(dados: dict):
    with _conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO pedidos
            (order_id, date_created, item_id, variation_id, quantidade, preco_unitario, total_amount, status)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            dados.get("order_id"), dados.get("date_created"), dados.get("item_id"),
            dados.get("variation_id"), dados.get("quantidade"), dados.get("preco_unitario"),
            dados.get("total_amount"), dados.get("status")
        ))


def registrar_alerta(tipo: str, mensagem: str):
    with _conn() as c:
        c.execute(
            "INSERT INTO alertas_log (tipo, mensagem) VALUES (?,?)",
            (tipo, mensagem)
        )


def marcar_alerta_enviado(alerta_id: int):
    with _conn() as c:
        c.execute("UPDATE alertas_log SET enviado=1 WHERE id=?", (alerta_id,))


# ── Queries para o dashboard ──────────────────────────────────────────────────

def get_dashboard_data() -> dict:
    with _conn() as c:
        # Último snapshot de cada produto próprio
        proprios = c.execute("""
            SELECT s.*
            FROM snapshots_proprios s
            INNER JOIN (
                SELECT item_id, MAX(coletado_em) as max_dt
                FROM snapshots_proprios
                GROUP BY item_id
            ) latest ON s.item_id = latest.item_id AND s.coletado_em = latest.max_dt
            ORDER BY s.item_id
        """).fetchall()

        # Variações mais recentes por item
        variacoes = c.execute("""
            SELECT v.*
            FROM snapshots_variacoes v
            INNER JOIN (
                SELECT item_id, MAX(coletado_em) as max_dt
                FROM snapshots_variacoes
                GROUP BY item_id
            ) latest ON v.item_id = latest.item_id AND v.coletado_em = latest.max_dt
            ORDER BY v.item_id, v.cor
        """).fetchall()

        # Top concorrentes (última coleta)
        concorrentes = c.execute("""
            SELECT s.*
            FROM snapshots_concorrentes s
            INNER JOIN (
                SELECT item_id, MIN(posicao_busca) as min_pos, MAX(coletado_em) as max_dt
                FROM snapshots_concorrentes
                GROUP BY item_id
            ) latest ON s.item_id = latest.item_id AND s.coletado_em = latest.max_dt
            ORDER BY s.posicao_busca
            LIMIT 20
        """).fetchall()

        # Pedidos recentes
        pedidos_recentes = c.execute("""
            SELECT * FROM pedidos
            ORDER BY date_created DESC
            LIMIT 10
        """).fetchall()

        # Vendas hoje
        hoje = date.today().isoformat()
        vendas_hoje = c.execute("""
            SELECT COUNT(*) as pedidos, SUM(quantidade) as unidades, SUM(total_amount) as receita
            FROM pedidos
            WHERE date_created >= ?
        """, (hoje,)).fetchone()

        # Histórico mensal
        historico = c.execute("""
            SELECT * FROM historico_mensal ORDER BY mes DESC LIMIT 12
        """).fetchall()

        # Alertas ativos (não enviados ou recentes)
        alertas = c.execute("""
            SELECT * FROM alertas_log
            WHERE enviado = 0 OR enviado_em >= datetime('now', '-24 hours')
            ORDER BY enviado_em DESC
            LIMIT 20
        """).fetchall()

        # Última coleta
        ultima_coleta = c.execute("""
            SELECT MAX(coletado_em) as dt FROM snapshots_proprios
        """).fetchone()

        return {
            "proprios":        [dict(r) for r in proprios],
            "variacoes":       [dict(r) for r in variacoes],
            "concorrentes":    [dict(r) for r in concorrentes],
            "pedidos_recentes": [dict(r) for r in pedidos_recentes],
            "vendas_hoje":     dict(vendas_hoje) if vendas_hoje else {},
            "historico_mensal": [dict(r) for r in historico],
            "alertas":         [dict(r) for r in alertas],
            "ultima_coleta":   ultima_coleta["dt"] if ultima_coleta else None,
        }


def get_ultimo_pedido_date() -> str | None:
    with _conn() as c:
        row = c.execute("SELECT MAX(date_created) as dt FROM pedidos").fetchone()
        return row["dt"] if row else None


def get_alertas_pendentes() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM alertas_log WHERE enviado=0 ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def get_snapshot_anterior_proprio(item_id: str) -> dict | None:
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM snapshots_proprios
            WHERE item_id = ?
            ORDER BY coletado_em DESC
            LIMIT 2
        """, (item_id,)).fetchall()
        return dict(rows[1]) if len(rows) >= 2 else None
