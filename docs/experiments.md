# Protocolo Experimental — Formação de Lotes Operacionais de Linhas de Ônibus

## 1. Objetivo

Este documento define o protocolo experimental para comparar as três metaheurísticas exigidas no trabalho:

- Particle Swarm Optimization (PSO), com adaptação por Random Keys;
- Busca Tabu (TS);
- Ant Colony Optimization (ACO).

Também será utilizada uma heurística gulosa determinística como baseline de referência.

O objetivo dos experimentos é comparar:

1. qualidade final das soluções;
2. robustez entre execuções independentes;
3. velocidade de convergência;
4. esforço computacional;
5. escalabilidade com o tamanho do problema;
6. sensibilidade aos principais hiperparâmetros;
7. comportamento dos algoritmos para diferentes números de lotes \(K\);
8. potencial de aceleração em GPU.

A formulação matemática e a função objetivo estão definidas em `docs/formulation.md`.

---

## 2. Instâncias experimentais

Serão utilizadas três classes de tamanho:

| Classe | Número de unidades |
|---|---:|
| Pequena | 20 |
| Média | 60 |
| Grande | 150 |

Cada unidade corresponde a um sentido/variante operacional de linha de ônibus.

### 2.1. Construção das instâncias

As instâncias serão construídas a partir da rede real, por **amostragem estratificada**, buscando preservar diversidade em:

- território/região;
- passageiros por dia;
- PU·km.

As instâncias serão **aninhadas**:

\[
\mathcal{L}_{20}\subset\mathcal{L}_{60}\subset\mathcal{L}_{150}.
\]

Assim, a instância pequena está contida na média e a média está contida na grande.

Esse desenho permite interpretar o crescimento de complexidade de forma mais limpa, pois as instâncias maiores representam ampliações progressivas do mesmo problema.

### 2.2. Registro da seleção

O processo de seleção deverá ser reproduzível.

Devem ser registrados:

- universo original de unidades;
- critérios de estratificação;
- seed utilizada na amostragem, quando aplicável;
- IDs das unidades pertencentes a cada instância.

---

## 3. Número de lotes

Cada uma das três instâncias será resolvida para:

\[
K\in\{3,4,5,6,7,8\}.
\]

Todos os valores de \(K\) serão testados nas três classes de tamanho.

O estudo não buscará forçar a identificação de um único valor ótimo de \(K\), pois a formulação baseline não contém penalidade explícita associada ao número de lotes.

Os valores de \(K\) serão tratados como **cenários de desenho institucional**, comparando seus compromissos entre:

- equilíbrio de demanda;
- equilíbrio de PU·km;
- coerência territorial;
- afinidade funcional.

---

## 4. Algoritmos comparados

O experimento principal comparará:

1. PSO;
2. Busca Tabu;
3. ACO.

A heurística gulosa será utilizada como baseline determinístico.

Todos os algoritmos deverão utilizar exatamente:

- a mesma formulação do problema;
- a mesma função objetivo;
- as mesmas matrizes de entrada;
- as mesmas regras de reparo;
- a mesma canonicalização de soluções.

---

## 5. Heurística gulosa de referência

A heurística gulosa será executada uma vez para cada combinação:

\[
\text{instância}\times K.
\]

Ela seguirá a regra definida em `formulation.md`:

1. ordenar unidades em ordem decrescente de PU·km;
2. alocar cada unidade ao lote que produzir o menor aumento marginal na função objetivo;
3. em caso de empate, escolher o lote com menor PU·km acumulado;
4. garantir que todos os lotes estejam ativos.

Como a heurística é determinística, ela será tratada como referência fixa, e não como método sujeito a análise estatística inferencial.

Para cada metaheurística será calculada a melhoria percentual em relação à gulosa:

\[
\text{Melhoria}(\%)=
100\cdot
\frac{C_{\text{gulosa}}-C_{\text{meta}}}
{C_{\text{gulosa}}}.
\]

---

## 6. Número de execuções

Para cada combinação:

\[
\text{algoritmo}\times\text{tamanho}\times K,
\]

serão realizadas:

\[
30
\]

execuções independentes.

Como existem:

- 3 algoritmos;
- 3 tamanhos;
- 6 valores de \(K\);
- 30 execuções;

o experimento principal compreenderá:

\[
3\times3\times6\times30=1620
\]

execuções de metaheurísticas.

---

## 7. Controle de aleatoriedade

Serão utilizadas sementes pseudoaleatórias explicitamente registradas.

Para cada combinação de tamanho e \(K\):

- o mesmo conjunto de 30 seeds será reutilizado em PSO, TS e ACO;
- cada algoritmo poderá utilizar sua própria estratégia de inicialização;
- a inicialização deverá ser totalmente reprodutível a partir da seed.

Não será exigida uma solução inicial idêntica entre os métodos, pois isso poderia distorcer a natureza populacional de PSO e ACO.

A comparabilidade será garantida principalmente por:

- mesmo problema;
- mesmos dados;
- mesmas seeds;
- mesmo orçamento de avaliações da função objetivo.

---

## 8. Critério de parada e orçamento computacional

A comparação principal será feita utilizando o **mesmo orçamento de avaliações da função objetivo**.

Não será utilizado o mesmo número de iterações, pois uma iteração possui custo e significado diferentes em PSO, TS e ACO.

Os orçamentos serão:

| Instância | Avaliações máximas |
|---|---:|
| 20 unidades | 20.000 |
| 60 unidades | 60.000 |
| 150 unidades | 150.000 |

A regra equivale, aproximadamente, a:

\[
1000
\]

avaliações da função objetivo por unidade da instância.

O tempo computacional será medido como resultado, e não utilizado como critério principal de parada.

---

## 9. Registro da convergência

Em cada execução serão armazenados 100 checkpoints igualmente espaçados no orçamento de avaliações.

Para cada checkpoint será registrado:

\[
C_{\text{best}}(e),
\]

onde \(e\) representa o número acumulado de avaliações da função objetivo.

Os checkpoints podem ser representados por:

\[
p_j=\frac{j}{100}, \qquad j=1,\ldots,100.
\]

Assim, cada curva representa a evolução da melhor solução em função da fração do orçamento total consumido.

Isso permite comparar algoritmos e tamanhos de instância em escala normalizada.

---

## 10. Métricas registradas por execução

Para cada execução serão armazenados, no mínimo:

### 10.1. Métrica principal

- melhor custo total final:

\[
C^*_{\text{final}}.
\]

### 10.2. Componentes da melhor solução

- \(C_D\): componente de equilíbrio de demanda;
- \(C_P\): componente de equilíbrio de PU·km;
- \(C_T\): componente territorial;
- \(C_A\): componente de afinidade funcional;
- \(CV_D\): coeficiente de variação de passageiros/dia;
- \(CV_P\): coeficiente de variação de PU·km.

### 10.3. Esforço computacional

- tempo total de otimização;
- número efetivo de avaliações;
- número de iterações ou ciclos realizados, apenas como informação auxiliar;
- número de reparos de solução, quando aplicável.

### 10.4. Convergência

- melhor custo nos 100 checkpoints.

### 10.5. Identificação experimental

- algoritmo;
- tamanho da instância;
- \(K\);
- seed;
- configuração de hiperparâmetros;
- ambiente computacional;
- versão do código/commit Git, quando possível.

---

## 11. Resumo estatístico

Para cada combinação:

\[
\text{algoritmo}\times\text{tamanho}\times K,
\]

as 30 execuções serão resumidas por:

- melhor valor observado;
- média;
- mediana;
- desvio-padrão;
- intervalo interquartil.

Essas estatísticas serão calculadas, no mínimo, para o custo final.

Quando útil, também poderão ser calculadas para:

- tempo;
- componentes da função objetivo;
- melhoria percentual em relação à heurística gulosa.

---

## 12. Tuning de hiperparâmetros

O tuning será realizado antes do experimento principal.

Será utilizada apenas:

- instância média: \(N=60\);
- \(K=5\).

Depois do tuning, os melhores parâmetros serão **congelados** e utilizados em todas as instâncias e valores de \(K\) no experimento principal.

A finalidade é evitar ajuste específico para cada cenário e reduzir o risco de overfitting experimental.

### 12.1. Estratégia

Será utilizada uma **busca em grade curta e controlada**.

Para cada configuração serão realizadas:

\[
10
\]

execuções independentes.

A melhor configuração será selecionada segundo:

1. menor média do custo final;
2. em caso de resultados muito próximos, menor desvio-padrão;
3. persistindo empate prático, menor tempo médio.

As seeds do tuning também deverão ser fixadas e registradas.

---

## 13. Grade de tuning do PSO

Parâmetros avaliados:

### Número de partículas

\[
n_p\in\{20,40\}.
\]

### Inércia

\[
w\in\{0.4,0.7\}.
\]

### Componente cognitivo

\[
c_1\in\{1.5,2.0\}.
\]

### Componente social

\[
c_2\in\{1.5,2.0\}.
\]

Total:

\[
2^4=16
\]

configurações.

Com 10 execuções por configuração:

\[
16\times10=160
\]

execuções de tuning.

---

## 14. Grade de tuning da Busca Tabu

Parâmetros avaliados:

### Tamanho da lista tabu

\[
L_{\text{tabu}}\in\{5,10,20\}.
\]

### Tamanho da vizinhança amostrada

\[
n_{\text{viz}}\in\{20,50\}.
\]

### Limite de estagnação

\[
n_{\text{stag}}\in\{50,100\}.
\]

Total:

\[
3\times2\times2=12
\]

configurações.

Com 10 execuções:

\[
12\times10=120
\]

execuções de tuning.

---

## 15. Grade de tuning do ACO

Parâmetros avaliados:

### Peso do feromônio

\[
\alpha\in\{1.0,2.0\}.
\]

### Peso da informação heurística

\[
\beta\in\{1.0,2.0\}.
\]

### Taxa de evaporação

\[
\rho\in\{0.1,0.3\}.
\]

### Número de formigas

\[
n_a\in\{20,40\}.
\]

Total:

\[
2^4=16
\]

configurações.

Com 10 execuções:

\[
16\times10=160
\]

execuções de tuning.

---

## 16. Custo total do tuning

O tuning completo compreenderá:

\[
160+120+160=440
\]

execuções.

Assim, antes dos experimentos adicionais de GPU, o protocolo completo prevê:

\[
1620+440=2060
\]

execuções de metaheurísticas.

---

## 17. Informação heurística do ACO

A informação heurística para a escolha de uma atribuição será baseada no aumento marginal da função objetivo.

De forma conceitual:

\[
\eta\propto\frac{1}{\Delta C+\varepsilon}.
\]

Quanto menor o custo marginal da alocação, maior sua atratividade.

Na implementação, deverá ser utilizada uma transformação numericamente estável para tratar:

- \(\Delta C=0\);
- \(\Delta C<0\);
- diferenças muito pequenas entre alternativas.

A regra definitiva usada no código deverá ser registrada no relatório técnico.

---

## 18. Comparação estatística entre metaheurísticas

Como não será assumida normalidade dos resultados, será utilizada análise não paramétrica.

### 18.1. Teste global

Será utilizado o **teste de Friedman** para comparar PSO, TS e ACO.

Hipótese nula:

\[
H_0:
\]

os algoritmos apresentam desempenho equivalente segundo a métrica analisada.

Será adotado:

\[
\alpha=0.05.
\]

### 18.2. Comparações par a par

Caso o teste global indique diferença significativa, serão aplicados testes de **Wilcoxon pareado** entre:

- PSO × TS;
- PSO × ACO;
- TS × ACO.

Será aplicada **correção de Holm** aos valores-p.

A análise pareada será baseada nas seeds controladas.

### 18.3. Tamanho de efeito

Além do valor-p, será reportada a **rank-biserial correlation** para as comparações pareadas.

O objetivo é distinguir:

- diferença estatisticamente detectável;
- diferença com magnitude prática relevante.

---

## 19. Comparação com a heurística gulosa

A gulosa será tratada como uma referência determinística.

Para cada metaheurística serão apresentados:

- diferença absoluta no custo;
- melhoria percentual;
- tempo de execução.

Não será aplicado teste estatístico inferencial contra a heurística gulosa.

---

## 20. Curvas de convergência

Para evitar excesso de gráficos no relatório, serão apresentadas curvas de convergência para:

- pequena, \(K=5\);
- média, \(K=5\);
- grande, \(K=5\).

Para cada algoritmo será exibida:

- mediana do melhor custo nos 100 checkpoints;
- faixa interquartil.

O eixo horizontal deverá representar:

- número de avaliações;
- ou percentual do orçamento consumido.

A segunda representação é preferível quando as três classes forem colocadas em uma mesma análise.

---

## 21. Análise de escalabilidade

A análise de escalabilidade utilizará, como caso representativo:

\[
K=5.
\]

Serão produzidos, no mínimo:

### 21.1. Tempo × tamanho

Gráfico de:

\[
\text{tempo médio de otimização}
\]

em função de:

\[
N\in\{20,60,150\}.
\]

### 21.2. Qualidade × tamanho

Gráfico de:

\[
\text{custo final médio}
\]

em função do tamanho da instância.

Esses gráficos deverão comparar PSO, TS e ACO.

Outros gráficos poderão ser incluídos caso revelem comportamento relevante.

---

## 22. Análise do número de lotes

Para cada valor:

\[
K\in\{3,4,5,6,7,8\},
\]

serão analisados separadamente:

- custo total;
- \(CV_D\);
- \(CV_P\);
- \(C_T\);
- \(C_A\).

O relatório não deverá declarar automaticamente um único \(K\) como ótimo.

A análise deverá procurar identificar:

- ganhos marginais ao aumentar \(K\);
- deterioração de coerência territorial ou funcional;
- melhoria ou piora do equilíbrio entre lotes;
- eventuais pontos de compromisso.

---

## 23. Ambiente computacional oficial

Os benchmarks finais serão executados em **Linux nativo**.

Hardware de referência:

- CPU: AMD Ryzen 9 5900XT;
- 16 núcleos físicos;
- 32 threads lógicas;
- 64 GB de memória RAM;
- GPU NVIDIA RTX 3060 para os experimentos adicionais de aceleração.

O ambiente deverá registrar:

- distribuição Linux;
- versão do kernel;
- versão do Python;
- versões das bibliotecas;
- versão do driver NVIDIA;
- versão do CUDA, quando aplicável;
- número de threads permitido por processo.

A versão-alvo do projeto será Python 3.14, desde que todas as bibliotecas necessárias estejam compatíveis no momento da execução final.

Caso alguma dependência crítica exija versão anterior, a versão efetivamente utilizada deverá ser documentada.

---

## 24. Paralelismo no benchmark principal

Cada execução individual será restringida a **uma thread de CPU**.

Os múltiplos núcleos físicos serão utilizados para executar diferentes seeds/configurações em paralelo.

Isso reduz diferenças artificiais decorrentes de paralelismo interno desigual entre PSO, TS e ACO.

Exemplo conceitual:

```text
16 núcleos físicos
→ até 16 execuções independentes simultâneas
→ 1 thread por execução
```

O número real de workers poderá ser reduzido caso benchmarks preliminares indiquem:

- contenção de memória;
- competição por cache;
- thermal throttling;
- perda de estabilidade temporal.

---

## 25. Medição do tempo computacional

O tempo registrado será exclusivamente o **tempo de otimização**.

Serão excluídos:

- leitura dos arquivos;
- construção de \(S_{ij}\);
- construção de \(W_{ij}\);
- processamento geoespacial;
- preparação da matriz OD;
- geração das instâncias;
- geração de gráficos;
- exportação final dos resultados.

O cronômetro deverá iniciar imediatamente antes da inicialização operacional do algoritmo e terminar imediatamente após sua última avaliação.

Deverá ser utilizada uma função monotônica de alta resolução, por exemplo:

```python
time.perf_counter()
```

---

## 26. Experimento adicional de GPU

A comparação principal permanecerá baseada em CPU.

A GPU será tratada como experimento adicional de aceleração.

### Cenário

- instância grande: \(N=150\);
- \(K=5\);
- 30 seeds;
- mesmos hiperparâmetros do experimento principal;
- mesmo orçamento de 150.000 avaliações.

Serão comparadas implementações CPU e GPU apenas nos algoritmos em que a paralelização por GPU for tecnicamente coerente.

PSO e ACO são candidatos naturais.

Busca Tabu poderá permanecer exclusivamente em CPU se sua estrutura sequencial não produzir paralelismo suficientemente eficiente.

### Speedup

Será calculado:

\[
S=
\frac{T_{\text{CPU}}}
{T_{\text{GPU}}}.
\]

Também deverá ser verificado se a versão GPU preserva:

- mesma função objetivo;
- mesma interpretação das soluções;
- resultados numericamente equivalentes quando aplicável.

A GPU não deverá ser requisito para executar o projeto.

---

## 27. Organização sugerida dos resultados

Cada execução deverá gerar uma linha em uma tabela principal, por exemplo:

```text
algorithm
instance_size
K
seed
best_cost
C_D
C_P
C_T
C_A
CV_D
CV_P
runtime_s
evaluations
hyperparameter_config
```

Os checkpoints de convergência podem ser armazenados em tabela separada:

```text
algorithm
instance_size
K
seed
checkpoint
evaluations
best_cost
```

Isso facilita:

- análise estatística;
- gráficos;
- auditoria;
- reprodução.

---

## 28. Reprodutibilidade

Antes da execução final, o repositório deverá permitir reproduzir os experimentos por comandos explícitos.

Exemplo de estrutura conceitual:

```bash
python -m src.experiments.tune --algorithm pso
python -m src.experiments.tune --algorithm tabu
python -m src.experiments.tune --algorithm aco

python -m src.experiments.run_main

python -m src.experiments.analyze
python -m src.experiments.plot

python -m src.experiments.run_gpu
```

Os comandos definitivos podem mudar durante a implementação.

O importante é manter separação entre:

1. geração/pré-processamento de dados;
2. tuning;
3. execução principal;
4. análise estatística;
5. geração de figuras.

---

## 29. Verificações antes do benchmark final

Antes das 1.620 execuções principais, deverá ser realizado um piloto curto para verificar:

1. todas as soluções respeitam \(K\) lotes não vazios;
2. canonicalização funciona corretamente;
3. CPU e memória permanecem estáveis;
4. as seeds reproduzem exatamente os mesmos resultados;
5. o contador de avaliações é idêntico entre execuções equivalentes;
6. checkpoints são gravados corretamente;
7. o tempo medido exclui pré-processamento;
8. não há paralelismo interno acidental;
9. o tuning foi congelado;
10. nenhuma alteração de algoritmo ocorre durante os experimentos principais.

---

## 30. Princípio de congelamento experimental

Após o início do benchmark principal:

- a função objetivo não deverá mudar;
- as instâncias não deverão mudar;
- as seeds não deverão mudar;
- os hiperparâmetros selecionados não deverão mudar;
- o orçamento não deverá mudar;
- regras de reparo não deverão mudar.

Se uma falha metodológica exigir alteração, os resultados anteriores afetados deverão ser descartados e a rodada correspondente deverá ser executada novamente.

---

## 31. Resultados mínimos esperados no relatório

O relatório deverá conseguir responder, no mínimo:

1. Qual algoritmo produz as melhores soluções em média?
2. Qual algoritmo apresenta menor variabilidade?
3. Qual converge mais rapidamente em função do orçamento de avaliações?
4. Qual possui menor tempo computacional?
5. Como o desempenho muda de \(N=20\) para \(N=150\)?
6. As diferenças são estatisticamente significativas?
7. Qual a magnitude das diferenças?
8. Quanto as metaheurísticas melhoram sobre a heurística gulosa?
9. Como os resultados mudam entre \(K=3\) e \(K=8\)?
10. Há trade-off entre equilíbrio e coerência territorial/funcional?
11. A aceleração por GPU produz speedup relevante?
12. Qual método parece mais adequado para esse tipo de problema e por quê?

---

## 32. Síntese do protocolo

### Experimento principal

\[
3\text{ algoritmos}
\times
3\text{ tamanhos}
\times
6\text{ valores de }K
\times
30\text{ seeds}
=
1620\text{ execuções}.
\]

### Tuning

\[
440\text{ execuções}.
\]

### Total antes do estudo GPU

\[
2060\text{ execuções}.
\]

### Orçamento por execução

- pequena: 20.000 avaliações;
- média: 60.000 avaliações;
- grande: 150.000 avaliações.

### Comparabilidade

- mesmas instâncias;
- mesmos \(K\);
- mesmas seeds;
- mesmo orçamento de avaliações;
- 1 thread por execução;
- Linux nativo;
- hiperparâmetros congelados após tuning.

### Análise

- melhor, média, mediana, desvio-padrão e IQR;
- Friedman;
- Wilcoxon pareado + Holm;
- rank-biserial correlation;
- curvas de convergência;
- análise de escalabilidade;
- comparação com gulosa;
- estudo adicional CPU × GPU.
