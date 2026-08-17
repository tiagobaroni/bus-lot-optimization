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

O projeto concluiu a preparação dos dados, o núcleo comum do problema e o
contrato comum dos otimizadores e a Busca Tabu. As
instâncias, o carregamento, a canonicalização, a função objetivo, o orçamento de
avaliações, o cache opcional, o reparo de lotes vazios e o baseline guloso
determinístico estão implementados e testados. Também estão implementados a
configuração uniforme das execuções, o RNG local, os 100 checkpoints, a parada
estrita pelo orçamento, a cronometragem e o resultado serializável. A TS usa
realocações amostradas, memória de reversão, aspiração e reinícios. ACO e PSO
ainda não foram implementados.

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

Os módulos do núcleo já implementados estão em `src/metaheuristica`. Os módulos
de PSO, Busca Tabu e ACO permanecem planejados para os próximos blocos.

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

Ainda não há um comando de benchmark, pois ACO, PSO e o executor experimental
não foram implementados. O núcleo pode ser verificado com:

```bash
uv run pytest -q
```

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

A Busca Tabu pode ser executada com configuração explícita. Os valores abaixo
são apenas um exemplo e não substituem o tuning planejado:

```python
from metaheuristica import RunConfig, TabuConfig, load_artesp_instance, run_tabu

instance = load_artesp_instance("data/instances", 20)
result = run_tabu(
    instance,
    RunConfig(k=3, seed=20260817, budget=20_000),
    TabuConfig(tabu_tenure=10, neighborhood_size=50, stagnation_limit=100),
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

1. Implementar e testar ACO e PSO com o mesmo orçamento de avaliações.
2. Executar o tuning, congelar os hiperparâmetros e realizar o benchmark principal.
3. Gerar tabelas, gráficos, análises estatísticas e o relatório final.

## Licença

Este projeto é distribuído sob a licença MIT. Consulte o arquivo [`LICENSE`](LICENSE).
