"""Configuração do painel: fica em dados/config.json e é aplicada nos agentes em funcionamento."""
import copy
import json
import threading
from pathlib import Path

from .sementes import AGENDA_PADRAO, EXIGE_APROVACAO, SEMENTES


def padrao():
    return {
        "agentes": {m: {"ativo": True} for m in SEMENTES},
        "agenda": [
            {"marketplace": m, "tarefa": t, "cada_minutos": max(1, s // 60), "ativa": True}
            for s, m, t in AGENDA_PADRAO
        ],
        "exige_aprovacao": {m: sorted(EXIGE_APROVACAO.get(m, ())) for m in SEMENTES},
        "aprendizado": {"limiar_falha_pct": 25, "minimo_execucoes": 4},
    }


def _inteiro(valor, minimo, maximo, padrao_):
    try:
        return max(minimo, min(maximo, int(valor)))
    except (TypeError, ValueError):
        return padrao_


class Configuracao:
    def __init__(self, arquivo):
        self.arquivo = Path(arquivo)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.dados = padrao()
        if self.arquivo.exists():
            try:
                self.dados = self.limpar(json.loads(self.arquivo.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass  # arquivo corrompido: volta para o padrão

    @staticmethod
    def limpar(novo):
        """Valida a configuração recebida: só aceita agentes e tarefas que existem e limita os números."""
        base = padrao()
        novo = novo if isinstance(novo, dict) else {}
        for m in SEMENTES:
            ativo = (novo.get("agentes", {}).get(m) or {}).get("ativo", True)
            base["agentes"][m]["ativo"] = bool(ativo)
        agenda = []
        vistos = set()
        for a in novo.get("agenda", []) if isinstance(novo.get("agenda"), list) else []:
            m, t = a.get("marketplace"), a.get("tarefa")
            if m in SEMENTES and t in SEMENTES[m] and (m, t) not in vistos:
                vistos.add((m, t))
                agenda.append({"marketplace": m, "tarefa": t,
                               "cada_minutos": _inteiro(a.get("cada_minutos"), 1, 10080, 60),
                               "ativa": bool(a.get("ativa", True))})
        if agenda:
            base["agenda"] = agenda
        exige = novo.get("exige_aprovacao")
        if isinstance(exige, dict):
            for m in SEMENTES:
                lista = exige.get(m, base["exige_aprovacao"][m])
                base["exige_aprovacao"][m] = sorted({t for t in lista if t in SEMENTES[m]}) if isinstance(lista, list) else []
        apr = novo.get("aprendizado") or {}
        base["aprendizado"] = {
            "limiar_falha_pct": _inteiro(apr.get("limiar_falha_pct"), 5, 80, 25),
            "minimo_execucoes": _inteiro(apr.get("minimo_execucoes"), 2, 30, 4),
        }
        return base

    def atualizar(self, novo):
        with self._lock:
            self.dados = self.limpar(novo)
            self.arquivo.write_text(json.dumps(self.dados, ensure_ascii=False, indent=2), encoding="utf-8")
            return copy.deepcopy(self.dados)

    def aplicar(self, orq):
        c = self.dados
        for m, ag in orq.agentes.items():
            ag.ativo = c["agentes"][m]["ativo"]
            ag.exige_aprovacao = set(c["exige_aprovacao"].get(m, []))
        melhorador = next(iter(orq.agentes.values())).melhorador
        melhorador.limiar_falha = c["aprendizado"]["limiar_falha_pct"] / 100
        melhorador.minimo_execucoes = c["aprendizado"]["minimo_execucoes"]
        orq.definir_agenda(
            [(a["cada_minutos"] * 60, a["marketplace"], a["tarefa"]) for a in c["agenda"] if a["ativa"]],
            imediato=False,
        )
