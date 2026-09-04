# Protocolo Experimental - Formação de Lotes Operacionais de Linhas de Ônibus

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

### 2.3. Regra de seleção adotada

São elegíveis apenas unidades com demanda, PU·km, centroide das paradas e
estratos necessários não nulos. Em particular, as 11 unidades sem PU·km são
excluídas antes da amostragem, pois não permitiriam calcular um dos componentes
da função objetivo sem imputação.

O campo `programacao_vigente_na_data` não é usado como filtro. No sistema da
ARTESP, a programação é atualizada quando há alteração do serviço, enquanto o
registro anterior continua representando a operação que não foi alterada. Por
isso, o valor `False` nesse campo não indica inatividade. A presença de
passageiros observados confirma a operação das unidades mantidas no universo.

A similaridade de mercados O-D será mantida na função objetivo, embora cerca de
64,1% da massa da matriz possua destino modelado por modelo gravitacional. Os
resultados serão descritos como derivados de uma matriz que combina informação
observada e modelada, nunca como fluxos integralmente observados. Uma análise
adicional poderá retirar \(O_{ij}\) de \(W_{ij}\) e renormalizar os dois
componentes restantes para medir a sensibilidade a essa limitação.

A cobertura territorial é representada por uma grade de 4 por 4. Seus limites
são os quartis das latitudes e longitudes dos centroides médios das paradas de
cada unidade elegível. A instância de 20 unidades deve conter ao menos uma
unidade de cada uma das 16 células, impedindo concentração em uma única parte da
RMSP.

Depois dessa cobertura inicial, a seleção é incremental e busca aproximar as
distribuições do universo em célula espacial, quartil de demanda e quartil de
PU·km. O desvio territorial recebe peso 2, enquanto os desvios de demanda e
PU·km recebem peso 1 cada. A seed adotada é `20260816`, e os empates são
resolvidos por uma prioridade pseudoaleatória determinada por essa mesma seed e,
por fim, por `unit_id`.

O gerador está em `experiments/generate_instances.py`. Os IDs selecionados e o
manifesto completo da seleção ficam em `data/instances/`.

Para tornar o benchmark executável sem acesso ao pacote-fonte ignorado pelo
Git, `data/instances/` também contém os atributos das 150 unidades e uma tabela
esparsa com \(S_{ij}\), \(T_{ij}\), \(I_{ij}\) e \(O_{ij}\). As instâncias de
20 e 60 são obtidas filtrando essas tabelas pelos IDs registrados, sem duplicar
os dados. Pares ausentes da tabela esparsa têm valor zero nas quatro métricas.

O mesmo diretório contém um GeoPackage para cada tamanho experimental, com
camadas de itinerários, paradas e terminais que podem ser abertas diretamente no
QGIS. A instância sintética `tiny_manual`, com quatro unidades e dois lotes,
possui solução ótima canônica `[0, 0, 1, 1]` e custo zero, além de seu próprio
GeoPackage com itinerários e paradas. Ela é usada somente para verificação
manual e testes, não integra o benchmark comparativo.

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

Cada execução usa um `numpy.random.Generator` local, inicializado por
`numpy.random.PCG64(seed)`. Não é permitido usar ou alterar RNG global. Todas as
consultas à função objetivo consomem orçamento, incluindo inicialização, reparo,
soluções repetidas e cache hits. O cache fica desabilitado por padrão.

O algoritmo é interrompido imediatamente depois da avaliação que consome o
limite, ainda que isso ocorra no meio de uma iteração, geração ou construção. O
melhor incumbente viável é então devolvido com o motivo
`budget_exhausted`.

---

## 9. Registro da convergência

Em cada execução serão armazenados 100 checkpoints igualmente espaçados no orçamento de avaliações. Para orçamento (B), o checkpoint (j) é registrado imediatamente depois da avaliação de limiar

\[
e_j=\left\lceil\frac{jB}{100}\right\rceil,
\qquad j=1,\ldots,100.
\]

Para cada checkpoint serão registrados o melhor custo total acumulado e seus
quatro componentes normalizados. A solução completa é armazenada somente no
resultado final.

O valor principal de cada checkpoint é:

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

Cada avaliação é processada individualmente, mesmo que o método trabalhe com
populações ou lotes de candidatos. Assim, nenhum algoritmo arredonda o orçamento
para completar sua iteração interna.

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

O tuning foi realizado antes do experimento principal.

Será utilizada apenas:

- instância média: \(N=60\);
- \(K=5\).

Os melhores parâmetros foram **congelados** e serão utilizados em todas as
instâncias e valores de \(K\) no experimento principal.

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

As seeds fixadas para o tuning são `{0,1,2,3,4,5,6,7,8,9}`. O benchmark usará
posteriormente um conjunto disjunto. A seleção é automática e separada por
algoritmo: menor média do custo, empate até `1e-12` resolvido por menor
desvio-padrão amostral (`ddof=1`), depois menor tempo médio e, por fim, menor
tupla lexicográfica dos hiperparâmetros.

O tuning usa 16 processos independentes depois de preflight, um por núcleo
físico e sempre com uma thread por execução. O tempo é somente o terceiro
desempate, pois concorrência
pode introduzir ruído. Nenhuma configuração é eliminada antecipadamente e a
seleção exige as 440 execuções oficiais completas.

Além do resumo por configuração, foram calculados efeitos marginais por nível
de hiperparâmetro. Eles são exclusivamente descritivos e não são interpretados
como efeitos causais, pois existem interações entre parâmetros.

### 12.2. Resultado vigente do tuning oficial

A campanha foi refeita depois das correções da auditoria, no commit de campanha
`3205687`, com 16 workers, e completou as 440 execuções sem falhas. Foram
consolidadas 440 linhas de execução e 44.000 checkpoints. Os números abaixo são
os resultados vigentes; os valores da execução de 17/08/2026 foram substituídos
porque a correção do PSO alterou resultados.

| Algoritmo | Parâmetros selecionados | Custo médio | Desvio-padrão amostral | Segundo colocado | Diferença de média |
|---|---|---:|---:|---:|---:|
| Busca Tabu | `tabu_tenure=10`, `neighborhood_size=20`, `stagnation_limit=100` | 0,126415 | 0,013287 | 0,129629 | 0,003214 |
| ACO | `alpha=1.0`, `beta=2.0`, `rho=0.1`, `n_ants=40` | 0,146303 | 0,021000 | 0,151504 | 0,005201 |
| PSO | `n_particles=40`, `inertia=0.4`, `cognitive=2.0`, `social=2.0` | 0,269236 | 0,030456 | 0,280569 | 0,011333 |

A análise marginal descritiva sugere, dentro das grades avaliadas, menor custo
médio com `alpha=1.0` no ACO, `inertia=0.4` e `social=2.0` no PSO e
`stagnation_limit=100` na Busca Tabu. Esses contrastes não são causais e não
isolam interações entre hiperparâmetros. Os resultados completos estão nos
Parquet de resumo e efeitos em `results/tables/`, e os parâmetros oficiais estão
em `experiments/configs/frozen_parameters.toml`. Qualquer alteração nesses
parâmetros exige um novo ciclo de tuning.

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

O PSO implementado usa posição Random Keys de dimensão `N`, topologia global,
inicialização balanceada, velocidade limitada a `[-0.5,0.5]` e posição limitada
a `[0,1]`. Lotes vazios são tratados pelo reparo comum, cujas avaliações também
consomem o orçamento experimental. A execução CPU com NumPy e `float64` é a
referência normativa; GPU permanece um estudo adicional posterior.

Com 10 execuções por configuração:

\[
16\times10=160
\]

execuções de tuning.

---

## 14. Grade de tuning da Busca Tabu

A Busca Tabu utiliza somente realocações de uma unidade entre lotes, sem
esvaziar a origem. A vizinhança é amostrada uniformemente sem reposição. O
retorno da unidade ao lote anterior permanece tabu por uma quantidade de
movimentos aceitos, com aspiração apenas por melhora estrita do melhor global.

Movimentos admissíveis de piora podem ser aceitos. Ao atingir o limite de
estagnação, ou quando toda a amostra está tabu sem aspiração, a execução reinicia
em outra solução aleatória balanceada e preserva o melhor global.

O `swap` não faz parte do experimento principal por acrescentar uma vizinhança
de até `O(N²)`. Sua inclusão depende de evidência de estagnação após os testes
com `move`.

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

O ACO constrói diretamente sequências canônicas, garantindo `K` lotes ativos sem
reparo. A informação heurística normaliza em `[1, 2]` os custos parciais das
alternativas permitidas. Cada solução completa consome uma avaliação.

Todas as formigas de uma geração usam a mesma matriz `tau`. Ao completar a
colônia, aplica-se evaporação por `(1-rho)` e cada formiga deposita
`1-custo_total` nas próprias atribuições. Geração interrompida pelo orçamento
não atualiza feromônio parcialmente.

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

Nesta máquina de referência, o padrão será de 16 workers independentes, um por
núcleo físico. As 32 threads lógicas não serão usadas automaticamente. O número
real de workers poderá ser reduzido caso benchmarks preliminares indiquem:

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
C_D
C_P
C_T
C_A
```

Isso facilita:

- análise estatística;
- gráficos;
- auditoria;
- reprodução.

O tempo `runtime_s` usa relógio monotônico e cobre a preparação operacional
interna do algoritmo, sua inicialização e suas avaliações. Ficam fora dessa
janela o carregamento da instância, a leitura de arquivos, a validação e
canonicalização finais, a serialização e a gravação do resultado.

---

## 28. Reprodutibilidade

### 28.1. Automação, retomada e integridade

As campanhas são descritas por TOML estrito e expandidas em cenários
determinísticos. Cada cenário recebe SHA-256 calculado sobre algoritmo,
hiperparâmetros, instância, `K`, seed, orçamento, pesos e cache. A componente de
instância cobre o SHA-256 do JSON de definição **e** o SHA-256 de cada arquivo de
dados que o carregador abre à parte, porque o JSON das instâncias ARTESP traz
apenas nome, contagem e a lista de unidades: demanda, produção e métricas de par
vêm de `artesp_rmsp_150_units.parquet` e `artesp_rmsp_150_pair_metrics.parquet`.
Sem os dois no identificador, dados de objetivo diferentes produziriam cenários
com o mesmo identificador. Resultados individuais são publicados atomicamente em
JSON e somente um documento válido e com hash esperado é considerado concluído.

A CLI oferece `plan`, `execute` e `consolidate`. A execução é sequencial por
padrão e aceita processos independentes por `--workers`, mantendo uma thread por
execução. Retomadas ignoram resultados válidos, tentam novamente falhas e
interrompem diante de arquivo corrompido ou incompatível.

Os JSON são fonte operacional. A consolidação produz uma tabela Parquet de
execuções, outra de checkpoints e um manifesto com contagens e hashes. Campanha
incompleta exige autorização explícita e permanece marcada como provisória e não
oficial.

Execuções oficiais exigem Git disponível e worktree limpa. Ambiente, commit,
versões, limites de threads e instantes UTC são registrados. Autorizações para
estado sujo ou não versionado existem apenas para desenvolvimento e tornam o
resultado não oficial.

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

Antes do tuning, uma validação cruzada diagnóstica submete TS, ACO e PSO ao
mesmo validador de resultado. Ela possui duas camadas:

1. na instância minúscula, cada método usa `K=2`, orçamento 100 e seeds
   `{0,1,2}` e deve alcançar o ótimo conhecido de custo zero;
2. nas instâncias ARTESP, cada método percorre os 18 cenários formados pelos
   tamanhos `{20,60,150}` e valores de `K` de 3 a 8, com seed `20260817` e
   orçamento 100.

As configurações dessa etapa são somente diagnósticas e não antecipam o tuning.
O validador exige orçamento exato, 100 checkpoints, incumbente não crescente,
solução canônica e viável, reavaliação pela função objetivo comum, serialização
JSON e cache inativo. Os cenários `(20,3)`, `(60,5)` e `(150,8)` são repetidos
para cada método depois de uma execução intermediária.

A validação também confirma que o RNG global, as configurações e as instâncias
permanecem inalterados e que a ordem dos algoritmos não afeta os resultados.
Não se fixa limite absoluto de RAM nessa suíte, pois ele seria dependente da
máquina. A medição quantitativa pertence ao piloto em ambiente controlado.

Nenhuma tabela experimental é persistida nesta etapa. Persistência, retomada e
consolidação pertencem à automação experimental.

O piloto pré-benchmark da B10 usa a seed `20260818`, os parâmetros congelados e
os orçamentos oficiais. Ele combina os três algoritmos, as instâncias de 20, 60
e 150 unidades e `K` em `{3,8}`, totalizando 18 execuções.

A campanha começa com 16 workers e monitoramento por `/proc`. Depois de ao
menos uma conclusão, uma interrupção por `Ctrl+C` verifica a preservação de
resultados atômicos e a retomada dos cenários pendentes. O monitor registra CPU,
RSS agregado, memória disponível, swap, processos e threads a cada segundo.

Os critérios operacionais são ausência de OOM e consumo de swap, uma thread
computacional ativa por execução, CPU compatível com até 16 workers, ausência
de otimizadores persistentes e memória disponível igual ou superior ao maior
valor entre 10% da RAM e 2 GiB. Threads auxiliares ociosas do alocador ou da
leitura Parquet são registradas separadamente e não contam como paralelismo
computacional do otimizador.
Falha exclusivamente de recursos exige repetição integral da rodada. O número
de workers **não** é reduzido: ele é fixado em 16 pelo congelamento, e tanto a
CLI quanto a verificação do manifesto recusam qualquer outro valor. A
recuperação passa por **nova sessão registrada** da mesma rodada, e nunca por
sobrescrever o resumo de recursos de uma sessão já registrada: o diário
operacional precisa preservar o registro fiel de que uma sessão específica
reprovou em recursos.

Três execuções completas são repetidas em saída isolada: TS em `(20,3)`, ACO em
`(60,8)` e PSO em `(150,3)`. Todos os campos determinísticos devem coincidir.

O piloto verifica:

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

As seeds do benchmark principal são os inteiros de `10` a `39`, usados de forma
pareada em todos os métodos e disjuntos do tuning e do piloto. A configuração
`experiments/configs/benchmark.toml` expande exatamente 1.620 cenários.

Depois da aprovação do piloto, um manifesto registra hashes do código,
automação, instâncias, configurações, dependências e artefatos. A execução do
benchmark é recusada se qualquer item protegido ou o ambiente divergir.

### 29.1. Resultado do piloto oficial

O piloto foi executado em 18/08/2026 no commit `5a9b805`, com 16 workers, e
concluiu as 18 execuções e os 1.800 checkpoints sem falhas. A interrupção
planejada ocorreu depois de 8 conclusões; a retomada preservou essas execuções e
processou somente as 10 pendentes.

O monitor registrou pico agregado de 2,34 GiB de RSS e 1.635% de CPU. A menor
memória disponível foi 35,0 GiB, o swap permaneceu sem uso e cada otimizador
teve no máximo uma thread computacional ativa. As três reproduções selecionadas
coincidiram integralmente nos campos determinísticos.

O tempo revelou forte assimetria operacional. No ACO, `(150,3)` consumiu
6.389,35 s e `(150,8)` consumiu 10.971,45 s, enquanto os máximos observados de
TS e PSO foram 68,96 s e 91,20 s. Esses valores são descritivos de uma única
seed e não sustentam conclusão estatística, mas devem orientar o escalonamento
da B11.

### 29.2. Infraestrutura e execução da B11

A B11 foi separada em dois marcos. A B11-I implementa e testa integralmente a
infraestrutura, sem produzir resultados oficiais. A B11-E começa somente por
autorização explícita, em uma janela na qual carga e temperatura da máquina
possam ser controladas.

As 30 seeds formam cinco lotes disjuntos de seis seeds. Cada lote contém 324
execuções e é dividido em 54 subgrupos definidos por algoritmo, instância e
`K`. Um subgrupo contém seis execuções e pode ser interrompido e retomado
isoladamente. A barreira de auditoria continua pertencendo ao lote completo.

A unidade de invocação oficial é o **lote inteiro**, isto é `execute --batch N`
sem filtros. O `ProcessPoolExecutor` cria processos sob demanda, um por cenário
submetido, de modo que submeter um subgrupo por vez ocupa 6 dos 16 workers e
converte as 512,02 h-CPU do roteiro versionado em 85,34 h de relógio, contra
32,00 h ideais do lote inteiro. Esses quatro números são anteriores à aceleração
do ACO; com ela, o total passa a cerca de 195 h-CPU, isto é 32,52 h pelo subgrupo
contra 12,20 h ideais pelo lote inteiro. O subgrupo permanece como caminho de retomada dirigida.
Pelo lote inteiro, a morte de um worker alcança os 324 cenários em voo, e é por
isso que ela é registrada como interrupção, sem consumir a tentativa única.

Os subgrupos são ordenados antes da B11-E pela duração estimada com os tempos do
piloto. Para cada algoritmo e instância, `K=3` e `K=8` são âncoras e os valores
intermediários usam interpolação linear. Tempos da própria B11-E não alteram a
fila. A estimativa resultante, já pela invocação por lote inteiro, era de
aproximadamente 33 horas ideais e de 35 a 40 horas com margem operacional, cerca
de 6,5 a 8 horas por lote. Com a aceleração de 3,58 vezes do ACO, ela passa a
aproximadamente 12,20 horas ideais e de 13 a 15 horas com margem operacional,
cerca de 2,6 a 3 horas por lote. A projeção mantém a mesma proporção de margem e
será substituída pelo roteiro regenerado depois que o piloto for refeito.

Depois que o lote recebe a rodada inicial integral, cada ID falho pode ser
repetido uma única vez. Uma segunda falha bloqueia a campanha. Uma
interrupção externa não conta como falha. O lote seguinte só é liberado após a
barreira confirmar 324 resultados, 32.400 checkpoints, proveniência,
congelamento, recursos, ausência de lacunas, duplicatas, temporários e artefato
estranho ao roteiro. A barreira confere esses itens por si, e não pela linha de
comando que a invoca; registra no relatório do lote o commit, o estado da
worktree e o hash do congelamento; e grava as suas tabelas em
`results/operational/`, fora da árvore versionada. Uma interrupção externa,
inclusive morte de worker por sinal ou pelo matador por falta de memória, é
registrada como interrupção e não consome a tentativa única. O bloqueio por
segunda falha é propriedade do histórico do ID e não do estado corrente.

Os comandos operacionais definitivos estão documentados no `README.md`. O
preflight `experiments.run_benchmark readiness` é somente leitura. O roteiro
estático fica em `results/tables/benchmark_execution_schedule.json` e não
contém resultados científicos.

---

## 29.1. Infraestrutura GPU da B11A

O estudo adicional mantém ACO e PSO híbridos: controle, RNG, construção,
reparo e estado ficam na CPU; somente avaliações independentes da função
objetivo são agrupadas em CuPy com `float64`. A função CPU permanece normativa.
A Busca Tabu foi deferida porque a atualização do incumbente após cada
movimento torna seu caminho atual sequencial; uma versão GPU futura dependerá
de profiling que demonstre ganho na avaliação paralela da vizinhança.

A campanha contém 60 cenários, ACO e PSO em `N=150`, `K=5`, seeds 10 a 39 e
150.000 avaliações. Ela é sequencial, usa namespace próprio e só pode começar
depois da B11-E. O PSO usa os parâmetros definitivos `n_particles=40`,
`inertia=0.4`, `cognitive=2.0` e `social=2.0`. A conformidade exige tolerâncias
absoluta e relativa de `1e-12`, igualdade de orçamento e checkpoints,
arbitragem CPU de quase empates e confirmação CPU da solução final.

O tempo oficial inclui transferências, sincronizações e arbitragens ocorridas
durante a otimização. Contexto, compilação e aquecimento prévios são registrados
separadamente. O speedup é pareado com a execução CPU oficial de mesmo
algoritmo, instância, `K` e seed. Microbenchmark de kernel é apenas diagnóstico.

A execução requer exclusividade da placa, preflight ocioso de 60 segundos e
monitoramento térmico contínuo. Interrupções de segurança preservam sessão e
telemetria e não publicam resultado parcial.

A renovação B11A-R, concluída depois da B11-E, propagou `social=2.0` às
configurações oficial e diagnóstica. A conformidade passou a vincular seu
resultado ao hash da configuração e ao conjunto de IDs. O roteiro vigente
contém 60 IDs únicos, com hash
`cc8d52559e5f16bce9718b04453166231d71a4885ea3126f443c7e33f957b61a`,
e a prontidão valida também os 60 pares CPU oficiais antes de declarar
`infrastructure_ready=true`.

### 29.1.1. Desfecho do estudo adicional de GPU

O estudo adicional foi **encerrado com limitação registrada**, na forma que o
critério de saída prevê. A infraestrutura ficou completa e verificada; o que não
se obteve foi aceleração relevante, e a razão é mecânica e mensurada.

**A limitação não é de corretude.** A conformidade foi aprovada com diferença
máxima de `3,33e-16` entre os caminhos CPU e GPU, contra a régua normativa de
`1e-12`, com igualdade de orçamento e de checkpoints e confirmação em CPU da
solução final. A implementação em GPU está correta e reproduz o caminho
normativo dentro da tolerância exigida.

**Medição do ACO.** Três cenários oficiais foram executados e validados em
02/09/2026, em `N=150`, `K=5` e orçamento de 150.000 avaliações, pareados com a
execução CPU oficial de mesma semente:

| seed | GPU (s) | CPU (s) | speedup | kernel (s) | transferências (s) | fração de dispositivo |
|---|---|---|---|---|---|---|
| 10 | 2.723,2 | 2.743,8 | 1,008 | 4,15 | 0,36 | 0,166 % |
| 11 | 2.698,1 | 2.704,1 | 1,002 | 3,98 | 0,35 | 0,161 % |
| 12 | 2.754,4 | 2.826,2 | 1,026 | 3,96 | 0,35 | 0,157 % |

O speedup fica em torno da unidade e a fração de dispositivo abaixo de 0,17 %:
das cerca de 45 minutos de cada execução, menos de 5 segundos ocorrem na placa.
É exatamente a leitura que a publicação conjunta de `speedup` e fração de
dispositivo existe para permitir.

**Causa.** O desenho híbrido delega à GPU apenas a avaliação em lote. O
perfilamento de uma geração de 40 formigas, em `N=150` e `K=5`, atribui **98,7 %
do tempo à construção das formigas no host** (730 ms), 1,2 % à avaliação (9 ms)
e 0,1 % à atualização de feromônio. A construção é sequencial por dependência:
cada uma das 150 posições depende do estado parcial anterior, somando cerca de
22 milhões de decisões por cenário. Pela lei de Amdahl, acelerar
indefinidamente a fração avaliável limita o speedup a `1/0,987 ≈ 1,013×`. O
valor medido, entre 1,002 e 1,026, é portanto o resultado estrutural do desenho
híbrido, e não deficiência da implementação nem do dispositivo.

**Dimensionamento da carga.** Cada decisão da construção opera sobre 40 formigas
por no máximo 5 alternativas, isto é 200 elementos. Uma sondagem exploratória de
viabilidade — diagnóstica, fora da campanha oficial — mediu que, mesmo
vetorizando a construção entre formigas, o tempo por geração é de 41 ms em NumPy
sobre CPU contra 438 ms em CuPy na mesma máquina, e que a paridade entre os dois
só ocorre por volta de 1.200 formigas simultâneas, trinta vezes o `n_ants`
congelado. O custo em GPU é dominado por lançamento de kernel, e não por
aritmética. A conclusão é que a granularidade do ACO com estes parâmetros é
pequena demais para a placa.

**A conclusão acima não se estende ao PSO.** No PSO a avaliação responde por
cerca de 46 % do custo, contra 1,2 % no ACO — e a medição do recorte, na seção
29.1.2, confirma que a diferença de desenho produz resultado oposto ao do ACO.

### 29.1.2. Medição do PSO em GPU

O recorte de 30 cenários PSO do roteiro oficial (ranks 31 a 60, seeds 10 a 39)
foi executado e validado em 04/09/2026, em `N=150`, `K=5` e orçamento de
150.000 avaliações, pareado com a execução CPU oficial de mesma semente. Os 30
cenários concluíram sem falha em 55 minutos de execução sequencial.

| | GPU (s) | CPU (s) | speedup | fração de dispositivo |
|---|---|---|---|---|
| média | 40,92 | 73,98 | 1,814 | 10,27 % |
| desvio-padrão amostral | — | — | 0,078 | 0,90 p.p. |
| mínimo | 33,15 | 65,45 | 1,520 | 7,68 % |
| máximo | 53,00 | 81,12 | 1,974 | 12,54 % |

**Ao contrário do ACO, o PSO produz aceleração real e mensurável.** O speedup
médio de `1,814×` é consistente com a fração de custo já estimada para a
avaliação no PSO: se ela responde por 46 % do tempo total, o teto de Amdahl
para o desenho híbrido, com o tempo de avaliação tendendo a zero, é
`1/(1-0,46) ≈ 1,852×`. A média medida fica a `98 %` desse teto, e a distância
restante é explicada pela própria fração de dispositivo observada, `10,27 %`:
o caminho GPU ainda gasta parte não desprezível do seu tempo em lançamento de
kernel (`3,825 s` em média) e transferências (`0,345 s` em média), então o
tempo de avaliação não tende a zero na prática. A diferença com o ACO não é de
implementação, é de forma: o PSO delega à GPU uma fatia do custo grande o
bastante para que a aceleração dessa fatia apareça no tempo total, enquanto no
ACO a fatia delegável é `1,2 %`, pequena demais para qualquer ganho na
avaliação se propagar ao tempo da execução.

Os 30 documentos individuais ficam em `results/gpu/raw/`, fora do Git; o
cálculo por cenário compara `runtime_seconds` de cada um com a linha CPU de
mesmo algoritmo, instância, `K` e seed em `results/tables/benchmark_runs.parquet`,
e a fração de dispositivo vem de `diagnostics.gpu_timing` em cada documento.

**Estado ao encerrar.** A infraestrutura permanece íntegra e verificável:
conformidade aprovada, roteiro de 60 identificadores, manifesto de prontidão
regenerado sobre o código vigente e `readiness` declarando
`infrastructure_ready` e `execution_ready` verdadeiros. A campanha GPU segue
**parcial por desenho**: 30 dos 60 resultados oficiais, apenas o recorte PSO.
Os 30 cenários ACO não foram reexecutados nesta leva — fazê-lo reconfirmaria,
ao custo de ~23 h, um resultado já medido e explicado na seção 29.1.1.
`consolidate` recusa sobre esse estado, corretamente, por exigir os 60 e o
pareamento 1:1. O encerramento
continua sendo decisão de escopo, e não impedimento técnico: a campanha
completa continua executável a qualquer momento.

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

---

## 33. Melhor média de custo

**Observação.** Em `benchmark_summary.parquet`, a média de `cost_mean` sobre as
18 combinações instância×K é `0,156831` para a Busca Tabu, `0,208578` para o
ACO e `0,286118` para o PSO. Comparando diretamente `cost_mean` combinação a
combinação, a Busca Tabu apresenta o menor valor em 17 das 18 combinações. A
única exceção é `artesp_rmsp_150, k=5`, em que o ACO tem `cost_mean=0,156884`
contra `0,161771` da Busca Tabu — uma diferença absoluta de `0,004887`, cerca
de 3% do valor de custo da Busca Tabu nessa combinação.

**Inferência.** Considerando a média amostral sobre as 30 seeds de cada
combinação, a Busca Tabu produz, de forma consistente, as soluções de menor
custo médio entre os três algoritmos, com uma única inversão marginal em favor
do ACO, restrita a uma combinação específica de tamanho grande e `K=5`.

**Limitação.** A comparação acima é de médias amostrais; não estabelece, por si
só, significância estatística — essa questão é tratada separadamente nas seções
38 e 39. A contagem "17 de 18" trata todas as combinações instância×K como
igualmente relevantes, o que não reflete necessariamente sua importância
prática relativa. Tampouco considera o custo computacional associado (seção
36) nem o desempenho contra a heurística gulosa (seção 40).

---

## 34. Menor variabilidade

**Observação.** Em `benchmark_summary.parquet`, a média de `cost_std` sobre as
18 combinações é `0,012639` para a Busca Tabu, `0,022381` para o ACO e
`0,028481` para o PSO. A Busca Tabu tem o menor `cost_std` em 11 das 18
combinações, o ACO em 4 e o PSO em 3. Em três combinações de `artesp_rmsp_20`
(`k=6`, `k=7`, `k=8`), o `cost_std` da Busca Tabu é, respectivamente,
`7,67e-05`, `0,0` e `2,82e-17` — praticamente nulo, sinal de convergência
determinística das 30 seeds ao mesmo ponto.

**Inferência.** Em média, a Busca Tabu apresenta a menor dispersão de custo
entre seeds, embora sem vencer em todas as combinações. A dispersão
praticamente nula observada na instância pequena é compatível com um espaço de
busca suficientemente reduzido para que a busca local convirja de forma quase
determinística ao mesmo ótimo local a partir de sementes diferentes.

**Limitação.** Baixa variabilidade não é mérito isolado: precisa ser lida em
conjunto com o nível médio de custo (seção 33), pois convergir de forma quase
determinística a um ótimo local ruim também produziria `cost_std` baixo. Não
foi aplicado teste formal de igualdade de variâncias entre algoritmos; a
comparação acima é descritiva.

---

## 35. Convergência em função do orçamento

**Observação.** As curvas de convergência para `K=5` nas três classes de
tamanho estão em `results/figures/benchmark_convergence_20.{png,pdf}`,
`benchmark_convergence_60.{png,pdf}` e `benchmark_convergence_150.{png,pdf}`,
com a mediana do melhor custo e a faixa interquartil sobre os 100 checkpoints
(seção 20). A partir dos dados subjacentes em `benchmark_checkpoints.parquet`,
o primeiro checkpoint em que a mediana do custo corrente fica a até 5% do
valor mediano final do próprio algoritmo ocorre, em percentual do orçamento
consumido:

| instância | ACO | Busca Tabu | PSO |
|---|---:|---:|---:|
| `artesp_rmsp_20` | 2% | 9% | 74% |
| `artesp_rmsp_60` | 8% | 22% | 49% |
| `artesp_rmsp_150` | 4% | 7% | 35% |

**Inferência.** Nas três classes de tamanho, ACO e Busca Tabu se aproximam de
seu próprio patamar final de custo consumindo uma fração pequena do orçamento
(no máximo 22%), enquanto o PSO continua melhorando por uma fração muito maior
do orçamento, entre 35% e 74%.

**Limitação.** "Convergir rápido" aqui é relativo ao patamar final do próprio
algoritmo, não a um ótimo comum entre os três. Um algoritmo pode convergir
rapidamente para um patamar pior, como o ACO faz na maioria das combinações
(seção 33); convergência rápida não implica solução final melhor. O critério
de "5% do valor final" é arbitrário e não testado quanto à sensibilidade a
outros limiares.

---

## 36. Tempo computacional

**Observação.** Em `benchmark_summary.parquet`, a média de `runtime_mean`
sobre as 18 combinações é `20,05 s` para a Busca Tabu, `30,89 s` para o PSO e
`1.095,93 s` para o ACO. A Busca Tabu tem o menor `runtime_mean` em 16 das 18
combinações; o PSO vence nas duas restantes
(`artesp_rmsp_20, k=7`: `2,1838 s` contra `2,1909 s`, margem de `0,007 s`;
`artesp_rmsp_20, k=8`: `2,0066 s` contra `2,1923 s`, margem de `0,186 s`). Em
`artesp_rmsp_150, k=5`, por exemplo, `runtime_mean` é `2.765,72 s` no ACO
contra `73,98 s` no PSO e `48,73 s` na Busca Tabu.

**Inferência.** A Busca Tabu tem, na quase totalidade das combinações, o menor
tempo computacional entre os três algoritmos; o PSO só a supera por margem
mínima em duas combinações de instância pequena. O ACO é sistematicamente o
mais lento, entre cerca de ×20 e ×61 mais lento que a Busca Tabu conforme a
combinação (razão `runtime_mean` ACO/Busca Tabu), o que é consistente com o
perfilamento da seção 29.1.1, em que a construção sequencial das formigas
domina o tempo de execução.

**Limitação.** O tempo medido é de parede, com 1 thread por execução, sob o
protocolo das seções 23-25; não é uma medida de complexidade assintótica nem
inclui o custo do tuning (seção 16). A comparação não pondera tempo contra
qualidade de solução de forma conjunta — essa leitura combinada aparece apenas
qualitativamente na seção 44.

---

## 37. Escalabilidade de N=20 a N=150

**Observação.** Para `K=5`, caso representativo da análise de escalabilidade
(seção 21), as figuras `results/figures/benchmark_scalability_time.{png,pdf}`
e `benchmark_scalability_quality.{png,pdf}` mostram, a partir de
`benchmark_summary.parquet`:

| algoritmo | tempo N=20 (s) | tempo N=150 (s) | fator | custo N=20 | custo N=60 | custo N=150 | variação N=20→150 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ACO | 49,79 | 2.765,72 | ×55,55 | 0,2219 | 0,1582 | 0,1569 | −29,31% |
| PSO | 3,04 | 73,98 | ×24,36 | 0,1882 | 0,2685 | 0,3357 | +78,37% |
| Busca Tabu | 2,18 | 48,73 | ×22,37 | 0,1420 | 0,1281 | 0,1618 | +13,93% |

**Inferência.** O tempo cresce em todos os algoritmos de N=20 para N=150, mas
de forma muito mais acentuada no ACO (fator ×55,55) do que no PSO (×24,36) e na
Busca Tabu (×22,37). O custo médio final, olhando apenas os dois extremos
(N=20 e N=150), não cresce da mesma forma para os três algoritmos: o ACO
melhora (custo menor em N=150 que em N=20) e o faz de forma monótona, com
N=60 entre os dois (`0,1582`); o PSO piora de forma também monótona, com
N=60 igualmente entre os extremos (`0,2685`); já a Busca Tabu piora do
extremo inicial ao final (+13,93%), mas não o faz de forma monótona — o custo
cai em N=60 (`0,1281`, abaixo tanto de N=20 quanto de N=150) antes de subir
para N=150.

**Limitação.** Essa leitura usa apenas `K=5`, por ser o corte de referência da
seção 21; não foi verificado se o mesmo padrão se repete nos demais valores de
`K`. A redução de custo do ACO em instâncias maiores não implica que o ACO seja
preferível em N=150 de forma geral: essa combinação específica
(`artesp_rmsp_150, k=5`) é justamente a única, entre as 18 combinações do
benchmark, em que o ACO (`0,156884`) tem custo médio menor que a Busca Tabu
(`0,161771`) — exceção já registrada na seção 33 — e mesmo assim o tempo de
execução do ACO ali é ordens de grandeza maior que o da Busca Tabu (seção 36).
Não há, nestes dados, explicação causal para o porquê de o custo do ACO cair
com o tamanho da instância.

---

## 38. Significância estatística

**Observação.** Em `benchmark_statistical_tests.parquet`, o teste de Friedman
rejeitou `H0` (`α=0,05`) em 18 das 18 combinações instância×K (`rejects_h0`
verdadeiro em todas as linhas). A estatística de Friedman varia de `30,076` a
`60,0`, e o valor-p varia de `9,358e-14` a `2,945e-07` — o maior valor-p ocorre
em `artesp_rmsp_20, k=3`. Nas comparações par a par de Wilcoxon com correção de
Holm, PSO×Busca Tabu e PSO×ACO são significativas (`p_holm<0,05`) em 18 das 18
combinações (maior `p_holm`: `4,218e-05` e `2,630e-05`, respectivamente). Já a
comparação Busca Tabu×ACO não é significativa (`p_holm≥0,05`) em 5 das 18
combinações, todas em `artesp_rmsp_150`: `k=4` (`p_holm=0,7766`), `k=5`
(`0,5425`), `k=6` (`0,9677`), `k=7` (`0,5291`) e `k=8` (`0,1981`). Na mesma
instância, `k=3` permanece significativa (`p_holm=0,0248`).

**Inferência.** Existe diferença global detectável entre os três algoritmos em
todas as 18 combinações testadas. Entretanto, a diferença específica entre
Busca Tabu e ACO não é individualmente significativa em cinco das seis
combinações de `K` na instância grande — ou seja, a rejeição global de `H0` não
implica que todo par de algoritmos difira em todo cenário.

**Limitação.** A rejeição de `H0` no teste de Friedman não quantifica magnitude
(ver seção 39). O padrão de não significância concentrado em
`artesp_rmsp_150` entre Busca Tabu e ACO justamente na instância em que a
seção 33 registrou a única inversão de ranking não deve ser interpretado além
do que os dados mostram: ele indica que a diferença de custo entre os dois
métodos, nessa instância, é pequena o suficiente para não ser detectada com 30
seeds, mas não permite concluir equivalência.

---

## 39. Magnitude das diferenças

**Observação.** Em `benchmark_statistical_tests.parquet`, considerando as 18
combinações instância×K que rejeitaram `H0` no teste de Friedman (seção 38), a
`rank_biserial correlation` das comparações par a par tem magnitude absoluta
entre `0,9365` e `1,0` (média `0,9965`) para PSO×Busca Tabu, e entre `0,8323`
e `1,0` (média `0,9752`) para PSO×ACO — em ambos os casos, efeito de
magnitude próxima da máxima teórica em todas as 18 combinações. Já para Busca
Tabu×ACO, a magnitude absoluta varia entre `0,0108` e `1,0` (média `0,6782`),
com dispersão muito maior. As cinco combinações sem significância pareada
(`p_holm≥0,05`, seção 38) coincidem exatamente com as de menor magnitude:
`artesp_rmsp_150, k=6` tem `rank_biserial=-0,0108` (`p_holm=0,9677`), `k=4` tem
`-0,0624`, `k=7` tem `-0,1355`, `k=5` tem `0,1312` e `k=8` tem `-0,2731`.

**Inferência.** A diferença entre PSO e os outros dois algoritmos é de
magnitude prática grande e consistente em todo o benchmark. Já a diferença
entre Busca Tabu e ACO tem magnitude que varia por combinação, sendo grande na
maior parte das 18 combinações, mas pequena justamente nas cinco combinações
de `artesp_rmsp_150` (`k=4` a `k=8`) em que a seção 38 não encontrou
significância individual — um caso de coerência entre valor-p e tamanho de
efeito, e não uma contradição entre os dois.

**Limitação.** O resultado global do teste de Friedman (seção 38) não deve ser
superextrapolado para "todo par de algoritmos difere em todo cenário": para
Busca Tabu×ACO, especificamente em `artesp_rmsp_150` com `k` de 4 a 8, a
diferença de custo é pequena tanto em termos de significância quanto de
magnitude de efeito. Isso não significa que os dois algoritmos sejam
equivalentes nessas combinações, apenas que a diferença, se existir, é pequena
demais para ser separada da variação amostral com o desenho de 30 seeds usado
aqui.

---

## 40. Melhoria sobre a heurística gulosa

**Observação.** Em `benchmark_vs_greedy.parquet`, a média de
`improvement_percent` sobre as 18 combinações instância×K é `+18,75%`
(desvio-padrão `25,59` p.p.) para a Busca Tabu, `-2,17%` (`23,82` p.p.) para o
ACO e `-55,65%` (`70,60` p.p.) para o PSO. A Busca Tabu melhora sobre a gulosa
em 12 das 18 combinações, o ACO em 6 e o PSO em 5. O padrão depende
fortemente do tamanho da instância: em `artesp_rmsp_150`,
`improvement_percent` é negativo nas 6 combinações de `K` de cada um dos três
algoritmos, ou seja, em 18 combinações algoritmo×K (3 algoritmos × 6 valores
de `K`) — **nenhum dos três algoritmos supera a heurística gulosa em nenhum
valor de `K` na instância grande** (pior caso: PSO em `k=3`, `-238,96%`). Já
em `artesp_rmsp_20` e `artesp_rmsp_60`, a Busca Tabu melhora sobre a gulosa
nas 12 combinações de instância×K correspondentes (6 valores de `K` em cada
uma das duas instâncias), entre `+13,20%` e `+52,27%`. O custo em tempo dessa
comparação é alto: a média de `time_ratio_vs_greedy` é `×291,28` para a Busca
Tabu, `×443,64` para o PSO e `×12.293,76` para o ACO — a heurística gulosa
roda em frações de segundo em todas as combinações.

**Inferência.** A melhoria das metaheurísticas sobre a heurística gulosa não é
uniforme: existe nas instâncias pequena e média, de forma consistente para a
Busca Tabu, mas desaparece por completo na instância grande, onde a gulosa
supera as três metaheurísticas em todos os valores de `K` testados, ao custo
de centenas a milhares de vezes mais tempo de execução para as
metaheurísticas.

**Limitação.** Os dados não permitem explicar causalmente por que a vantagem
se inverte em `artesp_rmsp_150`. Hipóteses possíveis — orçamento de avaliações
insuficiente relativamente ao tamanho do espaço de busca, ou a heurística
gulosa sendo particularmente bem adequada à estrutura dessa instância — não
foram testadas aqui e não devem ser apresentadas como conclusão. O achado deve
ser lido como um resultado robusto (é unânime nas 18 combinações da instância
grande) mas não explicado pelos artefatos disponíveis nesta tarefa.

---

## 41. K=3 vs K=8

**Observação.** Em `benchmark_by_k.parquet`, comparando as médias sobre as
três instâncias entre `K=3` e `K=8`:

| algoritmo | `total_cost` (k=3→k=8) | `cv_demand` (k=3→k=8) | `cv_production` (k=3→k=8) | `c_territorial` (k=3→k=8) | `c_affinity` (k=3→k=8) |
|---|---|---|---|---|---|
| ACO | 0,0712→0,3413 | 0,0413→0,7418 | 0,0899→0,7271 | 0,0653→0,2341 | 0,1008→0,3175 |
| PSO | 0,1490→0,4174 | 0,0588→0,3088 | 0,0417→0,2665 | 0,2272→0,5860 | 0,2785→0,6933 |
| Busca Tabu | 0,0628→0,2404 | 0,0447→0,3178 | 0,0556→0,2513 | 0,0643→0,2510 | 0,0951→0,3474 |

Todos os cinco componentes crescem, para os três algoritmos, ao passar de
`K=3` para `K=8`.

**Inferência.** Aumentar o número de lotes de 3 para 8 piora, em média, todos
os componentes medidos — custo total, desequilíbrio de demanda e de PU·km, e
incoerência territorial e funcional — para os três algoritmos. O ACO é o mais
sensível ao aumento de `K` em `cv_demand` e `cv_production` (razão k=8/k=3 de
cerca de dezoito e oito vezes, respectivamente), enquanto a Busca Tabu tem o
menor crescimento absoluto de `total_cost` entre os três (`+0,1776`, contra
`+0,2701` no ACO e `+0,2683` no PSO); em termos de razão k=8/k=3, porém, é o
PSO que cresce menos (×2,80, contra ×3,83 na Busca Tabu e ×4,79 no ACO) — as
duas leituras (absoluta e relativa) não apontam para o mesmo algoritmo.

**Limitação.** A tabela agrega as três instâncias; o comportamento por
instância individual não é detalhado aqui. O crescimento de todos os
componentes com `K` é um resultado observacional sobre a formulação usada, não
uma afirmação de que `K` pequeno é preferível em termos de decisão
institucional — a seção 3 já registra que o estudo não busca identificar um
`K` ótimo único, e a comparação de compromissos é aprofundada na seção 42.

---

## 42. Trade-off equilíbrio×coerência

**Síntese textual sobre `benchmark_by_k.parquet`, sem novo artefato.**
Estendendo a seção 41 para os seis valores de `K`, o crescimento de
`total_cost`, `cv_demand`, `cv_production`, `c_territorial` e `c_affinity` com
`K` é monótono, ou quase monótono, para os três algoritmos: a única exceção
identificada é a Busca Tabu em `cv_production`, que cai de `0,0556` em `k=3`
para `0,0306` em `k=4`, antes de voltar a crescer a partir de `k=5`
(`0,0854`, `0,1609`, `0,2157`, `0,2513`).

Não há, nestes dados, nenhum valor de `K` que reduza simultaneamente todos os
cinco componentes em relação a `K` menores — aumentar o número de lotes é,
para os três algoritmos, consistentemente pior tanto no equilíbrio de demanda
e de PU·km (`cv_demand`, `cv_production`) quanto na coerência territorial e
funcional (`c_territorial`, `c_affinity`), e também no custo total agregado.
Isso é compatível com a formulação da seção 3, que declaradamente não penaliza
o número de lotes: dividir o problema em mais lotes menores tende a aumentar a
variabilidade relativa entre lotes e a fragmentar territórios e afinidades
funcionais que, com menos lotes, ficam mais concentrados.

Não há, portanto, evidência nestes dados de um "ponto de equilíbrio" em que
mais lotes melhorem coerência territorial/funcional às custas de equilíbrio, ou
vice-versa — na faixa `K∈{3,...,8}` testada, as duas famílias de métrica
pioram juntas. Isso não permite concluir que essa relação se mantenha fora da
faixa testada, nem que um valor de `K` maior que 8 ou menor que 3 produziria
comportamento diferente; a seção 22 já registra que o relatório não deve
declarar automaticamente um `K` como ótimo, e os dados aqui reforçam essa
cautela, sem contradizê-la.

---

## 43. Sensibilidade a hiperparâmetros

**Observação.** Em `results/tables/tuning_parameter_effects.parquet` (artefato
já existente, reaproveitado sem reexecução), todas as 23 linhas trazem
`interpretation="descriptive_noncausal"`. A diferença entre níveis de
`mean_of_mean_cost` por parâmetro é: no ACO, `alpha` (`0,169483` em nível 1,0
contra `0,303648` em nível 2,0, diferença `0,1342`) é muito mais influente que
`beta` (`0,0434`), `n_ants` (`0,0237`) e `rho` (`0,0170`). No PSO, todos os
quatro parâmetros têm diferença pequena e semelhante entre si (`0,0087` a
`0,0158`: `n_particles`, `cognitive`, `social`, `inertia`, nessa ordem
crescente). Na Busca Tabu, as diferenças são ainda menores (`0,0027` a
`0,0153`), e `tabu_tenure`, com três níveis (5, 10, 20), tem seu menor
`mean_of_mean_cost` no nível intermediário (`0,137703` em 10, contra
`0,140539` em 5 e `0,138944` em 20) — um padrão não monótono.

**Inferência.** Dentro da grade de tuning testada (seções 12 a 15), o parâmetro
`alpha` do ACO tem, isoladamente, o maior efeito descritivo sobre o custo
médio entre todos os parâmetros de todos os três algoritmos — sua diferença
entre níveis (`0,1342`) é cerca de três vezes a do segundo parâmetro mais
influente (`beta` do ACO, `0,0434`) e entre cerca de nove e cinquenta vezes a
diferença de cada parâmetro individual de PSO e Busca Tabu (que variam entre
`0,0027` e `0,0158`). PSO e Busca Tabu aparentam ser comparativamente menos
sensíveis, dentro da grade testada, aos parâmetros variados.

**Limitação.** O próprio artefato rotula a interpretação como
"descriptive_noncausal": os valores comparam médias marginais por nível dentro
da grade de tuning (seção 12), não isolam o efeito de um parâmetro mantendo os
demais fixos em um desenho fatorial completo, e não sustentam inferência
causal sobre qual parâmetro "causa" mais variação de custo. A grade de tuning
foi definida antes do congelamento experimental (seção 30) e não foi
re-executada para esta tarefa.

---

## 44. Método mais adequado e aceleração por GPU

**Síntese textual, referenciando as seções 29.1.1/29.1.2 (GPU) sem
recalcular.** Reunindo as seções 33-42: a Busca Tabu tem, na maior parte das
combinações testadas, o menor custo médio (seção 33), a menor variabilidade
(seção 34), o menor tempo computacional (seção 36) e a maior melhoria sobre a
heurística gulosa (seção 40) entre os três algoritmos. Essa vantagem, porém,
não é universal: na instância grande, a diferença Busca Tabu×ACO deixa de ser
estatisticamente significativa em cinco dos seis valores de `K` (seções 38 e
39), e nenhum dos três algoritmos supera a heurística gulosa em nenhuma
combinação de `artesp_rmsp_150` (seção 40). Não há, portanto, um único método
uniformemente superior em todo o desenho experimental: a Busca Tabu é a
escolha mais consistente dentro da faixa de instâncias e `K` testada, com a
ressalva de que, na instância grande, sua vantagem sobre o ACO some
estatisticamente e sua vantagem sobre a heurística gulosa se inverte.

Quanto à aceleração por GPU (pergunta 11), o resultado já registrado nas
seções 29.1.1 e 29.1.2 não é uniforme entre algoritmos: o PSO obteve speedup
médio real de `1,814×` sobre CPU, compatível com a fração de seu custo
delegável à GPU (seção 29.1.2); o ACO não obteve aceleração relevante
(speedup entre `1,002×` e `1,026×`), porque a construção sequencial das
formigas, não paralelizável no desenho testado, domina 98,7% do tempo de
execução (seção 29.1.1). A Busca Tabu não foi objeto do estudo adicional de
GPU.

**Limitação.** A síntese acima integra resultados de tarefas e escopos
diferentes — o benchmark principal em CPU (seções 33-42) e o estudo adicional
de GPU, parcial por desenho e restrito a 30 dos 60 cenários planejados,
cobrindo apenas o recorte PSO (seção 29.1.2). Não há medição de GPU para a
Busca Tabu nestes dados, o que impede qualquer afirmação sobre sua
aceleração por GPU. A recomendação de "método mais adequado" acima é uma
leitura qualitativa das seções 33-42 deste mesmo documento, não um critério
estatístico único e formal de escolha de algoritmo; ela não incorpora custo de
implementação, maturidade de cada método fora deste experimento, nem
requisitos operacionais específicos de uma futura adoção prática.
