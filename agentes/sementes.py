"""Procedimentos iniciais de cada agente e agenda padrão (em segundos)."""


def passo(acao, tentativas=0, **params):
    return {"acao": acao, "params": params, "tentativas": tentativas}


SEMENTES = {
    "shopee": {
        "relatorio_diario": [passo("buscar_pedidos"), passo("resumir")],
        "monitorar_concorrentes": [passo("buscar_precos_concorrentes"), passo("sugerir_preco", preco_minimo=90.0)],
    },
    "mercadolivre": {
        "responder_perguntas": [passo("buscar_perguntas"), passo("rascunhar_resposta")],
        "relatorio_diario": [passo("buscar_pedidos"), passo("resumir")],
    },
    "amazon": {
        "checar_estoque": [passo("checar_estoque"), passo("resumir")],
    },
    "tiktok": {
        "relatorio_diario": [passo("buscar_pedidos"), passo("resumir")],
    },
}

# Tarefas que só liberam o resultado depois do seu OK
EXIGE_APROVACAO = {
    "shopee": {"monitorar_concorrentes"},
    "mercadolivre": {"responder_perguntas"},
}

# Chance de falha por limite de requisições em cada conector simulado
P_LIMITE = {"shopee": 0.7, "mercadolivre": 0.5, "amazon": 0.6, "tiktok": 0.4}

# (intervalo em segundos, marketplace, tarefa)
AGENDA_PADRAO = [
    (86400, "shopee", "relatorio_diario"),
    (3600, "shopee", "monitorar_concorrentes"),
    (900, "mercadolivre", "responder_perguntas"),
    (86400, "mercadolivre", "relatorio_diario"),
    (1800, "amazon", "checar_estoque"),
    (86400, "tiktok", "relatorio_diario"),
]
