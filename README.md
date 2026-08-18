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

O benchmark principal pode ser inventariado sem executá-lo:

```bash
uv run python -m experiments.run \
  --config experiments/configs/benchmark.toml plan
```

Sua execução exige um manifesto de congelamento válido e recusa alterações em
código, automação, instâncias, parâmetros, configuração ou ambiente protegido.

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

1. Executar o piloto pré-benchmark com os parâmetros congelados.
2. Executar o benchmark principal.
3. Gerar tabelas, gráficos, análises estatísticas e o relatório final.

## Licença

Este projeto é distribuído sob a licença MIT. Consulte o arquivo [`LICENSE`](LICENSE).
