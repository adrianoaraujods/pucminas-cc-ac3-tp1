# Uso de IA + Plano Final — Trabalho 1 (Etapa 2)

> Documento de apoio ao artigo para declaração de uso de ferramentas de IA.
> Registra **como a IA foi usada**, as **decisões tomadas em conjunto** e o
> **plano final** da bancada experimental.

## 1. Como a IA foi usada nesta etapa

A ferramenta de IA (assistente de desenvolvimento) foi usada nas seguintes
atividades da etapa:

1. **Condução da decisão de design ("grilling").** Uma sessão de entrevista
   estruturada na qual a IA questionou o grupo sobre a simulação planejada,
   apresentou recomendações e exigiu que cada decisão fosse confirmada ou
   refutada antes de prosseguir. O resultado foi a árvore de decisões da
   Seção 3.
2. **Levantamento de fatos técnicos.** A IA pesquisou em fontes primárias
   (arXiv, repositórios do gem5 e do ChampSim) para verificar:
   - os protocolos de canal encoberto (Algoritmos 1, 2 e 3) do artigo
     *Leaking Information Through Cache LRU States* (Xiong & Szefer);
   - a disponibilidade das políticas de substituição no gem5;
   - a viabilidade de representar o SRRIP canônico a partir da classe
     `BRRIPRP` já existente no gem5 (`btp=100, hit_priority=True`);
   - a compatibilidade de toolchain (Python, SCons) para o build.
3. **Formulação do plano de implementação** (Seção 4), incluindo fases,
   riscos e estratégia de reprodutibilidade.
4. **Produção de texto e código.** A redação da metodologia no artigo e a
   implementação do driver do canal, configurações do gem5, scripts de
   métricas e análise de resultados serão redigidos/verificados com IA,
   sempre sob revisão e responsabilidade integral do grupo.

O grupo compreende e valida todo o conteúdo aqui descrito antes de sua
inclusão no artigo.

## 2. Contexto

O trabalho avalia canais encobertos baseados no **estado de políticas de substituição de cache** (LRU e SRRIP/RRIP). O experimento será conduzido no simulador **gem5** em modo *syscall-emulation* (SE), seguindo e adaptando os protocolos do artigo *Leaking Information Through Cache LRU States in Commercial Processors and Secure Caches* (Xiong et al., IEEE TC 2021).

Esta etapa (Etapa 2) exige, além do texto do artigo: **ambiente do simulador configurado** e **testes preliminares de viabilidade**. Resultados consolidados pertencem à Etapa 3.

## 3. Árvore de decisões (todas discutidas e aprovadas pelo grupo)

| #   | Tema                        | Decisão aprovada                                                                                                                                                      |
| --- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q1  | Escopo desta etapa          | Bancada viável + PoC do canal + metodologia no artigo                                                                                                                 |
| Q2  | Política RRIP               | SRRIP canônico (hit-priority), expresso no gem5 como `BRRIPRP(num_bits=2, btp=100, hit_priority=True)` + alias Python `SRRIPRP`; sem modificação em C++               |
| Q3  | Execução sender/receiver    | PoC com fio único (papéis em sequência); medida realista com SMT na L1 compartilhada (1 core `timing`, `numThreads=2`) — O3 está quebrado no gem5 pinado |
| Q4  | Nível de cache avaliado     | Sanity check no L1; resultado principal na LLC                                                                                                                        |
| Q5  | Toolchain                   | gem5 branch `stable` (commit fixado); Python 3.11 via `mise`; SCons via pip; build X86 SE                                                                             |
| Q6  | Protocolos de canal         | Algoritmos 1 (com memória compartilhada) e 2 (sem memória compartilhada)                                                                                              |
| Q7  | Hierarquia/parâmetros fixos | L1 32 KB, 8-way · L2 256 KB, 8-way · LLC 2 MB, 16-way; clock nominal 2 GHz                                                                                            |
| Q8  | Variáveis da metodologia    | Indep.: política (LRU×SRRIP), nível (L1×LLC), parâmetros do canal (Ts/Tr/d). Dep.: taxa de transmissão (Kbps), taxa de erro (edit-distance), IPC, nº de acessos à LLC |
| Q9  | Repositório                 | Mesmo repo: `article/` (LaTeX) e `sim/` (experimento)                                                                                                                 |
| Q10 | Workloads de desempenho     | Microbenchmark sintético (padrão *scan*, para contraste LRU×SRRIP) + MiBench                                                                                          |
| Q11 | Mitigação                   | Way-partitioning (descrita nesta etapa; implementação/avaliação na Etapa 3); DAWG discutido qualitativamente                                                          |

### Recomendações da IA que foram acatadas
- SRRIP canônico via parametrização do `BRRIPRP` (evita escrever C++)
  **em vez de** usar o BRRIP default (btp=3), cuja inserção aleatória
  não corresponde ao SRRIP citado no artigo e embaralharia a análise do canal.
- Cenário de medida realista no modo hyper-threaded (SMT `timing` com 2
  contextos, L1 compartilhada), preservando comparabilidade com o artigo
  original; o O3 do gem5 25.1 pinado inviabilizou o O3-SMT (segfault
  documentado em `sim/results/README.md`).
- Workload sintético com padrão de varredura para expor a diferença de
  desempenho entre LRU e SRRIP (objetivo original do SRRIP: *scan-resistance*).

### Decisões que permanecem do grupo
- Hipóteses e interpretação dos resultados;
- Escolha dos parâmetros fixos de hierarquia;
- Enquadramento das variáveis independentes/dependentes.

## 4. Plano final de implementação

### Fase 0 — Reorganização do repositório
- Mover os arquivos LaTeX (`main.tex`, `etapa-*.tex`, `*.sty`, `*.bst`,
  `*.bib`) para `article/`.
- Criar `sim/` contendo: `README.md`, `configs/`, `src/`, `scripts/`,
  `results/`.

### Fase 1 — Bootstrap (mise + gem5)
- Instalar Python 3.11 via `mise`; venv em `sim/.venv`; instalar `scons`.
- Clonar gem5 (`stable`) como submódulo de `sim/gem5`, com hash fixado
  (registrado no README de reprodutibilidade).
- Compilar `build/X86/gem5.opt` e executar um smoke test em modo SE.

### Fase 2 — Driver do canal (PoC, fio único, Alg. 1)
- Programa em C que aloca um buffer e escolhe um conjunto-alvo por `stride`
  (linhas de 64 B; mesmo conjunto = mesmo índice).
- Loop de rodadas: Inicialização (linhas 0..d-1) → Codificação (touch na
  linha 0 se bit=1) → Decodificação (linhas d..N + cronometragem da linha 0
  via *pointer chasing* de 7 elementos + `rdtsc`).
- Classificação hit/miss por limiar; comparada com o bit enviado; latências
  gravadas por rodada.

### Fase 3 — Validação no L1 com LRU (sanity check)
- Esperado: erro ~0 e traços de latência bimodais (dois clusteres, rápido e
  lento), análogos à Fig. 4 do artigo de referência.

### Fase 4 — SRRIP canônico
- Definir `SRRIPRP` (alias Python sobre `BRRIPRP` com `btp=100` e
  `hit_priority=True`); conferir o comportamento determinístico
  (hit → RRPV=0).
- Repetir o PoC sob SRRIP no L1 e verificar se o canal ainda transfere
  bits por rodada (hipótese central: o estado RRIP também vaza).

### Fase 5 — Canal na LLC (Algs. 1 e 2) e métricas
- Adaptar o PoC para a LLC (transmissor precisa de *miss* em L1/L2 para
  chegar à LLC; ruído maior, documentar).
- Varrer `Ts`, `Tr`, `d`; métricas: taxa de transmissão
  (bits × 2 GHz ÷ ciclos) e taxa de erro (Wagner-Fischer/edit-distance).
- Saídas em CSV + gráficos de latência por rodada e erro × taxa.

### Fase 6 — Cenário realista (SMT na L1 compartilhada) — CONCLUÍDA com desvio
- **Executado (modelo final)**: o O3 do gem5 25.1 pinado está quebrado
  (segfault `Decode::sortInsts` até com `hello` de fio único), e no CPU
  `timing` a latência de *miss* além da L1 é invisível no caminho
  load-to-use. O cenário realista passou a ser **SMT de verdade**: 1 core
  TimingSimple, `numThreads=2`, mesmas threads do binário (`pthread_create`
  → `clone`) compartilhando a L1, protocolo **Prime+Probe** (Alg. 3 com
  sincronização por flag `volatile g_phase`).
- Resultado: sob **LRU** erro zero (0/64; lat 374 vs 182, limiar 191);
  SRRIP/RRIP **não** colapsam o canal neste cenário de flood cross-thread
  (scan da RRIP incrementa linhas quentes → vazam como LRU; 0/64); BRRIP
  degrada (5/64). `d≈assoc` é condição (d=4/d=16 → 18/64).
- Pendência de escopo (não fazer): O3-SMT continua impedido pela build.

### Fase 7 — Frente de desempenho (Etapa 3; metodologia documentada agora)
- **Executado**: microbenchmark sintético *scan* (`sim/src/scan.c`, loop
  `scripts/perf.sh`): buffer = tamanho da LLC varrido em streaming com hot
  set revisitado; SRRIP reduz MR da LLC (0,32→0,13) e eleva IPC ~21% vs.
  LRU sob o mesmo orçamento de ticks (`runs/perf/perf.tsv`).
- Pendente (Etapa 3): MiBench (binários estáticos X86) como segundo
  workload; gráficos de IPC e miss rate; variar tamanho de B/H.

### Fase 8 — Mitigação por way-partitioning
- Descrever na metodologia: cada domínio confinado a um subconjunto de
  ways por conjunto, isolando também o estado de substituição.
- Implementação e avaliação (banda residual × custo de IPC) na Etapa 3.

### Fase 9 — Redação da Metodologia no `article/main.tex`
- Ambiente experimental, hierarquia, variáveis (Seção 3), métricas,
  estratégia de análise, reprodutibilidade (comandos exatos) e a seção
  "Uso de IA" preenchida com o conteúdo deste documento.

## 5. Riscos e contramedidas

| Risco                                      | Contramedida                                                                     |
| ------------------------------------------ | -------------------------------------------------------------------------------- |
| Python 3.14 do sistema incompatível        | Python 3.11 isolado via `mise`                                                   |
| O3 do gem5 25.1 pinado quebrado (segfault) | Modelo SMT com CPU `timing` (1 core, `numThreads=2`, L1 compartilhada)           |
| TimingSimple não modela latência além do L1| Discriminador restrito ao par hit/miss na L1 compartilhada (Prime+Probe SMT)     |
| SRRIP/RRIP não colapsam sob flood cross-thread | Documentado como achado; colapso RRIP demonstrado só no protocolo de fio único |
| Limitacões do SE multithread (clone/futex) | Protocolo sem mutex (flag `volatile g_phase`); `len(workload)==numThreads`; guard `SmtProcess` |
| Granularidade do `rdtsc` no SE             | Validação cruzada com stats de cache do gem5 por rodada                          |
| Build longo do gem5                        | Compilação paralela (24 núcleos); artefatos fora do git (`.gitignore`)           |

## 6. Reprodutibilidade

`sim/README.md` conterá: hash do submódulo gem5, versões de Python/SCons,
comandos de build e de execução, parâmetros fixos e resultados esperados
(CSVs e gráficos).

## 7. Declaração de uso de IA

Este documento evidencia que o assistente de IA foi empregado em: condução da sessão de entrevista de decisão, levantamento de fatos técnicos, elaboração do plano e futura produção de texto/código. **Todas as decisões técnicas e científicas foram tomadas e aprovadas pelo grupo, que permanece responsável** pelo conteúdo do artigo, pela correção da metodologia e pela validade dos resultados.

> Última atualização: 13/09/2026