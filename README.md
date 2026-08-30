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

O projeto concluiu a preparação dos dados, o núcleo comum do problema, o
contrato comum dos otimizadores, a Busca Tabu, o ACO, o PSO e o tuning oficial.
As
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
- PSO: `n_particles=40`, `inertia=0.4`, `cognitive=2.0` e `social=1.5`.

Os resultados consolidados e a seleção auditável estão em `results/tables/`.

O piloto pré-benchmark completou 18 execuções oficiais e 1.800 checkpoints no
commit `5a9b805`. A interrupção e a retomada, os limites de recursos e três
reproduções exatas foram aprovados. Os artefatos preliminares estão em
`results/tables/` e `results/figures/`, e o manifesto de congelamento bloqueia a
execução do benchmark se algum insumo protegido divergir.

A infraestrutura da B11-I está concluída e testada. Os cinco lotes, 270
subgrupos, escalonamento, retomada, tentativa única, monitoramento, barreiras e
consolidação estão prontos. A B11-E não foi iniciada e aguarda autorização
explícita para uma janela com carga e temperatura controladas.

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
metaheurísticas podem ser verificados com:

```bash
uv run pytest -q
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
`.gitignore` ou deixado como rascunho. Durante a campanha isso derruba o portão
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
    PsoConfig(n_particles=40, inertia=0.4, cognitive=2.0, social=1.5),
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

1. Executar o benchmark principal.
2. Gerar tabelas, gráficos e análises estatísticas.
3. Produzir o relatório final e o vídeo resumo.

## Experimento adicional com GPU

A infraestrutura isolada da B11A usa CuPy 14, CUDA 12 e Python 3.14, sem
alterar o ambiente CPU. A Busca Tabu não foi portada: sua trajetória é
sequencial e ainda não há profiling que justifique um experimento GPU próprio.

```bash
uv sync --project gpu --dev
uv run --project gpu python -m metaheuristica_gpu.run readiness
```

O `readiness` deve indicar `infrastructure_ready=true` e, até a conclusão da
B11-E, `waiting_for_b11e=true`. Depois da B11-E e de autorização explícita,
um único ID poderá ser executado por vez:

```bash
uv run --project gpu python -m metaheuristica_gpu.run plan
uv run --project gpu python -m metaheuristica_gpu.run execute --scenario-id ID
uv run --project gpu python -m metaheuristica_gpu.run validate --scenario-id ID
uv run --project gpu python -m metaheuristica_gpu.run consolidate
```

Cada execução exige 60 segundos de GPU ociosa, até 50 °C e utilização média
de até 5%. A telemetria interrompe a execução diante de aquecimento sustentado,
throttling, concorrência ou perda de acesso ao driver, e é coletada por um
processo próprio, separado do processo cujo tempo é publicado. `resume`
reaproveita o mesmo ID e ignora resultados já completos. Os 60 resultados GPU
ficam em `results/gpu/` e não se misturam ao benchmark CPU.

**Quanto esperar entre um `execute` e o próximo.** Nada. O resfriamento roda no
fim de cada cenário e só devolve quando a placa marca **50 °C ou menos**, que é
exatamente o mesmo limiar que o preflight do cenário seguinte aceita: os dois
leem uma única constante, e por isso o próximo `execute` pode ser disparado
imediatamente. A espera só é necessária quando um `execute` é disparado sem ter
passado por um resfriamento, por exemplo depois de uma execução interrompida ou
de qualquer outro uso da placa. Nesse caso, aguarde a temperatura cair a 50 °C
ou menos antes de tentar de novo, conferindo com:

```bash
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits
```

A temperatura ociosa medida desta placa é de 38 °C, bem abaixo do limiar, de
modo que a espera, quando existir, é a de uma placa voltando à ociosidade.

## Licença

Este projeto é distribuído sob a licença MIT. Consulte o arquivo [`LICENSE`](LICENSE).
