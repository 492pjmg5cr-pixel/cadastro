"""Biblioteca de procedimentos.

O que cada agente aprendeu fica guardado aqui: um arquivo JSON por procedimento,
com versões, pontuação, histórico de execuções e feedback das aprovações.
"""
import copy
import json
import random
import threading
import time
from pathlib import Path

MIN_TESTE = 4  # execuções mínimas de uma versão candidata antes de decidir


def agora():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def pontuacao(versao):
    """Taxa de sucesso suavizada: começa em 0,5 e converge para a taxa real."""
    return (versao["sucessos"] + 1) / (versao["execucoes"] + 2)


def assinatura(passos):
    return json.dumps(passos, sort_keys=True, ensure_ascii=False)


class BibliotecaProcedimentos:
    def __init__(self, pasta):
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ---------- leitura e escrita ----------
    def _arquivo(self, pid):
        return self.pasta / f"{pid}.json"

    def existe(self, pid):
        return self._arquivo(pid).exists()

    def carregar(self, pid):
        with self._lock:
            return json.loads(self._arquivo(pid).read_text(encoding="utf-8"))

    def salvar(self, proc):
        with self._lock:
            destino = self._arquivo(proc["id"])
            tmp = destino.with_suffix(".tmp")
            tmp.write_text(json.dumps(proc, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(destino)

    def listar(self):
        with self._lock:
            return [self.carregar(p.stem) for p in sorted(self.pasta.glob("*.json"))]

    # ---------- criação ----------
    def criar_se_nao_existe(self, pid, marketplace, tarefa, passos):
        with self._lock:
            if self.existe(pid):
                return self.carregar(pid)
            proc = {
                "id": pid,
                "marketplace": marketplace,
                "tarefa": tarefa,
                "ultima_versao": 1,
                "campeao": {"versao": 1, "passos": copy.deepcopy(passos), "execucoes": 0, "sucessos": 0},
                "candidato": None,
                "descartados": [],
                "historico": [{"versao": 1, "motivo": "versão inicial", "em": agora()}],
                "execucoes_recentes": [],
                "feedback": {"aprovados": 0, "rejeitados": 0},
                "notas": [],
            }
            self.salvar(proc)
            return proc

    # ---------- uso ----------
    def escolher_versao(self, proc, prob_candidato=0.5):
        """Devolve ('campeao'|'candidato', cópia da versão a executar)."""
        cand = proc.get("candidato")
        if cand and random.random() < prob_candidato:
            return "candidato", copy.deepcopy(cand)
        return "campeao", copy.deepcopy(proc["campeao"])

    def registrar_execucao(self, pid, qual, num_versao, ok, erros, segundos):
        with self._lock:
            proc = self.carregar(pid)
            alvo = proc["campeao"] if qual == "campeao" else proc["candidato"]
            if alvo is not None and alvo["versao"] == num_versao:
                alvo["execucoes"] += 1
                alvo["sucessos"] += int(ok)
            proc["execucoes_recentes"].append(
                {"versao": num_versao, "qual": qual, "ok": ok, "erros": erros,
                 "segundos": round(segundos, 3), "em": agora()}
            )
            proc["execucoes_recentes"] = proc["execucoes_recentes"][-60:]
            self._avaliar_candidato(proc)
            self.salvar(proc)
            return proc

    def registrar_feedback(self, pid, aprovado, motivo=""):
        with self._lock:
            proc = self.carregar(pid)
            proc["feedback"]["aprovados" if aprovado else "rejeitados"] += 1
            if not aprovado and motivo:
                proc["notas"].append({"em": agora(), "rejeicao": motivo})
            self.salvar(proc)

    # ---------- aprendizado ----------
    def propor_candidato(self, pid, passos, motivo):
        """Cria uma versão candidata (só uma por vez). Devolve True se criou."""
        with self._lock:
            proc = self.carregar(pid)
            sig = assinatura(passos)
            if proc["candidato"] or sig in proc["descartados"] or sig == assinatura(proc["campeao"]["passos"]):
                return False
            proc["ultima_versao"] += 1
            v = proc["ultima_versao"]
            proc["candidato"] = {"versao": v, "passos": passos, "execucoes": 0, "sucessos": 0, "motivo": motivo}
            proc["historico"].append({"versao": v, "motivo": f"candidata: {motivo}", "em": agora()})
            self.salvar(proc)
            return True

    def _avaliar_candidato(self, proc):
        cand = proc.get("candidato")
        if not cand or cand["execucoes"] < MIN_TESTE:
            return
        champ = proc["campeao"]
        resumo = (f"{cand['sucessos']}/{cand['execucoes']} contra "
                  f"{champ['sucessos']}/{champ['execucoes']} da v{champ['versao']}")
        if pontuacao(cand) > pontuacao(champ):
            proc["historico"].append({"versao": cand["versao"], "motivo": f"promovida ({resumo})", "em": agora()})
            proc["campeao"] = {"versao": cand["versao"], "passos": cand["passos"],
                               "execucoes": cand["execucoes"], "sucessos": cand["sucessos"]}
        else:
            proc["descartados"].append(assinatura(cand["passos"]))
            proc["historico"].append({"versao": cand["versao"], "motivo": f"descartada ({resumo})", "em": agora()})
        proc["candidato"] = None
