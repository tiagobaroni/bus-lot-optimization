# Formulação do Problema — Formação de Lotes Operacionais de Linhas de Ônibus

## 1. Objetivo

O problema consiste em agrupar sentidos/variantes operacionais de linhas de ônibus em lotes operacionais, buscando simultaneamente:

1. equilíbrio de demanda entre os lotes;
2. equilíbrio de produção operacional entre os lotes;
3. coerência territorial;
4. afinidade funcional entre as linhas agrupadas.

Cada sentido/variante é tratado como uma unidade indivisível e deve pertencer integralmente a exatamente um lote.

A primeira formulação considera um número fixo de lotes `K`. O problema será resolvido separadamente para:

\[
K \in \{3,4,5,6,7,8\}.
\]

Não haverá penalidade explícita associada ao número de lotes no baseline. A comparação entre diferentes valores de `K` será feita a partir da qualidade das melhores partições encontradas e da decomposição dos componentes da função objetivo.

---

## 2. Unidade de decisão

A unidade elementar de decisão é um **sentido/variante operacional de linha de ônibus**.

Seja o conjunto de unidades:

\[
\mathcal{L}=\{1,2,\ldots,N\}.
\]

Cada unidade \(i\in\mathcal{L}\) deve ser atribuída a um e somente um lote:

\[
x_i \in \{1,\ldots,K\}.
\]

A solução pode ser representada por um vetor inteiro:

\[
\mathbf{x}=(x_1,x_2,\ldots,x_N).
\]

Exemplo:

```text
[1, 1, 3, 2, 2, 1, 3]
```

indica a alocação de sete sentidos/variantes a três lotes.

Cada sentido/variante é indivisível: o modelo não redesenha, corta ou distribui uma mesma variante entre lotes diferentes.

---

## 3. Dados mínimos por sentido/variante

Sempre que possível, cada unidade \(i\) deverá possuir:

- identificação da linha;
- identificação do sentido/variante;
- sequência ordenada de pontos de parada;
- geometria espacial do itinerário;
- passageiros por dia;
- capacidade ofertada;
- produção em PU·km;
- terminais atendidos;
- informações necessárias para identificar integração funcional com outras linhas.

### 3.1. Demanda

A medida principal de demanda será:

\[
D_i=\text{passageiros/dia da unidade }i.
\]

Sempre que possível, os valores serão utilizados diretamente por sentido/variante.

### 3.2. Produção operacional

A principal medida de produção será:

\[
P_i=\text{PU·km da unidade }i.
\]

O PU·km representa capacidade ofertada multiplicada pela distância produzida e será usado como principal critério de equilíbrio operacional.

A quantidade de **assentos ofertados por dia** será mantida como indicador auxiliar, mas não será componente principal da função objetivo no baseline.

---

## 4. Restrições estruturais

Para um valor fixo de `K`:

1. cada unidade deve pertencer a exatamente um lote;
2. todos os `K` lotes devem conter pelo menos uma unidade.

Logo:

\[
x_i\in\{1,\ldots,K\},\quad \forall i,
\]

e

\[
|\{i:x_i=k\}| \geq 1,\quad \forall k\in\{1,\ldots,K\}.
\]

No baseline não serão impostos limites rígidos de:

- passageiros por lote;
- PU·km por lote;
- número de linhas por lote;
- frota;
- extensão.

O equilíbrio será induzido pela função objetivo.

Soluções com lotes vazios serão **reparadas antes da avaliação**.

---

## 5. Função objetivo

A função objetivo será composta por quatro critérios normalizados e com pesos iguais:

\[
C(\mathbf{x})=
\frac{1}{4}C_D+
\frac{1}{4}C_P+
\frac{1}{4}C_T+
\frac{1}{4}C_A.
\]

onde:

- \(C_D\): desequilíbrio de demanda;
- \(C_P\): desequilíbrio de produção em PU·km;
- \(C_T\): penalidade por separação de linhas territorialmente próximas;
- \(C_A\): penalidade por separação de linhas funcionalmente afins.

O problema consiste em:

\[
\min_{\mathbf{x}} C(\mathbf{x}).
\]

Os pesos iguais representam uma hipótese inicial de neutralidade entre os quatro pilares. Análises futuras poderão testar sensibilidade a outros pesos.

---

## 6. Equilíbrio de demanda

Para cada lote \(k\):

\[
D_k=\sum_{i:x_i=k}D_i.
\]

O desequilíbrio será medido pelo coeficiente de variação:

\[
CV_D=\frac{\sigma(D_1,\ldots,D_K)}
{\mu(D_1,\ldots,D_K)}.
\]

Para limitar o componente ao intervalo \([0,1)\), será aplicada a transformação:

\[
C_D=\frac{CV_D}{1+CV_D}.
\]

Valores menores indicam maior equilíbrio de passageiros/dia entre os lotes.

---

## 7. Equilíbrio de produção operacional

Para cada lote \(k\):

\[
P_k=\sum_{i:x_i=k}P_i.
\]

O desequilíbrio de produção também será medido por coeficiente de variação:

\[
CV_P=\frac{\sigma(P_1,\ldots,P_K)}
{\mu(P_1,\ldots,P_K)}.
\]

O componente normalizado será:

\[
C_P=\frac{CV_P}{1+CV_P}.
\]

Valores menores indicam maior equilíbrio de PU·km entre os lotes.

---

## 8. Coerência territorial

A coerência territorial será formulada como uma **penalidade por separação de pares de linhas espacialmente próximos ou sobrepostos**.

Define-se uma matriz:

\[
S_{ij}\in[0,1],
\]

onde valores maiores indicam maior sobreposição ou proximidade territorial entre as unidades \(i\) e \(j\).

### 8.1. Construção de \(S_{ij}\)

O baseline utilizará a **sobreposição de trechos/corredores normalizada pela extensão das duas linhas**.

A fórmula operacional exata poderá depender do formato final dos dados geoespaciais, mas deverá respeitar:

- \(S_{ij}=0\) para ausência de relação espacial relevante;
- \(S_{ij}=1\) para sobreposição espacial máxima segundo a métrica adotada;
- simetria: \(S_{ij}=S_{ji}\).

### 8.2. Penalidade territorial

A penalidade será:

\[
C_T=
\frac{
\sum_{i<j}
S_{ij}\,\mathbf{1}(x_i\neq x_j)
}{
\sum_{i<j}S_{ij}
}.
\]

Assim:

- \(C_T=0\): nenhuma relação espacial ponderada foi cortada;
- valores maiores: mais relações espaciais relevantes foram separadas entre lotes.

---

## 9. Afinidade funcional

A afinidade funcional será representada por uma matriz:

\[
W_{ij}\in[0,1].
\]

Ela combinará três componentes, com pesos iguais:

\[
W_{ij}=
\frac{1}{3}T_{ij}
+
\frac{1}{3}I_{ij}
+
\frac{1}{3}O_{ij}.
\]

onde:

- \(T_{ij}\): terminal compartilhado;
- \(I_{ij}\): integração funcional;
- \(O_{ij}\): similaridade de mercados origem-destino.

### 9.1. Terminal compartilhado

\[
T_{ij}=
\begin{cases}
1,&\text{se }i\text{ e }j\text{ compartilham ao menos um terminal}\\
0,&\text{caso contrário.}
\end{cases}
\]

### 9.2. Integração funcional

\[
I_{ij}=
\begin{cases}
1,&\text{se existir integração funcional relevante entre }i\text{ e }j\\
0,&\text{caso contrário.}
\end{cases}
\]

A definição empírica de "integração funcional relevante" deverá ser documentada quando os dados forem preparados.

### 9.3. Similaridade de mercados origem-destino

O componente \(O_{ij}\) será contínuo:

\[
0\leq O_{ij}\leq1.
\]

Ele representará a similaridade entre os conjuntos de demanda OD potencialmente atendidos por duas linhas.

#### Mercado OD potencialmente atendido

Para cada par OD \(r\), com demanda \(q_r\), considera-se que uma linha atende potencialmente esse par quando:

1. a origem estiver a até **400 m** de pelo menos uma parada da linha;
2. o destino estiver a até **400 m** de pelo menos uma parada da linha;
3. origem e destino aparecerem em ordem compatível com o sentido/variante do itinerário.

Para cada linha \(i\), define-se um vetor de atendimento:

\[
v_{ir}=
\begin{cases}
q_r,&\text{se }i\text{ atende potencialmente o par OD }r\\
0,&\text{caso contrário.}
\end{cases}
\]

#### Jaccard ponderado

O baseline utilizará o índice de Jaccard ponderado:

\[
O_{ij}=
\frac{
\sum_r \min(v_{ir},v_{jr})
}{
\sum_r \max(v_{ir},v_{jr})
}.
\]

Assim:

- \(O_{ij}=0\): as duas linhas praticamente não disputam ou compartilham os mesmos mercados OD;
- \(O_{ij}=1\): os mercados OD potencialmente atendidos são equivalentes segundo a medida adotada.

O raio de 400 m será tratado como hipótese metodológica do baseline e poderá ser objeto de análise de sensibilidade futura.

### 9.4. Penalidade de afinidade funcional

A mesma lógica usada no componente territorial será aplicada:

\[
C_A=
\frac{
\sum_{i<j}
W_{ij}\,\mathbf{1}(x_i\neq x_j)
}{
\sum_{i<j}W_{ij}
}.
\]

Valores menores indicam maior preservação das relações funcionais dentro dos mesmos lotes.

---

## 10. Reparo de lotes vazios

Como todos os `K` lotes devem estar ativos, uma solução com lote vazio será reparada antes da avaliação.

Estratégia proposta:

1. identificar cada lote vazio;
2. considerar unidades pertencentes a lotes com pelo menos duas unidades;
3. calcular o impacto de mover cada candidata para o lote vazio;
4. executar o movimento que provoque o menor aumento estimado na função objetivo;
5. repetir até que todos os lotes estejam ativos.

A escolha aleatória será evitada no reparo baseline para melhorar a estabilidade e a reprodutibilidade.

---

## 11. Simetria de rótulos e canonicalização

Os identificadores dos lotes não possuem significado intrínseco.

As soluções:

```text
[1, 1, 2, 2, 3, 3]
```

e

```text
[3, 3, 1, 1, 2, 2]
```

representam a mesma partição.

Será utilizada uma função de **canonicalização de rótulos**, renumerando os lotes pela ordem de primeira ocorrência.

Exemplo:

```text
[3, 3, 1, 1, 2, 2]
```

torna-se:

```text
[1, 1, 2, 2, 3, 3]
```

A canonicalização será usada para:

- comparação de soluções;
- testes;
- armazenamento;
- cache, se implementado.

---

## 12. Variação do número de lotes

O baseline não otimizará `K` diretamente dentro das metaheurísticas.

Cada problema será resolvido separadamente para:

\[
K=3,4,5,6,7,8.
\]

Não haverá termo \(\lambda K\) ou outra penalidade explícita por quantidade de lotes.

Para cada `K`, serão registrados:

- custo total \(C\);
- \(CV_D\);
- \(CV_P\);
- \(C_T\);
- \(C_A\).

A avaliação do efeito de `K` será feita pela análise conjunta dessas métricas, e não apenas pelo custo agregado.

Caso o custo total apresente comportamento monotônico em função de `K`, esse resultado será interpretado como evidência de que a formulação pode necessitar, em versão futura, de:

- custo estrutural de fragmentação;
- restrições adicionais;
- critérios econômicos relacionados à quantidade de lotes;
- ou otimização endógena de `K`.

---

## 13. Heurística gulosa de referência

Além de PSO, Busca Tabu e ACO, será implementada uma heurística gulosa determinística como baseline.

### 13.1. Ordem de processamento

As unidades serão ordenadas em ordem decrescente de PU·km.

### 13.2. Construção

Cada unidade será atribuída ao lote que produzir o menor aumento marginal da função objetivo.

A construção deverá assegurar, diretamente ou por reparo, que todos os `K` lotes sejam utilizados.

### 13.3. Desempate

Se duas alternativas produzirem o mesmo aumento marginal de custo, a unidade será atribuída ao lote com **menor PU·km acumulado** naquele momento.

A heurística será determinística para fornecer uma referência estável às execuções estocásticas das metaheurísticas.

---

## 14. Hipóteses e limitações do baseline

A formulação inicial assume explicitamente:

1. **Unidade indivisível:** cada sentido/variante pertence integralmente a um único lote.
2. **K fixo por execução:** `K` é resolvido separadamente para valores de 3 a 8.
3. **Todos os lotes ativos:** não são permitidos lotes vazios após reparo.
4. **Sem limites rígidos de porte:** não há mínimo/máximo de passageiros, PU·km ou número de linhas.
5. **Pesos iguais:** os quatro componentes da função objetivo possuem peso \(1/4\).
6. **Demanda:** equilíbrio medido por passageiros/dia.
7. **Produção:** equilíbrio medido principalmente por PU·km.
8. **Assentos ofertados:** indicador auxiliar, não componente principal do baseline.
9. **Equilíbrio:** coeficiente de variação transformado por \(CV/(1+CV)\).
10. **Territorialidade:** baseada em sobreposição/proximidade de itinerários.
11. **Afinidade funcional:** média simples entre terminal compartilhado, integração funcional e similaridade OD.
12. **Terminal compartilhado:** variável binária.
13. **Integração funcional:** variável binária.
14. **Similaridade OD:** Jaccard ponderado entre mercados OD potencialmente atendidos.
15. **Raio de acesso:** 400 m entre origem/destino e pontos de parada.
16. **Sentido do itinerário:** a ordem das paradas deve ser respeitada na identificação de atendimento OD.
17. **Sem penalidade explícita por K:** a quantidade de lotes será analisada a posteriori.
18. **Reparo de inviabilidade:** lotes vazios serão preenchidos por estratégia de menor aumento de custo.
19. **Baseline externo:** heurística gulosa determinística em ordem decrescente de PU·km.

Essas hipóteses são decisões metodológicas do baseline e poderão ser revistas após os primeiros experimentos.

---

## 15. Pontos ainda a detalhar durante a implementação

A formulação conceitual está fechada, mas alguns detalhes operacionais dependem dos dados reais e deverão ser documentados antes dos experimentos principais:

1. fórmula geoespacial exata para \(S_{ij}\);
2. regra empírica para classificar uma integração funcional como relevante;
3. tratamento de linhas com dados incompletos por sentido/variante;
4. estratégia de desagregação quando passageiros/dia ou PU·km estiverem disponíveis apenas de forma agregada;
5. regras de consistência topológica e ordenação dos pontos de parada;
6. pré-processamento da matriz OD para avaliar atendimento potencial;
7. tratamento de pares OD sem atendimento por nenhuma linha;
8. definição exata do desvio padrão usado no coeficiente de variação, que deve ser consistente em todas as implementações.

---

## 16. Extensões futuras possíveis

Após a implementação e validação do baseline, poderão ser estudadas:

- pesos não uniformes na função objetivo;
- sensibilidade ao raio de acesso de 400 m;
- intensidade contínua de integração funcional;
- importância relativa de terminais;
- limites mínimos/máximos de porte;
- custos institucionais associados ao número de lotes;
- otimização endógena de `K`;
- restrições de conectividade territorial;
- inclusão de frota ou assentos ofertados na função objetivo;
- comparação com métodos exatos em instâncias pequenas;
- análise multiobjetivo em vez de soma ponderada.

---

## 17. Síntese

O problema baseline pode ser descrito como:

> Dado um conjunto de sentidos/variantes de linhas de ônibus, com demanda, produção, geometrias, pontos de parada e relações funcionais, particioná-lo em `K` lotes não vazios de modo a equilibrar passageiros/dia e PU·km e, ao mesmo tempo, minimizar a separação de linhas territorialmente próximas e funcionalmente afins.

A mesma formulação e a mesma função objetivo deverão ser utilizadas por PSO, Busca Tabu, ACO e pela heurística gulosa de referência.
