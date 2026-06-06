import json
from datetime import datetime

import db
import ml_api
from config import ML_SELLER_ID


def _load_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _calcular_margem(preco: float, preco_custo: float, custos: dict, em_promocao: bool = False) -> float:
    comissao = custos.get("comissao_classico_pct", 0.115)
    envio    = custos.get("envio_flex_liquido",    4.30)
    embalagem = custos.get("custo_embalagem",      0.50)
    margem = preco * (1 - comissao) - envio - embalagem - preco_custo
    return round(margem, 2)


def _extrair_variacoes(item_data: dict) -> list[dict]:
    variacoes = []
    for v in item_data.get("variations", []):
        cor = ""
        for attr in v.get("attribute_combinations", []):
            if attr.get("id") in ("COLOR", "COR", "color"):
                cor = attr.get("value_name", "")
                break
        variacoes.append({
            "variation_id": str(v.get("id", "")),
            "cor":    cor,
            "estoque": v.get("available_quantity", 0),
            "vendido": v.get("sold_quantity", 0),
            "preco":   v.get("price") or item_data.get("price", 0),
        })
    return variacoes


def coletar_proprios():
    print("[coleta] Coletando anúncios próprios...")
    config = _load_json("produtos.json")
    produtos = [p for p in config["produtos"] if p.get("ativo")]
    custos   = config.get("custos_fixos", {})

    for produto in produtos:
        item_id = produto["item_id"]
        try:
            item = ml_api.get_item(item_id)
            if not item or item.get("error"):
                print(f"[coleta] Item {item_id} não encontrado: {item.get('error')}")
                continue

            visitas   = ml_api.get_visitas(item_id)
            rev_count, rev_nota = ml_api.get_reviews(item_id)

            preco = item.get("price", 0)
            em_promo = bool(item.get("original_price") and item["original_price"] > preco)

            snapshot = {
                "item_id":       item_id,
                "titulo":        item.get("title", ""),
                "preco":         preco,
                "status":        item.get("status", ""),
                "visitas_30d":   visitas,
                "total_vendido": item.get("sold_quantity", 0),
                "estoque_total": item.get("available_quantity", 0),
                "reviews_count": rev_count,
                "reviews_nota":  rev_nota,
                "em_promocao":   em_promo,
                "preco_promocao": item.get("original_price"),
            }
            db.inserir_snapshot_proprio(snapshot)

            variacoes = _extrair_variacoes(item)
            if variacoes:
                db.inserir_variacoes(item_id, variacoes)

            print(f"[coleta]   {item_id} OK — R${preco} | estoque:{item.get('available_quantity')} | visitas:{visitas}")

        except Exception as e:
            print(f"[coleta] Erro em {item_id}: {e}")


def coletar_pedidos():
    print("[coleta] Coletando pedidos...")
    desde = db.get_ultimo_pedido_date()
    offset = 0
    total_novos = 0

    while True:
        resultado = ml_api.get_pedidos(ML_SELLER_ID, desde=desde, offset=offset)
        pedidos = resultado.get("results", [])
        if not pedidos:
            break

        for pedido in pedidos:
            order_id = str(pedido.get("id", ""))
            date_created = pedido.get("date_created", "")

            for item in pedido.get("order_items", []):
                db.inserir_pedido({
                    "order_id":      order_id,
                    "date_created":  date_created,
                    "item_id":       item.get("item", {}).get("id", ""),
                    "variation_id":  str(item.get("item", {}).get("variation_id") or ""),
                    "quantidade":    item.get("quantity", 1),
                    "preco_unitario": item.get("unit_price", 0),
                    "total_amount":  pedido.get("total_amount", 0),
                    "status":        pedido.get("status", ""),
                })
            total_novos += 1

        paging = resultado.get("paging", {})
        offset += paging.get("limit", 50)
        if offset >= paging.get("total", 0):
            break

    print(f"[coleta] {total_novos} pedidos novos coletados")


def coletar_concorrentes():
    print("[coleta] Coletando concorrentes...")
    config    = _load_json("concorrentes.json")
    fixos     = [c for c in config.get("concorrentes", []) if c.get("ativo")]
    busca_cfg = config.get("busca_automatica", {})

    # IDs fixos configurados
    for conc in fixos:
        item_id = conc["item_id"]
        try:
            item = ml_api.get_item(item_id)
            if not item or item.get("error"):
                continue
            seller = item.get("seller", {})
            rev_count, rev_nota = ml_api.get_reviews(item_id)
            db.inserir_snapshot_concorrente({
                "item_id":       item_id,
                "vendedor_id":   str(seller.get("id", "")),
                "vendedor_nome": conc.get("nome", seller.get("nickname", "")),
                "titulo":        item.get("title", ""),
                "preco":         item.get("price", 0),
                "total_vendido": item.get("sold_quantity", 0),
                "reviews_count": rev_count,
                "reviews_nota":  rev_nota,
                "frete_gratis":  item.get("shipping", {}).get("free_shipping", False),
                "tipo_anuncio":  item.get("listing_type_id", ""),
                "posicao_busca": 0,
                "termo_busca":   "",
            })
        except Exception as e:
            print(f"[coleta] Erro concorrente {item_id}: {e}")

    # Busca automática por termos
    if busca_cfg.get("ativo"):
        termos = busca_cfg.get("termos", [])
        top_n  = busca_cfg.get("top_n_resultados", 10)
        seller_id_proprio = ML_SELLER_ID

        for termo in termos:
            try:
                resultados = ml_api.buscar_itens(termo, limite=top_n)
                for pos, item in enumerate(resultados, start=1):
                    # Ignorar próprios anúncios
                    seller = item.get("seller", {})
                    if str(seller.get("id", "")) == str(seller_id_proprio):
                        continue
                    db.inserir_snapshot_concorrente({
                        "item_id":       item.get("id", ""),
                        "vendedor_id":   str(seller.get("id", "")),
                        "vendedor_nome": seller.get("nickname", ""),
                        "titulo":        item.get("title", ""),
                        "preco":         item.get("price", 0),
                        "total_vendido": item.get("sold_quantity", 0),
                        "reviews_count": item.get("reviews", {}).get("rating_total", 0),
                        "reviews_nota":  item.get("reviews", {}).get("rating_average", 0.0),
                        "frete_gratis":  item.get("shipping", {}).get("free_shipping", False),
                        "tipo_anuncio":  item.get("listing_type_id", ""),
                        "posicao_busca": pos,
                        "termo_busca":   termo,
                    })
                print(f"[coleta]   Busca '{termo}': {len(resultados)} itens")
            except Exception as e:
                print(f"[coleta] Erro busca '{termo}': {e}")


def executar():
    inicio = datetime.now()
    print(f"\n{'='*50}")
    print(f"[coleta] INÍCIO {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*50}")

    try:
        ml_api.renovar_token()
    except Exception as e:
        print(f"[coleta] AVISO: falha ao renovar token — {e}. Tentando com token existente.")

    coletar_proprios()
    coletar_pedidos()
    coletar_concorrentes()

    from alertas import verificar_e_enviar
    verificar_e_enviar()

    duracao = (datetime.now() - inicio).seconds
    print(f"[coleta] CONCLUÍDO em {duracao}s\n")
