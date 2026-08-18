# AGENTS.md - Projeto de Metaheurísticas

## 1. Objetivo deste repositório

Este repositório contém o trabalho final da disciplina **Metaheurísticas e Aplicações**, do curso de Métodos Matemáticos Aplicados da UTFPR.

O projeto deverá formular, implementar e comparar metaheurísticas aplicadas a um problema prático de transporte coletivo.

### Tema escolhido

**Formação de lotes operacionais de linhas de ônibus.**

A pergunta central é:

> Como agrupar linhas de ônibus em lotes operacionais coerentes e equilibrados, considerando critérios territoriais, operacionais e de integração da rede?

Uma extensão desejável é estudar também **quantos lotes devem existir**, em vez de assumir um número `K` fixo.

---

## 2. Requisitos acadêmicos obrigatórios

A especificação formal do professor está em:

- `docs/trabalho.md`
- `docs/dicas.md`

Esses documentos são a fonte primária dos requisitos do trabalho. Em caso de conflito entre ideias deste arquivo e `docs/trabalho.md`, **prevalece `docs/trabalho.md`**.

O trabalho deve implementar e comparar, para o mesmo problema:

1. **PSO - Particle Swarm Optimization**
2. **TS - Tabu Search / Busca Tabu**
3. **ACO - Ant Colony Optimization**

O código deve ser desenvolvido em **Python**.

A análise deve incluir:

- qualidade da solução;
- média ao longo de múltiplas execuções;
- tempo de CPU;
- sensibilidade a parâmetros-chave;
- escalabilidade em instâncias pequenas, médias e grandes;
- comparação crítica entre PSO, TS e ACO.

O repositório também deverá conter um `README.md` com instruções de execução.

## 2.1. Preferências de redação

- Todos os textos devem estar em português brasileiro, com acentuação correta.
- Nunca usar o travessão tipográfico.
- Usar o hífen simples `-` quando ele for adequado.

---

## 3. Diretriz de escopo

O objetivo não é construir um modelo completo de planejamento ou concessão de transporte coletivo.

A prioridade é criar um **problema de otimização bem definido, reproduzível e suficientemente rico para comparar PSO, TS e ACO**.

Começar simples e adicionar critérios progressivamente.

Não adicionar novas restrições ou objetivos sem justificar:

1. o significado operacional;
2. como o termo é calculado;
3. como ele afeta o espaço de busca;
4. como será normalizado ou ponderado na função objetivo.

Evitar complexidade acidental.

---

## 4. Formulação inicial do problema

Considere:

- `N` linhas de ônibus;
- `K` lotes operacionais;
- cada linha deve pertencer a exatamente um lote.

Cada linha pode possuir atributos como:

- demanda;
- extensão;
- produção quilométrica;
- frota;
- custo operacional estimado;
- municípios/zonas atendidos;
- terminal principal;
- geometria do itinerário.

Também pode existir uma matriz de relacionamento entre linhas:

`W[i, j]`

representando intensidade da relação entre as linhas `i` e `j`, que pode incorporar:

- sobreposição de itinerários;
- compartilhamento de terminais;
- integração/transferências;
- proximidade territorial;
- relações funcionais conhecidas.

### Objetivo inicial

Minimizar uma função composta, por exemplo:

`C = w1 * desequilibrio + w2 * fragmentacao + w3 * relacoes_cortadas + w4 * terminais_divididos + penalidades`

Os componentes devem ser normalizados antes de combinar pesos, salvo justificativa explícita em contrário.

### Possíveis componentes

**Desequilíbrio entre lotes**

Evitar lotes excessivamente diferentes em:

- demanda;
- quilometragem;
- frota;
- custo operacional.

**Relações cortadas**

Penalizar pares de linhas fortemente relacionadas que sejam alocados em lotes diferentes.

**Fragmentação territorial**

Penalizar lotes espacialmente dispersos ou operacionalmente desconectados.

**Terminais/corredores divididos**

Penalizar a separação excessiva de linhas fortemente dependentes de uma mesma infraestrutura.

---

## 5. Número de lotes K

Não assumir definitivamente que `K` precisa ser fixo.

Trabalhar em duas etapas:

### Etapa A - baseline com K fixo

Resolver:

> dado `K`, qual é a melhor partição das linhas?

Executar para uma faixa plausível:

`K_min <= K <= K_max`

### Etapa B - seleção de K

Comparar o melhor resultado para diferentes valores de `K`.

Pode ser usado um custo estrutural de fragmentação, por exemplo:

`C_total(K) = C_particao(K) + lambda_K * K`

ou critérios operacionais que naturalmente penalizem excesso de lotes, como:

- tamanho mínimo por lote;
- tamanho máximo por lote;
- interfaces entre operadores;
- fragmentação de terminais/corredores;
- perda de escala.

Uma extensão futura pode tornar `K` endógeno à própria metaheurística, mas isso NÃO é requisito do primeiro baseline.

---

## 6. Representação canônica da solução

Para `K` fixo, usar inicialmente um vetor inteiro de tamanho `N`:

`solution[i] = k`

onde:

- `i` identifica a linha;
- `k in {0, ..., K-1}` identifica o lote.

Exemplo:

`[0, 0, 2, 1, 1, 0, 2]`

### Simetria de rótulos

Partições equivalentes podem possuir rótulos diferentes.

Exemplo:

- `[0, 0, 1, 1, 2, 2]`
- `[2, 2, 0, 0, 1, 1]`

representam a mesma partição.

Implementar uma função de **canonicalização de rótulos** para:

- comparação de soluções;
- cache;
- testes;
- armazenamento de resultados.

Exemplo de forma canônica:

`[0, 0, 1, 1, 2, 2]`

---

## 7. Adaptação das metaheurísticas

### 7.1. Busca Tabu

Representação: vetor de alocação de linhas a lotes.

Movimentos iniciais:

- `move(line, source_lot, target_lot)`
- opcionalmente `swap(line_a, line_b)`

A lista tabu deve preferencialmente armazenar atributos de movimento, e não a solução inteira.

Critério de aspiração padrão:

> permitir movimento tabu se gerar solução melhor que a melhor solução global encontrada.

Evitar esvaziar um lote quando `K` for fixo, ou aplicar reparo explícito.

### 7.2. ACO

Construir a solução linha por linha.

Feromônio inicial sugerido:

`tau[i, k]`

= desejabilidade aprendida de alocar a linha `i` ao lote `k`.

A heurística:

`eta[i, k]`

deve ser definida a partir de informação local do problema, por exemplo:

- afinidade com linhas já alocadas ao lote;
- impacto marginal no desequilíbrio;
- proximidade territorial;
- terminal compartilhado;
- impacto marginal em relações cortadas.

A escolha deve usar a lógica:

`P(i -> k) proportional to tau[i,k]^alpha * eta[i,k]^beta`

A heurística precisa ser documentada e testada.

### 7.3. PSO

PSO clássico é contínuo; o problema é combinatório.

Usar uma adaptação explícita e documentada por **Random Keys**, conforme o protocolo experimental atual:

- posição da partícula em espaço contínuo;
- decodificação determinística para uma alocação discreta em `K` lotes;
- reparo para garantir que todos os lotes permaneçam ativos;
- comparação com TS e ACO usando a mesma função objetivo e o mesmo orçamento de avaliações.

Não esconder a adaptação: ela é parte central do trabalho e deve ser explicada no relatório. Qualquer mudança para outra representação deverá ser registrada antes do tuning.

---

## 8. Comparabilidade experimental

As três metaheurísticas devem avaliar **exatamente a mesma função objetivo** e as mesmas instâncias.

Separar:

- lógica do problema;
- funções de custo;
- geração/carregamento de instâncias;
- algoritmos de otimização;
- experimento/benchmark;
- visualização.

Não duplicar a implementação da função objetivo dentro de PSO, TS e ACO.

Sempre que possível, usar o mesmo orçamento de avaliação de fitness ou documentar claramente por que os orçamentos diferem.

Registrar:

- seed;
- parâmetros;
- número de avaliações;
- melhor custo;
- histórico de convergência;
- tempo de CPU;
- solução final.

---

## 9. Instâncias

Criar inicialmente três classes:

### Pequena
- aproximadamente 10-20 linhas;
- 2-3 lotes.

### Média
- aproximadamente 30-60 linhas;
- 3-5 lotes.

### Grande
- aproximadamente 100+ linhas;
- 4-8 lotes.

Instâncias sintéticas devem ser reproduzíveis por `seed`.

Preferir dados reais ou semirrealistas quando isso não comprometer o prazo do trabalho.

Criar pelo menos uma instância minúscula em que o resultado possa ser verificado manualmente.

---

## 10. Estrutura atual e planejada do repositório

```text
metaheuristica/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── .gitignore
├── docs/
│   ├── dicas.md
│   ├── trabalho.md
│   ├── formulation.md
│   └── experiments.md
├── src/
│   └── metaheuristica/
│       ├── __init__.py
│       ├── problem.py
│       ├── objective.py
│       ├── canonical.py
│       ├── instances.py
│       ├── pso.py
│       ├── tabu.py
│       ├── aco.py
│       └── metrics.py
├── tests/
│   ├── test_objective.py
│   ├── test_canonical.py
│   ├── test_instances.py
│   ├── test_pso.py
│   ├── test_tabu.py
│   └── test_aco.py
├── data/
│   ├── raw/
│   ├── processed/
│   └── instances/
├── experiments/
│   ├── run_benchmark.py
│   └── configs/
└── results/
    ├── tables/
    └── figures/
```

A estrutura de diretórios já foi criada, mas os diretórios de código, testes, dados, experimentos e resultados ainda contêm apenas marcadores `.gitkeep`. Os arquivos Python listados acima são a estrutura planejada, não componentes já implementados.

A estrutura pode evoluir, mas deve manter separação clara entre problema, algoritmos, experimentos e resultados.

---

## 11. Engenharia e qualidade

- Python 3.14, conforme a restrição declarada em `pyproject.toml` e no protocolo experimental.
- Preferir código tipado quando isso melhorar clareza.
- Manter funções pequenas e testáveis.
- Evitar dependências pesadas sem necessidade.
- Usar seeds explícitas para reprodutibilidade.
- Não usar estado global para RNG.
- Testar invariantes da representação.
- Testar que cada metaheurística sempre retorna uma solução decodificável.
- Testar que a função objetivo produz o mesmo valor para partições equivalentes após canonicalização.
- Não otimizar desempenho prematuramente.
- Primeiro produzir uma implementação correta; depois medir gargalos.

---

## 12. Política de alterações

Antes de implementar mudanças grandes:

1. explicar brevemente o desenho proposto;
2. identificar arquivos afetados;
3. indicar implicações na comparação PSO × TS × ACO;
4. criar ou atualizar testes.

Não alterar simultaneamente:

- a representação;
- a função objetivo;
- e a lógica da metaheurística

sem necessidade. Fazer mudanças incrementais para preservar capacidade de diagnóstico.

## 12.1. Fluxo obrigatório por bloco

Todo bloco de trabalho definido em `TODO.md` deve seguir, sem saltos, esta
sequência:

1. brainstorming interativo, tratando uma decisão por vez;
2. escrita da especificação do bloco;
3. aprovação explícita da especificação pelo usuário;
4. escrita do plano de implementação;
5. aprovação explícita do plano pelo usuário;
6. implementação.

É proibido iniciar a implementação antes das duas aprovações explícitas. A
aprovação de uma decisão durante o brainstorming não equivale à aprovação da
especificação nem à aprovação do plano.

A especificação deve consolidar as decisões do brainstorming e definir escopo,
comportamento, contratos, invariantes, casos de erro e critérios de aceitação,
sem se transformar em uma sequência de passos de implementação.

O plano somente deve ser escrito depois da aprovação da especificação. Ele deve
decompor o trabalho em mudanças pequenas, indicar os arquivos afetados e definir
as verificações de cada etapa.

As especificações e os planos devem ser salvos localmente em `superpowers/`,
preferencialmente como `superpowers/B<N>_spec.md` e
`superpowers/B<N>_plan.md`. Esse diretório deve permanecer no `.gitignore` e
não pode ser enviado ao GitHub.

Ao interromper o trabalho, atualizar em `TODO.md` a fase atual, a última decisão
ou tarefa concluída e a próxima ação atômica, para permitir retomada sem depender
da memória da conversa.

---

## 13. Fontes e rastreabilidade

Documentos acadêmicos do professor:

- `docs/trabalho.md` - especificação formal do trabalho.
- `docs/dicas.md` - orientações de implementação.

Ao escrever relatório, comentários metodológicos ou documentação:

- distinguir requisitos do professor de decisões do projeto;
- citar fontes externas quando utilizadas;
- não inventar benchmark, resultado ou propriedade matemática;
- marcar explicitamente hipóteses e simplificações.

---

## 14. Estado atual do projeto

Estado registrado em 18/08/2026:

- a B5 foi incorporada à branch `main` e enviada ao remoto
  `https://github.com/tiagobaroni/bus-lot-optimization.git` no commit `ee9026c`;
- a B6 foi incorporada à branch `main` e enviada ao remoto no commit `5b6fd4c`;
- a B7 foi incorporada à branch `main` e enviada ao remoto no commit `e9daa2b`;
- a B8 foi incorporada à branch `main` e enviada ao remoto no commit `8ef628f`;
- as instâncias reais de 20, 60 e 150 unidades e a instância minúscula estão
  versionadas e carregam sem depender dos dados-fonte ignorados;
- a linguagem definida é Python 3.14;
- `docs/formulation.md` contém a formulação conceitual do baseline;
- `docs/experiments.md` contém o protocolo experimental planejado;
- `docs/trabalho.md` e `docs/dicas.md` preservam os requisitos e orientações acadêmicas;
- a unidade de decisão é o sentido/variante operacional de uma linha de ônibus;
- o baseline resolve separadamente `K` em `{3, 4, 5, 6, 7, 8}`;
- a função objetivo com quatro componentes, o reparo de lotes vazios, a
  canonicalização e a heurística gulosa determinística estão implementados e
  testados;
- o protocolo prevê instâncias aninhadas de 20, 60 e 150 unidades, 30 seeds por cenário, 100 checkpoints de convergência e orçamento de 20.000, 60.000 e 150.000 avaliações, respectivamente;
- o tuning planejado soma 440 execuções e o experimento principal soma 1.620 execuções;
- os benchmarks finais serão executados em Linux nativo, com uma thread por execução individual;
- nesta máquina de referência, usar por padrão 16 workers independentes, um por
  núcleo físico; não usar automaticamente as 32 threads lógicas;
- GPU é um experimento adicional e não será requisito para executar o projeto;
- o contrato comum dos otimizadores está implementado com `RunConfig`, RNG
  local, orçamento estrito, 100 checkpoints, cronometragem e resultado
  serializável;
- a Busca Tabu está implementada com realocações amostradas, memória de reversão,
  aspiração estrita e reinícios por estagnação ou bloqueio;
- o ACO está implementado com construção canônica, heurística de custo parcial,
  probabilidades estáveis e atualização de feromônio por geração;
- o PSO está implementado com Random Keys, inicialização balanceada, dinâmica
  síncrona, reparo contabilizado e projeção coerente;
- a B7 validou conjuntamente TS, ACO e PSO na instância minúscula e nos 18
  cenários ARTESP, sem alterar o código de produção;
- a B8 implementou TOML estrito, IDs por conteúdo, retomada,
  multiprocessamento, proveniência e consolidação, sem executar campanhas reais;
- a B9 completou as 440 execuções oficiais de tuning no commit `dc91468`, com
  16 workers, zero falhas, 44.000 checkpoints e consolidação oficial;
- os parâmetros congelados são Busca Tabu `(tabu_tenure=10,
  neighborhood_size=20, stagnation_limit=100)`, ACO `(alpha=1.0, beta=2.0,
  rho=0.1, n_ants=40)` e PSO `(n_particles=40, inertia=0.4, cognitive=2.0,
  social=1.5)`;
- os artefatos consolidados, o ranking, os efeitos marginais descritivos e a
  seleção auditável estão em `results/tables/`; qualquer alteração dos
  parâmetros congelados exige novo ciclo de tuning;
- a B10 implementou configuração oficial do piloto e do benchmark, validação
  dos parâmetros congelados, interrupção auditável, monitoramento por `/proc`,
  reprodução exata, figuras preliminares e manifesto de congelamento;
- o piloto oficial da B10 completou 18 execuções e 1.800 checkpoints no commit
  `5a9b805`, com zero falhas, retomada correta de 8 resultados preservados e 10
  pendentes, três reproduções exatas e critérios de recursos aprovados;
- o benchmark está configurado com seeds de 10 a 39 e expande exatamente 1.620
  cenários; sua execução é recusada se o manifesto de congelamento divergir;
- o ACO grande dominou o tempo do piloto, chegando a 10.971,45 s em
  `(N=150,K=8)`; isso afeta o planejamento operacional da B11, mas não altera o
  protocolo ou os parâmetros congelados;
- a B11-I concluiu a infraestrutura do benchmark com cinco lotes, 270
  subgrupos, prioridade pelo piloto, retomada, tentativa única, monitoramento,
  barreiras e consolidação testados;
- a B11-E permanece sem resultados oficiais e aguarda autorização explícita
  para uma janela com carga e temperatura controladas;
- o caminho físico do projeto não deve ser presumido: no Windows ele pode ser `D:\dev\metaheuristica`, enquanto no Linux será definido pelo ambiente de execução.

Os detalhes de dados, formulação, automação experimental e tuning estão
consolidados. Permanece pendente a execução do benchmark principal.

Próximo objetivo recomendado:

1. iniciar a B11-E somente após autorização explícita do usuário;
2. executar os subgrupos na ordem congelada e nas janelas térmicas disponíveis;
3. validar cada lote antes de avançar para o seguinte.
