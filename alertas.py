import os
import json
from config import TWILIO_SID, TWILIO_AUTH_TOKEN, WHATSAPP_FROM, WHATSAPP_TO
import db


def _enviar_whatsapp(mensagem: str):
    if not TWILIO_SID or not TWILIO_AUTH_TOKEN or not WHATSAPP_TO:
        print(f"[alertas] WhatsApp não configurado — mensagem: {mensagem}")
        return

    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=mensagem,
            from_=WHATSAPP_FROM,
            to=WHATSAPP_TO,
        )
        print(f"[alertas] WhatsApp enviado: {mensagem[:60]}...")
    except Exception as e:
        print(f"[alertas] Erro ao enviar WhatsApp: {e}")


def _load_produtos() -> dict:
    with open("produtos.json") as f:
        return json.load(f)


def verificar_estoque(dados: dict) -> list[dict]:
    """Verifica estoque crítico nas variações."""
    config = _load_produtos()
    minimos = {p["item_id"]: p.get("estoque_alerta_minimo", 5) for p in config["produtos"]}
    alertas = []

    variacoes_por_item: dict[str, list] = {}
    for v in dados.get("variacoes", []):
        variacoes_por_item.setdefault(v["item_id"], []).append(v)

    for prop in dados.get("proprios", []):
        item_id = prop["item_id"]
        minimo  = minimos.get(item_id, 5)
        variacoes = variacoes_por_item.get(item_id, [])

        if variacoes:
            for v in variacoes:
                estoque = v.get("estoque", 0) or 0
                if estoque <= minimo:
                    cor = v.get("cor") or "Sem variação"
                    alertas.append({
                        "tipo": "ESTOQUE_CRITICO",
                        "mensagem": (
                            f"⚠️ ESTOQUE CRÍTICO: {cor} do {prop['titulo'][:30]} "
                            f"com apenas {estoque} unidades"
                        ),
                    })
        else:
            estoque = prop.get("estoque_total", 0) or 0
            if estoque <= minimo:
                alertas.append({
                    "tipo": "ESTOQUE_CRITICO",
                    "mensagem": (
                        f"⚠️ ESTOQUE CRÍTICO: {prop['titulo'][:30]} "
                        f"com apenas {estoque} unidades"
                    ),
                })
    return alertas


def verificar_preco_concorrente(dados: dict) -> list[dict]:
    """Verifica se concorrente está mais barato."""
    alertas = []
    meu_menor_preco = min(
        (p["preco"] for p in dados.get("proprios", []) if p.get("preco")),
        default=None
    )
    if meu_menor_preco is None:
        return alertas

    vistos = set()
    for conc in dados.get("concorrentes", []):
        preco_conc = conc.get("preco", 0) or 0
        item_id    = conc.get("item_id", "")
        if preco_conc > 0 and preco_conc < meu_menor_preco and item_id not in vistos:
            vistos.add(item_id)
            nome = conc.get("vendedor_nome") or conc.get("item_id", "")
            alertas.append({
                "tipo": "PRECO_CONCORRENTE",
                "mensagem": (
                    f"📉 CONCORRENTE: {nome[:20]} vendendo por "
                    f"R${preco_conc:.2f} (você: R${meu_menor_preco:.2f})"
                ),
            })
    return alertas


def verificar_margem_negativa(dados: dict) -> list[dict]:
    """Verifica margem negativa nos próprios anúncios."""
    config = _load_produtos()
    custos = config.get("custos_fixos", {})
    prod_cfg = {p["item_id"]: p for p in config["produtos"]}
    alertas = []

    for prop in dados.get("proprios", []):
        item_id = prop["item_id"]
        preco   = prop.get("preco", 0) or 0
        pc      = prod_cfg.get(item_id, {}).get("preco_custo", 4.255)

        comissao  = custos.get("comissao_classico_pct", 0.115)
        envio     = custos.get("envio_flex_liquido", 4.30)
        embalagem = custos.get("custo_embalagem", 0.50)
        margem    = preco * (1 - comissao) - envio - embalagem - pc

        if margem < 0:
            alertas.append({
                "tipo": "MARGEM_NEGATIVA",
                "mensagem": (
                    f"🚨 MARGEM NEGATIVA: {prop['titulo'][:30]} "
                    f"vendendo a R${preco:.2f} (perda de R${abs(margem):.2f})"
                ),
            })
    return alertas


def verificar_anuncio_pausado(dados: dict) -> list[dict]:
    alertas = []
    for prop in dados.get("proprios", []):
        status = prop.get("status", "active")
        if status != "active":
            alertas.append({
                "tipo": "ANUNCIO_PAUSADO",
                "mensagem": (
                    f"❌ ANÚNCIO PAUSADO: {prop['titulo'][:30]} "
                    f"está com status '{status}'"
                ),
            })
    return alertas


def verificar_e_enviar():
    print("[alertas] Verificando condições de alerta...")
    dados = db.get_dashboard_data()

    todos_alertas = []
    todos_alertas += verificar_estoque(dados)
    todos_alertas += verificar_preco_concorrente(dados)
    todos_alertas += verificar_margem_negativa(dados)
    todos_alertas += verificar_anuncio_pausado(dados)

    if not todos_alertas:
        print("[alertas] Nenhum alerta gerado.")
        return

    for alerta in todos_alertas:
        db.registrar_alerta(alerta["tipo"], alerta["mensagem"])

    # Buscar pendentes e enviar
    pendentes = db.get_alertas_pendentes()
    if pendentes:
        resumo = "\n".join(a["mensagem"] for a in pendentes[:10])
        _enviar_whatsapp(f"QUBOTECH Monitor:\n\n{resumo}")
        for a in pendentes:
            db.marcar_alerta_enviado(a["id"])

    print(f"[alertas] {len(todos_alertas)} alertas processados")
