# Formação de Lotes Operacionais de Linhas de Ônibus com Metaheurísticas

Trabalho final da disciplina **Metaheurísticas e Aplicações**, do curso de Métodos Matemáticos Aplicados da UTFPR.

O projeto investiga a aplicação e a comparação de três metaheurísticas - **Particle Swarm Optimization (PSO)**, **Busca Tabu (TS)** e **Ant Colony Optimization (ACO)** - ao problema de formação de lotes operacionais de linhas de ônibus.

## Objetivo

Dado um conjunto de linhas de ônibus e atributos que descrevem suas características territoriais, operacionais e funcionais, busca-se agrupá-las em lotes operacionais coerentes e equilibrados.

A formulação deverá considerar, progressivamente, critérios como:

- equilíbrio de demanda, produção quilométrica, frota e/ou custo operacional entre lotes;
- afinidade entre linhas;
- sobreposição de itinerários;
- compartilhamento de terminais;
- integração entre serviços;
- continuidade e coerência territorial;
- fragmentação de corredores e interfaces operacionais.

A primeira versão do problema será resolvida para um número fixo de lotes `K`. Em seguida, diferentes valores de `K` serão comparados para investigar a quantidade de lotes que produz o melhor compromisso entre os critérios considerados.

## Metaheurísticas

O mesmo problema e a mesma função objetivo serão avaliados com:

1. **PSO - Particle Swarm Optimization**
   - adaptação ao domínio combinatório;
   - representação contínua com decodificação para lotes;
   - documentação explícita da estratégia de discretização.

2. **TS - Tabu Search**
   - movimentos de realocação de linhas entre lotes;
   - lista tabu baseada em atributos dos movimentos;
   - critério de aspiração.

3. **ACO - Ant Colony Optimization**
   - construção sequencial da partição;
   - feromônio associado à alocação linha-lote;
   - informação heurística baseada em características do problema.

## Requisitos acadêmicos

A especificação formal do trabalho e as orientações fornecidas pelo professor estão preservadas em:

- [`docs/trabalho.md`](docs/trabalho.md)
- [`docs/dicas.md`](docs/dicas.md)

Esses documentos são a referência principal para os requisitos acadêmicos.

O trabalho exige, entre outros itens:

- implementação de PSO, TS e ACO;
- investigação de parâmetros;
- múltiplas execuções;
- comparação da qualidade das soluções;
- medição do tempo de CPU;
- análise de escalabilidade;
- instâncias de tamanhos diferentes;
- relatório técnico;
- vídeo-resumo de até 3 minutos.

## Estado atual

**A B11-E (execução do benchmark principal) foi concluída**, com 1.620 execuções
oficiais e zero falhas. **A B11A (experimento adicional com GPU) foi encerrada
com uma limitação registrada**: o PSO foi medido em GPU, com o speedup relatado
em `docs/experiments.md` §29.1.1-29.1.2, e o ACO não mostrou ganho relevante
nesse ambiente — ver a mesma referência para os detalhes. **A B11B (auditoria
técnica pré-execução) está fechada**, com 89 achados diagnosticados e 29
pacotes de correção implementados. **A B12 (análise e visualização) está
concluída**: a campanha gulosa oficial foi executada e a análise estatística
completa — testes de Friedman, Wilcoxon pareado com correção de Holm,
tamanho de efeito rank-biserial, escalabilidade e convergência — respondeu às
doze perguntas da Seção 31 de `docs/experiments.md`; os detalhes estão em
`docs/experiments.md` §33-44. O relatório técnico final, em
`docs/relatorio/relatorio.tex` (compilável via `docs/relatorio/build.sh`),
sintetiza toda essa análise no formato exigido pelo enunciado do trabalho.

O projeto concluiu a preparação dos dados, o núcleo comum do problema, o
contrato comum dos otimizadores, a Busca Tabu, o ACO, o PSO e o tuning oficial. As
instâncias, o carregamento, a canonicalização, a função objetivo, o orçamento de
avaliações, o cache opcional, o reparo de lotes vazios e o baseline guloso
determinístico estão implementados e testados. Também estão implementados a
configuração uniforme das execuções, o RNG local, os 100 checkpoints, a parada
estrita pelo orçamento, a cronometragem e o resultado serializável. A TS usa
realocações amostradas, memória de reversão, aspiração e reinícios. O ACO usa
construção canônica, heurística parcial e atualização de feromônio por geração.
O PSO usa Random Keys, inicialização balanceada, reparo contabilizado e
projeção coerente da solução reparada.

Decisões registradas:

- linguagem: **Python 3.14**;
- unidade de decisão: sentido/variante operacional de uma linha de ônibus;
- baseline: `K` fixo, com `K` em `{3, 4, 5, 6, 7, 8}`;
- função objetivo: quatro componentes com pesos iguais, cobrindo equilíbrio de demanda, equilíbrio de produção em PU·km, coerência territorial e afinidade funcional;
- métodos: PSO com adaptação por Random Keys, Busca Tabu e ACO;
- referência adicional: heurística gulosa determinística;
- protocolo: instâncias de 20, 60 e 150 unidades, 30 seeds, orçamento proporcional de avaliações e 100 checkpoints de convergência;
- ambiente oficial dos benchmarks: Linux nativo;
- GPU: experimento adicional, sem ser requisito de execução.

O tuning oficial completou 440 execuções na instância de 60 unidades, com
`K=5`, 60.000 avaliações e 10 seeds por configuração. Os parâmetros selecionados
automaticamente e congelados são:

- Busca Tabu: `tabu_tenure=10`, `neighborhood_size=20` e
  `stagnation_limit=100`;
- ACO: `alpha=1.0`, `beta=2.0`, `rho=0.1` e `n_ants=40`;
- PSO: `n_particles=40`, `inertia=0.4`, `cognitive=2.0` e `social=2.0`.

Os resultados consolidados e a seleção auditável estão em `results/tables/`.

O piloto pré-benchmark completou 18 execuções oficiais e 1.800 checkpoints no
commit `5a9b805`. A interrupção e a retomada, os limites de recursos e três
reproduções exatas foram aprovados. Os artefatos preliminares estão em
`results/tables/` e `results/figures/`, e o manifesto de congelamento bloqueia a
execução do benchmark se algum insumo protegido divergir.

A consolidação oficial da B11-E está em
`results/tables/benchmark_{runs,checkpoints}.parquet`, acompanhada pelo
`benchmark_manifest.json` completo e oficial (commit de execução `959e561`).

O estado detalhado e as pendências metodológicas estão em [`AGENTS.md`](AGENTS.md), [`docs/formulation.md`](docs/formulation.md) e [`docs/experiments.md`](docs/experiments.md).

## Estrutura atual e planejada

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
├── data/
│   ├── raw/
│   ├── processed/
│   └── instances/
├── experiments/
└── results/
    ├── tables/
    └── figures/
```

Os módulos do núcleo e das três metaheurísticas estão em `src/metaheuristica`.

## Ambiente e caminhos

Os benchmarks finais serão executados em Linux nativo. O desenvolvimento também poderá ocorrer no Windows. O caminho físico do projeto varia conforme o ambiente e não deve ser fixado em scripts: no Windows ele pode ser `D:\dev\metaheuristica`, enquanto no Linux será definido pela máquina ou pelo ambiente de execução.

Use caminhos relativos à raiz do projeto e, quando necessário, uma variável de ambiente para indicar essa raiz.

Exemplo usando `venv` no Windows PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Exemplo equivalente em Linux:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

As dependências e suas versões resolvidas estão em `pyproject.toml` e `uv.lock`.
Para preparar o ambiente de desenvolvimento:

```bash
uv sync --dev
```

## Execução

Os hiperparâmetros finais foram congelados pelo tuning. A automação permite
planejar, executar, retomar e consolidar campanhas. O núcleo e as
metaheurísticas de CPU podem ser verificados com:

```bash
uv run pytest -q tests
```

A suíte usa o pacote-fonte bruto da ARTESP em `_temp/dados_artesp/`, que o
`.gitignore` exclui do repositório. Um clone sem esse pacote deve declarar a
ausência explicitamente, ou a suíte falha com um guardião dedicado em vez de
pular os três testes de geração de instâncias em silêncio:

```bash
BUS_LOT_SEM_PACOTE_FONTE=1 uv run pytest -q tests
```

Com o pacote-fonte presente, os 564 testes coletados incluem esses três. Sem
ele, com a declaração acima, são 561 aprovados e 3 pulados.

A réplica GPU usa ambiente isolado e deve ser verificada separadamente:

```bash
uv run --project gpu pytest -q gpu/tests
```

O piloto diagnóstico anterior ao tuning pode ser inspecionado sem executar
cenários:

```bash
uv run python -m experiments.run \
  --config experiments/configs/pilot_diagnostic.toml plan
```

O piloto oficial pré-benchmark contém 18 cenários com os parâmetros congelados,
os orçamentos finais e a seed `20260818`:

```bash
uv run python -m experiments.run \
  --config experiments/configs/pilot.toml plan
```

Para executar ou retomar o piloto com o monitor Linux de recursos:

```bash
uv run python -m experiments.run \
  --config experiments/configs/pilot.toml \
  --workers 16 --monitor-resources execute
```

Uma quantidade maior de workers deve ser escolhida explicitamente. Cada worker
mantém uma thread por execução. Worktrees sujas são recusadas por padrão;
`--allow-dirty` existe somente para desenvolvimento e marca o resultado como não
oficial.

Depois que todos os cenários terminarem:

```bash
uv run python -m experiments.run \
  --config experiments/configs/pilot.toml consolidate
```

A validação reavalia as soluções, audita interrupção e retomada, verifica os
recursos e repete três cenários em saída isolada:

```bash
uv run python -m experiments.validate_pilot \
  --config experiments/configs/pilot.toml
uv run python -m experiments.analyze_pilot \
  --config experiments/configs/pilot.toml
uv run python -m experiments.freeze_benchmark generate \
  --config experiments/configs/pilot.toml --workers 16
```

O escopo protegido do congelamento é recalculado a cada verificação, percorrendo
o sistema de arquivos e **não** o índice do Git. Qualquer `.py` novo sob
`experiments/` ou sob `src/metaheuristica/` faz a verificação recusar com
`escopo protegido divergente`, inclusive arquivo não rastreado, ignorado pelo
`.gitignore` ou deixado como rascunho. A única exceção é nominal, arquivo por
arquivo, e está na constante `AUDIT_ONLY_PATHS` de
`experiments/benchmark_freeze.py`: hoje ela contém apenas
`experiments/audit_fingerprint.py`, que é ferramenta de conferência da auditoria e
não é importada por código de campanha algum. Durante a campanha isso derruba o portão
e, como a causa não é óbvia na mensagem, o diagnóstico é comparar o escopo com o
que o Git conhece:

```bash
uv run python -m experiments.freeze_benchmark verify --workers 16
git status --porcelain --untracked-files=all -- experiments src/metaheuristica
git ls-files --others -- experiments src/metaheuristica
```

Se o caminho nomeado pela recusa aparecer como não rastreado, é rascunho e deve
sair da árvore. Se estiver versionado, a recusa é legítima e exige renovação do
congelamento, que é operação de fechamento e não de campanha.

O benchmark principal é separado em infraestrutura (B11-I) e execução oficial
(B11-E). O preflight integral é somente leitura:

```bash
uv run python -m experiments.run_benchmark readiness
```

O roteiro estático contém cinco lotes de 324 execuções. Cada lote possui 54
subgrupos de seis seeds, ordenados pela duração estimada no piloto:

```bash
uv run python -m experiments.run_benchmark schedule
```

Um lote inteiro, ou um subgrupo dele, pode ser planejado sem executar nada:

```bash
uv run python -m experiments.run_benchmark plan --batch 1
uv run python -m experiments.run_benchmark plan --batch 1 \
  --algorithm aco --instance artesp_rmsp_150 --k 8
```

Quando a B11-E for explicitamente autorizada, o caminho oficial é o lote
inteiro, isto é `execute --batch N` **sem filtros**, e a sequência por lote é:

```bash
uv run python -m experiments.run_benchmark execute --batch 1
uv run python -m experiments.run_benchmark retry --batch 1
uv run python -m experiments.run_benchmark barrier --batch 1
```

A razão de o lote ser a unidade de invocação é de ocupação: o
`ProcessPoolExecutor` cria processos sob demanda, um por cenário submetido, de
modo que submeter um subgrupo de seis cenários ocupa **6 dos 16 workers**. O
roteiro hoje versionado soma 512,02 h-CPU, e esse número é **anterior à
aceleração do ACO**: submetido lote a lote, seriam 32,00 h ideais de relógio,
cerca de 6,5 h por lote; submetido subgrupo a subgrupo, 85,34 h, cerca de
17,07 h por lote.

Com a aceleração de 3,58 vezes já aplicada ao ACO, as 439,7 h-CPU que ele
respondia em `N=150` passam a 122,8, e o total cai para cerca de **195 h-CPU**:
submetido lote a lote, isso são **12,20 h ideais de relógio**, cerca de 2,4 h
por lote; submetido subgrupo a subgrupo, são **32,52 h**, cerca de 6,5 h por
lote. Esses valores são projeção aritmética sobre o piloto anterior, e o número
definitivo virá do roteiro regenerado depois que o piloto for refeito.

A invocação por subgrupo continua disponível, e o seu lugar é a **retomada
dirigida**, quando se quer reexecutar uma fatia identificada do lote:

```bash
uv run python -m experiments.run_benchmark execute --batch 1 \
  --algorithm aco --instance artesp_rmsp_150 --k 8
```

**Advertência sobre o raio de dano.** Pelo lote inteiro, a morte de um worker,
por sinal ou pelo matador por falta de memória, alcança os 324 cenários em voo,
contra 6 pela invocação por subgrupo. O que torna esse raio aceitável é a
distinção entre morte de worker e falha do cenário: o evento é registrado como
interrupção, **não** consome a tentativa única de cenário algum, e a retomada
reexecuta os pendentes. Uma segunda falha própria de um mesmo ID continua
bloqueando a campanha.

O comando pode ser interrompido por `Ctrl+C` e retomado. Resultados válidos são
ignorados, cenários interrompidos retornam à fila e falhas aguardam o fim da
rodada inicial do lote. `retry` só deve ser chamado se houver falhas elegíveis.
Se não houver, segue-se diretamente para `barrier`. Depois das cinco barreiras:

```bash
uv run python -m experiments.run_benchmark finalize
```

A campanha usa exatamente 16 workers, uma thread computacional por execução e
recusa alterações em código, automação, instâncias, parâmetros, configuração
ou ambiente protegido. O número de workers é fixado pelo congelamento e a CLI
recusa qualquer outro valor. A estimativa atual é de **13 a 15 horas no total**,
ou 2,6 a 3 horas por lote, isto é as 12,20 h ideais com margem operacional; a
margem é a mesma proporção que a faixa anterior à aceleração do ACO, quando
eram 35 a 40 horas no total, ou 6,5 a 8 horas por lote. É seguro pausar entre
lotes para controlar carga e
temperatura; pelo caminho oficial a pausa natural é o intervalo entre a barreira
de um lote e a execução do seguinte.

A barreira do lote confere resultados, checkpoints, proveniência, congelamento,
recursos, ausência de lacunas, duplicatas, temporários e artefato estranho, e
grava as suas tabelas em `results/operational/benchmark_batches/`, fora da
árvore versionada, de modo que a worktree continua limpa e o lote seguinte
permanece executável.

Uma repetição integral deve usar uma cópia da configuração com outro
`output_root`; não se apagam nem sobrescrevem resultados oficiais válidos. O
mecanismo cobre os artefatos de campanha, e **não** cobre
`experiments/configs/frozen_parameters.toml`, cujo caminho é fixo na raiz do
repositório: para conferir a análise do tuning sem escrever, use o modo de
verificação descrito adiante.

Os JSON individuais ficam em `results/raw/` e não entram no Git. As tabelas
Parquet e o manifesto em `results/tables/` são os artefatos consolidados. Um
resultado existente inválido interrompe a retomada e nunca é sobrescrito
automaticamente.

O tuning oficial é planejado por:

```bash
uv run python -m experiments.run \
  --config experiments/configs/tuning.toml plan
```

Essa configuração contém as 440 execuções concluídas sobre a instância de 60
unidades e não deve ser alterada sem um novo ciclo de tuning. A seleção
automática pode ser reproduzida por:

```bash
uv run python -m experiments.analyze_tuning \
  --config experiments/configs/tuning.toml
```

O comando recusa campanha incompleta ou não oficial e gera resumo, efeitos
marginais descritivos, seleção auditável e `frozen_parameters.toml`.

A análise é reprodutível byte a byte: sobre os mesmos insumos, e com as mesmas
versões de `pandas` e de `pyarrow`, cujas marcas os arquivos Parquet carregam,
ela produz os mesmos quatro artefatos, com os mesmos resumos. Isso importa
porque `frozen_parameters.toml` está entre os arquivos protegidos pelo
congelamento, e o seu caminho é fixo: ao contrário dos demais artefatos, ele
**não** acompanha `output_root`, de modo que a repetição integral por uma cópia
da configuração com outro `output_root` não protege este arquivo. Sob
congelamento, portanto, não se reexecuta a análise para conferir; confere-se
com:

```bash
uv run python -m experiments.analyze_tuning \
  --config experiments/configs/tuning.toml --verify
```

O modo de verificação produz os artefatos num diretório descartável fora da raiz
e apenas os compara com os oficiais. Ele não escreve nada. Sai com código 0 e
`artefatos idênticos aos oficiais` quando tudo confere, e com código 1 e a lista
dos caminhos divergentes quando não confere. Artefato ausente conta como
divergente. O documento de seleção recomputado sai na saída padrão nos dois
modos; o instante da execução sai na saída de erro, e de propósito não entra no
documento, porque o resumo dele é embutido no arquivo protegido.

Enquanto o tuning não for refeito, `--verify` responde 1 sobre os artefatos
versionados hoje, que foram produzidos antes das correções da auditoria: o
documento de seleção em disco ainda traz o carimbo de tempo e a tolerância
escalar. Os vencedores e as fontes são idênticos, e os dois arquivos Parquet
saem byte a byte iguais.

Exemplo mínimo de carregamento e avaliação:

```python
import numpy as np

from metaheuristica import FitnessEvaluator, load_artesp_instance

instance = load_artesp_instance("data/instances", 20)
evaluator = FitnessEvaluator(instance, k=3, budget=1)
solution = np.arange(instance.n_units) % 3
result = evaluator.evaluate(solution)
print(result.total_cost, result.c_demand, result.c_production)
```

O baseline guloso determinístico pode ser executado diretamente:

```python
from metaheuristica import load_artesp_instance, run_greedy

instance = load_artesp_instance("data/instances", 20)
result = run_greedy(instance, k=3)
print(result.solution, result.evaluation.total_cost, result.evaluations)
```

O ACO também exige configuração explícita. O exemplo usa os parâmetros
congelados:

```python
from metaheuristica import AcoConfig, RunConfig, load_artesp_instance, run_aco

instance = load_artesp_instance("data/instances", 20)
result = run_aco(
    instance,
    RunConfig(k=3, seed=20260817, budget=20_000),
    AcoConfig(alpha=1.0, beta=2.0, rho=0.1, n_ants=40),
)
print(result.solution, result.evaluation.total_cost, result.evaluations)
```

O PSO exige os quatro hiperparâmetros explícitos. O exemplo usa os parâmetros
congelados:

```python
from metaheuristica import PsoConfig, RunConfig, load_artesp_instance, run_pso

instance = load_artesp_instance("data/instances", 20)
result = run_pso(
    instance,
    RunConfig(k=3, seed=20260817, budget=20_000),
    PsoConfig(n_particles=40, inertia=0.4, cognitive=2.0, social=2.0),
)
print(result.solution, result.evaluation.total_cost, result.evaluations)
```

A Busca Tabu pode ser executada com a configuração congelada:

```python
from metaheuristica import RunConfig, TabuConfig, load_artesp_instance, run_tabu

instance = load_artesp_instance("data/instances", 20)
result = run_tabu(
    instance,
    RunConfig(k=3, seed=20260817, budget=20_000),
    TabuConfig(tabu_tenure=10, neighborhood_size=20, stagnation_limit=100),
)
print(result.solution, result.evaluation.total_cost, result.evaluations)
```

## Reprodutibilidade

Toda execução experimental deverá registrar, no mínimo:

- algoritmo;
- instância;
- seed;
- parâmetros;
- número de avaliações da função objetivo;
- melhor valor encontrado;
- solução final;
- histórico de convergência;
- tempo de CPU.

Instâncias sintéticas deverão ser reproduzíveis a partir de uma seed explícita.

## Desenvolvimento assistido por IA

Ferramentas de IA podem ser utilizadas no desenvolvimento, conforme permitido pelo enunciado do trabalho, mas todo código, documentação e resultado devem ser revisados e auditados pelos integrantes do grupo.

As instruções persistentes para agentes de desenvolvimento estão em [`AGENTS.md`](AGENTS.md).

## Próximos passos

1. Renovar a infraestrutura GPU com os parâmetros definitivos da B11-E.
2. Executar a campanha GPU somente depois de autorização explícita.
3. Gerar tabelas, gráficos e análises estatísticas.
4. Produzir o relatório final e o vídeo resumo.

## Experimento adicional com GPU

A infraestrutura isolada da B11A usa CuPy 14, CUDA 12 e Python 3.14, sem
alterar o ambiente CPU. A Busca Tabu não foi portada: sua trajetória é
sequencial e ainda não há profiling que justifique um experimento GPU próprio.

```bash
uv sync --project gpu --dev
uv run --project gpu python -m metaheuristica_gpu.run readiness
```

**O estudo adicional foi encerrado com limitação registrada.** A implementação
em GPU está correta — a conformidade aprovou com diferença máxima de `3,33e-16`
contra a régua normativa de `1e-12` —, mas a aceleração depende do algoritmo.
Três cenários ACO medidos deram speedup entre `1,002` e `1,026`, com menos de
`0,17 %` do tempo ocorrendo no dispositivo: o custo do ACO é a construção
sequencial das formigas no host, que responde por `98,7 %` do tempo e que a GPU
não toca. **O PSO, medido à parte em 30 cenários, é diferente**: speedup médio
de `1,814×` (mínimo `1,520×`, máximo `1,974×`), porque a avaliação responde por
cerca de 46 % do custo do PSO contra 1,2 % no ACO. Os números e a análise estão
em `docs/experiments.md`, seções 29.1.1 e 29.1.2.

A infraestrutura permanece íntegra e a campanha completa continua executável a
qualquer momento: o `readiness` indica `infrastructure_ready=true` e
`execution_ready=true`. A campanha GPU tem hoje 30 dos 60 resultados oficiais,
só o recorte PSO — parcial por desenho, e `consolidate` recusa sobre esse
estado corretamente. Um único ID por vez:

```bash
uv run --project gpu python -m metaheuristica_gpu.run plan
uv run --project gpu python -m metaheuristica_gpu.run execute --scenario-id ID
uv run --project gpu python -m metaheuristica_gpu.run validate --scenario-id ID
uv run --project gpu python -m metaheuristica_gpu.run consolidate
```

Cada execução exige 60 segundos consecutivos de GPU ociosa, a 50 °C ou menos e
com utilização média de até 5%; a temperatura é **aguardada**, e não motivo de
recusa imediata. A telemetria interrompe a execução diante de aquecimento sustentado,
throttling, concorrência ou perda de acesso ao driver, e é coletada por um
processo próprio, separado do processo cujo tempo é publicado. `resume`
reaproveita o mesmo ID e ignora resultados já completos. Os 60 resultados GPU
ficam em `results/gpu/` e não se misturam ao benchmark CPU.

**Quanto esperar entre um `execute` e o próximo.** Nada, e não é preciso
conferir nada antes. Não existe resfriamento ao fim da execução: a espera
térmica acontece dentro do preflight do cenário seguinte, que aguarda a placa
chegar a **50 °C ou menos** e só então exige a janela de ociosidade sustentada.
Há um único critério de aptidão térmica, avaliado num único ponto, na entrada de
cada cenário.

Se a placa não estabilizar em **20 minutos** de espera, o `execute` para com erro
explícito em vez de aguardar indefinidamente. Isso indica problema ambiental, de
ventilação ou carga externa na placa, e pede diagnóstico, não nova tentativa.
Concorrência de outro processo computacional e utilização média acima de 5%
continuam recusando de imediato, sem espera.

A temperatura pode ser conferida a qualquer momento com:

```bash
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits
```

A temperatura ociosa medida desta placa é de 38 °C, bem abaixo do limiar, de
modo que a espera, quando existir, é a de uma placa voltando à ociosidade.

## Análise e visualização

```bash
uv run python -m experiments.run_greedy
uv run python -m experiments.analyze_benchmark
```

Resumo de uma frase por pergunta da Seção 31 de `docs/experiments.md`
(detalhe completo e qualificado nas seções 33-44):

1. A Busca Tabu tem o menor custo médio em 17 das 18 combinações instância×K.
2. A Busca Tabu tem, em média, a menor variabilidade entre seeds.
3. ACO e Busca Tabu convergem a seu próprio patamar consumindo no máximo 22%
   do orçamento; o PSO só se estabiliza entre 35% e 74%.
4. A Busca Tabu tem o menor tempo computacional em 16 das 18 combinações; o
   ACO é o mais lento, entre ×20 e ×61 mais que a Busca Tabu.
5. De N=20 a N=150 o tempo cresce mais no ACO (×55,55) que no PSO (×24,36) e
   na Busca Tabu (×22,37); o custo melhora com N só no ACO.
6. O teste de Friedman rejeitou H0 em 18 das 18 combinações instância×K
   (todos p<0,05, o maior ≈2,94e-07).
7. PSO difere de ACO e Busca Tabu com magnitude prática grande e consistente;
   Busca Tabu×ACO tem magnitude pequena justamente onde a seção 38 não achou
   significância (`artesp_rmsp_150`, `k=4` a `k=8`).
8. A Busca Tabu melhora sobre a heurística gulosa nas instâncias pequena e
   média, mas nenhum dos três algoritmos supera a gulosa em nenhum `K` da
   instância grande.
9. Todos os cinco componentes medidos pioram, para os três algoritmos, ao
   passar de `K=3` para `K=8`.
10. Não há, na faixa `K∈{3,...,8}` testada, um `K` que melhore equilíbrio e
    coerência territorial/funcional ao mesmo tempo — ambos pioram juntos.
11. A aceleração por GPU não é uniforme: o PSO obteve speedup médio real de
    `1,814×`, mas o ACO não obteve aceleração relevante (`1,002×`-`1,026×`).
12. Não há um método uniformemente superior: a Busca Tabu é a escolha mais
    consistente na faixa testada, com a ressalva registrada na instância
    grande.

## Licença

Este projeto é distribuído sob a licença MIT. Consulte o arquivo [`LICENSE`](LICENSE).
