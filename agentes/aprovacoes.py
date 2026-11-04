"""Fila de aprovação: ações que falam com clientes ou mudam preços esperam o seu OK."""
import json
import threading
from pathlib import Path

from .memoria import agora


class FilaAprovacao:
    def __init__(self, arquivo):
        self.arquivo = Path(arquivo)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self.arquivo.exists():
            self._gravar([])

    def _ler(self):
        return json.loads(self.arquivo.read_text(encoding="utf-8"))

    def _gravar(self, itens):
        self.arquivo.write_text(json.dumps(itens, ensure_ascii=False, indent=2), encoding="utf-8")

    def adicionar(self, procedimento, versao, itens):
        with self._lock:
            todos = self._ler()
            novo = {"id": len(todos) + 1, "procedimento": procedimento, "versao": versao,
                    "itens": itens, "status": "pendente", "criado_em": agora(), "motivo": ""}
            todos.append(novo)
            self._gravar(todos)
            return novo["id"]

    def pendentes(self):
        with self._lock:
            return [i for i in self._ler() if i["status"] == "pendente"]

    def decidir(self, id_item, aprovado, motivo=""):
        with self._lock:
            todos = self._ler()
            item = next((i for i in todos if i["id"] == id_item and i["status"] == "pendente"), None)
            if item is None:
                return None
            item["status"] = "aprovado" if aprovado else "rejeitado"
            item["motivo"] = motivo
            self._gravar(todos)
            return item
