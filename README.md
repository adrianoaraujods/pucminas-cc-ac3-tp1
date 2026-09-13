# TRABALHO 1 – ETAPA 2: Proposta da Pesquisa e Metodologia Experimental

Objetivo. Transformar a oportunidade identificada na Etapa 1 em uma proposta experimental consistente, dando sequência ao estudo de memória.

A oportunidade de pesquisa definida na Etapa 1 deverá ser mantida nesta etapa, servindo como base para a elaboração da hipótese e da metodologia experimental. Alterações significativas no tema somente poderão ser realizadas mediante justificativa e aprovação do professor.

## Atividades

- Produzir Seção com texto de introdução:
  - Definir claramente a pergunta de pesquisa e a hipótese. Contextualizar o problema; apresentar a motivação; justificar a relevância; e apresentar a hipótese e os objetivos.
  - Justificar a relevância científica da proposta.
- Produzir Seção com Trabalhos Correlatos
  - Comparar criticamente os cinco artigos estudados, e outros se quiserem.
  - Destacar diferenças metodológicas, limitações, vantagens.
  - Relatar como a proposta do grupo se posiciona em relação ao estado da arte desses trabalhos.
- Descrever a metodologia experimental:
  - Escolher um simulador (gem5, Sniper ou equivalente).
  - Definir workloads, parâmetros arquiteturais, métricas e estratégia de análise.
  - Garantir que os experimentos sejam reproduzíveis.
  - Detalhar ambiente experimental; variáveis independentes; variáveis dependentes; forma de análise dos resultados; outras informações que sejam necessárias para clarificar a metodologia definida, cujo resultado será apresentado na última etapa.

> NOTA: A leitura do artigo escolhido na primeira etapa deve ter dado ao grupo uma ideia de como um trabalho científico é escrito. Mas a seguir, algumas dicas são apresentadas.

> ATENÇÃO: Espera-se que, ao final desta etapa, o grupo já tenha iniciado a configuração do simulador escolhido e realizado testes preliminares para validar a viabilidade da metodologia proposta. Não é necessário apresentar resultados consolidados, mas recomenda-se verificar antecipadamente se o ambiente experimental está corretamente configurado.

### Escolha do Simulador
#### gem5

Simulador arquitetural detalhado amplamente utilizado em pesquisa.

Site oficial:
https://www.gem5.orgLinks to an external site.

Documentação:
https://www.gem5.org/documentation/Links to an external site.

Tutorial oficial:
https://www.gem5.org/documentation/learning_gem5/Links to an external site.

Repositório GitHub:
https://github.com/gem5/gem5Links to an external site.

Permite:

- simulação detalhada de caches;
- diferentes modelos de CPU;
- memória virtual;
- modos syscall ou full-system.

#### Sniper Multicore Simulator

Simulador voltado para avaliação rápida de arquiteturas multicore.

Site oficial:
https://snipersim.orgLinks to an external site.

Documentação:
https://snipersim.org/w/The_Sniper_Multi-Core_SimulatorLinks to an external site.

Tutorial inicial:
https://snipersim.org/w/Tutorial

Permite:

estudo de hierarquia de memória multicore;

análise de escalabilidade;

métricas de IPC, stalls e comportamento de memória.

#### Outros simuladores (opcional)

Exemplos aceitáveis:

- ChampSim
- MARSSx86
- ZSim
- simuladores acadêmicos equivalentes

## Entregável

Versão atualizada do artigo contendo, no mínimo: Introdução, Trabalhos Correlatos, Motivação, Hipótese e Metodologia Experimental.

### Estrutura do artigo

Template (obrigatório): Seguir o template LaTeX da SBC de conferências, disponível no Overleaf e no site da SBCLinks to an external site..

Introdução: Contextualização, problema, objetivo e contribuição.

Trabalhos Correlatos: Discussão crítica de trabalhos recentes sobre simulação de memória ou arquitetura.

Metodologia / Arquiteturas Simuladas: Descrição detalhada dos cenários experimentais.

Referências: Apenas os trabalhos citados.

> NOTA: Nesta etapa o artigo ainda não conterá resultados experimentais nem conclusões. Essas seções serão desenvolvidas na Etapa 3.

## Observações

Os experimentos ainda não precisam estar concluídos. Ao final desta etapa, o grupo deverá possuir um planejamento experimental completo.

Complementando as orientações apresentadas na Etapa 1, o uso de ferramentas de IA também é permitido nesta etapa, desde que:

- seja explicitamente declarado no artigo;
- indique onde foi utilizado (texto, código, análise, etc.);
- o grupo compreenda integralmente o conteúdo produzido.
- Os autores permanecem responsáveis pelo trabalho.
- 
## Critérios de avaliação

- qualidade da introdução;
- fundamentação da hipótese;
- consistência metodológica;
- clareza da redação científica;
- reprodutibilidade da metodologia.
