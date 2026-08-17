# TODO operacional

Este arquivo organiza o desenvolvimento em blocos interrompíveis e retomáveis.
Ele registra o estado operacional do projeto. Os requisitos acadêmicos continuam
sendo definidos por `docs/trabalho.md`, e as decisões metodológicas por
`docs/formulation.md` e `docs/experiments.md`.

## Estado de retomada

- **Atualizado em:** 17/08/2026
- **Bloco ativo:** nenhum
- **Fase do bloco ativo:** B9 concluída, aguardando início da B10
- **Último bloco concluído:** B9 - Tuning
- **Próxima ação atômica:** iniciar o brainstorming interativo da B10 quando solicitado.
- **Bloqueios conhecidos:** nenhum.
- **Última verificação:** `uv run pytest -q` aprovado, `git diff --check` sem
  erros e auditoria dos sete artefatos concluída em 17/08/2026.

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

## B11A - Experimento adicional com GPU

**Estado:** `PENDENTE - ADICIONAL`

**Depende de:** B11.

**Objetivo:** avaliar se uma implementação em GPU produz aceleração relevante
sem alterar o baseline normativo em CPU.

**Tarefas:**

- [ ] Selecionar os algoritmos e operações tecnicamente adequados à GPU.
- [ ] Manter o caminho CPU com NumPy e `float64` como referência normativa.
- [ ] Implementar o caminho GPU separadamente, sem alterar resultados já
  congelados.
- [ ] Definir e testar equivalência numérica, de orçamento e de convergência.
- [ ] Registrar GPU, CPU, software, precisão numérica e ambiente de execução.
- [ ] Medir tempo total, tempo computacional relevante e custos de transferência.
- [ ] Calcular speedup por tamanho e cenário.
- [ ] Documentar divergências, limitações e casos em que a GPU não compensa.

**Critério de saída:** comparação CPU e GPU auditável, ou limitação explícita
registrada caso o experimento adicional não possa ser executado. A
indisponibilidade de GPU não invalida nem bloqueia o baseline obrigatório.

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
