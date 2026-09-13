# sim/ — Ambiente de simulação (gem5)

Bancada experimental do canal encoberto baseado em estado de cache (LRU ×
SRRIP). Repositório do experimento; o artigo fica em `article/`.

## Toolchain fixada (reprodutibilidade)

| Componente | Versão | Notas |
|---|--------|-------|
| gem5 | `v25.1.0.1-13-gf5c5a6e390` (commit `f5c5a6e390f55dd5984977815bf9d0bd05da6945`) | branch `stable`, submódulo git do repo |
| Python | 3.11.16 (via mise) | isolado do Python do sistema (3.14) por compatibilidade |
| SCons | 4.11.1 | instalado no venv `sim/.venv` |
| GCC | 16.2.1 | aviso do gem5: suporte oficial até 14.2 (build OK) |
| Braço | X86 | modo *syscall-emulation* (SE) |

mise: 2026.9.1 linux-x64.

## Estrutura

```
sim/
  gem5/         submódulo gem5 (não editar; commit fixado acima)
  .venv/        venv Python 3.11 (não versionado)
  configs/      scripts de configuração de simulação
  src/          código-fonte dos programas (driver do canal, workloads)
  scripts/      scripts de execução/análise
  results/      saídas (stats, CSVs, gráficos)
```

## Build

```bash
cd sim/gem5
../.venv/bin/scons build/X86/gem5.opt -j 24
```

Binário: `sim/gem5/build/X86/gem5.opt`.

## Smoke test (SE mode)

```bash
sim/gem5/build/X86/gem5.opt \
  sim/gem5/configs/deprecated/example/se.py \
  -c sim/gem5/tests/test-progs/hello/bin/x86/linux/hello
```

Saída esperada: `Hello world!` seguido de `Exiting @ tick 6046000 ...`.

> Nota: `configs/example/se.py` foi deprecado no gem5 25.x — vive em
> `configs/deprecated/example/`. O experimento usará script de configuração
> próprio em `sim/configs/`.