"""Reproduz tabelas e figura complementares do relatório, sem novas campanhas.

Na raiz do repositório:
    uv run python docs/relatorio/gerar_complementos.py

Lê os resultados oficiais consolidados e escreve apenas em docs/relatorio/.
As tabelas e a figura são versionadas para permitir compilar o LaTeX sem Python.
"""

from hashlib import sha256
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

from metaheuristica.instances import load_artesp_instance


RAIZ = Path(__file__).resolve().parents[2]
SAIDA = Path(__file__).resolve().parent
NOMES = {"tabu": "Busca Tabu", "aco": "ACO", "pso": "PSO"}
ORDEM = ("tabu", "aco", "pso")
FONTES = (
    "results/tables/benchmark_runs.parquet",
    "results/tables/benchmark_summary.parquet",
    "results/tables/greedy_runs.parquet",
    "results/tables/benchmark_statistical_tests.parquet",
    "results/maps/lot_maps_manifest.json",
    "data/instances/artesp_rmsp_150.json",
    "data/instances/artesp_rmsp_150_units.parquet",
    "data/instances/artesp_rmsp_150_pair_metrics.parquet",
)


def numero(valor: float, casas: int = 6, milhar: bool = False) -> str:
    formato = f"{valor:,.{casas}f}" if milhar else f"{valor:.{casas}f}"
    return formato.replace(",", "Z").replace(".", ",").replace("Z", ".")


def valor_p(valor: float) -> str:
    if valor >= 0.0001:
        return numero(valor, 4)
    mantissa, expoente = f"{valor:.2e}".split("e")
    return "$" + mantissa.replace(".", "{,}") + r"\times10^{" + str(int(expoente)) + "}$"


def tabela(titulo: str, rotulo: str, colunas: str, cabecalho: list[str], linhas: list[list[str]]) -> str:
    """Tabela quebrável, com cabeçalho repetido e fonte de tamanho legível."""
    linha_cabecalho = " & ".join(cabecalho) + r" \\"
    return "\n".join([
        r"\begingroup\small",
        r"\setlength{\tabcolsep}{5pt}",
        r"\begin{longtable}{" + colunas + "}",
        r"\caption{" + titulo + r"}\label{" + rotulo + r"}\\",
        r"\toprule", linha_cabecalho, r"\midrule", r"\endfirsthead",
        r"\multicolumn{" + str(len(cabecalho)) + r"}{c}{\tablename~\thetable{} (continuação)}\\",
        r"\toprule", linha_cabecalho, r"\midrule", r"\endhead",
        r"\midrule\multicolumn{" + str(len(cabecalho)) + r"}{r}{Continua na próxima página}\\",
        r"\endfoot", r"\bottomrule", r"\endlastfoot",
        *(" & ".join(linha) + r" \\" for linha in linhas),
        r"\end{longtable}", r"\endgroup",
    ])


def main() -> None:
    runs = pd.read_parquet(RAIZ / FONTES[0])
    resumo = pd.read_parquet(RAIZ / FONTES[1])
    gulosa = pd.read_parquet(RAIZ / FONTES[2])
    testes = pd.read_parquet(RAIZ / FONTES[3])
    mapas = json.loads((RAIZ / FONTES[4]).read_text(encoding="utf-8"))
    instancia = load_artesp_instance(RAIZ / "data/instances", 150)
    assert len(runs) == 1620 and len(resumo) == 54 and len(testes) == 18
    assert runs.official.all() and gulosa.official.all()
    assert runs.groupby(["instance", "k", "algorithm"]).size().eq(30).all()
    assert not runs.duplicated(["instance", "k", "algorithm", "seed"]).any()
    for linha in resumo.itertuples():
        grupo = runs[(runs.instance == linha.instance) & (runs.k == linha.k) & (runs.algorithm == linha.algorithm)]
        valores = [grupo.total_cost.mean(), grupo.total_cost.std(ddof=1), grupo.total_cost.min(), grupo.runtime_seconds.mean()]
        esperados = [linha.cost_mean, linha.cost_std, linha.cost_min, linha.runtime_mean]
        np.testing.assert_allclose(valores, esperados, rtol=0, atol=1e-12)

    partes = [
        "% Gerado por docs/relatorio/gerar_complementos.py; não editar as tabelas manualmente.",
        *(f"% Fonte: {fonte}; SHA256: {sha256((RAIZ / fonte).read_bytes()).hexdigest()}" for fonte in FONTES),
        r"\section{Resultados completos por cenário}\label{ap:resultados}",
        "Média, desvio-padrão amostral (DP) e melhor custo das 30 execuções de cada "
        "cenário. O tempo é a média do tempo de parede de uma execução, em segundos. "
        "O melhor de 30 resultados não representa o esforço de uma tentativa única. "
        "As tabelas são extraídas dos resultados oficiais, sem novas execuções. "
        "Valores exibidos são arredondados; as comparações usam os números completos.",
    ]
    for n in (20, 60, 150):
        linhas = []
        for k in range(3, 9):
            for algoritmo in ORDEM:
                r = resumo[(resumo.instance == f"artesp_rmsp_{n}") & (resumo.k == k) & (resumo.algorithm == algoritmo)].iloc[0]
                linhas.append([str(k), NOMES[algoritmo], numero(r.cost_mean), numero(r.cost_std), numero(r.cost_min), numero(r.runtime_mean, 2, True)])
        partes.append(tabela(f"Resultados da instância de {n} unidades.", f"tab:resultados-{n}", "rlrrrr", ["$K$", "Algoritmo", "Custo médio", "DP", "Melhor custo", "Tempo (s)"], linhas))

    partes += [
        r"\subsection{Frequência de superação da gulosa}\label{ap:frequencias}",
        r"Na instância grande, conta-se uma superação quando o custo da metaheurística "
        r"é menor que o da gulosa em mais de $10^{-12}$. As entradas indicam quantas das "
        r"30 execuções superam a referência. Não ocorreram empates dentro dessa "
        r"tolerância. Essas frequências descrevem a amostra, sem garantir sucesso em novas execuções.",
    ]
    linhas = []
    for k in range(3, 9):
        ref = gulosa[(gulosa.instance == "artesp_rmsp_150") & (gulosa.k == k)].iloc[0].total_cost
        linha = [str(k), numero(ref)]
        for algoritmo in ORDEM:
            valores = runs[(runs.instance == "artesp_rmsp_150") & (runs.k == k) & (runs.algorithm == algoritmo)].total_cost
            assert not (abs(valores - ref) <= 1e-12).any()
            linha.append(f"{int((valores < ref - 1e-12).sum())}/30")
        linhas.append(linha)
    partes.append(tabela("Superações da gulosa na instância de 150 unidades.", "tab:frequencias", "rrrrr", ["$K$", "Custo da gulosa", "Busca Tabu", "ACO", "PSO"], linhas))

    partes += [
        r"\clearpage\section{Contrastes estatísticos}\label{ap:contrastes}",
        r"Os valores-p ajustados e os efeitos são extraídos do artefato estatístico "
        r"oficial. Holm corrige os três pares dentro de cada cenário. O efeito é "
        r"calculado sobre A menos B: sinal negativo favorece A; positivo favorece B. "
        r"A coluna $\Delta$ é a diferença de custo médio, média(A) menos média(B), "
        r"e não uma estatística do teste de Wilcoxon. Aplicam-se as ressalvas da "
        r"Seção~\ref{subsec:estatistica}.",
    ]
    for n in (20, 60, 150):
        linhas = []
        for k in range(3, 9):
            r = testes[(testes.instance == f"artesp_rmsp_{n}") & (testes.k == k)].iloc[0]
            medias = resumo[(resumo.instance == f"artesp_rmsp_{n}") & (resumo.k == k)].set_index("algorithm").cost_mean
            for a, b in (("pso", "tabu"), ("pso", "aco"), ("tabu", "aco")):
                prefixo = f"wilcoxon_{a}_vs_{b}_"
                linhas.append([str(k), f"{NOMES[a]} / {NOMES[b]}", valor_p(r[prefixo + "p_holm"]), numero(r[prefixo + "rank_biserial"], 4), numero(medias[a] - medias[b])])
        partes.append(tabela(f"Contrastes da instância de {n} unidades.", f"tab:contrastes-{n}", "rlrrr", ["$K$", "A / B", "$p$ ajustado", "Efeito", r"$\Delta$ médio"], linhas))

    partes += [
        r"\clearpage\section{Composição dos lotes selecionados}\label{ap:lotes}",
        r"As tabelas descrevem as soluções de $N=150$, $K=5$ selecionadas pelo "
        r"manifesto cartográfico. Cada uma usa rótulos canônicos de 0 a 4, pela "
        r"ordem da primeira ocorrência no vetor. Esses rótulos não estão associados "
        r"às cores dos PNG nem constituem alinhamento entre algoritmos. A identidade "
        r"exata dos PNG com os resultados do manifesto permanece não comprovada.",
    ]
    selecionadas = {}
    linhas = []
    for algoritmo in ORDEM:
        c = next(c for c in mapas["combinations"] if c["instance"] == "artesp_rmsp_150" and c["k"] == 5 and c["algorithm"] == algoritmo)
        encontrados = runs[runs.scenario_id == c["scenario_id"]]
        assert len(encontrados) == 1
        r = encontrados.iloc[0]
        assert r.seed == c["seed"] and r.algorithm == algoritmo and r.k == 5
        assert abs(r.total_cost - c["total_cost"]) < 1e-12
        selecionadas[algoritmo] = r
        linhas.append([NOMES[algoritmo], str(r.seed), numero(r.total_cost), numero(r.c_demand, 4), numero(r.c_production, 4), numero(r.c_territorial, 4), numero(r.c_affinity, 4)])
    partes.append(tabela("Soluções identificadas no manifesto cartográfico.", "tab:selecionadas", "lrrrrrr", ["Algoritmo", "Semente", "Custo", "$C_D$", "$C_P$", "$C_T$", "$C_A$"], linhas))
    partes.append(r"A demanda e a produção são somadas por lote, na ordem de unidades "
                  r"da instância. As participações dividem essas somas pelos totais da "
                  r"instância. Todos os lotes estão ativos e cada unidade é contada uma "
                  r"única vez. As somas foram verificadas antes do arredondamento; as "
                  r"parcelas exibidas podem diferir ligeiramente dos totais por arredondamento.")
    for algoritmo in ORDEM:
        r = selecionadas[algoritmo]
        labels = np.array(json.loads(r.solution_json))
        assert labels.shape == (150,) and set(labels) == set(range(5))
        linhas = []
        soma_d = soma_p = 0.0
        for lote in range(5):
            mask = labels == lote
            demanda = instancia.demand[mask].sum()
            producao = instancia.production[mask].sum()
            soma_d += demanda
            soma_p += producao
            linhas.append([str(lote), f"{mask.sum()} ({numero(100*mask.mean(), 2)}\\%)", numero(demanda, 2, True), numero(100*demanda/instancia.demand.sum(), 2), numero(producao, 2, True), numero(100*producao/instancia.production.sum(), 2)])
        np.testing.assert_allclose([soma_d, soma_p], [instancia.demand.sum(), instancia.production.sum()], rtol=1e-12, atol=1e-9)
        linhas.append(["Total", r"150 (100\%)", numero(soma_d, 2, True), "100,00", numero(soma_p, 2, True), "100,00"])
        partes.append(tabela(f"Porte dos lotes da solução selecionada de {NOMES[algoritmo]}.", f"tab:lotes-{algoritmo}", "rrrrrr", ["Lote", r"Unidades (\%)", "Demanda/dia", r"\%", r"PU$\cdot$km/dia", r"\%"], linhas))
        partes.append(r"Identificador do cenário: {\footnotesize\path{" + r.scenario_id + "}}.")
    partes.append("Diferenças no número de unidades podem coexistir com equilíbrio "
                  "de demanda e produção, pois as unidades têm portes diferentes. As "
                  "tabelas caracterizam uma solução por método e não medem compacidade, "
                  "conectividade ou variabilidade entre as 30 execuções.")

    (SAIDA / "tabelas").mkdir(exist_ok=True)
    (SAIDA / "tabelas/resultados_complementares.tex").write_text("\n\n".join(partes) + "\n", encoding="utf-8")
    cores = ("#0072B2", "#D55E00", "#009E73")
    with plt.rc_context({"font.size": 12}):
        fig, axes = plt.subplots(1, 3, figsize=(11, 4.8), sharey=True)
        for ax, n in zip(axes, (20, 60, 150)):
            dados = [runs[(runs.instance == f"artesp_rmsp_{n}") & (runs.k == 5) & (runs.algorithm == a)].sort_values("seed").total_cost.to_numpy() for a in ORDEM]
            caixas = ax.boxplot(dados, tick_labels=[NOMES[a] for a in ORDEM], patch_artist=True, showfliers=False, widths=0.5, medianprops={"color": "#222222"})
            for patch, cor in zip(caixas["boxes"], cores):
                patch.set_facecolor(cor)
                patch.set_alpha(0.20)
            for pos, (valores, cor) in enumerate(zip(dados, cores), start=1):
                ax.scatter(pos + np.linspace(-0.17, 0.17, len(valores)), valores, s=15, color=cor, alpha=0.75, zorder=3)
            ref = gulosa[(gulosa.instance == f"artesp_rmsp_{n}") & (gulosa.k == 5)].iloc[0].total_cost
            ax.axhline(ref, color="#333333", linestyle="--", linewidth=1.3, label="Gulosa")
            ax.set_title(f"N = {n}")
            ax.tick_params(axis="x", labelsize=11)
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.2f}".replace(".", ",")))
            ax.grid(axis="y", alpha=0.2)
            ax.legend(loc="upper left", frameon=False)
        axes[0].set_ylabel("Custo final (menor é melhor)")
        fig.tight_layout()
        fig.savefig(SAIDA / "figuras/distribuicao_custos_k5.pdf", bbox_inches="tight", metadata={"CreationDate": None, "ModDate": None})
        plt.close(fig)
    print("Complementos gerados; 1.620 execuções, 54 resumos e totais dos 15 lotes conferidos.")


if __name__ == "__main__":
    main()
