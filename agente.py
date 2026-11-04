"""Agente especialista em um marketplace: executa o melhor procedimento conhecido e aprende com o resultado."""
import time

from .conectores import ErroConector


class AgenteMarketplace:
    def __init__(self, nome, conector, biblioteca, melhorador, padroes, exige_aprovacao=()):
        self.nome = nome
        self.conector = conector
        self.biblioteca = biblioteca
        self.melhorador = melhorador
        self.padroes = padroes  # {tarefa: passos iniciais}
        self.exige_aprovacao = set(exige_aprovacao)
        self.ativo = True          # agente pausado não executa nada
        self.estado = "ocioso"     # "ocioso" ou "trabalhando" (usado pelo painel)
        self.ultimo = None         # resumo da última execução (usado pelo painel)

    def executar(self, tarefa, params=None):
        if tarefa not in self.padroes:
            raise ValueError(f"agente '{self.nome}' não conhece a tarefa '{tarefa}'")
        pid = f"{self.nome}.{tarefa}"
        proc = self.biblioteca.criar_se_nao_existe(pid, self.nome, tarefa, self.padroes[tarefa])
        qual, versao = self.biblioteca.escolher_versao(proc)

        ctx, erros, ok = dict(params or {}), [], True
        inicio = time.time()
        self.estado = "trabalhando"
        try:
            for passo in versao["passos"]:
                try:
                    self._rodar_passo(passo, ctx)
                except ErroConector as e:
                    ok = False
                    erros.append({"acao": passo["acao"], "erro": type(e).__name__, "msg": str(e)})
                    break
        finally:
            self.estado = "ocioso"
        segundos = time.time() - inicio

        self.biblioteca.registrar_execucao(pid, qual, versao["versao"], ok, erros, segundos)
        melhoria = self.melhorador.talvez_melhorar(pid)
        self.ultimo = {
            "tarefa": tarefa, "ok": ok, "versao": versao["versao"], "em": time.time(),
            "resumo": ctx.get("resumo") or (f"falhou em {erros[0]['acao']}" if erros else "concluída"),
        }
        return {"procedimento": pid, "versao": versao["versao"], "qual": qual, "ok": ok,
                "erros": erros, "ctx": ctx, "segundos": segundos, "melhoria": melhoria}

    def _rodar_passo(self, passo, ctx):
        acao = passo["acao"]
        params = passo.get("params", {})
        tentativas = passo.get("tentativas", 0)
        for i in range(tentativas + 1):
            try:
                if acao == "pausar":
                    time.sleep(params.get("segundos", 0.05))
                    ctx["resfriado"] = True
                elif acao == "resumir":
                    ctx["resumo"] = self._resumir(ctx)
                else:
                    self.conector.chamar(acao, params, ctx)
                return
            except ErroConector:
                if i == tentativas:
                    raise
                time.sleep(0.02 * (i + 1))

    @staticmethod
    def _resumir(ctx):
        partes = []
        if "pedidos" in ctx:
            total = sum(p["valor"] for p in ctx["pedidos"])
            partes.append(f"{len(ctx['pedidos'])} pedidos, R$ {total:.2f}")
        if "estoque" in ctx:
            baixos = [e for e in ctx["estoque"] if e["qtd"] < 5]
            partes.append(f"{len(baixos)} SKUs com estoque baixo")
        return " | ".join(partes) or "sem dados"
