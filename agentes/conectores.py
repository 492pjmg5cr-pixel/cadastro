"""Conectores com os marketplaces.

ConectorSimulado permite testar todo o sistema sem tocar em conta real.
Para usar de verdade, crie uma classe que herde de Conector e chame a API OFICIAL
do marketplace dentro de `chamar` (Shopee Open Platform, API do Mercado Livre,
Selling Partner API da Amazon, API do TikTok Shop).
"""
import random


class ErroConector(Exception):
    pass


class LimiteDeRequisicoes(ErroConector):
    pass


class Conector:
    nome = "base"

    def chamar(self, acao, params, ctx):
        raise NotImplementedError


ACOES_COM_LIMITE = {"buscar_pedidos", "buscar_perguntas", "buscar_precos_concorrentes", "checar_estoque"}


class ConectorSimulado(Conector):
    """Simula um marketplace. Leituras falham com frequência por limite de requisições,
    a menos que o procedimento tenha feito uma pausa antes (`resfriado`)."""

    def __init__(self, nome, p_limite=0.6, semente=None):
        self.nome = nome
        self.p_limite = p_limite
        self.rng = random.Random(semente)

    def chamar(self, acao, params, ctx):
        funcao = getattr(self, f"_{acao}", None)
        if funcao is None:
            raise ErroConector(f"ação desconhecida: {acao}")
        if acao in ACOES_COM_LIMITE:
            p = 0.05 if ctx.get("resfriado") else self.p_limite
            if self.rng.random() < p:
                raise LimiteDeRequisicoes(f"{self.nome}: limite de requisições atingido em {acao}")
        return funcao(params, ctx)

    def _buscar_pedidos(self, params, ctx):
        prefixo = self.nome[:3].upper()
        ctx["pedidos"] = [
            {"id": f"{prefixo}-{i:04d}", "valor": round(self.rng.uniform(19.9, 249.9), 2)}
            for i in range(self.rng.randint(3, 25))
        ]

    def _buscar_perguntas(self, params, ctx):
        modelos = ["Tem em estoque?", "Qual o prazo de entrega?", "Aceita troca?", "Tem nota fiscal?"]
        ctx["perguntas"] = [
            {"id": f"P{i}", "texto": self.rng.choice(modelos)} for i in range(self.rng.randint(1, 6))
        ]

    def _rascunhar_resposta(self, params, ctx):
        respostas = {
            "estoque": "Olá! Sim, temos o produto disponível e pronto para envio.",
            "prazo": "Olá! O prazo é informado no carrinho conforme o seu CEP.",
            "troca": "Olá! Aceitamos troca em até 7 dias após o recebimento.",
            "nota": "Olá! Sim, enviamos nota fiscal com o pedido.",
        }
        rascunhos = []
        for p in ctx.get("perguntas", []):
            t = p["texto"].lower()
            chave = next((k for k in respostas if k in t), "prazo")
            rascunhos.append({"pergunta_id": p["id"], "pergunta": p["texto"], "resposta": respostas[chave]})
        ctx["rascunhos"] = rascunhos

    def _buscar_precos_concorrentes(self, params, ctx):
        ctx["concorrentes"] = [
            {"sku": f"SKU-{i}", "meu_preco": 100.0, "menor_concorrente": round(self.rng.uniform(85, 115), 2)}
            for i in range(self.rng.randint(2, 6))
        ]

    def _sugerir_preco(self, params, ctx):
        margem_minima = params.get("preco_minimo", 90.0)
        ctx["sugestoes"] = [
            {"sku": c["sku"], "de": c["meu_preco"], "para": max(margem_minima, round(c["menor_concorrente"] * 0.99, 2))}
            for c in ctx.get("concorrentes", [])
            if c["menor_concorrente"] < c["meu_preco"]
        ]

    def _checar_estoque(self, params, ctx):
        ctx["estoque"] = [{"sku": f"SKU-{i}", "qtd": self.rng.randint(0, 30)} for i in range(8)]
