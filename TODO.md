# TODO operacional

Este arquivo organiza o desenvolvimento em blocos interrompíveis e retomáveis.
Ele registra o estado operacional do projeto. Os requisitos acadêmicos continuam
sendo definidos por `docs/trabalho.md`, e as decisões metodológicas por
`docs/formulation.md` e `docs/experiments.md`.

## Estado de retomada

- **Atualizado em:** 02/09/2026
- **Bloco ativo:** B11A-R - renovação da infraestrutura GPU após a B11-E.
- **Último bloco concluído:** B11-E - benchmark principal.
- **Branch de trabalho:** `main`; o fechamento administrativo da B11-E será
  incorporado antes das alterações GPU.
- **O que aconteceu com a primeira tentativa da B11-E.** Ela rodou em 31/08/2026 e
  **não** foi interrompida: o lote 1 concluiu 324 de 324 cenários, com zero falhas, e a
  **barreira reprovou** com `critério de recursos não satisfeito`. O critério contava
  threads que houvessem acumulado ao menos um tique desde o nascimento do processo, e
  uma thread auxiliar do pool cruza esse piso por volta da terceira tarefa de cada
  worker. Era artefato de contagem, não paralelismo. O achado e a correção estão em
  `docs/auditoria.md`, em **F7-11**, que é o resíduo previsto de F7-7 se realizando.
- **O que a B11C entregou.** O critério passou a decidir por `max_optimizer_cpu_ratio`,
  a razão entre o tempo de CPU do processo e o intervalo entre amostras, com tolerância
  de `1,10`; `max_active_optimizer_threads` continua publicada como observação e não
  decide mais; a série ganhou `optimizer_pids` e a exigência de que todo processo
  observado tenha ao menos um intervalo medido. O piloto foi refeito e o congelamento
  renovado, em cinco commits, pelo motivo registrado abaixo.
- **Última decisão concluída:** o lançador aceitará resultados oficiais existentes,
  revalidará e pulará lotes com barreira aprovada e repetirá `finalize` depois das
  cinco barreiras.
- **O que a B11D entregou:** o lançador canônico versionado está em
  `experiments/executa_b11e.sh`; `_temp/executa_b11e.sh` preserva o comando operacional
  como wrapper. A retomada aceita resultados oficiais, revalida e pula lotes com
  barreira, não cria sessão vazia nem pausa em lote pulado e repete `finalize` depois
  das cinco barreiras. Há 14 testes isolados do lançador.
- **B11-E concluída:** cinco barreiras aprovadas, 1.620 execuções oficiais,
  162.000 checkpoints, zero falhas e zero ausências. O manifesto consolidado
  declara `complete: true` e `official: true`, com proveniência no commit de
  execução `959e561`.
- **Última decisão concluída:** brainstorming da B11A-R encerrado com aprovação
  explícita. O bloco renovará a infraestrutura GPU com `social=2.0`, sem executar
  a B11A-E, e exigirá `infrastructure_ready=true`, mas não `execution_ready=true`.
- **Especificação da B11A-R:** `superpowers/B11A_R_spec.md`, aprovada
  explicitamente em 02/09/2026.
- **Plano da B11A-R:** `superpowers/B11A_R_plan.md`, aprovado explicitamente em
  02/09/2026; implementação e commits locais autorizados.
- **Última tarefa concluída:** fechamento administrativo da B11-E no commit
  local `f5f0302`; propagação de `social=2.0`, vínculo da conformidade e
  validação dos 60 pares CPU implementados, com 35 testes focais aprovados.
- **Próxima ação atômica:** executar verificações amplas, estabilizar o commit
  da renovação e regenerar conformidade, roteiro e manifesto em GPU real.
- **Objetivo atual:** renovar a infraestrutura da B11A-E com `social=2.0`,
  regenerar conformidade, roteiro e manifesto e obter
  `infrastructure_ready: true`, sem executar resultados oficiais GPU.
- **Bloqueios conhecidos:** nenhum para o fechamento administrativo da B11-E.
  **A B11A-E mantém o bloqueio operacional, que não é de código:** há um processo
  gráfico de navegador ocupando a placa nesta máquina, e ele precisa estar fechado
  antes de iniciar a campanha da réplica.
- **A transação de fechamento do congelamento deixou de caber em um commit, e quem
  retomar precisa saber disso.** Os dezoito documentos de `results/raw/pilot/` passaram
  a ser versionados na Tarefa 20 da B11B, mas a tolerância de sujeira de
  `generate_freeze_manifest` deriva de `PILOT_ARTIFACTS` mais o roteiro e não os inclui.
  Refazer o piloto exige, na ordem: remover os documentos e commitar, senão a
  reexecução seleciona zero cenários; executar e commitar os documentos, senão
  `consolidate` recusa por árvore suja; consolidar, validar, analisar e commitar os
  artefatos; gerar o manifesto e commitar; regerar o roteiro e gerar o manifesto de
  novo, commitando os dois juntos, porque o roteiro é caminho protegido e commitá-lo
  antes faria a guarda entre o commit do piloto e o HEAD recusar. **Não alargar a
  tolerância para contornar.**
- **Pendências de registro que não bloqueiam nada, e ficam para quem retomar:**
  tornar **incondicional** a exigência de `inherited_thread_limits` na validação do
  piloto, hoje possível porque **os dezoito documentos passaram a ter o campo**; decidir
  se a dependência de `results/raw/` e o defeito de diretório de trabalho da suíte da
  réplica viram **achados novos** no registro; a asserção `diferenca < 1e-15` em
  `gpu/tests/test_numerics.py`, mais estrita que a régua normativa; três dos quatro
  sítios de `COST_TOLERANCE` no ACO sem caso de afrouxamento;
  `gpu/configs/gpu_diagnostic.toml` sem cobertura de carregamento; e dois símbolos
  declarados em vez de removidos, `arbitration_cpu_seconds` e `MemoryLayoutError`.
  **O limiar de `max_active_optimizer_threads` deixou de existir como pendência:** ele
  não decide mais nada, e a medição que o substituiu foi calibrada contra campanha real.
- **Última verificação, no fecho da B11C:** suíte de CPU com **533 aprovados e zero
  reprovados**, contra 517 na partida, e suíte da réplica com **98** aprovados sobre
  dispositivo real, invocada com `uv run --project gpu pytest gpu/tests` a partir da
  raiz. O piloto refeito foi aprovado com reprodução, com razão de consumo de `1,0093`,
  e um subgrupo real do benchmark foi executado como prova, aprovado com `1,0087`. Os
  dezoito documentos do piloto e os seis do subgrupo são idênticos aos anteriores em
  tudo que não é temporal.
- **Consequência já cumprida:** a correção do PSO alterou resultados, e o tuning e o
  piloto oficiais foram refeitos antes da B11-E. O piloto foi refeito uma segunda vez
  na B11C, agora sem alteração de resultado, apenas para alinhar o commit e regravar a
  série de recursos no esquema novo.
- **Última verificação:** no fim do commit do pacote **R3**, impressão digital
  idêntica no **conjunto completo dos 42 cenários**, sem restrição a subconjunto,
  suíte de CPU com **517 aprovados e zero reprovados**, contra 511 aprovados na
  partida, e suíte da réplica com **98** aprovados sobre dispositivo real, nas duas
  invocações, da raiz e de dentro do próprio subprojeto. A contagem sobe pelos seis
  casos novos do pacote. **A linha de base é a que o refazimento do piloto regravou**,
  com `content_sha256` `a6a550e3...`, e a identidade acima é medida contra ela.
- **As duas reprovações previstas cessaram**, como estava anunciado, com o
  refazimento do piloto no commit `8d0322c`: a suíte de CPU foi medida no pacote R2 com
  zero reprovações. O registro abaixo fica como história do período em que elas valiam.
- **A suíte de CPU ficou com duas reprovações previstas, e elas não eram regressão.**
  Desde o commit do pacote B13,
  `tests/test_benchmark_freeze.py::test_revalidation_rejects_altered_objective_function`
  e `tests/test_benchmark_freeze.py::test_revalidation_rejects_verdict_with_foreign_commit`
  reprovam **também na árvore de trabalho**, por `ConfigurationError: resultado
  ausente`: o B13 pôs os dois Parquet no `scenario_id`, o identificador nomeia todo
  arquivo sob `results/raw/` e os dezoito documentos do piloto deixaram de resolver.
  São guardas funcionando sobre artefatos obsoletos, e foram deliberadamente **não
  puladas**, porque pular desligaria as guardas que protegem a assinatura do manifesto
  na Tarefa 20. **As duas cessam com o refazimento do tuning e do piloto, na Tarefa
  19B.** Quem retomar não deve lê-las como regressão, e uma **terceira** reprovação,
  ou reprovação com outro nome, é defeito novo. Limite anterior, que continua valendo
  por outra causa: um clone limpo **não** roda a suíte integral, porque `results/raw/`
  é ignorado e os dezoito documentos do piloto não estão no Git. A decisão sobre
  versioná-los ficou para a Tarefa 20, quando os artefatos já serão os definitivos.
- **Achado fechado, e a linha estava atrasada:** rodando a suíte da réplica com o
  diretório de trabalho em `gpu/`, cinco testes falhavam por caminho relativo
  `data/instances/tiny_manual.json` resolvido contra o `cwd`. **Corrigido em `7d1fd68`**,
  que ancorou os dois arquivos restantes em `Path(__file__).parents[2]`, como os outros
  seis já faziam. A invocação de dentro do subprojeto é verde desde então, e foi medida
  de novo no lote L7, com a mesma contagem da invocação a partir da raiz.
- **Handover detalhado:** `superpowers/B11B_handover.md`, fora do Git, com o
  estado completo e as armadilhas conhecidas.

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

**Estado:** `CONCLUÍDO`

**Depende de:** B3.

**Objetivo:** implementar TS sobre a representação canônica comum.

**Tarefas:**

- [x] Implementar movimento `move` sem esvaziar lote.
- [x] Avaliar se `swap` é necessário antes de adicioná-lo.
- [x] Implementar vizinhança amostrada com RNG explícito.
- [x] Armazenar atributos de movimento na lista tabu.
- [x] Implementar aspiração por melhoria do melhor global.
- [x] Integrar orçamento e checkpoints comuns.
- [x] Testar validade, tabu, aspiração e reprodutibilidade.

**Critério de saída:** TS respeita exatamente o orçamento, nunca retorna lote
vazio e passa nos testes comuns dos otimizadores.

**Checkpoint:**

- brainstorming iniciado após a conclusão e o push da B3 no commit `0893890`;
- a vizinhança inicial usará somente `move(linha, origem, destino)`, sem esvaziar
  o lote de origem;
- `swap` fica fora do baseline porque acrescentaria até `O(N²)` candidatos por
  iteração, consumindo o orçamento de avaliações e reduzindo a quantidade de
  atualizações da trajetória; sua inclusão futura exigirá evidência de
  estagnação relevante;
- a cada iteração serão enumerados os `move` válidos e amostrados uniformemente,
  sem reposição, `min(n_viz, movimentos_válidos)` candidatos; cada candidato é
  avaliado uma vez e vence o melhor admissível;
- `n_viz` permanece hiperparâmetro com a grade prevista `{20, 50}`;
- depois de aceitar `move(i, origem, destino)`, a memória proíbe o retorno
  `move(i, destino, origem)` pelos próximos `L_tabu` movimentos aceitos, com
  grade `{5, 10, 20}`;
- os rótulos permanecem estáveis durante a trajetória e são canonicalizados
  somente para comparação de incumbentes e resultado público;
- a aspiração libera movimento tabu apenas quando o custo melhora estritamente o
  melhor global por mais de `1e-12`; empate não ativa aspiração;
- a solução inicial é gerada por permutação aleatória das unidades e atribuição
  cíclica `r mod K`, garantindo lotes ativos e tamanhos equilibrados; sua
  avaliação é a primeira do orçamento;
- a TS não usa o guloso como inicial porque sua construção faria consultas fora
  do orçamento comum ou consumiria avaliações parciais específicas do baseline;
- `n_stag` conta movimentos aceitos consecutivos sem melhora estrita do melhor
  global, com grade `{50, 100}`;
- ao atingir `n_stag`, ou quando toda a amostra estiver tabu sem aspiração, a TS
  gera e avalia nova solução aleatória balanceada, torna-a corrente, preserva o
  melhor global, limpa a memória tabu e zera a estagnação;
- cada reinício consome uma avaliação e pode atualizar o melhor global;
- todos os movimentos amostrados são avaliados, inclusive os tabu, para permitir
  verificar aspiração; vence o admissível de menor custo e ele é sempre aceito,
  mesmo quando piora a solução corrente;
- empates de custo dentro de `1e-12` são resolvidos pela menor solução resultante
  canonicalizada e depois pela menor tupla `(índice, origem, destino)`;
- memória tabu e estagnação são atualizadas somente depois da aceitação;
- `TabuConfig` é imutável e exige explicitamente `tabu_tenure`,
  `neighborhood_size` e `stagnation_limit`, todos inteiros positivos e sem
  padrões antes do tuning;
- os diagnósticos registram iterações concluídas, movimentos aceitos, reinícios,
  aspirações aceitas, candidatos tabu avaliados e melhorias globais;
- uma iteração termina apenas com movimento aceito ou reinício concluído;
  esgotamento no meio da amostra não aplica movimento nem incrementa iteração;
- os testes cobrirão todas as regras unitárias e todos os tamanhos e valores de
  `K` com orçamento reduzido;
- brainstorming encerrado e especificação escrita em
  `superpowers/B4_spec.md`;
- especificação aprovada pelo usuário;
- plano de implementação escrito em `superpowers/B4_plan.md`;
- plano aprovado e implementação concluída conforme a especificação;
- integração validada nos 18 cenários ARTESP com orçamento reduzido;
- verificação final: 124 testes aprovados e `git diff --check` sem erros;
- próxima ação atômica: iniciar o brainstorming da B5 quando solicitado;
- bloqueio: nenhum.

---

## B5 - ACO

**Estado:** `CONCLUÍDO`

**Depende de:** B3.

**Objetivo:** implementar construção probabilística linha a linha.

**Tarefas:**

- [x] Definir e testar `tau[i, k]`.
- [x] Implementar heurística marginal com afinidade e equilíbrio.
- [x] Implementar probabilidade com `alpha` e `beta`.
- [x] Garantir lotes ativos por construção ou reparo comum.
- [x] Implementar evaporação e depósito de feromônio.
- [x] Integrar orçamento e checkpoints comuns.
- [x] Testar probabilidades, atualização, validade e reprodutibilidade.

**Critério de saída:** ACO produz soluções válidas, documenta sua heurística e
passa nos testes comuns dos otimizadores.

**Checkpoint:**

- brainstorming iniciado após a conclusão e o push da B4 no commit `c4413c1`;
- cada formiga processa as unidades na ordem estável da instância e constrói uma
  sequência de crescimento restrito: a primeira unidade usa lote `0` e cada
  seguinte escolhe lote aberto ou abre somente o próximo rótulo;
- quando as unidades restantes forem exatamente suficientes para abrir os lotes
  faltantes, a abertura passa a ser obrigatória;
- toda solução termina canônica e com exatamente `K` lotes, sem reparo, e cada
  partição possui uma única representação para o feromônio `tau[i, k]`;
- `eta[i, k]` reutiliza o custo parcial dos quatro componentes; entre escolhas
  permitidas, recebe `1 + (C_max - C[i,k])/(C_max - C_min)`, ficando em `[1, 2]`;
- se os custos parciais empatarem dentro de `1e-12`, todas as escolhas recebem
  `eta = 1`;
- cálculos heurísticos parciais não consomem orçamento; somente a solução
  completa de cada formiga usa uma avaliação comum;
- `tau` é matriz densa `N x K` inicializada em `1.0`; probabilidades usam
  `tau^alpha * eta^beta`, calculadas em log;
- após cada geração completa, aplicar evaporação por `(1-rho)` e somar, em cada
  atribuição, depósito `1-custo_total` de todas as formigas;
- geração interrompida não altera o feromônio, mas suas formigas já avaliadas
  permanecem válidas para incumbente e checkpoints;
- `AcoConfig` é imutável, sem padrões antes do tuning, e exige `alpha > 0`,
  `beta > 0`, `0 < rho < 1` e `n_ants` inteiro positivo;
- ficam preservadas as grades `alpha={1,2}`, `beta={1,2}`, `rho={0.1,0.3}` e
  `n_ants={20,40}`;
- todas as formigas de uma geração usam o mesmo `tau`; evaporação e depósitos
  ocorrem uma única vez somente após as `n_ants` avaliações completas;
- o baseline não terá estagnação ou reinício e continuará até o orçamento comum;
- os diagnósticos registram gerações, formigas, atualizações, atribuições
  forçadas e probabilísticas, melhorias globais e extremos finais de `tau`;
- a formiga que esgota o orçamento é contabilizada, mas geração parcial não
  incrementa geração ou atualização de feromônio;
- testes cobrirão construção, heurística, probabilidades, atualização, geração
  parcial, reprodutibilidade e os 18 cenários reais com orçamento reduzido;
- CPU `float64` permanece normativa e GPU fica fora da B5;
- brainstorming encerrado e especificação escrita em
  `superpowers/B5_spec.md`;
- especificação aprovada pelo usuário;
- plano de implementação escrito em `superpowers/B5_plan.md`;
- plano aprovado e implementação concluída conforme a especificação;
- cálculo parcial incremental validado contra a função comum, sem alterar a
  formulação;
- integração validada nos 18 cenários ARTESP com orçamento reduzido;
- verificação final: 157 testes aprovados e `git diff --check` sem erros;
- próxima ação atômica: iniciar o brainstorming da B6 quando solicitado;
- bloqueio: nenhum.

---

## B6 - PSO com Random Keys

**Estado:** `CONCLUÍDO`

**Depende de:** B3.

**Objetivo:** implementar a adaptação contínua definida no protocolo.

**Tarefas:**

- [x] Fixar a dimensão e a semântica da posição contínua.
- [x] Implementar decodificação determinística para `K` lotes.
- [x] Aplicar reparo comum para lotes vazios.
- [x] Implementar velocidade, inércia e componentes cognitivo e social.
- [x] Atualizar `pbest` e `gbest` com desempates determinísticos.
- [x] Integrar orçamento e checkpoints comuns.
- [x] Testar decodificação, validade e reprodutibilidade.

**Critério de saída:** PSO respeita a adaptação por Random Keys, produz soluções
válidas e passa nos testes comuns dos otimizadores.

**Checkpoint:**

- brainstorming iniciado após a conclusão e o push da B5 no commit `ee9026c`;
- cada partícula possui posição de dimensão `N` em `[0,1]`; a coordenada `x[i]`
  representa a unidade `i` e decodifica para
  `min(floor(K*x[i]), K-1)`;
- posições são limitadas a `[0,1]` após atualização e a decodificação é
  determinística;
- lotes vazios usam o reparo comum, com todas as avaliações provisórias
  consumindo o orçamento do PSO;
- a divisão por ranking em `K` partes foi descartada porque imporia lotes quase
  iguais em quantidade de unidades, restrição ausente da formulação;
- cada posição inicial parte de alocação aleatória balanceada e sorteia chaves
  dentro do intervalo do lote correspondente, garantindo viabilidade inicial;
- velocidades começam uniformemente em `[-0.5,0.5]` e permanecem limitadas a
  esse intervalo; posições são limitadas a `[0,1]`;
- a velocidade usa a fórmula clássica com vetores independentes `r1` e `r2` por
  partícula e dimensão;
- cada iteração usa snapshot de `gbest`; avaliações são sequenciais, `pbest` e
  `gbest` atualizam após candidato completo, mas só afetam velocidades na
  iteração seguinte;
- partículas não avaliadas por interrupção não alteram melhores pessoais ou
  global;
- candidato atualizado é decodificado, reparado com avaliações contabilizadas,
  projetado preservando a fração interna de cada chave e só então avaliado como
  solução viável completa;
- a projeção usa `x'=(lote_reparado+u)/K`, onde
  `u=K*x-lote_decodificado`, com ajuste numérico dentro do intervalo;
- candidato interrompido durante reparo ou antes da avaliação final não altera
  posição, velocidade, `pbest` ou `gbest`;
- `PsoConfig` é imutável e sem padrões, com `n_particles` positivo, inércia
  finita em `[0,1]` e coeficientes cognitivo e social positivos;
- preservam-se as grades `{20,40}`, `{0.4,0.7}`, `{1.5,2.0}` e `{1.5,2.0}`;
- a topologia é global e `pbest` e `gbest` comparam custo, solução canônica e
  posição lexicográfica, nessa ordem, sempre armazenando cópias;
- toda a população inicial é avaliada antes da primeira atualização;
- `n_particles` deve caber no orçamento; diagnósticos registram iterações,
  partículas, reparos, avaliações de reparo, melhores e cortes de limites;
- iteração só termina com toda a população avaliada; partículas completas de uma
  iteração interrompida permanecem válidas, sem incrementar a iteração;
- deve valer `particles_evaluated + repair_evaluations = avaliações totais`;
- testes cobrirão Random Keys, dinâmica, reparo, projeção, sincronismo,
  interrupções, reprodutibilidade e os 18 cenários reais;
- CPU `float64` permanece normativa e GPU fica fora da B6;
- brainstorming encerrado e especificação escrita em
  `superpowers/B6_spec.md`;
- especificação aprovada pelo usuário;
- plano de implementação escrito em `superpowers/B6_plan.md`;
- plano aprovado pelo usuário e implementação iniciada;
- núcleo Random Keys, projeção, dinâmica síncrona e diagnósticos implementados;
- integração validada nos 18 cenários ARTESP com orçamento reduzido;
- verificação final: 179 testes aprovados e `git diff --check` sem erros;
- próxima ação atômica: iniciar o brainstorming da B7 quando solicitado;
- bloqueio: nenhum.

---

## B7 - Validação cruzada dos métodos

**Estado:** `CONCLUÍDO`

**Depende de:** B4, B5 e B6.

**Objetivo:** confirmar comparabilidade antes de qualquer tuning.

**Tarefas:**

- [x] Executar os três métodos sobre a instância minúscula.
- [x] Confirmar a mesma função objetivo e decomposição de custos.
- [x] Confirmar o mesmo orçamento de avaliações.
- [x] Confirmar formato idêntico de resultados e checkpoints.
- [x] Testar todas as combinações de tamanho e `K` com orçamento curto.
- [x] Verificar memória, tempo e ausência de estado global.

**Critério de saída:** nenhum algoritmo possui caminho próprio de cálculo do
custo, e todos passam pelo piloto curto sem violar invariantes.

**Checkpoint:**

- brainstorming iniciado após a conclusão e o push da B6 no commit `5b6fd4c`;
- a validação será separada em duas camadas: a instância minúscula verificará
  custo conhecido e decomposição recalculada externamente; as instâncias ARTESP
  verificarão contrato, orçamento, checkpoints, viabilidade, reprodutibilidade
  e escalabilidade curta, sem exigir ótimo conhecido;
- na instância minúscula, cada método será executado com `K=2`, orçamento de
  100 avaliações e seeds diagnósticas `{0,1,2}`; cada algoritmo usará uma
  configuração fixa válida, sem que essa escolha seja tratada como tuning;
- todas essas execuções deverão alcançar o ótimo conhecido de custo zero;
- cada solução minúscula será reavaliada diretamente pela função objetivo comum;
  custo total, quatro componentes e dois coeficientes de variação deverão
  coincidir com tolerâncias absoluta e relativa de `1e-12`;
- a solução deverá ser canônica, viável e ter custo zero, mas algoritmos
  diferentes não precisarão devolver o mesmo vetor quando houver ótimos
  equivalentes ou múltiplos;
- o piloto ARTESP executará os três algoritmos nos 18 cenários formados por
  tamanhos `{20,60,150}` e `K` de 3 a 8, com seed `20260817` e orçamento de 100
  avaliações;
- a reprodutibilidade será verificada repetindo integralmente os cenários
  `(20,3)`, `(60,5)` e `(150,8)` e comparando todos os campos determinísticos,
  com exclusão apenas do tempo;
- as configurações diagnósticas serão TS `(5,20,50)`, ACO
  `(alpha=1.0,beta=1.0,rho=0.1,n_ants=20)` e PSO
  `(n_particles=20,inertia=0.7,cognitive=1.5,social=1.5)`;
- essas configurações não antecipam nem influenciam o tuning da B9;
- um validador comum exigirá orçamento exato, término por orçamento, 100
  checkpoints nos limiares previstos, custos acumulados não crescentes, último
  checkpoint igual ao resultado final, eco correto da configuração, solução
  canônica e viável, serialização JSON e zero acertos de cache quando
  desabilitado;
- diagnósticos específicos continuarão validados separadamente;
- na B7, memória será tratada como isolamento de estado: RNG global inalterado,
  reprodução após execuções intermediárias e imutabilidade de configurações e
  instâncias; o tempo deverá ser finito e não negativo;
- limites quantitativos de RAM ficam para a escalabilidade em ambiente
  controlado, pois limites absolutos seriam dependentes da máquina;
- o experimento de GPU foi organizado como B11A, depois do benchmark CPU e
  antes da análise, sem bloquear o baseline obrigatório;
- a B7 adicionará somente validadores, testes cruzados e documentação; não
  alterará algoritmos, representação nem função objetivo;
- se a validação revelar defeito, a B7 será interrompida para apresentar e
  decidir a correção antes de qualquer mudança no código de produção;
- os testes cruzados ficarão em `tests/test_cross_validation.py`; verificações
  equivalentes serão migradas de `test_core_integration.py` para evitar
  duplicação, enquanto testes específicos continuarão em seus módulos;
- o protocolo será registrado em `docs/experiments.md`, sem persistir tabelas
  experimentais, cuja automação pertence à B8;
- brainstorming encerrado e especificação escrita em
  `superpowers/B7_spec.md`;
- especificação aprovada pelo usuário;
- plano de implementação escrito em `superpowers/B7_plan.md`;
- plano aprovado pelo usuário e implementação executada sem alteração em
  `src/metaheuristica`;
- as nove execuções minúsculas alcançaram custo zero e passaram pela reavaliação
  comum;
- os três métodos passaram nos 18 cenários ARTESP, totalizando 54 execuções;
- reprodutibilidade representativa, isolamento do RNG global, imutabilidade e
  independência da ordem de execução foram validados;
- protocolo registrado em `docs/experiments.md`, sem persistir resultados;
- verificação final: 201 testes aprovados e `git diff --check` sem erros;
- próxima ação: iniciar o brainstorming da B8 quando solicitado;
- bloqueio: nenhum.

---

## B8 - Automação experimental

**Estado:** `CONCLUÍDO`

**Depende de:** B7.

**Objetivo:** executar cenários por configuração, com retomada segura e sem
duplicar resultados.

**Tarefas:**

- [x] Definir configuração piloto e modelos para tuning e benchmark.
- [x] Implementar CLI de execução por algoritmo, instância, `K` e seed.
- [x] Gerar identificador determinístico de cada execução.
- [x] Gravar resultados de forma atômica.
- [x] Detectar e ignorar execuções já concluídas.
- [x] Registrar falhas sem perder execuções anteriores.
- [x] Consolidar tabela principal e checkpoints.
- [x] Documentar comandos no README.

**Critério de saída:** uma execução interrompida pode ser retomada sem repetir
resultados válidos nem corromper arquivos.

**Checkpoint:**

- brainstorming iniciado após a conclusão e o push da B7 no commit `e9daa2b`;
- as configurações serão arquivos TOML declarativos separados por finalidade em
  `experiments/configs/`: tuning, piloto e benchmark;
- a leitura usará `tomllib` do Python 3.14, sem dependência adicional, e a
  automação expandirá instâncias, valores de `K`, seeds, orçamentos, pesos,
  algoritmos e grades em cenários individuais;
- campos desconhecidos, combinações duplicadas e valores inválidos serão
  rejeitados explicitamente;
- cada execução terá SHA-256 de um JSON canônico contendo versão do esquema,
  finalidade, algoritmo, hiperparâmetros, instância e seu hash, `K`, seed,
  orçamento, pesos e política de cache;
- o nome será legível e terminará com os 12 primeiros caracteres do hash, mas o
  resultado armazenará o hash completo; qualquer entrada relevante alterada
  produzirá outro ID;
- cada execução será armazenada em JSON independente sob
  `results/raw/<finalidade>/`, publicado por arquivo temporário no mesmo
  diretório, validação, sincronização e `os.replace`;
- retomadas ignorarão somente JSON válido, completo e com hash esperado;
  arquivos inválidos ou incompatíveis causarão erro sem sobrescrita automática;
- falhas ficarão separadas em `results/failures/<finalidade>/` e nunca serão
  consideradas conclusões;
- uma única CLI oferecerá operações `plan`, `execute` e `consolidate`, além de
  seleção por `--scenario-id` e limite diagnóstico `--max-runs`;
- `execute` será sequencial por padrão e aceitará `--workers N` explícito para
  processos independentes, cada execução individual restrita a uma thread;
- a quantidade de workers nunca será escolhida automaticamente;
- erros de configuração ou expansão impedirão qualquer execução; falhas de um
  cenário serão registradas e os demais continuarão, salvo `--fail-fast`;
- a CLI terminará com código não zero se restarem falhas; novas chamadas
  tentarão novamente cenários falhos e preservarão histórico com exceção,
  mensagem, instante e traceback mesmo após sucesso posterior;
- `Ctrl+C` interromperá de forma limpa, sem registrar como falhos cenários que
  ainda não começaram;
- os JSON individuais serão a fonte primária; `consolidate` gerará em Parquet
  tabelas de execuções e checkpoints, mais manifesto JSON com contagens e hashes;
- a consolidação validará IDs, duplicatas, esquema, ordenação determinística e
  completude, exigindo `--allow-incomplete` para uma saída provisória marcada;
- as três saídas derivadas serão publicadas atomicamente;
- cada resultado registrará commit, estado e hash do worktree, Python, sistema,
  kernel, arquitetura, processador, CPUs, versões das dependências, limites de
  threads e instantes UTC;
- worktree suja será recusada por padrão e exigirá `--allow-dirty`; ausência de
  Git exigirá `--allow-unversioned`, sempre com marcação não oficial;
- TOML e código serão versionados; JSON individuais, falhas e temporários serão
  ignorados; Parquet consolidados, manifestos e figuras finais serão
  versionados;
- as tabelas consolidadas preservarão solução, diagnósticos e proveniência, e o
  manifesto registrará hashes e completude;
- saídas incompletas, sujas ou não versionadas não poderão ser resultados finais;
- brainstorming encerrado e especificação escrita em
  `superpowers/B8_spec.md`;
- especificação aprovada pelo usuário;
- plano de implementação escrito em `superpowers/B8_plan.md`;
- plano aprovado pelo usuário e implementação executada sem alteração em
  `src/metaheuristica`;
- configuração, expansão, IDs, proveniência, persistência, retomada, falhas,
  execução sequencial e paralela, CLI e consolidação implementadas;
- `pilot.toml` é executável; tuning e benchmark permanecem como modelos não
  executáveis até a aprovação das seeds e o congelamento dos parâmetros;
- verificação final: 221 testes aprovados e `git diff --check` sem erros;
- nenhuma campanha real foi executada e nenhum resultado real foi criado;
- próxima ação: iniciar o brainstorming da B9 quando solicitado;
- bloqueio: nenhum.

---

## B9 - Tuning

**Estado:** `CONCLUÍDO`

**Depende de:** B8.

**Objetivo:** executar as 440 execuções de ajuste previstas e congelar uma
configuração por algoritmo.

**Tarefas:**

- [x] Executar tuning do PSO.
- [x] Executar tuning da TS.
- [x] Executar tuning do ACO.
- [x] Consolidar qualidade, dispersão e tempo.
- [x] Escolher parâmetros pelo critério documentado.
- [x] Registrar configurações congeladas e justificativas.
- [x] Proibir alteração posterior sem novo ciclo de tuning.

**Critério de saída:** três configurações congeladas, rastreáveis e prontas para
o piloto final.

**Checkpoint:**

- brainstorming iniciado após a conclusão e o push da B8 no commit `8ef628f`;
- o tuning usará as seeds explícitas `{0,1,2,3,4,5,6,7,8,9}`, igualmente
  para PSO, TS e ACO;
- as 30 seeds do benchmark serão decididas depois e formarão conjunto disjunto
  das seeds usadas no tuning;
- cada algoritmo escolherá por menor média de custo; empate até `1e-12` usará
  menor desvio-padrão amostral (`ddof=1`), depois menor tempo médio com a mesma
  tolerância e, por fim, menor tupla lexicográfica dos hiperparâmetros na ordem
  documentada;
- não será criada faixa subjetiva de resultados praticamente próximos;
- nesta máquina, o padrão aprovado passou a ser 16 workers, um por núcleo
  físico e uma thread por execução; as 32 threads lógicas não serão usadas
  automaticamente;
- o tempo será somente o terceiro desempate; comparações rigorosas de tempo
  ficarão para o benchmark controlado;
- todas as 440 execuções usarão `artesp_rmsp_60`, `K=5`, orçamento 60.000,
  pesos iguais, cache desabilitado e as grades completas aprovadas: 160 PSO,
  120 TS e 160 ACO;
- nenhuma configuração será eliminada antecipadamente;
- infraestrutura e análise serão testadas, commitadas e enviadas antes da
  campanha oficial, que exigirá worktree limpa;
- a seleção exigirá 440 resultados válidos e oficiais; falhas serão retentadas
  com histórico e uma falha persistente após três tentativas será apresentada;
- correção posterior invalidará somente resultados afetados, identificados por
  commit e cenário;
- serão versionados Parquet de execuções e checkpoints, manifesto, resumo por
  configuração, JSON de seleção e `frozen_parameters.toml` referenciado ao
  manifesto oficial;
- o resumo registrará 10 execuções, média, desvio-padrão amostral, mínimo,
  mediana, máximo, tempo médio, ranking e indicador da selecionada;
- o ranking será separado por algoritmo e usará custo total final; não haverá
  substituição manual do vencedor;
- componentes serão resumidos para interpretação, e efeitos marginais por nível
  de hiperparâmetro serão descritivos, sem alegação causal; interações completas
  permanecerão disponíveis;
- resultados surpreendentes serão documentados, não contornados por escolha
  manual;
- brainstorming encerrado e especificação escrita em
  `superpowers/B9_spec.md`;
- especificação aprovada pelo usuário;
- plano de implementação escrito em `superpowers/B9_plan.md`;
- plano aprovado pelo usuário;
- `tuning.toml` implementado com expansão validada em 440 cenários;
- estatísticas, ranking, sensibilidade descritiva e geração dos artefatos
  implementados e testados com dados sintéticos;
- a tentativa inicial com 8 workers foi interrompida após 39 resultados válidos,
  movidos de forma recuperável para `_temp/b9_discarded_workers8` e excluídos da
  campanha oficial;
- o preflight com 16 workers concluiu 18 cenários sem falhas, OOM ou uso
  material de swap;
- a campanha oficial completou 440 execuções, com 440 IDs únicos, zero falhas,
  44.000 checkpoints e proveniência uniforme no commit `dc91468`;
- a consolidação foi marcada como completa e oficial, com hashes verificados;
- os vencedores automáticos foram Busca Tabu `(10, 20, 100)`, ACO
  `(1.0, 2.0, 0.1, 40)` e PSO `(40, 0.4, 2.0, 1.5)`, nas ordens de parâmetros
  documentadas;
- os sete artefatos oficiais foram gerados, inclusive
  `experiments/configs/frozen_parameters.toml`, cuja política exige novo tuning
  para qualquer alteração;
- próxima ação: iniciar o brainstorming interativo da B10 quando solicitado;
- bloqueio: nenhum.

---

## B10 - Piloto pré-benchmark

**Estado:** `CONCLUÍDO`

**Depende de:** B9.

**Objetivo:** validar a operação completa antes das 1.620 execuções principais.

**Tarefas:**

- [x] Executar subconjunto representativo de cenários.
- [x] Verificar orçamento, checkpoints, CPU e memória.
- [x] Verificar retomada após interrupção simulada.
- [x] Validar tabelas e gráficos preliminares.
- [x] Congelar código, instâncias, parâmetros e ambiente do benchmark.

**Critério de saída:** piloto sem erro e congelamento registrado por commit.

**Checkpoint:**

- brainstorming iniciado em 18/08/2026 após a conclusão da B9;
- cobertura aprovada para o piloto oficial: 18 execuções, combinando os três
  algoritmos, as instâncias de 20, 60 e 150 unidades, `K` nos extremos
  `{3, 8}` e uma seed exclusiva do piloto;
- cada tamanho usará seu orçamento oficial de 20.000, 60.000 ou 150.000
  avaliações e os hiperparâmetros congelados na B9;
- o conjunto permite ocupar os 16 workers e observar os extremos de tamanho e
  de quantidade de lotes sem transformar o piloto em campanha extensa;
- o `pilot.toml` existente foi identificado preliminarmente como configuração
  diagnóstica anterior ao tuning, com orçamento de 100 avaliações;
- o `pilot.toml` diagnóstico será preservado como `pilot_diagnostic.toml`, com
  atualização de seus testes e referências documentais; o novo `pilot.toml`
  representará o piloto oficial da B10;
- a seed exclusiva do piloto oficial será `20260818`, aplicada igualmente aos
  18 cenários e reservada fora do tuning e do futuro benchmark principal;
- o piloto será planejado para confirmar 18 IDs e iniciado com 16 workers; após
  ao menos uma conclusão e enquanto houver processos ativos, receberá uma
  interrupção normal por `Ctrl+C`;
- o estado intermediário será auditado para preservar resultados completos,
  rejeitar parciais e não registrar como falhas os cenários interrompidos; a
  mesma campanha será retomada com 16 workers, ignorando somente resultados
  válidos, e consolidada após as 18 conclusões;
- a campanha será monitorada a cada segundo por uma ferramenta Linux leve,
  baseada em `/proc` e sem dependência adicional, registrando CSV bruto e
  resumo JSON com RSS agregado, memória disponível, swap, CPU, processos e
  threads;
- o tempo oficial continuará sendo `optimization_time`; o monitor será somente
  diagnóstico;
- os critérios de recursos serão ausência de OOM, swap causado pela campanha e
  crescimento persistente de memória, uma thread por execução, uso agregado
  compatível com até 16 workers e memória disponível sempre igual ou superior
  ao maior valor entre 10% da RAM total e 2 GiB;
- se os critérios falharem, a quantidade de workers será reduzida e o piloto
  repetido antes do congelamento;
- a B10 produzirá uma tabela das 18 execuções, figura de convergência em seis
  painéis, figura de tempo, figura diagnóstica de recursos e resumo JSON dos
  critérios de aceitação, todos explicitamente preliminares;
- a análise preliminar não fará inferências sobre média, variabilidade ou
  significância com uma única seed;
- `matplotlib` será adicionado como dependência direta para as figuras da B10 e
  da futura B12;
- a reprodução exata repetirá, em saída temporária isolada, TS com `(20,3)`,
  ACO com `(60,8)` e PSO com `(150,3)`, sempre com orçamento completo;
- solução, custos, avaliações, checkpoints, diagnósticos e motivo de parada
  deverão ser exatamente iguais; somente tempo, timestamps e campos derivados
  do momento da execução serão excluídos;
- as três repetições não integrarão os 18 resultados oficiais, mas seu resumo
  será preservado na validação da B10;
- o benchmark principal usará as 30 seeds inteiras de `10` a `39`, aplicadas
  igualmente a todos os algoritmos, tamanhos e valores de `K`;
- esse conjunto é disjunto das seeds do tuning, da validação diagnóstica e do
  piloto oficial e não foi escolhido em função de desempenho;
- um manifesto versionado de congelamento registrará hashes SHA-256 do código,
  automação, instâncias, configurações, parâmetros congelados, `pyproject.toml`
  e `uv.lock`, além do esquema, commit limpo do piloto e ambiente;
- a automação da B11 recusará divergência em qualquer item protegido; mudanças
  somente documentais não invalidarão o congelamento;
- a implementação, configurações e testes serão commitados antes do piloto; os
  artefatos aprovados e o manifesto serão commitados ao concluir a B10, e
  qualquer alteração posterior em item protegido exigirá novo piloto;
- `pilot.toml` e `benchmark.toml` declararão explicitamente uma única
  configuração por algoritmo e serão validados por igualdade exata contra
  `frozen_parameters.toml` antes da expansão ou execução;
- resultados registrarão o hash dos parâmetros congelados, e qualquer
  algoritmo ausente, valor divergente ou grade com múltiplas opções será erro;
- `benchmark.template.toml` será substituído pelo `benchmark.toml` executável,
  com as seeds de `10` a `39` e expansão exata para 1.620 cenários;
- serão versionados os Parquet e manifesto consolidados do piloto, amostras e
  resumo de recursos, validação JSON, tabela CSV, figuras PNG e PDF e manifesto
  de congelamento;
- permanecerão ignorados os JSON individuais, temporários, resíduos da
  interrupção, repetições isoladas e logs completos; o resultado da auditoria
  de reprodução ficará no JSON de validação;
- a B10 somente será aprovada com 18 execuções válidas, retomada correta, três
  reproduções exatas, critérios de recursos satisfeitos, consolidação completa,
  figuras geradas e manifesto de congelamento validado;
- falhas funcionais ou de reprodutibilidade exigirão correção e repetição dos
  resultados afetados; falha apenas de recursos exigirá reduzir workers e
  repetir o piloto; diferenças de qualidade não autorizam retuning;
- brainstorming encerrado e especificação escrita em
  `superpowers/B10_spec.md`;
- especificação aprovada explicitamente pelo usuário;
- plano de implementação escrito em `superpowers/B10_plan.md`;
- plano aprovado explicitamente pelo usuário e implementação autorizada;
- configurações oficiais, parâmetros congelados, auditoria de interrupção,
  monitor de recursos, validação, reprodução, figuras e barreira de
  congelamento implementados;
- o piloto expande 18 IDs, o benchmark 1.620 e o diagnóstico preservado 54;
- preflight diagnóstico com dois workers confirmou ausência de swap, margem de
  memória, cerca de dois núcleos usados e uma thread computacional ativa por
  otimizador; threads auxiliares ociosas são registradas separadamente;
- interrupção diagnóstica por `Ctrl+C` terminou com código 130, sem falhas,
  temporários ou processos órfãos, e preservou os resultados anteriores;
- verificação da implementação: 239 testes aprovados em 108,86 s e
  `git diff --check` sem erros;
- infraestrutura commitada antes do piloto em `5a9b805`, com worktree limpa;
- a interrupção oficial preservou 8 resultados completos, deixou 10 pendentes,
  zero falhas, zero temporários e nenhum processo órfão; a retomada executou os
  10 pendentes e ignorou os 8 válidos;
- as 18 execuções oficiais e os 1.800 checkpoints foram consolidados com
  proveniência uniforme no commit `5a9b805`;
- o pico agregado foi 2,34 GiB de RSS e 1.635% de CPU, a menor memória
  disponível foi 35,0 GiB, o swap permaneceu zerado e cada otimizador teve no
  máximo uma thread computacional ativa;
- as reproduções de TS `(20,3)`, ACO `(60,8)` e PSO `(150,3)` coincidiram em
  todos os campos determinísticos;
- tabela e figuras preliminares foram geradas em CSV, PNG e PDF e inspecionadas
  visualmente; ajustes posteriores afetaram somente apresentação e não os
  resultados experimentais;
- o ACO foi o principal custo temporal do piloto: 6.389,35 s em `(150,3)` e
  10.971,45 s em `(150,8)`, fato a considerar no planejamento operacional da
  B11, sem alterar o protocolo congelado;
- `benchmark_freeze_manifest.json` foi gerado e verificado com 16 workers,
  protegendo código, automação, instâncias, configurações, dependências,
  ambiente e artefatos do piloto;
- B10 concluída; próxima ação: iniciar o brainstorming da B11 quando solicitado.

---

## B11 - Benchmark principal

**Estado:** `B11-I CONCLUÍDA - B11-E CONCLUÍDA`

**Depende de:** B10.

**Objetivo geral:** preparar e executar os cenários principais em Linux nativo,
uma thread por execução.

### B11-I - Infraestrutura

**Estado:** `CONCLUÍDA`

**Objetivo:** deixar toda a campanha CPU criada, revisada, testada e pronta para
execução, sem disparar os 1.620 cenários oficiais.

**Critério de saída:** quando o usuário decidir iniciar a B11-E, nada precisará
ser criado ou revisado; bastará executar os comandos documentados e acompanhar
as barreiras já testadas.

### B11-E - Execução

**Estado:** `CONCLUÍDA`

**Depende de:** B11-I e autorização explícita do usuário em momento com carga e
temperatura adequadas.

**Tarefas:**

- [x] Concluir e validar toda a infraestrutura da B11-I.
- [x] Registrar o ambiente computacional no início da B11-E.
- [x] Executar 3 algoritmos, 3 tamanhos, 6 valores de `K` e 30 seeds.
- [x] Monitorar completude sem alterar configurações congeladas.
- [x] Reexecutar somente falhas identificadas pelo ID do cenário.
- [x] Validar as 1.620 linhas da tabela principal.
- [x] Preservar resultados brutos e hashes.

**Critério de saída:** todos os cenários válidos e auditáveis, sem duplicatas ou
lacunas.

**Checkpoint de retomada:**

- brainstorming iniciado em 18/08/2026, após o envio da B10 ao remoto no
  commit `b83ea43`;
- permanecem congelados os 1.620 cenários, as seeds de 10 a 39, os parâmetros,
  os orçamentos, os 16 workers e os IDs definidos por conteúdo;
- primeira decisão concluída: particionamento operacional da campanha, sem
  modificar o protocolo experimental nem a identidade dos cenários;
- particionamento aprovado: cinco lotes de 324 execuções, cada um contendo
  todas as combinações de algoritmo, tamanho e `K`, para as seeds `10-15`,
  `16-21`, `22-27`, `28-33` e `34-39`;
- os lotes são apenas unidades operacionais de execução, auditoria e retomada;
  não alteram IDs, resultados, parâmetros ou análise estatística;
- segunda decisão concluída: ordem de submissão dos cenários dentro de cada
  lote;
- ordenação aprovada: prioridade determinística por duração estimada a partir
  do piloto, da maior para a menor, com desempate estável pelo ID do cenário;
- a prioridade é exclusivamente operacional e não depende de resultados
  parciais nem altera qualquer elemento congelado;
- terceira decisão concluída: política de validação e liberação entre lotes;
- barreira aprovada: o lote seguinte somente será liberado após validação
  automática dos 324 resultados únicos, ausência de falhas, lacunas e
  temporários, compatibilidade com o congelamento e consolidação incremental
  reproduzível;
- falhas serão tratadas exclusivamente pelos IDs afetados antes da liberação
  do lote seguinte, sem necessidade de aprovação manual quando a barreira for
  satisfeita;
- quarta decisão concluída: limite e comportamento das novas tentativas;
- política aprovada: uma única nova tentativa automática por ID após o término
  da execução inicial do lote;
- uma segunda falha do mesmo ID interrompe a campanha antes do lote seguinte e
  preserva artefatos e logs para diagnóstico;
- interrupções externas não contam como falha: na retomada, resultados válidos
  são ignorados e somente IDs incompletos retornam à fila;
- conjunto de decisões do brainstorming pronto para aprovação de encerramento.
- brainstorming encerrado com aprovação explícita do usuário;
- especificação escrita em `superpowers/B11A_I_spec.md` e aguardando aprovação;
- implementação e execução oficial ainda não autorizadas.
- especificação aprovada explicitamente pelo usuário; pedido de implementação
  não substitui a aprovação obrigatória do plano ainda inexistente;
- plano de implementação em elaboração.
- plano escrito em `superpowers/B11A_I_plan.md` e aguardando aprovação
  explícita; implementação ainda não autorizada.
- plano aprovado explicitamente e implementação autorizada pelo usuário em
  18/08/2026; a B11A-E permanece sem autorização.
- divisão aprovada: a B11-I entrega somente a infraestrutura integralmente
  pronta; a B11-E executa posteriormente a campanha oficial;
- prontidão da B11-I significa que o início da B11-E não exigirá criação ou
  revisão de código, configuração, testes, validações ou instruções;
- a B11-E será autorizada separadamente pelo usuário, considerando carga e
  temperatura do computador.
- granularidade aprovada para a B11-E: cada lote de 324 poderá ser executado em
  54 subgrupos de seis IDs, definidos por algoritmo, instância, `K` e pelas
  seis seeds do lote;
- cada subgrupo poderá ser executado e retomado separadamente para permitir
  controle de carga e temperatura, mas a barreira continuará pertencendo ao
  lote completo;
- a especificação revisada da B11-I está pronta para aprovação formal.
- especificação da B11-I aprovada explicitamente pelo usuário em 18/08/2026;
- plano de implementação em elaboração; implementação ainda não autorizada.
- plano escrito em `superpowers/B11_plan.md` e aguardando aprovação explícita;
- a renovação controlada do manifesto ao final da B11-I registrará a nova
  automação, preservando código científico, configuração, instâncias,
  parâmetros, IDs e artefatos do piloto.
- plano aprovado explicitamente pelo usuário e implementação autorizada em
  18/08/2026;
- nenhuma execução oficial da B11-E foi autorizada.
- B11-I implementada com cinco lotes, 270 subgrupos, prioridade derivada do
  piloto, diário operacional, retomada, tentativa única, monitoramento,
  barreiras, consolidação isolada, CLI e preflight;
- roteiro determinístico protegido em
  `results/tables/benchmark_execution_schedule.json`;
- ensaios reduzidos usaram somente diretórios temporários e
  `results/raw/benchmark` permaneceu ausente;
- 254 testes coletados, suíte completa aprovada e `git diff --check` sem erros;
- manifesto de congelamento renovado com 16 workers e sem mudança nos 1.620
  IDs, configurações, instâncias, hiperparâmetros ou artefatos do piloto;
- comandos definitivos documentados; a B11-E não exige criação ou revisão
  adicional e aguarda a conclusão da B11B e, depois dela, a autorização do
  usuário.
- execução concluída em 02/09/2026 sobre o commit `959e561`, com os cinco lotes
  aprovados nas barreiras;
- consolidação oficial com 1.620 execuções, 162.000 checkpoints, zero falhas,
  zero ausências e hashes verificados;
- próxima ação: fechar administrativamente os artefatos em commit próprio e
  renovar a infraestrutura GPU na B11A-R.

---

## B11A - Experimento adicional com GPU

**Estado:** `B11A-I CONCLUÍDA - B11A-R ATIVA - B11A-E NÃO AUTORIZADA`

**Dependências internas:** a B11A-I poderá começar depois da conclusão da
B11-I; a B11A-E somente poderá começar depois da conclusão da B11-E e de
autorização explícita do usuário.

**Critério de prontidão da B11A-I:** quando o usuário decidir iniciar a B11A-E,
nada precisará ser criado ou revisado; toda a infraestrutura GPU estará testada
e pronta para executar.

**Objetivo:** avaliar se uma implementação em GPU produz aceleração relevante
sem alterar o baseline normativo em CPU.

**Tarefas:**

- [x] Selecionar os algoritmos e operações tecnicamente adequados à GPU.
- [x] Manter o caminho CPU com NumPy e `float64` como referência normativa.
- [x] Implementar o caminho GPU separadamente, sem alterar resultados já
  congelados.
- [x] Definir e testar equivalência numérica, de orçamento e de convergência.
- [x] Registrar GPU, CPU, software, precisão numérica e ambiente de execução.
- [x] Medir tempo total, tempo computacional relevante e custos de transferência.
- [x] Preparar cálculo pareado de speedup por cenário.
- [x] Documentar divergências, limitações e casos em que a GPU não compensa.

**Critério de saída:** comparação CPU e GPU auditável, ou limitação explícita
registrada caso o experimento adicional não possa ser executado. A
indisponibilidade de GPU não invalida nem bloqueia o baseline obrigatório.

**Checkpoint de retomada:**

- B11A-I iniciada em 18/08/2026 após a conclusão e o push da B11-I no commit
  `a6857d0`;
- a B11-E permanece pronta, congelada e sem resultados oficiais;
- primeira decisão pendente: algoritmos incluídos na infraestrutura GPU.
- escopo aprovado: preparar caminhos GPU adicionais para ACO e PSO; manter a
  Busca Tabu exclusivamente no baseline CPU nesta etapa;
- TS foi deferida porque sua trajetória depende sequencialmente do incumbente e
  da atualização após cada movimento, enquanto a vizinhança já é amostrada;
  não há paralelismo independente demonstrado que justifique agora o custo de
  transferência, sincronização, nova dependência e validação numérica;
- o deferimento não afirma impossibilidade de aceleração: uma futura TS em GPU
  exigirá experimento próprio de avaliação paralela de vizinhança, caso o
  profiling posterior identifique esse cálculo como gargalo relevante;
- decisão atual: backend GPU de ACO e PSO.
- backend aprovado: CuPy 14 para NVIDIA CUDA, instalado em ambiente GPU
  separado do ambiente CPU normativo da B11-E;
- a escolha é compatível com Python 3.14 e com a RTX 3060 de 12 GB, compute
  capability 8.6; nenhuma dependência GPU está atualmente instalada;
- o ambiente isolado deverá ter lock, verificação de driver/runtime e
  proveniência próprios, sem alterar o lock ou o congelamento da B11-E;
- decisão atual: fronteira entre operações CPU e GPU.
- fronteira aprovada: CuPy calculará somente a função objetivo em lotes de
  candidatos; RNG `PCG64`, construção, reparo, estado e transições de ACO e PSO
  permanecerão na CPU;
- ACO agrupará avaliações das formigas de uma geração e PSO, das partículas de
  uma iteração, preservando ordem individual de consumo do orçamento;
- a solução final será reavaliada pela função CPU normativa e transferências
  CPU-GPU integrarão o tempo da variante GPU;
- decisão atual: contrato de equivalência numérica e desempate.
- contrato aprovado: GPU em `float64`, com `abs_tol=1e-12` e
  `rel_tol=1e-12` para custo total e componentes;
- orçamento, ordem, checkpoints, viabilidade e canonicalização deverão
  coincidir exatamente; candidatos quase empatados terão arbitragem CPU sem
  consumir nova avaliação lógica;
- solução final e casos determinísticos de conformidade deverão coincidir
  exatamente; divergência fora da tolerância bloqueará a B11A-E sem fallback
  silencioso;
- decisão atual: cobertura experimental e referência temporal CPU.
- cobertura aprovada: ACO e PSO em `N=150`, `K=5`, seeds de 10 a 39 e orçamento
  150.000, totalizando 60 execuções GPU sem concorrência na mesma placa;
- o speedup fim a fim usará os tempos CPU oficiais correspondentes da B11-E,
  sem repetir 60 execuções CPU completas;
- a B11A-I também preparará microbenchmark diagnóstico da avaliação em lote
  para separar kernel, transferências e custo total, sem substituir o speedup
  principal;
- decisão atual: contrato de medição temporal GPU.
- medição aprovada: aquecimento fixo fora do tempo oficial, contexto e
  compilação inicial registrados separadamente e sincronização antes e depois
  da otimização;
- o tempo oficial GPU incluirá transferências, arbitragem CPU e sincronizações
  recorrentes; kernels, transferências, arbitragem e tempo frio também serão
  registrados separadamente para diagnóstico;
- o speedup principal será `runtime_seconds` oficial da B11-E dividido pelo
  tempo oficial GPU correspondente;
- decisão atual: política térmica e de exclusividade da GPU.
- política aprovada: autorização explícita, uma execução GPU por vez, preflight
  ocioso de 60 s, início com até 50 °C e utilização média de até 5%;
- monitorar a cada segundo temperatura, utilização, memória, potência, clocks
  e throttling; interromper com 80 °C por 10 s, throttling térmico ou outro
  processo computacional na GPU;
- exigir cooldown até 50 °C, o mesmo limiar do preflight; interrupção térmica
  não conta como falha e os logs ficam vinculados ao ID;
- resolução sem instalação confirmou `cupy-cuda12x 14.1.1` com runtime CUDA
  12.9 e compatibilidade de dependências com o NumPy 2.5.2 atual;
- decisão atual: empacotamento e lock do ambiente GPU.
- ambiente aprovado: subprojeto isolado `gpu/`, Python 3.14, dependência local
  do projeto, versões compartilhadas alinhadas, `cupy-cuda12x[ctk]` série 14,
  runtime CUDA 12 e `gpu/uv.lock` próprio;
- comandos usarão `uv run --project gpu` e registrarão driver, runtime, CuPy,
  NumPy, GPU e compute capability; `pyproject.toml`, `uv.lock` e ambiente da
  B11-E não serão alterados;
- conjunto de decisões do brainstorming pronto para aprovação de encerramento.
- brainstorming, especificação e plano aprovados explicitamente;
- implementação autorizada em 18/08/2026; B11A-E não autorizada;
- ambiente CuPy/CUDA 12 isolado, avaliação em lote, ACO e PSO híbridos,
  orçamento, conformidade, telemetria, persistência e CLI implementados;
- suíte GPU integral aprovada com 262 testes antes das verificações finais;
- próxima ação atômica: executar conformidade diagnóstica, congelar o manifesto
  GPU e verificar a prontidão final em worktree limpa.
- preflight real aprovado com 60 amostras, máximo de 38 °C e utilização média
  de 0%; conformidade diagnóstica aprovada nas instâncias de 20, 60 e 150
  unidades e em execuções reduzidas de ACO e PSO;
- suíte CPU aprovada com 254 testes e suíte GPU aprovada com 17 testes;
- manifesto e roteiro determinísticos gerados para exatamente 60 IDs, sem
  resultados oficiais CPU ou GPU;
- B11A-I concluída; próxima ação atômica é executar B11-E somente após nova
  autorização explícita do usuário. A B11A-E permanece bloqueada até a
  conclusão da B11-E e sua própria autorização explícita.

### B11A-R - Renovação após a B11-E

**Estado:** `EM IMPLEMENTAÇÃO`

**Escopo aprovado:** propagar `social=2.0`, invalidar os IDs GPU antigos,
regenerar conformidade, roteiro e manifesto e obter
`infrastructure_ready=true`, sem executar a B11A-E.

**Checkpoint:**

- brainstorming encerrado e aprovado em 02/09/2026;
- especificação `superpowers/B11A_R_spec.md` aprovada;
- plano `superpowers/B11A_R_plan.md` aprovado e implementação autorizada;
- B11-E fechada administrativamente no commit local `f5f0302`;
- configurações oficial e diagnóstica atualizadas para `social=2.0`;
- prontidão passa a validar manifesto, hash e exatamente 60 pares CPU oficiais;
- conformidade passa a carregar a identidade da configuração e dos IDs;
- nenhuma execução oficial GPU autorizada ou produzida.

---

## B11B - Auditoria técnica pré-execução

**Estado:** `EM ANDAMENTO`

**Depende de:** B11A-I.

**Objetivo:** submeter as premissas e o código-fonte do projeto a uma auditoria
técnica completa antes de iniciar as 1.620 execuções oficiais da B11-E e, na
sequência, as 60 execuções GPU da B11A-E, confrontando o que foi construído com
o que estava planejado.

**Tarefas:**

- [ ] F1 - Mecanismo geral.
- [ ] F2 - Testes.
- [ ] F3 - PSO.
- [ ] F4 - ACO.
- [ ] F5 - Busca Tabu.
- [ ] F6 - Benchmark.
- [ ] F7 - CPU.
- [ ] F8 - GPU.
- [ ] F9 - Resultados.

**Critério de saída:**

1. As nove frentes auditadas, cada uma com relatório e veredito.
2. Todo achado submetido à verificação adversarial.
3. `docs/auditoria.md` completo, incluindo achados refutados e limitações
   metodológicas.
4. Toda correção aprovada aplicada, e toda correção em caminho não coberto pela
   impressão digital acompanhada de teste que falha antes e passa depois.
5. Impressão digital regravada, comparada, com a classificação final de cada
   correção registrada.
6. Suíte de CPU integralmente aprovada, com no mínimo os 254 testes atuais mais
   os acrescentados pela auditoria.
7. Suíte de GPU integralmente aprovada, com no mínimo os 17 testes atuais mais
   os acrescentados.
8. Portão dos 18 cenários executado e conferido.
9. Roteiro do benchmark regenerado e conferido.
10. Manifesto de congelamento renovado, com `readiness` retornando
    `ready: true` e `git_dirty: false`.
11. `TODO.md` com o checkpoint da B11B e com o cabeçalho "Estado de retomada"
    corrigido.
12. `AGENTS.md` seção 14 e `README.md` atualizados quanto ao estado real.
13. Todos os commits com autoria e assinatura exclusivas do usuário.

**Checkpoint de retomada:**

- commit auditado `ca5b81f`, com a B11A-I como último bloco concluído; a B11-E
  e a B11A-E aguardam a conclusão da B11B;
- brainstorming encerrado com seis decisões aprovadas pelo usuário;
- primeira decisão, alcance: todo defeito real é corrigido, aceitando desde já
  o custo de refazer o tuning e o piloto caso a correção altere resultados;
- segunda decisão, profundidade das premissas: conformidade mais solidez
  interna; verifica-se que o código faz o que os documentos afirmam e que cada
  premissa é bem definida e entrega o que promete; não se reabrem escolhas de
  desenho defensáveis;
- terceira decisão, execução: auditores independentes por frente, sem receber
  justificativa do autor do código, seguidos de verificação adversarial com
  instrução de refutar por padrão;
- quarta decisão, oráculo de regressão: impressão digital determinística
  rápida após cada correção, mais portão final de reprodução dos 18 cenários
  do piloto contra `results/tables/pilot_runs.parquet`;
- quinta decisão, registro: documento versionado `docs/auditoria.md`;
  especificação e plano permanecem em `superpowers/`, fora do Git, conforme a
  Seção 12.1 do `AGENTS.md`;
- sexta decisão, melhorias: todas são aplicadas, inclusive legibilidade e
  refatoração em arquivos protegidos pelo congelamento;
- rótulo do bloco aprovado: B11B - Auditoria técnica pré-execução;
- especificação e plano aprovados explicitamente pelo usuário em 19/08/2026.

---

## B12 - Análise e visualização

**Estado:** `PENDENTE`

**Depende de:** B11. Incorpora B11A somente se o experimento adicional for
executado.

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

- [ ] Sensibilidade ao raio de 400 m.
- [ ] Sensibilidade sem (O_{ij}).
- [ ] Peso não uniforme dos componentes.
- [ ] Seleção endógena de `K`.
- [ ] Comparação exata adicional na instância minúscula.
