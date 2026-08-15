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
   - feromônio associado à alocação linha–lote;
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

O projeto está na fase de **formulação do problema**.

Decisões atuais:

- linguagem: **Python**;
- problema: formação de lotes operacionais de linhas de ônibus;
- baseline: `K` fixo;
- análise posterior: varredura de diferentes valores de `K`;
- extensão possível: `K` endógeno às próprias metaheurísticas;
- todas as metaheurísticas deverão avaliar exatamente a mesma função objetivo e as mesmas instâncias.

Antes da implementação dos algoritmos, serão definidos:

1. modelo de dados mínimo;
2. representação da solução;
3. componentes da função objetivo;
4. normalização e pesos;
5. restrições hard e soft;
6. instâncias sintéticas verificáveis;
7. protocolo experimental.

## Estrutura planejada

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

A estrutura poderá ser simplificada ou ajustada conforme a formulação amadurecer.

## Ambiente

Recomendação inicial:

- Python 3.14
- ambiente virtual local
- dependências declaradas em `pyproject.toml`

Exemplo usando `venv` no Windows PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

As dependências serão definidas após a formulação inicial. A intenção é manter o conjunto pequeno, provavelmente incluindo bibliotecas para:

- arrays e cálculo numérico;
- manipulação de dados;
- grafos/geometria, se necessário;
- gráficos;
- testes.

## Execução

Os comandos de execução serão definidos quando a primeira versão funcional estiver implementada.

A meta é que a execução experimental seja reproduzível por linha de comando, por exemplo:

```bash
python -m experiments.run_benchmark --config experiments/configs/baseline.yaml
```

O formato final ainda poderá mudar.

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

1. Consolidar `docs/formulation.md`.
2. Definir uma instância mínima verificável manualmente.
3. Implementar e testar a função objetivo.
4. Consolidar `docs/experiments.md`.
5. Implementar uma heurística de referência simples.
6. Implementar TS, ACO e PSO.
7. Realizar tuning e experimentos de escalabilidade.
8. Gerar tabelas, gráficos e relatório final.

## Licença

Projeto acadêmico. A licença de distribuição ainda não foi definida.
