"""Melhorador: lê as falhas de um procedimento e propõe uma versão candidata.

As regras abaixo funcionam sem internet nem IA. Para casos que as regras não cobrem,
passe `gancho_llm(proc, execucoes) -> (passos, motivo) | None`, que pode chamar um
modelo de linguagem para sugerir novos passos a partir dos erros.
"""
import copy
from collections import Counter


class Melhorador:
    def __init__(self, biblioteca, gancho_llm=None, limiar_falha=0.25, janela=10, minimo_execucoes=4):
        self.biblioteca = biblioteca
        self.gancho_llm = gancho_llm
        self.limiar_falha = limiar_falha
        self.janela = janela
        self.minimo_execucoes = minimo_execucoes

    def talvez_melhorar(self, pid):
        proc = self.biblioteca.carregar(pid)
        if proc["candidato"]:
            return None
        champ = proc["campeao"]
        recentes = [r for r in proc["execucoes_recentes"]
                    if r["qual"] == "campeao" and r["versao"] == champ["versao"]][-self.janela:]
        if len(recentes) < self.minimo_execucoes:
            return None
        taxa_falha = sum(1 for r in recentes if not r["ok"]) / len(recentes)
        if taxa_falha < self.limiar_falha:
            return None
        proposta = self._regras(champ["passos"], recentes)
        if proposta is None and self.gancho_llm:
            proposta = self.gancho_llm(proc, recentes)
        if proposta is None:
            return None
        passos, motivo = proposta
        return motivo if self.biblioteca.propor_candidato(pid, passos, motivo) else None

    def _regras(self, passos, recentes):
        contagem = Counter()
        for r in recentes:
            for e in r["erros"]:
                contagem[(e["acao"], e["erro"])] += 1
        if not contagem:
            return None
        (acao, erro), n = contagem.most_common(1)[0]
        if n < 2:
            return None
        novos = copy.deepcopy(passos)
        idx = next((i for i, p in enumerate(novos) if p["acao"] == acao), None)
        if idx is None:
            return None
        if erro == "LimiteDeRequisicoes":
            if not any(p["acao"] == "pausar" for p in novos[:idx]):
                novos.insert(idx, {"acao": "pausar", "params": {"segundos": 0.05}})
                return novos, f"'{acao}' falhou {n}x por limite de requisições: inserida pausa antes"
            tentativas = novos[idx].get("tentativas", 0)
            if tentativas < 3:
                novos[idx]["tentativas"] = tentativas + 1
                return novos, f"'{acao}' ainda falha com pausa: tentativas {tentativas} -> {tentativas + 1}"
        return None
