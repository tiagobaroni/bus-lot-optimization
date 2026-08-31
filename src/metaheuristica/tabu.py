"""Busca Tabu com movimentos de realocação entre lotes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from metaheuristica.canonical import (
    validate_k,
    validate_solution,
    validated_solution_key,
)
from metaheuristica.errors import ConfigurationError
from metaheuristica.metrics import COST_TOLERANCE, OptimizationResult, RunConfig
from metaheuristica.optimizer import OptimizationContext, execute_optimizer
from metaheuristica.problem import EvaluationResult, ProblemInstance


IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class TabuConfig:
    """Hiperparâmetros específicos da Busca Tabu."""

    tabu_tenure: int
    neighborhood_size: int
    stagnation_limit: int

    def __post_init__(self) -> None:
        for name, value in (
            ("tabu_tenure", self.tabu_tenure),
            ("neighborhood_size", self.neighborhood_size),
            ("stagnation_limit", self.stagnation_limit),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ConfigurationError(f"{name} deve ser um inteiro positivo")


@dataclass(frozen=True, slots=True, order=True)
class TabuMove:
    """Realocação de uma unidade entre dois lotes estáveis."""

    unit_index: int
    source_lot: int
    target_lot: int

    def reversed(self) -> TabuMove:
        return TabuMove(self.unit_index, self.target_lot, self.source_lot)


@dataclass(frozen=True, slots=True)
class _EvaluatedCandidate:
    move: TabuMove
    solution: IntArray
    canonical_key: tuple[int, ...]
    evaluation: EvaluationResult
    was_tabu: bool
    aspiration: bool

    @property
    def admissible(self) -> bool:
        return not self.was_tabu or self.aspiration


@dataclass(frozen=True, slots=True)
class _TabuEntry:
    """As duas pontas da janela de proibição de uma reversão."""

    registered_at: int
    expiration: int


class _TabuMemory:
    """Janelas de proibição de reversões, medidas em movimentos aceitos.

    F5-7: a forma anterior guardava só a expiração e usava o **próprio
    contador** como valor de ausência, `self._expirations.get(move,
    accepted_moves) > accepted_moves`. A resposta para ausência saía certa por
    acidente, porque `a > a` é falso, mas a janela de um movimento registrado
    ficava aberta em baixo: qualquer contador estritamente menor que a expiração
    respondia "proibido", inclusive contadores anteriores ao próprio registro.
    Com o registro da seção 14 no sétimo movimento aceito e prazo de quatro, a
    janela correta é `{7, 8, 9, 10}` e a observada era `{0, ..., 10}`.

    A correção tem duas partes, e a primeira sozinha não bastaria. A sentinela
    passa a ser explícita, o `None` de `dict.get`, o que separa "ausente" de
    "expirado agora"; e a janela passa a ser fechada nas duas pontas, pelo
    movimento aceito que a criou e pela expiração, o que exige guardar também o
    contador do registro. Trocar apenas a sentinela devolveria exatamente a
    mesma função, porque a ponta de baixo é o defeito inteiro.

    **O invariante do contador, que não estava escrito nem asseverado.** A
    leitura só é correta porque o contador de movimentos aceitos é monótono não
    decrescente dentro do segmento entre dois reinícios, e porque o reinício
    limpa a memória inteira por `clear`. O piso do segmento é o contador do
    último expurgo, que é o ponto em que o laço anuncia o avanço da série;
    consultar ou registrar abaixo dele é rebobinar, e a asserção reprova. Sem
    ela, uma alteração futura que zerasse o contador no reinício sem limpar a
    memória reintroduziria proibições fantasmas em silêncio.
    """

    __slots__ = ("_entries", "_counter_floor")

    def __init__(self) -> None:
        self._entries: dict[TabuMove, _TabuEntry] = {}
        self._counter_floor: int | None = None

    def _assert_counter_advances(self, accepted_moves: int) -> None:
        assert (
            self._counter_floor is None or accepted_moves >= self._counter_floor
        ), (
            "o contador de movimentos aceitos foi rebobinado dentro do segmento: "
            f"{accepted_moves} < {self._counter_floor}"
        )

    def register(self, move: TabuMove, *, accepted_moves: int, tenure: int) -> None:
        self._assert_counter_advances(accepted_moves)
        self._entries[move.reversed()] = _TabuEntry(
            registered_at=accepted_moves, expiration=accepted_moves + tenure
        )

    def purge(self, *, accepted_moves: int) -> None:
        self._assert_counter_advances(accepted_moves)
        self._counter_floor = accepted_moves
        expired = sorted(
            move
            for move, entry in self._entries.items()
            if entry.expiration <= accepted_moves
        )
        for move in expired:
            del self._entries[move]

    def is_tabu(self, move: TabuMove, *, accepted_moves: int) -> bool:
        self._assert_counter_advances(accepted_moves)
        entry = self._entries.get(move)
        if entry is None:
            return False
        return entry.registered_at <= accepted_moves < entry.expiration

    def clear(self) -> None:
        """Fecha o segmento: a memória e o piso do contador voltam ao início."""

        self._entries.clear()
        self._counter_floor = None

    @property
    def entries(self) -> tuple[tuple[TabuMove, int], ...]:
        return tuple(
            (move, self._entries[move].expiration) for move in sorted(self._entries)
        )


def _balanced_random_solution(
    n_units: int, k: int, rng: np.random.Generator
) -> IntArray:
    validate_k(k, n_units)
    permutation = rng.permutation(n_units)
    solution = np.empty(n_units, dtype=np.int64)
    solution[permutation] = np.arange(n_units, dtype=np.int64) % k
    return solution


def _enumerate_valid_moves(
    solution: Any, *, k: int
) -> tuple[IntArray, tuple[TabuMove, ...]]:
    """Valida a solução corrente e enumera os movimentos que a mantêm viável.

    F5-4: esta é a validação **mais externa** do laço, e é a única que
    sobrevive. Ela devolve agora também os rótulos validados, porque são eles
    que os movimentos enumerados endereçam: quem recebe o par não precisa
    revalidar o mesmo vetor para aplicar um movimento que saiu daqui.

    Todo movimento devolvido tem origem com mais de uma unidade, logo nenhum
    deles esvazia lote, e todo destino está em `0 <= destino < k`. É esta
    garantia, computada uma vez por iteração, que faz de cada candidato uma
    solução já válida.
    """

    labels = validate_solution(solution, n_units=len(solution), k=k)
    lot_sizes = np.bincount(labels, minlength=k)
    moves: list[TabuMove] = []
    for unit_index, source_value in enumerate(labels):
        source = int(source_value)
        if lot_sizes[source] <= 1:
            continue
        for target in range(k):
            if target != source:
                moves.append(TabuMove(unit_index, source, target))
    return labels, tuple(moves)


def _sample_moves(
    moves: tuple[TabuMove, ...], size: int, rng: np.random.Generator
) -> tuple[TabuMove, ...]:
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ConfigurationError("tamanho da vizinhança deve ser um inteiro positivo")
    count = min(size, len(moves))
    if count == 0:
        return ()
    positions = rng.permutation(len(moves))[:count]
    return tuple(moves[int(position)] for position in positions)


def _apply_move(labels: IntArray, move: TabuMove) -> IntArray:
    """Aplica sobre rótulos já validados um movimento já enumerado.

    F5-4: as sete conferências que ficavam aqui, mais a validação que as
    precedia, eram redundantes por candidato. Todas elas são consequência da
    enumeração, que roda uma vez por iteração sobre o mesmo vetor: o índice da
    unidade vem de `enumerate` sobre os rótulos, origem e destino vêm de
    `range(k)`, os dois são diferentes por construção, a unidade pertence ao
    lote de origem porque foi de lá que ela saiu, e a origem tem mais de uma
    unidade porque a enumeração descarta as demais.

    A garantia vale para **todos** os candidatos da iteração porque cada um é
    construído a partir de `current`, e não encadeado sobre o candidato
    anterior: a ocupação medida uma vez continua sendo a ocupação de partida de
    cada aplicação.
    """

    candidate = np.array(labels, dtype=np.int64, copy=True)
    candidate[move.unit_index] = move.target_lot
    return candidate


def _candidate_is_better(
    candidate: _EvaluatedCandidate, incumbent: _EvaluatedCandidate
) -> bool:
    # Comparação exata de custo seguida da cadeia de desempate. A banda de
    # COST_TOLERANCE não era transitiva, e como _select_best_admissible é redução
    # sequencial na ordem da amostra, o vencedor dependia dessa ordem e podia ser
    # estritamente pior que outro admissível, contra a seção 14.
    candidate_cost = candidate.evaluation.total_cost
    incumbent_cost = incumbent.evaluation.total_cost
    if candidate_cost < incumbent_cost:
        return True
    if candidate_cost == incumbent_cost:
        if candidate.canonical_key != incumbent.canonical_key:
            return candidate.canonical_key < incumbent.canonical_key
        return candidate.move < incumbent.move
    return False


def _select_best_admissible(
    candidates: list[_EvaluatedCandidate],
) -> _EvaluatedCandidate | None:
    best: _EvaluatedCandidate | None = None
    for candidate in candidates:
        if not candidate.admissible:
            continue
        if best is None or _candidate_is_better(candidate, best):
            best = candidate
    return best


@dataclass(slots=True)
class _TabuDiagnostics:
    iterations_completed: int = 0
    accepted_moves: int = 0
    restarts: int = 0
    aspiration_acceptances: int = 0
    tabu_candidates_evaluated: int = 0
    global_improvements: int = 0

    def publish(self, context: OptimizationContext) -> None:
        context.update_diagnostics(
            iterations_completed=self.iterations_completed,
            accepted_moves=self.accepted_moves,
            restarts=self.restarts,
            aspiration_acceptances=self.aspiration_acceptances,
            tabu_candidates_evaluated=self.tabu_candidates_evaluated,
            global_improvements=self.global_improvements,
        )


def _strict_improvement(before: float | None, after: float | None) -> bool:
    return before is not None and after is not None and after < before - COST_TOLERANCE


def _aspiration_applies(
    *, was_tabu: bool, candidate_cost: float, global_best_cost: float | None
) -> bool:
    return (
        was_tabu
        and global_best_cost is not None
        and candidate_cost < global_best_cost - COST_TOLERANCE
    )


def _incumbent_cost(context: OptimizationContext) -> float | None:
    incumbent = context.incumbent_evaluation
    return None if incumbent is None else incumbent.total_cost


def _tabu_search(
    context: OptimizationContext,
    config: TabuConfig,
    *,
    n_units: int,
    k: int,
) -> None:
    diagnostics = _TabuDiagnostics()
    diagnostics.publish(context)
    memory = _TabuMemory()
    stagnation = 0

    current = _balanced_random_solution(n_units, k, context.rng)
    context.evaluate(current)

    def evaluate_restart() -> IntArray:
        restart = _balanced_random_solution(n_units, k, context.rng)
        before = _incumbent_cost(context)
        evaluations_before = context.evaluations

        def close_restart() -> None:
            """Fecha o reinício pelo contrato novo de `optimizer.py`.

            F5-3: estas cinco linhas ficavam **depois** do `try/finally`, e o
            reinício que consumia a última avaliação do orçamento perdia todas
            elas, porque `EvaluationLimitReached` propagava antes. A correção
            **não** é mover as linhas para o `finally`: o `finally` já existe e
            serve a outro propósito, a publicação de diagnósticos, e
            sobrecarregá-lo esconderia que o problema é de contrato e o faria
            reaparecer no próximo algoritmo que consumisse a última avaliação
            em caminho especial.
            """

            nonlocal stagnation
            memory.clear()
            stagnation = 0
            diagnostics.restarts += 1
            diagnostics.iterations_completed += 1
            diagnostics.publish(context)

        try:
            context.evaluate(restart, finalize=close_restart)
        finally:
            if context.evaluations > evaluations_before:
                after = _incumbent_cost(context)
                if _strict_improvement(before, after):
                    diagnostics.global_improvements += 1
                diagnostics.publish(context)
        return restart

    while True:
        memory.purge(accepted_moves=diagnostics.accepted_moves)
        labels, moves = _enumerate_valid_moves(current, k=k)
        sampled = _sample_moves(moves, config.neighborhood_size, context.rng)
        if not sampled:
            current = evaluate_restart()
            continue

        candidates: list[_EvaluatedCandidate] = []
        iteration_improved = False
        for move in sampled:
            candidate_solution = _apply_move(labels, move)
            was_tabu = memory.is_tabu(
                move, accepted_moves=diagnostics.accepted_moves
            )
            before = _incumbent_cost(context)
            evaluations_before = context.evaluations
            try:
                evaluation = context.evaluate(candidate_solution)
            finally:
                if context.evaluations > evaluations_before:
                    if was_tabu:
                        diagnostics.tabu_candidates_evaluated += 1
                    after = _incumbent_cost(context)
                    if _strict_improvement(before, after):
                        diagnostics.global_improvements += 1
                        iteration_improved = True
                    diagnostics.publish(context)
            aspiration = _aspiration_applies(
                was_tabu=was_tabu,
                candidate_cost=evaluation.total_cost,
                global_best_cost=before,
            )
            # F5-4: `canonicalize_solution` validava este mesmo vetor uma
            # terceira vez por candidato. `validated_solution_key`, publicada
            # pelo pacote L7, é a metade posterior à validação e produz a mesma
            # tupla a partir dos mesmos `int64` na mesma ordem. A precondição de
            # rótulos já validados é do chamador e está cumprida por
            # construção, conforme `_enumerate_valid_moves` e `_apply_move`.
            candidates.append(
                _EvaluatedCandidate(
                    move=move,
                    solution=candidate_solution,
                    canonical_key=validated_solution_key(
                        candidate_solution, n_units=n_units
                    ),
                    evaluation=evaluation,
                    was_tabu=was_tabu,
                    aspiration=aspiration,
                )
            )

        winner = _select_best_admissible(candidates)
        if winner is None:
            current = evaluate_restart()
            continue

        current = winner.solution
        diagnostics.accepted_moves += 1
        memory.register(
            winner.move,
            accepted_moves=diagnostics.accepted_moves,
            tenure=config.tabu_tenure,
        )
        if winner.was_tabu and winner.aspiration:
            diagnostics.aspiration_acceptances += 1
        stagnation = 0 if iteration_improved else stagnation + 1
        diagnostics.iterations_completed += 1
        diagnostics.publish(context)

        if stagnation >= config.stagnation_limit:
            current = evaluate_restart()


def run_tabu(
    instance: ProblemInstance,
    run_config: RunConfig,
    tabu_config: TabuConfig,
) -> OptimizationResult:
    """Executa a Busca Tabu pelo contrato comum dos otimizadores."""

    if not isinstance(tabu_config, TabuConfig):
        raise ConfigurationError("tabu_config deve ser TabuConfig")

    def search(context: OptimizationContext, config: TabuConfig) -> None:
        _tabu_search(
            context,
            config,
            n_units=instance.n_units,
            k=run_config.k,
        )

    return execute_optimizer(
        instance,
        run_config,
        tabu_config,
        algorithm="tabu",
        search=search,
    )
