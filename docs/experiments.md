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

### 12.2. Resultado do tuning oficial

A campanha oficial foi executada em 17/08/2026 no commit `dc91468`, com 16
workers, e completou as 440 execuções sem falhas. O intervalo entre o início da
primeira execução e o fim da última foi de aproximadamente 3 h 43 min. Foram
consolidadas 440 linhas de execução e 44.000 checkpoints.

| Algoritmo | Parâmetros selecionados | Custo médio | Desvio-padrão amostral | Segundo colocado | Diferença de média |
|---|---|---:|---:|---:|---:|
| Busca Tabu | `tabu_tenure=10`, `neighborhood_size=20`, `stagnation_limit=100` | 0,126415 | 0,013287 | 0,129629 | 0,003214 |
| ACO | `alpha=1.0`, `beta=2.0`, `rho=0.1`, `n_ants=40` | 0,146303 | 0,021000 | 0,151504 | 0,005201 |
| PSO | `n_particles=40`, `inertia=0.4`, `cognitive=2.0`, `social=1.5` | 0,274437 | 0,033236 | 0,287264 | 0,012826 |

A análise marginal descritiva sugere, dentro das grades avaliadas, menor custo
médio com `alpha=1.0` no ACO, `inertia=0.4` e `social=1.5` no PSO e
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
hiperparâmetros, instância, `K`, seed, orçamento, pesos e cache. Resultados
individuais são publicados atomicamente em JSON e somente um documento válido e
com hash esperado é considerado concluído.

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
Falha exclusivamente de recursos reduz os workers e exige repetição integral.

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
