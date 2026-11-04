# IA de automação com agentes para marketplaces

Sistema que roda em segundo plano, com um agente especialista por marketplace
(Shopee, Mercado Livre, Amazon, TikTok Shop). Cada agente guarda os procedimentos
que usa e os melhora a cada execução.

Só usa a biblioteca padrão do Python 3.9+. Nada para instalar.

## Testar agora

```bash
python principal.py demo                # 30 rodadas simuladas, mostra o aprendizado
python principal.py demo --rodadas 60   # mais rodadas
python principal.py rodar --escala 0.001   # modo segundo plano, 1000x mais rápido (teste)
python principal.py rodar               # modo segundo plano com a agenda real
python principal.py status              # procedimentos, versões e pontuações
python principal.py aprovacoes          # o que espera o seu OK
python principal.py aprovar 3           # aprova o item 3
python principal.py rejeitar 3 -m "tom formal demais"
```

Os dados ficam na pasta `dados/` (ou `dados_demo/` na demonstração):
`procedimentos/*.json` (a memória dos agentes), `execucoes.jsonl` (log) e `aprovacoes.json`.

## Como funciona o aprendizado

1. O agente pega o procedimento campeão da tarefa e executa os passos.
2. Cada execução grava sucesso, erros e tempo no arquivo do procedimento.
3. Se a taxa de falha passa de 25% (após 4 execuções), o `Melhorador` propõe uma
   **versão candidata** (ex.: inserir uma pausa antes de uma leitura que estoura o limite
   de requisições, ou aumentar as tentativas).
4. A candidata roda em metade das execuções. Depois de 4 testes, só vira campeã se for melhor;
   senão é descartada e nunca proposta de novo.
5. Rejeições na fila de aprovação ficam anotadas no procedimento (`notas`) para orientar melhorias.

## Arquivos

| Arquivo | Função |
| --- | --- |
| `agentes/memoria.py` | Biblioteca de procedimentos: versões, pontuação, candidata x campeã |
| `agentes/melhorador.py` | Regras que reescrevem procedimentos; gancho opcional para IA (`gancho_llm`) |
| `agentes/agente.py` | Agente de marketplace: executa passos, tenta de novo, registra resultado |
| `agentes/conectores.py` | `ConectorSimulado` (teste) e a base para conectores reais |
| `agentes/orquestrador.py` | Fila de prioridade, agendador e trabalhadores em segundo plano |
| `agentes/aprovacoes.py` | Fila de aprovação humana |
| `agentes/sementes.py` | Procedimentos iniciais e agenda padrão |
| `principal.py` | Linha de comando |

## Próximos passos para uso real

1. **Conector real**: crie uma classe que herde de `Conector` (em `agentes/conectores.py`) e chame a
   **API oficial** do marketplace dentro de `chamar(acao, params, ctx)`; depois troque
   `ConectorSimulado` por ela em `montar()` no `principal.py`. Comece só com leitura (pedidos, perguntas, estoque).
2. **Credenciais**: guarde tokens em variáveis de ambiente ou `.env`, nunca nos arquivos de procedimento.
3. **IA no aprendizado**: implemente `gancho_llm(proc, execucoes)` e passe ao `Melhorador` para que um
   modelo de linguagem sugira novos passos a partir dos erros e das rejeições.
4. **Aprovação humana**: mantenha em `EXIGE_APROVACAO` toda tarefa que responde clientes ou muda preço.
5. **Servidor 24h**: rode `python principal.py rodar` num VPS (por exemplo com `systemd` ou `tmux`).

Atenção: automatizar o painel do vendedor com robôs de navegador pode violar os termos dos marketplaces.
Prefira sempre as APIs oficiais.
