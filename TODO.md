# TODO operacional

Este arquivo organiza o desenvolvimento em blocos interrompíveis e retomáveis.
Ele registra o estado operacional do projeto. Os requisitos acadêmicos continuam
sendo definidos por `docs/trabalho.md`, e as decisões metodológicas por
`docs/formulation.md` e `docs/experiments.md`.

## Estado de retomada

- **Atualizado em:** 17/08/2026
- **Bloco ativo:** nenhum - aguardando início da B4
- **Fase do bloco ativo:** não iniciada
- **Último bloco concluído:** B3 - Contrato comum dos otimizadores
- **Próxima ação atômica:** iniciar o brainstorming da B4 quando solicitado.
- **Bloqueios conhecidos:** nenhum.
- **Última verificação:** `uv run pytest -q`, com 69 testes aprovados.

> **Aviso:** todos os blocos devem seguir o fluxo obrigatório definido na Seção
> 12.1 de `AGENTS.md`: brainstorming, especificação, aprovação, plano, aprovação
> e somente então implementação. Especificações e planos ficam em
> `superpowers/`, fora do Git.

---

## B0 - Dados e instâncias

**Estado:** `CONCLUÍDO`

**Objetivo:** produzir dados rastreáveis, autocontidos e comuns aos três
algoritmos.

**Entregas concluídas:**

- [x] Aprovar a regra espacial de integração funcional e registrar a limitação.
- [x] Aprovar o coeficiente territorial de sobreposição.
- [x] Registrar a parcela modelada da matriz O-D como limitação.
- [x] Excluir as 11 unidades sem PU·km.
- [x] Selecionar instâncias aninhadas de 20, 60 e 150 unidades.
- [x] Verificar dispersão espacial, demanda e PU·km.
- [x] Criar instância minúscula com ótimo verificável manualmente.
- [x] Exportar atributos e métricas entre pares em Parquet.
- [x] Exportar as quatro instâncias em GeoPackage para o QGIS.
- [x] Registrar seed, proveniência, hashes e critérios no manifesto.
- [x] Testar integridade, aninhamento e reprodutibilidade.

**Artefatos:**

- `data/instances/selection_manifest.json`
- `data/instances/tiny_manual.json`
- `data/instances/artesp_rmsp_{20,60,150}.json`
- `data/instances/artesp_rmsp_150_units.parquet`
- `data/instances/artesp_rmsp_150_pair_metrics.parquet`
- `data/instances/*.gpkg`
- `experiments/generate_instances.py`

**Critério de saída:** satisfeito, com 3 testes aprovados.

---

## B1 - Núcleo do problema

**Estado:** `CONCLUÍDO`

**Depende de:** B0.

**Objetivo:** representar instâncias e soluções e calcular uma única função
objetivo compartilhada por todos os métodos.

**Tarefas:**

- [x] Criar o pacote `src/metaheuristica` e sua interface pública mínima.
- [x] Implementar estruturas tipadas para unidades, métricas entre pares e
  instâncias.
- [x] Carregar `tiny_manual.json`.
- [x] Carregar as instâncias reais filtrando a base de 150 pelos IDs.
- [x] Validar IDs, dimensões, valores finitos e métricas no intervalo `[0, 1]`.
- [x] Implementar canonicalização de rótulos.
- [x] Implementar validação e reparo determinístico de lotes vazios.
- [x] Fixar o desvio padrão populacional para o coeficiente de variação.
- [x] Implementar `C_D`, `C_P`, `C_T` e `C_A` separadamente.
- [x] Implementar o custo total com pesos iguais.
- [x] Implementar contador central de avaliações de fitness.
- [x] Testar invariância por permutação de rótulos.
- [x] Testar manualmente custo zero e ótimo da instância minúscula.
- [x] Testar casos inválidos, lotes vazios e denominadores nulos.
- [x] Atualizar `docs/formulation.md` com decisões surgidas na implementação.

**Arquivos previstos:**

- `src/metaheuristica/__init__.py`
- `src/metaheuristica/problem.py`
- `src/metaheuristica/instances.py`
- `src/metaheuristica/canonical.py`
- `src/metaheuristica/objective.py`
- `tests/test_instances.py`
- `tests/test_canonical.py`
- `tests/test_objective.py`

**Critério de saída:** a instância minúscula e as três reais carregam; a função
objetivo é única, determinística, testada e independente dos algoritmos.

**Checkpoint:**

- implementação concluída conforme a especificação e o plano aprovados;
- especificação aprovada: `superpowers/B1_spec.md`;
- plano aprovado: `superpowers/B1_plan.md`;
- verificação final: 53 testes aprovados e `git diff --check` sem erros;
- próxima ação atômica: iniciar o brainstorming da B2 quando solicitado;
- bloqueio: nenhum.

---

## B2 - Baseline guloso determinístico

**Estado:** `CONCLUÍDO`

**Depende de:** B1.

**Objetivo:** estabelecer uma referência simples e auditável para qualidade e
depuração.

**Tarefas:**

- [x] Ordenar unidades por PU·km decrescente, com desempate determinístico.
- [x] Garantir a abertura inicial dos `K` lotes.
- [x] Alocar pelo menor aumento marginal do custo.
- [x] Aplicar os desempates definidos na formulação.
- [x] Usar o contador central de avaliações.
- [x] Registrar solução, componentes, avaliações e convergência.
- [x] Testar determinismo e viabilidade para todos os valores de `K`.

**Critério de saída:** baseline executável nas quatro instâncias e resultados
repetíveis byte a byte para a mesma entrada.

**Checkpoint:**

- última decisão concluída: ordenar por PU·km decrescente, abrir os `K` lotes
  com as primeiras unidades e avaliar cada alocação seguinte no subproblema
  induzido pelas unidades já processadas, consumindo exatamente `K(N-K)`
  avaliações; ordenar empates de PU·km por `unit_id` e desempatar lotes por
  custo com tolerância de `1e-12`, menor PU·km acumulado e menor rótulo;
  retornar solução canônica, custo decomposto, avaliações, ordem de processamento
  e rastreio das inclusões, deixando tempo e serialização comum para a B3;
- especificação aprovada: `superpowers/B2_spec.md`;
- plano aprovado: `superpowers/B2_plan.md`;
- ajuste aprovado: PU·km de `A` e `C` igual a 200 e de `B` e `D` igual a 100,
  permitindo que a abertura gulosa preserve a possibilidade do ótimo conhecido;
- implementação concluída com orçamento exato `K(N-K)` nos 18 cenários reais;
- verificação final: 69 testes aprovados e `git diff --check` sem erros;
- próxima ação atômica: iniciar o brainstorming da B3 quando solicitado;
- bloqueio: nenhum.

---

## B3 - Contrato comum dos otimizadores

**Estado:** `CONCLUÍDO`

**Depende de:** B1 e B2.

**Objetivo:** impedir diferenças acidentais de orçamento, métricas e formato de
resultado entre PSO, TS e ACO.

**Tarefas:**

- [x] Definir configuração comum de execução.
- [x] Definir resultado comum com seed, custo, componentes e solução.
- [x] Definir histórico nos 100 checkpoints normalizados.
- [x] Implementar parada estrita pelo orçamento de avaliações.
- [x] Separar tempo de carregamento do tempo de otimização.
- [x] Garantir RNG local e explícito por execução.
- [x] Testar serialização e igualdade de resultados reproduzidos.

**Arquivos previstos:**

- `src/metaheuristica/metrics.py`
- `src/metaheuristica/optimizer.py`
- testes correspondentes.

**Critério de saída:** um otimizador de teste usa o contrato sem ultrapassar o
orçamento e produz todos os campos exigidos pelo protocolo.

**Checkpoint:**

- última decisão concluída: separar `RunConfig` imutável, contendo `K`, seed,
  orçamento, pesos, checkpoints e política de cache, das configurações de
  hiperparâmetros específicas de TS, ACO e PSO; fornecer a instância
  separadamente;
- os 100 checkpoints usam os limiares `ceil(j * orçamento / 100)`, registram o
  melhor incumbente imediatamente após cada limiar e contêm índice, avaliações,
  custo total e componentes normalizados, enquanto a solução completa permanece
  apenas no resultado final;
- toda avaliação, inclusive na inicialização, consome orçamento; o otimizador
  interrompe inclusive uma iteração em andamento ao esgotá-lo e retorna o melhor
  incumbente viável;
- o resultado comum registra algoritmo, `K`, seed, orçamento, pesos, solução
  canônica, custo total, componentes normalizados, avaliações consumidas,
  acertos de cache, 100 checkpoints, tempo de otimização, motivo da parada e um
  campo separado para diagnósticos específicos;
- o tempo de otimização usa relógio monotônico e cobre a preparação interna do
  algoritmo até a última avaliação, excluindo carregamento da instância, leitura
  de arquivos e serialização;
- execuções reproduzidas devem coincidir em solução, custos, avaliações e
  checkpoints, mas não em tempo;
- cada execução usa um `numpy.random.Generator` local criado pela infraestrutura
  a partir da seed, sem RNG global ou compartilhado;
- a infraestrutura cria RNG, avaliador e registrador, trata exclusivamente o
  sinal de orçamento esgotado como término normal, valida e canonicaliza o
  incumbente final e não mascara ausência de incumbente ou outros erros;
- o contrato é estrutural, sem herança obrigatória, e será comprovado por um
  otimizador mínimo restrito aos testes;
- brainstorming encerrado e especificação escrita em
  `superpowers/B3_spec.md`;
- especificação aprovada pelo usuário;
- plano de implementação escrito em `superpowers/B3_plan.md`;
- plano aprovado e implementação concluída conforme a especificação;
- verificação final: 99 testes aprovados e `git diff --check` sem erros;
- próxima ação atômica: iniciar o brainstorming da B4 quando solicitado;
- bloqueio: nenhum.

---

## B4 - Busca Tabu

**Estado:** `PENDENTE`

**Depende de:** B3.

**Objetivo:** implementar TS sobre a representação canônica comum.

**Tarefas:**

- [ ] Implementar movimento `move` sem esvaziar lote.
- [ ] Avaliar se `swap` é necessário antes de adicioná-lo.
- [ ] Implementar vizinhança amostrada com RNG explícito.
- [ ] Armazenar atributos de movimento na lista tabu.
- [ ] Implementar aspiração por melhoria do melhor global.
- [ ] Integrar orçamento e checkpoints comuns.
- [ ] Testar validade, tabu, aspiração e reprodutibilidade.

**Critério de saída:** TS respeita exatamente o orçamento, nunca retorna lote
vazio e passa nos testes comuns dos otimizadores.

---

## B5 - ACO

**Estado:** `PENDENTE`

**Depende de:** B3.

**Objetivo:** implementar construção probabilística linha a linha.

**Tarefas:**

- [ ] Definir e testar `tau[i, k]`.
- [ ] Implementar heurística marginal com afinidade e equilíbrio.
- [ ] Implementar probabilidade com `alpha` e `beta`.
- [ ] Garantir lotes ativos por construção ou reparo comum.
- [ ] Implementar evaporação e depósito de feromônio.
- [ ] Integrar orçamento e checkpoints comuns.
- [ ] Testar probabilidades, atualização, validade e reprodutibilidade.

**Critério de saída:** ACO produz soluções válidas, documenta sua heurística e
passa nos testes comuns dos otimizadores.

---

## B6 - PSO com Random Keys

**Estado:** `PENDENTE`

**Depende de:** B3.

**Objetivo:** implementar a adaptação contínua definida no protocolo.

**Tarefas:**

- [ ] Fixar a dimensão e a semântica da posição contínua.
- [ ] Implementar decodificação determinística para `K` lotes.
- [ ] Aplicar reparo comum para lotes vazios.
- [ ] Implementar velocidade, inércia e componentes cognitivo e social.
- [ ] Atualizar `pbest` e `gbest` com desempates determinísticos.
- [ ] Integrar orçamento e checkpoints comuns.
- [ ] Testar decodificação, validade e reprodutibilidade.

**Critério de saída:** PSO respeita a adaptação por Random Keys, produz soluções
válidas e passa nos testes comuns dos otimizadores.

---

## B7 - Validação cruzada dos métodos

**Estado:** `PENDENTE`

**Depende de:** B4, B5 e B6.

**Objetivo:** confirmar comparabilidade antes de qualquer tuning.

**Tarefas:**

- [ ] Executar os três métodos sobre a instância minúscula.
- [ ] Confirmar a mesma função objetivo e decomposição de custos.
- [ ] Confirmar o mesmo orçamento de avaliações.
- [ ] Confirmar formato idêntico de resultados e checkpoints.
- [ ] Testar todas as combinações de tamanho e `K` com orçamento curto.
- [ ] Verificar memória, tempo e ausência de estado global.

**Critério de saída:** nenhum algoritmo possui caminho próprio de cálculo do
custo, e todos passam pelo piloto curto sem violar invariantes.

---

## B8 - Automação experimental

**Estado:** `PENDENTE`

**Depende de:** B7.

**Objetivo:** executar cenários por configuração, com retomada segura e sem
duplicar resultados.

**Tarefas:**

- [ ] Definir arquivos de configuração para tuning, piloto e benchmark.
- [ ] Implementar CLI de execução por algoritmo, instância, `K` e seed.
- [ ] Gerar identificador determinístico de cada execução.
- [ ] Gravar resultados de forma atômica.
- [ ] Detectar e ignorar execuções já concluídas.
- [ ] Registrar falhas sem perder execuções anteriores.
- [ ] Consolidar tabela principal e checkpoints.
- [ ] Documentar comandos no README.

**Critério de saída:** uma execução interrompida pode ser retomada sem repetir
resultados válidos nem corromper arquivos.

---

## B9 - Tuning

**Estado:** `PENDENTE`

**Depende de:** B8.

**Objetivo:** executar as 440 execuções de ajuste previstas e congelar uma
configuração por algoritmo.

**Tarefas:**

- [ ] Executar tuning do PSO.
- [ ] Executar tuning da TS.
- [ ] Executar tuning do ACO.
- [ ] Consolidar qualidade, dispersão e tempo.
- [ ] Escolher parâmetros pelo critério documentado.
- [ ] Registrar configurações congeladas e justificativas.
- [ ] Proibir alteração posterior sem novo ciclo de tuning.

**Critério de saída:** três configurações congeladas, rastreáveis e prontas para
o piloto final.

---

## B10 - Piloto pré-benchmark

**Estado:** `PENDENTE`

**Depende de:** B9.

**Objetivo:** validar a operação completa antes das 1.620 execuções principais.

**Tarefas:**

- [ ] Executar subconjunto representativo de cenários.
- [ ] Verificar orçamento, checkpoints, CPU e memória.
- [ ] Verificar retomada após interrupção simulada.
- [ ] Validar tabelas e gráficos preliminares.
- [ ] Congelar código, instâncias, parâmetros e ambiente do benchmark.

**Critério de saída:** piloto sem erro e congelamento registrado por commit.

---

## B11 - Benchmark principal

**Estado:** `PENDENTE`

**Depende de:** B10.

**Objetivo:** executar os cenários principais em Linux nativo, uma thread por
execução.

**Tarefas:**

- [ ] Registrar ambiente computacional.
- [ ] Executar 3 algoritmos, 3 tamanhos, 6 valores de `K` e 30 seeds.
- [ ] Monitorar completude sem alterar configurações congeladas.
- [ ] Reexecutar somente falhas identificadas pelo ID do cenário.
- [ ] Validar as 1.620 linhas da tabela principal.
- [ ] Preservar resultados brutos e hashes.

**Critério de saída:** todos os cenários válidos e auditáveis, sem duplicatas ou
lacunas.

---

## B12 - Análise e visualização

**Estado:** `PENDENTE`

**Depende de:** B11.

**Objetivo:** transformar resultados brutos em evidências comparativas.

**Tarefas:**

- [ ] Calcular média, dispersão e intervalos por cenário.
- [ ] Comparar qualidade, componentes do custo e tempo de CPU.
- [ ] Analisar sensibilidade aos parâmetros.
- [ ] Analisar escalabilidade de 20 a 150 unidades.
- [ ] Comparar resultados para diferentes valores de `K`.
- [ ] Gerar curvas de convergência nos checkpoints comuns.
- [ ] Executar sensibilidade sem o componente O-D, se houver tempo.
- [ ] Gerar tabelas e figuras reproduzíveis.
- [ ] Separar claramente observação, inferência e limitação.

**Critério de saída:** todas as perguntas da Seção 31 de `docs/experiments.md`
possuem evidência tabular ou gráfica correspondente.

---

## B13 - Relatório, README e empacotamento

**Estado:** `PENDENTE`

**Depende de:** B12.

**Objetivo:** entregar código, método, resultados e instruções coerentes entre
si.

**Tarefas:**

- [ ] Atualizar o estado real e os comandos do README.
- [ ] Documentar formulação, algoritmos e adaptação Random Keys.
- [ ] Documentar dados, limitações e decisões aprovadas.
- [ ] Documentar tuning, protocolo, ambiente e resultados.
- [ ] Produzir comparação crítica entre PSO, TS e ACO.
- [ ] Conferir citações e distinguir fontes de decisões do projeto.
- [ ] Verificar instalação e execução em ambiente limpo.
- [ ] Conferir licença, dados versionados e tamanho do pacote.

**Critério de saída:** uma pessoa externa reproduz o fluxo documentado sem
informação adicional dos autores.

---

## B14 - Vídeo e auditoria final

**Estado:** `PENDENTE`

**Depende de:** B13.

**Objetivo:** concluir os materiais acadêmicos e verificar a entrega.

**Tarefas:**

- [ ] Escrever roteiro do vídeo de até 3 minutos.
- [ ] Selecionar problema, método, resultado e conclusão essenciais.
- [ ] Gravar e revisar o vídeo.
- [ ] Executar todos os testes em ambiente limpo.
- [ ] Reproduzir uma execução curta a partir do README.
- [ ] Conferir arquivos obrigatórios e ausência de dados temporários.
- [ ] Conferir consistência entre relatório, tabelas e resultados brutos.
- [ ] Criar checklist final de entrega.

**Critério de saída:** código, relatório e vídeo prontos para submissão.

---

## Blocos opcionais

Estes blocos não podem atrasar o baseline obrigatório:

- [ ] GPU para algoritmos em que a paralelização seja tecnicamente coerente.
- [ ] Sensibilidade ao raio de 400 m.
- [ ] Sensibilidade sem (O_{ij}).
- [ ] Peso não uniforme dos componentes.
- [ ] Seleção endógena de `K`.
- [ ] Comparação exata adicional na instância minúscula.
