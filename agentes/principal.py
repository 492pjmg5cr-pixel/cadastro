#!/usr/bin/env python3
"""Linha de comando do sistema de agentes para marketplaces.

  python principal.py demo                 simula várias rodadas e mostra o aprendizado
  python principal.py rodar                roda em segundo plano com a agenda padrão
  python principal.py status               mostra procedimentos e pontuações
  python principal.py aprovacoes           lista o que espera o seu OK
  python principal.py aprovar 3            aprova o item 3   (rejeitar 3 -m "motivo")
"""
import argparse
import random
import shutil
import time
from pathlib import Path

from agentes.agente import AgenteMarketplace
from agentes.aprovacoes import FilaAprovacao
from agentes.conectores import ConectorSimulado
from agentes.melhorador import Melhorador
from agentes.memoria import BibliotecaProcedimentos
from agentes.orquestrador import Orquestrador
from agentes.sementes import AGENDA_PADRAO, EXIGE_APROVACAO, P_LIMITE, SEMENTES


def montar(pasta, semente=None, trabalhadores=1, log=print):
    pasta = Path(pasta)
    biblioteca = BibliotecaProcedimentos(pasta / "procedimentos")
    aprovacoes = FilaAprovacao(pasta / "aprovacoes.json")
    melhorador = Melhorador(biblioteca)
    agentes = {
        mkt: AgenteMarketplace(
            mkt,
            ConectorSimulado(mkt, P_LIMITE[mkt], semente),  # troque por um conector real aqui
            biblioteca, melhorador, SEMENTES[mkt], EXIGE_APROVACAO.get(mkt, ()),
        )
        for mkt in SEMENTES
    }
    return Orquestrador(agentes, biblioteca, aprovacoes, pasta, trabalhadores, log)


def descrever(passos):
    return " > ".join(p["acao"] + (f"(x{p['tentativas'] + 1})" if p.get("tentativas") else "") for p in passos)


def taxa(execucoes):
    return f"{100 * sum(1 for e in execucoes if e['ok']) / len(execucoes):.0f}%" if execucoes else "-"


def mostrar_status(biblioteca):
    for proc in biblioteca.listar():
        champ, rec = proc["campeao"], proc["execucoes_recentes"]
        print(f"\n{proc['id']}  (v{champ['versao']}, pontuação {(champ['sucessos'] + 1) / (champ['execucoes'] + 2):.2f})")
        print(f"  passos: {descrever(champ['passos'])}")
        if proc["candidato"]:
            print(f"  em teste: v{proc['candidato']['versao']}  {descrever(proc['candidato']['passos'])}")
        if len(rec) >= 8:
            print(f"  sucesso: primeiras 8 execuções {taxa(rec[:8])}  ->  últimas 8 {taxa(rec[-8:])}")
        for h in proc["historico"]:
            print(f"  v{h['versao']}: {h['motivo']}")
        fb = proc["feedback"]
        if fb["aprovados"] or fb["rejeitados"]:
            print(f"  aprovações: {fb['aprovados']} aprovadas, {fb['rejeitados']} rejeitadas")


def cmd_demo(args):
    pasta = Path(args.dados)
    if pasta.exists() and not args.manter:
        shutil.rmtree(pasta)
    orq = montar(pasta, args.semente)
    random.seed(args.semente)
    tarefas = [(m, t) for m, ts in SEMENTES.items() for t in ts]
    print(f"Simulando {args.rodadas} rodadas de {len(tarefas)} tarefas (4 agentes) em segundo plano...\n")
    orq.iniciar()
    for _ in range(args.rodadas):
        for mkt, tarefa in tarefas:
            orq.enfileirar(mkt, tarefa)
        orq.esperar(60)
    orq.parar()
    rng = random.Random(args.semente)
    for item in orq.aprovacoes.pendentes():
        orq.decidir_aprovacao(item["id"], rng.random() < 0.85, "" if rng.random() < 0.5 else "tom formal demais")
    print(f"\nExecuções: {orq.contadores['ok']} com sucesso, {orq.contadores['falha']} com falha")
    mostrar_status(orq.biblioteca)


def cmd_rodar(args):
    orq = montar(args.dados, trabalhadores=args.trabalhadores)
    for cada, mkt, tarefa in AGENDA_PADRAO:
        orq.agendar(cada * args.escala, mkt, tarefa)
    orq.iniciar()
    print("Agentes rodando em segundo plano. Ctrl+C para parar.")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        orq.parar()
        print("\nParado.")


def cmd_status(args):
    mostrar_status(montar(args.dados).biblioteca)


def cmd_aprovacoes(args):
    pend = montar(args.dados).aprovacoes.pendentes()
    if not pend:
        print("Nada esperando aprovação.")
    for i in pend:
        print(f"\n#{i['id']}  {i['procedimento']} (v{i['versao']})")
        for it in i["itens"]:
            print("   ", it)


def cmd_decidir(args, aprovado):
    item = montar(args.dados).decidir_aprovacao(args.id, aprovado, args.motivo or "")
    print(f"Item {args.id}: {item['status']}" if item else f"Item {args.id} não encontrado ou já decidido.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dados", default="dados", help="pasta onde ficam procedimentos e logs")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo")
    d.add_argument("--rodadas", type=int, default=30)
    d.add_argument("--semente", type=int, default=7)
    d.add_argument("--manter", action="store_true", help="não apagar dados anteriores")
    d.set_defaults(f=cmd_demo, dados_padrao="dados_demo")

    r = sub.add_parser("rodar")
    r.add_argument("--escala", type=float, default=1.0, help="multiplica os intervalos (0.01 = 100x mais rápido)")
    r.add_argument("--trabalhadores", type=int, default=1)
    r.set_defaults(f=cmd_rodar)

    sub.add_parser("status").set_defaults(f=cmd_status)
    sub.add_parser("aprovacoes").set_defaults(f=cmd_aprovacoes)
    for nome, valor in (("aprovar", True), ("rejeitar", False)):
        s = sub.add_parser(nome)
        s.add_argument("id", type=int)
        s.add_argument("-m", "--motivo")
        s.set_defaults(f=lambda a, v=valor: cmd_decidir(a, v))

    args = p.parse_args()
    if args.cmd == "demo" and args.dados == "dados":
        args.dados = "dados_demo"
    args.f(args)


if __name__ == "__main__":
    main()
