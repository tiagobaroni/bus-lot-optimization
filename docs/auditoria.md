# Auditoria técnica B11B - registro dos achados da fase de diagnóstico

## Cabeçalho

**Escopo auditado.** Nove frentes cobrindo o repositório inteiro no que toca à
campanha experimental: F1 mecanismo geral do núcleo compartilhado
(`src/metaheuristica/` sem os três algoritmos), F2 suíte de testes (`tests/`),
F3 PSO (`src/metaheuristica/pso.py`), F4 ACO (`src/metaheuristica/aco.py`),
F5 Busca Tabu (`src/metaheuristica/tabu.py`), F6 orquestração do benchmark e
congelamento (`experiments/`), F7 disciplina de CPU, threads e cronometragem,
F8 infraestrutura GPU (`gpu/`) e F9 resultados já publicados
(`results/`, tuning e piloto).

**Data.** 19 de agosto de 2026.

**Commit auditado.** `ca5b81f89f7f62a82e92c92408a932e7ec08e8c6`, ponto de partida
da branch `auditoria-b11b`. A fase de diagnóstico não escreveu em arquivo algum
do repositório; este documento é o primeiro produto de escrita da auditoria.

**Método.** Cada frente foi auditada por um auditor independente, com instrução de
tratar toda decisão de código como suspeita até que os documentos a justificassem,
com permissão de execução e proibição de escrita. Os nove relatórios somam 7.164
linhas. Em seguida, cada um dos 89 achados passou por verificação adversarial
independente, conduzida por quem não auditou a frente, com instrução de refutar
por padrão: nove verificadores de frente mais verificadores dedicados aos quatro
achados originalmente classificados como `D1`. Os números publicados aqui são os
do verificador; onde auditor e verificador divergiram, a divergência está
registrada em campo próprio de cada achado.

**Resultado agregado da verificação.** Dois achados foram refutados
integralmente e receberam classe `R`. Seis foram rebaixados de classe. Cerca de
uma dúzia de magnitudes foi corrigida para baixo, sem derrubar o achado. A
contagem de `D1` caiu de quatro para um.

**Sobre o esquema de campos.** A seção 9 de `superpowers/B11B_spec.md` trata da
política de congelamento e cascata, e não do esquema de registro. A lista dos
onze campos obrigatórios usada aqui é a do Passo 3 do briefing da Tarefa 12, que
é a fonte disponível e explícita. Um décimo segundo campo, de divergência entre
auditor e verificador, foi acrescentado para cumprir a regra de publicar o número
do verificador sem apagar o do auditor.

## 1. Sumário quantitativo por classe

| Classe | Definição | Quantidade | Destino |
|---|---|---:|---|
| `D1` | Defeito que altera qualquer número produzido pela campanha | 1 | Onda A |
| `D2` | Defeito real cujo efeito não aparece em resultado da campanha | 10 | Onda B |
| `D3` | Defeito latente de risco operacional | 29 | Onda B, prioridade |
| `M1` | Melhoria de desempenho preservando comportamento | 6 | Onda B |
| `M2` | Melhoria de cobertura de teste | 21 | Onda do defeito associado, ou C |
| `M3` | Melhoria de legibilidade ou simplificação | 7 | Onda C |
| `L1` | Limitação metodológica que não é defeito | 13 | Registro apenas |
| `R` | Refutado pela verificação adversarial | 2 | Apêndice A |
| **Total** | | **89** | |

O único `D1` é o achado A1 da frente F3, o limite de velocidade do PSO que não
limita o passo. Ele muda 10 de 10 resultados oficiais do tuning do PSO e é o único
`D1` **hoje**, isto é o único cujo diff já foi **medido**.

**A Onda A não é necessariamente o único gatilho da cascata, e isso precisa ser dito
aqui.** Três achados classificados `D2` publicam previsão de diff **não zero** na
impressão digital, todos em campo de diagnóstico: **A5** no PSO, **F4-4** no ACO e
**F5-3** na Busca Tabu. Pela regra de reclassificação automática da taxonomia,
"achado previsto como `D2` que produza qualquer diferença passa a ser `D1`, e o ramo
alterado da cascata assume", os três **reclassificam para `D1`** se a impressão
digital confirmar a previsão, e pelo ruling de cascata por escopo cada um toca um
cenário `pso`, `aco` e `tabu` respectivamente, o que dispara o ramo alterado.

**A pergunta que discrimina, e ela está aberta:** a impressão digital dos 42 cenários
compara o dicionário de diagnósticos, ou apenas o vetor de solução e os sete campos do
`EvaluationResult`? A seção 9 da especificação diz "diff zero nos 42 cenários" sem
enumerar campos, e a Tarefa 14, que define o oráculo, ainda não existe. O oráculo
privado que a frente F4 usou no protótipo **comparava** os diagnósticos, mas é artefato
diferente. **Se o oráculo da Tarefa 14 cobrir diagnósticos, a Onda B carrega três
gatilhos de cascata além da Onda A; se cobrir só solução e avaliação, os três fecham
com diff zero e permanecem `D2`.** A decisão pertence à Tarefa 14 e precisa ser tomada
com esta consequência à vista, não descoberta no portão da Tarefa 13. Registro que
isso **fortalece** o argumento de que o ramo alterado já está praticamente comprado, e
não o contrário.

**Distribuição por frente, depois de todas as reclassificações.**

| Frente | `D1` | `D2` | `D3` | `M1` | `M2` | `M3` | `L1` | `R` | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F1 mecanismo geral | 0 | 1 | 3 | 2 | 1 | 1 | 1 | 0 | 9 |
| F2 testes | 0 | 0 | 1 | 0 | 15 | 0 | 0 | 0 | 16 |
| F3 PSO | 1 | 1 | 2 | 1 | 1 | 0 | 3 | 1 | 10 |
| F4 ACO | 0 | 1 | 1 | 1 | 1 | 0 | 1 | 0 | 5 |
| F5 Busca Tabu | 0 | 1 | 2 | 1 | 1 | 1 | 1 | 0 | 7 |
| F6 benchmark | 0 | 3 | 9 | 0 | 0 | 0 | 0 | 0 | 12 |
| F7 CPU | 0 | 2 | 5 | 0 | 1 | 1 | 1 | 0 | 10 |
| F8 GPU | 0 | 1 | 4 | 1 | 1 | 4 | 2 | 1 | 14 |
| F9 resultados | 0 | 0 | 2 | 0 | 0 | 0 | 4 | 0 | 6 |
| **Total** | **1** | **10** | **29** | **6** | **21** | **7** | **13** | **2** | **89** |

**Reconciliação com as classes propostas pelos auditores.** A contagem original,
antes da verificação adversarial, era `D1` 4, `D2` 10, `D3` 33, `M1` 6, `M2` 21,
`M3` 4, `L1` 11, total 89. As oito mudanças:

| Achado | Classe do auditor | Classe do verificador | Razão |
|---|---|---|---|
| A2 (F3) | `D1` | `R` | A premissa citada não existe em `docs/formulation.md` seção 16 |
| F8-3 (F8) | `D3` | `R` | Existe um segundo mecanismo de conformidade que o achado não citou |
| F8-1 (F8) | `D1` | `M3` mais componente `M2` | A divergência medida é 1/1802 da tolerância normativa de `1e-12` |
| F8-2 (F8) | `D1` | `L1` | Não existe resultado GPU oficial a alterar; o número comprometido é futuro |
| A9 (F3) | `D3` | `L1` | Apoiava-se em regra metodológica da auditoria, não em regra do projeto |
| F6-09 (F6) | `D3` | `D2` | A consequência central, lote permanentemente sem barreira, é falsa |
| F8-5 (F8) | `D2` | `M3` | Coerência com a adjudicação de código morto por desenho nos mesmos campos |
| F8-9 (F8) | `D3` | `M3` | O cenário exige evento futuro deliberado; a campanha congelada usa 40, dentro do limite |

Aritmética: `D1` 4 menos {A2, F8-1, F8-2} igual a 1; `D3` 33 menos {A9, F6-09,
F8-9, F8-3} igual a 29; `D2` 10 mais {F6-09} menos {F8-5} igual a 10; `M3` 4 mais
{F8-1, F8-5, F8-9} igual a 7; `L1` 11 mais {A9, F8-2} igual a 13; `R` 0 mais
{A2, F8-3} igual a 2.

**Convenção de contagem.** F8-1 é contado uma única vez, sob `M3`, porque o
resíduo substantivo depois da refutação é código morto. Ele carrega também uma
componente `M2`, de asserção ausente, que segue junto na mesma correção. Se as
duas componentes fossem contadas em separado, a coluna `M2` teria 22 e a soma
das classes seria 90 para 89 achados.

## 2. Esquema de campos e convenções

Cada achado traz doze campos, na ordem fixa abaixo.

1. **Frente** - qual das nove frentes o produziu.
2. **Classe** - a classe após a verificação adversarial, pela taxonomia da
   seção 1.
3. **Premissa** - o que o documento prescreve, com documento, seção e a
   **fonte** declarada.
4. **Previsto** - o que a premissa implicava para o código.
5. **Código** - o que o código faz, com arquivo e linha.
6. **Evidência** - números do verificador, não do auditor.
7. **Veredito adversarial** - confirmado, confirmado parcialmente, reclassificado
   ou refutado, com a razão.
8. **Divergência auditor / verificador** - o que o auditor publicou e a
   verificação corrigiu. `nenhuma` quando o verificador reproduziu tudo.
9. **Decisão** - o que fazer.
10. **Onda** - A, B, C ou registro apenas.
11. **Situação** - `aberto`, `aberto com lacuna declarada`, `fechado sem ação`,
    `refutado` ou, a partir da Onda A, `fechado com correção de código` e `fechado
    com teste novo`, sempre com o pacote que fechou o achado.
12. **Impressão digital** - era `pendente` em todos na fase de diagnóstico, porque o
    oráculo dos 42 cenários ainda não existia. O oráculo passou a existir na Tarefa
    14, em `experiments/audit_fingerprint.py`, e desde o pacote A1 as entradas já
    fechadas trazem o resultado observado no lugar de `pendente`: o escopo de
    cenários e de campos que divergiu, ou a declaração de que a alteração não tem
    efeito próprio por ser restrita a `tests/`.

**Convenção de fonte de premissa, obrigatória.** Toda citação de premissa declara
sua fonte, em uma de duas categorias:

- **normativa** - `docs/formulation.md` e `docs/experiments.md`. São os documentos
  do projeto. Divergência contra eles é defeito do projeto.
- **metodologia da auditoria** - qualquer coisa em `superpowers/` ou nos dossiês
  de frente desta auditoria, incluindo `constraints.md` e a exigência de
  comparação exata por `float.hex()`. Divergência contra eles não é defeito do
  projeto e não pode ser classificada como tal.

A confusão entre as duas categorias fabricou dois achados nesta auditoria. A
causa raiz está registrada na seção 6, porque é achado sobre a auditoria e não
sobre o projeto.

**Convenção de lacuna declarada.** Achado cujo mecanismo e cujas premissas foram
confirmados, mas cuja magnitude sustentadora da classe não foi reproduzida pelo
verificador, entra com situação `aberto com lacuna declarada` e não pode ser
tratado como fechado. É o caso de A7 e A8 da frente F3.

## 3. Achados por frente

### 3.1. Frente F1 - mecanismo geral do núcleo compartilhado

Nove achados, nenhum refutado, sete confirmados integralmente e dois confirmados
parcialmente com magnitudes internas derrubadas. Nenhuma reclassificação. O
verificador conferiu as nove premissas citadas palavra por palavra na fonte, e não
no relatório, e registrou uma única imprecisão, em F1-02.

**Ausência de `D1` afirmada, não omitida.** As verificações que produziriam `D1`
se falhassem foram executadas e passaram: as `K(N-K)` avaliações do guloso
conferem nas 18 combinações oficiais; os limiares `ceil(jB/100)` conferem em sete
orçamentos, com último limiar igual a `B` e sequência estritamente crescente; a
canonicalização é invariante sob permutação de rótulos em 300 soluções vezes todas
as `K!` permutações, com zero falhas; o reparo é determinístico e termina em no
máximo `K-1` iterações; e existe um único caminho de agregação, sem renormalização
depois da soma ponderada.

#### F1-01. A avaliação final reaproveitada pelo guloso não é a função objetivo da solução do guloso

- **Frente:** F1.
- **Classe:** `D3`.
- **Premissa:** `docs/formulation.md` seção 13.3, linhas 581-582, literal: "A
  última avaliação escolhida coincide com a função objetivo completa e será
  reutilizada sem nova avaliação". **Fonte: normativa.** A leitura exata de
  "coincide" tem apoio interno independente: `tests/test_greedy.py:49-50` já
  afirma `result.evaluation == evaluate_solution(...)` com `==` de dataclass, sem
  tolerância.
- **Previsto:** a última avaliação parcial do guloso é numericamente idêntica à
  função objetivo completa da solução devolvida, autorizando não gastar uma
  avaliação extra.
- **Código:** `src/metaheuristica/greedy.py:135` e `greedy.py:149`, com origem em
  `src/metaheuristica/objective.py:163` (`_evaluate_partial_assignment`) e
  `objective.py:105` (`_evaluate_arrays`). No último passo o conjunto induzido é a
  instância inteira, mas permutada pela ordem de processamento decrescente de
  PU·km; `np.bincount` acumula na ordem do vetor recebido e `np.triu_indices`
  percorre os pares na ordem da matriz recebida. `greedy.py:149` publica esse
  `evaluation` ao lado de `solution` canonicalizada, e o par não é
  autoconsistente.
- **Evidência:** divergência bit a bit reproduzida pelo verificador em **18 de 18**
  combinações oficiais, com 1 a 6 campos divergentes por combinação, e
  `result.evaluation == evaluate_solution(...)` falso nas 18. Os três exemplos do
  relatório reproduziram com os mesmos dígitos hexadecimais: `N=20, K=3`
  `total_cost` `0x1.139ef3308520dp-4` contra `0x1.139ef3308520cp-4`, delta
  `1,3878e-17`; `N=150, K=3` `cv_demand` delta `-1,5959e-16`; `N=60, K=4`
  `cv_production` delta `-1,6653e-16`. A contagem de avaliações confere `K(N-K)`
  exato nas 18, logo o defeito é de valor e não de orçamento.
- **Veredito adversarial:** CONFIRMADO, classe `D3` mantida. A defesa de que a
  seção 13.3 poderia não exigir igualdade bit a bit foi rejeitada por dois motivos
  independentes: a seção não oferece tolerância própria para essa afirmação, e
  derrubar a leitura exata exigiria derrubar o teste existente do próprio
  repositório.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Reavaliar a solução canônica final, ou construir a última
  avaliação parcial na ordem natural da instância, de modo que o par publicado
  seja autoconsistente.
- **Onda:** B, com prioridade, junto de F1-07 que é o irmão de cobertura.
- **Situação:** fechado no commit `5f2774a`, do pacote B6. A avaliação publicada
  passa a ser calculada sobre a solução canônica, na ordem natural da instância,
  pelo mesmo caminho de `evaluate_solution`, num ponto único de publicação que
  também absorveu o ramo `budget == 0`, o qual avaliava rótulos crus e carregava o
  mesmo defeito latente. A chamada não passa pelo `FitnessEvaluator` e por isso não
  debita unidade alguma de orçamento: o contador segue exatamente `K(N-K)`, com a
  guarda existente intacta. `solution`, `processing_order` e `trace` não mudam, e o
  `partial_cost` do último passo permanece o valor da ordem de construção, com
  comentário explícito no código.
- **Impressão digital:** diff não zero, **conforme previsto**. Foram 37 campos de
  `evaluation` divergentes, distribuídos pelos 9 cenários `greedy:*`, de 3 a 6
  campos por cenário, sem tocar `solution`, `processing_order`, `evaluations` ou
  qualquer campo de `trace`, e com diff zero nos 33 cenários `tabu:*`, `aco:*` e
  `pso:*`. O envelope observado coincide com o previsto, verificado por dois
  caminhos independentes: script sobre a saída de `compare` e caminhada estrutural
  por `float.hex()` do documento antigo contra o regravado. A linha de base foi
  regravada no mesmo commit, com o conjunto completo dos 42 cenários. Classe `D3`
  mantida: a reclassificação automática da seção 7 da especificação é a fronteira
  entre `D1` e `D2` e não alcança `D3`, e o Passo H não se aplica.

#### F1-02. A tolerância de `_same_evaluation` admite divergência real entre o checkpoint 100 e o resultado final

- **Frente:** F1.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seções 9 e 27 (a partir da linha 929): a
  tabela principal e a tabela de checkpoints registram `best_cost` e os
  componentes da mesma execução, chaveadas por `algorithm`, `instance_size`, `K` e
  `seed`. **Fonte: normativa.**
- **Previsto:** o valor de `best_cost` da linha principal e o do `checkpoint = 100`
  descrevem o mesmo incumbente e são o mesmo número.
- **Código:** `src/metaheuristica/metrics.py:277`, com a definição em
  `metrics.py:325-348`: `_same_evaluation` aplica
  `math.isclose(rel_tol=1e-12, abs_tol=1e-12)` nos sete campos. No caminho CPU
  `checkpoints[-1].evaluation is incumbent_evaluation` é `True` e a tolerância é
  inócua. No caminho GPU os objetos são distintos por construção, com
  `evaluation=final_cpu` e checkpoints medidos na GPU.
- **Evidência:** cenário reproduzido pelo verificador. `OptimizationResult` com
  `algorithm="aco_gpu"`, checkpoint 100 em `total_cost = 0.25` e `evaluation` em
  `0.25 + 9e-13` foi construído sem erro; `to_dict()` exportou
  `0x1.0000000003f55p-2` na tabela principal contra `0x1.0000000000000p-2` na
  tabela de checkpoints, divergência exportada `9,000022949123831e-13`. A defesa
  mais séria, de inalcançabilidade sob a configuração congelada, foi testada e
  **falha**: `verify_every_batch` tem padrão `False`
  (`gpu/src/metaheuristica_gpu/aco.py:133` e `pso.py:134`), `run.py:205` e
  `run.py:207` não passam o argumento, e o único uso de `True` em produção é
  `run.py:131-132`, dentro de `run_conformance` sobre `tiny_manual`.
- **Veredito adversarial:** CONFIRMADO, classe `D3` mantida. Risco operacional
  sobre caminho alcançável é exatamente `D3`.
- **Divergência auditor / verificador:** o achado citou a seção 26 como exigindo
  "resultados numericamente equivalentes"; o documento diz "resultados
  numericamente equivalentes **quando aplicável**"
  (`docs/experiments.md:922`). O veredito não se apoia nessa citação, e sim na
  inconsistência entre as duas tabelas da seção 27.
- **Decisão:** corrigir. Trocar a tolerância por verificação de identidade, ou por
  igualdade exata via `float.hex()`, e alinhar o caminho GPU para publicar o mesmo
  objeto nos dois lugares.
- **Onda:** B, com prioridade.
- **Situação:** fechado com correção de código e três testes novos, no commit do
  pacote B7. `_same_evaluation` passa a aceitar somente identidade de objeto ou
  igualdade exata por `float.hex()` nos sete campos, e os caminhos GPU do ACO e do
  PSO passam a publicar em `evaluation` o mesmo objeto que a tabela de checkpoints
  carrega, em vez da avaliação recalculada na CPU. A conferência de conformidade
  contra a CPU permanece intacta, por `require_equivalent`, cuja tolerância de
  `1e-12` é contrato do projeto e não se confunde com a comparação exata, que é
  metodologia da auditoria. A divergência prevista pelo achado foi **observada em
  execução real** ao rodar o teste novo antes da correção: no PSO da GPU, com
  `artesp_rmsp_20`, `K=3`, seed 7 e orçamento 600, a avaliação recalculada na CPU
  deu `total_cost` `0,07671054313991764` contra `0,07671054313991765` medido na
  GPU, isto é a divergência de último bit que a tolerância absorvia em silêncio.
  **Passo G.** Classe prevista `D3`; classe observada `D3`; a observação **bate**
  com a previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, sobre o **conjunto completo dos 42
  cenários**, sem `--only`, porque `metrics.py` é compartilhado pelos quatro
  algoritmos. **Passo G.** Diff previsto zero; diff observado zero; a observação
  **bate** com a previsão. O zero é o esperado por construção: no caminho CPU
  `checkpoints[-1].evaluation is incumbent_evaluation`, logo apertar a guarda não
  pode mudar número algum, e o oráculo não percorre o caminho GPU.

#### F1-03. O incumbente registrado pode crescer, e o desvio acumula acima da tolerância

- **Frente:** F1.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 9, linhas 288-289, literal: "Para cada
  checkpoint serão registrados o melhor custo total acumulado e seus quatro
  componentes normalizados"; e seção 10.1, linha 322, "melhor custo total final".
  **Fonte: normativa.**
- **Previsto:** o valor gravado em cada checkpoint é o mínimo dos custos viáveis
  já observados, e a sequência `C_best(e_1)` a `C_best(e_100)` é não crescente.
- **Código:** `src/metaheuristica/metrics.py:153-165`, em especial
  `metrics.py:162` e `:164`. `_is_better` trata `abs(difference) <= 1e-12` como
  empate e, no empate, substitui o incumbente quando a solução canônica é
  lexicograficamente menor, trocando também `_incumbent_evaluation`. A janela de
  tolerância desliza com o novo custo de referência e o desvio acumula sem limite
  ligado a `1e-12`.
- **Evidência:** o verificador refez o cenário com **quatro soluções canônicas e
  viáveis**, conferidas uma a uma por `solution_key(..., n_units=4, k=2) == sol`:
  `(0,1,1,1)` em `0.5`, `(0,1,1,0)` em `0.5+5e-13`, `(0,1,0,1)` em `0.5+1e-12` e
  `(0,0,1,1)` em `0.5+15e-13`, com desvio acumulado
  `1,500022328571049e-12`, idêntico ao do cenário original. O complemento também
  reproduz: uma melhora real de `5e-13` é descartada quando a solução é
  lexicograficamente maior.
- **Veredito adversarial:** CONFIRMADO, classe `D3` mantida. O mecanismo sobrevive
  à correção do cenário.
- **Divergência auditor / verificador:** o cenário publicado pelo auditor usava
  soluções não canônicas e com lotes vazios, inalcançáveis em
  `ConvergenceRecorder.observe`, porque o caminho real só recebe soluções que
  passaram por `solution_key`. **A onda de correção deve usar o cenário canônico
  do verificador, não o do relatório.** Isso corrige a apresentação, não o achado.
- **Decisão:** corrigir. Comparar por mínimo estrito, mantendo o desempate
  lexicográfico apenas para escolha de solução e não para substituição do valor
  registrado.
- **Onda:** B, com prioridade.
- **Situação:** fechado com correção de código e sete testes novos, no commit do
  pacote B8. `_is_better` passa a comparar `total_cost` por mínimo estrito e a
  aplicar o desempate lexicográfico **apenas na igualdade exata**, onde não há
  valor a deslocar. O cenário canônico do verificador foi usado como teste, e não
  o do relatório, conforme a divergência registrada acima: as quatro soluções
  `(0,1,1,1)` em `0,5`, `(0,1,1,0)` em `0,5+5e-13`, `(0,1,0,1)` em `0,5+1e-12` e
  `(0,0,1,1)` em `0,5+15e-13`, com `n_units=4` e `k=2`. Sob a forma anterior o
  desvio acumulado reproduziu `1,500022328571049e-12`, idêntico ao registrado
  aqui; sob a forma corrigida a série do incumbente é não crescente e termina em
  `0,5`. Um segundo teste apresenta o contraexemplo de não transitividade nas
  **seis** ordens possíveis, e falhava em quatro delas antes da correção.
  **Passo G.** Classe prevista `D3`; classe observada `D3`; a observação **bate**
  com a previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, sobre o **conjunto completo dos 42
  cenários**, sem `--only`, porque `metrics.py` é compartilhado pelos quatro
  algoritmos. **Passo G.** Diff previsto zero; diff observado zero; a observação
  **bate** com a previsão. O zero confirma por medição a evidência do registro, de
  que empates dentro de `1e-12` entre partições distintas das instâncias ARTESP não
  ocorrem, e a janela exposta pela correção é maior que o empate exato: toda
  diferença em `(0, 1e-12]` mudava de desfecho.

#### F1-04. A mensagem de `EvaluationLimitReached` interpola `evaluations` no lugar do orçamento

- **Frente:** F1.
- **Classe:** `D2`.
- **Premissa:** `docs/experiments.md` seção 8: o algoritmo é interrompido
  imediatamente depois da avaliação que consome o limite, e o diagnóstico
  identifica o limite. **Fonte: normativa.** O padrão correto de mensagem é
  definido pelo próprio código, em `src/metaheuristica/evaluator.py:100`.
- **Previsto:** a mensagem informa avaliações consumidas contra orçamento, com o
  orçamento na segunda posição.
- **Código:** `src/metaheuristica/optimizer.py:103`, literalmente
  `f"orçamento esgotado: {self.evaluations}/{self.evaluations} avaliações"`,
  dentro de `_stop_at_limit`, guardado por `if self._evaluator.remaining == 0` em
  `optimizer.py:101`.
- **Evidência:** como `remaining` é `budget - evaluations`
  (`evaluator.py:94-95`), `remaining == 0` implica `evaluations == budget` sempre,
  portanto o texto renderizado é sempre correto e nenhuma entrada atual produz
  saída divergente. O defeito é estabelecido por inconsistência interna
  verificável: `evaluator.py:100` é
  `f"orçamento esgotado: {self._evaluations}/{self._budget} avaliações"`, com o
  orçamento na segunda posição.
- **Veredito adversarial:** CONFIRMADO, classe `D2` mantida. O verificador
  registrou que refutar este achado por não discriminar na saída seria refutar a
  própria existência da classe `D2`, que é literalmente a classe de defeito sem
  efeito em resultado. Não é `M3`, porque a expressão está objetivamente errada e
  passaria a mentir sob qualquer relaxamento do guardião.
- **Divergência auditor / verificador:** nenhuma. O relatório declarou por conta
  própria que nenhuma entrada atual divergia, e desqualificou corretamente a
  evidência errada da mensagem `"1/1 avaliações"`, que vem de `evaluator.py:100`
  e está correta.
- **Decisão:** corrigir. Trocar a segunda interpolação por
  `self._evaluator.budget`.
- **Onda:** B, junto de A5 e F5-3, no commit único de contrato de
  `optimizer.py` descrito na conexão 9 da seção 5. A alternativa de deixá-lo na Onda C
  foi descartada: a interpolação da mensagem é logicamente independente do contrato do
  contador, mas mora na **mesma função**, `_stop_at_limit`, e separar as duas
  correções significaria tocar `optimizer.py` duas vezes, em duas ondas, sob
  congelamento.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero.

#### F1-05. `_balance_totals_component` usa NumPy em vetores de 3 a 8 elementos e domina o custo do ACO

- **Frente:** F1.
- **Classe:** `M1`.
- **Premissa:** `docs/experiments.md` seção 8 (orçamento de avaliações como
  critério de parada) e seção 29.1 (estimativa de 33 h ideais e 35 a 40 h com
  margem para a B11-E); `docs/formulation.md` seção 15. **Fonte: normativa.**
  Nenhuma prescrição documental proíbe a implementação atual: o achado é de
  desempenho, não de conformidade.
- **Previsto:** nada. A seção 29.1 registra a assimetria operacional como fato a
  orientar o escalonamento, e este é o trecho onde o custo nasce.
- **Código:** `src/metaheuristica/objective.py:29-32`, consumido em
  `objective.py:66-67` dentro de `_evaluate_aggregates`, chamado pelo ACO em
  `src/metaheuristica/aco.py:119` (`_PartialConstructionState.evaluate_choice`) e
  `aco.py:212`. `np.mean(totals)` e `np.std(totals, ddof=0)` sobre vetores de
  comprimento `K` entre 3 e 8: o custo é quase todo overhead de despacho do NumPy,
  não aritmética.
- **Evidência:** medição reproduzida pelo verificador com `min` de 7 repetições de
  20.000 laços: `_evaluate_aggregates` com `K=5` em `26,60 us`, das quais as duas
  chamadas de `_balance_totals_component` custam `23,97 us`, isto é **90,1%**
  contra os 91% declarados. Corroboração independente por `cProfile` da frente F4
  em `artesp_rmsp_150`, `K=8`: `_evaluate_aggregates` em 52,1% e
  `_balance_totals_component` em 45,0% do tempo total do ACO, com 443.104
  chamadas, o que dá 86,3% de `_evaluate_aggregates`. A atribuição de 55 a 75% a
  `evaluate_choice` também é corroborada: a frente F4 mede `evaluate_choice` em
  74,6% cumulativo em `K=8`.
- **Veredito adversarial:** CONFIRMADO PARCIALMENTE. O diagnóstico sobrevive e a
  classe `M1` é mantida. **A prescrição é refutada**, e com ela a localização do
  achado.
- **Divergência auditor / verificador:** três itens. Primeiro, a "ressalva
  obrigatória" do relatório, de que capturar o ganho exigiria quebrar bits e
  refazer tuning e piloto, é **falsa**: a variante O2 da frente F4 elimina o mesmo
  overhead preservando os bits exatamente. Segundo, o parágrafo "Prioridade
  relativa entre os dois achados `M1`" apresenta uma dicotomia falsa e deve ser
  riscado: existe uma terceira opção, F1-06 e o ganho de F1-05 juntos no ramo
  preservado. Terceiro, erro de localização: o ganho bit-preservador não mora em
  `objective.py:29-32` e sim no laço de construção de `aco.py`, que é quem pode
  agrupar as `m` alternativas numa única redução; `_balance_totals_component`
  chamada uma vez por vetor não tem o que economizar sem mudar a aritmética. O
  valor de `2,89 us` do equivalente aritmético não reproduziu em nenhuma das duas
  formas testadas (`1,03 us` sobre lista, `5,32 us` sobre `ndarray`), mas o fator
  derivado fica entre 4,3x e 5,4x contra os 4,9x declarados. O verificador recusou
  explicitamente o enquadramento de comparar 3,58x com 4,9x, porque são escopos
  diferentes: um sobre o ACO inteiro, outro sobre `_evaluate_aggregates` isolado.
- **Decisão:** não abrir correção própria. A medição fica registrada como
  diagnóstico e o ganho é capturado por F4-1, que é a variante bit-preservadora.
  Ver a conexão 1 da seção 5.
- **Onda:** B, embutida em F4-1.
- **Situação:** fechado **sem correção própria**, no commit `d297377`, do pacote B5,
  exatamente como decidido: a medição fica registrada como diagnóstico e o ganho que ela
  buscava foi capturado por F4-1 pelo caminho bit-preservador. Não há linha de código
  atribuível a este achado, e o oráculo que o cobre é o de F4-1,
  `test_batched_choice_costs_reproduce_the_reference_bit_by_bit`, herdado por absorção. A
  ressalva original do relatório, de que capturar o ganho exigiria quebrar bits e refazer
  tuning e piloto, fica definitivamente refutada por demonstração: o ganho foi capturado
  e o diff é zero nos 42 cenários.
  **Sobre o parágrafo "Prioridade relativa entre os dois achados `M1`", e a instrução de
  riscá-lo.** A instrução está cumprida, e a forma de cumprimento precisa ficar escrita
  para que o item não fique eternamente aberto. O parágrafo **não existe** neste registro
  versionado: ele pertence ao relatório de origem da frente F1, e este documento apenas o
  cita, aqui no campo de divergência acima e na conexão 1 da seção de conexões, nos dois
  casos **já** para declarar que ele apresenta uma dicotomia falsa e deve ser riscado.
  Riscar aqui seria riscar a própria instrução de riscar. A dicotomia foi resolvida de
  fato, e não apenas por anotação: a terceira opção que o parágrafo negava, F1-06 e o
  ganho de F1-05 juntos no ramo bit-preservado, foi a que o pacote B5 executou. A
  instrução é portanto **inócua no registro versionado** e fica registrada como
  executada, sem pendência residual.
  **Passo G.** Classe prevista `M1`; classe observada `M1`; a observação **bate** com a
  previsão. Sem reclassificação, e o Passo H não se aplica. A classe é mantida porque o
  que caiu foi a prescrição, e não a medição, que reproduz com 90,1% e tem corroboração
  independente de 86,3% por `cProfile`.
- **Impressão digital:** zero, conforme previsto, herdada de F4-1 e conferida no
  conjunto completo dos 42 cenários no Passo F de `d297377`. **Passo G.** Diff previsto
  zero; diff observado zero; a observação **bate** com a previsão.

#### F1-06. Cada avaliação completa recomputa `np.triu_indices` e canonicaliza e valida a solução duas vezes

- **Frente:** F1.
- **Classe:** `M1`.
- **Premissa:** `docs/experiments.md` seção 8 (orçamento de 150.000 avaliações na
  instância grande) e seção 29.1 (35 a 40 h). O invariante a preservar é o da
  seção 11 de `docs/formulation.md`, canonicalização usada em comparação, testes,
  armazenamento e cache. **Fonte: normativa.**
- **Previsto:** nada especifica a implementação. A correção é de desempenho e não
  pode alterar o invariante de canonicalização.
- **Código:** `src/metaheuristica/objective.py:115` (`np.triu_indices` dentro de
  `_evaluate_arrays`) e `src/metaheuristica/evaluator.py:104-120`
  (`FitnessEvaluator.evaluate`), que chama `solution_key` (`canonical.py:68`, que
  canonicaliza e valida) e depois `evaluate_solution` (`objective.py:188`, que
  valida outra vez em `objective.py:197`). Para `N=150` são 11.175 pares por
  avaliação e dois vetores `int64` de 11.175 posições alocados por chamada.
- **Evidência:** mecanismo confirmado por leitura. Piso realmente alcançável pela
  correção bit-segura, recomposto pelo verificador como `solution_key` mais gather
  com triangular pré-computado mais `_evaluate_aggregates`, sem revalidação:

  | `N` | `K` | `evaluate` atual | piso bit-seguro | gather isolado | `_evaluate_aggregates` | `solution_key` |
  |---:|---:|---:|---:|---:|---:|---:|
  | 20 | 3 | `129,9 us` | `53,4 us` | `8,4 us` | `26,3 us` | `18,7 us` |
  | 60 | 5 | `169,0 us` | `71,7 us` | `17,4 us` | `26,4 us` | `27,9 us` |
  | 150 | 5 | `352,0 us` | `146,3 us` | `70,8 us` | `26,4 us` | `49,2 us` |
  | 150 | 8 | `349,3 us` | `138,9 us` | `62,7 us` | `26,8 us` | `49,4 us` |

  Totais de campanha sobre as 18 combinações e 1.620 execuções: estado atual entre
  **`9,8 h`** e **`10,1 h`** de CPU, piso bit-seguro entre **`4,0 h`** e
  **`4,9 h`**, economia real entre **`5,2 h`** e **`5,8 h`** de CPU. Medições
  isoladas em `N=150`: `np.triu_indices(150, 1)` em **`43,1 us`** e `solution_key`
  em **`49,3 us`**.
- **Veredito adversarial:** CONFIRMADO PARCIALMENTE. O mecanismo sobrevive e a
  classe `M1` é mantida, porque a recomputação por avaliação e a dupla validação
  existem, são verificáveis por leitura e valem entre 5 e 6 horas de CPU de
  campanha. As magnitudes derivadas saem.
- **Divergência auditor / verificador:** cinco itens, todos de inflação de
  magnitude. Primeiro, a coluna "núcleo com triangular pré-computado" do relatório
  é **impossível** e autocontraditória com F1-05 no mesmo documento: declara
  `8,2 us` em `N=20, K=3` para um caminho que obrigatoriamente paga
  `_evaluate_aggregates`, medido em `26,1` a `26,8 us`. O que a coluna realmente
  mediu foi o gather isolado, `8,4 us`, omitindo `_evaluate_aggregates` e
  `solution_key`. Segundo, o piso declarado de **`1,8 h`** está subestimado por
  mais de duas vezes: o real é `4,0` a `4,9 h`. Terceiro, a economia declarada de
  **"cerca de 8 horas"** está superestimada em cerca de 40%: a real é `5,2` a
  `5,8 h`. Quarto, as medições isoladas de **`88,7 us`** e **`93,2 us`** são cerca
  do dobro das reproduzidas, `43,1 us` e `49,3 us`; as porcentagens declaradas de
  14% e 15% não decorrem dos absolutos declarados sobre nenhum denominador
  publicado. Quinto, a conclusão comparativa de "cerca de uma ordem de grandeza a
  favor de F1-05" cai junto, e a decisão que ela pedia não precisa ser tomada.
- **Decisão:** corrigir, pelo caminho explicitamente bit-seguro: pré-computar os
  vetores triangulares por instância e remover a revalidação duplicada, sem
  alterar a ordem das operações de somatório.
- **Onda:** B, junto de F4-1, por serem o mesmo commit de desempenho no módulo
  compartilhado.
- **Situação:** fechado no commit `d297377`, do pacote B5, pelas duas metades da
  prescrição e pelo caminho declaradamente bit-seguro. Primeira metade:
  `_triangular_indices` (`src/metaheuristica/objective.py:30-51`) memoriza os pares do
  triângulo superior **por tamanho**, e não por instância, porque o caminho parcial do
  guloso avalia submatrizes induzidas de todos os tamanhos de 1 a `N`; a ordem dos pares
  é exatamente a de `np.triu_indices`, logo a ordem dos somatórios não muda. Segunda
  metade: `evaluator.py:104-127` canonicaliza uma única vez e passa o vetor canônico
  direto para `_evaluate_labels`, removendo a segunda validação que `evaluate_solution`
  fazia; `evaluate_solution` permanece intacta, porque é a função pública usada pelo
  espelho GPU e pela conferência normativa.
  **Bit-neutralidade da remoção, conferida por leitura na revisão independente.**
  `solution_key` (`canonical.py:68-72`) é literalmente `canonicalize_solution` seguido da
  compreensão de tupla que `evaluator.py:116` passou a fazer na mão, e
  `evaluate_solution` redevolvia, por `validate_solution` (`objective.py:292-302`), o
  mesmo vetor `int64` somente-leitura que `canonicalize_solution` já havia produzido, os
  dois passando por `_immutable_int_array`. Os rótulos que entram em `np.bincount` são
  idênticos em valor, `dtype` e ordem. O `weights or ObjectiveWeights()` removido era
  inócuo, porque `self._weights` nunca é `None` (`evaluator.py:58`).
  **Poder discriminante, e a distinção importa.** A memorização é cache puro: revertê-la
  não muda comportamento algum, logo nenhum teste dirigido pode falhar sem ela e nenhum é
  necessário para a correção. O que ela cria, e o que precisava de teste, é o **contrato
  de imutabilidade** do estado global memorizado, que a própria docstring declara e que
  não era asseverado em lugar nenhum. Esse teste foi escrito no fechamento do pacote:
  `tests/test_objective.py::test_triangular_indices_are_shared_and_read_only` assevera
  que duas chamadas do mesmo tamanho devolvem o **mesmo objeto**, que os dois vetores têm
  `flags.writeable is False`, que uma escrita neles levanta `ValueError` e que a ordem
  dos pares continua sendo a de `np.triu_indices`. A remoção da validação dupla em
  `evaluator.py`, essa sim, **é** observável, porque muda a forma do argumento que chega
  a `_evaluate_labels` de tupla para vetor, e está coberta pela suíte inteira e pelo diff
  zero nos 42 cenários.
  **Passo G.** Classe prevista `M1`; classe observada `M1`; a observação **bate** com a
  previsão. Sem reclassificação, e o Passo H não se aplica. A lacuna de teste registrada
  pela revisão independente do pacote está fechada.
- **Impressão digital:** zero, conforme previsto, dentro do zero conferido no conjunto
  completo dos 42 cenários no Passo F de `d297377`. **Passo G.** Diff previsto zero; diff
  observado zero; a observação **bate** com a previsão. A expectativa foi confirmada pelo
  oráculo, validado por marcador, e não presumida.

#### F1-07. O teste que sustenta o reaproveitamento do guloso só exercita uma instância de 4 unidades

- **Frente:** F1.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 13.3 e `docs/experiments.md` seção 29,
  verificações antes do benchmark final. **Fonte: normativa.** O invariante é
  afirmado para "uma instância com `N` unidades", sem restrição de tamanho.
- **Previsto:** a cobertura exercita o invariante em instância representativa das
  que a campanha vai usar.
- **Código:** `tests/test_greedy.py:48-50`,
  `test_final_partial_result_equals_public_objective`, cujo corpo é
  `result = run_greedy(TINY, k=2)` e
  `assert result.evaluation == evaluate_solution(TINY, result.solution, k=2)`.
  `TINY` é `data/instances/tiny_manual.json`, com `N=4`, ordem de processamento
  `(0, 2, 1, 3)` e 4 avaliações.
- **Evidência:** o verificador confirmou que a comparação é `==` de dataclass,
  exata nos sete campos, e que nenhuma outra chamada de `run_greedy` no arquivo usa
  instância oficial. O mesmo padrão de asserção aplicado às 18 combinações oficiais
  falha em **18 de 18**, conforme a reprodução de F1-01. A cobertura atual afirma
  com `==` exato um invariante que só vale no caso de 4 unidades.
- **Veredito adversarial:** CONFIRMADO, classe `M2` mantida. A defesa de classe
  alta demais foi rejeitada, porque `M2` já é a mais branda disponível para lacuna
  de cobertura. O verificador registrou que este achado não é dupla contagem de
  F1-01: F1-01 é o defeito no código, F1-07 é a razão pela qual a suíte verde não
  o encontrou.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Estender o teste às instâncias oficiais, no mesmo commit
  da correção de F1-01, para que ele passe a discriminar.
- **Onda:** B, na onda do defeito associado F1-01, e não na Onda C.
- **Situação:** fechado no commit `5f2774a`, do pacote B6. O teste passou a cobrir
  as 18 combinações oficiais com três asserções por combinação: igualdade de
  dataclass sem tolerância, contagem de avaliações igual a `K(N-K)` e igualdade
  campo a campo por `float.hex()`. Como a correção de F1-01 torna a primeira
  asserção quase tautológica, o teste ganhou o caso negativo obrigatório, que
  injeta a permutação antiga por monkeypatch, prova por marcador de contagem de
  chamadas que o ponto de injeção foi percorrido, e confere que a autoconsistência
  se quebra em `N=20` com `K=3`. Um vigésimo caso cobre o ramo `K == N`, que nenhum
  teste exercitava.
- **Impressão digital:** zero, **como previsto**. Nenhuma das 37 diferenças
  observadas no pacote vem de `tests/`. Classe `M2` mantida.

#### F1-08. Código morto em `objective.py`

- **Frente:** F1.
- **Classe:** `M3`.
- **Premissa:** `docs/formulation.md` seção 20, linha 745: "A mesma formulação e a
  mesma função objetivo deverão ser utilizadas por PSO, Busca Tabu, ACO e pela
  heurística gulosa de referência"; `docs/experiments.md` seção 27, que lista
  auditoria entre os objetivos da organização dos resultados. **Fonte: normativa.**
- **Previsto:** o núcleo compartilhado expõe um caminho único de avaliação.
- **Código:** `src/metaheuristica/objective.py:35-37` (`_balance_component`) e
  `objective.py:46-51` (`_cut_component`).
- **Evidência:** `grep -rn "_balance_component\|_cut_component" src gpu/src tests
  experiments` devolve exatamente duas linhas, as duas de definição:
  `objective.py:35` e `objective.py:46`. Zero referências, as duas funções nunca
  executam. O contraste confere: `_cut_fraction`, definida em `objective.py:40`, é
  referenciada em `:51`, `:68` e `:69`; `_evaluate_labels`, definida em `:87`, é
  referenciada em `:198` e `:211`.
- **Veredito adversarial:** CONFIRMADO, classe `M3` mantida. O verificador ampliou
  a busca a `experiments/`, que o achado não incluía, com o mesmo resultado.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, removendo as duas funções. Consequência concreta a
  registrar para as ondas: `_cut_component` aparenta ser o cálculo do componente
  territorial, mas o cálculo vivo está embutido em `_evaluate_arrays`,
  `objective.py:115-118`. O risco é uma correção desta própria auditoria ser
  aplicada na função morta e a suíte continuar verde.
- **Onda:** C.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero, por remoção de código que
  nunca executa.

#### F1-09. O orçamento de avaliações não é uma unidade comparável entre ACO, PSO, Busca Tabu e guloso

- **Frente:** F1.
- **Classe:** `L1`.
- **Premissa:** tensão entre duas fontes normativas. `docs/experiments.md:245`,
  "A comparação principal será feita utilizando o mesmo orçamento de avaliações da
  função objetivo", e `:268-270`, "Todas as consultas à função objetivo consomem
  orçamento, incluindo inicialização, reparo, soluções repetidas e cache hits",
  com a justificativa em `:246`, "pois uma iteração possui custo e significado
  diferentes em PSO, TS e ACO". Contra `docs/formulation.md` seção 15, "somente a
  solução completa da formiga consome uma avaliação do orçamento". **Fonte:
  normativa nas duas pontas.** As três citações foram conferidas na fonte e
  existem literalmente.
- **Previsto:** duas coisas diferentes, segundo qual documento se lê.
- **Código:** segue a seção 15 e não a seção 8.
  `src/metaheuristica/evaluator.py:97-149` define o que debita;
  `src/metaheuristica/aco.py:119` e `aco.py:212` calculam custos parciais dos
  quatro componentes sem debitar; `src/metaheuristica/greedy.py:109` debita cada
  avaliação parcial. `OptimizationContext` (`optimizer.py:38-104`) expõe
  `evaluate` e `evaluate_provisional_for_repair` e não expõe
  `evaluate_partial_for_greedy`, consolidando a assimetria na fronteira.
- **Evidência:** o verificador reproduziu a afirmação que sustenta o achado, de que
  os dois caminhos parciais calculam o mesmo objeto matemático cobrado de formas
  diferentes: em `N=20, K=4`, 73 comparações, 59 idênticas bit a bit, 14
  divergentes, divergência relativa máxima `2,487e-16`, todas no último bit. O
  efeito medido é o da própria seção 29.1: ACO `(150,3)` em `6.389,35 s` e
  `(150,8)` em `10.971,45 s` contra máximos de `68,96 s` na Busca Tabu e
  `91,20 s` no PSO, fator entre 70 e 160 sob orçamento nominalmente igual.
- **Veredito adversarial:** CONFIRMADO, classe `L1` mantida, com reserva de leitura
  registrada. Não é promovido a defeito porque o código segue uma das duas
  prescrições documentais.
- **Divergência auditor / verificador:** dois itens. Primeiro, os sub-números não
  reproduziram literalmente: o relatório declara 140 comparações, `3,608e-16` e 11
  divergências no último bit; o verificador obteve 73, `2,487e-16` e 14, porque o
  caminho de construção sorteado não é o mesmo. A substância reproduz
  integralmente. Segundo, o verificador registra **contra** o achado uma leitura
  que o enfraquece: é possível ler os dois documentos como consistentes, com a
  seção 15 especificando o que conta como consulta ao objetivo, em vez de abrir
  exceção contra a seção 8. Sob essa leitura a palavra "incompatíveis" do relatório
  é forte demais. O achado sobrevive porque essa reserva não explica a assimetria
  **interna ao núcleo**: o mesmo objeto matemático é cobrado no guloso e não é
  cobrado no ACO.
- **Decisão:** registro apenas. A escolha entre corrigir a cobrança, reescrever a
  seção 8 ou declarar a limitação no relatório final é decisão de metodologia,
  fora da alçada da auditoria. O relatório final precisa declarar que a comparação
  estatística da seção 18 herda esse viés a favor do ACO.
- **Onda:** registro apenas.
- **Situação:** fechado sem ação de código.
- **Impressão digital:** pendente, sem alteração esperada por não haver correção.

### 3.2. Frente F2 - suíte de testes

Dezesseis achados, todos confirmados, nenhum refutado, nenhuma reclassificação. A
frente sondou 42 mutações sobre uma cópia integral do repositório: 26 mortas, 16
sobreviveram com a suíte integralmente verde em 254 aprovados. As 16 sobreviventes
mapeiam para 12 achados, porque cinco mutações independentes sustentam F2-05; os
outros quatro achados apoiam-se em evidência de outra natureza.

**Validação de método, e por que ela é indispensável aqui.** O verificador
reexecutou as 16 mutações em cópias construídas do zero, uma por mutação, e
obteve `254 passed` nas 16. Validou o próprio método por marcador, com um `raise`
incondicional no import produzindo 31 erros de coleta, e inspecionou por
`python -c` o símbolo mutado em cada uma das 16 cópias. Reexecutou também `M02`,
`M13`, `M27` e `M33`, as quatro mortas que sustentam o raciocínio de três
achados, e as quatro morreram exatamente pelos testes nomeados. Essa validação é
indispensável porque existe um padrão de comando de mutação que não carrega o
mutante, descrito na seção 6.

**Nota de fonte de premissa.** F2-03 e F2-14 citam, entre suas premissas, a
"restrição global do projeto" de comparação numérica exata, que é **metodologia
desta auditoria** e não regra do projeto. Nos dois casos, porém, existe âncora
normativa independente e suficiente: `docs/formulation.md` seções 13.3, 14 e 15 e
`docs/experiments.md` seção 12.1 fixam `1e-12` como limiar em quatro pontos
distintos do próprio projeto. Os dois achados sobrevivem sobre a âncora normativa
sozinha, e por isso não foram inflados pela confusão descrita na seção 6.

#### F2-01. A identidade de avaliações do PSO é verificada de forma vazia

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 16, "o PSO usa o reparo comum e
  contabiliza todas as avaliações provisórias"; `docs/experiments.md` seção 8,
  "Todas as consultas à função objetivo consomem orçamento, incluindo
  inicialização, reparo, soluções repetidas e cache hits", e seção 13. **Fonte:
  normativa.**
- **Previsto:** um teste que confirme `particles_evaluated + repair_evaluations`
  igual ao total de avaliações, com o reparo efetivamente ocorrendo.
- **Código:** `src/metaheuristica/pso.py:382-386` (`_verify_diagnostics`, chamado
  em `pso.py:260`, `:297`, `:336` e `:340`); único teste da identidade em
  `tests/test_pso.py:125`.
- **Evidência:** nos dois únicos cenários de PSO exercitados pela suíte,
  `repair_attempts`, `repairs_completed` e `repair_evaluations` são todos zero, e
  a asserção degenera em `100 + 0 == 100`. Mutação `M03`, corpo de
  `_verify_diagnostics` reduzido a `return None`: `254 passed`, reexecutado pelo
  verificador em cópia isolada em 125,95 s. Grep próprio do verificador confirma
  que `repair_evaluations` aparece em exatamente um arquivo de teste, a mesma
  linha citada. Em condição de campanha sobre `artesp_rmsp_20` com os parâmetros
  congelados, o reparo consome 992 de 2.000 avaliações em `K=5` e 1.756 de 2.000
  em `K=8`, isto é 87,8% do orçamento: o caminho sem cobertura é o que domina o
  consumo das 540 execuções de PSO do benchmark.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta. A defesa de que
  poderia haver cobertura em outro arquivo não se sustenta. O caminho de reparo é
  alcançável em produção, logo é lacuna de cobertura no sentido estrito e não ramo
  inalcançável.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Construir cenário de PSO em que o reparo efetivamente
  ocorra e asseverar a identidade com `repair_evaluations` maior que zero.
- **Onda:** C, isolada. Não há defeito de código associado.
- **Situação:** aberto.
- **Impressão digital:** pendente. Teste novo não altera resultado.

#### F2-02. Teste tautológico da tolerância de desempate do guloso

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 13.3, "Custos com diferença absoluta
  de até `1e-12` serão considerados empatados". **Fonte: normativa.**
- **Previsto:** um teste que fixe o valor `1e-12`, de modo que afrouxá-lo seja
  detectado.
- **Código:** `tests/test_greedy.py:79-87` calcula o custo de sonda como
  `1.0 + COST_TOLERANCE / 2.0`, a partir da própria constante que deveria
  verificar. A constante é `src/metaheuristica/greedy.py:16`, usada em
  `greedy.py:56` e `:58`.
- **Evidência:** mutação `M01`, `COST_TOLERANCE` de `1e-12` para `1e-6`:
  `254 passed`, reexecutado pelo verificador em 115,71 s. O verificador conferiu o
  texto do teste e classificou a tautologia como genuína e algébrica, não como
  coincidência de dados: qualquer valor positivo satisfaz a asserção por
  construção.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Trocar a sonda por literal independente da constante.
- **Onda:** C, isolada.
- **Situação:** aberto.
- **Impressão digital:** pendente.

#### F2-03. O afrouxamento de `metrics.COST_TOLERANCE` é detectado apenas por acidente

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seções 13.3, 14 e 15, que fixam `1e-12` para
  desempate do guloso, aspiração da Busca Tabu e amplitude nula da informação
  heurística do ACO; `docs/experiments.md` seção 12.1, que fixa `1e-12` para
  empate na seleção do tuning. **Fonte: normativa.** O relatório também invoca a
  restrição global de comparação exata, que é **metodologia da auditoria**; o
  achado não depende dela.
- **Previsto:** testes que fixem `1e-12` como limiar semântico, de modo que
  afrouxá-lo derrube os testes das regras que dele dependem.
- **Código:** `src/metaheuristica/metrics.py:21`, consumida em `metrics.py:160`,
  `:162`, `:327`, `tabu.py:157`, `:159`, `:199`, `:208`, `pso.py:151`, `:153`,
  `aco.py:218`, `:310`, `:400`, `:413`. Do lado dos testes,
  `tests/test_cross_validation.py:78-83` e `:155` usam a própria constante como
  tolerância, e os testes com literais (`tests/test_tabu.py:151-160` e
  `tests/test_pso.py:104-107`, com `5e-13`) só detectam o aperto, nunca o
  afrouxamento.
- **Evidência:** mutação `M02`, `1e-12` para `1e-6`, reexecutada pelo verificador
  em cópia isolada: `1 failed, 253 passed` em 100,35 s, e a única falha é
  `tests/test_aco.py::test_deposit_amount_handles_boundaries_and_tolerance`, que
  testa faixa de depósito de feromônio e não semântica de empate, caindo por
  acidente porque `aco.py:310` usa a mesma constante como folga de faixa.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Trocar as asserções tautológicas por literais e
  acrescentar teste negativo de afrouxamento nas regras de empate.
- **Onda:** C, isolada.
- **Situação:** aberto.
- **Impressão digital:** pendente.

#### F2-04. A verificação do congelamento não possui teste algum

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/experiments.md` seção 29, "Depois da aprovação do piloto, um
  manifesto registra hashes do código, automação, instâncias, configurações,
  dependências e artefatos. A execução do benchmark é recusada se qualquer item
  protegido ou o ambiente divergir"; seção 30, princípio de congelamento
  experimental. **Fonte: normativa.**
- **Previsto:** um teste que confirme que o verificador recusa a execução quando um
  arquivo protegido, um artefato do piloto, a quantidade de workers ou o ambiente
  divergem do manifesto.
- **Código:** `experiments/benchmark_freeze.py:103-133`
  (`verify_freeze_manifest`), `:77-101` (`generate_freeze_manifest`) e `:48-55`
  (`protected_paths`). O verificador implementa sete recusas
  (`benchmark_freeze.py:111`, `:113`, `:116`, `:123`, `:126`, `:128`, `:132`) e
  nenhum teste as exercita. `tests/test_benchmark_freeze.py` cobre somente
  `_hash_files`, e as duas chamadas ao verificador em
  `tests/test_benchmark_cli.py:11` e `:26` são anuladas por `monkeypatch` com
  retorno fixo.
- **Evidência:** mutação `E7`, `return manifest` inserido logo após a leitura do
  manifesto, transformando a barreira em função que aceita qualquer estado do
  repositório: `254 passed`. Reconfirmado pelo verificador em cópia isolada, com
  inspeção direta do símbolo mutado.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, com prioridade sobre os demais `M2`. É o portão que
  protege as 40 horas de campanha, e uma alteração de
  `src/metaheuristica/objective.py` no meio da campanha passaria sem recusa.
- **Onda:** B, na onda dos defeitos associados F6-02 e F6-03, que são os defeitos
  reais do mesmo mecanismo de congelamento. Ver a conexão 6 da seção 5.
- **Situação:** fechado com dezenove testes novos, nos commits do pacote B1.
  `tests/test_benchmark_freeze.py` passou a construir, por fixture, um repositório
  Git em miniatura com o escopo protegido inteiro, o manifesto montado pelos
  próprios utilitários do módulo e nenhum `monkeypatch` sobre o verificador. Um
  caso negativo por recusa: `schema_version` incompatível, `approved_workers`
  divergente, `protected_files` ausente do manifesto, arquivo protegido
  modificado, arquivo protegido removido, `pilot_artifacts` ausente do manifesto,
  artefato do piloto divergente e ambiente divergente, mais o controle positivo de
  que a verificação aceita o repositório que congelou. As recusas novas trazidas
  por F6-03 e F6-02 estão nos mesmos arquivos e são listadas nas entradas
  correspondentes. **Detecção da remoção da própria guarda:** com a mutação `E7`,
  `return manifest` inserido logo após a leitura do manifesto, a suíte passou de
  `299 passed` para `13 failed, 286 passed`, com as treze falhas concentradas nas
  recusas da verificação; a mutação foi revertida em seguida. É a mesma mutação
  que, no estado pré-B1 **deste ramo**, sobrevivia integralmente e devolvia
  `274 passed`. O número `254` citado no campo de evidência acima é a contagem do
  estado originalmente auditado, e não a deste ramo.
- **Impressão digital:** zero, conforme previsto. O pacote vive em `experiments/`
  e em `tests/`, fora do caminho científico executado pelo oráculo.

#### F2-05. A barreira de auditoria por lote sobrevive a cinco enfraquecimentos independentes

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/experiments.md` seção 29.2, "Depois que os 54 subgrupos de um
  lote recebem a rodada inicial, cada ID falho pode ser repetido uma única vez.
  Uma segunda falha bloqueia a campanha. O lote seguinte só é liberado após a
  barreira confirmar 324 resultados, 32.400 checkpoints, proveniência,
  congelamento, recursos, ausência de lacunas, duplicatas e temporários". **Fonte:
  normativa.**
- **Previsto:** testes que confirmem que a barreira recusa lote incompleto, lote
  com segunda falha, campanha com temporários, diário incompleto ou resumo de
  recursos reprovado, e que o lote `n` só é liberado com a barreira do `n-1`
  aprovada.
- **Código:** `experiments/benchmark_validation.py:72-115` (`validate_batch`), com
  guardas em `:73-76`, `:79`, `:80`, `:82` e `:91`. O único teste positivo,
  `tests/test_benchmark_validation.py:30-47`, roda com `select_benchmark`,
  `blocked_failures`, `_documents`, `_validate_operations` e `documents_to_frames`
  substituídos por dublês (`:37-41`), e apenas para `batch=1`, de modo que o
  encadeamento entre lotes nunca executa.
- **Evidência:** cinco mutações independentes, todas com `254 passed` e todas
  reexecutadas pelo verificador: `E2` (`_validate_operations` para `return []`),
  `E3` (`if batch > 1:` para `if False:`), `E4` (`len(documents) == 324` para
  `>= 1`), `E5` (guarda de segunda falha removida) e `E6` (guarda de temporários
  removida). Um lote com 200 de 324 execuções poderia ser assinado como aprovado e
  liberar o lote seguinte.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Testes da barreira com validadores reais, incluindo o
  encadeamento entre lotes, com um caso negativo por guarda.
- **Onda:** B, na onda dos defeitos associados F6-01, F6-04 e F6-05, que são
  defeitos reais da mesma barreira.
- **Situação:** fechado no commit do pacote B2, com dezesseis testes.
  `tests/test_benchmark_validation.py` passou a exercitar a barreira com
  validadores reais sobre um repositório de brinquedo versionado e congelado,
  construído em `tests/toy_repository.py`, com três instâncias sintéticas, dois
  lotes de 324 execuções reais cada e 32.400 checkpoints por lote, executados pelo
  caminho saturado. Nenhuma das cinco funções é substituída por dublê, com uma
  única exceção nomeada: o caso da contagem de 324 precisa de um seletor truncado,
  porque `select_benchmark` já recusa lote de tamanho diferente e sem o dublê a
  guarda seria inalcançável. Casos negativos: barreira anterior ausente, segunda
  falha, arquivos temporários, artefato estranho, resultado ausente, contagem menor
  que 324, resultado não oficial, proveniência não uniforme, diário incompleto,
  diário ausente, operação sem sessão, resumo de recursos reprovado, worktree suja
  e congelamento divergente. O encadeamento entre lotes é exercitado nos dois
  sentidos: o lote 2 é recusado sem a barreira do lote 1 e aprovado depois dela,
  com os 324 resultados reais do lote 2.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os 42
  cenários devolveu "impressão digital idêntica" com saída 0, antes e depois do
  lote. O pacote vive em `experiments/`, `.gitignore`, `README.md`,
  `docs/` e `tests/`, fora do caminho científico executado pelo oráculo.

#### F2-06. O reinício da Busca Tabu não tem a limpeza da memória verificada

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 14, "Depois de `n_stag` movimentos
  aceitos sem melhora global, a busca gera outra solução aleatória balanceada,
  limpa a memória e preserva o incumbente. O mesmo reinício ocorre quando toda a
  amostra está tabu sem aspiração". **Fonte: normativa.**
- **Previsto:** um teste que confirme que o reinício limpa a memória tabu, e não
  apenas que houve reinício.
- **Código:** `src/metaheuristica/tabu.py:232-250` (`evaluate_restart`), em
  especial `tabu.py:245` (`memory.clear()`); ramos chamadores em `tabu.py:257`,
  `:301` e `:318`. `tests/test_tabu.py:208-217` verifica apenas
  `diagnostics["restarts"] > 0` e a identidade
  `iterations_completed == accepted_moves + restarts`.
- **Evidência:** mutação `M17`, `memory.clear()` removido de `evaluate_restart`:
  `254 passed`, reconfirmado pelo verificador com inspeção do símbolo mutado. A
  sonda `M33`, com `raise` no ramo de amostra integralmente tabu
  (`tabu.py:300`), disparou em
  `tests/test_cross_validation.py::test_tiny_optimum_and_common_contract[0-tabu]`,
  provando que o ramo é executado sem que nenhuma das suas três consequências
  declaradas seja asseverada.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta. O verificador
  registrou que `M17` não tem equivalente entre os quatro mutantes de `tabu.py` da
  frente F5, logo não há dupla contagem.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Observar o estado da memória através de um reinício.
- **Onda:** B, junto do achado 5 da frente F5, que é o defeito latente da mesma
  região de `tabu.py`. Ver a conexão 5 da seção 5.
- **Situação:** fechado com um teste novo, no commit do pacote B12, sem alteração de
  `src/`. A memória passa a ser observada **através** do reinício, e não apenas pelo
  lado dos contadores: `clear` é instrumentada, o conteúdo é lido antes e depois, e
  para cada entrada viva a consulta `is_tabu` com o contador que **antes** responderia
  "tabu", isto é a expiração menos um, passa a responder "não tabu". O teste exige
  que ao menos um reinício tenha encontrado a memória povoada, de modo que ele não
  passa por vacuidade se o cenário deixar de produzir memória viva, e confere que o
  número de limpezas observadas iguala o número de reinícios publicado. Sob a remoção
  de `memory.clear()`, que é a mutação `M17` do registro, a instrumentação nunca é
  chamada e o teste falha.
  **Passo G.** Classe prevista `M2`; classe observada `M2`; a observação **bate** com
  a previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, dentro do zero conferido no
  subconjunto `tabu:*` e no conjunto completo dos 42 cenários no Passo F do pacote
  B12. A alteração é restrita a `tests/test_tabu.py`. **Passo G.** Diff previsto
  zero; diff observado zero; a observação **bate** com a previsão.

#### F2-07. A aceitação por aspiração nunca é exercitada em execução integrada

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 14, "A aspiração libera essa reversão
  somente quando seu custo melhora o melhor global por mais de `1e-12`", repetida
  na seção 14 de `docs/experiments.md`. **Fonte: normativa.**
- **Previsto:** evidência de que a liberação de uma reversão tabu por aspiração
  ocorre e produz o efeito declarado dentro de uma execução completa.
- **Código:** `src/metaheuristica/tabu.py:311-312`, alimentado por
  `tabu.py:202-209` (`_aspiration_applies`) e `tabu.py:61-62` (`admissible`). O
  diagnóstico `aspiration_acceptances` não é asseverado em arquivo algum.
- **Evidência:** sonda `M34`, com
  `raise ConfigurationError("SONDA: aceitacao por aspiracao alcancada")` na entrada
  do ramo: `254 passed`, isto é em nenhuma execução de Busca Tabu da suíte,
  incluindo os 18 cenários ARTESP de `test_artesp_pilot_all_k`, um candidato tabu
  foi aceito por aspiração. A regra em si está protegida em nível de unidade: a
  mutação `M13` foi morta por
  `test_aspiration_requires_strict_improvement_beyond_tolerance`, reconfirmado
  pelo verificador.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta. A sonda é conclusiva
  sobre a não execução do ramo.
- **Divergência auditor / verificador:** nenhuma. A confiança declarada pelo
  auditor já era média-alta, com a avaliação de impacto marcada como inferencial.
- **Decisão:** corrigir. Construir cenário integrado em que a aspiração dispare e
  asseverar `aspiration_acceptances`.
- **Onda:** B, junto do achado 6 da frente F5, que aponta a mesma fronteira sem
  cobertura pelo lado do algoritmo.
- **Situação:** fechado com um teste novo de execução **integrada**, no commit do
  pacote B12, sem alteração de `src/`. A sonda `M34` do registro mostrou que nenhuma
  execução de Busca Tabu da suíte, incluindo os dezoito cenários ARTESP do piloto,
  aceitava um candidato tabu por aspiração, e que `aspiration_acceptances` não era
  asseverado em arquivo algum. O teste novo roda `run_tabu` sobre a instância real
  `artesp_rmsp_20` com `K=5`, seed 1, orçamento 600 e `tabu_tenure=40` contra
  `neighborhood_size=5`: o prazo longo somado à amostra estreita torna a aspiração
  frequente, e o diagnóstico é asseverado em **7** aceitações, com o valor fixado e
  não apenas exigido positivo. A configuração foi encontrada por varredura no
  scratchpad, fora do repositório, e a seed `20260819`, reservada à impressão
  digital, não foi usada.
  **Passo G.** Classe prevista `M2`; classe observada `M2`; a observação **bate** com
  a previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, dentro do zero conferido no
  subconjunto `tabu:*` e no conjunto completo dos 42 cenários no Passo F do pacote
  B12. A alteração é restrita a `tests/test_tabu.py`. **Passo G.** Diff previsto
  zero; diff observado zero; a observação **bate** com a previsão.

#### F2-08. A manutenção dos `K` lotes nos vetores de totais não é testada

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 13.2, "O equilíbrio manterá os `K`
  lotes nos vetores de totais, enquanto os componentes territoriais e funcionais
  considerarão somente relações cujas duas unidades já tenham sido processadas";
  mesma regra nas seções 10 e 15. **Fonte: normativa.**
- **Previsto:** um teste que confirme que um lote ainda vazio continua entrando no
  cálculo do coeficiente de variação com total zero.
- **Código:** `src/metaheuristica/objective.py:120-121`, as duas chamadas
  `np.bincount(labels, weights=..., minlength=k)`, e `objective.py:36`. O
  comportamento correto está implementado, mas nenhum teste o fixa: os testes de
  avaliação parcial (`tests/test_objective.py:81-105`) e de reparo usam
  configurações em que o vetor tem naturalmente comprimento `K`.
- **Evidência:** mutação `M35`, `minlength=k` removido das duas chamadas:
  `254 passed`, com ausência do argumento confirmada por inspeção direta nas duas
  linhas alvo. Com essa regressão o custo provisório do reparo do PSO passaria a
  subestimar o desequilíbrio de todo lote vazio de rótulo alto, escolhendo doadores
  diferentes; como o reparo consome até 87,8% do orçamento de PSO em `K=8`, a
  trajetória inteira do PSO mudaria com a suíte verde.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Teste com lote vazio de rótulo alto.
- **Onda:** C, isolada.
- **Situação:** aberto.
- **Impressão digital:** pendente.

#### F2-09. O uso de um único instantâneo do melhor global por iteração do PSO não é testado

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 16, "cada iteração usa um único
  snapshot do melhor global". **Fonte: normativa.**
- **Previsto:** um teste que distinga a atualização síncrona da assíncrona.
- **Código:** `src/metaheuristica/pso.py:275-279`, `gbest_snapshot =
  gbest.position.copy()` seguido da construção de todos os `trials` da iteração. A
  regra está implementada, mas `tests/test_pso.py` não tem teste algum sobre a
  atualização de velocidade dentro do laço principal.
- **Evidência:** mutação `M36`, instantâneo removido e `gbest.position` passado
  diretamente a `_trial_state`, tornando a atualização assíncrona: `254 passed`,
  com ausência de `gbest_snapshot` confirmada por inspeção. Os testes de
  reprodutibilidade (`tests/test_pso.py:129-137`) não protegem contra isso, porque
  comparam duas execuções do mesmo código mutado entre si.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Teste que compare trajetórias síncrona e assíncrona sobre
  população em que o melhor global muda no meio da iteração.
- **Onda:** A, junto de A1, A10 e F2-10, porque toca a mesma região de `pso.py` e a
  correção de A1 precisa dessa cobertura nova para não reintroduzir a assimetria.
- **Situação:** fechado com dois testes novos, no commit do pacote A1, e com uma
  ressalva sobre a mutação citada no campo de evidência.
  `test_trial_state_depends_on_which_global_best_it_receives` fixa que a tentativa
  muda quando muda o melhor global recebido, sem o que o instantâneo não teria
  efeito algum, e `test_pso_uses_a_single_global_best_snapshot_per_iteration` espia
  `_trial_state` ao longo de `run_pso` e assevera que todas as partículas de uma
  mesma iteração recebem o mesmo vetor, exigindo ainda que exista iteração em que o
  melhor global mude por causa de uma partícula que não é a última, sem o que o
  cenário não discriminaria. **Ressalva de evidência:** a mutação `M36`, que remove
  `gbest_snapshot` e passa `gbest.position` à mesma list comprehension, é **inerte**
  sob a estrutura atual do laço, porque todas as tentativas da iteração são
  construídas antes de qualquer avaliação; conferido por medição, com
  `reproducible_data()` idêntico entre a árvore e o mutante, e a suíte inteira
  passando contra ele. O mutante que discrimina é o de laço intercalado, que calcula
  a tentativa de cada partícula logo antes da avaliação dela; rodado fora da árvore,
  com `pytest -o "pythonpath=..."` e canário de marcador que confirma qual árvore foi
  carregada, o teste novo é o único da suíte do PSO que falha. Os dois testes passam
  antes e depois da correção de A1, porque o comportamento já estava correto; a
  falsificação deles é a execução contra o mutante, não uma falha prévia na árvore.
- **Impressão digital:** sem efeito próprio, porque a alteração é restrita a
  `tests/`.

#### F2-10. A limitação de velocidade durante a busca do PSO não é testada

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 16 e `docs/experiments.md` seção 13,
  "velocidade limitada a `[-0.5,0.5]` e posição limitada a `[0,1]`". **Fonte:
  normativa.**
- **Previsto:** um teste que confirme o recorte da velocidade calculada pela
  fórmula de atualização, não apenas o da velocidade sorteada na inicialização.
- **Código:** `src/metaheuristica/pso.py:186`,
  `np.clip(raw_velocity, -VELOCITY_LIMIT, VELOCITY_LIMIT)` em `_trial_state`, e o
  contador `velocity_clips` publicado em `pso.py:110`.
  `tests/test_pso.py:83` verifica a faixa apenas das velocidades iniciais, e
  `velocity_clips` não é asseverado em arquivo algum.
- **Evidência:** mutação `M37`, recorte substituído por `raw_velocity` durante a
  busca: `254 passed`, com ausência do `np.clip` confirmada por inspeção. A
  mutação `M27`, que eleva `VELOCITY_LIMIT` de `0.5` para `5.0`, é morta por
  `test_initial_population_is_balanced_viable_and_reproducible`, o que protege a
  constante mas não o ponto de aplicação; o verificador reexecutou `M27` e ela
  morre com velocidades observadas de até `4.19`, fora de `[-0.5, 0.5]`, o que só
  ocorre com o limite mutado.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, no mesmo commit de A1. Este é o teste que faltava para
  que a divergência de A1 tivesse sido detectada pela suíte.
- **Onda:** A, junto de A1, e não na Onda C. É a cobertura do único `D1` da
  auditoria.
- **Situação:** fechado com dois testes novos, no commit do pacote A1.
  `test_trial_state_limits_the_step_during_the_search` usa o cenário discriminante
  do verificador, `x=0,10` com `pbest=gbest=1,0`, `v=0,5`, `r1=r2=1` e pesos
  congelados, e assevera o passo por coordenada, a faixa da velocidade guardada,
  `velocity_clips`, que não era asseverado em arquivo algum, e o rótulo
  decodificado, 3 sob a ordem prescrita contra 4 sob a defeituosa.
  `test_search_loop_keeps_every_coordinate_step_within_the_velocity_limit` espia
  `_trial_state` ao longo de uma execução inteira de `run_pso` e cobre a limitação
  **durante a busca**, que era a lacuna do achado. Os dois falham antes da
  correção, com passo máximo 0,9 e 0,9529 respectivamente.
- **Impressão digital:** sem efeito próprio, porque a alteração é restrita a
  `tests/`.

#### F2-11. A igualdade entre avaliação final e último checkpoint não tem teste negativo

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/experiments.md` seção 9 e seção 29, "O validador exige
  orçamento exato, 100 checkpoints, incumbente não crescente, solução canônica e
  viável, reavaliação pela função objetivo comum". **Fonte: normativa.**
- **Previsto:** um teste que construa um `OptimizationResult` cujo último
  checkpoint divirja da avaliação final e confirme a recusa.
- **Código:** `src/metaheuristica/metrics.py:276-278` e `:325-348`. Há testes
  negativos para contagem errada de checkpoints (`tests/test_metrics.py:131-149`)
  e para diagnósticos não serializáveis (`:122-128`), mas nenhum para divergência
  entre avaliação final e último checkpoint.
- **Evidência:** mutação `M05`, `_same_evaluation` sempre verdadeiro:
  `254 passed`, com a redução a `return True` confirmada por inspeção. A gravidade
  é reduzida por controle equivalente do lado do teste em
  `tests/test_cross_validation.py:136`, sobre execuções reais. O auditor registrou
  também que `metrics.py:275`, "motivo de parada não suportado", é inalcançável
  enquanto `TerminationReason` tiver um único membro, e portanto não pode receber
  teste.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta.
- **Divergência auditor / verificador:** nenhuma. A confiança do auditor já era
  média quanto ao impacto, pelo controle equivalente.
- **Decisão:** corrigir, no mesmo commit de F1-02, que é o defeito da mesma
  guarda.
- **Onda:** B, na onda de F1-02.
- **Situação:** fechado com dois testes novos em `tests/test_metrics.py`, no commit
  do pacote B7, junto de F1-02, que é o defeito da mesma guarda. O caso negativo
  constrói o cenário do verificador, com `algorithm` igual a `aco_gpu`, checkpoint
  100 em `0,25` e avaliação final em `0,25 + 9e-13`, e assevera a recusa pela
  mensagem "avaliação final diverge do último checkpoint". O caso positivo confere
  que valores iguais bit a bit em objetos distintos continuam aceitos, de modo que
  a guarda não passou a exigir identidade de objeto, que o caminho GPU não tem.
  **Poder discriminante:** o caso negativo foi executado sob a forma anterior e
  falhou com "DID NOT RAISE", porque a tolerância de `1e-12` absorvia os `9e-13`.
  **Passo G.** Classe prevista `M2`; classe observada `M2`; a observação **bate**
  com a previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, dentro do zero conferido no
  conjunto completo dos 42 cenários no Passo F do pacote B7. A alteração deste
  achado é restrita a `tests/` e não tem efeito próprio sobre o caminho científico.
  **Passo G.** Diff previsto zero; diff observado zero; a observação **bate** com a
  previsão.

#### F2-12. 177 dos 231 sítios de `ConfigurationError` não são acionados por teste algum

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** as mensagens em causa materializam regras de
  `docs/experiments.md` seções 8, 9, 12.1, 28.1, 29 e 29.2, e de
  `docs/formulation.md` seções 4, 10, 13, 14, 15 e 16. **Fonte: normativa quanto
  às regras; a exigência de um teste por sítio é metodologia da auditoria**, vinda
  da lista de verificações obrigatórias do dossiê da frente.
- **Previsto:** que cada recusa esperada seja demonstrada por teste.
- **Código:** medição exaustiva sobre `src/metaheuristica/` e `experiments/`. 80
  sítios em `src`, 49 nunca acionados; 151 em `experiments`, 128 nunca acionados.
  Concentrações em `experiments/config.py` 23, `analyze_tuning.py` 14,
  `storage.py` 13, `run_benchmark.py` 10, `benchmark_freeze.py` 9.
- **Evidência:** o verificador reproduziu a contagem de forma independente,
  instrumentando `ConfigurationError.__init__` para gravar `arquivo:linha` do
  chamador via `sys._getframe(1)` e comparando com
  `grep -rn "raise ConfigurationError" src/ experiments/`: **231 sítios, 177 nunca
  acionados, 49 em `src` e 128 em `experiments`, idêntico ao relatório**. Sem
  amostragem.
- **Veredito adversarial:** CONFIRMADO, recontagem própria idêntica. Classe `M2`
  correta.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir parcialmente, por triagem. Cobrir os sítios que
  materializam regra normativa e governam a expansão determinística dos 1.620
  cenários, em especial as 23 recusas de TOML estrito de `experiments/config.py`.
  Cobrir 177 sítios indiscriminadamente não é decisão que a auditoria recomende.
- **Onda:** C, isolada, com escopo reduzido pela triagem.
- **Situação:** aberto.
- **Impressão digital:** pendente.

#### F2-13. O afrouxamento da tolerância de empate do tuning não é detectado

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/experiments.md` seção 12.1, "A seleção é automática e
  separada por algoritmo: menor média do custo, empate até `1e-12` resolvido por
  menor desvio-padrão amostral (`ddof=1`), depois menor tempo médio e, por fim,
  menor tupla lexicográfica dos hiperparâmetros". **Fonte: normativa.**
- **Previsto:** um teste que fixe `1e-12` como limiar de empate na seleção.
- **Código:** `experiments/tuning_analysis.py:19` (`TOLERANCE = 1e-12`), usada em
  `:46` e republicada em `experiments/analyze_tuning.py:122`. O teste de desempate
  em `tests/test_tuning_analysis.py:147-161` usa o literal `1.0 + 5e-13`, cujo
  resultado é o mesmo para `1e-12` e para `1e-6`.
- **Evidência:** mutação `E1`, `TOLERANCE` de `1e-12` para `1e-6`: `254 passed`,
  com `TOLERANCE = 1e-06` confirmado carregado por inspeção direta.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Teste que force um par de médias separadas por menos que
  `1e-6` e mais que `1e-12`.
- **Onda:** B, na onda do achado 2 da frente F9, que é o defeito latente da mesma
  tolerância.
- **Situação:** fechado com dois testes novos em `tests/test_tuning_analysis.py`, no
  commit do pacote B8, junto de F9-2. O primeiro usa um par de médias separadas por
  `1e-9`, isto é mais que `1e-12` e menos que `1e-6`, com o desvio apontando para a
  outra configuração, de modo que trocar a tolerância do custo por `1e-6` inverte o
  vencedor. O segundo fixa a tolerância zero do tempo, com duas médias distando
  `1e-13`, que sob a tolerância antiga empatavam e caíam no desempate lexicográfico.
  **Poder discriminante, verificado por mutação na própria árvore de trabalho**, sem
  `PYTHONPATH` e portanto sem o risco de o mutante não ser carregado: com
  `TOLERANCES["mean_cost"]` em `1e-6` o primeiro teste falha, e com
  `TOLERANCES["mean_runtime_seconds"]` de volta em `1e-12` o segundo falha. A árvore
  foi restaurada em seguida e conferida. A mutação `E1` do registro, que devolvia
  `254 passed`, está morta.
  **Passo G.** Classe prevista `M2`; classe observada `M2`; a observação **bate** com
  a previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, dentro do zero conferido no
  conjunto completo dos 42 cenários no Passo F do pacote B8. A alteração deste
  achado é restrita a `tests/` e não tem efeito próprio sobre o caminho científico.
  **Passo G.** Diff previsto zero; diff observado zero; a observação **bate** com a
  previsão.

#### F2-14. Quatro asserções usam tolerância relativa de `1e-6`

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 15, informação heurística normalizada
  exatamente em `[1, 2]`, com `aco.py:254` exigindo que as probabilidades somem 1
  com `atol=1e-12`. **Fonte: normativa.** A restrição global de comparação exata
  também é citada pelo relatório e é **metodologia da auditoria**; o achado não
  depende dela, porque a guarda de `1e-12` está no próprio código do projeto.
- **Previsto:** que a normalização fosse verificada com a mesma exigência de
  `1e-12` aplicada pelo código.
- **Código:** `tests/test_aco.py:109`, `:110`, `:137` e `:147`, todas na forma
  `== pytest.approx(valor)` sem argumentos de tolerância, o que aplica o padrão
  `rel=1e-6`. Em particular `tests/test_aco.py:147` verifica com `1e-6` a mesma
  soma que `aco.py:254` verifica com `1e-12`, isto é o teste é mais frouxo que a
  guarda do próprio código.
- **Evidência:** o verificador consultou o comportamento real de `pytest.approx`
  na versão instalada, 9.1.1, e leu os quatro pontos citados: o padrão é de fato
  `rel=1e-6`, seis ordens de grandeza acima do exigido. Um erro relativo de `1e-7`
  na normalização de `eta` passaria pelo teste e pela guarda `aco.py:221`.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta.
- **Divergência auditor / verificador:** nenhuma. A confiança do auditor já era
  média quanto à materialidade, porque a fórmula atual é exata e o desvio
  precisaria ser introduzido por regressão futura.
- **Decisão:** corrigir. Fixar `abs=1e-12` nas quatro asserções.
- **Onda:** B, junto de F4-5, que é o outro achado de tolerância em
  `tests/test_aco.py` e que a correção de F4-1 obriga a mover no mesmo commit.
- **Situação:** fechado com a correção das quatro asserções de `tests/test_aco.py`, no
  commit `d297377`, do pacote B5. As quatro asserções que
  estavam em `tests/test_aco.py:109`, `:110`, `:137` e `:147` na forma
  `== pytest.approx(valor)` sem argumentos passaram a `abs=1e-12` e, depois da
  movimentação que a correção de F4-1 obrigou, vivem em `tests/test_aco.py:110`, `:111`,
  `:300` e `:310`. A quarta delas verifica agora com `1e-12` a mesma soma de
  probabilidades que o código do projeto já verificava com `1e-12`, o que elimina o caso
  em que o teste era mais frouxo que a guarda do próprio código.
  **Poder discriminante:** o próprio teste é o oráculo. Sob a forma anterior, `rel=1e-6`,
  um erro relativo de `1e-7` na normalização de `eta` passaria; sob `abs=1e-12` ele não
  passa. **Nota metodológica:** a restrição global de comparação exata é metodologia da
  auditoria e não regra do projeto, e o achado nunca dependeu dela; o `1e-12` fixado aqui
  é o do código do projeto, e não deve ser confundido com o contrato de conformidade da
  GPU, que também usa `1e-12` de tolerância e **não** exige igualdade exata.
  **Passo G.** Classe prevista `M2`; classe observada `M2`; a observação **bate** com a
  previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, dentro do zero conferido nos 42
  cenários no Passo F de `d297377`. A alteração é restrita a `tests/test_aco.py` e não
  tem efeito próprio sobre o caminho científico. **Passo G.** Diff previsto zero; diff
  observado zero; a observação **bate** com a previsão.

#### F2-15. O oráculo declarado do `tiny_manual` é decorativo e as instâncias congeladas não estão fixadas ao gerador

- **Frente:** F2.
- **Classe:** `M2`.
- **Premissa:** `docs/experiments.md` seção 2.3, "A instância sintética
  `tiny_manual`, com quatro unidades e dois lotes, possui solução ótima canônica
  `[0, 0, 1, 1]` e custo zero. Ela é usada somente para verificação manual e
  testes". **Fonte: normativa.**
- **Previsto:** um oráculo independente, e coerência entre o oráculo declarado no
  arquivo de dados e o oráculo usado pelos testes.
- **Código:** `data/instances/tiny_manual.json:47-62` (bloco `expected_optimum`);
  `tests/test_generate_instances.py:60-71` e `:74-89`. O verificador leu
  `load_tiny_instance` em `src/metaheuristica/instances.py:90-114` linha a linha e
  confirmou que a função **nunca** acessa a chave `expected_optimum`. O único
  teste que a lê o faz sobre uma cópia regerada em `tmp_path`, nunca sobre o
  arquivo versionado.
- **Evidência:** mutação `M38`, `data/instances/tiny_manual.json` versionado
  alterado com `cost` de `0.0` para `0.5` e `canonical_solution` de `[0,0,1,1]`
  para `[0,1,0,1]`: `254 passed`, reexecutado pelo verificador em 114,31 s. O
  mesmo mecanismo vale para `artesp_rmsp_20.json`, `artesp_rmsp_60.json`,
  `artesp_rmsp_150.json`, `artesp_rmsp_150_units.parquet` e
  `artesp_rmsp_150_pair_metrics.parquet`: constam de `FIXED_PROTECTED` em
  `experiments/benchmark_freeze.py:32-38`, mas o verificador que compara seus
  hashes é ele próprio sem teste, que é F2-04. Não existe hoje linha de defesa
  testada entre o gerador e os dados congelados.
- **Veredito adversarial:** CONFIRMADO, classe `M2` correta. A hipótese de que o
  oráculo fosse circular foi testada e **descartada** pelo próprio auditor, via
  mutação `M06`, morta por dois oráculos manuais independentes. O achado não é
  sobre circularidade, e sim sobre o arquivo de dados versionado ficar sem
  fixação.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Fixar os arquivos versionados por hash conhecido, ou
  consumir `expected_optimum` do arquivo versionado num teste de núcleo.
- **Onda:** B, junto de F6-08, que é o defeito real do identificador por conteúdo
  que não cobre os dois Parquet. Ver a conexão 7 da seção 5.
- **Situação:** aberto.
- **Impressão digital:** pendente.

#### F2-16. Três testes dependem de pacote de dados ignorado pelo Git

- **Frente:** F2.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 2.3, "Para tornar o benchmark
  executável sem acesso ao pacote-fonte ignorado pelo Git, `data/instances/`
  também contém os atributos das 150 unidades e uma tabela esparsa"; seção 28,
  "Antes da execução final, o repositório deverá permitir reproduzir os
  experimentos por comandos explícitos". **Fonte: normativa.**
- **Previsto:** que a reprodução dependa apenas do que está versionado.
- **Código:** `tests/test_generate_instances.py:13`
  (`SOURCE_DIR = PROJECT_ROOT / "_temp" / "dados_artesp"`), usado em `:21`, `:61`
  e `:77`; `.gitignore:16` ignora `_temp/`.
- **Evidência:** o verificador reproduziu diretamente. Cópia do repositório sem
  `_temp/`: **3 failed, 251 passed**, com as três falhas exatamente
  `test_generated_instances_are_nested_and_spatially_distributed`,
  `test_tiny_instance_has_manual_optimum_and_geopackage` e
  `test_generation_is_reproducible`, todas por
  `FileNotFoundError: .../_temp/dados_artesp/units.parquet`. Com `_temp/` de volta,
  26 MB confirmados ignorados por `.gitignore:16`, a mesma suíte dá
  `254 passed in 99.21s`.
- **Veredito adversarial:** CONFIRMADO, reproduzido diretamente. Classe `D3`
  correta: não é mutação de regra sobrevivendo, é dependência de ambiente não
  declarada que quebra a promessa de reprodutibilidade da seção 28, o que é
  distinto de `M2`.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir. Marcar os três testes como opcionais por presença do
  pacote-fonte, ou derivar os fixtures do que está versionado. Colide com o
  critério de saída da B13 e precisa entrar antes dele.
- **Onda:** B, com prioridade.
- **Situação:** aberto.
- **Impressão digital:** pendente. Alteração restrita a `tests/`, sem efeito em
  resultado de campanha.

### 3.3. Frente F3 - PSO com Random Keys

Dez achados. Um refutado integralmente (A2, classe `R`, no Apêndice A), um
reclassificado de `D3` para `L1` (A9), dois com lacuna declarada (A7 e A8), e o
único `D1` da auditoria inteira (A1). Os dois achados originalmente `D1`
receberam verificação dedicada, além da verificação de frente.

**Portão de reprodução cumprido nas duas verificações.** O baseline limpo reproduz
as dez linhas oficiais de `results/tables/tuning_runs.parquet` com média
`0,274437411389966` idêntica à oficial, `float.hex()` idênticos (seed 0
`0x1.3a4b3ed0e6288p-2`, seed 1 `0x1.3d5b8a43b7e2cp-2`, seed 2
`0x1.31a7012611722p-2`), `position_clips` médio 403.296,6 e `velocity_clips` médio
249.052,2. A instrumentação foi verificada como inerte.

**Conclusão de frente, verificada.** O fator 2,17x do PSO é **propriedade** da
adaptação por Random Keys a este problema de particionamento, não defeito de
implementação. As três pernas do argumento se sustentam. A causa medida é a
granularidade do encoding: as trocas de rótulo por candidato escalam como
`K*|dx|`, com custo em forma de U e ótimo interior, de modo que nenhum limite de
velocidade entrega localidade e alcance ao mesmo tempo. Corrigidos A1 e A2 juntos,
que é o PSO clássico conformante, o custo médio vai de 0,274437 para 0,276688,
isto é 2,19x em vez de 2,17x, e nenhuma correção isolada produz efeito
distinguível de ruído, com `|t| <= 0,43`, enquanto a lacuna até a Busca Tabu vale
13,1 erros padrão. Duas ressalvas obrigatórias do verificador, a carregar para o
relatório final: a perna 1 tem erro factual pontual, porque a configuração
vencedora tem a **quarta** menor fração de reparo da grade e não a segunda; e a
"forma de U" mistura **três condições experimentais diferentes** numa única curva,
uma série monótona controlada mais o código atual e a busca aleatória pura
emendados nas pontas, logo o ótimo interior é propriedade do **conjunto** e não de
uma série única, e precisa de nota explícita antes de qualquer reuso.

**Achado colateral de peso, reproduzido de forma independente.** O guloso
determinístico faz 0,268290 com 275 avaliações, melhor que a média do PSO com
60.000 avaliações e 218 vezes mais barato.

#### A1. O limite de velocidade não limita o passo

- **Frente:** F3.
- **Classe:** `D1`. O único da auditoria.
- **Premissa:** `docs/formulation.md` seção 16, "A velocidade segue a fórmula
  clássica com inércia e componentes cognitivo e social. As posições são limitadas
  a `[0,1]`, as velocidades a `[-0.5,0.5]`"; `docs/experiments.md` seção 13,
  "velocidade limitada a `[-0.5,0.5]` e posição limitada a `[0,1]`". **Fonte:
  normativa.** A divergência provada não é contra a letra da seção, que o estado
  guardado satisfaz, e sim contra o significado consagrado de `v_max` na fórmula
  clássica que a própria seção invoca: uma saturação de velocidade posterior à
  atualização de posição não limita passo algum.
- **Previsto:** `v <- clamp(w*v + c1*r1*(p-x) + c2*r2*(g-x), -0.5, 0.5)` e em
  seguida `x <- clamp(x + v, 0, 1)`, de modo que o limite de `0,5` borne o
  deslocamento por coordenada em meio domínio.
- **Código:** `src/metaheuristica/pso.py:172-189`, com o defeito na ordem entre a
  linha 177 e a linha 186. A linha 177 calcula
  `raw_position = particle.position + raw_velocity` usando a velocidade **bruta**,
  e só a linha 186 satura a velocidade que será guardada. O limite portanto só
  afeta o valor herdado pelo termo de inércia da iteração seguinte.
- **Evidência (números do verificador):** o deslocamento efetivo por coordenada é
  bornado por **1,0 por construção**, porque `pso.py:185` satura a posição em
  `[0,1]` e as duas posições pertencem a `[0,1]`. Máximo do passo de tentativa
  medido **exatamente 1,0** nas dez seeds, o dobro do limite prescrito, com
  **1.886.548 de 34.380.000** atualizações de coordenada acima de 0,5, isto é
  **5,49%**, variando de 0,77% (seed 2) a 12,16% (seed 1). Máximo de
  `|raw_velocity|` observado 3,083. Sob a ordem corrigida: **zero** violações e
  máximo exatamente 0,5. Cenário válido, construído pelo verificador: `x=0,10`,
  `pbest=gbest=1,0`, `v=0,5`, `r1=r2=1`, pesos congelados, dá `raw_velocity=3,35`,
  o código produz posição `1,0`, passo **0,9** e rótulo **4**, enquanto a ordem
  prescrita produz `v=0,5`, posição `0,6`, passo `0,5` e rótulo **3**. Com `x=0,0`
  o passo chega a `1,0` e o rótulo vai a 4 contra 2. Efeito em resultado: a
  correção muda o `float.hex()` em **10 de 10** seeds e leva a média de 0,274437
  para **0,280569**, com `delta = +0,006131`, `sd = 0,052919`, `t = +0,37` em 9
  graus de liberdade, isto é **piora** e o efeito é indistinguível de ruído.
- **Veredito adversarial:** CONFIRMADO como `D1`, com três refutações internas. A
  classe é `D1` por critério objetivo e não por leitura de texto: corrigir a ordem
  altera todos os dez resultados oficiais e invalida o congelamento do tuning do
  PSO. A defesa do "documento impreciso" é parcialmente válida e fica registrada
  como ressalva, não como classe alternativa: a seção 16 não escreve a ordem das
  operações e as velocidades armazenadas estão sempre em `[-0.5,0.5]`.
- **Divergência auditor / verificador:** três itens, todos de magnitude ou de
  cenário. Primeiro, **o limite de 3,7 está errado**, e o erro é qualitativo: 3,7
  borna a velocidade bruta, não o passo; o passo é bornado por **1,0**. A frase do
  relatório "o limite não borna deslocamento algum" é falsa. Segundo, **cai o
  corolário das 18,5 células**: o teto real é **5 células** de largura `1/K = 0,2`,
  isto é salto máximo de **4 rótulos**. Terceiro, **o cenário concreto publicado
  não demonstra o defeito**: `x=0,50` produz passo 0,5 e rótulo 4 sob as **duas**
  ordens, isto é é caso em conformidade; ele foi substituído pelo cenário `x=0,10`
  registrado no campo de evidência. A onda de correção deve usar o cenário do
  verificador.
- **Decisão:** corrigir, e a correção não pode ser justificada por ganho de
  qualidade, apenas por conformidade. Falta uma decisão explícita do responsável
  pela formulação sobre em qual lado escrever a emenda, código ou documento; ela
  não altera a classe, mas decide se o tuning do PSO precisa ser refeito.
- **Onda:** A. É o único achado da Onda A.
- **Situação:** fechado com correção de código, no commit do pacote A1. A decisão 1
  do usuário, de 19 de agosto de 2026, escreveu a emenda no código e não no
  documento: `_trial_state`, em `src/metaheuristica/pso.py:162-193`, satura a
  velocidade antes de somá-la à posição. `velocity_clips` continua contado sobre
  `raw_velocity`, que é a definição existente; `position_clips` passa a ser contado
  sobre um `raw_position` já derivado do passo saturado, e essa mudança de valor é
  legítima e prevista. Medição de fechamento com a instrumentação do verificador,
  configuração congelada, `artesp_rmsp_60`, `K=5`, orçamento 60.000, seeds 0 a 9:
  antes, máximo do passo **1,0** e 1.886.548 de 34.380.000 coordenadas acima de
  0,5, isto é 5,4873%, reproduzindo o número do verificador; depois, **zero**
  violações em 34.336.800 coordenadas e máximo **exatamente 0,5**
  (`0x1.0000000000000p-1`). A média das dez seeds passou de 0,274437411389966 para
  0,280568556706720, com `float.hex()` alterado em 10 de 10 seeds, isto é a
  correção **piora** a média, como previsto, e se justifica apenas por
  conformidade com a seção 16 de `docs/formulation.md`.
  **Nota de escopo da medição.** As zero violações em 34.336.800 coordenadas valem
  para o passo da **tentativa**, `trial.position - posição_anterior`, que é a
  grandeza do achado. O deslocamento efetivamente comprometido na partícula ainda
  excede 0,5 em 938.817 coordenadas, isto é 2,73%, com máximo `0,9999192982105172`,
  contra 1.966.457 coordenadas e máximo `1,0` antes da correção. Esse excedente vem
  do reparo de lotes vazios e da projeção de volta ao espaço contínuo, que a seção
  16 sanciona expressamente, logo **não é violação nem defeito** e não é objeto de
  A1. A frase sobre zero violações não deve ser lida como afirmação sobre o
  movimento total da partícula.
  **Divergência conhecida com o espelho GPU, aberta por esta correção.**
  `gpu/src/metaheuristica_gpu/pso.py:83-101` mantém a ordem antiga, com
  `raw_position = particle.position + raw_velocity` e saturação da velocidade só na
  saída, isto é conserva o defeito que a CPU deixou de ter. Antes da correção os
  dois lados coincidiam bit a bit; depois, divergem em **5,16e-2** de custo total,
  contra a régua normativa de `1e-12`. Não tocar em `gpu/` foi conformidade com a
  lista de arquivos do pacote A1. O espelhamento do PSO foi **realocado para o
  pacote B5**, que já é o dono do espelhamento do ACO. Enquanto B5 não fechar, fica
  **proibido renovar o manifesto de congelamento**: a exposição só abriria nesse
  momento, porque `_cpu_readiness()` em `gpu/src/metaheuristica_gpu/run.py:186`
  reexecuta a verificação antes de todo cenário GPU e o manifesto hoje já diverge, o
  que mantém o alarme armado.
  **Proveniência da correção do espelho, executada no pacote B5 e registrada aqui.** A
  divergência acima foi fechada no commit `d297377`, que é o commit de código do pacote
  B5, e **não** em nenhum commit do pacote A1. `gpu/src/metaheuristica_gpu/pso.py:95-109`
  passou a saturar a velocidade **antes** de somá-la à posição, espelhando
  `metaheuristica.pso._trial_state`, com o comentário no código apontando o pacote A1 como
  origem. O teste novo `gpu/tests/test_pso_gpu.py:25-48`
  (`test_pso_gpu_matches_cpu_on_a_real_instance`, parametrizado em `K=3` e `K=5` sobre
  `artesp_rmsp_20`) mede a divergência que existia: **`5,16e-2`** de custo total, contra a
  régua normativa de `1e-12` de `metaheuristica_gpu.numerics`. O teste anterior, em quatro
  unidades com `K=2`, passava mesmo com o espelho defeituoso, porque as duas trajetórias
  chegam a custo zero de qualquer forma.
  **A lacuna de origem é da lista de arquivos do pacote A1**, que declarou
  `src/metaheuristica/pso.py` e `tests/test_pso.py` e **omitiu**
  `gpu/src/metaheuristica_gpu/pso.py`. Não tocar em `gpu/` foi conformidade com essa
  lista, e foi a lista que estava incompleta. A correção é substantiva e o defeito era
  real e latente; o que não é defensável, e fica registrado como irregularidade de
  escrituração, é que a mudança entrou num commit cuja mensagem não a menciona em nenhuma
  linha e cuja lista de arquivos declarada também não a previa. Esta nota existe para que
  quem procurar a origem da correção do espelho do PSO não a procure em vão no commit do
  pacote A1.
  **Efeito sobre a proibição de renovar o manifesto.** O bloqueio condicionado a B5 está
  cumprido, porque o espelho do PSO deixou de divergir. Isso **não** libera a renovação do
  manifesto de congelamento: a regra permanente da seção 4 de
  `superpowers/B11B_plan_ondas.md` continua proibindo que qualquer pacote das ondas
  regenere o manifesto, e a renovação é da Tarefa 20. A recusa atual de `freeze` e de
  `readiness` é o mecanismo corrigido funcionando, e não regressão.
- **Impressão digital:** diff **não zero**, confinado ao escopo previsto. Divergiram
  exatamente os **11 cenários `pso:*`** e **nenhum** cenário `tabu:*`, `aco:*` ou
  `greedy:*`, em 7.325 diferenças de campo mais o `content_sha256` do documento. Os
  campos divergentes são `solution`, os sete de `evaluation`, os 100 `checkpoints`
  e **os dez campos de `diagnostics`**, todos dentro da previsão do pacote:
  `position_clips`, `velocity_clips` e `personal_best_updates` em 11 cenários cada,
  `global_best_updates` e `strict_global_improvements` em 10 cada, e
  `iterations_completed`, `particles_evaluated`, `repair_attempts`,
  `repair_evaluations` e `repairs_completed` em 6 cada. Linha de base regravada: o `content_sha256` passa de
  `a2d820eba10c4793f6612dbb6f53eebd8e26395e6374bc5ceb1d441ddf4e6b48` para
  `8b4fbfb31f64917e78cdfadcdea0b48cf71f7b95457a14ea04d17ec4388e1e35`. **O ramo 3 da
  cascata está confirmado por medição**: o tuning e o piloto oficiais precisam ser
  refeitos.

#### A3. Avaliações de reparo são viáveis mas ficam inelegíveis para o incumbente

- **Frente:** F3.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md:268-270`, "Todas as consultas à função
  objetivo consomem orçamento, incluindo inicialização, reparo, soluções repetidas
  e cache hits", combinada com a seção 10.1, linhas 320-326, "melhor custo total
  final". **Fonte: normativa**, as duas citações conferidas literalmente.
- **Previsto:** o orçamento é gasto em consultas à função objetivo e a métrica
  reportada é o melhor custo visto pela execução.
- **Código:** `src/metaheuristica/pso.py:290-305`;
  `src/metaheuristica/repair.py:74-82`;
  `src/metaheuristica/evaluator.py:122-134`, com `eligible=False`. Em
  `metrics.py`, `ConvergenceRecorder.observe` só atualiza o incumbente dentro do
  bloco `if eligible:`, e `evaluate_provisional_for_repair` chama
  `self._notify(None, result, eligible=False)` incondicionalmente. Nenhuma
  avaliação de reparo pode, por construção, virar incumbente, não importa seu
  custo.
- **Evidência:** o verificador reproduziu nas seeds 0, 1 e 2: 300, 720 e 120
  avaliações provisórias de reparo, **100% delas com zero lotes vazios no candidato
  avaliado**, e o melhor custo provisório por execução (0,438; 0,454; 0,467) sempre
  pior que o custo final (0,307; 0,310; 0,298), dentro da faixa das 10 execuções
  oficiais, 0,306 a 0,467 contra finais entre 0,208 e 0,310. São 2.664 avaliações
  por execução, 4,44% do orçamento, com custos calculados pela mesma
  `_evaluate_labels` da função objetivo oficial e depois descartados.
- **Veredito adversarial:** CONFIRMADO, classe `D3` mantida. O mecanismo é
  verificável por leitura direta e não depende de medição. O risco é estrutural e
  não se materializou.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, tornando elegível a avaliação provisória cujo candidato
  seja integralmente viável, ou declarar explicitamente na formulação que
  avaliações de reparo não competem pelo incumbente.
- **Onda:** B, com prioridade.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado **não** zero se a elegibilidade
  mudar, porque o incumbente pode passar a absorver custo provisório.

#### A4. A solução reparada é reavaliada em duplicidade

- **Frente:** F3.
- **Classe:** `M1`.
- **Premissa:** `docs/formulation.md` seções 13.2 e 13.3, "A última avaliação
  escolhida coincide com a função objetivo completa e será reutilizada sem nova
  avaliação", citada corretamente como contraste, porque vale para o guloso e não
  para o PSO. **Fonte: normativa.**
- **Previsto:** o projeto conhece e usa o princípio de não pagar duas vezes pela
  mesma avaliação completa.
- **Código:** `src/metaheuristica/pso.py:294` seguida de `pso.py:320`;
  `src/metaheuristica/repair.py:74-105`. Quando existe exatamente um lote vazio, o
  candidato vencedor do reparo já foi avaliado por
  `evaluate_provisional_for_repair` com a mesma `_evaluate_labels`, e `pso.py:320`
  o avalia novamente por `context.evaluate`, consumindo mais uma unidade de
  orçamento.
- **Evidência:** o verificador instrumentou `repair_empty_lots` e
  `OptimizationContext.evaluate` e comparou o custo provisório **vencedor** contra
  o da reavaliação seguinte: na seed 0, **5 de 5 reparos com pares bit a bit
  idênticos**. `repair_attempts == repairs_completed` em todas as execuções
  observadas, logo o número de duplicatas por execução é exatamente
  `repairs_completed`, com média de 44,4 reproduzida do Parquet oficial, isto é
  0,074% do orçamento de 60.000. Nas configurações mais reparadoras da grade chega
  a 255 duplicatas por execução, 0,43%.
- **Veredito adversarial:** CONFIRMADO por teste direto, bit a bit. Classe `M1`
  mantida.
- **Divergência auditor / verificador:** nenhuma no resultado. O verificador
  registra que sua primeira tentativa de instrumentação comparou contra a
  **última** chamada de reparo em vez da vencedora e deu 5 de 5 divergentes, o que
  confirma apenas que o vencedor não é necessariamente o último testado; corrigido
  o alvo, a identidade é total. Registro por honestidade de método.
- **Decisão:** corrigir, reaproveitando a avaliação vencedora do reparo. Atenção:
  reaproveitar libera uma unidade de orçamento por reparo e portanto muda a
  trajetória.
- **Onda:** B, junto de A3, por tocarem o mesmo bloco de reparo.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado **não** zero, porque o orçamento
  liberado altera o número de candidatos avaliados.

#### A5. Contadores de saturação incluem a iteração interrompida

- **Frente:** F3.
- **Classe:** `D2`.
- **Premissa:** `docs/experiments.md` seções 8 e 10.3, orçamento interrompido
  imediatamente depois da avaliação que consome o limite, e diagnósticos de esforço
  por execução. **Fonte: normativa** quanto às seções; a formulação da verificação
  "iteração interrompida que não incrementa contador" é **metodologia da
  auditoria**, vinda do dossiê da frente, e o achado não depende dela.
- **Previsto:** os diagnósticos de uma iteração não concluída não devem ser
  atribuídos a iterações concluídas.
- **Código:** `src/metaheuristica/pso.py:276-282` contra `pso.py:355`. As linhas
  280 e 281 somam `position_clips` e `velocity_clips` de **todas** as
  `n_particles` tentativas antes de qualquer avaliação, e `iterations_completed` só
  é incrementado na linha 355.
- **Evidência:** o verificador demonstrou de forma **mais direta** que o
  relatório, varrendo o orçamento em torno do ponto de corte de uma iteração com
  `N=4` e `n_particles=4`:

  | Orçamento | `iterations_completed` | `particles_evaluated` | `position_clips` |
  |---:|---:|---:|---:|
  | 100 | 23 | 100 | 272 |
  | 101 | 24 | 101 | 284 |
  | 102 | 24 | 102 | 284 |
  | 103 | 24 | 103 | 284 |
  | 104 | 24 | 104 | 284 |

  De orçamento 101 a 104, `position_clips` fica travado em 284 mesmo que o número
  de partículas efetivamente avaliadas na iteração final suba de 1 para 4, o que
  prova o mecanismo sem depender de inferência aritmética sobre a campanha oficial.
  No dado oficial da seed 0, o excesso é de cerca de 103 saturações em 307.107,
  isto é 0,034%.
- **Veredito adversarial:** CONFIRMADO, com evidência adicional. Classe `D2`
  mantida, porque nada disso afeta o incumbente ou o custo final, apenas os
  diagnósticos.
- **Divergência auditor / verificador:** nenhuma. O verificador **acrescentou** um
  achado adjacente que reforça a classe: mesmo em orçamento que divide exatamente
  por `n_particles`, `iterations_completed` fica um abaixo do esperado, porque a
  última avaliação de **qualquer** execução dispara `EvaluationLimitReached` em
  `OptimizationContext._stop_at_limit`, que verifica `remaining == 0` **depois** de
  uma avaliação bem sucedida, e esse caminho de exceção nunca alcança a linha que
  incrementa o contador. Ou seja, a iteração final de qualquer execução do PSO não
  é contada. Esse item derivado consta do Apêndice B, porque não passou por
  verificação adversarial independente.
- **Decisão:** corrigir, movendo a soma dos contadores de saturação para depois da
  avaliação de cada tentativa.
- **Onda:** B.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado limitado a campos de diagnóstico,
  o que **é** diff para o oráculo, porque a impressão digital compara os sete
  campos e os diagnósticos.

#### A6. O recuo ao ponto médio abandona a fração prescrita

- **Frente:** F3.
- **Classe:** `D3`.
- **Premissa:** `docs/formulation.md` seção 16, "A solução reparada é projetada de
  volta ao espaço contínuo preservando a fração interna de cada chave", conferida
  literalmente. **Fonte: normativa.**
- **Previsto:** a chave projetada é exatamente `(lote + u)/K`, com `u` a fração
  interna original.
- **Código:** `src/metaheuristica/pso.py:203-212`, no bloco `for ... else` de
  `_project_position`. Depois de até 16 passos de `np.nextafter` na direção do
  ponto médio, o ramo `else` substitui a chave por `(lote + 0.5)/K`, descartando
  `u` e fixando `u = 0,5`, sem registrar diagnóstico algum do descarte.
- **Evidência:** o verificador reproduziu `_project_position` fora de `pso.py` e
  contou quantas coordenadas exaurem as 16 tentativas sem decodificar no rótulo
  alvo: **0 ocorrências** nas seeds 0, 1 e 2, em 1.140 avaliações de reparo com uma
  projeção cada, consistente com o "nunca acionado" do relatório, que mediu 0 em
  13.268.820 coordenadas projetadas nas 10 execuções oficiais. A projeção normal
  preserva `u` com desvio máximo da ordem de 16 ULP. Não há teste cobrindo o ramo.
- **Veredito adversarial:** CONFIRMADO quanto ao mecanismo e à não ocorrência.
  Classe `D3` mantida: mecanismo real, nunca observado.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, registrando diagnóstico quando o ramo acionar, ou
  levantando erro em vez de descartar silenciosamente a fração que o documento
  manda preservar.
- **Onda:** B, com prioridade.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero, porque o ramo nunca aciona.

#### A7. A canonicalização da posição viva não está documentada e é decisiva

- **Frente:** F3.
- **Classe:** `L1`.
- **Premissa:** `docs/formulation.md` seção 11, que lista os usos da
  canonicalização como "comparação de soluções; testes; armazenamento; cache, se
  implementado", e a seção 16, que prescreve projeção de volta ao espaço contínuo
  **apenas** para o caso de reparo. Contraste interno: a seção 14 diz, para a Busca
  Tabu, "Os rótulos permanecem estáveis durante a trajetória". **Fonte:
  normativa**, as duas citações conferidas literalmente, e a da seção 14 usada como
  contraste e não como violação.
- **Previsto:** a canonicalização é operação de comparação e armazenamento; a
  posição da partícula é reescrita somente quando houve reparo.
- **Código:** `src/metaheuristica/pso.py:219-226` (`_canonical_candidate`),
  acionadas em `pso.py:247` e `:307`. A cada iteração, todo candidato cuja
  decodificação não esteja em forma canônica tem a **posição viva reescrita** por
  `_project_position`, o que muda as coordenadas da partícula sem que exista
  movimento no espaço de soluções.
- **Evidência:** o verificador confirmou o exemplo diretamente:
  `canonicalize_solution([2,2,0,0,1,1], n_units=6, k=3)` devolve `[0,0,1,1,2,2]` e
  a nova chave da unidade 0 reproduz o "cerca de 0,17" citado, contra cerca de 0,83
  antes, um salto de 0,66 no domínio `[0,1]` sem melhora alguma. Taxa de reescrita
  medida pelo verificador nas seeds 0, 1 e 2: **24,2%, 78,8% e 5,2%**, média 36,1%,
  próxima da média oficial de 39,1% mas com dispersão muito maior do que o número
  único sugere.
- **Veredito adversarial:** CONFIRMADO quanto ao mecanismo e às premissas. **A
  magnitude de qualidade que sustenta a classe não foi reproduzida.**
- **Divergência auditor / verificador:** dois itens. Primeiro, o número único de
  39,1% esconde variação de 5,2% a 78,8% entre seeds e precisa de nota se for
  reusado. Segundo, e decisivo: a alegação de que suprimir a canonicalização da
  posição viva muda a média para 0,286856 e derruba a troca de rótulo por
  coordenada de 30,8% para 1,2% **não foi reverificada**, porque exigiria modificar
  código, o que o contrato de somente leitura da verificação proibia. **Isso pesa
  sobre a classificação**, porque a própria justificativa de `L1` é que "o
  comportamento do código é melhor que o do documento", o que depende inteiramente
  daquele número. Se ele não se sustentar, o achado teria de ser reavaliado como
  defeito que altera resultados, sem a defesa de que a mudança é benéfica.
- **Decisão:** corrigir a **seção 16** de `docs/formulation.md`, que hoje não
  descreve um mecanismo que responde por toda a diversificação do método. Antes
  disso, reproduzir 0,286856 de forma independente. **A onda de correção não pode
  tratar A7 como fechado em `L1` sem essa reprodução.**
- **Onda:** registro apenas, condicionado ao fechamento da lacuna.
- **Situação:** **aberto com lacuna declarada.**
- **Impressão digital:** pendente. Sem alteração de código prevista, logo diff
  esperado zero; se a lacuna reabrir a classe, a previsão muda.

#### A8. O desempate por posição troca o atrator sem melhora alguma

- **Frente:** F3.
- **Classe:** `L1`.
- **Premissa:** `docs/formulation.md` seção 16, "topologia global" e "cada iteração
  usa um único snapshot do melhor global", conferidas literalmente. **Fonte:
  normativa.**
- **Previsto:** a cadeia de desempates existe para tornar determinística a escolha
  entre soluções equivalentes; o atrator global é o melhor global.
- **Código:** `src/metaheuristica/pso.py:159`, usada em `pso.py:257`, `:266`,
  `:328`, `:348` e `:371`. A cadeia está implementada exatamente como prescrita, e
  o terceiro nível, posição lexicográfica, é atingido com altíssima frequência
  quando o candidato tem a **mesma** solução canônica do incumbente.
- **Evidência:** o número central é verificável direto do Parquet oficial, sem
  instrumentação: `global_best_updates` médio 1.944,3 e
  `strict_global_improvements` médio 32,2, logo
  `(1944,3 - 32,2)/1944,3 = 0,98344`, isto é **98,3%** das substituições do atrator
  não melhoram nada. O verificador instrumentou `_best_comparison` nas seeds 0, 1 e
  2 e contou **0 ocorrências de nível 2** (soluções canônicas distintas empatadas
  em custo) contra dezenas de milhares de nível 3, consistente com o "nunca
  ocorreu" do relatório.
- **Veredito adversarial:** CONFIRMADO, classe `L1` mantida. **A magnitude de
  qualidade não foi reproduzida.**
- **Divergência auditor / verificador:** a alegação de que suprimir apenas o nível
  3 muda a média para 0,272414, com `delta = -0,002023` e `t = -0,15`, **não foi
  reverificada**, pela mesma razão de A7: exigiria alterar código e rodar 10 seeds.
- **Decisão:** registro apenas, com a consequência a declarar no relatório final: o
  critério documentado produz um atrator que se move quase 2.000 vezes por execução
  sem melhorar nada, e isso precisa estar dito se as curvas de convergência do PSO
  forem interpretadas.
- **Onda:** registro apenas, condicionado ao fechamento da lacuna.
- **Situação:** **aberto com lacuna declarada.**
- **Impressão digital:** pendente.

#### A9. A comparação com tolerância mais desempate não é transitiva

- **Frente:** F3.
- **Classe:** `L1`, rebaixada de `D3`.
- **Premissa:** o achado citava `constraints.md:19-20`, "Comparação de `float64`
  sempre exata, bit a bit, via `float.hex()`. Proibido usar tolerância na comparação
  da impressão digital". A citação **existe literalmente**, mas sua **fonte é
  metodologia desta auditoria**, não regra do projeto. A premissa correta, que
  sustenta o achado, é `docs/experiments.md` seção 10.1, que define a métrica
  principal como "melhor custo total final". **Fonte: normativa**, para a premissa
  válida; **fonte: metodologia da auditoria**, para a premissa citada e descartada.
- **Previsto:** a métrica reportada é o melhor custo total final da execução, e o
  incumbente não pode ser uma solução estritamente pior que outra já vista.
- **Código:** `src/metaheuristica/pso.py:149-159` e
  `src/metaheuristica/metrics.py:153-165`, com `COST_TOLERANCE = 1e-12`. O padrão
  de tolerância seguida de desempate por tupla produz relação não transitiva: `a`
  empata com `b`, `b` empata com `c`, e `a` perde de `c` por custo, logo a ordem
  final passa a depender da ordem de apresentação.
- **Evidência:** o verificador demonstrou o mecanismo **no componente que produz a
  métrica oficial**, e não em abstrato. Rodou o `ConvergenceRecorder` real, sem
  modificação, com três observações: `a` custo `0,0` solução `(0,5)`, `b` custo
  `0,6e-12` solução `(0,1)`, `c` custo `1,2e-12` solução `(0,0)`. O incumbente
  registrado termina em `c`, com custo `1,2e-12`, apesar de `a` ter sido visto antes
  e ser estritamente melhor por mais que a tolerância. Probabilidade de ocorrência
  real desprezível: 0 de 3 seeds reproduzidas, consistente com 0 de 10 oficiais,
  porque exige duas partições **diferentes** empatarem em custo até `1e-12`.
- **Veredito adversarial:** **REFUTADO quanto ao enquadramento da premissa,
  mecanismo sobrevive, reclassificado de `D3` para `L1`.** A restrição global
  citada é usada de forma consistente em toda esta auditoria como regra de
  metodologia de verificação de reprodutibilidade, e o projeto usa `1e-12` como
  tolerância de desempate **deliberada e documentada** em pelo menos três outros
  lugares: aspiração e empates de custo da Busca Tabu
  (`docs/formulation.md` seção 14, linhas 599-604), desempate de seleção do tuning
  (`docs/experiments.md` seção 12.1) e a própria cadeia de desempate do PSO da
  seção 16, que a verificação obrigatória 6 do relatório já havia declarado
  conforme. Como o mecanismo é propriedade inerente de um padrão que o projeto usa
  em três outros lugares sem tratá-lo como defeito, a classe correta é `L1`.
- **Divergência auditor / verificador:** a citação de premissa deve ser
  **removida** e substituída por `docs/experiments.md` seção 10.1. O verificador
  registra também que sua primeira tentativa atacou `_best_comparison`, o desempate
  interno do `gbest`, que mostra o mecanismo mas não é o componente que gera
  `C*_final`; corrigiu para o `ConvergenceRecorder`.
- **Decisão:** registro apenas. É um dos dois achados inflados pela confusão entre
  fonte normativa e metodologia da auditoria, cuja causa raiz está na seção 6.
- **Onda:** registro apenas.
- **Situação:** fechado sem ação de código.
- **Impressão digital:** pendente.

#### A10. `_trial_state` não tem cobertura de teste

- **Frente:** F3.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 16 e `docs/experiments.md` seção 13,
  limites de posição e velocidade com números explícitos. **Fonte: normativa.**
- **Previsto:** um invariante com números explícitos é exatamente o tipo que o
  conjunto de testes deve fixar.
- **Código:** `tests/test_pso.py`, 10 testes em 146 linhas, nenhuma referência a
  `_trial_state`, confirmado por leitura integral do verificador. A única asserção
  sobre limite de velocidade está em `tests/test_pso.py:82-83`, dentro de
  `test_initial_population_is_balanced_viable_and_reproducible`, e cobre apenas a
  velocidade **inicial** de `_initial_particle`, condição que A1 não viola.
- **Evidência:** `_trial_state`, a função que contém A1, é a única rotina central
  do PSO sem teste direto, e a suíte passa inteira com o defeito presente. Um teste
  com `w=0.4`, `c1=2.0`, `c2=1.5`, `x=[0.5]`, `pbest=[1.0]`, `gbest=[1.0]`,
  `v=[0.5]`, `r1=r2=1.0` deveria afirmar `trial.position - x <= 0.5`, e falharia no
  código atual porque o deslocamento bruto é 1,95.
- **Veredito adversarial:** CONFIRMADO, classe `M2` mantida.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, no mesmo commit de A1. Junto de F2-10, é a cobertura que
  faltava para que o único `D1` da auditoria tivesse sido detectado pela suíte, e o
  defeito atravessou o tuning oficial de 440 execuções sem sinal.
- **Onda:** A, junto de A1.
- **Situação:** fechado com teste novo, no commit do pacote A1.
  `test_trial_state_reproduces_the_formula_and_both_counters`, em
  `tests/test_pso.py`, exercita `_trial_state` diretamente e fixa a fórmula inteira
  contra valores calculados à mão: os dois sorteios de `PCG64(2026)`, as quatro
  velocidades, as quatro posições e os dois contadores. O teste falha sob a ordem
  defeituosa, que produz posições `1,0` e `0,0` no lugar de `0,6` e `0,4` e
  `position_clips` 2 em vez de 0. O vetor sugerido no campo de evidência, com
  `x=0,5`, **não** foi usado, porque produz o mesmo passo sob as duas ordens; o
  vetor do teste tem coordenadas em `0,10` e `0,90`, que discriminam.
- **Impressão digital:** sem efeito próprio, porque a alteração é restrita a
  `tests/`. O diff não zero registrado em A1 é do mesmo commit e vem inteiro da
  correção de A1.

### 3.4. Frente F4 - ACO

Cinco achados, zero refutados, cinco confirmados integralmente, nenhuma
reclassificação. Todas as premissas foram conferidas literalmente na fonte e
existem como citadas. Números reproduzidos, em vários casos bit a bit por
`float.hex()`: geração de aborto 1075, 814 e 324 para `rho` 0,5, 0,6 e 0,9;
`final_tau_min` idêntico em quatro orçamentos com o incumbente mudando em
`budget=439`; divergência de exatamente 1 ULP em `c_territorial`; e contagens
exatas de chamada por `cProfile`, 221352, 221552, 443104, 30000 e 342354.

**Zero `D1` afirmativo.** A unicidade canônica foi confirmada exaustivamente com
contagem igual a `S(n,k)` para `2 <= n <= 9`; a abertura obrigatória não falha em
prefixo alcançável; `eta` está sempre em `[1,2]`; as probabilidades em log são
estáveis; e o depósito é estritamente positivo, com limite provado de
`custo <= 0,862854` em `K=8`.

**O ganho de 3,58x preservando os bits, que é a alegação de maior consequência
prática da auditoria, sobreviveu à verificação adversarial.** O verificador testou
mais de 61.000 linhas adversariais: vetores derivados de base comum, linhas
independentes, zeros de todo tipo, magnitudes extremas, cancelamento
catastrófico, `K` de 2 até 500 e portanto muito além do intervalo `[2,12]`
alegado, mais a cadeia explícita de custo total de O2 em 40.000 casos. Zero
divergências sob construção C-contígua. E usou **dois controles negativos** para
provar que o comparador detecta divergência quando ela existe: `ddof=1` falha em
50 de 50, e produto BLAS falha em 11,7%. Sem esses controles a ausência de
divergência não significaria nada. Duas candidatas maiores foram rejeitadas com
disciplina, e a verificação concordou com as duas rejeições: **O3** a 4,11x
depende de trocar `rng.choice` por `cdf.searchsorted`, cuja exatidão repousa em
detalhe de implementação não documentado do NumPy e não em semântica IEEE 754;
**O5** a 4,51x colapsa os cortes por `bincount`, reassociação que difere em cerca
de um terço das somas individuais, e é rara **e silenciosa**. A diferença entre
4,51x e 3,58x é o preço da garantia.

**Ressalva nova, acionável, que nenhum dos dois lados havia visto: a identidade
depende de ordem C.** Construindo a mesma matriz `(m,K)` em ordem Fortran, a
redução em `axis=1` diverge em **22 de 50 linhas (44%) com `K=8`** e **17 de 50
(34%) com `K=12`**, enquanto a ordem C dá zero divergência em `K` de 2, 5, 8 e 12.
Isso não refuta o que o relatório testou, porque "matriz contígua" no NumPy
produz ordem C por padrão, mas é lacuna de robustez sem guarda-corpo.
**Recomendação obrigatória para a onda de correção: incluir
`assert matrix.flags['C_CONTIGUOUS']` na implementação real.** Sem isso, uma
refatoração futura que produza a matriz por transposição ou por `order='F'`
quebra a identidade em silêncio, que é exatamente o modo de falha usado para
rejeitar O5.

**Limitação de escopo declarada.** As 176.557 linhas e 176 execuções citadas pelo
relatório não são re-verificáveis, porque o protótipo original foi escrito fora da
árvore e não existe mais. Isso é limitação e não refutação. Consequência
acionável: a identidade bit a bit precisa ser **reestabelecida contra a
implementação real** quando a onda materializar O2 e O4 em código versionado, e
não presumida herdada do protótipo descartado.

#### F4-1. Recomputação evitável no custo parcial da construção

- **Frente:** F4.
- **Classe:** `M1`.
- **Premissa:** `docs/formulation.md` seção 15, "Para cada escolha permitida, o
  ACO calcula o custo parcial dos mesmos quatro componentes usados pelo guloso";
  `docs/experiments.md` seção 15, "A informação heurística normaliza em `[1, 2]` os
  custos parciais das alternativas permitidas". **Fonte: normativa.** Os documentos
  prescrevem *que valores* precisam existir, não o número de operações.
- **Previsto:** um custo parcial por alternativa permitida, com os mesmos quatro
  componentes. Nada prevê revalidação do prefixo completo por posição,
  reconstrução do vetor de rótulos por escolha, recálculo dos denominadores de
  corte por escolha, nem republicação de diagnósticos por formiga.
- **Código:** `src/metaheuristica/aco.py:109-143` (`evaluate_choice` e `append`),
  `:205-223` (`_heuristic_from_state`), `:145-187` (`_validate_prefix` e
  `_construction_choices`), `:265-307` (`_construct_ant`), `:347-357` e `:416`
  (`_AcoDiagnostics.publish`, chamado por formiga). Por posição e por alternativa,
  `evaluate_choice` faz duas cópias de vetores de tamanho `K`, uma reconstrução
  `np.asarray(self.labels, dtype=np.int64)` do prefixo inteiro a partir de lista
  Python, e **quatro** reduções, das quais duas não dependem de `lot` e produzem o
  mesmo `float64` para todas as `m` alternativas; e constrói um
  `EvaluationResult` cujo `__post_init__` roda `isfinite` sobre sete campos quando
  o consumidor usa apenas `total_cost`. `append` recalcula as mesmas quatro somas.
  `_validate_prefix` percorre o prefixo inteiro em Python a cada posição, tornando
  a validação quadrática por formiga. `_construct_ant` revalida `tau` inteiro por
  formiga, embora `tau` seja constante na geração.
- **Evidência:** o verificador reproduziu o `cProfile` com contagens de chamada
  **idênticas** ao relatório: `evaluate_choice` 221.352, `_evaluate_aggregates`
  221.552, `_balance_totals_component` 443.104, `_validate_prefix` 30.000,
  `numpy.asarray` 342.354, `EvaluationResult.__post_init__` 221.552. Frações de
  tempo cumulativo consistentes: 74,2% para `evaluate_choice` contra 74,6% do
  relatório, e 44,8% para `_balance_totals_component` contra 45,0%. Campanha ACO
  com `N=150`: **439,7 h-CPU** no estado atual contra **122,8 h-CPU** com a
  variante recomendada, isto é 27,48 h para 7,67 h de relógio com 16 workers.
  Verificação adicional que o relatório não tinha: a extrapolação entre sementes é
  segura, com contagem de chamadas por formiga de 1106,76 / 1104,70 / 1107,90 /
  1102,67 / 1107,21 em cinco sementes, dispersão de 0,47%, e tempo por formiga
  entre 73,6 e 74,4 ms, dispersão abaixo de 1%.
- **Veredito adversarial:** CONFIRMADO. Classe `M1`, sem candidato melhor: o
  código implementa a regra documentada corretamente, não é questão de teste nem
  de legibilidade.
- **Divergência auditor / verificador:** nenhuma nos números do achado. Duas
  ressalvas foram **acrescentadas** pelo verificador: a dependência de ordem C,
  descrita acima, e a impossibilidade de re-verificar as 176.557 linhas do
  protótipo descartado.
- **Decisão:** corrigir, com a variante O4, que monta matriz `(m,K)` contígua e faz
  as reduções com `np.add.reduce` replicando a aritmética de
  `numpy._methods._var` na mesma ordem de operações, em vez de trocar
  `np.mean`/`np.std` por aritmética `float` ingênua. Este achado **supera a
  prescrição** de F1-05 e absorve o ganho que ela buscava. A onda precisa mover
  junto três testes e um helper: `tests/test_aco.py:93-111`, `:114-127` (que é
  F4-5), `:69-79` e `src/metaheuristica/aco.py:189-202` (`_heuristic_values`, usado
  apenas pelos testes). E precisa espelhar a mudança em
  `gpu/src/metaheuristica_gpu/aco.py:42-84`, que reimplementa o mesmo padrão de
  recomputação, para que `require_equivalent` continue válido.
- **Onda:** B. Deve entrar **antes** de qualquer retuning, porque o tuning roda 160
  execuções de ACO e o próprio retuning fica mais barato com a correção aplicada.
- **Situação:** fechado no commit `d297377`, do pacote B5, com a variante O4.
  `_PartialConstructionState.choice_costs` (`src/metaheuristica/aco.py:114-168`) monta a
  matriz `(2m, K)` contígua em ordem C e delega a redução a `_evaluate_total_costs`
  (`src/metaheuristica/objective.py:99-135`), que por sua vez chama
  `_balance_totals_matrix` (`:61-89`), a réplica vetorizada que reproduz a ordem de
  operações de `numpy._core._methods._mean` e `._var` com `ddof=0`, em vez de trocar
  `np.mean` e `np.std` por aritmética `float` ingênua. `_heuristic_from_state`
  (`aco.py:297`) consome os custos em lote e `_construct_ant` (`aco.py:363`) mantém
  `opened` incrementalmente, o que remove a validação quadrática do prefixo e a
  revalidação de `tau` por formiga. O guarda-corpo obrigatório está na implementação
  real, em `objective.py:78` e `:85`, e não apenas no teste, com o comentário exigido;
  ver o item `B1` do Apêndice B.
  **Oráculo usado, e ele não é tautológico.** A implementação anterior,
  `evaluate_choice`, foi **preservada intacta** (`aco.py:170-199`), com docstring
  declarando que ela é a referência normativa, e
  `test_batched_choice_costs_reproduce_the_reference_bit_by_bit` compara `choice_costs`
  contra ela por `float.hex()` em 27 combinações parametrizadas de instância e `K`,
  percorrendo construções reais e comparando em toda posição não forçada. Os dois
  controles negativos obrigatórios estão em
  `test_negative_controls_prove_the_comparator_detects_divergence`: `ddof=1` diverge em
  toda linha e o produto por BLAS diverge em parte delas. Isso é o que o item `B2` do
  Apêndice B exigia, a saber, reestabelecer a identidade contra a implementação real, já
  que o protótipo original não é re-verificável.
  **Ganho medido.** 3,58x preservando os bits, declarado pelo pacote; a revisão
  independente reproduziu **3,70x** medindo `_construct_ant` em `artesp_rmsp_150` com
  `K=8`, com as sete variáveis de thread fixadas em `1` e validação por `aco.__file__` de
  qual módulo foi carregado, com a base caindo dentro da faixa de 73,6 a 74,4 ms por
  formiga que o verificador da F4 mediu. O número do pacote é conservador. Campanha ACO
  em `N=150` cai de 439,7 h-CPU para 122,8 h-CPU, como projeção aritmética; o número
  definitivo vem do roteiro regenerado.
  **O `S` honesto do ACO, e o resultado que entra no relatório.** O espelhamento em
  `gpu/` foi feito, por unificação e não por cópia, de modo que a construção da GPU
  recebeu o mesmo ganho: 3,18x medidos pela revisão independente. Com isso o `S` do ACO
  **não inverte de sinal**, e passa a ser da ordem de **1,006**, contra os 1,3518
  anteriores. Este é o resultado que entra no relatório final: **o resultado do ACO na
  GPU é negativo**, no sentido de que a variante GPU deixa de apresentar ganho
  apreciável sobre a CPU otimizada, e é ele que deve ser relatado, e não o 1,3518 medido
  contra a CPU lenta. Sem o espelhamento o `S` cairia a cerca de 0,38, isto é a GPU
  ficaria cerca de 2,6 vezes mais lenta que a CPU otimizada. O número 1,006 é projeção
  aritmética, corroborada em direção e magnitude pela revisão independente, e não
  substitui o roteiro regenerado; ver o item `B9` do Apêndice B.
  **Mudança de comportamento observável dentro das linhas removidas, declarada aqui
  porque não foi declarada no commit.** Entre as 56 linhas removidas de `gpu/aco.py`
  estava `heuristic()`, que **não** verificava finitude dos custos nem confinamento de
  `eta` a `[1, 2]`. O `_heuristic_from_state` que a substitui levanta
  `ConfigurationError` nos dois casos (`src/metaheuristica/aco.py:304` e `:315`). É
  endurecimento desejável, o caminho feliz é idêntico, e é a única mudança de
  comportamento observável que a revisão encontrou nas 112 linhas removidas pelo commit.
  **Passo G.** Classe prevista `M1`; classe observada `M1`; a observação **bate** com a
  previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, sobre o **conjunto completo dos 42
  cenários**, sem `--only`, porque `objective.py` e `evaluator.py` afetam os quatro
  algoritmos. **Passo G.** Diff previsto zero; diff observado zero; a observação **bate**
  com a previsão. O zero era exigência e não previsão neste pacote, porque a
  bit-preservação é a alegação inteira do achado, e por isso o oráculo foi validado por
  marcador antes de a ausência de diff ser interpretada. A revisão independente do pacote
  **não** refez a impressão digital, por determinação do pacote de revisão; o que ela
  reconferiu foram as duas suítes e as medições de ganho. A expectativa deixou de ser
  presumida do protótipo descartado e passou a ser confirmada contra a implementação
  real.

#### F4-2. A informação heurística é ordinal, de amplitude fixa, e sua influência decai a zero relativo

- **Frente:** F4.
- **Classe:** `L1`.
- **Premissa:** tensão entre duas fontes normativas. `docs/experiments.md` seção 17
  declara a forma conceitual `eta ∝ 1/(ΔC + ε)` e exige que "A regra definitiva
  usada no código deverá ser registrada no relatório técnico";
  `docs/formulation.md` seção 15 registra a regra definitiva,
  `eta[i,k] = 1 + (C_max - C[i,k]) / (C_max - C_min)`. **Fonte: normativa nas duas
  pontas**, ambas conferidas literalmente.
- **Previsto:** atratividade decrescente no custo marginal, na família recíproca,
  cuja razão entre melhor e pior alternativa acompanha a razão dos custos.
- **Código:** `src/metaheuristica/aco.py:213-223`, `:244-246` e `:38-42`.
  Implementa fielmente a regra da seção 15, que é transformação min-max afim e não
  recíproca.
- **Evidência:** duas consequências estruturais medidas. Primeira, a transformação
  é invariante de escala: a amplitude de log de `eta` foi **`1,386294` em 100% dos
  casos**, em 71.520 conjuntos de escolha em `N=150, K=8`, 141.600 em `N=60, K=5` e
  378.945 em `N=20, K=5`, enquanto a amplitude bruta dos custos subjacentes variou
  de `2,291e-04` a `4,843e-01`, fator de 2.113 entre extremos. Segunda, como `tau`
  não tem limite, a amplitude de log do feromônio supera a da heurística muito
  antes do fim do orçamento: o verificador reimplementou a construção com os
  parâmetros congelados e mediu a fração de escolhas em que `tau` domina `eta` em
  **8,40% nas gerações 0-1 e 93,64% nas gerações 9-11**, contra 8,4% e 93,6% do
  relatório. Em `N=20, K=5` com orçamento completo, a amplitude de log de `tau` vai
  de 7,47 no primeiro quinto a 49,95 no último, com razão final
  `tau_max/tau_min` de `2,3e+25`. Estatísticas pareadas reproduzidas exatamente:
  `beta=2` menos `beta=1` em 80 pares dá diferença média `-0,043423`, erro padrão
  `0,007120`, `t=-6,10`, com `beta=2` vencendo em 76,25% dos pares; `alpha=2` menos
  `alpha=1` dá `+0,134165` com erro padrão `0,006986` e perde em 100% dos 80 pares.
  No canto vencedor, a diferença vencedor contra vice é `-0,005201` com erro padrão
  `0,013928`, `t=-0,37`.
- **Veredito adversarial:** CONFIRMADO. Classe `L1` correta: o código implementa
  fielmente a regra registrada na fonte de verdade declarada, logo não há
  divergência documento contra código; a tensão é contra a forma conceitual da
  seção 17, que o próprio documento trata como preliminar. A defesa de caminho
  inalcançável sob os hiperparâmetros congelados foi testada e **não se sustenta**.
- **Divergência auditor / verificador:** uma correção de número interno, e **ela
  fortalece o achado**. O relatório afirma "sinal invertido em 4 das 10 sementes";
  recontando as dez diferenças por semente (`0,0285; 0,0049; -0,0001; 0,0592;
  -0,0650; 0,0012; 0,0129; 0,0068; -0,0944; -0,0061`), **6 das 10** divergem do
  sinal da média, não 4. Este é um dos dois casos independentes do mesmo erro de
  subcontagem, tratado na conexão 4 da seção 5.
- **Decisão:** registro apenas, como limitação a declarar no relatório técnico, e
  não como defeito a corrigir sob congelamento. Registrar também que
  `AcoConfig` rejeita `beta = 0`, portanto a ablação "sem heurística" não é
  executável sem alterar código, e não existe evidência experimental no
  repositório sobre quanto a heurística contribui.
- **Onda:** registro apenas.
- **Situação:** fechado sem ação de código.
- **Impressão digital:** pendente.

#### F4-3. Evaporação sem piso aborta a execução com `rho` maior ou igual a 0,5

- **Frente:** F4.
- **Classe:** `D3`.
- **Premissa:** `docs/formulation.md` seção 15, "Depois de uma geração completa, o
  feromônio evapora por `(1-rho)` e cada formiga deposita `1-custo_total` em todas
  as suas atribuições"; `docs/experiments.md` seção 15 repete a regra e fixa a
  grade `rho ∈ {0.1, 0.3}`. **Fonte: normativa.**
- **Previsto:** evaporação geométrica indefinida, sem piso declarado, e execução
  que termina por esgotamento de orçamento, que é o único motivo previsto em
  `metrics.py:168-171`.
- **Código:** `src/metaheuristica/aco.py:326`, `:333-334` e `:44-50`. Como a
  construção é de crescimento restrito, as células `tau[i, j]` com `j > i` nunca
  recebem depósito e sofrem apenas evaporação pura, valendo `(1-rho)^G`. Com `rho`
  de 0,1 e 0,3 a multiplicação satura no menor subnormal `4,941e-324` e nunca chega
  a zero. Com `rho >= 0,5` a saturação não ocorre, `4,941e-324 * 0,5` cai
  exatamente no meio e o arredondamento para par produz `0,0`, a guarda dispara e
  levanta `ConfigurationError`, que não é `BudgetExhausted` e portanto **não** é
  capturada por `execute_optimizer` (`optimizer.py:139-141`): a exceção sobe e mata
  a execução.
- **Evidência:** reprodução exata pelo verificador. Com `rho = 0.1` e `0.3`, 4.000
  gerações sem aborto, `min(tau) = 9,333e-184` e `4,941e-324`. Com `rho = 0.5`,
  aborto na geração **1075**; com `0.6`, na **814**; com `0.9`, na **324**.
  Qualquer configuração com `rho >= 0,5` e `budget / n_ants >= 1075` perde a
  execução inteira depois de horas de cálculo, sem incumbente e sem checkpoints.
- **Veredito adversarial:** CONFIRMADO, reprodução exata. Classe `D3` mantida.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, com piso explícito de feromônio ou com conversão da guarda
  em terminação controlada. **A campanha congelada não está exposta**: usa
  `rho = 0.1` e o pior caso é `150000/40 = 3750` gerações, com
  `0,9^3750 = 2,567e-172`, muito acima do subnormal. A grade de tuning também
  sobrevive, mas por saturação de subnormais e não por projeto. A exposição é de
  qualquer retuning que amplie a grade de `rho`, ou de instância futura com
  orçamento maior.
- **Onda:** B, com prioridade.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero, porque a campanha congelada
  não aciona o caminho.

#### F4-4. `final_tau_min` é um diagnóstico degenerado

- **Frente:** F4.
- **Classe:** `D2`.
- **Premissa:** `docs/experiments.md` seção 10 prevê o registro de métricas por
  execução destinadas à análise do comportamento do método; `docs/formulation.md`
  seção 15 descreve `tau` como o estado adaptativo do ACO. **Fonte: normativa.**
- **Previsto:** métricas por execução que digam algo sobre o que a busca fez.
- **Código:** `src/metaheuristica/aco.py:355`
  (`final_tau_min=float(np.min(tau))`), publicado em `:374`, `:407`, `:416` e
  `:421`. Toma o mínimo sobre a matriz inteira; pelo argumento estrutural de F4-3,
  as células com `j > i` nunca recebem depósito e valem todas o mesmo `(1-rho)^G`,
  enquanto qualquer célula com ao menos um depósito vale no mínimo `0,137146`.
- **Evidência:** reprodução exata bit a bit. Em `artesp_rmsp_20`, `K=5`, seed 10,
  `rho=0.1`, `n_ants=40`, `budget=400`, `final_tau_min = 0x1.650bf60432fdap-2 =
  0,34867844`, que é exatamente `0,9^10`, e **o mesmo valor bit a bit para
  `budget = 401, 419, 439`**, inclusive em 439, cujo incumbente é diferente
  (`0x1.dbffbbb8204a5p-3` contra `0x1.e55cb2a0abe3cp-3`). O `argmin` é `tau[0,1]`,
  célula que nenhuma formiga pode alcançar. Consumidores verificados por grep:
  apenas `tests/test_aco.py:251-252`, uso legítimo.
- **Veredito adversarial:** CONFIRMADO, reprodução exata bit a bit. Classe `D2`
  mantida.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, restringindo o mínimo às células estruturalmente
  alcançáveis, ou removendo o campo. `final_tau_max` é informativo e deve ser
  mantido.
- **Onda:** B.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff **esperado não zero** no campo de
  diagnóstico, que a impressão digital compara.

#### F4-5. O teste do estado parcial ancora uma igualdade exata que só vale no caso de três unidades

- **Frente:** F4.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 15, "o ACO calcula o custo parcial dos
  mesmos quatro componentes usados pelo guloso", reforçada pela docstring de
  `_PartialConstructionState` (`aco.py:79-80`). **Fonte: normativa.** O documento
  exige equivalência da grandeza matemática, e não poderia exigir igualdade bit a
  bit entre duas ordens de somatório distintas.
- **Previsto:** equivalência dos quatro componentes.
- **Código:** `tests/test_aco.py:114-127`, sobre
  `src/metaheuristica/aco.py:109-128` e `src/metaheuristica/objective.py:163-181`.
  `_PartialConstructionState` acumula os cortes linha a linha, na ordem da
  construção, enquanto `_evaluate_partial_assignment` soma o triângulo superior da
  submatriz induzida numa única redução. O teste afirma `incremental == common`,
  igualdade exata dos sete campos, e passa apenas porque o caso escolhido tem três
  unidades e `K=2`.
- **Evidência:** reprodução exata bit a bit. Em 1.033 comparações sobre
  `artesp_rmsp_150` com prefixos de 3 a 60 unidades e `K` de 3 a 8, **639 coincidem
  bit a bit e 394 não**, com diferença absoluta máxima de `2,220e-16`. Cenário
  concreto: em `artesp_rmsp_20`, `K=3`, rótulos `(0,0,0,1,0,0,0,2)`,
  `c_territorial` incremental é `0x1.98dba3ca1543ap-1` contra
  `0x1.98dba3ca1543bp-1` do guloso, um ULP, embora `total_cost` coincida em
  `0x1.2b0c95cf8295ep-1`.
- **Veredito adversarial:** CONFIRMADO, reprodução exata bit a bit. Classe `M2`
  mantida.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, trocando a igualdade exata por tolerância explícita ou por
  comparação contra a construção anterior. O risco concreto é de falsa segurança: o
  teste como está induz a onda de correção a usar um **oráculo errado**. O oráculo
  correto para a construção do ACO é a própria construção antes da mudança,
  comparada por `float.hex()`.
- **Onda:** B, no mesmo commit de F4-1, que é a correção que este teste bloquearia.
- **Situação:** fechado com teste novo em `tests/test_aco.py`, no commit `d297377`, do
  pacote B5. `tests/test_aco.py:114-127`,
  que afirmava `incremental == common`, igualdade exata dos sete campos sobre um único
  caso de três unidades e `K=2`, foi substituído por
  `test_incremental_partial_state_is_equivalent_within_tolerance`, parametrizado em três
  casos de instâncias reais, `artesp_rmsp_20` com `K=3` e `K=5` e `artesp_rmsp_60` com
  `K=8`, comparando os sete campos com `abs=1e-12` e com docstring registrando por que a
  equivalência é da grandeza e não dos bits: o estado parcial acumula os cortes linha a
  linha, na ordem da construção, e `_evaluate_partial_assignment` soma o triângulo
  superior numa única redução. O oráculo bit a bit da construção, que é o oráculo correto
  para o ACO, passou a ser
  `test_batched_choice_costs_reproduce_the_reference_bit_by_bit`, contra
  `evaluate_choice` preservado intacto. **Poder discriminante:** o teste novo falharia
  sob a forma anterior, a igualdade exata, porque o dossiê mede 394 divergências em 1.033
  comparações, com diferença absoluta máxima de `2,220e-16`.
  **Passo G.** Classe prevista `M2`; classe observada `M2`; a observação **bate** com a
  previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, e o zero é do conjunto completo dos 42
  cenários conferido no Passo F de `d297377`, junto de F4-1. A alteração deste achado é
  restrita a `tests/test_aco.py` e não tem efeito próprio sobre o caminho científico.
  **Passo G.** Diff previsto zero; diff observado zero; a observação **bate** com a
  previsão. O oráculo foi validado por marcador. A revisão independente do pacote **não**
  refez a impressão digital, por determinação do pacote de revisão.

### 3.5. Frente F5 - Busca Tabu

**Nota de identificadores.** O relatório de origem, `frente-6-report.md`, numera os
achados como "Achado 1" a "Achado 7", sem prefixo de frente. Este registro os renomeia
para `F5-1` a `F5-7`, preservando a ordem, para que a referência cruzada entre frentes
seja inequívoca. O mapeamento é direto: `F5-n` é o "Achado n" do relatório de origem.
Quem rastrear para trás deve buscar "Achado n" em `frente-6-report.md`.

Sete achados, zero refutados, sete confirmados, nenhuma reclassificação. Todas as
premissas conferidas palavra por palavra na fonte. As oito verificações
obrigatórias foram confirmadas por execução instrumentada, e não por leitura: o
código da Busca Tabu é fiel ao que os documentos prescrevem nos oito pontos.
Nenhum `D1`.

**Hipótese dirigida da frente refutada, e a refutação é do coordenador.** A
suposição de que `n_viz=20` vencer no mínimo da grade significasse que a Busca
Tabu se beneficia de trajetória mais longa **caiu**. O mecanismo se confirmou
exatamente, com `accepted_moves = piso((orçamento - 1 - reinícios)/n_viz)`, dando
2997,5 com `n_viz=20` contra 1199,0 com `n_viz=50`, razão 2,5 igual a 50/20. Mas
na grade inteira `n_viz=50` tem custo médio **menor**, 0,137696 contra 0,140428,
vencendo 35 de 60 pares casados, e a vantagem de `n_viz=20` só existe com
`n_stag=100`. O auditor descartou explicitamente a frase do coordenador "o ótimo
pode estar abaixo de 20" por falta de base, e descartou também a explicação
alternativa por taxa ótima de reinício, porque a taxa não ordena as células.

**Um mutante muda o resultado de referência em 7% e passa os 254 testes.** Ver o
achado 5. O código atual está correto; o que falta é proteção.

#### Achado F5-1. A grade de tuning não separa qualidade da vizinhança de frequência efetiva de reinício

- **Frente:** F5.
- **Classe:** `L1`.
- **Premissa:** `docs/experiments.md:429-431` (seção 12.1), "Além do resumo por
  configuração, foram calculados efeitos marginais por nível de hiperparâmetro.
  Eles são exclusivamente descritivos e não são interpretados como efeitos
  causais"; `docs/experiments.md:436-447` (seção 12.2), com
  `neighborhood_size=20` congelado e custo médio 0,126415;
  `docs/formulation.md:597-599` (seção 14), `n_stag` denominado em movimentos
  aceitos; `docs/experiments.md:243-249` (seção 8), orçamento em avaliações da
  função objetivo. **Fonte: normativa**, as quatro citações conferidas fiéis.
- **Previsto:** que os doze pontos da grade fossem comparáveis entre si e que a
  configuração vencedora indicasse a melhor combinação dentro dos níveis avaliados.
- **Código:** `src/metaheuristica/tabu.py:255` (`_sample_moves`), `:305`
  (`accepted_moves += 1`) e `:313-318` (contagem de estagnação e reinício). Cada
  iteração consome exatamente `n_viz` avaliações e aceita exatamente um movimento,
  logo o comprimento da trajetória é rigidamente
  `piso((orçamento - 1 - reinícios)/n_viz)`. Como `n_stag` é denominado em
  movimentos aceitos e o orçamento em avaliações, `n_viz` é a **taxa de câmbio**
  entre as duas unidades e fixa a frequência de reinício por orçamento: o mesmo
  `n_stag=50` significa reiniciar a cada 1/60 do orçamento com `n_viz=20` e a cada
  1/24 com `n_viz=50`.
- **Evidência:** todos os números recalculados diretamente dos Parquet pelo
  verificador, reproduzindo **exatamente**, inclusive no quarto decimal.

  | Recorte | Média `n_viz=20` | Média `n_viz=50` | Delta pareado | Vitórias de 20 | Teste de sinais |
  |---|---:|---:|---:|---:|---:|
  | Grade inteira | 0,140428 | 0,137696 | +0,0027314 | 25 de 60 | `p = 0,2451` |
  | Só `n_stag=50` | 0,151865 | 0,141600 | +0,010265 | 8 de 30 | `p = 0,0161` |
  | Só `n_stag=100` | 0,128990 | 0,133792 | -0,004802 | 17 de 30 | `p = 0,5847` |

  Diagnóstico por célula reproduzido linha a linha. Razão de trajetória
  `2997,5/1199,0 = 2,5006`, isto é `50/20`. Melhoras globais por orçamento:
  **108,333** com `n_viz=20` contra **124,633** com `n_viz=50`. Os três piores
  pontos da grade são exatamente as três células `n_viz=20` com `n_stag=50`,
  recalculadas como `(5,20,50) = 0,155116`, `(20,20,50) = 0,152680` e
  `(10,20,50) = 0,147798`, sem nenhuma outra célula se intrometendo. Contraste
  marginal de `stagnation_limit` de 0,015341 contra 0,002732 de
  `neighborhood_size`, isto é **5,615 vezes** maior, e de sinal contrário ao nível
  vencedor. Identidades `accepted_moves == piso((budget-1-restarts)/n_viz)` e
  `iterations_completed == accepted_moves + restarts` reproduzidas nas 6 execuções
  do piloto sem exceção.
- **Veredito adversarial:** CONFIRMADO, classe `L1` mantida, com **correção
  obrigatória de uma frase**.
- **Divergência auditor / verificador:** a frase "a vizinhança maior compra escolha
  local melhor por avaliação, e não é a trajetória mais longa que explica a
  vitória" é atribuição causal **positiva** que a própria lógica central do achado,
  o confundimento estrutural, proíbe. É a mesma proibição que o achado usa
  corretamente para recusar a história da taxa ótima de reinício. **Apenas a
  negativa está provada**, isto é que trajetória mais longa não explica a vitória.
  A positiva passa a ser hipótese não testável nesta grade. O coordenador
  apresentou a positiva como resultado ao usuário e isso precisa ser corrigido com
  ele. Nada mais do achado muda.
- **Decisão:** registro apenas, publicando **só a negativa**. Qualquer afirmação
  futura sobre o ótimo de `n_viz` exige antes redenominar `n_stag` como fração do
  orçamento ou dos movimentos aceitos esperados, em novo ciclo de tuning.
- **Onda:** registro apenas.
- **Situação:** fechado sem ação de código.
- **Impressão digital:** pendente.

#### Achado F5-2. A cadeia de desempate com tolerância não é ordem total, e o vencedor pode não ser o melhor movimento admissível

- **Frente:** F5.
- **Classe:** `D3`.
- **Premissa:** `docs/formulation.md` seção 14, "O melhor movimento admissível da
  amostra é sempre aceito, inclusive quando piora a solução corrente. Empates de
  custo usam a solução canônica e depois a tupla do movimento". **Fonte:
  normativa.**
- **Previsto:** o movimento aceito é o de menor custo entre os admissíveis, com
  empates resolvidos por cadeia determinística e independente da ordem de
  amostragem.
- **Código:** `src/metaheuristica/tabu.py:153-163` (`_candidate_is_better`) e
  `:166-175` (`_select_best_admissible`, redução sequencial).
  `_candidate_is_better` trata como empate qualquer diferença até
  `COST_TOLERANCE = 1e-12`, relação que não é transitiva, e a redução sequencial na
  ordem da amostra faz o resultado depender dessa ordem.
- **Evidência:** reproduzido bit a bit com o código real. Três candidatos com
  custos `A = 0,0`, `B = 0,7e-12`, `C = 1,4e-12` e chaves canônicas decrescentes:
  em `[A,B,C]` vence `C`; em `[C,B,A]` vence `A`; em `[A,C,B]` vence `B`. Três
  ordens da mesma amostra dão três vencedores diferentes, e em `[A,B,C]` o vencedor
  `C` é estritamente pior que `A` **pelo próprio comparador do código**, porque
  `0,0 < 1,4e-12 - 1e-12`, o que contradiz diretamente a premissa. Em 299 amostras
  instrumentadas em `artesp_rmsp_20` com `K=5`, nenhuma iteração apresentou empate
  de custo dentro de `1e-12` entre candidatos admissíveis.
- **Veredito adversarial:** CONFIRMADO, reproduzido bit a bit. Classe `D3`
  mantida.
- **Divergência auditor / verificador:** nenhuma. Dois atenuantes que o próprio
  auditor registrou e que o verificador manteve: isto **não** quebra
  reprodutibilidade, porque a ordem da amostra é determinada pelo `Generator`
  semeado; e a situação exige três custos separados por algo entre 0 e `2e-12` em
  valores da ordem de 0,13, isto é diferenças relativas próximas de `1e-11`.
- **Decisão:** corrigir, tornando o comparador uma ordem total, por comparação
  exata de custo seguida da cadeia de desempate.
- **Onda:** B, com prioridade. Mesma família de A9 do PSO, mas aqui a premissa é
  normativa e explícita, o que é a razão de a classe não cair para `L1`.
- **Situação:** fechado com correção de código e um teste novo, parametrizado em
  seis casos, no commit do pacote B8. `_candidate_is_better` passa a comparar custo
  por igualdade exata,
  seguida da cadeia de desempate por chave canônica e depois por tupla do
  movimento, o que torna o comparador ordem total e o resultado de
  `_select_best_admissible` invariante à ordem da amostra. O teste novo apresenta
  a amostra do verificador, com custos `0,0`, `0,7e-12` e `1,4e-12` e chaves
  canônicas decrescentes, nas **seis** permutações, e falhava em quatro delas
  antes da correção, reproduzindo os três vencedores diferentes registrados na
  evidência. **A9 e o seu espelho `gpu/pso.py:70-80` não foram tocados**, porque
  A9 é `L1` e fica fora deste pacote, e os dois seguem idênticos entre si, sem
  divergência de critério introduzida entre CPU e GPU. `arbitrate_best` também não
  foi tocado, conforme o aviso de risco do pacote.
  **Registro de uma asserção que documentava o defeito:**
  `tests/test_tabu.py::test_candidate_selection_accepts_aspiration_and_uses_tie_breaks`
  exigia que, entre `0,2` e `0,2 + 5e-13`, vencesse o de **maior** custo por ter
  chave canônica menor, isto é a suíte registrava o descarte de uma melhora real
  como comportamento correto. A asserção foi corrigida para exercitar o desempate
  na igualdade exata e ganhou o caso que confere que a melhora de `5e-13` passa a
  decidir, nas duas ordens de apresentação.
  **Passo G.** Classe prevista `D3`; classe observada `D3`; a observação **bate**
  com a previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, dentro do zero conferido no
  conjunto completo dos 42 cenários no Passo F do pacote B8. **Passo G.** Diff
  previsto zero; diff observado zero; a observação **bate** com a previsão. O zero
  confirma a evidência do registro, de que em 299 amostras instrumentadas nenhuma
  iteração apresentou empate de custo dentro de `1e-12` entre candidatos
  admissíveis.

#### Achado F5-3. Reinício que consome a última avaliação do orçamento não é contabilizado

- **Frente:** F5.
- **Classe:** `D2`.
- **Premissa:** `docs/experiments.md` seções 10.3 e 8: o esforço computacional por
  execução é registrado por métricas de diagnóstico, e "o algoritmo é interrompido
  imediatamente depois da avaliação que consome o limite". **Fonte: normativa.**
- **Previsto:** que o diagnóstico refletisse o número de reinícios efetivamente
  realizados.
- **Código:** `src/metaheuristica/tabu.py:232-250`, especificamente as linhas 247 e
  248, que ficam **depois** do bloco `try/finally` que envolve
  `context.evaluate(restart)`. Quando `EvaluationLimitReached` é lançada ali, o
  `finally` publica os diagnósticos mas as duas linhas não executam.
- **Evidência:** reproduzido exatamente pelo verificador com `run_tabu` real,
  `tiny_manual.json`, `RunConfig(k=4, seed=5, budget=120)`,
  `TabuConfig(tabu_tenure=5, neighborhood_size=20, stagnation_limit=100)`:
  `evaluations = 120`, isto é 1 solução inicial mais 119 reinícios efetivamente
  executados, mas `restarts = 118` e `iterations_completed = 118`. Subcontagem de
  exatamente 1.
- **Veredito adversarial:** CONFIRMADO, reproduzido exatamente. Classe `D2`
  mantida, sem efeito em custo, solução ou checkpoints, e a identidade
  `iterations_completed == accepted_moves + restarts` continua válida porque os dois
  contadores são omitidos juntos.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, movendo os incrementos para dentro do `finally` ou para
  antes da avaliação. É a mesma família de A5 do PSO, na fronteira do orçamento.
- **Onda:** B, junto de A5.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff **esperado não zero** em campo de
  diagnóstico.

#### Achado F5-4. Canonicalização e validação repetidas por candidato

- **Frente:** F5.
- **Classe:** `M1`.
- **Premissa:** `docs/experiments.md` seções 25 e 10.3 tratam o tempo computacional
  como resultado medido, e a seção 12.1 o usa no terceiro desempate do tuning.
  **Fonte: normativa**, mas sem prescrição explícita sobre custo por avaliação: a
  premissa frágil é interna ao código.
- **Previsto:** nada explícito. A chave canônica do candidato já é calculada dentro
  do avaliador.
- **Código:** `src/metaheuristica/tabu.py:285-287` recalcula
  `canonicalize_solution` do zero em laço Python sobre as `N` posições, duplicando
  o que `evaluator.py:105` (`solution_key`) já fez; somam-se `tabu.py:133`,
  `objective.py:197` e `tabu.py:107`, três validações adicionais.
- **Evidência:** contagens reproduzidas **exatamente** pelo verificador, que
  precisou corrigir o próprio harness antes de a contagem bater, porque
  `from X import Y` liga um nome próprio no módulo importador. Em
  `artesp_rmsp_150`, `K=5`, `seed=77`, `budget=15000`: **29.998 canonicalizações**
  em 15.000 avaliações, isto é 1,9999 por avaliação, e **60.749 validações**, isto
  é 4,0499 por avaliação. `results/tables/pilot_runs.parquet` confirma
  `runtime_seconds = 68,963908` para `artesp_rmsp_150, k=3, budget=150000`.
- **Veredito adversarial:** CONFIRMADO, contagens reproduzidas exatamente. Classe
  `M1` mantida.
- **Divergência auditor / verificador:** os percentuais de tempo, 18,9% e 16,0%,
  dependem de máquina e **não foram re-medidos**; a evidência que sustenta a
  classificação são as contagens de chamada, e essas reproduzem exatamente. O
  verificador registrou também que o piloto tem `K` em `{3,8}` para `N=150` e não
  `K=5`, logo a comparação com os 68,96 s é de coerência de ordem de grandeza e não
  reprodução do mesmo ponto, o que já está implícito no texto do achado e não é
  erro.
- **Decisão:** **não corrigir antes do benchmark.** A severidade real é baixa: com
  540 execuções de Busca Tabu, eliminar a canonicalização duplicada economizaria da
  ordem de dezenas de minutos numa campanha dominada pelo ACO. A recomendação
  explícita do auditor, mantida, é não mexer, porque alteraria a impressão digital
  sem ganho relevante.
- **Onda:** C, e somente se a Onda A já tiver disparado o ramo alterado por outra
  razão.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado **não** zero, o que é exatamente
  a razão de a decisão ser adiar.

#### Achado F5-5. O contador do prazo tabu é um canal de regressão silenciosa no algoritmo de referência

- **Frente:** F5.
- **Classe:** `D3`, com `M2` como classe secundária.
- **Premissa:** `docs/formulation.md` seção 14, "o retorno `move(i, destino,
  origem)` permanece tabu pelos próximos `L_tabu` movimentos aceitos";
  `docs/experiments.md` seção 12.2, que exige novo ciclo de tuning para qualquer
  alteração dos parâmetros congelados, e seção 29, verificações antes do benchmark
  final. **Fonte: normativa.**
- **Previsto:** que a denominação do prazo em movimentos aceitos fosse propriedade
  protegida, de modo que uma alteração dela fosse detectada antes de contaminar a
  comparação entre as três metaheurísticas.
- **Código:** `src/metaheuristica/tabu.py:253`, `:264-266` e `:306-310`, os três
  pontos onde `diagnostics.accepted_moves` alimenta a memória tabu. **A
  implementação é correta.** A única asserção existente sobre o prazo é
  `tests/test_tabu.py:131-141`, que exercita `_TabuMemory` isolada com
  `register(accepted_moves=1, tenure=3)`, isto é **com o contador fornecido pelo
  próprio teste**. Nenhum teste percorre `_tabu_search` verificando qual contador
  chega a `is_tabu` e a `register`. O verificador buscou em todo `tests/` por
  `tenure`, `is_tabu` e `.register(` fora de `test_tabu.py` e confirmou que a guarda
  é única.
- **Evidência:** quatro mutantes reconstruídos pelo verificador, com diff conferido
  contra o `tabu.py` real, carregados por `sys.path.insert` explícito, e todos os
  valores batendo **dígito a dígito** com o relatório.

  | Variante | Suíte | Custo final | `float.hex()` | Aspirações | Reinícios | Tabu avaliados |
  |---|---|---:|---|---:|---:|---:|
  | baseline | 254 de 254 | 0,12904819343271928 | `0x1.084a6b5336172p-3` | 9 | 27 | 2027 |
  | B | **254 de 254** | **0,12006716303716230** | **`0x1.ebcb8ba916fccp-4`** | 12 | 26 | 1829 |
  | B linha | 254 de 254 | 0,12904819343271928 | `0x1.084a6b5336172p-3` | 9 | 27 | 2027 |
  | A | 254 de 254 | 0,12904819343271928 | `0x1.084a6b5336172p-3` | 9 | 27 | 2027 |
  | C | 254 de 254 | 0,12904819343271928 | `0x1.084a6b5336172p-3` | 9 | 27 | 2027 |

  O mutante **B**, que troca `accepted_moves` por `iterations_completed` nos três
  pontos, **altera o resultado do algoritmo de referência em cerca de 7%** e passa
  os 254 testes sem uma única falha. O mutante **B linha**, a mesma troca
  realinhada, é **inerte**, o que confirma por experimento que a propriedade não é
  verificável por comportamento: só um teste que inspecione o argumento passado a
  `is_tabu` a protege, e esse teste não existe.
- **Veredito adversarial:** CONFIRMADO no resultado. Classe `D3` com `M2`
  secundária mantida. Não há defeito de resultado hoje.
- **Divergência auditor / verificador:** nenhuma nos números. O verificador
  levantou um **achado adicional sobre o método de evidência do próprio relatório**,
  que não invalida este achado porque ele reproduziu tudo com método corrigido e
  validado por marcador. Esse achado sobre a auditoria está na seção 6.
- **Decisão:** corrigir, criando teste que inspecione o argumento passado a
  `is_tabu` e a `register` ao longo de `_tabu_search`. Como a Busca Tabu é a régua
  contra a qual ACO e PSO são julgados, uma regressão dessa natureza entraria na
  campanha sem alarme e a impressão digital só a detectaria depois de já ter sido
  regravada.
- **Onda:** B, com prioridade, junto de F2-06, que aponta a mesma região por outro
  ângulo. Ver a conexão 5 da seção 5.
- **Situação:** fechado com um teste novo, no commit do pacote B12. Nenhuma linha de
  `src/metaheuristica/tabu.py` foi alterada, porque o código está correto; o que
  faltava era proteção. O teste percorre `_tabu_search` inteira com `purge`,
  `is_tabu` e `register` instrumentados por `monkeypatch`, cobrindo os **três**
  pontos do achado, e assevera que a série recebida por `register` é exatamente
  `1, 2, ..., accepted_moves` e que toda consulta e toda expurga recebem o número
  de movimentos aceitos até ali. A execução escolhida tem reinícios, e é isso que
  separa as duas séries, porque `iterations_completed` passa a ser estritamente
  maior que `accepted_moves`.
  **Vereditos de morte dos quatro mutantes da frente F5.** Reexecutados pelo método
  validado: cópia do repositório inteiro para fora da árvore, execução do `pytest`
  **de dentro da cópia**, nunca por `PYTHONPATH`. A validação por marcador foi feita
  antes de interpretar qualquer sobrevivência: um `raise` inserido em
  `tabu.py` da cópia interrompeu a coleta, provando que o módulo carregado é o da
  cópia e não o do repositório. A execução de referência é a mesma do dossiê,
  `artesp_rmsp_60` com `K=5`, seed 0, orçamento 60000 e parâmetros congelados
  `tabu_tenure=10, neighborhood_size=20, stagnation_limit=100`, com comparação por
  `float.hex()`.

  | Variante | Suíte antes | Suíte agora | Custo de referência | `float.hex()` | Veredito |
  |---|---|---|---:|---|---|
  | baseline | 254 de 254 | **399 de 399** | 0,12904819343271928 | `0x1.084a6b5336172p-3` | - |
  | B | 254 de 254 | **1 falha** | 0,12006716303716230 | `0x1.ebcb8ba916fccp-4` | **morto** |
  | B linha | 254 de 254 | **1 falha** | 0,12904819343271928 | `0x1.084a6b5336172p-3` | **morto** |
  | A | 254 de 254 | **1 falha** | 0,12904819343271928 | `0x1.084a6b5336172p-3` | **morto** |
  | C | 254 de 254 | **4 falhas** | 0,12904819343271928 | `0x1.084a6b5336172p-3` | **morto** |

  Os quatro morrem. B e B linha caem pelo teste do contador, A pelo teste da
  fronteira exata da aspiração e C pelo teste do ramo de amostra inteiramente tabu,
  mais dois outros testes deste pacote e mais
  `tests/test_audit_fingerprint.py`, porque o ramo que C suprime é percorrido pelo
  cenário `tabu:tiny_manual:2:frozen`, conforme a correção de alcance registrada em
  F5-6. Os cinco custos de referência e os
  diagnósticos reproduzem **dígito a dígito** a tabela medida em `ca5b81f`, o que
  confirma de passagem que os pacotes B7 e B8 não alteraram o resultado do
  algoritmo de referência. A régua contra a qual ACO e PSO são julgados passa a
  estar protegida.
  **Passo G.** Classe prevista `D3` com `M2` secundária; classe observada `D3` com
  `M2` secundária; a observação **bate** com a previsão. Sem reclassificação, e o
  Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, por construção, porque o pacote só
  acrescenta teste e não altera `src/`. Conferida no subconjunto `tabu:*` e depois
  no **conjunto completo dos 42 cenários** como controle, ambos com "impressão
  digital idêntica". **Passo G.** Diff previsto zero; diff observado zero; a
  observação **bate** com a previsão.

#### Achado F5-6. Fronteira da aspiração e dois dos três ramos de reinício sem cobertura

- **Frente:** F5.
- **Classe:** `M2`.
- **Premissa:** `docs/formulation.md` seção 14 fixa que a aspiração só libera por
  melhora maior que `1e-12` e que o reinício também ocorre quando toda a amostra
  está tabu sem aspiração; `docs/experiments.md` seção 29 exige verificações antes
  do benchmark final. **Fonte: normativa.**
- **Previsto:** que uma regressão nessas duas regras fosse detectada pela suíte.
- **Código:** `tests/test_tabu.py:151-160` e `:208-217`; os ramos não cobertos
  estão em `src/metaheuristica/tabu.py:256-258` (amostra vazia) e `:299-302`
  (amostra inteiramente tabu). O teste de aspiração exercita `5e-13`, dentro da
  tolerância, e `0,4` contra `0,5`, muito fora; o ponto onde a estritez do `<`
  decide, melhora de exatamente `1e-12`, não é testado.
- **Evidência:** mutantes A e C reproduzidos bit a bit pelo verificador, ambos
  passando 254 de 254 e ambos **inertes** em resultado, com custo final
  `0x1.084a6b5336172p-3` e diagnósticos idênticos ao baseline. A inércia tem
  explicação, e é ela que mantém o achado em `M2` e não em `D3`: o mutante A só se
  manifesta quando a margem é exatamente `1e-12`, e o mutante C só se manifesta se
  a amostra ficar inteiramente bloqueada, o que é impossível com os parâmetros
  congelados, porque a memória guarda no máximo `L_tabu = 10` entradas vivas, medido
  em exatamente 10, contra 20 movimentos distintos na amostra; o máximo observado de
  bloqueados numa amostra foi 5, em 2.998 amostras.
- **Veredito adversarial:** CONFIRMADO, mutantes reproduzidos bit a bit. Classe
  `M2` mantida.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, com teste na fronteira exata de `1e-12` e testes para os
  dois ramos de reinício descobertos.
- **Onda:** B, junto de F2-07, que cobre a mesma fronteira pelo lado da suíte.
- **Situação:** fechado com três testes novos, no commit do pacote B12, sem
  alteração de `src/`. O primeiro fixa a fronteira exata da aspiração: com melhora
  de **exatamente** `1e-12` a reversão **não** é liberada, e com `2e-12` é, que é o
  único ponto onde trocar `<` por `<=` muda a resposta. Os outros dois cobrem os
  dois ramos de reinício descobertos. O de **amostra vazia** é construído com `K`
  igual ao número de unidades, situação em que cada lote tem uma única unidade e
  todo movimento esvaziaria a origem; o de **amostra inteiramente tabu** estreita a
  amostra até o bloqueio total ocorrer, e a asserção exige que o bloqueio valha para
  amostra não trivial, de pelo menos dois candidatos, para não passar por um caso
  degenerado de amostra unitária.
  **Correção de alcance do ramo de amostra inteiramente tabu.** O campo Evidência
  acima conclui que a condição é impossível sob os parâmetros congelados, apoiado em
  dez entradas vivas na memória contra vinte movimentos distintos na amostra. Essa
  medição é de `artesp_rmsp_60` e **não se transporta para o `tiny_manual`**, onde
  `neighborhood_size = 20` é limitado pelo número de movimentos válidos, que é
  quatro em quatro unidades com `K=2`. Medido no cenário
  `tabu:tiny_manual:2:frozen` da própria impressão digital, com os parâmetros
  congelados e a seed reservada: **cinco** amostras ficaram inteiramente tabu, todas
  com quatro candidatos, em vinte e seis amostras. O ramo é, portanto, inalcançável
  **na grade ARTESP** e alcançável no `tiny_manual` sob congelamento. A consequência
  prática apareceu na validação por mutação: o mutante C, inerte na execução de
  referência, **quebra também `tests/test_audit_fingerprint.py`**, porque altera o
  resultado daquele cenário. Isto refina o alcance descrito na Evidência, não muda a
  classe, que segue `M2` por ser fresta de cobertura, e não muda veredito algum de
  impressão digital, porque nenhum código de `src/` foi alterado neste pacote. Os dois ramos são provados percorridos por
  marcador, e não por inferência a partir dos diagnósticos: `_sample_moves` e
  `_select_best_admissible` são instrumentados e as ocorrências contadas. Mutantes A
  e C mortos, conforme a tabela de vereditos em F5-5.
  **Observação registrada durante a construção do teste do ramo de amostra vazia.**
  O número de reinícios ficou em 98 contra 99 amostras vazias, folga de exatamente
  uma unidade. **Isto não é achado novo**: é F5-3, já registrado e ainda aberto, o
  reinício que consome a última avaliação do orçamento e não é contabilizado porque
  `diagnostics.restarts` é incrementado depois do `try/finally` que envolve a
  avaliação. A asserção do teste foi escrita como intervalo, e **não** fixa a folga,
  justamente para não bloquear a correção de F5-3.
  **Passo G.** Classe prevista `M2`; classe observada `M2`; a observação **bate** com
  a previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, dentro do zero conferido no
  subconjunto `tabu:*` e no conjunto completo dos 42 cenários no Passo F do pacote
  B12. A alteração é restrita a `tests/test_tabu.py`. **Passo G.** Diff previsto
  zero; diff observado zero; a observação **bate** com a previsão.

#### Achado F5-7. `is_tabu` usa o próprio contador como valor padrão, apoiado em invariante não declarado

- **Frente:** F5.
- **Classe:** `M3`.
- **Premissa:** `docs/formulation.md` seção 14 define a memória tabu por prazo de
  expiração em movimentos aceitos; `docs/experiments.md` seção 28 exige código
  auditável e reprodutível. **Fonte: normativa** quanto às duas; a citação de
  `AGENTS.md` que o relatório também faz é **regra interna do repositório**, não
  documento metodológico do projeto, e o achado não depende dela.
- **Previsto:** uma consulta de proibição que responda "não proibido" quando o
  movimento não está na memória.
- **Código:** `src/metaheuristica/tabu.py:85-86`,
  `return self._expirations.get(move, accepted_moves) > accepted_moves`. Usa
  `accepted_moves` como sentinela de ausência, o que devolve o resultado certo para
  ausência mas faz a função responder "proibido" para qualquer contador
  estritamente menor que a expiração registrada, inclusive contadores anteriores ao
  próprio registro. A correção depende de um invariante não escrito nem asseverado:
  o contador é monótono não decrescente e nunca é rebobinado dentro de um segmento
  entre reinícios.
- **Evidência:** reproduzido exatamente. Com
  `mem.register(TabuMove(3,1,2), accepted_moves=7, tenure=4)`, o esperado por
  leitura da especificação é proibido apenas para `a` em `{7,8,9,10}`; o observado é
  proibido para `a` em `{0,...,10}`. A janela correta aparece quando se restringe a
  consulta a `a >= 7`, que é o que ocorre no laço real.
- **Veredito adversarial:** CONFIRMADO, reproduzido exatamente. Classe `M3`
  mantida, sem efeito em resultado hoje.
- **Divergência auditor / verificador:** nenhuma. A confiança do auditor já era
  baixa quanto a impacto.
- **Decisão:** corrigir, usando sentinela explícita em vez do próprio contador. Uma
  futura alteração que zerasse ou reduzisse o contador em reinício reintroduziria
  proibições fantasmas sem que nenhuma asserção reclamasse.
- **Onda:** C.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero.

### 3.6. Frente F6 - orquestração do benchmark e congelamento

Doze achados. Onze confirmados integralmente, um refutado na consequência central
e rebaixado de `D3` para `D2` (F6-09). Nenhum `D1`. **É a frente de maior risco
operacional da auditoria**: sem correção, a campanha de 35 a 40 horas não chega ao
fim pelo caminho documentado.

**Linha de base reconferida de forma independente antes de qualquer teste.**
`verify_freeze_manifest` aceita e cobre 52 arquivos protegidos, `protected_paths`
devolve os mesmos 52, e `validate_benchmark_partition` devolve exatamente
1.620 cenários, 5 lotes, 324 por lote, 270 subgrupos, 54 por lote, 6 por subgrupo.
Todo o exercício ocorreu em clone descartável, com `results/raw/benchmark`
permanecendo inexistente na árvore real.

**Barreira de lote: parcialmente incorreta.** A aritmética está certa e foi
confirmada por execução, e lacuna e temporário são de fato rejeitados. O auditor
ainda testou e **refutou a própria suspeita** de que a guarda de temporários fosse
vazia por causa de nomes ocultos, porque `pathlib.Path.glob` casa dotfiles no
Python 3.14. Mas faltam três das oito regras que a seção 29.2 atribui à barreira:
ela não confere proveniência uniforme, não detecta artefato estranho no diretório
de resultados, e a guarda de segunda falha é apagada por sucesso posterior.
Portanto o caso não é "sem teste porém correta", e sim **sem teste e com regras
faltantes**.

**Ausência de `D1` afirmada.** Nenhum dos doze achados altera um número já
produzido: `results/raw/benchmark` não existe e a campanha nunca rodou. Vários
passariam a `D1` se materializados durante a campanha, e é isso que os mantém em
`D3`.

#### F6-01. A barreira de um lote suja a worktree e impede oficialmente os lotes seguintes e o encerramento

- **Frente:** F6.
- **Classe:** `D3`. É o achado de maior gravidade da frente.
- **Premissa:** `docs/experiments.md` seção 29.2, "O lote seguinte só é liberado
  após a barreira confirmar 324 resultados, 32.400 checkpoints, proveniência,
  congelamento, recursos, ausência de lacunas, duplicatas e temporários"; seção
  28.1, "Execuções oficiais exigem Git disponível e worktree limpa". **Fonte:
  normativa.** O `README.md`, que documenta a sequência `execute`, `retry`,
  `barrier` por lote e `finalize` sem nenhum passo de commit entre lotes, é **regra
  interna do repositório**, e é citado como evidência do fluxo pretendido.
- **Previsto:** que aprovar a barreira do lote `n` liberasse a execução oficial do
  lote `n+1`, e que os cinco lotes e o encerramento formassem sequência executável.
- **Código:** `experiments/benchmark_validation.py:94-98` grava
  `results/tables/benchmark_batches/batch-01_runs.parquet` e
  `batch-01_checkpoints.parquet` em diretório **versionado e não ignorado**;
  `.gitignore:21-29` ignora `results/raw/`, `results/failures/` e
  `results/operational/` mas **não** `results/tables/`. A partir daí
  `capture_provenance` recusa toda execução, e o mesmo bloqueio atinge `readiness`,
  `finalize` e `consolidate_campaign` (`consolidation.py:150-154`, com
  `allow_dirty=False`).
- **Evidência:** reproduzido diretamente pelo verificador. `git check-ignore`
  negativo para `results/tables/` e `git ls-files results/tables` mostra que o
  diretório já é versionado. Gravando os dois arquivos da barreira,
  `git status --porcelain --untracked-files=all` deixa de ser vazio e
  `capture_provenance(root, allow_dirty=False)` recusa com a mensagem exata
  "worktree suja; use --allow-dirty para execução não oficial".
- **Veredito adversarial:** CONFIRMADO, e **mais grave** que o texto original
  sugeria. Classe `D3` mantida.
- **Divergência auditor / verificador:** o relatório descreve "duas saídas
  disponíveis ao operador, ambas ruins". Isso é impreciso e o bloqueio real é
  **total**: `_parser()` de `experiments/run_benchmark.py:39-49` **não define flag
  `--allow-dirty` alguma**, e `execute_operation` é sempre chamado com o padrão
  `False`, sem override pela CLI oficial. A única via alternativa é abandonar
  `run_benchmark` e usar `experiments.run`, que não passa por `execute_operation` e
  portanto **não grava o diário operacional por rodada** que `_validate_operations`
  exige, logo nem essa via produziria um lote 2 capaz de passar pela barreira. Ou
  seja: existe **zero** saída pelo fluxo oficial documentado, não duas saídas ruins.
- **Decisão:** corrigir, com precedência máxima entre os `D3`. Duas opções:
  acrescentar `results/tables/benchmark_batches/` ao `.gitignore`, ou mover as
  tabelas de barreira para `results/operational/`, que já é ignorado.
- **Onda:** B, primeira posição.
- **Situação:** fechado no commit do pacote B2. Das duas opções do registro foi
  adotada a segunda, mover as tabelas da barreira para
  `results/operational/benchmark_batches/`, e não acrescentar `results/tables/` ao
  `.gitignore`, porque `results/tables/` contém artefatos oficiais versionados e
  vários deles estão em `FIXED_PROTECTED`. O `.gitignore` recebeu, ainda assim,
  `results/tables/benchmark_batches/` como rede contra execução por versão antiga
  do código. **Oráculo:** `tests/test_benchmark_validation.py`
  `test_barrier_writes_outside_versioned_tables_and_leaves_worktree_clean` roda a
  barreira do lote 1 sobre repositório Git temporário, com cópia do `.gitignore`
  real, e exige `git status --porcelain --untracked-files=all` vazio. Antes da
  correção o teste falhava com
  `?? results/tables/benchmark_batches/batch-01_checkpoints.parquet` e
  `?? results/tables/benchmark_batches/batch-01_runs.parquet`. Como a linha nova do
  `.gitignore` sozinha faria o oráculo passar, o teste também exige que o relatório
  aponte para `results/operational/` e que `results/tables/benchmark_batches` não
  exista.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os 42
  cenários devolveu "impressão digital idêntica" com saída 0, antes e depois do
  lote. O pacote vive em `experiments/`, `.gitignore`, `README.md`,
  `docs/` e `tests/`, fora do caminho científico executado pelo oráculo.

#### F6-02. O congelamento é gerado sobre worktree suja, sem revalidar comportamento e sem confrontar o commit do piloto

- **Frente:** F6.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 29, "Depois da aprovação do piloto, um
  manifesto registra hashes do código, automação, instâncias, configurações,
  dependências e artefatos. A execução do benchmark é recusada se qualquer item
  protegido ou o ambiente divergir"; seção 30, princípio de congelamento
  experimental; seção 29, itens 9 e 10, "o tuning foi congelado" e "nenhuma
  alteração de algoritmo ocorre durante os experimentos principais". **Fonte:
  normativa.**
- **Previsto:** que o manifesto congelasse o estado de código que o piloto aprovou,
  de modo que o congelamento fosse evidência de que o benchmark roda sobre o
  comportamento validado.
- **Código:** `experiments/benchmark_freeze.py:77-100`, em especial `:82-83`
  (aceita o veredito gravado em `pilot_validation.json`), `:85`
  (`capture_provenance(root, allow_dirty=True)`, hardcoded), `:90`
  (`"pilot_commit": validation["campaign_commit"]`) e `:93`. Contraste em
  `experiments/pilot_validation.py:217-218`, onde o piloto exige
  `len(commits) == 1 and None not in commits`.
- **Evidência:** o verificador reproduziu a **cadeia inteira** com mutação real em
  `src/metaheuristica/objective.py`, dobrando `weights.affinity * c_affinity` em
  `_evaluate_aggregates`. `generate_freeze_manifest` aceitou sobre worktree suja;
  `verify_freeze_manifest` aceitou o novo manifesto; depois de commitar a mutação,
  `readiness` devolveu `ready = True` e `git_dirty = False`; e só
  `_validate_result` contra um artefato real do piloto recusou, com "reavaliação
  divergente". Confirmado por `grep -rn "pilot_commit"` que o campo é escrito uma
  única vez, em `benchmark_freeze.py:90`, e **nunca lido**. E, o mais importante:
  **a divergência já existe hoje no repositório íntegro**, com o manifesto
  registrando o piloto em `5a9b805` e o `HEAD` do ramo em `739fb3d`, sem que nada
  compare os dois.
- **Veredito adversarial:** CONFIRMADO, cadeia completa reproduzida. Classe `D3`
  mantida, com a mesma ressalva: **passa a `D1`** no instante em que uma alteração
  de comportamento for efetivamente congelada, porque as 40 horas produziriam
  números de um código nunca validado pelo piloto.
- **Divergência auditor / verificador:** nenhuma. A hipótese dirigida 1 do dossiê
  foi confirmada **e agravada**.
- **Decisão:** corrigir. Recusar geração sobre worktree suja; confrontar
  `pilot_commit` com o `HEAD`; e revalidar comportamento com `_validate_result`
  contra ao menos um artefato do piloto antes de assinar o manifesto.
- **Onda:** B, com prioridade, junto de F6-03 e de F2-04, que é a cobertura ausente
  do mesmo mecanismo.
- **Situação:** fechado com correção de código e cinco testes novos, nos commits do
  pacote B1. As três correções estão no mesmo bloco de `generate_freeze_manifest`,
  antes da montagem e da escrita do manifesto, de modo que a recusa acontece sem
  assinar nada: a proveniência passou a ser capturada com `allow_dirty=False`; o
  `campaign_commit` do veredito é confrontado com o `git_commit` do `HEAD` e a
  divergência recusa com "commit do piloto diverge do HEAD"; e
  `_revalidate_pilot_behaviour`, função nova no mesmo módulo, carrega os
  documentos oficiais do piloto, exige que a proveniência deles seja uniforme e
  igual ao `campaign_commit` gravado, e reexecuta `_validate_result` de
  `experiments/pilot_validation.py` contra os dezoito artefatos reais, em cerca de
  0,5 s. O campo `pilot_commit`, antes escrito e nunca lido, passou a ser a
  variável confrontada. Testes: recusa sobre worktree suja, recusa por
  `pilot_commit` divergente do `HEAD` e recusa, já dentro da revalidação, quando o
  carregamento dos documentos oficiais não encontra resultado do piloto e levanta
  `resultado ausente`, o que fixa que a revalidação é alcançada antes da
  assinatura; os três com asserção de que o manifesto **não** foi escrito;
  mais a cadeia demonstrada pela auditoria, com `evaluate_solution` substituída por
  variante que dobra `weights.affinity * c_affinity`, sobre os artefatos reais do
  repositório, que recusa com "reavaliação divergente" e cujo controle positivo,
  sem a substituição, aceita. O quinto teste fixa a guarda de proveniência, que
  recusa veredito cujo `campaign_commit` não é o dos dezoito documentos. A guarda
  de lista vazia que existia no primeiro commit foi removida no segundo, por ser
  inalcançável: `_load_official_documents` levanta `resultado ausente` antes de
  poder devolver lista vazia.
- **Impressão digital:** zero, conforme previsto.

#### F6-03. A verificação do congelamento não recalcula o escopo protegido e não vê arquivo novo

- **Frente:** F6.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 29, "A execução do benchmark é recusada
  se qualquer item protegido ou o ambiente divergir"; seção 30. **Fonte:
  normativa.**
- **Previsto:** que o conjunto protegido, definido por `protected_paths` como todo
  `*.py` sob `src/metaheuristica/` e sob `experiments/` mais uma lista fixa, fosse
  comparado com o estado corrente, de modo que qualquer divergência de escopo,
  inclusive de composição, fosse recusada.
- **Código:** `experiments/benchmark_freeze.py:117` usa `expected_protected` vindo
  de `manifest.get("protected_files")` em `:114`, e **nunca** chama
  `protected_paths(root)`, que é definido em `:48-54` e chamado apenas em `:93`,
  dentro do gerador. O escopo de proteção fica congelado no instante da geração.
- **Evidência:** reproduzido por três vias independentes, com controles positivo e
  negativo na mesma bateria. `protected_paths` **reconhece** os arquivos novos como
  protegidos, e ainda assim a verificação os ignora: novo `.py` sob `experiments/`
  aceitou sem alarme; novo `.py` sob `src/metaheuristica/` aceitou sem alarme;
  controle de remoção dos dois aceitou; arquivo protegido **modificado** recusou com
  "congelamento divergente"; arquivo protegido **removido** recusou com "arquivo
  protegido ausente"; controle final restaurado aceitou.
- **Veredito adversarial:** CONFIRMADO, incluindo a alegação central solicitada
  para verificação independente. Classe `D3` mantida. A gravidade contida, dano de
  auditoria e não de resultado, porque importar o módulo novo tipicamente exige
  editar um arquivo já protegido, é leitura **correta e não inflação**.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, chamando `protected_paths(root)` na verificação e recusando
  divergência de composição. **O manifesto hoje não pode ser apresentado como
  evidência de que o código é idêntico ao congelado, apenas de que aqueles 52
  arquivos são idênticos**, e isso precisa constar do relatório final se o
  congelamento for citado como garantia.
- **Onda:** B, com prioridade, junto de F6-02.
- **Situação:** fechado com correção de código e cinco testes novos, nos commits do
  pacote B1. `verify_freeze_manifest` passou a chamar `protected_paths(root)` e a
  comparar a composição do escopo corrente com as chaves gravadas antes de
  qualquer hash, recusando com "escopo protegido divergente" e nomeando a
  diferença simétrica; o cotejo de hashes passou a correr sobre o escopo
  recalculado. Testes: arquivo `.py` novo sob `experiments/`, módulo `.py` novo sob
  `src/metaheuristica/` e módulo removido do escopo dinâmico, os três recusados
  com o caminho nomeado na mensagem. Antes da correção os três devolviam "DID NOT
  RAISE". A remoção de arquivo da lista fixa continua recusando por "arquivo
  protegido ausente", porque `FIXED_PROTECTED` pertence ao escopo exista ou não em
  disco, e essa distinção está fixada por teste próprio. **Segundo commit do
  pacote:** a revisão apontou que o bloco irmão, o de `pilot_artifacts`, tinha o
  mesmo defeito e não recebera a correção. Ele reidratava o conjunto das chaves
  gravadas, de modo que remover uma entrada do manifesto e adulterar o arquivo
  correspondente em disco era aceito sem alarme. A verificação passou a comparar
  a composição gravada com `PILOT_ARTIFACTS` e a recusar com "escopo de artefatos
  do piloto divergente" antes de conferir conteúdo, com teste que devolvia "DID
  NOT RAISE" sem a correção. A mensagem de recusa por composição passou também a
  acumular o que `FIXED_PROTECTED` perdeu em disco, porque a lista fixa não
  aparece na diferença simétrica e, com duas causas simultâneas, a recusa nomeava
  apenas uma.
- **Impressão digital:** zero, conforme previsto.
- **Confirmação empírica no repositório íntegro, portão de revisão do pacote B1:**
  `uv run python -m experiments.freeze_benchmark verify --workers 16` passou a
  recusar com saída 2 e mensagem `erro: escopo protegido divergente:
  ['experiments/audit_fingerprint.py']`. O arquivo é legítimo, criado por esta
  auditoria, e a recusa é o comportamento correto do mecanismo corrigido: **é a
  primeira vez que a verificação enxerga um arquivo novo dentro do escopo
  protegido**, o que confirma a segunda hipótese da frente F6 sobre o repositório
  real e não apenas em fixture. A recusa de composição precede a de conteúdo, de
  modo que a divergência de hashes preexistente, medida no mesmo estado como
  `congelamento divergente: ['experiments/benchmark_freeze.py',
  'experiments/pilot_validation.py', 'src/metaheuristica/pso.py']`, deixa de ser a
  mensagem apresentada. O manifesto **não** foi regenerado; a renovação é da
  Tarefa 20.
- **Nota de anexação de evidência futura:** o Passo 9 da Tarefa 14 é uma sonda
  cujo resultado se anexa a **este** achado, e não a F6-02. O ruling de preflight
  registrado no diário nomeou "F6-2", mas por conteúdo a hipótese de que arquivo
  novo não é detectado é F6-03. Correção registrada aqui.

#### F6-04. A política de tentativa única é baseada em estado, e um sucesso posterior apaga o bloqueio da segunda falha

- **Frente:** F6.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 29.2, "cada ID falho pode ser repetido
  uma única vez. Uma segunda falha bloqueia a campanha". **Fonte: normativa.**
- **Previsto:** que a segunda falha de um ID fosse estado terminal da campanha,
  isto é que o bloqueio fosse propriedade do **histórico** do ID.
- **Código:** `experiments/benchmark_operations.py:148-155`, em especial `:153-154`;
  `experiments/storage.py:152-156`, onde `classify` devolve `COMPLETED` sempre que o
  resultado existe e é válido, sem olhar o registro de falha;
  `experiments/benchmark_validation.py:79`. O bloqueio é recalculado a cada chamada
  a partir do estado corrente. `record_failure` nunca apaga o registro e
  `_publish_success` nunca o consulta, de modo que o histórico permanece em disco,
  íntegro e ignorado. O caminho para a terceira tentativa não é `run_benchmark`,
  cujo `retry` recusa IDs com duas tentativas, e sim a CLI genérica
  `experiments.run`, que trata a finalidade `benchmark` de forma explícita em
  `run.py:69-72` e não impõe limite de tentativas.
- **Evidência:** reproduzido pelo verificador com cenário real e registro de falha
  fabricado com dois `attempts`: estado do ID com resultado **e** falha dupla é
  `completed`; `blocked_failures` com o resultado publicado devolve `()`; e o
  controle negativo, removendo o resultado, devolve o ID bloqueado.
- **Veredito adversarial:** CONFIRMADO, classe `D3` mantida. A ressalva do próprio
  auditor, de que o caminho para a terceira tentativa não é o fluxo oficial, é
  **precisa e não enfraquece o achado**: o bloqueio depende de convenção de uso da
  CLI, não de invariante de dados.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, fazendo `blocked_failures` consultar o histórico de
  tentativas independentemente do estado corrente.
- **Onda:** B, com prioridade, junto de F2-05, que é a cobertura ausente da mesma
  guarda.
- **Situação:** fechado no commit do pacote B2. `blocked_failures` passou a
  consultar o histórico de tentativas em `results/failures/`, independentemente do
  estado corrente, e `campaign_blocked_failures` aplica a mesma regra à campanha
  inteira. A recusa passou a valer também na CLI genérica: `experiments.run`, com
  finalidade `benchmark`, interrompe `execute` com `campanha bloqueada por segunda
  falha` antes de qualquer execução. **Evidência:** com duas falhas registradas e o
  resultado removido, a CLI genérica devolvia 0 e reexecutava o ID bloqueado
  (`{"selected": 1, "succeeded": 1}`), que era a terceira tentativa; passou a
  devolver 2 sem executar nada. Com o resultado publicado sobre duas falhas,
  `blocked_failures` devolvia `()` e passou a devolver o ID, e a barreira do lote
  recusa com `lote contém segunda falha`.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os 42
  cenários devolveu "impressão digital idêntica" com saída 0, antes e depois do
  lote. O pacote vive em `experiments/`, `.gitignore`, `README.md`,
  `docs/` e `tests/`, fora do caminho científico executado pelo oráculo.

#### F6-05. A barreira do lote não confere proveniência nem artefato estranho, e não registra o congelamento que diz confirmar

- **Frente:** F6.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 29.2, a lista dos oito itens que a
  barreira deve confirmar. **Fonte: normativa.**
- **Previsto:** que a barreira, e não a linha de comando que a invoca, confirmasse
  os oito itens, e que o relatório assinado por ela servisse de evidência auditável.
- **Código:** `experiments/benchmark_validation.py:72-115`, cuja lista de
  importações em `:10-19` **não inclui** `verify_freeze_manifest` nem
  `capture_provenance`, e cujo relatório em `:99-112` não contém commit, hash de
  congelamento nem estado da worktree; `experiments/run_benchmark.py:186-190`, onde
  o ramo `barrier` da CLI chama `verify_freeze_manifest` e nada mais. Dos oito
  itens, a barreira confirma seis.
- **Evidência:** reproduzido. Um `alien_result.json` colocado em
  `results/raw/benchmark/` não é detectado por `_temporary_files` nem por
  `blocked_failures`; quem acusa é `readiness`, o preflight que roda **uma única
  vez antes** da campanha, e a consolidação final, que roda **depois** de 40 horas.
  Entre esses dois instantes, que é exatamente quando os artefatos são criados,
  nenhuma barreira de lote olha o diretório.
- **Veredito adversarial:** CONFIRMADO na formulação estrita. Classe `D3` mantida.
- **Divergência auditor / verificador:** uma imprecisão textual. A frase
  "proveniência não é conferida em nenhum ponto do benchmark" é **forte demais**:
  `validate_document` exige que `document.get("provenance")` seja um `dict` e a
  barreira exige `document.get("official") is True`, logo proveniência **é**
  minimamente checada por documento individual. A alegação sustentada é mais
  estreita e continua verdadeira: **não há verificação de que os 324 documentos do
  lote compartilham o mesmo `git_commit`**, ao contrário do piloto.
- **Decisão:** corrigir, movendo congelamento e proveniência para dentro de
  `validate_batch`, acrescentando varredura do diretório de resultados, e gravando
  commit e hash de congelamento no relatório do lote. Somado a F6-01, a barreira do
  lote 2 em diante será necessariamente assinada com worktree suja ou com commit
  intermediário não previsto, e o relatório não registrará nem uma coisa nem outra.
- **Onda:** B, com prioridade, junto de F6-01 e F6-04.
- **Situação:** fechado no commit do pacote B2. `validate_batch` passou a chamar
  `verify_freeze_manifest` e `capture_provenance(allow_dirty=False)` por si, antes
  de qualquer leitura de resultado, a varrer o diretório de resultados por artefato
  estranho ao roteiro da campanha inteira, e a exigir `git_commit` uniforme entre os
  324 documentos, que era a alegação estreita e verdadeira do verificador. O
  relatório do lote passou a registrar `git_commit`, `git_dirty`, `results_commit`,
  `freeze_sha256` e `workers`. A CLI repassa `--workers` à barreira e não duplica
  mais a verificação. **Oráculo:** casos negativos de worktree suja, congelamento
  divergente, artefato estranho e proveniência não uniforme, mais o controle
  positivo que confere os campos novos contra o `HEAD` e o hash do manifesto.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os 42
  cenários devolveu "impressão digital idêntica" com saída 0, antes e depois do
  lote. O pacote vive em `experiments/`, `.gitignore`, `README.md`,
  `docs/` e `tests/`, fora do caminho científico executado pelo oráculo.

#### F6-06. A morte de um único worker converte os cenários pendentes em falhas com a tentativa única já consumida

- **Frente:** F6.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 29.2, "cada ID falho pode ser repetido
  uma única vez. Uma segunda falha bloqueia a campanha. Uma interrupção externa não
  conta como falha"; seção 28.1, "Retomadas ignoram resultados válidos, tentam
  novamente falhas". **Fonte: normativa.**
- **Previsto:** que apenas a falha própria de um cenário consumisse a tentativa
  única, e que eventos externos não fossem contabilizados como falha do cenário.
- **Código:** `experiments/execution.py:219-222`, `:224-233` e `:239-252`;
  `experiments/storage.py:159-177`. Quando um processo filho morre por sinal, o
  `ProcessPoolExecutor` entra em estado quebrado e atribui `BrokenProcessPool` a
  todos os futuros pendentes; `BrokenProcessPool` é subclasse de `Exception`, cai no
  mesmo ramo de uma falha algorítmica, e gera um `record_failure` por cenário
  atingido. `KeyboardInterrupt`, a única exceção tratada de outra forma, só cobre
  sinal recebido pelo **processo principal**.
- **Evidência:** reproduzido pelo verificador em espelho fiel do laço real, com
  `spawn`, `ProcessPoolExecutor`, `as_completed`, 4 workers reais, 8 tarefas reais e
  um worker morrendo por `os._exit(1)`, cujo efeito observável é idêntico a
  `SIGKILL` por OOM killer: **8 de 8** cenários pendentes viraram
  `record_failure(BrokenProcessPool)`, com `succeeded=0`.
- **Veredito adversarial:** CONFIRMADO por reprodução direta. Classe `D3` mantida,
  com a confiança "alta para o mecanismo, média para a probabilidade".
- **Divergência auditor / verificador:** **o alcance de 324 precisa ser
  qualificado.** `select_benchmark` devolve `expected = 6 if algorithm is not None
  else 324` (`benchmark_batches.py:81`). A invocação documentada no `README.md` para
  a B11-E é **por subgrupo**, que submete **6** cenários por vez. O alcance real de
  um único evento depende de qual comando estava em voo: até **6** para um `execute`
  de subgrupo, que é o padrão documentado; até o número de IDs atualmente falhos
  para `retry`, que opera sem filtro; ou até **324** caso o operador invoque
  `execute --batch N` sem filtros, o que a CLI permite mas o `README.md` não
  exemplifica. O "324" do relatório vale só para esses dois últimos casos. Esta
  correção é a metade de risco da conexão 3 da seção 5.
- **Decisão:** corrigir, distinguindo `BrokenProcessPool` de falha algorítmica e não
  consumindo a tentativa única em morte de worker.
- **Onda:** B, com prioridade. **A decisão precisa ser tomada junto com a escolha
  entre o caminho documentado por subgrupo e o caminho saturado por lote, e não
  isoladamente.** Ver a conexão 3 da seção 5.
- **Situação:** fechado no commit do pacote B3. `BrokenProcessPool` ganhou ramo
  próprio, antes do ramo genérico de `Exception`, que chama `record_interrupted`,
  encerra o lote e devolve `interrupted = True`. `record_interrupted` é função nova
  de `experiments/storage.py`, irmã de `record_failure`, que grava em
  `results/failures/` com `kind: "interrupted"` em arquivo próprio, e não no
  registro de falha, de modo que o histórico de tentativas permanece intacto;
  `classify` continua devolvendo `PENDING` para cenário apenas interrompido. A
  assinatura adotada é `record_interrupted(paths, scenario, error)`, por simetria
  com `record_failure`, e não a do adendo, que passava a configuração.
  **Evidência:** o teste com quatro workers reais, oito cenários e um worker
  chamando `os._exit(1)` devolvia
  `ExecutionSummary(succeeded=0, failed=8, interrupted=False)`, isto é oito
  `record_failure` por morte de um worker; passou a devolver `failed=0`,
  `interrupted=True`, nenhum registro de falha, os oito cenários em `pending` e a
  retomada concluindo os oito.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os 42
  cenários devolveu "impressão digital idêntica" com saída 0, antes e depois do
  lote. O pacote vive em `experiments/`, `.gitignore`, `README.md`,
  `docs/` e `tests/`, fora do caminho científico executado pelo oráculo.

#### F6-07. Resultado não oficial válido é tratado como concluído pela retomada, e o preflight não olha o que já existe

- **Frente:** F6.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 28.1, "somente um documento válido e com
  hash esperado é considerado concluído" e "Autorizações para estado sujo ou não
  versionado existem apenas para desenvolvimento e tornam o resultado não oficial".
  **Fonte: normativa.**
- **Previsto:** que a marcação de não oficial fosse operante.
- **Código:** `experiments/storage.py:47-88` (`validate_document` **não** consulta o
  campo `official`), `:152-156` (`classify` devolve `COMPLETED`),
  `experiments/execution.py:78-81` (a retomada só reexecuta o que não está
  `COMPLETED`). A única consulta ao campo em todo o pipeline é
  `experiments/benchmark_validation.py:45`, dentro da barreira. O preflight conta
  mas não inspeciona (`run_benchmark.py:82-86` e `:109`).
- **Evidência:** reproduzido de ponta a ponta pelo verificador, sujando
  `docs/experiments.md`, que está fora do escopo protegido:
  `verify_freeze_manifest` aceitou; `execute` sem `--allow-dirty` recusou; o
  resultado gravado com `--allow-dirty` saiu com
  `official = False | motivos = ['dirty_worktree']`; `validate_document` **aceitou**
  o documento não oficial; `classify` devolveu `completed`; e `build_plan`
  selecionou **zero** cenários para reexecução.
- **Veredito adversarial:** CONFIRMADO, classe `D3` mantida. A retomada realmente
  adota em silêncio um resultado de desenvolvimento como concluído.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, fazendo `classify` recusar documento com
  `official is not True` quando a finalidade for `benchmark`.
- **Onda:** B, com prioridade.
- **Situação:** fechado no commit do pacote B3. `classify` passou a recusar
  documento com `official is not True` quando a finalidade do cenário é
  `benchmark`, devolvendo `PENDING`, de modo que a retomada reexecuta o cenário; a
  recusa não alcança piloto e tuning, o que é fixado por teste. O preflight passou
  a inspecionar em vez de apenas contar: `inspect_existing_results` valida cada
  documento existente e `readiness` recusa com `resultados não oficiais` além de
  `resultados inesperados`. **Evidência:** um resultado gerado sem versionamento
  era classificado como `completed` e `build_plan` selecionava zero cenários;
  passou a ser `pending` e a ser selecionado, e volta a `completed` quando o
  documento oficial o substitui. Consequência de manutenção registrada: o ensaio
  reduzido de `tests/test_benchmark_dry_run.py` passou a rodar sobre repositório
  versionado e limpo, porque resultado não oficial não conclui mais cenário de
  benchmark.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os 42
  cenários devolveu "impressão digital idêntica" com saída 0, antes e depois do
  lote. O pacote vive em `experiments/`, `.gitignore`, `README.md`,
  `docs/` e `tests/`, fora do caminho científico executado pelo oráculo.

#### F6-08. O identificador por conteúdo não cobre os dois Parquet que carregam todos os dados do objetivo

- **Frente:** F6.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 28.1, "Cada cenário recebe SHA-256
  calculado sobre algoritmo, hiperparâmetros, instância, `K`, seed, orçamento, pesos
  e cache". **Fonte: normativa.** A verificação obrigatória sobre cobertura do
  identificador é **metodologia da auditoria**, do dossiê da frente, e o achado não
  depende dela.
- **Previsto:** que o identificador determinasse univocamente o resultado esperado.
- **Código:** `experiments/scenarios.py:70-90`: o `payload` que alimenta
  `sha256(canonical_json(payload))` inclui apenas `instance.name`, `instance.path` e
  o SHA-256 do **JSON** da instância. Em
  `src/metaheuristica/instances.py:135-136`, `units_path` e `pairs_path` são
  **literais fixos**, `artesp_rmsp_150_units.parquet` e
  `artesp_rmsp_150_pair_metrics.parquet`, carregados para `size` 20, 60 ou 150
  indistintamente. O JSON contém apenas nome, contagem e a lista de `unit_ids`; toda
  a demanda, produção e métricas de par vêm dos dois Parquet, que não entram no
  identificador.
- **Evidência:** multiplicando por 1,5 a coluna `passengers_day` de
  `artesp_rmsp_150_units.parquet`, o `scenario_id` permaneceu
  `0d38a0e99c53d61b...`, o `instance.sha256` permaneceu `9616ea96d24eaf19` e o
  estado permaneceu `completed`: **identificador idêntico sobre dados de objetivo
  diferentes**. As três camadas de contenção foram todas confirmadas: os dois
  Parquet são versionados, logo alterá-los suja a worktree; estão em
  `FIXED_PROTECTED` (`benchmark_freeze.py:36-37`), logo o congelamento acusa com
  "congelamento divergente"; e a barreira reavalia o objetivo em `_validate_result`.
- **Veredito adversarial:** CONFIRMADO por leitura direta e completa. Classe `D3`
  mantida, não `D1`, porque o dano é contido pelas três camadas.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, incluindo os dois Parquet no payload do identificador, e
  corrigir a premissa da seção 28.1, que está incompleta. Registrar que a última
  camada **não existe no encerramento**: `finalize_benchmark` chama
  `consolidate_campaign`, que apenas revalida com `validate_document` e não reavalia
  o objetivo, de modo que uma troca de dados depois da assinatura do primeiro lote
  deixaria a tabela final misturando conjuntos se as duas primeiras camadas fossem
  contornadas.
- **Onda:** B, junto de F2-15, que aponta o mesmo buraco pelo lado da cobertura. Ver
  a conexão 7 da seção 5.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero, porque muda apenas o
  identificador; **atenção**, se o `scenario_id` mudar, os 42 cenários da impressão
  digital mudam de nome e o oráculo precisa ser gerado depois desta correção, não
  antes.

#### F6-09. A barreira de recursos é irreversível e o remédio previsto pelo documento é recusado pela própria CLI

- **Frente:** F6.
- **Classe:** `D2`, rebaixada de `D3`.
- **Premissa:** `docs/experiments.md` seção 29, "Falha exclusivamente de recursos
  reduz os workers e exige repetição integral"; seção 29.2. **Fonte: normativa**,
  com a ressalva do próprio auditor de que o contexto imediato da seção 29 é o
  piloto, o que deixa espaço para a interpretação de que ela não se aplica à B11-E.
- **Previsto:** que uma falha exclusivamente de recursos fosse recuperável pela
  redução do número de workers seguida de repetição.
- **Código:** `experiments/benchmark_validation.py:61-68`;
  `experiments/run_benchmark.py:142-143`, que recusa qualquer valor diferente de 16;
  `experiments/benchmark_freeze.py:112-113`, que recusa qualquer valor diferente de
  `approved_workers`.
- **Evidência:** as duas guardas foram confirmadas por execução: a CLI com
  `--workers 12` erra com "benchmark oficial exige exatamente 16 workers", e
  `verify` com `workers=12` recusa com "quantidade de workers diverge do
  congelamento". **Mas a consequência central é falsa.** O verificador fabricou um
  resumo de recursos reprovado e reexecutou a mesma operação: `resource_paths` é
  determinístico por `f"{selection.name}_{round_name}"` e `execute_operation` grava
  com `atomic_write_json`, que é **sobrescrita**. Reexecutando com os mesmos 16
  workers, sem descartar resultado e sem trocar `output_root`, a segunda chamada
  rodou com `selected=0`, isto é sem recômputo científico algum, e ainda assim
  invocou o `ResourceMonitor` e regravou o resumo com `passed = True`. Como
  `_validate_operations` lê `session["resource_summary"]`, o mesmo caminho de
  arquivo, para **todas** as sessões já registradas, a nova gravação aprovada faz a
  barreira aceitá-las **retroativamente**.
- **Veredito adversarial:** **REFUTADO na consequência central, reclassificado de
  `D3` para `D2`.** A afirmação de "lote permanentemente sem barreira possível" é
  **falsa**: o caminho de recuperação existe, é acessível pela CLI oficial, e não
  exige reduzir workers nem abrir novo `output_root`, desde que a causa da
  reprovação tenha sido transitória, que é precisamente a hipótese da seção 29.
- **Divergência auditor / verificador:** a consequência central cai. O fato residual
  e verdadeiro é que CLI e congelamento impedem literalmente reduzir o número de
  workers, o que diverge do texto literal da seção 29, mas isso é lacuna de
  implementação contra documentação sem efeito catastrófico e sem efeito em
  resultado científico. **Nota lateral do verificador, registrada e não promovida a
  achado novo:** o mecanismo que possibilita a recuperação, reescrever
  silenciosamente o resumo de recursos de uma sessão já registrada, é em si um
  problema de integridade do diário operacional, porque se perde o registro fiel de
  que uma sessão específica reprovou em recursos.
- **Decisão:** corrigir a divergência textual, alinhando a seção 29 ao que a CLI
  permite, ou permitindo a redução de workers com renovação de manifesto. A nota
  lateral sobre integridade do diário entra como item associado, não como achado
  novo, porque não passou por verificação adversarial independente.
- **Onda:** B, sem prioridade.
- **Situação:** fechado no commit do pacote B4, por alinhamento textual. Das duas
  opções da decisão foi adotada a primeira, alinhar a seção 29 ao que a CLI
  permite, e não permitir a redução de workers com renovação de manifesto: a
  segunda abriria um caminho de renovação de manifesto no meio da campanha, que é
  exatamente o que F6-02 acabou de fechar. A frase "Falha exclusivamente de
  recursos reduz os workers e exige repetição integral" passou a dizer que o número
  de workers é fixado em 16 pelo congelamento, que a CLI e a verificação do
  manifesto recusam qualquer outro valor, e que a recuperação passa por nova sessão
  registrada. **Item associado B7 absorvido:** a mesma redação diz que a
  recuperação nunca se dá por sobrescrever o resumo de recursos de uma sessão já
  registrada, porque o diário operacional precisa preservar o registro fiel de que
  uma sessão reprovou em recursos. **Oráculo:**
  `test_workers_other_than_sixteen_are_refused_in_both_gates` fixa as duas recusas,
  a da CLI e a do congelamento, de modo que texto e código não voltem a divergir.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os 42
  cenários devolveu "impressão digital idêntica" com saída 0, antes e depois do
  lote. O pacote vive em `experiments/`, `.gitignore`, `README.md`,
  `docs/` e `tests/`, fora do caminho científico executado pelo oráculo.

#### F6-10. A escrita atômica de Parquet não sincroniza o diretório após a substituição

- **Frente:** F6.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 28.1, "Resultados individuais são
  publicados atomicamente"; seção 29.2, sobre a barreira registrar as tabelas do
  lote com hash. **Fonte: normativa.**
- **Previsto:** publicação atômica e durável também para as tabelas consolidadas.
- **Código:** `experiments/consolidation.py:26-39` (`_atomic_parquet`) contra
  `experiments/storage.py:109-128` (`atomic_write_json`), que chama
  `_fsync_directory(path.parent)` em `:125`. `_atomic_parquet` cria o temporário no
  mesmo diretório, grava, sincroniza o arquivo e usa `os.replace`, o que garante
  atomicidade, mas **nunca** sincroniza o diretório após a troca. A sincronização é
  ainda feita sobre descritor aberto em modo somente leitura, o que funciona no
  Linux mas é frágil como contrato.
- **Evidência:** confirmado por leitura completa das duas rotinas do próprio
  projeto, uma delas correta. Sem o `fsync` do diretório, o `rename` pode não estar
  persistido caso o sistema perca energia imediatamente após a troca, apesar de o
  arquivo já estar durável: é comportamento POSIX documentado. Cenário: o relatório
  do lote, gravado por `atomic_write_json`, sobrevive; as duas tabelas podem não
  sobreviver, deixando um relatório aprovado que aponta para arquivos inexistentes.
- **Veredito adversarial:** CONFIRMADO por comparação direta de código. Classe `D3`
  mantida, com confiança média, porque o efeito exige perda de energia ou falha do
  sistema de arquivos. O verificador registrou explicitamente que o achado é
  inerentemente não reproduzível por execução e que **o relatório é transparente
  sobre essa limitação**.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, acrescentando `_fsync_directory(path.parent)` após o
  `os.replace` em `_atomic_parquet`.
- **Onda:** B.
- **Situação:** fechado com correção de código e dois testes novos, no commit do
  pacote B14. `_atomic_parquet` passou a chamar `_fsync_directory(path.parent)`
  logo depois do `os.replace`, reusando a rotina de `experiments/storage.py` em
  vez de duplicá-la, e o descritor de sincronização do arquivo passou a ser
  aberto em `rb+`, porque sincronizar sobre descritor somente leitura funciona no
  Linux mas não é contrato garantido. **Oráculo:** como o efeito observável exige
  perda de energia, o teste instrumenta `os.fsync` e classifica cada descritor
  com `stat.S_ISDIR`, asseverando a sequência arquivo e depois diretório.
  **Evidência:** sem a correção a sequência observada era `[False]` numa escrita
  e `[False, False]` em duas escritas sucessivas; com a correção passou a
  `[False, True]` e `[False, True, False, True]`.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os
  42 cenários devolveu "impressão digital idêntica" com saída 0, antes e depois
  do pacote. A correção vive em `experiments/`, fora do caminho dos 42 cenários.
  Classe prevista `D3`, classe observada `D3`, sem reclassificação.

#### F6-11. `ExecutionSummary.skipped` relata concluídos da campanha inteira, e o valor errado entra no diário operacional

- **Frente:** F6.
- **Classe:** `D2`.
- **Premissa:** `docs/experiments.md` seção 29.2, sobre o diário operacional que
  sustenta a barreira; seção 28.1, sobre retomadas que ignoram resultados válidos.
  **Fonte: normativa.**
- **Previsto:** que o resumo de uma execução de subgrupo descrevesse **aquela**
  execução.
- **Código:** `experiments/execution.py:256-258`, que posiciona `plan.completed` no
  terceiro campo posicional, declarado como `skipped`; `execution.py:96`, onde
  `completed` é contado sobre **todos** os 1.620 cenários e não sobre o escopo
  selecionado; consumo em `experiments/benchmark_operations.py:128`, que grava o
  valor no diário do lote.
- **Evidência:** reproduzido diretamente pelo verificador, com um subgrupo de 2
  cenários **garantidamente sem sobreposição** com os já concluídos. Esperado
  `selected=2, skipped=0`; observado
  `ExecutionSummary(expected=1620, selected=2, skipped=2, succeeded=2, failed=0,
  interrupted=False)`. `skipped=2` não descreve nada do subgrupo executado: é
  literalmente a contagem de concluídos da campanha inteira vazando para o campo
  errado.
- **Veredito adversarial:** CONFIRMADO por reprodução direta. Classe `D2` mantida:
  não há caminho de efeito sobre resultado científico, o dano é a corrupção do
  diário que a barreira lê.
- **Divergência auditor / verificador:** nenhuma. O verificador refinou o cenário,
  garantindo ausência de sobreposição, o que torna a demonstração mais limpa que a
  do relatório.
- **Decisão:** corrigir, contando `skipped` sobre o escopo selecionado.
- **Onda:** B.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero.

#### F6-12. `--allow-unversioned` mascara worktree suja e apaga o commit da proveniência

- **Frente:** F6.
- **Classe:** `D2`.
- **Premissa:** `docs/experiments.md` seção 28.1, "Execuções oficiais exigem Git
  disponível e worktree limpa. Ambiente, commit, versões, limites de threads e
  instantes UTC são registrados. Autorizações para estado sujo ou não versionado
  existem apenas para desenvolvimento e tornam o resultado não oficial". **Fonte:
  normativa.**
- **Previsto:** duas autorizações distintas, uma para estado sujo e outra para
  ausência de versionamento, com registro fiel do motivo, e commit registrado sempre
  que o Git estiver disponível.
- **Código:** `experiments/provenance.py:72-82`, o ramo `except ConfigurationError`
  que, quando `allow_unversioned` é verdadeiro, atribui `commit = None`,
  `dirty = None`, `dirty_hash = None` e o motivo `unversioned`, inclusive quando o
  repositório existe e a exceção original foi de worktree suja; exposição em
  `experiments/run.py:35`.
- **Evidência:** o verificador **executou** este caminho, que o auditor havia
  confirmado apenas por leitura. Com worktree suja e repositório Git presente e
  íntegro, `capture_provenance(root, allow_unversioned=True)` sem `allow_dirty`
  devolveu `nonofficial_reasons = ['unversioned']`, `git_commit = None` e
  `dirty_sha256 = None`. Por leitura de `provenance.py:54-106`: o commit é obtido
  com sucesso na linha 62 **antes** de qualquer checagem de sujeira, e o bloco
  descarta o commit já obtido.
- **Veredito adversarial:** CONFIRMADO por reprodução direta. Classe `D2` mantida:
  não contamina campanha oficial, porque a marcação de não oficial continua correta
  e a barreira recusa em `benchmark_validation.py:45`, mas poda rastreabilidade
  diagnóstica disponível.
- **Divergência auditor / verificador:** nenhuma no conteúdo; o verificador **elevou
  a evidência** de leitura para execução, o que o auditor havia declarado como
  limitação sua.
- **Decisão:** corrigir, separando os dois ramos de exceção e preservando commit e
  `dirty_sha256` quando o Git estiver disponível.
- **Onda:** B.
- **Situação:** fechado com correção de código e dois testes novos, no commit do
  pacote B14. O `try` passou a cobrir apenas as duas chamadas de Git, e a
  avaliação de sujeira migrou para um ramo `else`, de modo que `unversioned` fica
  reservado ao caso em que não há repositório. `--allow-unversioned` continua
  tolerando worktree suja, isto é nenhuma recusa nova foi criada, mas agora
  registra `git_commit`, `git_dirty` e `dirty_sha256` e o motivo `dirty_worktree`.
  **Evidência:** com repositório presente e sujo, `capture_provenance(root,
  allow_unversioned=True)` devolvia `git_commit = None` e
  `nonofficial_reasons = ['unversioned']`; passou a devolver o commit de 40
  caracteres, `git_dirty = True`, `dirty_sha256` não vazio e
  `nonofficial_reasons = ['dirty_worktree']`. O segundo teste fixa o caso sem
  repositório, que continua devolvendo `unversioned` com os três campos nulos.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os
  42 cenários devolveu "impressão digital idêntica" com saída 0, antes e depois
  do pacote. Os 42 cenários não passam por `experiments/` nem publicam
  proveniência. Classe prevista `D2`, classe observada `D2`, sem reclassificação.

### 3.7. Frente F7 - disciplina de CPU, threads e cronometragem

Dez achados, dez confirmados, zero refutados, nenhuma reclassificação. O
verificador tentou as cinco defesas do protocolo em cada achado e nenhuma se
sustentou, e reproduziu de forma independente os mecanismos e os números em nove
dos dez casos.

**Suspeita do coordenador sobre threads refutada por medição, e a refutação é boa
notícia: uma thread computacional por execução, confirmada.** Foram medidas 4
threads de sistema por processo otimizador com 16 workers em
`ProcessPoolExecutor` com `spawn`, em 91 amostras de `/proc`: 1 `python3`
principal acumulando ticks, 1 `jemalloc_bg_thd` e 2 dos pools do Arrow criados
por `pd.read_parquet` dentro de `load_artesp_instance`, as três últimas em **zero
tick** do início ao fim. Bate exatamente com `pilot_resource_summary.json`, que
registra `max_optimizer_threads` 4 e `max_active_optimizer_threads` 1. Contraprova
do auditor: sem as variáveis, o mesmo carregamento produz **66 threads**.

#### F7-1. O procedimento documentado da B11-E usa 6 dos 16 workers

- **Frente:** F7.
- **Classe:** `D3`. É o achado de maior impacto operacional da auditoria.
- **Premissa:** `docs/experiments.md` seção 24, "16 núcleos físicos, até 16
  execuções independentes simultâneas, 1 thread por execução" e "o padrão será de
  16 workers independentes, um por núcleo físico"; seção 29.2, linha 1133, "A
  estimativa resultante é de aproximadamente 33 horas ideais e de 35 a 40 horas com
  margem operacional, cerca de 6,5 a 8 horas por lote". **Fonte: normativa.** O
  `README.md:261-270` e `:284-287`, que prescrevem a invocação por subgrupo, são
  **regra interna do repositório** e constituem o procedimento cuja consequência o
  achado mede.
- **Previsto:** dezesseis execuções independentes simultâneas e duração total de 35
  a 40 horas de relógio, 6,5 a 8 horas por lote.
- **Código:** a unidade de invocação documentada é o **subgrupo**, e um subgrupo
  contém exatamente seis cenários (`experiments/benchmark_batches.py:82`,
  `expected = 6 if algorithm is not None else 324`).
  `experiments/run_benchmark.py:169-171` repassa `workers=16` a
  `execute_operation`, que chama `execute_campaign(config, workers=16,
  selected_scenarios=selected)`; em `experiments/execution.py:219-222` são
  submetidos tantos futuros quantos cenários selecionados, e o
  `ProcessPoolExecutor` cria processos **sob demanda**.
- **Evidência:** o verificador reproduziu o mecanismo central por **medição
  direta**: submeter 6 tarefas a um
  `ProcessPoolExecutor(max_workers=16, mp_context=spawn)` produz **6 processos e 6
  PIDs distintos**, nunca 16. E recalculou a aritmética do roteiro versionado
  diretamente de `results/tables/benchmark_execution_schedule.json`: 270 subgrupos;
  soma de `estimated_seconds_total` de **1.843.267,16 s = 512,02 h-CPU**, que
  dividida por 16 dá **32,00 h** ideais, compatível com as "aproximadamente 33 horas"
  do documento; soma de `estimated_seconds_per_run` de **307.211,19 s = 85,34 h**,
  isto é **17,07 h por lote**. Os quatro números batem dígito a dígito. O
  verificador confirmou também que o `README.md` **não contém em lugar nenhum** um
  exemplo de `execute --batch N` sem os três filtros: o caminho saturado existe mas
  não está documentado. Nenhuma verificação detecta a ociosidade: o único critério
  de CPU é `cpu_within_workers`, `peak_cpu <= workers * 100 * 1,10`
  (`resource_monitor.py:149`), que é um **teto** e não um piso, e 600% passa
  folgadamente sob 1760%.
- **Veredito adversarial:** CONFIRMADO sem ressalva material. Classe `D3` mantida:
  a comparação de tempo entre os três algoritmos não é alterada, porque a contenção
  é uniforme entre execuções nos dois modos; o que quebra é o planejamento da
  janela, do controle térmico e da previsão publicada.
- **Divergência auditor / verificador:** uma imprecisão de arredondamento. O
  relatório diz "fator 2,4x"; com os extremos documentados de 35 a 40 h o fator vai
  de **2,13x** (85,34/40) a **2,44x** (85,34/35), e 2,4x é o extremo favorável ao
  achado, não o ponto médio, que é cerca de 2,28x. A conclusão não muda: em
  qualquer ponto da faixa o fator está entre 2,1x e 2,4x.
- **Decisão:** decidir explicitamente entre os dois caminhos, e **junto com F6-06**,
  não isoladamente. O caminho saturado por lote é válido de ponta a ponta,
  confirmado: `select_benchmark` sem filtros devolve os 324 cenários,
  `BenchmarkSelection.name` devolve `batch-01` sem colisão, e
  `_validate_operations` usa `glob("batch-{batch:02d}_*.json")`, que casa com
  `batch-01_initial.json`. Ver a conexão 3 da seção 5.
- **Onda:** B, com prioridade. A mudança é de documentação de procedimento, não de
  código de algoritmo.
- **Situação:** fechado no commit do pacote B4, e é a materialização da decisão
  do usuário. O `README.md` passou a documentar `execute --batch N` **sem filtros**
  como caminho oficial, com a sequência `execute`, `retry`, `barrier` por lote, com
  a aritmética explícita (512,02 h-CPU, 32,00 h ideais pelo lote inteiro contra
  85,34 h pelo subgrupo, 17,07 h por lote) e com advertência sobre o raio de dano:
  uma morte de worker alcança 324 cenários em voo e não 6, e o que torna isso
  aceitável é a correção de F6-06, que registra o evento como interrupção sem
  consumir a tentativa única. A invocação por subgrupo permanece documentada como
  retomada dirigida, e a pausa entre lotes substitui a pausa entre subgrupos. A
  seção 29.2 de `docs/experiments.md` recebeu o mesmo alinhamento. **Oráculo:**
  `test_saturated_execute_covers_the_whole_batch` exercita `execute --batch 1` sem
  filtros sobre a campanha de brinquedo e confere que a seleção é o lote inteiro,
  que o diário sai como `batch-01_initial.json` cobrindo os 324 IDs e que
  `_validate_operations` o encontra.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os 42
  cenários devolveu "impressão digital idêntica" com saída 0, antes e depois do
  lote. O pacote vive em `experiments/`, `.gitignore`, `README.md`,
  `docs/` e `tests/`, fora do caminho científico executado pelo oráculo.

#### F7-2. O registro de `thread_limits` é tautológico e não pode falhar

- **Frente:** F7.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 23, linha 829, o ambiente "deverá
  registrar o número de threads permitido por processo"; seção 29, verificação 8,
  linha 1080, "não há paralelismo interno acidental". **Fonte: normativa.** A lista
  das sete variáveis é **metodologia da auditoria e restrição global do projeto
  registrada em `constraints.md`**; o achado se sustenta pela exigência normativa de
  registro, sozinha.
- **Previsto:** um registro por execução que constitua evidência de que a restrição
  valeu, isto é que permita distinguir o caso bom do ruim.
- **Código:** `experiments/worker.py:7-11` escreve as sete variáveis em
  `os.environ` no topo do módulo; `worker.py:68-75` lê de volta as mesmas sete
  chaves do mesmo `os.environ`, no mesmo processo, poucas linhas depois, e as
  devolve como `thread_limits`; `execution.py:113` copia para a proveniência e
  `pilot_validation.py:105` valida com `set(limits.values()) == {"1"}`. A asserção é
  verdadeira por construção.
- **Evidência:** o verificador confirmou por leitura que **não existe execução do
  processo otimizador em que esse campo possa divergir** de `{"1", ..., "1"}`, e que
  `pilot_validation.py:105` valida precisamente esse campo cego. O auditor mediu que
  o registro não distingue 4 threads de **66**: sem as variáveis, o mesmo
  carregamento de `artesp_rmsp_150` produz 66 threads no processo, 65 `python3` mais
  1 `jemalloc_bg_thd`.
- **Veredito adversarial:** CONFIRMADO. Nenhuma defesa aplicável: o caminho é o
  normal de toda execução, não há contenção anterior, e `D3` é adequada porque o
  monitor por `/proc` é evidência observacional independente que cobre parcialmente
  a lacuna.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, registrando o número de threads **observado**, não o valor
  declarado, ou lendo o ambiente do processo pai antes da escrita.
- **Onda:** B.
- **Situação:** fechado com correção de código e três testes novos, no commit do
  pacote B15. A captura do ambiente recebido passou a ocorrer em
  `experiments/__init__.py` **antes** do laço de escrita, exposta como
  `INHERITED_THREAD_LIMITS`; qualquer captura feita dentro de `worker.py` seria
  tautológica de novo, porque a importação de `experiments` é anterior à do
  módulo. O worker passou a devolver três registros com papéis distintos:
  `thread_limits`, que é declaração e é mantido como estava, o herdado do pai e a
  observação medida depois da otimização, com contagem de threads, contagem de
  threads com ticks acumulados e os dois contadores do Arrow. `pilot_validation`
  passou a exigir a garantia observada, `max_active_optimizer_threads` menor ou
  igual a um, e o comentário no ponto da igualdade declarada diz agora o que ela
  é. **Evidência:** com as sete variáveis em `8` no processo pai, o registro
  herdado devolve `{"8"}` e o declarado devolve `{"1"}`; movendo a captura para
  depois da escrita, o registro herdado volta a devolver `{"1"}` em qualquer
  ambiente, que é exatamente a cegueira do achado. A observação devolveu
  `threads_with_ticks` igual a 1 e `arrow_cpu_count` igual a 1.
  **Resíduo declarado:** os dois registros novos do worker não chegam ao
  documento publicado, porque `_publish_success` copia do worker apenas
  `thread_limits`, e `experiments/execution.py` não pertence à lista deste
  pacote. O campo `inherited_thread_limits` chega ao documento pelo lado da
  proveniência do orquestrador, que é onde ele documenta a configuração recebida
  pela campanha.
- **Impressão digital:** zero, conforme previsto e conforme a distinção que o
  próprio registro já antecipava. `compare --workers 16` sobre os 42 cenários
  devolveu "impressão digital idêntica" com saída 0, antes e depois do pacote. A
  previsão de diff não zero deste achado é sobre artefatos de campanha, que
  carregam proveniência; os 42 cenários não passam por `experiments/` nem
  publicam proveniência. Classe prevista `D3`, classe observada `D3`, sem
  reclassificação.

#### F7-3. O ponto de entrada da GPU não fixa nenhuma variável de thread

- **Frente:** F7.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 23, linha 829, registro do número de
  threads permitido em todo ambiente oficial; seção 26, linha 918, `S = T_CPU /
  T_GPU`. **Fonte: normativa.** A exigência de "uma thread por execução sem
  ressalva de projeto" vem de `constraints.md` e é **metodologia da auditoria**; o
  achado se sustenta pela exigência normativa de registro e pelo pareamento do
  speedup.
- **Previsto:** uma thread computacional por execução e o registro do limite em todo
  ambiente oficial, e um speedup pareado entre dois tempos medidos sob o mesmo
  regime de threading.
- **Código:** `gpu/src/metaheuristica_gpu/run.py:1-36` importa `numpy` na linha 17 e
  `metaheuristica` na linha 20 sem qualquer bloco de ambiente;
  `gpu/src/metaheuristica_gpu/environment.py:95-101` não registra thread alguma. O
  projeto `gpu/` não importa `experiments`, cuja proteção vive em
  `experiments/__init__.py:16-17`, e `src/metaheuristica/` não contém bloco de
  ambiente.
- **Evidência:** o verificador confirmou que `grep -rn "NUM_THREADS" gpu/src/` não
  devolve **nenhuma** ocorrência, e buscou também scripts de shell, `.env` e
  configuração em `gpu/` que pudessem fixar as variáveis por fora do Python: não há
  nenhum. Medição do auditor, em `artesp_rmsp_150`, `K=8`, parâmetros congelados,
  semente `20260819`: **66 threads** no processo GPU contra 4 no caminho CPU; sem
  limite o ACO faz 14,610 s e o PSO 2,437 s, com limite 14,964 s e 2,479 s, e o
  custo final é **bit a bit idêntico** nos dois regimes,
  `0x1.bd2f9037b16cap-2` e `0x1.f103a759b3702p-2`. Ou seja, em máquina ociosa a
  diferença é de 2,4% e 1,7% **a favor** do caso sem limite, isto é ruído: os
  algoritmos operam sobre vetores de `K` elementos e nunca despacham para BLAS
  multithread.
- **Veredito adversarial:** CONFIRMADO. Classe `D3` mantida, e não `D1`, porque não
  existe resultado GPU oficial e o efeito no tempo é mensuravelmente nulo nesta
  carga. O verificador não encontrou base para reclassificar.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, fixando as sete variáveis antes de qualquer importação em
  `gpu/src/metaheuristica_gpu/run.py` e acrescentando o campo de thread a
  `GpuEnvironment`. O defeito não é um tempo GPU inflado hoje, é a ausência da
  garantia e do seu registro, mais o risco de que qualquer operação futura em matriz
  densa passe a engajar 32 threads sem que nada denuncie.
- **Onda:** B, junto dos achados de `gpu/`, que não são protegidos pelo
  congelamento.
- **Situação:** fechado com correção de código e dois testes novos, no commit do
  pacote B15. `gpu/src/metaheuristica_gpu/run.py` ganhou o bloco de ambiente
  antes de qualquer importação, no mesmo padrão do ponto de entrada da impressão
  digital, com o valor recebido do pai capturado antes da escrita.
  `GpuEnvironment` ganhou dois campos, `thread_limits` e `observed_threads`, este
  último com contagem de threads e de threads com ticks acumulados, para que o
  registro não repita do lado da GPU a tautologia que F7-2 aponta do lado da CPU.
  **Evidência:** subprocesso limpo com as sete variáveis em `8` no ambiente do
  pai, importando `metaheuristica_gpu.run`, passou a observar as sete em `1` e o
  herdado em `8`; sem o bloco, o mesmo subprocesso observa `8`. Medição
  independente confirmou o mecanismo do achado: fora do ponto de entrada, o
  processo GPU chega a 36 threads.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os
  42 cenários devolveu "impressão digital idêntica" com saída 0, antes e depois
  do pacote. O oráculo é da CPU e não toca `gpu/`. Classe prevista `D3`, classe
  observada `D3`, sem reclassificação. **Consequência declarada:** alterar
  arquivos de `gpu/src/` muda `gpu_code_hash`, logo
  `results/gpu/metadata/gpu_readiness_manifest.json` fica divergente até a sua
  renovação, que é da B11A-E. Nenhum teste da suíte de GPU verifica o manifesto,
  e a renovação não pertence a este pacote.

#### F7-4. `ARROW_NUM_THREADS` é inerte; quem contém o Arrow é `OMP_NUM_THREADS`

- **Frente:** F7.
- **Classe:** `D2`.
- **Premissa:** a lista de sete variáveis que fixam a restrição a uma thread.
  **Fonte: metodologia da auditoria**, registrada em `constraints.md`. Este é um
  caso em que a fonte metodológica é o objeto correto do achado, e não uma premissa
  aplicada indevidamente ao código: **o achado é a afirmação falsa do próprio
  artefato normativo da auditoria**, não uma divergência do projeto contra
  `docs/`.
- **Previsto:** sete variáveis, cada uma cobrindo um mecanismo de paralelismo, todas
  efetivas.
- **Código:** `experiments/__init__.py:13`; `experiments/worker.py:9` e `:19-20`;
  `experiments/provenance.py:21`. Define `ARROW_NUM_THREADS=1`, que não é variável
  reconhecida pelo Apache Arrow. `VECLIB_MAXIMUM_THREADS` é variável do Accelerate
  da Apple e também não tem efeito em Linux, o que é inócuo porque a seção 23 fixa
  Linux nativo.
- **Evidência:** o verificador **reproduziu as três combinações** nesta máquina de
  32 threads lógicas: apenas `ARROW_NUM_THREADS=1` dá `cpu=32, io=8`; apenas
  `OMP_NUM_THREADS=1` dá `cpu=1, io=8`; nenhuma das duas dá `cpu=32, io=8`. Quem
  contém o pool de CPU do Arrow é `OMP_NUM_THREADS`, e o pool de entrada e saída só
  é contido pela chamada explícita `pa.set_io_thread_count(1)` de `worker.py:20`.
- **Veredito adversarial:** CONFIRMADO, reproduzido de forma independente. Classe
  `D2` correta e não `D1`, porque `worker.py:19-20` neutraliza o problema na
  campanha atual. O verificador considerou coerente a distinção que o relatório traça
  entre este achado, afirmação normativa falsa, e F7-9, código correto com forma
  arriscada, e não encontrou motivo para colapsar as duas classes.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir o enunciado da restrição global e manter as chamadas
  explícitas de `pyarrow`. Na campanha atual o efeito é nulo; o defeito é de
  enunciado da garantia, não de comportamento observado.
- **Onda:** B.
- **Situação:** fechado com correção de enunciado e um teste novo, no commit do
  pacote B15. Os três pontos que definem as sete variáveis passaram a declarar,
  em comentário, que `ARROW_NUM_THREADS` e `VECLIB_MAXIMUM_THREADS` são mantidas
  por simetria e sem efeito, e que a contenção do Arrow vem de `OMP_NUM_THREADS`
  mais as chamadas explícitas de `pa.set_cpu_count(1)` e
  `pa.set_io_thread_count(1)`. A lista das sete deixou de ser repetida em três
  arquivos e passou a vir de `experiments.THREAD_LIMIT_VARIABLES`, com
  `INEFFECTIVE_THREAD_VARIABLES` nomeando as duas inertes. **Oráculo:** teste que
  reproduz as três combinações em subprocesso, asseverando que só
  `ARROW_NUM_THREADS` deixa `pa.cpu_count()` acima de um, que só
  `OMP_NUM_THREADS` o leva a um, e que o ambiente do worker leva `cpu_count` e
  `io_thread_count` a um. **Redação da restrição global pendente de aprovação:**
  a emenda ao enunciado em `superpowers/B11B_plan.md` foi proposta ao usuário e
  não aplicada, porque plano aprovado não é emendado sem aprovação.
- **Impressão digital:** zero, conforme previsto. `compare --workers 16` sobre os
  42 cenários devolveu "impressão digital idêntica" com saída 0, antes e depois
  do pacote. Classe prevista `D2`, classe observada `D2`, sem reclassificação.

#### F7-5. `swap_unchanged` e `memory_margin` atravessam sessões separadas por um intervalo não monitorado

- **Frente:** F7.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 29, linhas 1074-1078, "Os critérios
  operacionais são ausência de OOM e consumo de swap e memória disponível igual ou
  superior ao maior valor entre 10% da RAM e 2 GiB", seguido de "Falha
  exclusivamente de recursos reduz os workers e exige repetição integral"; seção
  29.2, linha 1128, "Um subgrupo contém seis execuções e pode ser interrompido e
  retomado isoladamente". **Fonte: normativa.**
- **Previsto:** que os critérios de recurso descrevam a janela de execução
  observada, e que uma retomada seja isolada.
- **Código:** `experiments/resource_monitor.py:225-235` (`__enter__` recarrega
  **todas** as amostras de sessões anteriores do CSV) e `:133-151`, onde
  `minimum_available` é o mínimo sobre todas as linhas e `swap_delta` é
  `rows[0]["swap_free_bytes"] - rows[-1]["swap_free_bytes"]`, comparando a primeira
  amostra da **primeira** sessão com a última da sessão atual. Entre as duas há um
  intervalo de duração arbitrária em que nada foi amostrado.
  `benchmark_validation.py:68` exige `summary["passed"] is True` para cada sessão.
- **Evidência:** o verificador confirmou as duas linhas exatas por leitura e
  confirmou que o cenário é **alcançável**, porque o próprio `README.md:267` e
  `:287` autorizam interromper com `Ctrl+C`, retomar e pausar entre subgrupos para
  controlar temperatura, e não há contenção anterior no fluxo que neutralize isso.
  Cenário: no subgrupo `batch-01_aco_artesp_rmsp_150_k8`, cujo
  `estimated_seconds_per_run` é 10.971,5 s, uma pausa de um dia em que o uso normal
  da máquina consuma 1 MiB de swap não devolvido produz
  `swap_delta = 1.048.576`, `swap_unchanged = False`, `passed = False`, e a barreira
  falha bloqueando 324 execuções já concluídas. O erro simétrico também existe: swap
  consumido e devolvido dentro da janela dá delta zero e passa sem registro.
- **Veredito adversarial:** CONFIRMADO, com a mesma reserva de confiança que o
  auditor já registrou. Classe `D3` mantida.
- **Divergência auditor / verificador:** nenhuma. No piloto o critério passou, com
  `swap_consumed_bytes` igual a zero e interrupção curta.
- **Decisão:** corrigir, calculando os dois critérios por sessão e não sobre a série
  acumulada.
- **Onda:** B, com prioridade, porque o disparo custa um lote inteiro.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero.

#### F7-6. `elapsed_seconds` é sintético depois de uma retomada e esconde o intervalo real

- **Frente:** F7.
- **Classe:** `D2`.
- **Premissa:** `docs/experiments.md` seção 29, linha 1072, "O monitor registra CPU,
  RSS agregado, memória disponível, swap, processos e threads a cada segundo"; seção
  29.1, linhas 1105-1108. **Fonte: normativa.**
- **Previsto:** uma série temporal amostrada a cada segundo, na qual a coluna de
  tempo decorrido descreve tempo decorrido.
- **Código:** `experiments/resource_monitor.py:226-231`, em especial
  `offset = float(self._samples[-1]["elapsed_seconds"]) + self.interval_seconds` e
  `self._started = time.monotonic() - offset`. Na retomada o relógio da série é
  deslocado para que a primeira amostra nova caia exatamente um intervalo depois da
  última antiga, e o tempo de parada real desaparece da coluna.
- **Evidência:** o verificador reproduziu a medição sobre o **artefato real** do
  piloto, `results/operational/pilot_prebenchmark/resources.csv`, e obteve os mesmos
  três números: **10.467 amostras**, primeira em `1,0809999e-06 s`, última em
  `11.006,746975517 s`, e **maior salto entre amostras consecutivas de 1,109 s**,
  isto é zero saltos maiores que 3 s. Confirmou em `interruption.json` que a
  interrupção real ocorreu depois de 8 conclusões e que o CSV não mostra
  descontinuidade alguma no ponto correspondente. Nota adicional do auditor: 10.467
  amostras em 11.006,7 s dão intervalo médio de 1,0515 s e não 1,0 s, porque
  `_stop.wait(1.0)` não compensa o custo da amostragem; esse desvio de 5,2% é
  benigno mas confirma que a coluna não é índice confiável de tempo.
- **Veredito adversarial:** CONFIRMADO, reproduzido contra o artefato real. Classe
  `D2` correta: o verificador confirmou por leitura que `checks` usa apenas
  `memory_available_bytes`, `swap_free_bytes`,
  `max_active_threads_per_optimizer`, `cpu_percent` e `optimizer_process_count`,
  nenhum derivado de `elapsed_seconds`.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, renomeando a coluna para tempo monitorado acumulado ou
  registrando o instante absoluto de cada amostra.
- **Onda:** B.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero.

#### F7-7. A detecção de thread ativa tem uma janela cega de uma amostra e um piso de um tick

- **Frente:** F7.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 29, linhas 1074-1082, "uma thread
  computacional ativa por execução" e "Threads auxiliares ociosas do alocador ou da
  leitura Parquet são registradas separadamente e não contam como paralelismo
  computacional do otimizador"; verificação 8, linha 1080. **Fonte: normativa.**
- **Previsto:** um critério que distinga thread computacional de thread auxiliar
  ociosa e que detecte paralelismo interno acidental.
- **Código:** `experiments/resource_monitor.py:206-215`, em especial
  `if value > self._last_thread_ticks.get(identifier, value)`; `:55-71`; `:139-151`.
  A distinção por variação de ticks é, no essencial, a decisão certa, e por isso as
  3 threads auxiliares confirmadas em cada processo são corretamente ignoradas. Mas
  o padrão `.get(identifier, value)` faz um `tid` visto pela primeira vez ser
  comparado **consigo mesmo**, portanto nunca contado como ativo na amostra em que
  aparece; e a resolução de `utime + stime` é de 1 tick.
- **Evidência:** o verificador mediu `os.sysconf("SC_CLK_TCK")` nesta máquina e
  obteve **100**, confirmando o piso de 10 ms por tick, e confirmou que a comparação
  de um `tid` novo consigo mesmo não é uma possibilidade mas uma **consequência
  determinística** da expressão, sem tratamento compensatório em outro ponto do
  arquivo. A tolerância de `cpu_within_workers` dá 1.760% para 16 workers, e o
  piloto real registrou **1.635,2%**, confirmado contra `docs/experiments.md:1107`,
  abaixo do teto: o critério agregado não teria detectado uma thread computacional
  inteira adicional, porque a tolerância de 10% equivale a 1,76 núcleo.
- **Veredito adversarial:** CONFIRMADO, incluindo a granularidade do relógio. Classe
  `D3` mantida, com confiança média. O próprio achado se autolimita corretamente ao
  não alegar defeito presente.
- **Divergência auditor / verificador:** nenhuma. Na campanha atual o cenário é
  inatingível, porque as variáveis estão fixadas em todos os pontos de entrada da
  campanha CPU e os três algoritmos não despacham para BLAS multithread, como F7-3
  mostra por medição.
- **Decisão:** corrigir, tratando `tid` novo como ativo se seus ticks acumulados
  forem maiores que zero, e registrando o total de ticks por thread em vez de apenas
  o delta.
- **Onda:** B.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado **não** zero em campos de
  telemetria.

#### F7-8. A verificação 7 do piloto, "o tempo medido exclui pré-processamento", não tem implementação

- **Frente:** F7.
- **Classe:** `M2`.
- **Premissa:** `docs/experiments.md` seção 29, lista "O piloto verifica:", item 7,
  linha 1086, "o tempo medido exclui pré-processamento"; seção 25, linhas 866-882,
  que enumera o que deve ficar fora da janela. **Fonte: normativa.**
- **Previsto:** uma verificação executável, no conjunto que o piloto declara
  verificar, de que a janela cronometrada exclui pré-processamento.
- **Código:** `experiments/pilot_validation.py` integral. O único contato com
  `runtime_seconds` é `:164`, `comparable.pop("runtime_seconds", None)`, que a
  **remove** da comparação de determinismo. Nenhuma verificação toca a fronteira da
  janela.
- **Evidência:** o verificador leu o arquivo integralmente e confirmou que **não há,
  em lugar nenhum, asserção que compare a janela cronometrada com um limite, com a
  duração do carregamento da instância, ou com qualquer proxy do que a seção 25
  manda excluir**. Confirmou também `optimizer.py:114,125,144`, isto é que a janela
  em si parece correta, o que não é o que o achado afirma. Cenário: mover
  `_load_instance(path)` de `worker.py:46` para dentro de `execute_optimizer`, entre
  `start = clock()` e a construção do `FitnessEvaluator`, passa por toda a suíte de
  validação sem alteração, e o custo da leitura dos dois Parquet e da construção de
  `S_ij` e `W_ij` entraria integralmente no tempo publicado das 1.620 execuções.
- **Veredito adversarial:** CONFIRMADO. Classe `M2` correta, cobertura de teste e
  não defeito de comportamento.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, implementando a verificação 7 com uma cota superior sobre a
  fração do tempo atribuível a carregamento, ou instrumentando a fronteira da
  janela.
- **Onda:** B, junto de F6-02, porque as duas correções tocam a validação do piloto.
- **Situação:** fechado com implementação e seis testes novos, nos commits do pacote
  B1. A verificação 7 passou a existir como item próprio do relatório do piloto,
  no campo `timing_window` de `pilot_validation.json`, e é composta de duas partes.
  `_probe_timing_window` instrumenta a fronteira no **caminho de produção**:
  executa `experiments/worker.py:run_scenario` sobre um cenário de sonda,
  `tabu`, `artesp_rmsp_150`, `K=3`, orçamento 100, medindo o tempo total por fora e
  colhendo a janela de `runtime_seconds`, e mede à parte o custo de
  `_load_instance` como mínimo de cinco repetições depois de um aquecimento, isto é
  como cota inferior do carregamento. `_timing_window_report` é a regra pura:
  atribui à janela o carregamento que **não** aparece fora dela,
  `max(0, carga - (total - janela))`, e impõe cota superior de 5% sobre a fração
  resultante, recusando também sonda sem sensibilidade, em que a carga é pequena
  demais para que a inclusão fosse detectável. Medição no repositório íntegro:
  carga 0,034 s, janela 0,046 s, tempo excluído da janela 0,035 s, fração
  atribuída **0,0**. O cenário do achado, mover `_load_instance` para dentro da
  janela, levaria a fração a cerca de 0,43, isto é a oito vezes a cota. O cenário
  da sonda recebeu identidade própria, `scenario_id` e nome de arquivo derivados
  do seu próprio payload, para que a saída dela nunca possa ser gravada por cima
  de um resultado oficial. Testes:
  aceitação com carregamento fora da janela, recusa com carregamento integralmente
  dentro, recusa com carregamento parcialmente dentro, recusa de sonda sem
  sensibilidade, execução da sonda real contra a árvore e identidade própria do
  cenário de sonda.
- **Impressão digital:** zero, conforme previsto.

#### F7-9. `root_pid` do monitor é capturado na importação do módulo, não na instanciação

- **Frente:** F7.
- **Classe:** `M3`.
- **Premissa:** `docs/experiments.md` seção 29, linhas 1070-1072, "A campanha começa
  com 16 workers e monitoramento por `/proc`", e a árvore monitorada deve ser a da
  campanha. **Fonte: normativa.**
- **Previsto:** que o monitor observe a árvore do processo que o instancia.
- **Código:** `experiments/resource_monitor.py:173-178`, em especial
  `root_pid: int = os.getpid()` na linha 178. O valor padrão de um campo de
  `dataclass` é avaliado uma única vez, quando a classe é criada, isto é na primeira
  importação do módulo, e não a cada instanciação.
- **Evidência:** o verificador **reproduziu isoladamente**, fora da árvore do
  repositório: um `dataclass` com `root_pid: int = os.getpid()`, instanciado no pai
  e depois em um filho `spawn`. No filho, o valor capturado por uma **nova**
  instância é o PID do próprio filho, porque o módulo é reexecutado do zero sob
  `spawn` e a expressão de valor padrão é reavaliada. Se `ResourceMonitor()` fosse
  instanciado dentro de um filho, `root_pid` seria o do filho, `descendants` estaria
  vazio, `optimizer_process_count` seria 0, e
  `one_active_thread_per_optimizer` e `no_persistent_optimizers` seriam verdadeiros
  **de forma vazia**, com `passed` verdadeiro sem ter observado nada.
- **Veredito adversarial:** CONFIRMADO, reproduzido isoladamente. Classe `M3` é a
  calibração certa e não `D3`, porque o caminho não é alcançável no grafo de chamadas
  atual: o verificador confirmou que o único chamador é `execute_operation`, que roda
  no processo principal, antes de `execute_campaign` criar o `ProcessPoolExecutor`.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, usando `field(default_factory=os.getpid)`.
- **Onda:** C.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero.

#### F7-10. A estimativa do roteiro ancora em duas medidas de uma única semente, e em 5 dos 9 pares a inclinação interpolada é decrescente em `K`

- **Frente:** F7.
- **Classe:** `L1`.
- **Premissa:** `docs/experiments.md` seção 29.2, linhas 1130-1133, "Os subgrupos
  são ordenados antes da B11-E pela duração estimada com os tempos do piloto. Para
  cada algoritmo e instância, `K=3` e `K=8` são âncoras e os valores intermediários
  usam interpolação linear"; seção 29.1, linhas 1110-1115, "Esses valores são
  descritivos de uma única seed e não sustentam conclusão estatística, mas devem
  orientar o escalonamento da B11". **Fonte: normativa.**
- **Previsto:** uma ordenação de subgrupos e uma previsão de duração derivadas de
  duas âncoras por par, com a limitação da semente única já reconhecida.
- **Código:** `experiments/benchmark_schedule.py:48-54`, em especial
  `estimates[(algorithm, instance, k)] = lower + (upper - lower) * (k - 3) / 5`, e
  `:39-47`, que exige exatamente 18 âncoras. Faz exatamente o que o documento diz,
  sem desvio.
- **Evidência:** **a interpolação se sustenta.** Confrontada com a curva medida pela
  frente F4 nos seis valores de `K` para o par `(aco, artesp_rmsp_150)`:

  | `K` | interpolado (s) | medido F4 (s) | erro |
  |---:|---:|---:|---:|
  | 3 | 6.389,35 | 6.310,9 | +1,2% |
  | 4 | 7.305,77 | 7.425,3 | -1,6% |
  | 5 | 8.222,19 | 8.410,2 | -2,2% |
  | 6 | 9.138,61 | 9.408,4 | -2,9% |
  | 7 | 10.055,03 | 10.186,4 | -1,3% |
  | 8 | 10.971,45 | 11.023,2 | -0,5% |
  | soma | 52.082,40 | 52.764,4 | **-1,3%** |

  A curva real é levemente côncava, logo a reta subestima todos os intermediários,
  com erro máximo de 2,9% em `K=6`. Como esse par responde por 1.562.472 dos
  1.843.267 s-CPU do roteiro, isto é **84,8%** do orçamento, o viés agregado é da
  ordem de 1%. O verificador releu as 18 âncoras direto de
  `results/tables/pilot_runs.parquet` e todos os 18 valores coincidem exatamente,
  incluindo o sinal da inclinação de cada par: **5 decrescentes**, `(pso,150)`
  91,197 para 89,353, `(pso,20)` 5,014 para 2,488, `(pso,60)` 19,786 para 15,751,
  `(tabu,150)` 68,964 para 67,176, `(tabu,60)` 14,761 para 14,639; e **4
  crescentes**, os três do ACO e `(tabu,20)` 3,827 para 4,089. Os cinco pares
  decrescentes somam 1,9% dos s-CPU do roteiro, e a estimativa é usada apenas como
  chave de ordenação (`benchmark_schedule.py:70-71`) e para o total informativo de
  `readiness`, nunca como corte ou limite.
- **Veredito adversarial:** CONFIRMADO, incluindo a checagem de consistência
  solicitada entre "a interpolação se sustenta" e "a projeção de horas de relógio
  não se sustenta". Classe `L1` mantida.
- **Divergência auditor / verificador:** nenhuma. O verificador examinou
  explicitamente se as duas afirmações conflitam e **concluiu que não**, por razão
  estrutural: `estimated_seconds_per_run` e
  `estimated_seconds_total = estimated_seconds_per_run * 6` vêm da mesma
  interpolação, mas alimentam duas perguntas independentes, uma de acurácia,
  respondida com -1,3%, e outra de escalonamento, respondida em F7-1 com evidência
  de que o procedimento documentado ocupa 6 workers e não 16. Uma interpolação exata
  produziria a mesma discrepância de 2,4x, e uma imprecisa não mudaria esse fator.
- **Decisão:** registro apenas. **As duas questões precisam ser mantidas separadas no
  relatório final: a interpolação está a 1,3% do medido; a projeção de relógio está
  a 2,1x-2,4x, e a causa disso é F7-1 e não a interpolação.**
- **Onda:** registro apenas. Ver também o achado F9-5, que trata da mesma estimativa
  pelo ângulo da obsolescência caso a Onda B acelere o ACO; os dois não se
  contradizem nem se repetem.
- **Situação:** fechado sem ação de código.
- **Impressão digital:** pendente.

### 3.8. Frente F8 - infraestrutura GPU

Catorze achados, e a frente que mais mudou na verificação adversarial: **três
refutações e cinco reclassificações**. Os dois achados originalmente `D1`
receberam verificação dedicada, além da verificação de frente, e **os dois caíram
como `D1`**. Com isso a contagem de `D1` da auditoria caiu de quatro para um. A
classe `D3`, operacionalmente a mais urgente, caiu de seis achados propostos para
quatro confirmados. Nenhum dos quatro tem efeito observado em medição real.

**Ambiente sem limitação.** A suíte GPU rodou: 271 testes coletados a partir da
raiz, 254 da suíte CPU mais 17 da GPU, todos aprovados em 99,55 s. O `readiness`
GPU retornou código 0 com `infrastructure_ready=true`, `execution_ready=false`,
`waiting_for_b11e=true`, `existing_official_results=0`, `git_dirty=false`, sobre
RTX 3060, CUDA 12.9, CuPy 14.1.1, com `float64_kernel_passed=true`. Zero
resultados GPU oficiais existem.

**Ruling de cascata, registrado.** Os dois achados originalmente `D1` da GPU **não
disparavam** a cascata da campanha CPU, mesmo antes de serem rebaixados. Ambos
vivem em `gpu/`, que não é protegido pelo congelamento da B11-E nem entra em
`protected_paths`, e a campanha B11A-E nunca rodou, logo não existe resultado a
invalidar. O custo de cascata deles é zero e a correção é barata agora.

**O que sobrou do achado central da frente, depois da refutação.** A equivalência
exata **é** satisfeita nos termos do documento normativo. Orçamento e ordem de
consumo são exatamente iguais, verificado por instrumentação de
`ConvergenceRecorder.observe`, com sequência idêntica em 100% das posições,
inclusive nas 992 avaliações de reparo do PSO. Solução final e custo final
coincidem bit a bit, porque o custo final é recalculado na CPU antes de publicar.
Os cem checkpoints publicados carregam valores da GPU e divergem já no
checkpoint 1, com magnitude de **1 a 2 ulp**, isto é entre `2,220e-16` e
`5,551e-16`, o que é **1/1802 da tolerância normativa de `1e-12`**.

#### F8-1. Os cem checkpoints publicados carregam números da GPU e a arbitragem CPU de quase empates nunca é chamada

- **Frente:** F8.
- **Classe:** `M3`, rebaixada de `D1`, com componente `M2` associada.
- **Premissa:** `docs/experiments.md` linhas 1159-1162, seção 29.1 da B11A, cuja
  citação literal é: "A conformidade exige tolerâncias absoluta e relativa de
  `1e-12`, igualdade de orçamento e checkpoints, arbitragem CPU de quase empates e
  confirmação CPU da solução final". **Fonte: normativa.** **A palavra "exata" não
  aparece, e a régua de `1e-12` é fixada antes da enumeração.** O relatório invocou
  também as restrições globais de comparação exata por `float.hex()`, que são
  **metodologia desta auditoria** e cujo escopo é exclusivamente a impressão
  digital, cujos 42 cenários são todos de CPU. Esta confusão de fonte é a causa
  raiz registrada na seção 6.
- **Previsto:** que os checkpoints da GPU não divergissem da CPU **além de
  `1e-12`**, e que decisões de quase empate fossem arbitradas na CPU.
- **Código:** `gpu/src/metaheuristica_gpu/numerics.py:58-88` (`arbitrate_best`);
  `gpu/src/metaheuristica_gpu/evaluator.py:98-105`;
  `gpu/src/metaheuristica_gpu/aco.py:120-125` e `:153-160`;
  `gpu/src/metaheuristica_gpu/pso.py:70-80` e `:150-164`;
  `src/metaheuristica/metrics.py:153-165` e `:276-278`.
- **Evidência (números do verificador):** divergência máxima medida entre
  **`2,220e-16` e `5,551e-16`** em seis configurações, isto é **1/1802 do
  `abs_tol` normativo**. Colateral decisivo: com `verify_every_batch=True` o
  caminho de código da GPU reproduz o normativo **bit a bit** nas seis
  configurações, logo a única fonte de divergência é o dispositivo, e o repositório
  já contém e testa um modo exato. `arbitrate_best` de fato **nunca** é chamada,
  confirmado por `sys.setprofile` contando eventos de `call` cujo `f_code` é o
  próprio objeto de código, com **zero** chamadas em **oito** execuções reais,
  contra 1 a 401 chamadas de `require_equivalent` nas mesmas execuções; e
  `grep -rn "arbitrate_best"` devolve **uma única ocorrência** em todo o
  repositório, a própria definição.
- **Veredito adversarial:** **REFUTADO como `D1` e como `D2`.** Sob a taxonomia,
  `D1` é "defeito que altera qualquer número produzido pela campanha", e o
  pressuposto de **defeito** falha: com a régua de `1e-12` que a seção 29.1 fixa,
  uma divergência de 1 a 2 ulp é **conformidade**. Além disso, **a arbitragem CPU
  que a seção 29.1 exige É executada**, por código normativo compartilhado,
  `ConvergenceRecorder._is_better` e `gpu/pso.py:70-80`, idêntico operação por
  operação ao caminho CPU: em **30.070 comparações houve 3.019 quase empates sob
  GPU e 3.019 sob CPU, com zero divergências de classificação**. A seção exige
  arbitragem CPU, não a função `arbitrate_best`, que é artefato do subprojeto e não
  do documento.
- **Divergência auditor / verificador:** quatro itens, e o mais importante deles é
  que **a correção proposta pelo achado é afirmativamente errada**. Chamar
  `arbitrate_best` no ponto de decisão **quebraria** a igualdade de checkpoints que
  o próprio achado invoca, porque a chave de `arbitrate_best` é
  `(custo CPU, rótulos)` com o **custo primeiro** (`numerics.py:80-87`), contra
  rótulos apenas do caminho normativo (`metrics.py:160-164`): dois candidatos
  separados por `1e-13` são empate para o normativo e **não** são empate para
  `arbitrate_best`, logo adotar a correção **introduziria** divergência de critério
  onde hoje não há nenhuma, e de solução escolhida, não de último bit. Segundo, **o
  percentual de 28% a 44% está errado**: as contagens brutas reproduzem exatamente,
  888, 565, 834 e 579, mas o PSO gastou **1.008 e 1.068** avaliações elegíveis e
  não 2.000, logo a faixa correta em `total_cost` é **41,7% a 56,1%**, e contando
  os sete campos que o JSON publica a faixa é de **98,31% a 99,97%**; essa correção
  **agrava** o fato e não altera o veredito, porque a magnitude, não a frequência,
  é o que a seção 29.1 governa. Terceiro, a formulação correta do que o achado
  deveria ter dito é: o modo oficial publica checkpoints do dispositivo, conformes
  à tolerância por margem de fator 1.802 e sem amplificação medida; existe um modo
  que os torna exatos e ele está corretamente fora da região cronometrada; e a
  asserção de igualdade que o portão de conformidade deveria conter mora na suíte
  de testes e só na instância mínima.
- **Decisão:** duas correções independentes, que a triagem pode aceitar ou rejeitar
  isoladamente. **`M3`:** remover `arbitrate_best`, `synchronized_call` e o campo
  `synchronization_seconds`, que são código morto, ou documentar no módulo por que
  existem inertes; manter uma segunda implementação de desempate com chave
  diferente da normativa e sem chamador é convite a exatamente o erro de
  diagnóstico que este achado cometeu. **`M2`:** mover para dentro de
  `run_conformance` a asserção de igualdade de checkpoints contra execução CPU
  pareada, com pelo menos uma instância real, porque hoje `run.py:117-137` apenas
  **registra** `reproducible_data()` e não **afirma** nada.
- **Onda:** C para a componente `M3`; a componente `M2` acompanha, no mesmo commit.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero para a campanha CPU, porque a
  correção vive inteiramente em `gpu/`.
- **Limite declarado pelo verificador:** as medições usaram orçamentos de 2.000,
  4.000 e 20.000, e **não** os 150.000 oficiais, porque uma execução pareada de ACO
  em `artesp_rmsp_150` com orçamento cheio custaria cerca de 2,3 h de CPU. **A
  conformidade em 150.000 avaliações permanece não verificada por medição direta.**
  O que sustenta a extrapolação é que o desvio é erro de arredondamento por
  avaliação e não acumulação: o máximo absoluto ficou travado em 1 a 2 ulp com
  orçamento cinco vezes maior, e o critério que aprova é o absoluto de `1e-12`.

#### F8-2. O speedup do ACO mede uma reescrita de CPU, não a GPU

- **Frente:** F8.
- **Classe:** `L1`, rebaixada de `D1`.
- **Premissa:** `docs/experiments.md` seção 26, "Serão comparadas implementações
  CPU e GPU apenas nos algoritmos em que a paralelização por GPU for tecnicamente
  coerente" e `S = T_CPU / T_GPU`; seção 29.1 da B11A, "somente avaliações
  independentes da função objetivo são agrupadas em CuPy". **Fonte: normativa.**
- **Previsto:** que `T_GPU` diferisse de `T_CPU` por ter movido as avaliações em
  lote para o dispositivo, de modo que `S` fosse interpretável como aceleração por
  GPU.
- **Código:** `gpu/src/metaheuristica_gpu/aco.py:31-117` reescreve
  `_PartialConstructionState` como `_PartialState`, `_construction_choices` como
  `_choices` e `_construct_ant` como `_construct`, omitindo `_validate_prefix` por
  posição, a construção de `EvaluationResult` por escolha, `_choice_probabilities`
  com suas validações e a publicação de diagnósticos por formiga. **Essa reescrita
  fica dentro da região cronometrada** (`aco.py:138-139` e `:162-163`), enquanto a
  GPU recebe uma avaliação completa por formiga.
- **Evidência (números do verificador):** divisão medida em `artesp_rmsp_150`,
  `K=5`, seed 10. No ACO, **o dispositivo inteiro, `h2d` mais kernel mais `d2h`,
  responde por 0,1522 s, isto é 0,093% do tempo GPU**; a fração acelerável na CPU é
  **0,712%**; o **teto de Amdahl do dispositivo é 1,0072**; o ganho atribuível ao
  dispositivo e ao lote é **2,20%** e o ganho da reescrita de CPU é **97,60%**. O
  speedup observado de **1,3518** vem quase todo da reescrita. Um microbenchmark
  independente concorda em 0,43%. O PSO **passa** no teste de Amdahl, com
  dispositivo em **16,3%** do tempo e teto **3,13**; o ACO **reprova por 34%**.
- **Veredito adversarial:** **REFUTADO como `D1`, mecanismo CONFIRMADO,
  reclassificado `L1`.** A classe cai porque `D1` exige número alterado, e **não
  existe resultado GPU oficial**: existe um número **futuro** cujo significado está
  comprometido. A defesa de "condição necessária" foi testada e refutada.
- **Divergência auditor / verificador:** o mecanismo e a direção do achado se
  sustentam; o que cai é a classe. Os números do verificador são mais precisos que
  os do relatório, que estimava 0,085% de dispositivo contra os 0,093% medidos, e
  1,355 de speedup contra 1,3518.
- **Decisão:** registro apenas, com uma proibição explícita a carregar para o
  relatório final: **é proibido apresentar o `S` do ACO como aceleração por GPU na
  pergunta 11 da seção 31, porque isolada ela vale 1,006 e não 1,35.** As três
  saídas do relatório continuam disponíveis para a B11A-E: fazer o ACO GPU chamar o
  caminho de construção normativo, publicar um controle CPU contra CPU com a
  reescrita, ou deferir o ACO como a Busca Tabu já foi, pelo mesmo argumento de
  profiling que a seção 29.1 exige dela.
- **Onda:** registro apenas.
- **Situação:** fechado sem ação de código, com decisão de desenho pendente para a
  B11A-E.
- **Impressão digital:** pendente.
- **Achado próprio derivado do verificador, `M3`:** `consolidate` descarta
  `diagnostics.gpu_timing` ao montar `gpu_runs.parquet`, publicando `speedup` sem a
  fração de dispositivo que o interpreta. Consta do Apêndice B, porque não passou
  por verificação adversarial independente.

#### F8-4. Os dois únicos testes de equivalência de execução completa são vacuosos

- **Frente:** F8.
- **Classe:** `M2`.
- **Premissa:** `docs/experiments.md` seção 26, "deverá ser verificado se a versão
  GPU preserva a mesma função objetivo, a mesma interpretação das soluções e
  resultados numericamente equivalentes"; seção 29.1 da B11A, igualdade de
  checkpoints. **Fonte: normativa.**
- **Previsto:** cobertura que demonstre a equivalência do que será executado.
- **Código:** `gpu/tests/test_aco_gpu.py:10-19` e `gpu/tests/test_pso_gpu.py:10-19`,
  em especial a linha 15 de cada um, com `verify_every_batch=True`, e
  `gpu/src/metaheuristica_gpu/evaluator.py:94-97`. Os dois testes escrevem
  exatamente as asserções certas, `gpu.solution == cpu.solution`,
  `gpu.evaluation == cpu.evaluation` e `gpu.checkpoints == cpu.checkpoints`, todas
  por igualdade exata, e depois as aplicam a uma execução em que os resultados da
  GPU **foram descartados**.
- **Evidência:** o verificador confirmou por
  `grep -rn "run_aco_gpu\|run_pso_gpu" gpu/tests/ gpu/src/` que as duas únicas
  chamadas em `gpu/tests/` estão nas linhas 15 dos dois arquivos, ambas com
  `verify_every_batch=True`. `test_objective_gpu.py` testa
  `GpuBatchObjective.evaluate` sobre dados não triviais, mas apenas uma chamada de
  lote isolada, nunca a trajetória; `test_batch_evaluator.py` cobre truncamento de
  orçamento. **Nenhum teste do pacote roda a trajetória completa com dados não
  triviais e sem substituição pela CPU.** Trocando só a instância e o `K` para
  `artesp_rmsp_20`, `K=5`, seed 10, orçamento 2.000, a asserção
  `gpu.checkpoints == cpu.checkpoints` passa a falhar, com o checkpoint 1 valendo
  `0.5045496148091859` na CPU e `0.504549614809186` na GPU: o par de testes está a
  duas linhas de ser o teste que faltava.
- **Veredito adversarial:** CONFIRMADO, classe `M2` mantida. A lacuna é real e
  específica: falta um teste de trajetória completa em modo oficial sobre instância
  não trivial.
- **Divergência auditor / verificador:** nenhuma. **Este achado absorve todo o
  conteúdo válido de F8-3**, que foi refutado.
- **Decisão:** corrigir. Acrescentar teste de trajetória completa em modo oficial,
  com tolerância de `1e-12`, que é a régua normativa, e não com igualdade exata.
- **Onda:** C, isolada. Não há defeito de código associado, porque F8-3 caiu e F8-1
  virou `M3`.
- **Situação:** aberto.
- **Impressão digital:** pendente.

#### F8-5. Diagnósticos de conformidade publicados como zero sem significado nas 60 execuções

- **Frente:** F8.
- **Classe:** `M3`, rebaixada de `D2`.
- **Premissa:** `docs/experiments.md` seção 29.1 da B11A, "O tempo oficial inclui
  transferências, sincronizações e arbitragens ocorridas durante a otimização";
  seções 10.5 e 28.1 quanto ao valor probatório dos campos registrados por
  execução. **Fonte: normativa.**
- **Previsto:** que os campos de diagnóstico registrassem o que realmente ocorreu.
- **Código:** `gpu/src/metaheuristica_gpu/aco.py:183` e `pso.py:241`
  (`max_numerical_difference`); `evaluator.py:55` e `:87-91`;
  `timing.py:20-21`. `HybridEvaluator.__init__` inicializa
  `max_numerical_difference = 0.0` e só o atualiza dentro do bloco
  `if self.verify_every_batch:`; como a execução oficial usa o padrão `False`, o
  campo é **estruturalmente** `0.0`. `arbitration_cpu_seconds` só é incrementado
  dentro de `arbitrate_best`, que tem zero chamadas medidas.
  `synchronization_seconds` não é atribuído em lugar algum do pacote.
- **Evidência:** os três campos são publicados nos 60 documentos como parte de
  `gpu_timing`, ao lado de checkpoints que de fato divergem em 1 a 2 ulp. Um
  revisor que audite os JSON concluirá, pelos campos, que não houve divergência
  alguma.
- **Veredito adversarial:** **REFUTADO na classe, reclassificado de `D2` para
  `M3`.** A verificação dedicada de F8-1 já havia adjudicado dois dos três campos,
  `arbitration_cpu_seconds` e `synchronization_seconds`, como **código morto por
  desenho**, com classe `M3`; reabri-los como `D2` contradiria esse precedente sem
  motivo novo. O terceiro campo, `max_numerical_difference`, é novo nesta
  verificação e tem a mesma natureza: não é um valor **computado errado**, é um
  campo cuja definição operacional é honesta e **vazia por desenho**, porque a
  checagem que o alimentaria nunca roda em modo oficial. O risco é de leitura
  equivocada por auditor humano, que é exatamente o padrão que motivou `M3` em
  F8-1.
- **Divergência auditor / verificador:** a classe cai. **O achado tem razão sobre o
  risco**, e isso fica registrado: um revisor que leia
  `max_numerical_difference: 0.0` ao lado de checkpoints que divergem pode
  legitimamente concluir o oposto do que aconteceu. Mas corrigir isso é melhoria de
  legibilidade do artefato, não reversão de um defeito que produziu número errado.
- **Decisão:** corrigir, documentando no schema do JSON o significado condicional
  do campo, ou publicando campo derivado que interprete o `speedup`, como a
  `device_fraction` proposta para `consolidate`.
- **Onda:** C, junto de F8-1 e do item derivado sobre `gpu_timing`.
- **Situação:** aberto.
- **Impressão digital:** pendente.

#### F8-6. O limiar de resfriamento libera acima do limiar aceito pelo preflight

- **Frente:** F8.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 29.1 da B11A, "A campanha contém 60
  cenários... Ela é sequencial" e "A execução requer exclusividade da placa,
  preflight ocioso de 60 segundos e monitoramento térmico contínuo". **Fonte:
  normativa.**
- **Previsto:** uma campanha sequencial de 60 cenários em que o resfriamento entre
  execuções deixe a placa em condição aceita pelo preflight seguinte.
- **Código:** `gpu/src/metaheuristica_gpu/monitor.py:88-89`,
  `if sample.temperature_c > 50: raise GpuSafetyError`, contra `:159-168`, onde
  `cooldown` retorna quando `temperature_c <= 55`. Os dois limiares são
  inconsistentes por uma faixa de cinco graus, e não há espera intermediária nem no
  código nem no `README.md`, que documenta a sequência por cenário em `:424-439`
  sem mencionar resfriamento entre um `execute` e o próximo.
- **Evidência:** os dois valores foram confirmados por leitura direta, e a
  inconsistência já é demonstrada por `gpu/tests/test_monitor.py:13-14`, que mostra
  `preflight_idle` levantando `GpuSafetyError` a 51 graus. Disparado um segundo
  `execute --scenario-id` imediatamente após `cooldown()` retornar com a placa entre
  51 e 55 graus, a primeira amostra do preflight levanta `GpuSafetyError`, a sessão
  é gravada como `interrupted` e o comando sai com código 2.
- **Veredito adversarial:** CONFIRMADO como `D3`, **mas não é deadlock**. O
  verificador mediu a temperatura ociosa real desta placa agora, por
  `nvidia-smi --query-gpu=temperature.gpu`: **38 graus**, bem abaixo dos dois
  limiares. Depois que `cooldown()` retorna, nada volta a aquecer a placa entre uma
  execução e a próxima, de modo que a temperatura continua caindo em direção à
  ociosa. **A segunda execução da campanha consegue iniciar**: a condição é
  transitória e se resolve sozinha. O que existe é falha **espúria,
  determinística e recorrente** se os cenários forem disparados de volta a volta, e
  o `README.md` não informa quanto esperar.
- **Divergência auditor / verificador:** a palavra "trava" cai. O modo de falha real
  é: primeira tentativa reprova, sessão marcada `interrupted`, operador espera sem
  saber quanto e tenta de novo com sucesso. Isso é fricção operacional real, com
  sessões `interrupted` espúrias poluindo o histórico de 60 cenários, e **não**
  bloqueio irreversível. **Esta correção também derruba a leitura de deadlock que o
  coordenador havia repassado ao usuário.**
- **Decisão:** corrigir, alinhando os dois limiares e documentando a espera. A
  classe `D3` se mantém porque "risco operacional que pode quebrar a campanha em
  curso" é satisfeito pela repetição determinística da falha a cada início de
  cenário dentro da janela de 5 graus, mesmo sem ser permanente.
- **Onda:** B, com prioridade dentro de `gpu/`.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero para a campanha CPU.

#### F8-7. Falha de segurança na primeira amostra impede a gravação da telemetria

- **Frente:** F8.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 29.1 da B11A, "Interrupções de segurança
  preservam sessão e telemetria e não publicam resultado parcial". **Fonte:
  normativa**, citação literal confirmada.
- **Previsto:** que toda interrupção de segurança deixasse a telemetria em disco.
- **Código:** `gpu/src/metaheuristica_gpu/monitor.py:136-139`, onde `__enter__`
  chama `self._sample()` antes de o `with` estar estabelecido, e `:141-156`, onde
  `__exit__` é o **único** lugar do pacote que escreve o CSV de telemetria.
- **Evidência:** o verificador confirmou que `_sample`/`_check` podem levantar
  `ThermalInterruption` na primeira amostra por duas vias que disparam já na
  primeira, `software_thermal_slowdown or hardware_thermal_slowdown` e
  `external_processes`, e que **pelo protocolo de gerenciador de contexto do Python,
  se `__enter__` levanta, `__exit__` nunca é chamado**, o que é semântica
  documentada da instrução `with` e não interpretação. A exceção é capturada pelo
  `try` externo de `execute_scenario` (`run.py:209-215`), que preserva a sessão em
  JSON, mas o arquivo de telemetria **nunca chega a existir**.
- **Veredito adversarial:** CONFIRMADO quanto à afirmação principal, classe `D3`
  mantida. A justificativa da classe é a **alcançabilidade hoje**: uma
  `ThermalInterruption` na primeira amostra é alcançável em qualquer um dos 60
  cenários por condição externa comum, sem depender de reconfiguração alguma, ao
  contrário de F8-9. E a exigência perdida é de **segurança**, não de conveniência:
  "interrupções de segurança preservam sessão e telemetria" é parte do protocolo que
  decide se é seguro prosseguir para o próximo cenário depois de um evento térmico.
- **Divergência auditor / verificador:** **a subafirmação secundária é refutada.** O
  achado descreve uma "segunda aresta", em que `__exit__` acessaria
  `self.samples[0]` com lista vazia produzindo `IndexError` que mascara o erro
  original. Isso é **inalcançável**: `_sample()` sempre executa
  `self.samples.append(sample)` **antes** de chamar `self._check(sample)`, e
  `__exit__` só roda quando `__enter__` teve sucesso, o que implica que a primeira
  amostra já foi anexada. A alegação não se sustenta sob a semântica de `with`.
- **Decisão:** corrigir, movendo a primeira amostragem para depois do
  estabelecimento do contexto, ou gravando o CSV também no caminho de exceção de
  `__enter__`.
- **Onda:** B, com prioridade dentro de `gpu/`.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero para a campanha CPU.

#### F8-8. Valor desconhecido de throttling é interpretado como throttling ativo

- **Frente:** F8.
- **Classe:** `D3`, confiança baixa.
- **Premissa:** `docs/experiments.md` seção 29.1 da B11A, "monitoramento térmico
  contínuo". **Fonte: normativa**, mas a exigência específica de distinguir "sem
  throttling" de "não sei" é **formulação do próprio auditor** e não texto literal
  da seção. O achado não depende disso: o defeito de código é verificável
  independentemente de qualquer citação normativa.
- **Previsto:** interrupção diante de throttling **observado**.
- **Código:** `gpu/src/metaheuristica_gpu/monitor.py:39-40` (`_active`) e `:114-115`.
  `_active` devolve verdadeiro para qualquer texto fora do conjunto
  `{"not active", "no", "0", "n/a"}`, e o `nvidia-smi` devolve `[N/A]`, **com
  colchetes**, quando um contador não é suportado.
- **Evidência:** verificável estaticamente: `_active` normaliza por
  `.strip().lower()`, e `"[N/A]".strip().lower()` é `"[n/a]"`, que não é `"n/a"`,
  logo `_active("[N/A]") is True`. **Contraprova verificada pelo verificador nesta
  máquina agora:** `nvidia-smi` com as duas consultas de
  `clocks_event_reasons` devolveu `Not Active, Not Active`, sem colchetes e sem
  `[N/A]`. O gatilho não está presente nesta placa e neste driver hoje.
- **Veredito adversarial:** CONFIRMADO, com confiança baixa quanto à ocorrência,
  exatamente como o próprio achado se autoavaliou. Classe `D3` mantida.
- **Divergência auditor / verificador:** nenhuma no fato. O verificador registrou a
  nota de proveniência de premissa acima, que é a mesma lição de F8-1: a frase
  normativa não sustenta a exigência tão precisamente quanto o texto do achado
  sugere.
- **Decisão:** corrigir, tratando valor não reconhecido como desconhecido explícito
  em vez de throttling ativo, e falhando com mensagem de telemetria incompleta se a
  política exigir.
- **Onda:** B, dentro de `gpu/`, no mesmo commit de F8-7, porque o gatilho deste cai
  no mecanismo daquele.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero para a campanha CPU.

#### F8-9. Limite de lote fixo em 40 coincide por acaso com os hiperparâmetros congelados

- **Frente:** F8.
- **Classe:** `M3`, rebaixada de `D3`.
- **Premissa:** `docs/experiments.md` seção 26, "mesmos hiperparâmetros do
  experimento principal"; seção 12.2 e
  `experiments/configs/frozen_parameters.toml`, com `n_ants=40` e
  `n_particles=40`; seção 29.2 quanto à recusa diante de divergência de item
  protegido. **Fonte: normativa.**
- **Previsto:** que a infraestrutura GPU acompanhasse os hiperparâmetros oficiais e
  que qualquer incompatibilidade fosse detectada antes da execução.
- **Código:** `gpu/src/metaheuristica_gpu/objective.py:51-52`,
  `if not 1 <= host.shape[0] <= 40: raise GpuObjectiveError`, literal sem relação
  declarada com a configuração; `gpu/configs/gpu_benchmark.toml:28` e `:31` com
  `n_ants = 40` e `n_particles = 40`; `config.py:38-72` valida schema, backend,
  precisão, seeds e algoritmos, mas **não** compara os dois valores contra o teto.
  O sistema opera colado no limite, com folga zero.
- **Evidência:** os fatos foram todos confirmados por leitura direta, incluindo
  `change_policy = "requires_new_tuning"` em `frozen_parameters.toml`.
- **Veredito adversarial:** **REFUTADO na classe, reclassificado de `D3` para
  `M3`.** A afirmação central de `D3` é risco "que pode quebrar a campanha em
  curso", e a defesa de inalcançabilidade sob os hiperparâmetros congelados se
  aplica **com precisão cirúrgica**: o cenário de falha **exige** um evento futuro e
  deliberado, um novo ciclo de tuning, seguido de edição manual de
  `gpu_benchmark.toml`, seguido de novo `freeze`. Nenhum desses passos acontece
  durante a execução dos 60 cenários já congelados, que usam exatamente 40, dentro
  do limite. **Não há caminho de código nem de configuração atual por onde a
  campanha em curso alcance o `GpuObjectiveError`.**
- **Divergência auditor / verificador:** além da classe, um **erro factual
  secundário verificado**: o achado afirma "A sessão fica `failed`", mas
  `GpuObjectiveError` é subclasse de `RuntimeError` e `run.py:212` grava
  `"interrupted" if isinstance(error, RuntimeError) else "failed"`, logo a sessão
  seria gravada como **`interrupted`**, não `failed`. Não muda o argumento central,
  mas é deslize verificável que reduz a confiança no restante do detalhamento do
  cenário.
- **Decisão:** corrigir como robustez de manutenção, cruzando
  `n_ants`/`n_particles` contra o teto de `objective.py` em `config.py`, **antes do
  próximo ciclo de tuning** e não com urgência de campanha.
- **Onda:** C.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero.

#### F8-10. As réplicas GPU omitem as validações defensivas do caminho normativo e registram a chave do incumbente sem canonicalizar

- **Frente:** F8.
- **Classe:** `D3`, confiança média.
- **Premissa:** `docs/experiments.md` seção 29.1 da B11A, "A função CPU permanece
  normativa"; seção 30, princípio de congelamento experimental, que trata regras de
  reparo e função objetivo como invariantes. **Fonte: normativa.**
- **Previsto:** que o caminho GPU se comportasse como o CPU, inclusive ao recusar
  estados inválidos.
- **Código:** `gpu/src/metaheuristica_gpu/pso.py:50-54`;
  `gpu/src/metaheuristica_gpu/aco.py:64-69`, `:110-116` e `:124`;
  `gpu/src/metaheuristica_gpu/evaluator.py:79-82` e `:101-104`.
- **Evidência:** o verificador comparou as duas implementações **lado a lado, linha
  a linha**, e confirmou as seis omissões, nenhuma delas presente na réplica GPU sob
  outro nome: sem checagem de `dtype float64`, `ndim`, finitude e intervalo `[0,1]`
  da posição, que `pso.py:114-128` faz; sem checagem de `eta` finito e em `[1,2]`,
  que `aco.py:196-215` faz; sem checagem de `tau` e `eta` positivos e finitos nem de
  probabilidades normalizadas, que `aco.py:224-256` faz; sem checagem de
  canonicidade da solução da formiga, que `aco.py:302-305` faz; com clipagem
  silenciosa por `min(1.0, max(0.0, ...))` em vez da exceção de
  `aco.py:309-313`; e gravando `tuple(int(value) for value in solution)` em vez de
  `solution_key`, que canonicaliza. Como o desempate de quase empate do
  `ConvergenceRecorder` é lexicográfico sobre essa tupla, chaves não canônicas
  produziriam desempate diferente do da CPU.
- **Veredito adversarial:** CONFIRMADO, classe `D3` com confiança média mantida. A
  dúvida óbvia, se o reparo do PSO já produz saída canônica na prática, tem resposta
  na evidência existente: em `artesp_rmsp_20`, `K=5`, seed 10, orçamento 2.000, as
  **992 avaliações de reparo do PSO bateram bit a bit** entre CPU e GPU, nas mesmas
  posições da sequência, em quatro execuções. Isso é consistente com "latente e não
  realizado", que é exatamente a categoria de `D3`.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, replicando as validações defensivas e trocando a tupla
  bruta por `solution_key`.
- **Onda:** B, dentro de `gpu/`.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero para a campanha CPU.

#### F8-11. O monitor térmico roda dentro do processo cronometrado e infla o tempo oficial da GPU

- **Frente:** F8.
- **Classe:** `M1`, confiança média quanto à magnitude.
- **Premissa:** `docs/experiments.md` seção 24, linha 839, "Cada execução individual
  será restringida a **uma thread de CPU**", e seção 25, linha 866, "O tempo
  registrado será exclusivamente o **tempo de otimização**". **Fonte: normativa.**
  O relatório atribuiu a exigência a "restrições globais do projeto", que é
  `constraints.md:14` e portanto **metodologia da auditoria**; o verificador
  localizou o lastro normativo genuíno nas duas linhas acima, e registrou que só a
  citação veio da fonte errada.
- **Previsto:** simetria de instrumentação entre os dois lados da razão
  `T_CPU / T_GPU`.
- **Código:** `gpu/src/metaheuristica_gpu/monitor.py:43-76`, onde `query_sample`
  dispara **dois** `subprocess.run` de `nvidia-smi` por amostra, e `:119-130`, com
  thread de intervalo 1 segundo; `run.py:203-207` envolve o laço cronometrado
  inteiro dentro do `with GpuSafetyMonitor(...)`, **no mesmo processo Python** que
  roda a otimização. Do lado CPU, `experiments/run.py:82-90` e
  `experiments/benchmark_operations.py:100-102` mostram `execute_campaign` chamado
  dentro do `with ResourceMonitor(...)` **no processo orquestrador**, com os workers
  medidos rodando como processos separados e monitorados por `/proc`.
- **Evidência:** a assimetria estrutural foi verificada linha a linha nos dois
  lados. Cada amostra disputa o GIL com a única thread computacional e paga dois
  `fork`/`exec`, e num cenário de ACO em `N=150` isso significa milhares de pares de
  subprocessos dentro do processo cronometrado. Nas sondas do relatório o monitor
  **não** estava ativo, de modo que os speedups medidos, 1,3518 no ACO e 2,866 no
  PSO, são **otimistas** em relação ao que a campanha registrará.
- **Veredito adversarial:** CONFIRMADO, classe `M1` mantida. A confiança média
  quanto à magnitude é apropriada: **o efeito em segundos não foi medido por
  nenhuma das duas verificações**.
- **Divergência auditor / verificador:** apenas a proveniência da citação de
  premissa, corrigida acima.
- **Decisão:** corrigir, amostrando por NVML em processo, sem `subprocess`, ou
  movendo o monitor para fora do processo medido como já se faz na CPU. A telemetria
  contínua é exigida pela seção 29.1 e não pode simplesmente ser removida.
- **Onda:** B, dentro de `gpu/`, antes de qualquer execução da B11A-E, porque afeta
  o número que a campanha vai publicar.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero para a campanha CPU.

#### F8-12. Duplicação literal de código normativo entre os dois pacotes

- **Frente:** F8.
- **Classe:** `M3`.
- **Premissa:** `docs/experiments.md` seção 29.1 da B11A, "A função CPU permanece
  normativa"; seção 30. **Fonte: normativa.**
- **Previsto:** uma implementação normativa única.
- **Código:** `gpu/src/metaheuristica_gpu/objective.py:125-167`
  (`evaluate_provisional_cpu`, réplica de `src/metaheuristica/objective.py:201-211`
  combinado com `_evaluate_arrays` e `_evaluate_aggregates`);
  `gpu/src/metaheuristica_gpu/aco.py:31-94` contra
  `src/metaheuristica/aco.py:79-186`; `gpu/src/metaheuristica_gpu/pso.py:50-126`
  contra `src/metaheuristica/pso.py:114-225`.
- **Evidência:** a duplicação foi confirmada termo a termo:
  `evaluate_provisional_cpu` reproduz hoje, na mesma ordem, `np.bincount`, `ddof=0`
  e a soma ponderada dos quatro componentes. `gpu_code_hash` de fato só varre
  `(root / "gpu/src").rglob("*.py")`, e `_protected_hashes` de fato lista só cinco
  arquivos, nenhum de `src/metaheuristica/`. As sondas confirmam que os valores
  coincidem bit a bit hoje, nas 992 avaliações de reparo do PSO.
- **Veredito adversarial:** CONFIRMADO, classe `M3` mantida, **com correção factual
  grave ao cenário de falha**.
- **Divergência auditor / verificador:** **o cenário de falha é falso: existe um
  alarme, e ele está ativo.** `execute_scenario` (`run.py:183-186`) chama
  `_cpu_readiness()` **incondicionalmente, antes de todo e qualquer um dos 60
  cenários**. `_cpu_readiness()` (`run.py:71-78`) dispara
  `experiments.run_benchmark readiness` como subprocesso e propaga falha se
  `returncode != 0`; essa CLI chama `verify_freeze_manifest`, que re-hasheia sem
  cache exatamente os arquivos de `protected_paths`, e `src/metaheuristica` está
  **expressamente incluído**. O verificador conferiu o artefato real
  `results/tables/benchmark_freeze_manifest.json`: existe, tem 52 arquivos
  protegidos, e **14 deles estão sob `src/metaheuristica/`**. Se qualquer um
  divergir, `verify_freeze_manifest` levanta `ConfigurationError`,
  `run_benchmark.py:198-200` retorna código 2, e `GpuConfigurationError` aborta
  `execute_scenario` **antes** de qualquer computação GPU. A cadeia completa foi
  seguida arquivo por arquivo. **A frase "sem nenhum alarme" é factualmente falsa.**
  O achado verificou corretamente que o manifesto **da GPU** não protege
  `src/metaheuristica/`, mas não verificou que o manifesto **da CPU** já o faz e que
  a GPU o consulta a cada execução.
- **Decisão:** corrigir como ônus de manutenção, unificando a implementação. A
  classe não muda, porque `M3` depende só da duplicação existir, não do cenário
  refutado. O argumento correto é: a duplicação é ruído de manutenção sob um regime
  que **já** a protege contra divergência silenciosa, e não vetor de corrupção
  despercebida.
- **Onda:** C.
- **Situação:** aberto, com o **componente ACO antecipado pelo pacote B5**, no commit
  `d297377`. Transferência de escopo registrada aqui porque ela não estava prevista em
  lugar algum. O pacote B5 tinha por escopo declarado **espelhar** em `gpu/aco.py` a
  variante O4 de F4-1; o que ele fez foi **unificar**: a classe local
  `_PartialState` foi apagada e aliasada para `_PartialConstructionState` da CPU
  (`gpu/src/metaheuristica_gpu/aco.py:31-38`), com `_heuristic_from_state` importado do
  mesmo módulo. Não existe, depois desse commit, nenhuma linha da variante O4 nem
  nenhuma asserção de contiguidade em `gpu/aco.py`, porque não existe mais construção
  espelhada: existe uma só. A revisão independente do pacote B5 julgou a unificação
  **tecnicamente superior ao espelhamento**, porque torna a divergência impossível em
  vez de improvável, e por isso a correção registrada é de plano e de registro, e não
  reversão de código. Consequências, todas verificadas pela revisão:
  1. **O escopo restante de F8-12 é `gpu/objective.py` e o grosso de `gpu/pso.py`.** O
     trecho `gpu/aco.py:31-94` que este dossiê nomeia como réplica de
     `src/metaheuristica/aco.py:79-186` já não existe como réplica. A restrição dura de
     não alterar a ordem das operações de somatório perde objeto para o ACO e continua
     valendo integralmente para os dois arquivos restantes.
  2. **O teste que o pacote C7 prescrevia já está escrito.**
     `gpu/tests/test_aco_gpu.py::test_gpu_construction_shares_the_cpu_partial_state`
     assevera que a função unificada é a mesma referência nos dois pacotes, que é
     exatamente o teste prescrito. C7 chegará com essa parte do seu escopo consumida.
  3. **Duas asserções de `test_aco_gpu_matches_cpu_on_a_real_instance` viraram
     tautológicas**, e isso é consequência real da unificação e não observação
     estética: as asserções sobre `solution` e sobre `checkpoints`
     (`gpu/tests/test_aco_gpu.py:26-47`) comparam duas execuções cuja construção passou
     a ser literalmente o mesmo objeto de código, logo não podem mais discriminar
     divergência de construção. O que continua com poder discriminante nesse teste é o
     `require_equivalent` que dispara dentro do lote por `verify_every_batch=True`, e
     que exercita o **avaliador** e não a construção. A vacuidade das asserções externas
     sob `verify_every_batch=True` já é objeto de F8-4 e é o pacote C6 que a resolve; o
     que se registra aqui é a perda de poder discriminante causada pela unificação, que
     é independente daquela.
  A **ordem de execução de C7 fica em aberto** e não é decidida aqui: a revisão do
  pacote B5 recomendou reavaliar se C7 ainda precisa ser o último pacote da Onda C,
  agora que a maior superfície do seu escopo em `gpu/` já foi tocada, e essa reavaliação
  depende do estado de C5, C6 e B20, que não está estabelecido. A emenda de escopo foi
  aplicada em `superpowers/B11B_plan_ondas.md`, seção do pacote C7; a emenda de ordem
  não.
- **Impressão digital:** pendente para o escopo restante. O componente antecipado não
  alterou bits: o commit `d297377` deu diff **zero** nos 42 cenários, conforme o Passo F
  registrado em F4-1.

#### F8-13. O pareamento do speedup contrapõe CPU com 16 workers simultâneos a GPU sequencial e exclusiva

- **Frente:** F8.
- **Classe:** `L1`.
- **Premissa:** `docs/experiments.md` seção 26, `S = T_CPU / T_GPU`; seção 29.1 da
  B11A, "O speedup é pareado com a execução CPU oficial de mesmo algoritmo,
  instância, `K` e seed" e "A execução requer exclusividade da placa"; seção 24,
  linha 853, "Nesta máquina de referência, o padrão será de 16 workers
  independentes, um por núcleo físico"; seção 29.2, a campanha GPU "é sequencial".
  **Fonte: normativa**, todas as citações literais confirmadas.
- **Previsto:** as três seções são internamente consistentes quanto ao pareamento
  por chave, e o código as cumpre: a junção usa `algorithm`, `instance`, `k` e
  `seed`, com `validate="one_to_one"`, e recusa se o resultado não tiver 60 linhas.
  **A premissa frágil não está no pareamento, está no que cada tempo mede.**
- **Código:** `gpu/src/metaheuristica_gpu/run.py:242-254`, `:194` e `:197`. Divide
  um tempo de CPU medido enquanto outras 15 execuções disputavam caches L3, largura
  de banda e envelope térmico por um tempo de GPU medido com a máquina praticamente
  ociosa, sob lock exclusivo e após 60 segundos de verificação de ociosidade. Não há
  controle CPU sequencial na campanha, nem campo que registre a condição de carga.
- **Evidência:** todas as citações numéricas foram recalculadas de forma
  independente e batem exatamente. Os dois únicos pares diretamente comparáveis,
  ambos do ACO em `artesp_rmsp_150`, contrapondo a projeção isolada da F4 ao tempo
  do piloto sob 16 workers: em `K=3`, 6.310,9 s isolado contra 6.389,35 s sob carga,
  isto é **1,243%** mais lento sob carga; em `K=8`, 11.023,2 s isolado contra
  10.971,45 s sob carga, isto é **0,4695%** mais rápido sob carga. **Os dois pares
  têm sinais opostos** e magnitude abaixo da dispersão de 4,5% que a própria F4
  mediu entre orçamentos.
- **Veredito adversarial:** CONFIRMADO, classe `L1` mantida. O verificador destacou
  que este achado é incomum entre os doze por **já vir autolimitado**: reconhece
  explicitamente que o código cumpre os documentos, calcula o efeito nos dois pares
  disponíveis, encontra sinais opostos e **conclui contra sua própria hipótese
  inicial** que nada nas medições sugere que o viés explique o `S` de 1,355 do ACO,
  e que quem explica é F8-2.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** registro apenas, com mitigação recomendada e barata, porque a frente
  ainda não produziu resultado: medir também uma referência CPU sequencial e
  exclusiva para os mesmos 60 pares, e publicar as duas razões. O motivo para
  mitigar mesmo assim é de escala: um viés de 1%, ainda que dentro do ruído, é mais
  de dez vezes a contribuição real da GPU medida no ACO, que é 0,093%.
- **Onda:** registro apenas, com recomendação de desenho para a B11A-E.
- **Situação:** fechado sem ação de código.
- **Impressão digital:** pendente.

#### F8-14. O tempo oficial exclui a preparação do dispositivo sem registrá-la separadamente

- **Frente:** F8.
- **Classe:** `D2`.
- **Premissa:** `docs/experiments.md` seção 29.1 da B11A, "O tempo oficial inclui
  transferências, sincronizações e arbitragens ocorridas durante a otimização.
  Contexto, compilação e aquecimento prévios são registrados separadamente"; seção
  25, "O cronômetro deverá iniciar imediatamente antes da inicialização operacional
  do algoritmo". **Fonte: normativa**, citação literal confirmada.
- **Previsto:** que aquilo excluído do tempo oficial fosse registrado em campo
  próprio.
- **Código:** `gpu/src/metaheuristica_gpu/aco.py:137-139` e `pso.py:138-140`, onde o
  cronômetro parte **depois** da construção de `GpuBatchObjective`, contra
  `src/metaheuristica/optimizer.py:125-129`, onde na CPU o cronômetro parte
  **antes** da construção do `FitnessEvaluator`. A construção faz
  `np.triu_indices(n_units)` na CPU, cinco transferências para o dispositivo, duas
  reduções e um `synchronize`.
- **Evidência:** medição direta em `artesp_rmsp_150`, `K=5`, com contexto CUDA
  aquecido: a construção custa **2,0 ms em regime**, com 3,0 ms na primeira vez e
  depois 2,046, 2,008 e 1,996 ms. O verificador confirmou que esse custo **não
  aparece em nenhum campo**: `warmup` cobre só `warmup_gpu()`, que é um
  `cp.arange(1024)` genérico não relacionado à instância, e `cold_total_seconds` é
  medido de antes de `warmup_gpu()` até depois de `cooldown()`, um superconjunto que
  inclui `runtime_seconds` inteiro mais preparo e resfriamento, sem isolar a
  construção.
- **Veredito adversarial:** CONFIRMADO, classe `D2` mantida: violação literal da
  exigência de registro separado, sem efeito material em resultado publicado, com
  magnitude honestamente caracterizada pelo próprio achado, cerca de 0,05% no PSO e
  0,001% no ACO, **e na direção favorável à GPU**, o que torna a assimetria
  conservadora.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, acrescentando campo próprio para o custo de preparação do
  dispositivo.
- **Onda:** B, dentro de `gpu/`.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero para a campanha CPU.

### 3.9. Frente F9 - resultados já publicados

**Nota de identificadores.** O relatório de origem, `frente-10-report.md`, numera os
achados como "Achado 1" a "Achado 6", sem prefixo de frente. Este registro os renomeia
para `F9-1` a `F9-6`, preservando a ordem. O mapeamento é direto: `F9-n` é o "Achado n"
do relatório de origem.

Seis achados, seis confirmados, zero refutados, nenhuma reclassificação. O
verificador reproduziu **toda** alegação quantitativa direto dos Parquet, com
scripts independentes, e os hashes dos artefatos oficiais permaneceram inalterados,
com `verify` do congelamento devolvendo saída 0 ao final da frente.

**Correção de contagem, propagada da especificação e do plano.** O dossiê da frente
afirmava "onze dos doze hiperparâmetros"; a contagem correta é **dez dos onze**,
porque o PSO tem quatro parâmetros, o ACO tem quatro e a Busca Tabu tem três,
totalizando onze. O auditor verificou por três vias independentes, incluindo as 23
linhas de `results/tables/tuning_parameter_effects.parquet`, que seriam 27 com doze
parâmetros, e confirmou pelo histórico que `ALGORITHM_FIELDS["tabu"]` nunca teve um
quarto campo. O verificador confirmou a contagem, com dez parâmetros de dois níveis
e só `tabu_tenure` com três. A substância do achado dirigido não muda.

#### Achado F9-1. A seleção congelada não é distinguível de ruído no tamanho de amostra do próprio tuning, e a cadeia de desempate documentada é inalcançável

- **Frente:** F9.
- **Classe:** `L1`. **É o achado mais consequente de toda a auditoria** e o que
  recebeu a verificação mais dura.
- **Premissa:** `docs/experiments.md:414-416`, a lista numerada dos três critérios,
  em que o segundo entra "em caso de resultados muito próximos" e o terceiro
  "persistindo empate prático", e `:421-425`, a operacionalização em `1e-12`; seção
  12.2, que publica os parâmetros congelados que governam as 1.620 execuções
  oficiais, com política `requires_new_tuning`. **Fonte: normativa.**
- **Previsto:** que "resultados muito próximos" e "empate prático" tivessem
  conteúdo, isto é que a proximidade prática entre configurações fosse reconhecida e
  resolvida pelos critérios 2 e 3, de modo que o parâmetro congelado fosse
  defensável como o melhor ponto da grade.
- **Código:** `experiments/tuning_analysis.py:19` e `:40-48`. Operacionaliza "muito
  próximos" como igualdade numérica dentro de `1e-12`. Como as médias observadas
  diferem por muito mais que isso, a seleção **reduz-se ao `argmin` da média de dez
  seeds** e os critérios 2, 3 e 4 nunca são consultados. O código é fiel à
  formulação precisa da linha 422 e infiel ao sentido das linhas 415 e 416, ambas na
  mesma seção.
- **Evidência (todos os números reproduzidos de forma independente pelo
  verificador):** folgas mínimas entre médias consecutivas de **`5,5052e-05` no
  PSO**, **`8,4949e-04` na Busca Tabu** e **`1,1869e-03` no ACO**, todas **oito
  ordens de grandeza** acima da tolerância de `1e-12`, logo os critérios 2, 3 e 4
  são inalcançáveis. Teste exato de permutação pareada por seed, com 1.024
  permutações de sinal:

  | Algoritmo | Média do 1º | Média do 2º | Diferença | Erro padrão pareado | `p` exato | Seeds em que o 1º é pior |
  |---|---:|---:|---:|---:|---:|---:|
  | Busca Tabu | 0,126415 | 0,129629 | 0,003214 | 0,005817 | 0,59375 | **5 de 10** |
  | ACO | 0,146303 | 0,151504 | 0,005201 | 0,013928 | 0,77539 | **6 de 10** |
  | PSO | 0,274437 | 0,287264 | 0,012826 | 0,015672 | 0,43750 | **5 de 10** |

  Nos três algoritmos **a diferença que decidiu o congelamento é menor que o erro
  padrão pareado da própria diferença**. Além disso, o desvio amostral do vencedor
  da Busca Tabu, 0,013287, é o **maior** dos quatro melhores pontos da grade, e o
  segundo colocado tem 0,009803: se o critério 2 tivesse sido alcançado, ele
  apontaria para outra configuração. Contrafactual medido, reexecutando o próprio
  `_choose_best` com a tolerância trocada pelo erro padrão pareado: **dois dos três
  conjuntos congelados mudariam**, com a Busca Tabu passando a
  `tabu_tenure=5, neighborhood_size=50, stagnation_limit=100` e o ACO a
  `alpha=1.0, beta=1.0, rho=0.1, n_ants=20`, e o PSO inalterado. O verificador
  reproduziu o contrafactual completo e ele de fato inverte os vencedores de Tabu e
  ACO e deixa o PSO igual.
- **Veredito adversarial:** CONFIRMADO. A defesa de "pareamento inválido" foi
  testada e **cai**: `optimizer.py:126` semeia o RNG direto com o inteiro da seed e
  `scenarios.py` gera um cenário por configuração por seed dentro do mesmo
  algoritmo, instância e `K`, o que é desenho pareado legítimo de números aleatórios
  comuns.
- **Divergência auditor / verificador:** uma correção factual, e **ela fortalece o
  achado**. O relatório diz que o vencedor do ACO é pior que o segundo colocado em
  **4 de 10** seeds; a recontagem seed a seed dá **6 de 10**. Busca Tabu 5/10 e PSO
  5/10 conferem. Este é um dos dois casos independentes do mesmo erro de
  subcontagem, tratado na conexão 4 da seção 5.
- **Decisão:** registro apenas, **e não reabrir a seleção agora**: trocá-la exigiria
  novo ciclo completo e a ordenação entre métodos não muda. Duas consequências
  obrigatórias para o relatório final. Primeira, os parâmetros congelados precisam
  ser apresentados como **`argmin` dentro do ruído**, jamais como ótimos: o que se
  pode afirmar é que são os de menor média observada. Segunda, isto **valida por
  medição** a exigência de colocar as três configurações de segundo colocado na
  impressão digital.
- **Onda:** registro apenas.
- **Situação:** fechado sem ação de código.
- **Impressão digital:** pendente. O achado **motiva** a cobertura das configurações
  de segundo colocado no oráculo.

#### Achado F9-2. A tolerância de empate é um escalar único compartilhado por três grandezas de unidades diferentes, e recalibrá-la promove o tempo médio a critério decisivo

- **Frente:** F9.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md:426-429`, que afirma explicitamente que "o
  tempo é somente o terceiro desempate, pois concorrência pode introduzir ruído",
  isto é o documento reconhece que a medida de tempo é contaminada e por isso a
  rebaixa deliberadamente; `:415-416`. **Fonte: normativa.**
- **Previsto:** uma hierarquia estável em que o tempo médio, grandeza reconhecida
  como ruidosa, só possa decidir depois de média e desvio terem falhado em separar
  as configurações.
- **Código:** `experiments/tuning_analysis.py:19` e `:42-47`, o laço
  `for column in ("mean_cost", "std_cost", "mean_runtime_seconds")` com
  `<= minimum + TOLERANCE` no **mesmo** `TOLERANCE` para as três colunas. Usa o
  mesmo escalar `1e-12` para o custo total, adimensional e da ordem de 0,13, para o
  desvio amostral, também adimensional, e para o tempo médio, em segundos e da ordem
  de 10 na Busca Tabu e de 1.300 no ACO. **Não existe forma de afrouxar a noção de
  empate no custo sem afrouxar simultaneamente, e na mesma magnitude numérica, a
  noção de empate em segundos.**
- **Evidência:** confirmado por execução. Com
  `TOLERANCE = 0.005817`, que é o erro padrão pareado da Busca Tabu e portanto uma
  calibração plausível de empate prático na escala do custo, o filtro do critério 2
  também usa `0,005817`, e como as dispersões dos quatro candidatos vão de 0,009803
  a 0,013287 **nenhuma é eliminada**; o critério 3 então recebe quatro candidatos
  com tempos 13,935 s, 14,260 s, 14,273 s e 14,342 s, e com tolerância de
  `0,005817 s` elimina três, restando um vencedor escolhido **pelo tempo médio**,
  exatamente a grandeza que a seção 12.1 declara ruidosa. O mesmo ocorre no ACO com
  `TOLERANCE = 0.013928`: o vencedor passa a ser decidido por 1.284,08 s contra
  1.312,21 s, diferença de 2% entre execuções concorrentes de 21 minutos.
- **Veredito adversarial:** CONFIRMADO por execução. Classe `D3` mantida.
- **Divergência auditor / verificador:** nenhuma. O auditor já declarava confiança
  média na classe, reconhecendo que "quem preferir chamar isso de `M3` tem
  argumento", e sustentando `D3` porque o desfecho concreto é uma decisão errada e
  silenciosa.
- **Decisão:** corrigir, com **uma tolerância por critério**, mantendo a de tempo em
  zero ou próximo de zero. O risco é de um ciclo futuro de tuning, ou de uma revisão
  que ache `1e-12` excessivamente rígido à luz de F9-1: a recalibração aparentemente
  inocente de um único número **inverte silenciosamente a hierarquia declarada**.
- **Onda:** B, junto de F2-13, que é a cobertura ausente da mesma tolerância.
- **Situação:** fechado com correção de código e **três** testes novos em
  `tests/test_tuning_analysis.py`, dois no commit do pacote B8 e um no commit de
  correções da revisão do lote L1. O escalar único `TOLERANCE` deu lugar ao
  mapeamento `TOLERANCES`, com uma
  tolerância **por critério**: `1e-12` em `mean_cost`, `1e-12` em `std_cost` e
  **zero por desenho** em `mean_runtime_seconds`. O laço de `_choose_best` passa a
  iterar o mapeamento, o que amarra cada critério à sua própria escala e torna
  impossível afrouxar o custo afrouxando junto os segundos.
  `experiments/analyze_tuning.py:122` republica o mapeamento no lugar do escalar,
  para que o documento de seleção registre o que foi de fato aplicado. **A seleção
  congelada não foi reaberta**: `mean_cost` e `std_cost` seguem em `1e-12`, a
  recalibração é de estrutura e não de valor, e F9-1 permanece `L1`, registro
  apenas. **Passo G.** Classe prevista `D3`; classe observada `D3`; a observação
  **bate** com a previsão. Sem reclassificação, e o Passo H não se aplica.
- **Impressão digital:** zero, conforme previsto, dentro do zero conferido no
  conjunto completo dos 42 cenários no Passo F do pacote B8. O pacote vive em
  `experiments/` e em `tests/`, fora do caminho científico executado pelo oráculo.
  **Passo G.** Diff previsto zero; diff observado zero; a observação **bate** com a
  previsão.

#### Achado F9-3. A análise oficial não é byte a byte reprodutível e reescreve arquivo protegido pelo congelamento, sem destino alternativo possível

- **Frente:** F9.
- **Classe:** `D3`.
- **Premissa:** `docs/experiments.md` seção 30, congelamento experimental, com
  `results/tables/benchmark_freeze_manifest.json` registrando
  `experiments/configs/frozen_parameters.toml` entre os 52 arquivos protegidos;
  seção 28, reprodutibilidade como propriedade verificável dos artefatos. **Fonte:
  normativa.** O `README.md:296-302` e `:305-307`, que documentam o comando de
  análise e o princípio de repetição por outro `output_root`, são **regra interna do
  repositório**.
- **Previsto:** que reexecutar a análise sobre insumos idênticos produzisse
  artefatos idênticos, e que o roteiro documentado pudesse ser reexecutado sem
  invalidar o congelamento.
- **Código:** `experiments/analyze_tuning.py:132` (`"selected_at": utc_now()`),
  `:143-152` (o TOML congelado embute `selection_sha256`), `:176` (`frozen_path`
  fixo, que **ignora `output_root`**) e `:177-188`; portão em
  `experiments/benchmark_freeze.py:114-123` combinado com
  `experiments/run_benchmark.py:76`. Grava um carimbo de tempo dentro do documento
  de seleção, embute o sha256 desse documento no TOML protegido, e **não oferece
  destino alternativo algum**, de modo que o mecanismo de "outro `output_root`"
  prescrito pelo README não protege este caminho. `_atomic_text` e
  `atomic_write_json` sobrescrevem sem checar existência, e a análise não tem modo
  de verificação.
- **Evidência:** demonstração executada dos dois lados, controle e falha, com a raiz
  redirecionada para espelho no scratchpad. Todas as decisões saem idênticas bit a
  bit e os dois Parquet saem byte a byte idênticos, mas `selected_at` muda, o sha256
  de `tuning_selection.json` passa de `effa018d...` para `34287782...`, a linha 4 de
  `frozen_parameters.toml` muda, e o sha256 do TOML passa de `4fc1c42d...` para
  `2af2b0f2...`, que é exatamente o valor protegido no manifesto. Substituindo apenas
  o TOML numa segunda raiz, `verify_freeze_manifest` falha com
  `ConfigurationError: congelamento divergente:
  ['experiments/configs/frozen_parameters.toml']`, enquanto o controle com o TOML
  oficial passa.
- **Veredito adversarial:** CONFIRMADO por leitura de código ponto a ponto. Classe
  `D3` mantida.
- **Divergência auditor / verificador:** nenhuma.
- **Decisão:** corrigir, preferencialmente removendo `selected_at` do documento ou
  movendo-o para fora do que é resumido pelo sha, que é a opção que também restaura
  a reprodutibilidade byte a byte; alternativamente, aceitar argumento de destino no
  CLI, ou acrescentar modo de verificação que compare em vez de escrever.
  **Consequência operacional para a Tarefa 19B, passo 3: contar com mudança de hash
  do `frozen_parameters.toml` mesmo sem mudança de parâmetro.** Registro que este
  achado não é hipotético para o auditor: é a razão pela qual ele **recusou-se a
  rodar o comando literal** do próprio dossiê e espelhou a raiz no scratchpad, o que
  foi a decisão certa.
- **Onda:** B, com prioridade, porque interage com o congelamento.
- **Situação:** aberto.
- **Impressão digital:** pendente. Diff esperado zero em conteúdo de decisão, e
  **não** zero em hash de artefato, o que é precisamente o achado.

#### Achado F9-4. Com dois níveis por parâmetro, o tuning não distingue melhor valor de melhor extremo testado

- **Frente:** F9.
- **Classe:** `L1`.
- **Premissa:** `docs/experiments.md:396-400`, que declara a estratégia como "busca
  em grade curta e controlada", e a seção 12.2, que apresenta o resultado como
  "Parâmetros selecionados" com política `requires_new_tuning`. **Fonte: normativa.**
- **Previsto:** que a grade curta fosse suficiente para escolher os hiperparâmetros
  que governam toda a campanha, e que o resultado fosse apresentado como seleção de
  parâmetros.
- **Código:** `experiments/configs/tuning.toml:20-35`, dez listas de dois valores e
  uma de três. Avalia, por construção, apenas os extremos.
- **Evidência:** o auditor **recusou explicitamente** a formulação vazia de que "os
  vencedores estão nas bordas", porque numa grade de dois níveis todo vencedor está
  num extremo por construção. A formulação com conteúdo é a inversa, sobre o que o
  desenho é incapaz de detectar: não distingue "melhor valor" de "melhor entre os
  dois extremos testados"; não detecta ótimo interior, porque não há ponto interior
  onde ele possa aparecer; e não informa se o ótimo está fora da faixa, porque não
  existe curvatura observável. Única observação que o desenho permite, e o
  verificador a recomputou: no único parâmetro com três níveis a resposta marginal
  **não é monótona**, com médias **0,140539** em `tabu_tenure=5`, **0,137703** em
  `10` e **0,138944** em `20`, mínimo no interior, e o vencedor global da Busca Tabu
  tem justamente `tabu_tenure=10`.
- **Veredito adversarial:** CONFIRMADO por leitura da grade e recomputação dos
  efeitos. Classe `L1` mantida.
- **Divergência auditor / verificador:** nenhuma. O auditor já registrou a ressalva
  honesta de que as três médias estão dentro do ruído, como F9-1 mostra, e que
  portanto isto **não é prova** de curvatura, apenas a única observação que o
  desenho permite.
- **Decisão:** registro apenas. O relatório técnico deve descrever o resultado como
  "melhor configuração entre as avaliadas" e registrar as três incapacidades.
- **Onda:** registro apenas.
- **Situação:** fechado sem ação de código.
- **Impressão digital:** pendente.

#### Achado F9-5. As estimativas de duração do roteiro vêm de uma única seed, com dois pontos de ancoragem e interpolação linear, e são dominadas pelo ACO

- **Frente:** F9.
- **Classe:** `L1`.
- **Premissa:** o roteiro estático ordena 270 subgrupos por duração estimada e
  publica `estimated_seconds_per_run` e `estimated_seconds_total`; `README.md:286`
  converte isso em "estimativa atual é de 35 a 40 horas no total, ou 6,5 a 8 horas
  por lote", que é a grandeza usada para autorizar a janela de execução da B11-E.
  **Fonte: normativa** quanto ao desenho do roteiro em `docs/experiments.md` seção
  29.2; a frase publicada está no `README.md`, que é **regra interna do
  repositório**, e é o artefato a corrigir.
- **Previsto:** uma estimativa de duração utilizável para planejar a campanha e
  ordenar subgrupos.
- **Código:** `experiments/benchmark_schedule.py:26-54`, em particular `:39`, que
  aceita apenas `K` em `{3,8}`, `:43-47`, que exige 18 âncoras, e `:52-53`, com a
  fórmula literal; insumo em `experiments/configs/pilot.toml:5`,
  `seeds = [20260818]`, seed única. Não há repetição, logo não há estimativa de
  variância, e há apenas dois pontos, logo a linearidade em `K` é suposição do
  desenho e não pode ser testada com os dados oficiais do piloto.
- **Evidência:** o verificador reproduziu tudo. Âncoras do ACO em `artesp_rmsp_60`:
  **986,482158 s** em `K=3` e **1515,557278 s** em `K=8`, interpolando para
  **1198,11 s** em `K=5`. As dez execuções de tuning da configuração congelada do
  ACO no mesmo ponto medem média **1312,211977 s**, desvio amostral **43,907980 s**,
  mínimo **1237,607057 s** e máximo **1395,325777 s**. A estimativa é **8,70% menor**
  que a média observada, **2,60 desvios padrão** abaixo dela, e fica **fora de todo
  o intervalo** observado nas dez seeds. O erro é sistemático na direção do otimismo,
  compatível com resposta convexa em `K`, e o desenho de duas âncoras não tem como
  detectá-lo. Participação no tempo total do roteiro, recomputada:
  **ACO 98,061%, 502,09 h; PSO 1,092%, 5,59 h; Busca Tabu 0,847%, 4,34 h; total
  512,02 h**, ideal com 16 workers 32,00 h.
- **Veredito adversarial:** CONFIRMADO por execução e leitura de código. Classe `L1`
  mantida: é limitação conhecida da estimativa de tempo, que não afeta a ordenação de
  prioridade, que é o contrato real do roteiro.
- **Divergência auditor / verificador:** uma diferença de arredondamento
  irrelevante. O relatório cita **1198,13 s**; o valor correto é **1198,11 s**,
  diferença de 0,02 s ou cerca de 0,002%.
- **Decisão:** registro apenas, com **duas ações de fechamento, nenhuma de código**:
  registrar a limitação no relatório técnico, e **atualizar a duração prevista em
  `README.md:286-287` na tarefa de fechamento**, depois de a Onda B existir e de a
  impressão digital confirmar a preservação de bits. Se a Onda B aplicar o ganho de
  3,58x do ACO, o roteiro continuará byte a byte idêntico, o que é correto porque as
  estimativas só ordenam prioridade e a ordem relativa não muda se todos os tempos do
  ACO forem divididos pelo mesmo fator; mas os campos de estimativa passarão a
  descrever um tempo que não existe mais, e o `README.md` passará a **superestimar**
  a duração por fator próximo de três, já que 98% do total é ACO.
- **Onda:** registro apenas, com ação documental na tarefa de fechamento.
- **Situação:** fechado sem ação de código.
- **Impressão digital:** pendente.

#### Achado F9-6. A seção 12.2 publica quatro dos onze contrastes marginais e não registra que em dois deles o nível congelado não é o nível marginalmente melhor

- **Frente:** F9.
- **Classe:** `L1`.
- **Premissa:** `docs/experiments.md:432-435`, que declara os efeitos marginais como
  exclusivamente descritivos e não causais por existirem interações; seção 12.2, que
  seleciona em prosa alguns contrastes para comentar. **Fonte: normativa.**
- **Previsto:** uma descrição fiel do que a tabela de efeitos marginais mostra, com
  a ressalva de não causalidade.
- **Código:** `docs/experiments.md:449-452`, a prosa; dados completos em
  `results/tables/tuning_parameter_effects.parquet` e produção em
  `experiments/tuning_analysis.py:147-172`. A tabela publica os 23 níveis e portanto
  o dado está completo e correto no artefato; a prosa comenta quatro contrastes, e
  **todas as quatro afirmações são verdadeiras**. O que a prosa não diz é que em dois
  dos onze parâmetros o nível marginalmente melhor **não** é o nível congelado, e os
  quatro contrastes escolhidos são todos casos em que os dois coincidem.
- **Evidência:** o verificador leu `docs/experiments.md:449-455` literalmente e
  confirmou que a prosa cita apenas `alpha=1.0`, `inertia=0.4`, `social=1.5` e
  `stagnation_limit=100`, sem menção a `cognitive`, `neighborhood_size` ou `beta`. E
  recomputou os onze contrastes, ordenados por magnitude: `alpha` 0,13417, **`beta`
  0,04342**, `inertia` 0,03621, `social` 0,02532, `n_ants` 0,02366, `rho` 0,01700,
  `stagnation_limit` 0,01534, `n_particles` 0,01140, `cognitive` 0,00512,
  `tabu_tenure` 0,00284, `neighborhood_size` 0,00273. **`beta` é de fato o segundo
  maior contraste da grade e não é comentado**, logo o critério de escolha dos quatro
  não é declarado e não corresponde à ordem de magnitude. Os dois casos de
  divergência foram confirmados dígito a dígito: no PSO, `cognitive` marginal
  favorece 1,5 com 0,313817 contra 0,318939, e o congelado é 2,0; na Busca Tabu,
  `neighborhood_size` marginal favorece 50 com 0,137696 contra 0,140428, e o
  congelado é 20. Um leitor que reconstruísse a configuração nível a nível chegaria
  a `cognitive=1.5` no PSO e `neighborhood_size=50` na Busca Tabu, e nenhuma das
  duas é a configuração oficial.
- **Veredito adversarial:** CONFIRMADO por leitura literal do documento e
  recomputação dos contrastes. Classe `L1` mantida: é lacuna de registro e de alcance
  interpretativo, não erro de cálculo nem inconsistência de artefato, e não é `M3`
  porque não é legibilidade de código.
- **Divergência auditor / verificador:** nenhuma. O auditor registrou por conta
  própria que isto **não contradiz** o julgamento da frente F5, que considerou a
  seção 12.2 consistente, porque o contraste da Busca Tabu que a seção publica é
  correto e sobrevive à desagregação por `n_viz`.
- **Decisão:** registro apenas, com uma frase a acrescentar ao documento na tarefa de
  fechamento: o vencedor de cada algoritmo é a melhor **combinação** e não a
  composição dos melhores níveis, o que é exatamente a consequência esperada de
  haver interações que o próprio documento reconhece.
- **Onda:** registro apenas, com ação documental na tarefa de fechamento.
- **Situação:** fechado sem ação de código.
- **Impressão digital:** pendente.

## 4. Ausências afirmadas: o que foi verificado e não rendeu achado

Metade do valor de uma auditoria é distinguir "não havia problema ali" de "não
olhamos ali". Esta seção registra as verificações que foram executadas, passaram, e
portanto **não** geraram achado. Onde há número, ele é medido, não presumido.

**Núcleo compartilhado (F1).** As `K(N-K)` avaliações do guloso conferem exatamente
nas 18 combinações oficiais. Os limiares `ceil(jB/100)` conferem em sete orçamentos,
incluindo os três oficiais, com o último limiar igual a `B` e sequência estritamente
crescente. A canonicalização é invariante sob permutação de rótulos em 300 soluções
vezes todas as `K!` permutações, com zero falhas. O reparo é determinístico em cinco
repetições e tem terminação provada, com no máximo `K-1` iterações. Existe um único
caminho de agregação, `_evaluate_aggregates`, sem renormalização depois da soma
ponderada. O desvio padrão populacional é idêntico nos dois componentes de
equilíbrio. A contagem de exatamente 100 checkpoints confere. **Zero `D1`, e isso é
afirmação e não lacuna.**

**PSO (F3).** A decodificação `min(floor(K*x), K-1)` é conforme, com o extremo
`x = 1.0` testado. O instantâneo único do melhor global por iteração é conforme, e
`gbest` só é substituído por `_copy_best`, nunca mutado no lugar. A população inicial
é integralmente avaliada antes da primeira atualização. A contabilidade das
avaliações de reparo é conforme: a identidade
`particles_evaluated + repair_evaluations == evaluations == 60000` vale em **160 de
160** execuções oficiais de PSO do tuning. A projeção `x' = (lote + u)/K` é conforme
no caminho normal, com desvio máximo de 16 ULP. **A hipótese de que o reparo
consumisse o orçamento está REFUTADA por medição:** a fração é 0,0444 na configuração
congelada.

**ACO (F4).** A unicidade canônica foi confirmada exaustivamente, com contagem igual
a `S(n,k)` para `2 <= n <= 9`. A abertura obrigatória não falha em prefixo
alcançável. `eta` está sempre em `[1,2]`. As probabilidades em log são estáveis. O
depósito é estritamente positivo, com limite provado de `custo <= 0,862854` em
`K=8`.

**Busca Tabu (F5).** As **oito** verificações obrigatórias foram confirmadas por
execução instrumentada, e não por leitura: proibição efetiva de movimentos que
esvaziariam a origem; enumeração completa dos movimentos válidos; amostragem uniforme
sem reposição; contagem do prazo tabu em movimentos aceitos e não em iterações;
aspiração liberada apenas por melhora estritamente superior a `1e-12`; aceitação do
melhor movimento admissível mesmo quando piora; os dois modos de reinício;
estabilidade dos rótulos ao longo da trajetória; e a cadeia de desempates. **Zero
`D1`.** **A hipótese dirigida de que a Busca Tabu se beneficia de trajetória mais
longa está REFUTADA.**

**Benchmark (F6).** A aritmética da barreira está correta e foi confirmada por
execução: 1.620 cenários, 5 lotes de 324, 270 subgrupos de 6, 54 subgrupos por lote e
32.400 checkpoints; lacuna e temporário são de fato rejeitados. **O auditor testou e
refutou a própria suspeita** de que a guarda de temporários fosse vazia por causa de
nomes ocultos, porque `pathlib.Path.glob` casa dotfiles no Python 3.14.

**CPU (F7).** **A suspeita do coordenador sobre threads foi REFUTADA por medição:**
uma thread computacional por execução, confirmada, com 4 threads de sistema por
processo otimizador das quais 3 permanecem em zero tick do início ao fim. A
interpolação linear do roteiro **se sustenta**, com erro de -1,3% na soma do par
dominante, que é 84,8% do orçamento.

**GPU (F8).** A fronteira aprovada é respeitada, com o RNG na CPU: os dois
otimizadores criam `np.random.Generator(np.random.PCG64(run_config.seed))` na CPU,
exatamente como o caminho normativo, e nenhum módulo de `gpu/src` importa
`cupy.random`. Orçamento e ordem de consumo são **exatamente iguais**, com sequência
idêntica em 100% das posições, inclusive nas 992 avaliações de reparo do PSO. Solução
final e custo final coincidem **bit a bit**. O kernel de `float64` passa. As 992
avaliações de reparo do PSO coincidem bit a bit entre CPU e GPU nas mesmas posições
da sequência, em quatro execuções.

**Resultados (F9).** As cinco verificações obrigatórias foram executadas: a seleção é
reprodutível a partir dos Parquet consolidados; a cadeia de desempate está
implementada na ordem documentada; `ddof=1` é usado na seleção e `ddof=0` no
coeficiente de variação, como o documento manda; os efeitos marginais são o que o
documento afirma e sua natureza descritiva está registrada; e o manifesto é
consistente com as tabelas, com as contagens conferidas. Os hashes dos artefatos
oficiais permaneceram inalterados e `verify` do congelamento devolveu saída 0.

## 5. Passagem transversal

O que segue não é alcançável por auditor de frente única. As conexões 1 a 4 foram
identificadas pelo coordenador durante a Fase 1; as conexões 5 a 13 foram
encontradas nesta passagem, com as três que o diário havia explicitamente delegado a
esta tarefa incluídas entre elas.

### Conexão 1. A prescrição de F1-05 é superada por F4-1, e a medição de F1-05 se sustenta

A frente F1 propôs acelerar o ACO trocando `np.mean` e `np.std` por aritmética
`float`, o que **quebraria os bits** e disparia o ramo alterado. A frente F4 achou
caminho equivalente que **preserva os bits exatamente**, a variante O4, que monta
matriz `(m,K)` contígua e faz as reduções com `np.add.reduce` replicando a aritmética
de `numpy._methods._var` na mesma ordem de operações. A verificação confirmou a
identidade com **mais de 61.000 casos adversariais e dois controles negativos**, sem
contra-exemplo sob ordem C.

**Resolução: apenas a prescrição de F1-05 é superada; a medição se sustenta.** Esta
formulação corrige duas posições anteriores do coordenador, que primeiro registrou
F1-05 como "supersedido" e depois comparou 3,58x com 4,9x. O verificador recusou as
duas: a medição de 90,1% reproduz e tem corroboração independente de 86,3% por
`cProfile`; e comparar 3,58x com 4,9x é comparar escopos diferentes, um sobre o ACO
inteiro e outro sobre `_evaluate_aggregates` isolado. **O que refuta a ressalva de
F1-05 é a existência demonstrada de caminho bit-preservador, não a comparação de
fatores.**

Consequência: F1-05 não abre correção própria. A onda de correção executa F4-1, que
absorve o ganho, e o parágrafo "Prioridade relativa entre os dois achados `M1`" de
F1-06 deve ser riscado, porque apresenta uma dicotomia falsa. **Instrução cumprida no
pacote B5**, e a forma de cumprimento está registrada no campo `Situação` de F1-05: o
parágrafo pertence ao relatório de origem da frente F1 e nunca existiu neste registro
versionado, logo a instrução é inócua aqui; a dicotomia foi resolvida de fato, porque a
terceira opção que ela negava é a que o pacote executou.

### Conexão 2. Fechamento da divergência entre 19,0 s por execução e 5,2 a 5,8 h de economia

Os dois números **medem coisas diferentes**, e a aritmética que os liga é a seguinte.

- **F4, item de baixa prioridade sem número próprio:** `objective.py:105-123`
  recomputa `np.triu_indices(150)` e recoleta 11.175 elementos de duas matrizes em
  cada uma das 150.000 avaliações completas; precomputar vale **19,0 s por
  execução**. Escopo: **uma** execução, do ACO, na instância `artesp_rmsp_150`, com
  orçamento 150.000, cobrindo **apenas** a pré-computação do triangular e do gather.
- **F1-06, número do verificador:** economia de **5,2 a 5,8 h-CPU**, com estado atual
  entre 9,8 e 10,1 h-CPU e piso bit-seguro entre 4,0 e 4,9 h-CPU. Escopo: a
  **campanha inteira**, isto é 1.620 execuções sobre 18 combinações e três
  orçamentos, cobrindo a pré-computação **mais** a remoção da canonicalização e da
  validação duplicadas.

**Ponte aritmética.** O verificador mediu, em `N=150`, `triu_indices` em `43,1 us` e o
gather isolado em `70,8 us`, somando `113,9 us` por avaliação, o que dá **17,1 s por
execução**, contra os 19,0 s do relatório da F4: os dois coincidem em ordem de
grandeza, com a diferença atribuível a máquina distinta. A campanha tem **540**
execuções com orçamento 150.000, as seis combinações de `N=150` vezes 90 execuções,
logo o item da F4 vale entre **2,6 e 2,9 h-CPU** de campanha. Isso é um
**subconjunto próprio** dos 5,2 a 5,8 h-CPU de F1-06: a diferença são as outras
1.080 execuções, com orçamentos de 20.000 e 60.000, mais a remoção da dupla
canonicalização e validação, que o item da F4 não inclui.

**Número único a usar na onda de correção: 5,2 a 5,8 h-CPU de economia de campanha**,
que é o valor do verificador e o escopo completo da correção bit-segura em
`objective.py`. Os 19,0 s ficam registrados como **âncora por execução da combinação
mais caro**, útil para dimensionar o ganho por cenário, e **não** devem ser
multiplicados por 1.620, que produziria 8,55 h-CPU e superestimaria a economia por
supor que todas as execuções usam orçamento 150.000.

### Conexão 3. Caminho por subgrupo contra caminho saturado: duração e raio de dano em direções opostas

As duas decisões **não são separáveis**.

| | duração total | raio de dano de uma morte de worker |
|---|---:|---:|
| caminho documentado, por subgrupo | **85,34 h**, 17,07 h por lote | **6** cenários |
| caminho saturado, por lote | **32,00 h** ideais | **324** cenários |

A duração vem de F7-1, confirmada por recálculo independente sobre o roteiro
versionado, com 512,02 h-CPU e 6 processos reais medidos para 6 tarefas submetidas. O
raio de dano vem de F6-06, confirmado com o alcance corrigido: o "324" do relatório
original só vale para `retry` sem filtro ou `execute --batch N` sem filtros, e a
invocação por subgrupo que o `README.md` documenta submete 6 por vez.

**O caminho rápido é também o caminho de falha mais custosa.** A decisão precisa ser
tomada junto com a correção de F6-06, que distingue `BrokenProcessPool` de falha
algorítmica, e não isoladamente. Com F6-06 corrigido, o raio de dano do caminho
saturado deixa de consumir a tentativa única e a escolha passa a ser dominada pela
duração; sem F6-06 corrigido, o caminho saturado arrisca bloquear a campanha inteira
com um único evento de memória. **Recomendação: corrigir F6-06 primeiro, e só então
adotar o caminho saturado.** O caminho saturado é válido de ponta a ponta e passa a
barreira, o que foi confirmado por execução nas duas verificações, mas **não está
documentado no `README.md`**, e essa lacuna documental precisa ser sanada junto.

### Conexão 4. Duas frentes independentes cometeram o mesmo erro de subcontagem em comparação pareada de dez seeds

| Frente | Achado | Publicado | Correto | Efeito |
|---|---|---:|---:|---|
| F4 ACO | F4-2, sinal invertido entre `beta=2` e `beta=1` no canto vencedor | 4 de 10 | **6 de 10** | fortalece |
| F9 resultados | F9-1, seeds em que o vencedor do ACO é pior que o vice | 4 de 10 | **6 de 10** | fortalece |

Os dois casos são independentes, foram recontados seed a seed por verificadores
diferentes, e **nos dois a correção fortalece o achado**, porque mais seeds
divergindo do sinal da média é mais evidência de que a diferença é ruído. O padrão
é notável: dois auditores distintos, sobre o mesmo Parquet e o mesmo par de
configurações do ACO, produziram a mesma subcontagem. A explicação mais provável é
contagem de diferenças estritamente negativas em vez de divergências do sinal da
média, e a lição é que comparação pareada de dez seeds deve publicar as dez
diferenças, não só o contador.

### Conexão 5. Quatro mutantes de `tabu.py` que passam os 254 testes validam a premissa da frente F2 por outro caminho

O diário delegou esta reconciliação explicitamente a esta tarefa. **Não há dupla
contagem, e os dois verificadores concordam nisso de forma independente.** Os quatro
mutantes da F5, `B`, `B linha`, `A` e `C`, não aparecem entre as 42 mutações da F2;
há sobreposição de **vizinhança de código** e não de mutação. Em `tabu.py:208`, a
mutação `M13` da F2 troca `<` por `<=` **e** troca `- COST_TOLERANCE` por
`+ COST_TOLERANCE`, e **morre**; o mutante `A` da F5 troca só `<` por `<=`, mantendo
`- COST_TOLERANCE`, e **sobrevive**. As duas reexecuções, feitas cada uma sob a
definição exata do respectivo relatório, produzem **resultados opostos no mesmo ponto
do código**, o que demonstra por construção que são mutações diferentes.

**O que a conexão acrescenta.** A frente F2 estabeleceu que a suíte tem poder de
detecção limitado, com 16 de 42 mutações sobrevivendo. A frente F5 estabeleceu algo
mais forte no ponto mais sensível: um mutante que **muda o resultado do algoritmo de
referência em 7%** passa os 254 testes sem uma única falha. Como a Busca Tabu é a
régua contra a qual ACO e PSO são julgados, a conclusão conjunta é que **a suíte
atual não protege a régua**. Isso valida a premissa da F2 por medição de consequência,
e não só por contagem de mutantes. Consequência de onda: F2-06, F2-07, F5-5 e F5-6
entram no mesmo commit, porque cobrem a mesma região por quatro ângulos.

### Conexão 6. O portão que protege as 40 horas está simultaneamente sem teste e incorreto

Três achados de duas frentes convergem no mesmo mecanismo:

- **F2-04** (`M2`): `verify_freeze_manifest` **não possui teste algum**, e onde
  poderia ser exercitado é anulado por `monkeypatch`. Inserir `return manifest` na
  entrada da função mantém a suíte em 254 aprovados.
- **F6-02** (`D3`): o manifesto é gerado sobre worktree suja, com
  `allow_dirty=True` hardcoded, sem revalidar comportamento, e `pilot_commit` é
  escrito e **nunca lido**. A divergência já existe hoje, com o piloto em `5a9b805`
  e o `HEAD` em `739fb3d`.
- **F6-03** (`D3`): a verificação **nunca chama `protected_paths(root)`** e portanto
  não vê arquivo novo dentro do escopo protegido.

Isoladamente cada um é sério; juntos formam um quadro pior que a soma. O portão
formal do congelamento é o único mecanismo que separa a campanha de 40 horas de uma
alteração de algoritmo no meio do percurso, e ele **não tem teste que detecte sua
remoção** e **não implementa duas das regras que declara**. A cadeia inteira foi
demonstrada ponta a ponta: com `c_affinity` dobrado, gerar aceitou, verificar
aceitou, `readiness` declarou `ready: true`, e só `_validate_result` contra artefato
real do piloto recusou. **Consequência de onda: os três entram no mesmo commit, e
esse commit tem precedência sobre os demais da Onda B**, porque é o que protege todos
os outros.

### Conexão 7. O identificador por conteúdo e a fixação das instâncias são o mesmo buraco visto de dois lados

- **F6-08** (`D3`): o `scenario_id` cobre o SHA-256 do **JSON** da instância, mas os
  dois Parquet que carregam demanda, produção e métricas de par **não entram no
  identificador**, e as três instâncias leem os mesmos dois arquivos. Multiplicar
  `passengers_day` por 1,5 não muda o identificador.
- **F2-15** (`M2`): os arquivos de instância versionados **não estão fixados por
  teste algum** ao gerador nem a hash conhecido; alterar o `tiny_manual.json`
  versionado mantém a suíte em 254 aprovados.

O mesmo dado, os mesmos arquivos, dois mecanismos ausentes. A contenção que existe
hoje é o congelamento, que lista os dois Parquet em `FIXED_PROTECTED`, e essa
contenção depende do mecanismo da conexão 6, que está sem teste. **Além disso, a
terceira camada de contenção não existe no encerramento**: `finalize_benchmark`
chama `consolidate_campaign`, que apenas revalida com `validate_document` e **não
reavalia o objetivo**. Consequência de onda: F6-08 e F2-15 entram no mesmo commit,
depois do commit da conexão 6.

### Conexão 8. Corrigir F4-1 sem espelhar em `gpu/` destrói o experimento de speedup do ACO

Esta é a conexão de maior consequência prática encontrada nesta passagem, e o diário
havia delegado a reconciliação entre F8-2 e F4-1 a esta tarefa.

A verificação de F8-2 mediu, em `artesp_rmsp_150`, `K=5`, seed 10: o dispositivo
inteiro responde por **0,093%** do tempo GPU, o teto de Amdahl do dispositivo é
**1,0072**, o ganho atribuível ao dispositivo e ao lote é **2,20%** e o ganho da
reescrita de CPU é **97,60%**, com speedup observado de **1,3518**. Ou seja, a
variante GPU do ACO é predominantemente uma reescrita de CPU que remove
recomputação, que é **exatamente o mesmo tipo de otimização que F4-1 identificou no
caminho normativo**, com fator medido de **3,58x preservando os bits**.

**A aritmética que ninguém dos dois lados fez.** Com `T_CPU = 221,12 s` e
`T_GPU = 163,22 s`, aplicar F4-1 ao caminho CPU levaria `T_CPU` a cerca de
`221,12 / 3,58 = 61,8 s`, e o speedup passaria de 1,3518 para cerca de **0,38**, isto
é a variante GPU do ACO ficaria cerca de **2,6 vezes mais lenta** que a CPU
otimizada. A conclusão é dupla e ambos os lados importam. Primeiro, isto **confirma
por outro caminho** o veredito de F8-2: o `S` de 1,35 nunca mediu a GPU, e uma
otimização de CPU melhor o inverte. Segundo, e acionável: a "Nota para a onda de
correção" de F4-1 já registra que
`gpu/src/metaheuristica_gpu/aco.py:42-84` reimplementa o mesmo padrão de
recomputação e que qualquer mudança na construção da CPU precisa ser espelhada lá
para que `require_equivalent` continue válido. **Esse espelhamento não é cosmético:
sem ele, a Onda B destrói o único resultado científico que a B11A-E produziria para o
ACO.** Consequência de onda: o espelhamento em `gpu/` é parte obrigatória do commit
de F4-1, não item separado, e a decisão de desenho de F8-2 precisa ser tomada antes
da B11A-E.

### Conexão 9. Um defeito de fronteira de orçamento no núcleo compartilhado que três frentes viram pela metade

Três achados de três frentes tocam `src/metaheuristica/optimizer.py:99-104`, a função
`_stop_at_limit`, e nenhuma das três vê o quadro inteiro:

- **F1-04** (`D2`, frente do núcleo): a mensagem de `EvaluationLimitReached`
  interpola `evaluations` duas vezes. A frente do núcleo olhou a **mensagem**.
- **A5** (`D2`, frente do PSO): os contadores de saturação incluem a iteração
  interrompida, porque `EvaluationLimitReached` propaga antes do incremento de
  `iterations_completed`. O verificador acrescentou que **a última iteração de
  qualquer execução do PSO nunca é contada**, mesmo em orçamento que divide exato,
  porque `_stop_at_limit` verifica `remaining == 0` **depois** de uma avaliação bem
  sucedida.
- **F5-3** (`D2`, frente da Busca Tabu): o reinício que consome a última avaliação
  não é contabilizado, porque as duas linhas de incremento ficam depois do
  `try/finally` que envolve `context.evaluate`.

**A síntese que nenhum dos três relatórios faz:** o mecanismo é único e mora no
núcleo compartilhado, não em `pso.py` nem em `tabu.py`. `_stop_at_limit` levanta a
exceção **depois** de a avaliação ter sido consumida e **antes** de o chamador poder
fechar sua contabilidade, e cada algoritmo perde o que quer que estivesse depois do
ponto de levantamento. Os três achados são a mesma falha de contrato vista de três
módulos diferentes, e o auditor do núcleo, que olhou a função, viu só a interpolação
da mensagem. **Consequência de onda: F1-04, A5 e F5-3 devem ser corrigidos como um
único problema de contrato, e a correção pertence a `optimizer.py`, não aos três
algoritmos.** Os três estão classificados `D2`, todos com efeito confinado a
diagnóstico, o que mantém a prioridade baixa mas a correção unificada.

### Conexão 10. Tolerância mais desempate lexicográfico é um padrão de desenho do projeto, e aparece em cinco lugares com quatro classes diferentes

| Achado | Local | Classe | Premissa violada |
|---|---|---|---|
| F1-03 | `ConvergenceRecorder._is_better`, `metrics.py:153-165` | `D3` | seção 9, curva não crescente |
| A9 | `_best_comparison` do PSO, `pso.py:149-159` | `L1` | nenhuma normativa; premissa era metodológica |
| F5-2 | `_candidate_is_better` da Busca Tabu, `tabu.py:153-163` | `D3` | seção 14, "o melhor movimento admissível é sempre aceito" |
| F9-2 | `_choose_best` do tuning, `tuning_analysis.py:42-47` | `D3` | seção 12.1, hierarquia de critérios |
| F8-1 | `arbitrate_best`, `numerics.py:80-87` | `M3` | chave **diferente** das outras quatro |

O padrão estrutural é idêntico nos cinco: comparação com banda de `1e-12` seguida de
desempate por tupla, o que produz relação **não transitiva** e resultado dependente
da ordem de apresentação. **Isto não é um defeito replicado quatro vezes: é uma
decisão de desenho do projeto, deliberada e documentada em três seções normativas.**
É essa constatação que justifica o rebaixamento de A9 de `D3` para `L1`: onde não há
premissa normativa violada, o padrão é desenho e não defeito. E ela justifica manter
`D3` em F1-03, F5-2 e F9-2, porque nesses três existe premissa normativa explícita
que o padrão viola.

**Consequência de risco, e é ela que faz esta conexão valer.** `arbitrate_best` usa
`(custo CPU, rótulos)` com o custo **primeiro**, contra rótulos apenas nas outras
quatro. Uma correção que "unifique o desempate" sem notar essa diferença introduziria
divergência de critério entre CPU e GPU exatamente onde hoje não existe nenhuma, que
é precisamente o erro que a correção proposta por F8-1 cometia. **A onda de correção
deve tratar as quatro instâncias normativas como um único problema e deixar
`arbitrate_best` fora dele, removendo-o.**

### Conexão 11. A comparação central do relatório final repousa sobre duas fundações moles ao mesmo tempo

- **F1-09** (`L1`): a unidade de orçamento não mede trabalho comparável. Uma unidade
  significa uma avaliação completa no PSO e na Busca Tabu, uma avaliação parcial no
  guloso, e uma avaliação completa **mais** a construção inteira da formiga no ACO,
  que custa de 447 a 1.172 cálculos de componentes gratuitos. Efeito medido na
  própria seção 29.1: fator entre 70 e 160 de tempo de parede sob orçamento
  nominalmente igual.
- **F9-1** (`L1`): os hiperparâmetros congelados não são distinguíveis de vizinhos no
  tamanho de amostra do próprio tuning, com `p` exato de 0,594, 0,775 e 0,438 nos três
  algoritmos.
- **Achado colateral da F3**, reproduzido de forma independente: o guloso
  determinístico faz **0,268290 com 275 avaliações**, melhor que a média do PSO com
  **60.000** avaliações e 218 vezes mais barato.

Os três juntos dizem algo que nenhum diz sozinho: a comparação principal entre as
três metaheurísticas é feita sob uma unidade de esforço que favorece o ACO por
construção, com parâmetros que são `argmin` dentro do ruído, e o baseline mais
simples do estudo bate um dos três métodos por uma margem que o próprio orçamento não
explica. **Nenhum dos três é defeito de código e nenhum pede correção.** Os três são
obrigações de redação do relatório final, e precisam aparecer juntos, porque
apresentar um sem os outros dois dá ao leitor uma falsa impressão de solidez.

### Conexão 12. O remédio prescrito para F9-3 é a operação que F6-02 mostra ser insegura

`F9-3` (`D3`) estabelece que reexecutar a análise oficial do tuning, com resultado
idêntico em conteúdo, muda o hash de `experiments/configs/frozen_parameters.toml`, que
é arquivo protegido, e portanto **bloqueia a campanha**. A recuperação, como o próprio
achado registra, "exigiria regenerar o manifesto de congelamento, que é a operação
mais delicada do bloco". `F6-02` (`D3`) estabelece exatamente **por que** ela é
delicada: `generate_freeze_manifest` aceita worktree suja com `allow_dirty=True`
hardcoded, confia no veredito gravado do piloto em vez de revalidar comportamento, e
escreve `pilot_commit` sem nunca compará-lo com o `HEAD`.

Ou seja, o caminho de recuperação de um achado é o vetor de risco de outro. **A
correção de F6-02 precisa vir antes de qualquer regeneração de manifesto motivada por
F9-3**, e essa ordenação está registrada na seção 7. Consequência adicional para a
Tarefa 19B, passo 3: contar com mudança de hash do `frozen_parameters.toml` mesmo sem
mudança de parâmetro.

### Conexão 13. Quatro assimetrias independentes de medição entre CPU e GPU, com sinais que não se alinham

| Achado | Assimetria | Direção sobre `S` | Magnitude |
|---|---|---|---|
| F7-3 | GPU não fixa variável de thread alguma; 66 threads contra 4 | nula, medida | 2,4% e 1,7%, dentro do ruído, **a favor** do caso sem limite |
| F8-11 | monitor térmico roda dentro do processo cronometrado, com dois `nvidia-smi` por segundo | **reduz** `S` | não medida |
| F8-14 | preparação do dispositivo fica **fora** do tempo oficial | **aumenta** `S` | 2,0 ms, cerca de 0,05% no PSO e 0,001% no ACO |
| F8-13 | `T_CPU` sob contenção de 16 vias, `T_GPU` exclusivo | ambígua | dois pares com **sinais opostos**, 1,243% e 0,4695% |

**Os sinais não se alinham e três das quatro magnitudes não estão medidas.** A
conclusão conjunta é que o `S` do ACO não tem barra de erro defensável, o que reforça
por um quinto caminho independente a proibição registrada em F8-2 de apresentá-lo
como aceleração por GPU. Para o PSO o quadro é diferente: o dispositivo responde por
16,3% do tempo, o teto de Amdahl é 3,13, e o `S` de 2,866 passa no teste. **Cabe
publicar o `S` do PSO e não o do ACO**, ou publicar os dois com a fração de
dispositivo ao lado, que é o item derivado de F8-2 no Apêndice B.

## 6. Achados sobre a própria auditoria

Esta seção não é sobre o projeto. Ela registra três falhas do processo de auditoria
que foram expostas pela verificação adversarial, porque duas delas **fabricaram
achados que não existiam** e a terceira teria invalidado uma frente inteira se não
tivesse sido pega.

### 6.1. Causa raiz dos dois achados inflados: um bloco de premissas com rótulo errado

**O erro.** Foi anexado aos nove dossiês de frente um bloco intitulado "Restrições
globais do projeto" que continha, **misturadas**, restrições reais do projeto e
regras metodológicas da própria auditoria, entre elas a comparação de `float64`
sempre exata por `float.hex()` e a semente reservada. O rótulo do bloco estava
errado: parte do conteúdo é metodologia da auditoria, não regra do projeto.

**Os dois achados fabricados por essa causa.**

- **F8-1**, proposto como `D1`. A especificação da auditoria escreveu, na linha 269,
  "Igualdade **exata** de orçamento, de ordem de consumo e de checkpoints",
  acrescentando **tanto a palavra "exata" quanto o item "ordem de consumo"**, nenhum
  dos dois presente na fonte. O documento normativo,
  `docs/experiments.md` linhas 1159-1162, diz literalmente: "A conformidade exige
  tolerâncias absoluta e relativa de `1e-12`, igualdade de orçamento e checkpoints,
  arbitragem CPU de quase empates e confirmação CPU da solução final". **A palavra
  "exata" não aparece, e a régua de `1e-12` é fixada antes da enumeração.** Esse
  endurecimento foi propagado ao dossiê da frente F8 e fabricou um defeito que altera
  resultados onde havia **conformidade por margem de fator 1.802**.
- **A9**, proposto como `D3`. A refutação se apoia em que a comparação bit a bit por
  `float.hex()` tem escopo de **metodologia da própria auditoria**, e não de proibição
  de tolerância no desenho de algoritmos, que o projeto usa deliberadamente em três
  outros lugares, conforme a conexão 10.

**Lição, registrada porque é o modo de falha mais perigoso de uma auditoria.** Um
dossiê que endurece a premissa produz achado que não existe, e esse achado vem com
**evidência numérica correta sobre uma exigência inventada**. Foi exatamente o que
aconteceu nos dois casos: as medições de F8-1 e de A9 são corretas e reproduzíveis; o
que não existia era a exigência contra a qual foram julgadas.

**Regra em vigor a partir deste registro**, aplicada a todos os 89 achados deste
documento: toda citação de premissa identifica a fonte e declara se ela é normativa,
`docs/formulation.md` e `docs/experiments.md`, ou metodologia da auditoria, qualquer
coisa em `superpowers/` e nos dossiês. Achado que se apoie **apenas** em regra
metodológica da auditoria não pode ser classificado como defeito do projeto.

**Casos limítrofes que a regra resolveu sem derrubar o achado, e que valem como
contraprova de que a regra não é excessiva.** F2-03, F2-14, A5, F6-08, F7-2, F7-3,
F8-8 e F8-11 também citam fonte metodológica, e **os oito sobrevivem**, porque cada
um tem âncora normativa independente e suficiente. Em F8-11 o verificador localizou a
âncora que o auditor não citou: `docs/experiments.md` seção 24 linha 839 e seção 25
linha 866. F7-4 é o caso especial em que a fonte metodológica é o **objeto correto**
do achado, porque o achado **é** a afirmação falsa do próprio artefato da auditoria.

### 6.2. O comando de teste de mutação documentado não carrega o mutante

**O defeito.** O padrão `PYTHONPATH=<diretório> uv run pytest tests/ -q`, executado
com o diretório de trabalho dentro do repositório original, **não carrega o
mutante**. A causa é `pyproject.toml` linha 25, que define
`pythonpath = [".", "src"]`, e essa configuração é processada por plugin interno do
pytest em `pytest_configure`, que insere caminhos resolvidos **relativos ao `rootdir`
descoberto pelo pytest** no início de `sys.path`, sobrepondo a variável de ambiente.

**Onde está documentado.** Literalmente em `frente-6-report.md:292`, que é o relatório
da frente da Busca Tabu, e **não** no relatório da frente de testes, cuja seção de
método diz apenas "pytest sobre a cópia". A atribuição foi corrigida pelo verificador
da F2, que resolveu a ambiguidade em vez de aceitá-la.

**Consequência se não tivesse sido pego.** Sob o comando documentado, qualquer mutante
devolve suíte verde, inclusive um que apague a memória tabu inteira. **Poder
discriminante zero.** Um terceiro que tentasse reproduzir a sondagem obteria "254 de
254" para qualquer mutação, inclusive as 26 que a F2 já demonstrou serem mortas, e
concluiria por um falso "suíte sem poder de detecção" generalizado.

**Por que as duas frentes sobrevivem.** A frente F5 sobrevive porque o verificador
**reexecutou os quatro mutantes com método corrigido**, carregando o pacote mutado por
`sys.path.insert` explícito, e obteve todos os valores batendo dígito a dígito,
inclusive `float.hex()`. A frente F2 sobrevive porque o método dela era **outro**:
cada mutação recebeu cópia completa e autocontida do repositório, com o próprio
`pyproject.toml`, e a suíte foi sempre executada **de dentro** da cópia, de modo que o
`rootdir` é a própria cópia mutada e não há sombreamento. O verificador da F2 validou
isso por marcador, com um `raise` incondicional produzindo 31 erros de coleta, e
inspecionou por `python -c` o símbolo mutado em cada uma das 16 cópias.

**Raciocínio de corroboração independente, feito pelo coordenador e confirmado pelo
verificador:** se o mutante nunca carregasse, todas as 42 mutações da F2 teriam
passado e seriam reportadas como sobreviventes; mas a F2 reportou **26 mortas**. Os 26
mortos são, eles mesmos, evidência de que o método da F2 carregava o mutante.

**Regra em vigor.** A validação por marcador passa a ser exigência de qualquer
sondagem por mutação nesta auditoria, e a onda de correção que criar testes contra
mutantes deve incluir a própria validação de método. A recomendação operacional é
declarar explicitamente o diretório de trabalho, ou usar
`pytest -o "pythonpath=<cópia> ." <cópia>/tests`, que sobrepõe a opção do
`pyproject.toml` na linha de comando e não depende de `cwd`.

### 6.3. Erros do coordenador expostos pela verificação, e correções propagadas

Registrados porque são informação sobre a qualidade do diagnóstico, que a taxonomia
exige preservar.

1. **"Onze dos doze hiperparâmetros"** era **dez dos onze**. Corrigido na
   especificação e no plano. Verificado por três vias independentes, incluindo as 23
   linhas da tabela de efeitos, que seriam 27 com doze parâmetros.
2. **A hipótese de que a Busca Tabu se beneficia de trajetória mais longa** foi
   refutada. O mecanismo se confirmou exatamente; a conclusão caiu.
3. **A atribuição causal positiva "a vizinhança maior compra escolha local melhor por
   avaliação"** foi apresentada ao usuário como resultado e **não pode ser
   sustentada**: a própria lógica do confundimento estrutural a proíbe. Só a negativa
   está provada. **Isto precisa ser corrigido com o usuário.**
4. **A leitura de "deadlock" em F8-6** foi repassada ao usuário e está errada: a falha
   é espúria e recuperável esperando, não bloqueio permanente, com temperatura ociosa
   real medida em 38 graus.
5. **O enquadramento de "F1-05 supersedido por F4-1"** era grosseiro: apenas a
   prescrição é superada, e a medição se sustenta com corroboração independente.
6. **A comparação de 3,58x com 4,9x** foi recusada pelo verificador, porque são
   escopos diferentes.
7. **A suspeita sobre threads** foi refutada por medição, e a refutação é boa notícia.
8. **Lacuna de cobertura detectada e sanada durante a Tarefa 11:** o verificador da
   frente F8 completa caiu com erro de servidor e não foi redisparado de imediato,
   deixando os doze achados F8-3 a F8-14 sem veredito adversarial, o que violava o
   invariante 1 da especificação. Foi redespachado e concluído antes desta tarefa.
9. **Ruling de cascata por escopo**, que substitui a regra global da especificação: um
   diff confinado a cenários `greedy:*` não invalida tuning nem piloto, porque o
   guloso nunca foi ajustado no tuning e não aparece nos 18 cenários do piloto. Sob a
   regra antiga, corrigir F1-01 custaria 3 h 43 min de retuning desnecessário.

## 7. Estimativa de custo por onda

As estimativas de tempo abaixo são de **trabalho de correção e verificação**, não de
computação, salvo onde explicitamente dito. Elas são grosseiras por construção,
porque o conteúdo concreto de cada subtarefa só existe depois do portão de decisão do
usuário. Os custos de **computação** são os medidos, e esses são firmes.

| Onda | Achados | Arquivos afetados | Toca escopo protegido | Tempo estimado de trabalho |
|---|---:|---|---|---|
| A | **4** | `src/metaheuristica/pso.py`, `tests/test_pso.py` | **Sim**, `pso.py` está entre os 52 | 1 a 2 h |
| B | **56** | `src/metaheuristica/{objective,evaluator,metrics,optimizer,greedy,aco,pso,tabu}.py`, `experiments/{benchmark_validation,benchmark_freeze,benchmark_operations,execution,storage,provenance,consolidation,resource_monitor,pilot_validation,tuning_analysis,analyze_tuning,scenarios}.py`, `gpu/src/metaheuristica_gpu/{monitor,aco,pso,evaluator,run}.py`, `tests/`, `.gitignore`, `README.md` | **Sim**, `src/metaheuristica/` e `experiments/` inteiros | 20 a 30 h |
| C | **14** | `src/metaheuristica/{objective,tabu}.py`, `experiments/resource_monitor.py`, `gpu/src/metaheuristica_gpu/{numerics,timing,objective,config,run}.py`, `tests/` | **Sim**, parcialmente | 7 a 11 h |
| Registro apenas | **15** | nenhum arquivo de código; `docs/experiments.md`, `docs/formulation.md` e `README.md` na tarefa de fechamento | Não | 3 a 5 h de redação |
| **Total** | **89** | | | |

Dos 15 de registro apenas, **2 são de classe `R`** e vivem no Apêndice A.

### 7.1. Onda A, e a resposta explícita sobre invalidação do tuning

**Sim, existe candidato a invalidar o tuning com diff já medido, e é exatamente um:
A1. Mas ele não é o único gatilho possível da cascata**, e a qualificação da seção 1
vale aqui integralmente: A5, F4-4 e F5-3 são `D2` com previsão de diff **não zero** em
campo de diagnóstico, e reclassificam automaticamente para `D1` se o oráculo da Tarefa
14 comparar diagnósticos. Se isso ocorrer, a Onda B carrega três gatilhos próprios e
**a sobrevivência do tuning deixa de depender apenas da decisão sobre A1**.

A1 é o único `D1` da auditoria hoje. A verificação dedicada mediu que corrigir a ordem
de saturação **altera o `float.hex()` em 10 de 10 seeds** e leva a média de 0,274437
para 0,280569. Isso é condição suficiente para invalidar o congelamento do tuning do
PSO. Os outros três achados da Onda A, A10, F2-10 e F2-09, são cobertura de teste e
acompanham A1 no mesmo commit porque são exatamente os testes que teriam detectado
A1: `_trial_state` não tem teste algum, o único teste de limite de velocidade cobre
apenas a velocidade inicial, condição que A1 não viola, e o instantâneo único do
melhor global também não é testado na região que a correção reescreve.

**Consequência canônica, conforme o briefing:** ramo alterado, com **3 h 43 min de
relógio de retuning** com 16 workers, mais as **18 execuções do piloto**, mais
revalidação do piloto, regeração do roteiro e novo manifesto, nessa ordem.

**Ramo 3 confirmado por medição, e não mais por previsão.** O pacote A1 da Onda A
corrigiu a ordem de saturação no código e a impressão digital foi comparada contra a
linha de base `a2d820eb...` antes de qualquer regravação. Divergiram exatamente os
**11 cenários `pso:*`** e **nenhum** cenário `tabu:*`, `aco:*` ou `greedy:*`, o que
confirma o escopo previsto e descarta vazamento da correção para fora do PSO. A linha
de base foi regravada em seguida, com `content_sha256` igual a `8b4fbfb3...`. O tuning
e o piloto oficiais estão, portanto, invalidados por medição, e precisam ser refeitos
na tarefa de fechamento, depois das três ondas. O detalhe numérico está no achado A1.

**Consequência revisada, e ela é separada de propósito.** Se o ganho de 3,58x do ACO
de F4-1 entrar **antes** do retuning, o próprio retuning fica muito mais barato,
porque o tuning roda 160 execuções de ACO em `N=60` com média de 1.312 s. Sob essa
ordenação, o retuning passa de cerca de 3 h 43 min para cerca de **1 h 06 min**, e o
piloto, cujo relógio é dominado pelo ACO em `(150,8)` a 10.971 s, passa de cerca de
3 h para cerca de **45 min**. Ou seja, o ramo alterado deixaria de custar cerca de 7 h
e passaria a custar cerca de 2 h. **Esta é uma projeção derivada dos números de F4-1,
não uma medição do retuning**, e o risco de erro está nas estimativas de F4-1 estarem
superestimadas; a direção não muda. A ordenação do plano já faz isso corretamente, com
o refazimento de tuning e piloto depois das três ondas.

**Ruling de cascata por escopo, em vigor.** A regra global da especificação, de que
qualquer diferença na impressão digital invalida o tuning, é grosseira demais. Um diff
confinado a cenários `greedy:*` **não invalida** tuning nem piloto, porque o guloso
nunca foi ajustado no tuning e não aparece nos 18 cenários do piloto; exige apenas
renovação de manifesto e regeração de artefato que embuta custo do guloso. Diff que
toque qualquer cenário `tabu|aco|pso` continua disparando o ramo alterado. F1-01, se
corrigido, cai exatamente nesse caso, e sob a regra antiga custaria 3 h 43 min de
retuning desnecessário. **Os dois achados originalmente `D1` da GPU nunca disparavam a
cascata da campanha CPU**, porque vivem em `gpu/`, que não entra em
`protected_paths`, e a campanha B11A-E nunca rodou.

**A Onda A pode terminar vazia, e a contingência precisa estar completa.** Se a
decisão do usuário for emendar o **documento** em vez do código para A1, o que a
ressalva do verificador sobre a ambiguidade textual da seção 16 mantém como opção
legítima, a Onda A fica sem correção de código. Nesse caso A10, F2-10 e F2-09 perdem o
defeito-pai e, pela taxonomia, passam a `M2` isolados com destino à **Onda C**, onde
continuam valendo por si: a lacuna de cobertura de `_trial_state` existe
independentemente de qual lado da divergência de A1 for emendado, e é ela que impediria
a suíte de detectar uma regressão futura na mesma região.

**A sobrevivência do tuning nesse ramo, porém, não é automática.** Ela exige, além da
emenda documental de A1, que a impressão digital feche com diff zero também nos três
`D2` de previsão não zero, A5, F4-4 e F5-3, o que depende da decisão da Tarefa 14 sobre
o escopo de campos do oráculo. Onda A vazia é resultado válido e desejável, e não sinal
de que a triagem falhou; mas "Onda A vazia" não implica, por si, "tuning sobrevive".

### 7.2. Onda B, com a ordenação obrigatória

Os 56 achados da Onda B não são independentes. As conexões da seção 5 impõem cinco
grupos com precedência, e o resto pode ser feito em qualquer ordem.

1. **Primeiro, o portão do congelamento: F2-04, F6-02, F6-03.** É o commit que
   protege todos os outros, conforme a conexão 6. Sem ele, nenhuma das correções
   seguintes tem garantia de estar sob congelamento válido.
2. **Segundo, o desbloqueio do fluxo de campanha: F6-01, F6-04, F6-05, F6-06, F6-07,
   F2-05, F7-1.** Sem esses, a campanha não passa do lote 1 pelo caminho documentado.
   A decisão entre caminho por subgrupo e caminho saturado entra aqui, junto de F6-06
   e não separada, conforme a conexão 3.
3. **Terceiro, o desempenho do ACO: F4-1, com F1-06 e F4-5 no mesmo commit, e com o
   espelhamento obrigatório em `gpu/src/metaheuristica_gpu/aco.py:42-84`.** Precisa
   vir antes de qualquer retuning, porque barateia o próprio retuning, e o
   espelhamento não é opcional, conforme a conexão 8. Ganho medido: campanha ACO de
   439,7 h-CPU para 122,8 h-CPU, mais 5,2 a 5,8 h-CPU de F1-06.
4. **Quarto, a fronteira de orçamento como problema único de contrato: F1-04, A5 e
   F5-3 no mesmo commit, corrigidos em `optimizer.py`** e não nos três algoritmos,
   conforme a conexão 9. **Este é o grupo que carrega dois dos três `D2` de previsão de
   diff não zero**, logo é o commit cujo resultado na impressão digital pode
   reclassificar achados para `D1`; ele deve ser o último dos cinco grupos a rodar contra
   o oráculo, para que os quatro anteriores já estejam estáveis quando a cascata for
   avaliada.
5. **Quinto, o identificador por conteúdo: F6-08 com F2-15**, depois do grupo 1,
   conforme a conexão 7.

**Restrição de ordenação que não é conexão e precisa constar.** F6-08 altera a
composição do `scenario_id`. Se o oráculo da impressão digital dos 42 cenários for
gerado **antes** dessa correção, os identificadores mudam e o oráculo perde
comparabilidade. **O oráculo deve ser gerado depois de F6-08, ou F6-08 deve ser
diferida para depois do fechamento da impressão digital.** Esta é decisão da Tarefa 14
e está registrada aqui para que não passe.

**Custo de computação da Onda B.** Zero de campanha, porque nenhuma correção da Onda B
exige reexecutar cenário oficial. O custo de computação aparece só se a Onda A
disparar o ramo alterado, e nesse caso está contabilizado em 7.1.

### 7.3. Onda C

Catorze achados, nenhum com efeito em resultado, todos de legibilidade, cobertura
isolada ou robustez de manutenção. Nenhum toca a impressão digital com diff esperado
não zero. Se a Onda A terminar vazia, A10, F2-10 e F2-09 migram para cá como `M2`
isolados, conforme 7.1, e a Onda C passa a dezessete. Os cinco de `gpu/` (F8-1, F8-4, F8-5, F8-9, F8-12) podem ser feitos em
paralelo com os demais, porque `gpu/` não é protegido pelo congelamento da B11-E.

**Único item da Onda C com nota de precedência:** F5-4, canonicalização e validação
repetidas por candidato na Busca Tabu, tem recomendação explícita e mantida de **não
ser corrigido antes do benchmark**, porque alteraria a impressão digital sem ganho
relevante, da ordem de dezenas de minutos numa campanha dominada pelo ACO. Ele só
deve entrar se a Onda A já tiver disparado o ramo alterado por outra razão.

### 7.4. Registro apenas

Quinze achados, dos quais dois de classe `R`. Não geram correção de código. Geram
obrigações de redação, concentradas na tarefa de fechamento:

- **`docs/formulation.md` seção 16** precisa correção em dois pontos: omite a
  canonicalização da posição viva, que é A7 e responde pela diversificação inteira do
  método, e descreve um limite de velocidade que o código não aplica ao deslocamento,
  que é A1.
- **`docs/experiments.md` seção 12.2** precisa de uma frase dizendo que o vencedor de
  cada algoritmo é a melhor **combinação** e não a composição dos melhores níveis, que
  é F9-6, e da ressalva de que os parâmetros congelados são `argmin` dentro do ruído,
  que é F9-1.
- **`docs/experiments.md` seção 28.1** precisa corrigir a descrição do que o
  `scenario_id` cobre, que é F6-08.
- **`README.md:286-287`** precisa ter a duração prevista atualizada depois da Onda B e
  da impressão digital, que é F9-5, e precisa documentar o caminho saturado se ele for
  adotado, que é F7-1.
- **A restrição global da auditoria** precisa ter `ARROW_NUM_THREADS` corrigida, que é
  F7-4, e precisa separar o que é regra do projeto do que é metodologia, que é a
  seção 6.1.
- **O relatório final** precisa carregar, juntas, as três obrigações da conexão 11, a
  proibição de apresentar o `S` do ACO como aceleração por GPU de F8-2, a nota sobre
  as três condições experimentais misturadas na forma de U da conclusão da F3, e a
  publicação apenas da negativa em F5-1.

## Apêndice A. Achados refutados

Dois achados foram refutados integralmente pela verificação adversarial e recebem
classe `R`. Eles ficam registrados, com a razão da rejeição, porque **distinguir "não
havia problema ali" de "não olhamos ali" é metade do valor de uma auditoria**. Ambos
caíram por premissa que não existia na fonte normativa.

### A2. A velocidade guardada não é o deslocamento aplicado

- **Frente:** F3, PSO.
- **Classe:** `R`, refutado pela verificação adversarial. Classe proposta pelo
  auditor: `D1`, defeito que altera resultados.
- **Premissa:** o achado citava `docs/formulation.md` seção 16, "A velocidade segue a
  fórmula clássica com inércia". **Fonte: normativa**, mas **a exigência atribuída à
  seção não existe nela**, e é isso que derruba o achado, conforme o veredito abaixo.
- **Previsto:** segundo o achado, que o termo de inércia da iteração seguinte
  reutilizasse o movimento efetivamente executado pela partícula.
- **Código:** `src/metaheuristica/pso.py:367-368`, em `_commit_candidate`,
  alimentadas por `:184-189`, `:302` e `:307`.
  `particle.velocity = velocity.copy()` guarda `trial.velocity`, calculada antes de
  três transformações que alteram a posição final, a saturação de posição em `[0,1]`
  da linha 185, a projeção de reparo da linha 302 e a projeção de canonicalização da
  linha 307, de modo que `particle.position - posição_anterior` difere da velocidade
  guardada.
- **Evidência (números do verificador):** o fenômeno **existe, é grande e foi
  medido**, e nada nele é refutado. Resíduo não nulo em **25,46%** das 34.380.000
  coordenadas, resíduo máximo **1,094**, com **7,6%** atribuível à saturação de
  velocidade, **19,7%** à saturação de posição e **72,7%** à projeção de reparo ou
  canonicalização, e **zero** resíduos sem causa identificada. A variante do
  relatório foi reproduzida exatamente, com média **0,266910** e melhora em **6 das
  10** seeds.
- **Veredito adversarial: REFUTADO como defeito, e como `D1` e como `D2`,** por
  quatro argumentos independentes. **Primeiro, e decisivo: a
  seção 16 não diz o que o achado afirma que ela diz.** O texto é "A velocidade segue
  a fórmula clássica com inércia e componentes cognitivo e social, vetores aleatórios
  independentes e topologia global. As posições são limitadas a `[0,1]`, as
  velocidades a `[-0.5,0.5]`". **Não há uma palavra sobre a velocidade guardada
  precisar igualar o deslocamento realizado**, e a frase citada no achado, "o termo de
  inércia da iteração seguinte reutiliza o movimento efetivamente executado pela
  partícula", **não está no documento**: é inferência do autor do achado apresentada
  como previsão do documento. **Segundo, a inferência contradiz a própria fórmula
  clássica que ela invoca:** no PSO com saturação de velocidade e fronteira
  absorvente, a implementação padrão guarda a velocidade da fórmula, saturada, e
  satura a posição sem redefinir a velocidade; redefinir a velocidade a partir do
  movimento realizado é **variante** de tratamento de fronteira, não o clássico. O
  código guarda exatamente `clip(v_fórmula, -0.5, 0.5)`, que é o objeto que a seção 16
  nomeia e limita. **Terceiro, a causa dominante é consequência necessária de outra
  prescrição do próprio documento:** 72,7% dos resíduos vêm da projeção de volta ao
  espaço contínuo, que a seção 16 **manda** fazer, e da canonicalização, que a seção
  11 **manda** fazer, e nenhuma das duas diz nada sobre velocidade; exigir que a
  velocidade guardada acompanhe esse salto seria inventar uma regra que o documento
  não escreveu. **Quarto, a evidência de apoio é de qualidade e é ruído:** a variante
  do relatório foi reproduzida exatamente, com média 0,266910 e melhora em 6 das 10
  seeds, e o teste emparelhado dá `delta = -0,007527`, `sd = 0,055814`, `t = -0,43` em
  9 graus de liberdade, não significativo; e a "correção" **não é sequer bem
  definida**, porque outras duas leituras da mesma correção dão 0,256209 com `t=-1,46`
  e 0,269051 com `t=-0,47`, todas com `|t| < 1,5`.
- **Divergência auditor / verificador:** o fenômeno medido pelo auditor **não é
  refutado em nada**: a refutação é **normativa e de premissa**. O que cai é a
  atribuição da exigência à seção 16 e a classe. Registro também que **A2 é
  independente de A1, e a independência não o salva**: provado analiticamente no
  próprio cenário do achado e medido, sob a correção de A1 a fatia de 7,6% atribuível
  à saturação de velocidade **cai a zero**, mas **92,4% da massa do resíduo
  sobrevive**, com o máximo até um pouco maior, 1,200 contra 1,094. Portanto A2 não é
  derivado de A1. **Sobra um único `D1` no PSO porque A2 não é defeito, não porque
  seja consequência de A1.**
- **Decisão:** nenhuma correção de código e nenhuma invalidação do tuning. O resíduo
  máximo defensável seria uma nota documental registrando que a seção 16 não declara a
  política de velocidade na fronteira nem depois da projeção; **não é classificado
  como `L1` neste registro**, porque o veredito é de refutação e a taxonomia reserva
  `R` para isso.
- **Onda:** registro apenas, no Apêndice A.
- **Situação:** refutado.
- **Impressão digital:** pendente, sem alteração esperada por não haver correção.

### F8-3. O portão de conformidade não pode reprovar o caminho oficial

- **Frente:** F8, GPU.
- **Classe:** `R`, refutado pela verificação adversarial. Classe proposta pelo
  auditor: `D3`, defeito latente de risco operacional.
- **Premissa:** `docs/experiments.md` seção 29.1 da B11A, "A conformidade exige
  tolerâncias absoluta e relativa de `1e-12`, igualdade de orçamento e checkpoints".
  **Fonte: normativa.** `run.py:142-143` faz do artefato de conformidade um
  pré-requisito do congelamento e `_protected_hashes` o inclui entre os arquivos
  protegidos: é o portão formal da campanha.
- **Previsto:** um portão capaz de reprovar o caminho que será executado oficialmente.
- **Código:** `gpu/src/metaheuristica_gpu/evaluator.py:87-97`;
  `gpu/src/metaheuristica_gpu/run.py:118-138`, em especial `:129-132` e `:134`;
  `results/gpu/metadata/gpu_conformance.json`. O achado alegava que
  `run_conformance` só exercita `verify_every_batch=True`, modo em que os resultados
  da GPU são descartados, sobre uma fixture `tiny_manual` com `K=2` cujo custo é
  exatamente zero em 98 de 100 checkpoints, e que portanto o portão "não pode
  reprovar o caminho oficial".
- **Evidência (números do verificador):** o artefato real
  `results/gpu/metadata/gpu_conformance.json`, já presente no repositório, registra
  diferenças de **`3,3306690738754696e-16`** para a instância de 20 unidades,
  **`1,1102230246251565e-16`** para a de 60 e **`2,220446049250313e-16`** para a de
  150, medidas pelo mecanismo que o achado não citou. São da mesma ordem de grandeza,
  1 a 3 ulp, que as encontradas em F8-1 sobre execuções reais, e **não zero**, porque
  as soluções sintéticas usadas sobre as instâncias ARTESP não têm custo trivial.
- **Veredito adversarial: REFUTADO integralmente.** **O achado omitiu um segundo
  mecanismo que existe no mesmo
  arquivo.** `run_conformance` não tem um modo, tem **dois**, e o achado só cita o
  segundo. As linhas **120-128**, não citadas pelo achado, percorrem as três
  instâncias de 20, 60 e 150 unidades e chamam `GpuBatchObjective.evaluate`
  **diretamente**, que é a mesma função que o caminho oficial usa, **sem descartar
  nada**, e em seguida `verify_batch`, cujo `require_equivalent` levanta
  `NumericalDivergenceError` **não capturado em lugar nenhum** se qualquer campo
  divergir além de `1e-12`. Se isso acontecer, `run_conformance` propaga a exceção, o
  artefato de conformidade **não é criado**, e `generate_manifest` recusa congelar a
  campanha porque `CONFORMANCE.is_file()` é falso. **Isso é exatamente um portão capaz
  de reprovar o caminho oficial, sobre dados não triviais.**
  A evidência acima falsifica diretamente a frase decisiva do achado, "o único modo
  que verifica é `verify_every_batch=True`".
- **Divergência auditor / verificador:** a frase decisiva do achado é falsa, e com ela
  cai a conclusão. **O que sobrevive já mora em outro achado:** a trajetória completa
  do ACO e do PSO, com evolução de `tau` e de `pbest`/`gbest` ao longo de muitas
  iterações, só é testada de ponta a ponta em modo que descarta a GPU, sobre fixture
  de custo trivial. Isso é verdade, mas é exatamente o achado **F8-4**, já
  classificado `M2` e confirmado. **Não há conteúdo independente de F8-3 que
  sobreviva** depois de F8-4 ser contabilizado, e o próprio achado já admitia, na
  seção de cenário concreto, que "na prática a reprovação ocorre por exceção", o que
  concede que o portão tem dentes.
- **Decisão:** nenhuma correção própria. O conteúdo válido é executado por F8-4, na
  Onda C.
- **Onda:** registro apenas, no Apêndice A.
- **Situação:** refutado.
- **Impressão digital:** pendente, sem alteração esperada por não haver correção.

## Apêndice B. Itens pendentes de verificação adversarial

O Passo 2 do briefing exige que achado novo desta passagem transversal passe pela mesma
verificação adversarial da Tarefa 11. Nada nesta lista passou por ela. Estes itens
**não** entram na contagem dos 89 e **não** podem ser tratados como achados
verificados. São anotações, cada uma ancorada no achado que a originou.

| # | Item | Origem | Classe proposta | Achado-pai |
|---|---|---|---|---|
| B1 | A identidade bit a bit de O2 e O4 **depende de ordem C**: em ordem Fortran a redução diverge em 22 de 50 linhas (44%) com `K=8` e 17 de 50 (34%) com `K=12`. Recomendação: incluir `assert matrix.flags['C_CONTIGUOUS']` na implementação real. **Satisfeito pelo pacote B5**, no commit `d297377`: a asserção está na implementação real, em `src/metaheuristica/objective.py:78`, e uma segunda em `:85` cobre a matriz de desvios, sobre a qual corre a segunda redução. `tests/test_aco.py::test_balance_matrix_refuses_memory_that_is_not_c_contiguous` dispara a asserção com uma matriz em ordem Fortran e, no mesmo teste, mede que a redução em ordem Fortran de fato diverge, o que impede que o teste vire ritual. Ressalva registrada pela revisão independente do pacote: as duas são `assert` e somem sob `python -O`, o que hoje é risco latente e não atual, porque não há ocorrência de `-O`, `-OO` ou `PYTHONOPTIMIZE` em `experiments/`, `gpu/`, `configs/` ou `pyproject.toml`; a troca por recusa explícita cabe ao pacote da Onda C que voltar a tocar o arquivo. | verificador da F4 | robustez, sem classe atribuída | F4-1 |
| B2 | A identidade bit a bit precisa ser **reestabelecida contra a implementação real** quando a onda materializar O2 e O4 em código versionado, porque as 176.557 linhas e 176 execuções do protótipo original não são re-verificáveis: o protótipo foi escrito fora da árvore e não existe mais. **Satisfeito pelo pacote B5**, no commit `d297377`: `_PartialConstructionState.evaluate_choice` foi preservado intacto como referência normativa (`src/metaheuristica/aco.py:170-199`) e `tests/test_aco.py::test_batched_choice_costs_reproduce_the_reference_bit_by_bit` compara `choice_costs` contra ele por `float.hex()`, em 27 combinações parametrizadas de instância e `K`, percorrendo construções reais e comparando em toda posição não forçada. A identidade passou a ser medida contra a implementação real, e não herdada do protótipo descartado. Lacuna residual, medida pela revisão independente: o ramo de denominador nulo de `_cut_fractions` nunca é percorrido pelas instâncias congeladas, logo a identidade nele é afirmada por leitura; fechada por teste dirigido em `tests/test_objective.py`. | verificador da F4 | limitação de escopo | F4-1 |
| B3 | `consolidate` descarta `diagnostics.gpu_timing` ao montar `gpu_runs.parquet`, publicando `speedup` sem a fração de dispositivo que o interpreta. Recomendação: publicar campo derivado `device_fraction`. | verificador dedicado dos `D1` da GPU | `M3` | F8-2 |
| B4 | A metodologia de mutação de `frente-3-report.md` não declara o diretório de trabalho com precisão suficiente para excluir, por si só, o padrão defeituoso de `PYTHONPATH`. Lacuna de reprodutibilidade do relatório, não dos resultados. | verificador da F2 | `L1` | seção 6.2 |
| B5 | O padrão de comando de mutação documentado em `frente-6-report.md:292` não carrega o mutante. **Os dois verificadores divergem na classe**: o da F5 propõe `D3` de metodologia da auditoria, o da F2 propõe `L1`. A divergência não foi arbitrada. | verificadores da F5 e da F2 | `D3` ou `L1`, em disputa | seção 6.2 |
| B6 | **A última iteração de qualquer execução do PSO nunca é contada**, mesmo em orçamento que divide exato por `n_particles`, porque `_stop_at_limit` verifica `remaining == 0` **depois** de uma avaliação bem sucedida e o caminho de exceção nunca alcança o incremento de `iterations_completed`. Medido: orçamento 100 com `n_particles=4` dá 23 iterações e não 24. | verificador da F3 | reforça `D2` | A5 |
| B7 | Reescrever silenciosamente o resumo de recursos de uma sessão já registrada, que é o mecanismo que possibilita a recuperação de F6-09, **destrói a integridade do diário operacional**, porque sessões historicamente distintas passam a apontar para o mesmo arquivo mutável e se perde o registro fiel de que uma sessão reprovou em recursos. **Absorvido no pacote B4**, como item associado de F6-09: a seção 29 passou a dizer que a recuperação é por nova sessão registrada da mesma rodada, e nunca por sobrescrita do resumo de uma sessão já registrada. | verificador da F6 | não atribuída, ortogonal a F6-09 | F6-09 |
| B8 | A conformidade da GPU em **150.000 avaliações** permanece **não verificada por medição direta**. As medições usaram orçamentos de 2.000, 4.000 e 20.000, porque uma execução pareada de ACO em `artesp_rmsp_150` com orçamento cheio custaria cerca de 2,3 h de CPU. A extrapolação se apoia em que o desvio é arredondamento por avaliação e não acumulação, com o máximo travado em 1 a 2 ulp com orçamento cinco vezes maior. | verificador dedicado dos `D1` da GPU | limitação de escopo | F8-1 |
| B9 | **Aritmética da conexão 8, derivada nesta tarefa e não verificada por ninguém:** aplicar F4-1 ao caminho CPU levaria `T_CPU` de 221,12 s a cerca de 61,8 s e o speedup do ACO de 1,3518 a cerca de **0,38**, isto é a variante GPU ficaria cerca de 2,6 vezes mais lenta que a CPU otimizada, a menos que o espelhamento em `gpu/aco.py` seja feito. A conclusão qualitativa está apoiada em números verificados; **a divisão é minha e precisa de verificação independente antes de ser citada como resultado**. **Corroborada pela revisão independente do pacote B5**, na direção e na magnitude: a revisão mediu 3,70x de ganho na CPU e 3,18x na GPU, com a razão entre as construções passando de 0,805 para 0,937, que é o que a aritmética previa. A ressalva permanece quanto ao escopo: o que foi corroborado é a razão entre as construções, e não o `S` de campanha ponta a ponta. A mensagem de commit de `d297377` citou os 1,3518 e os 0,38 antes de a corroboração existir, o que é a irregularidade registrada; o `S` honesto do ACO depois do espelhamento é da ordem de **1,006**, é projeção aritmética como as demais deste bloco, e o número definitivo vem do roteiro regenerado. | esta tarefa | consequência de F4-1 e F8-2 | F4-1, F8-2 |
| B10 | **Lacunas declaradas de A7 e A8**, repetidas aqui por serem os dois únicos achados do registro com situação `aberto com lacuna declarada`: as magnitudes de qualidade que sustentam a classe `L1`, 0,286856 para A7 e 0,272414 para A8, **não foram reproduzidas** pelo verificador, porque exigiriam alterar código sob contrato de somente leitura. Se a magnitude de A7 não se sustentar, o achado teria de ser reavaliado como defeito que altera resultados, sem a defesa de que a mudança é benéfica. | verificador da F3 | condiciona a classe de A7 e A8 | A7, A8 |
