# Formulação do Problema - Formação de Lotes Operacionais de Linhas de Ônibus

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

A programação é interpretada segundo o funcionamento cadastral informado para
o sistema da ARTESP: um registro de programação é atualizado quando o serviço
sofre alteração, e a programação anterior continua válida enquanto não houver
nova alteração. Portanto, o campo `programacao_vigente_na_data` é apenas um
indicador de coincidência formal entre o período registrado e a data de
referência. O valor `False` não caracteriza serviço inativo e não constitui
critério de exclusão. Essa interpretação é corroborada, para o universo deste
projeto, pela existência de passageiros observados nas 894 unidades do pacote.

Consequentemente, `pu_km_day` será tratado como produção programada corrente. A
ausência de vigência formal na data de referência não será apresentada como
falha de cobertura nem como desalinhamento temporal da oferta.

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

O desvio padrão é populacional, com divisor \(K\) (`ddof=0`), pois os lotes
constituem a totalidade da partição avaliada e não uma amostra para inferência.

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

Também neste componente é usado o desvio padrão populacional (`ddof=0`).

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

O baseline utilizará o **coeficiente de sobreposição entre os buffers dos
itinerários**. Seja \(B_i\) o buffer de 200 m ao redor da geometria do itinerário
da unidade \(i\). Define-se:

\[
S_{ij}=
\frac{
\operatorname{área}(B_i\cap B_j)
}{
\min\!\left(\operatorname{área}(B_i),\operatorname{área}(B_j)\right)
}.
\]

Operacionalmente, a medida será calculada a partir de
`s_overlap_long.parquet`:

\[
S_{ij}=
\frac{
\texttt{intersection\_area\_m2}_{ij}
}{
\min\!\left(\texttt{area\_i\_m2}_{ij},\texttt{area\_j\_m2}_{ij}\right)
}.
\]

Pares ausentes da tabela esparsa recebem \(S_{ij}=0\). Essa definição garante:

- \(S_{ij}=0\) para ausência de relação espacial relevante;
- \(S_{ij}=1\) quando o buffer menor está integralmente contido no maior;
- simetria: \(S_{ij}=S_{ji}\).

O coeficiente foi preferido ao índice de Jaccard porque o Jaccard divide a
interseção pela união e pode atribuir valor baixo quando o corredor de uma linha
curta está contido no corredor de uma linha longa. A contenção é considerada
evidência territorial relevante para a formação dos lotes.

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

Como premissa operacional do projeto, considera-se que as linhas de transporte
público da RMSP possuem integração tarifária entre si. Portanto, no baseline, a
integração funcional relevante entre duas unidades é limitada pela viabilidade
espacial da transferência, e não pela existência de um acordo tarifário
específico entre as linhas.

\[
I_{ij}=
\begin{cases}
1,&\text{se existir ao menos uma oportunidade espacial de transferência entre }i\text{ e }j\\
0,&\text{caso contrário.}
\end{cases}
\]

Considera-se que existe uma oportunidade espacial de transferência quando ao
menos uma destas condições for satisfeita:

1. as unidades compartilham um terminal;
2. as unidades compartilham uma parada cadastrada;
3. existe ao menos um par de paradas distintas, uma de cada unidade, com
   distância de até 400 m.

Operacionalmente, a regra será calculada a partir de
`functional_links.parquet`:

\[
I_{ij}=\mathbf{1}\!\left(
\texttt{shared\_terminal\_count}_{ij}>0
\;\lor\;
\texttt{shared\_stop\_count}_{ij}>0
\;\lor\;
\texttt{nearby\_stop\_pair\_count}_{ij}>0
\right).
\]

Pares ausentes da tabela esparsa recebem \(I_{ij}=0\). O raio de 400 m é uma
hipótese metodológica do baseline e deverá ser mantido igual para todos os
algoritmos.

Essa variável representa uma **oportunidade física potencial de transferência**,
e não uma transferência efetivamente realizada. A bilhetagem disponível valida
somente o embarque e não possui identificador de cartão que permita encadear
pernas de uma mesma viagem. Portanto, não é possível observar diretamente a
quantidade de transferências entre cada par de linhas nem validar empiricamente
se as oportunidades espaciais identificadas são utilizadas pelos passageiros.

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

A matriz O-D utilizada não é integralmente observada. Aproximadamente 64,1% de
sua massa possui destino estimado por modelo gravitacional nos pares sem amostra
da pesquisa domiciliar. Portanto, \(O_{ij}\) representa similaridade entre
mercados potenciais construídos a partir de uma matriz que combina informação
observada e modelada. Ele não deve ser interpretado como similaridade baseada
exclusivamente em fluxos observados de passageiros.

Essa limitação é aceita no baseline porque a matriz preserva informação sobre a
estrutura dos mercados atendidos que seria perdida com a retirada completa do
componente. Uma análise de sensibilidade futura poderá recalcular a afinidade
funcional sem \(O_{ij}\), renormalizando os componentes restantes, para avaliar
quanto essa fonte modelada influencia as conclusões.

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

Se o denominador de \(C_T\) ou \(C_A\) for zero, o componente correspondente é
definido como zero, pois não existe relação positiva que possa ser cortada.

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

As unidades serão ordenadas em ordem decrescente de PU·km. Empates serão
resolvidos por `unit_id` em ordem lexicográfica crescente.

### 13.2. Construção

As primeiras `K` unidades abrirão os lotes de `0` a `K-1`, nessa ordem. Cada
unidade restante será atribuída ao lote que produzir o menor custo parcial.

O custo parcial será calculado no subproblema induzido pelas unidades já
processadas. O equilíbrio manterá os `K` lotes nos vetores de totais, enquanto
os componentes territoriais e funcionais considerarão somente relações cujas
duas unidades já tenham sido processadas.

A construção assegura diretamente que todos os `K` lotes sejam utilizados e não
requer reparo.

### 13.3. Desempate

Custos com diferença absoluta de até `1e-12` serão considerados empatados. Nesse
caso, a unidade será atribuída ao lote com **menor PU·km acumulado** antes da
inclusão. Persistindo o empate, será escolhido o menor rótulo de lote.

A heurística será determinística para fornecer uma referência estável às execuções estocásticas das metaheurísticas.

Para uma instância com `N` unidades, o baseline realizará exatamente
`K(N-K)` avaliações parciais. A última avaliação escolhida coincide com a função
objetivo completa e será reutilizada sem nova avaliação.

---

## 14. Busca Tabu

A Busca Tabu usa uma solução inicial aleatória e balanceada. Uma permutação das
unidades é distribuída ciclicamente entre os `K` lotes, garantindo viabilidade
sem reparo. Essa solução consome a primeira avaliação do orçamento.

O único movimento do baseline é `move(i, origem, destino)`. Movimentos que
esvaziariam a origem são proibidos. A cada iteração, todos os movimentos válidos
são enumerados e até `n_viz` deles são amostrados uniformemente, sem reposição.
Cada candidato amostrado consome uma avaliação.

Depois de aceitar `move(i, origem, destino)`, o retorno
`move(i, destino, origem)` permanece tabu pelos próximos `L_tabu` movimentos
aceitos. A aspiração libera essa reversão somente quando seu custo melhora o
melhor global por mais de `1e-12`.

O melhor movimento admissível da amostra é sempre aceito, inclusive quando
piora a solução corrente. Empates de custo usam a solução canônica e depois a
tupla do movimento. Os rótulos permanecem estáveis durante a trajetória para
preservar a semântica da memória tabu.

Depois de `n_stag` movimentos aceitos sem melhora global, a busca gera outra
solução aleatória balanceada, limpa a memória e preserva o incumbente. O mesmo
reinício ocorre quando toda a amostra está tabu sem aspiração.

O movimento `swap` não integra o baseline. Sua vizinhança acrescentaria até
`O(N²)` candidatos por iteração e consumiria o orçamento com menos atualizações
da trajetória. Ele somente será reconsiderado se os experimentos mostrarem
estagnação relevante.

---

## 15. Ant Colony Optimization

Cada formiga constrói uma sequência de crescimento restrito na ordem estável da
instância. A primeira unidade recebe lote `0`; as seguintes podem escolher um
lote aberto ou abrir somente o próximo rótulo. Quando as unidades restantes são
exatamente suficientes para os lotes ainda fechados, a abertura é obrigatória.
Assim, cada partição possui uma única representação canônica e termina viável
sem reparo.

Para cada escolha permitida, o ACO calcula o custo parcial dos mesmos quatro
componentes usados pelo guloso. Esses custos são convertidos em informação
heurística no intervalo `[1, 2]`:

```text
eta[i,k] = 1 + (C_max - C[i,k]) / (C_max - C_min)
```

Quando a amplitude dos custos não supera `1e-12`, todas as alternativas recebem
`eta = 1`. Esses cálculos orientam a construção, mas somente a solução completa
da formiga consome uma avaliação do orçamento.

A matriz densa `tau[i,k]` começa em `1.0`. As probabilidades são proporcionais a
`tau[i,k]^alpha * eta[i,k]^beta` e são calculadas em log para estabilidade.

Depois de uma geração completa, o feromônio evapora por `(1-rho)` e cada formiga
deposita `1-custo_total` em todas as suas atribuições. Uma geração interrompida
pelo orçamento preserva suas avaliações e o incumbente, mas não evapora nem
deposita feromônio parcialmente.

---

## 16. Particle Swarm Optimization com Random Keys

Cada partícula possui uma posição `float64` de dimensão `N` em `[0,1]`. A chave
da unidade `i` é decodificada por
`min(floor(K*x[i]), K-1)`. A inicialização parte de uma alocação aleatória
balanceada e sorteia as chaves dentro dos intervalos dos lotes, garantindo que
todos estejam ativos.

A velocidade segue a fórmula clássica com inércia e componentes cognitivo e
social, vetores aleatórios independentes e topologia global. As posições são
limitadas a `[0,1]`, as velocidades a `[-0.5,0.5]` e cada iteração usa um único
snapshot do melhor global.

Quando a decodificação esvazia lotes, o PSO usa o reparo comum e contabiliza
todas as avaliações provisórias. A solução reparada é projetada de volta ao
espaço contínuo preservando a fração interna de cada chave. Somente candidatos
com avaliação viável completa alteram a partícula e seus melhores.

---

## 17. Hipóteses e limitações do baseline

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
10. **Territorialidade:** coeficiente de sobreposição entre buffers de 200 m dos itinerários, normalizado pela menor área.
11. **Afinidade funcional:** média simples entre terminal compartilhado, integração funcional e similaridade OD.
12. **Terminal compartilhado:** variável binária.
13. **Integração funcional:** variável binária de oportunidade espacial, igual a 1 para terminal compartilhado, parada compartilhada ou par de paradas a até 400 m.
14. **Similaridade OD:** Jaccard ponderado entre mercados OD potencialmente atendidos.
15. **Raio de acesso:** 400 m entre origem/destino e pontos de parada.
16. **Sentido do itinerário:** a ordem das paradas deve ser respeitada na identificação de atendimento OD.
17. **Sem penalidade explícita por K:** a quantidade de lotes será analisada a posteriori.
18. **Reparo de inviabilidade:** lotes vazios serão preenchidos por estratégia de menor aumento de custo.
19. **Baseline externo:** heurística gulosa determinística em ordem decrescente de PU·km.

Essas hipóteses são decisões metodológicas do baseline e poderão ser revistas após os primeiros experimentos.

---

## 18. Decisões fechadas após a preparação dos dados

Os detalhes que dependiam dos dados reais foram resolvidos da seguinte forma:

1. unidades sem PU·km são excluídas antes da seleção das instâncias;
2. passageiros/dia já estão desagregados por linha e sentido, sem rateio;
3. a capacidade veicular é observada no nível da linha e herdada pelos sentidos,
   enquanto viagens programadas e extensão permanecem específicas da unidade;
4. quando existem variantes cadastrais para a mesma linha e sentido, usa-se a
   rota com início de operação mais recente, com desempate pelo maior ID;
5. as paradas são ordenadas pela sequência do itinerário, preservando o sentido
   para a identificação dos mercados O-D atendidos;
6. uma zona O-D é alcançável quando seu polígono intersecta o buffer de 400 m
   das paradas, e um par é servível quando a origem antecede o destino;
7. pares ausentes das tabelas esparsas recebem valor zero;
8. a integração funcional representa oportunidade espacial potencial, conforme
   a regra definida na Seção 9.2.

O núcleo implementado usa o desvio padrão populacional (`ddof=0`) de forma
idêntica para demanda e PU·km.

---

## 19. Extensões futuras possíveis

Após a implementação e validação do baseline, poderão ser estudadas:

- pesos não uniformes na função objetivo;
- sensibilidade ao raio de acesso de 400 m;
- sensibilidade da afinidade funcional à retirada do componente O-D modelado;
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

## 20. Síntese

O problema baseline pode ser descrito como:

> Dado um conjunto de sentidos/variantes de linhas de ônibus, com demanda, produção, geometrias, pontos de parada e relações funcionais, particioná-lo em `K` lotes não vazios de modo a equilibrar passageiros/dia e PU·km e, ao mesmo tempo, minimizar a separação de linhas territorialmente próximas e funcionalmente afins.

A mesma formulação e a mesma função objetivo deverão ser utilizadas por PSO, Busca Tabu, ACO e pela heurística gulosa de referência.
