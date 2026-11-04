"""Orquestrador: fila de tarefas, agendador e trabalhadores que rodam em segundo plano."""
import collections
import itertools
import json
import queue
import threading
import time
from collections import Counter
from pathlib import Path


class Orquestrador:
    def __init__(self, agentes, biblioteca, aprovacoes, pasta_dados, trabalhadores=1, log=print):
        self.agentes = agentes
        self.biblioteca = biblioteca
        self.aprovacoes = aprovacoes
        self.log = log
        self.pasta = Path(pasta_dados)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo_log = self.pasta / "execucoes.jsonl"
        self.fila = queue.PriorityQueue()
        self._ordem = itertools.count()
        self._parar = threading.Event()
        self._agenda = []
        self._lock_agenda = threading.Lock()
        self._threads = []
        self._n_trabalhadores = trabalhadores
        self.contadores = Counter()
        self.eventos = collections.deque(maxlen=80)  # atividade recente (painel)

    def _evento(self, tipo, texto):
        self.eventos.append({"em": time.strftime("%H:%M:%S"), "tipo": tipo, "texto": texto})

    # ---------- tarefas ----------
    def enfileirar(self, marketplace, tarefa, params=None, prioridade=5):
        self.fila.put((prioridade, next(self._ordem), marketplace, tarefa, params or {}))

    def agendar(self, cada_segundos, marketplace, tarefa, params=None, prioridade=5, imediato=True):
        with self._lock_agenda:
            self._agenda.append({"cada": cada_segundos, "mkt": marketplace, "tarefa": tarefa,
                                 "params": params, "prio": prioridade,
                                 "proxima": time.time() + (0 if imediato else cada_segundos)})

    def definir_agenda(self, itens, imediato=False):
        """itens: lista de (cada_segundos, marketplace, tarefa). Mantém o relógio das entradas que não mudaram."""
        with self._lock_agenda:
            antigas = {(a["mkt"], a["tarefa"], a["cada"]): a["proxima"] for a in self._agenda}
            nova = []
            for cada, mkt, tarefa in itens:
                proxima = antigas.get((mkt, tarefa, cada), time.time() + (0 if imediato else cada))
                nova.append({"cada": cada, "mkt": mkt, "tarefa": tarefa, "params": None, "prio": 5, "proxima": proxima})
            self._agenda = nova

    # ---------- ciclo de vida ----------
    def iniciar(self):
        self._parar.clear()
        for i in range(self._n_trabalhadores):
            self._threads.append(threading.Thread(target=self._trabalhar, name=f"trabalhador-{i}", daemon=True))
        self._threads.append(threading.Thread(target=self._agendador, name="agendador", daemon=True))
        for t in self._threads:
            t.start()

    def parar(self):
        self._parar.set()
        for t in self._threads:
            t.join(timeout=2)
        self._threads = []

    def esperar(self, timeout=60):
        """Espera a fila esvaziar (útil em testes e na demonstração)."""
        limite = time.time() + timeout
        while self.fila.unfinished_tasks and time.time() < limite:
            time.sleep(0.05)
        return self.fila.unfinished_tasks == 0

    # ---------- aprovação ----------
    def decidir_aprovacao(self, id_item, aprovado, motivo=""):
        item = self.aprovacoes.decidir(id_item, aprovado, motivo)
        if item:
            self.biblioteca.registrar_feedback(item["procedimento"], aprovado, motivo)
            self._evento("aprovacao", f"#{id_item} {item['procedimento']}: {'aprovado' if aprovado else 'rejeitado'}")
        return item

    # ---------- internos ----------
    def _agendador(self):
        while not self._parar.is_set():
            agora = time.time()
            with self._lock_agenda:
                for a in self._agenda:
                    if agora >= a["proxima"]:
                        a["proxima"] = agora + a["cada"]
                        if self.agentes[a["mkt"]].ativo:
                            self.enfileirar(a["mkt"], a["tarefa"], a["params"], a["prio"])
            time.sleep(0.05)

    def _trabalhar(self):
        while not self._parar.is_set():
            try:
                item = self.fila.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._processar(item)
            except Exception as e:  # um erro numa tarefa nunca derruba o sistema
                self.contadores["erros_internos"] += 1
                self.log(f"[erro] {item[2]}.{item[3]}: {e!r}")
            finally:
                self.fila.task_done()

    def _processar(self, item):
        _, _, mkt, tarefa, params = item
        agente = self.agentes[mkt]
        if not agente.ativo:
            self.contadores["ignoradas"] += 1
            return
        res = agente.executar(tarefa, params)
        self.contadores["ok" if res["ok"] else "falha"] += 1
        pedidos = res["ctx"].get("pedidos") or []
        with open(self.arquivo_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "em": time.strftime("%Y-%m-%d %H:%M:%S"), "marketplace": mkt, "procedimento": res["procedimento"],
                "versao": res["versao"], "qual": res["qual"], "ok": res["ok"], "erros": res["erros"],
                "segundos": round(res["segundos"], 3), "resumo": res["ctx"].get("resumo"),
                "pedidos": len(pedidos), "valor": round(sum(p["valor"] for p in pedidos), 2),
            }, ensure_ascii=False) + "\n")
        detalhe = "ok" if res["ok"] else f"falhou em {res['erros'][0]['acao']}"
        self._evento("execucao" if res["ok"] else "falha", f"{res['procedimento']} v{res['versao']}: {detalhe}")
        if res["melhoria"]:
            self.log(f"[aprendizado] {res['procedimento']}: {res['melhoria']}")
            self._evento("aprendizado", f"{res['procedimento']}: {res['melhoria']}")
        if res["ok"] and tarefa in agente.exige_aprovacao:
            itens = res["ctx"].get("rascunhos") or res["ctx"].get("sugestoes") or []
            if itens:
                self.aprovacoes.adicionar(res["procedimento"], res["versao"], itens)
                self._evento("aprovacao", f"{res['procedimento']}: {len(itens)} itens aguardando seu OK")
