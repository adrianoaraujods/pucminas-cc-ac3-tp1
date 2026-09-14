# Resultados preliminares (Etapa 2 - testes de viabilidade)

## Experimento

PoC de fio unico do canal encoberto por estado de cache (Algoritmo 1 de
Xiong & Szefer) rodado no gem5 25.1.0.1 (modo SE, TimingSimpleCPU).
Hierarquia base: L1 32 KiB / 8-way / 64 B, L2 256 KiB / 8-way, LLC 2 MiB /
16-way @ 2 GHz nominal. Conjunto alvo = set 0 (stride 4096 B).

Config: `sim/configs/config_channel.py`
Driver: `sim/src/channel.c`
Loop: `scripts/run_channel.sh`

## Resultados no L1 (64 bits, mensagem deadbeefcafebabe)

| Politica | lat (bit=1) | lat (bit=0) | limiar otimo | edit distance |
|---|------------|------------|--------------|--------------|
| LRU | 88 ciclos | 112 ciclos | 89 | **0 / 64** |
| SRRIP (canonico) | 88 ciclos | 88 ciclos | - | 46 / 64 |
| RRIP (btp=100, sem HP) | 88 ciclos | 88 ciclos | - | 46 / 64 |
| BRRIP (btp=3, FP) | 88 ciclos | 88 ciclos | - | 46 / 64 |

## Leitura preliminar

- Em **LRU**, a latencia da linha compartilhada decodifica o bit com erro
  zero: o estado de irreferencia recente (posicao LRU) vaza a acao do
  transmissor (linha presente sse bit=1). Traco bimodal separavel por limiar.
- Em **todas as variantes RRIP/SRRIP**, as latencias colapsam (88 ciclos para
  ambos os bits): a linha compartilhada permanece residente mesmo sem acao do
  transmissor (os *hits* da fase de init e das linhas helper satura o estado,
  a evicao recai sobre as linhas auxiliares, nao sobre a linha 0). O canal
  deixa de ser separavel com esse protocolo.
- Isso suporta a hipotese do artigo: a **semantica da politica de
  substituicao** determina a ocorrencia/qualidade do canal, nao apenas a
  presenca/ausencia fisica dos dados na cache.

## Observacao metodologica

O protocolo de fio unico usa a posicao de *evicao* do LRU para "apagar" a
linha 0. Em politicas RRIP canonicas (insercao em *long*, hit->RRPV=0) o
mesmo protocolo nao consegue apaga-la.

## Canal de 2 fios (SMT, L1 compartilhada) - F6

### Modelo escolhido

O O3-SMT do gem5 25.1 pinado (`f5c5a6e390f55dd5984977815bf9d0bd05da6945`)
esta quebrado: `se.py --smt --cpu-type=O3CPU` segfaulta em
`Decode::sortInsts` (decode.cc:488) mesmo com um `hello` de fio unico. Com o
CPU `timing`, a latencia de uma **miss a partir da L1 nao e visivel** no
caminho load-to-use (micro-benchmark: load L1/L2/DRAM ~ 10-14 ciclos; chase
sobre conjunto L2: 276 ciclos em residencia, l0 evictado e todas-evictadas
gelam no mesmo valor). Logo, o unico discriminador observavel e o par
**hit/miss na L1 compartilhada**. O experimento simula entao **SMT real**
(1 core, `numThreads=2`, duas threads do mesmo binario, L1 compartilhada e
privada ao core) com o protocolo **Prime+Probe**: o receptor faz o `prime` do
conjunto-alvo na L1; o transmissor (thread via `pthread_create` -> syscall
`clone`) evicta a vitima sse bit=1; o receptor cronometra o anel de
ponteiros.

Config: `--cpu-type timing --num-cores 1 --num-threads 2 --policy <p>
--policy-scope l1 -d 8` (driver `channel_2t.c`, `PRIME_P=6`, tail=8,
warmup=32, mensagem deadbeefcafebabe).

Observacoes de engenharia (SE + pthreads no gem5 25.1):
- `len(cpu.workload) == numThreads` e obrigatorio (fatal em base.cc:186).
  Usa-se o mesmo `Process` nos 2 contextos com o override `SmtProcess`
  (initState C++ executado 1x no contexto 0; o contexto 1 nasce Halted e e o
  `clone`/pthread_create o ativa).
- Binario estatico quebra no SE (panic "unmapped address 0", TLS estatico);
  usar build dinamico.

### Resultados (64 bits)

| Politica (scope L1) | lat (bit=1) | lat (bit=0) | limiar otimo | edit distance |
|---|------------|------------|--------------|--------------|
| LRU | 374 ciclos | 182 ciclos | 191 | **0 / 64** |
| SRRIP (canonico) | 374 ciclos | 182 ciclos | 191 | **0 / 64** |
| RRIP (btp=100, sem HP) | 374 ciclos | 182 ciclos | 191 | **0 / 64** |
| BRRIP (btp=3, FP) | 218 ciclos | 198 ciclos | 183 | 5 / 64 |
| LRU, d=4 (< assoc) | 108 ciclos | 108 ciclos | - | 18 / 64 |
| LRU, d=16 (> assoc) | 708 ciclos | 708 ciclos | - | 18 / 64 |

### Leitura

- Sob **LRU o canal SMT funciona**: erro zero, bimodal (374 vs 182, limiar
  191). Custo end-to-end de 1 bit/rodada ~10,2 us (60 Kbps, com servicos de SE em
  serie; a janela prime+medida em si custa ~400 ciclos). Mesma
  convenção do `metrics.tsv` (tick em ps).
- **d ~= associatividade da L1** e condicao para o canal: d=4 nao evicta a
  vitima (18/64 erros, sem bimodalidade) e d=16 satura a metrica do anel
  (todas as latencias iguais).
- Sob a familia RRIP o colapso **nao** ocorre no cenario de flood cross-thread:
  o scan do RRIP do gem5 incrementa TODAS as linhas do conjunto (inclusive
  quentes) a cada evicao, de modo que o flood de `d` insercoes do transmissor
  passa a evictar a vitima mesmo com RRPV=0: SRRIP e RRIP vazam tanto quanto o
  LRU (0/64); somente o BRRIP (btp baixo, hit_priority=False) degrada o canal
  para 5/64. Ou seja: em **L1 privada / LLC** o RRIP ja
  mostrou conter o canal; sob **SMT/L1 compartilhada** (flood cross-thread),
  a protecao RRPV nao impede a leak nesta implementacao.
- O O3 de qualquer tipo esta inutilizavel nesta build (segfault), o que impede
  o cenario experimental O3-SMT do plano original; o modelo SMT timing e o
  mais fiel ao co-location fisico disponivel.

## Frente de desempenho (Etapa 3) - microbenchmark scan

Carga sintetica `sim/src/scan.c`: buffer `B` do tamanho da LLC (2 MiB)
varrido em streaming (padrao scan; linhas 64 B) entre passadas que revisitam
um hot set `H` de 32 KiB (tamanho da L1). CPU `timing` em modo SE,
`--maxticks 30e9` (~60 M ciclos / ~2,4-2,9 M instrucoes). Loop:
`scripts/perf.sh` (resultados em `runs/perf/perf.tsv`, extraidos do
`stats.txt`: `system.cpu.ipc`, `overallMissRate::total` por nivel).

| Politica (scope) | IPC | MR L1d | MR L2 | MR LLC |
|---|----|----|----|----|
| LRU (l2llc ou all) | 0,0397 | 0,925 | 0,999 | **0,319** |
| SRRIP (l2llc) | 0,0480 | 0,938 | 0,9996 | **0,132** |
| SRRIP (all) | 0,0480 | 0,938 | 0,9995 | **0,132** |

- **SRRIP expoe a scan-resistance que motiva a politica**: o streaming insere
  em "long distance" e nao recicla o hot set nem polui a LLC — miss rate da
  LLC cai de 0,319 (LRU) para 0,132 (SRRIP) e o **IPC sobe ~21%** (0,040 ->
  0,048) sob o mesmo orcamento de ticks.
- A latencia de miss do L1d e alta (~0,93) nos dois casos: esperado, o buffer
  de streaming satura a L1 independentemente da politica; o efeito da politica
  aparece nos niveis mais baixos (L2/LLC), exatamente o escopo do SRRIP.
- Escopo `all` vs `l2llc`: indistinguiveis (a L2 256 KiB nao comporta o B de
  2 MiB; a diferencia entre politicas se manifesta na LLC).

Pendente (Etapa 3): MiBench como segundo workload; graficos de IPC e miss
rate; investimento se a janela de simulação permitir.

## Pendente

(a) redigir Metodologia + "Uso de IA" no `article/main.tex` (F9);
(b) variaveis (d, K, Ts/Tr, taxa) e sorteios de mensagens para taxonomia
    formal.