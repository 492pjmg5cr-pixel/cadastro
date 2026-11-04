"""Painel web local: agentes em 3D, relatórios com gráficos e configuração.

Abre em http://127.0.0.1:8765 e só aceita conexões do próprio computador.
"""
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .memoria import pontuacao

PAGINA = Path(__file__).parent / "web" / "painel.html"


def _nome_passos(passos):
    return [p["acao"] + (f" x{p['tentativas'] + 1}" if p.get("tentativas") else "") for p in passos]


def montar_estado(orq, config):
    procs = {p["id"]: p for p in orq.biblioteca.listar()}
    agentes = []
    for mkt, ag in orq.agentes.items():
        tarefas = []
        for tarefa in ag.padroes:
            p = procs.get(f"{mkt}.{tarefa}")
            tarefas.append({
                "tarefa": tarefa,
                "versao": p["campeao"]["versao"] if p else 1,
                "pontuacao": round(pontuacao(p["campeao"]), 2) if p else None,
                "passos": _nome_passos(p["campeao"]["passos"] if p else ag.padroes[tarefa]),
                "em_teste": bool(p and p["candidato"]),
                "exige_aprovacao": tarefa in ag.exige_aprovacao,
            })
        agentes.append({"id": mkt, "ativo": ag.ativo, "estado": ag.estado, "ultimo": ag.ultimo, "tarefas": tarefas})
    return {
        "agora": time.time(),
        "agentes": agentes,
        "fila": orq.fila.unfinished_tasks,
        "contadores": dict(orq.contadores),
        "aprovacoes": orq.aprovacoes.pendentes(),
        "eventos": list(orq.eventos)[-30:],
        "config": config.dados,
    }


def montar_relatorio(orq):
    registros = []
    if orq.arquivo_log.exists():
        for linha in orq.arquivo_log.read_text(encoding="utf-8").splitlines()[-3000:]:
            try:
                registros.append(json.loads(linha))
            except ValueError:
                continue
    por_mkt = {m: {"ok": 0, "falha": 0, "valor": 0.0, "pedidos": 0} for m in orq.agentes}
    historico = {m: [] for m in orq.agentes}
    for r in registros:
        m = r.get("marketplace") or r["procedimento"].split(".")[0]
        if m not in por_mkt:
            continue
        por_mkt[m]["ok" if r["ok"] else "falha"] += 1
        por_mkt[m]["valor"] = round(por_mkt[m]["valor"] + r.get("valor", 0), 2)
        por_mkt[m]["pedidos"] += r.get("pedidos", 0)
        historico[m].append(1 if r["ok"] else 0)
    # taxa de sucesso em janela móvel de 6 execuções, últimos 60 pontos
    serie = {}
    for m, h in historico.items():
        pts = [round(100 * sum(h[max(0, i - 5): i + 1]) / len(h[max(0, i - 5): i + 1])) for i in range(len(h))]
        serie[m] = pts[-60:]

    procs = orq.biblioteca.listar()
    melhorias, tabela, aprov, rejeit = [], [], 0, 0
    for p in procs:
        aprov += p["feedback"]["aprovados"]
        rejeit += p["feedback"]["rejeitados"]
        for h in p["historico"]:
            if h["versao"] > 1:
                melhorias.append({"procedimento": p["id"], "versao": h["versao"], "motivo": h["motivo"], "em": h["em"]})
        tabela.append({
            "id": p["id"], "versao": p["campeao"]["versao"], "pontuacao": round(pontuacao(p["campeao"]), 2),
            "execucoes": len(p["execucoes_recentes"]), "passos": _nome_passos(p["campeao"]["passos"]),
            "em_teste": bool(p["candidato"]),
        })
    melhorias.sort(key=lambda x: x["em"], reverse=True)
    total = sum(v["ok"] + v["falha"] for v in por_mkt.values())
    oks = sum(v["ok"] for v in por_mkt.values())
    return {
        "kpis": {
            "total": total, "ok": oks, "falhas": total - oks,
            "taxa": round(100 * oks / total) if total else 0,
            "melhorados": sum(1 for t in tabela if t["versao"] > 1), "procedimentos": len(tabela),
            "valor": round(sum(v["valor"] for v in por_mkt.values()), 2),
        },
        "por_marketplace": por_mkt, "serie": serie,
        "feedback": {"aprovados": aprov, "rejeitados": rejeit, "pendentes": len(orq.aprovacoes.pendentes())},
        "melhorias": melhorias[:15], "procedimentos": tabela,
    }


def _criar_handler(orq, config):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _enviar(self, dados, status=200, tipo="application/json; charset=utf-8"):
            corpo = dados if isinstance(dados, bytes) else json.dumps(dados, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def _erro(self, status, msg):
            self._enviar({"erro": msg}, status)

        def do_GET(self):
            rota = self.path.split("?")[0]
            if rota in ("/", "/index.html"):
                self._enviar(PAGINA.read_bytes(), 200, "text/html; charset=utf-8")
            elif rota == "/api/estado":
                self._enviar(montar_estado(orq, config))
            elif rota == "/api/relatorio":
                self._enviar(montar_relatorio(orq))
            else:
                self._erro(404, "não encontrado")

        def do_POST(self):
            if self.headers.get("X-Painel") != "1":
                return self._erro(403, "requisição não autorizada")
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho > 100_000:
                return self._erro(413, "pedido grande demais")
            try:
                dados = json.loads(self.rfile.read(tamanho) or b"{}")
            except ValueError:
                return self._erro(400, "JSON inválido")
            if not isinstance(dados, dict):
                return self._erro(400, "JSON inválido")
            try:
                self._tratar(self.path.split("?")[0], dados)
            except Exception as e:
                self._erro(500, f"erro interno: {e}")

        def _tratar(self, rota, dados):
            if rota == "/api/executar":
                mkt, tarefa = dados.get("marketplace"), dados.get("tarefa")
                ag = orq.agentes.get(mkt)
                if ag is None or tarefa not in ag.padroes:
                    return self._erro(400, "agente ou tarefa desconhecidos")
                if not ag.ativo:
                    return self._erro(409, "o agente está pausado")
                orq.enfileirar(mkt, tarefa, prioridade=1)
                return self._enviar({"ok": True})
            if rota == "/api/simular":
                rodadas = max(1, min(30, int(dados.get("rodadas", 10))))
                for _ in range(rodadas):
                    for mkt, ag in orq.agentes.items():
                        if ag.ativo:
                            for tarefa in ag.padroes:
                                orq.enfileirar(mkt, tarefa)
                return self._enviar({"ok": True, "rodadas": rodadas})
            if rota == "/api/agente":
                mkt = dados.get("marketplace")
                if mkt not in orq.agentes:
                    return self._erro(400, "agente desconhecido")
                novo = json.loads(json.dumps(config.dados))
                novo["agentes"][mkt]["ativo"] = bool(dados.get("ativo"))
                config.atualizar(novo)
                config.aplicar(orq)
                return self._enviar({"ok": True})
            if rota == "/api/aprovar":
                item = orq.decidir_aprovacao(int(dados.get("id", 0)), bool(dados.get("aprovado")),
                                             str(dados.get("motivo", ""))[:200])
                return self._enviar({"ok": bool(item)}) if item else self._erro(404, "item não encontrado")
            if rota == "/api/config":
                config.atualizar(dados.get("config"))
                config.aplicar(orq)
                return self._enviar({"ok": True, "config": config.dados})
            self._erro(404, "não encontrado")

    return Handler


def servir(orq, config, porta=8765, abrir=True):
    try:
        servidor = ThreadingHTTPServer(("127.0.0.1", porta), _criar_handler(orq, config))
    except OSError:
        print(f"A porta {porta} já está em uso. Tente outra: python principal.py painel --porta {porta + 1}")
        return
    url = f"http://127.0.0.1:{porta}"
    print(f"Painel rodando em {url}  (Ctrl+C para parar)")
    if abrir:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nPainel encerrado.")
    finally:
        servidor.server_close()
