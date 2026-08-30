from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from metaheuristica import ConfigurationError, SolutionValidationError
from metaheuristica.canonical import (
    canonicalize_solution,
    solution_key,
    validate_solution,
    validated_solution_key,
)
from metaheuristica.instances import load_artesp_instance
from metaheuristica.objective import evaluate_solution


INSTANCIAS = Path(__file__).parents[1] / "data/instances"
CAMPOS_DE_AVALIACAO = (
    "total_cost",
    "c_demand",
    "c_production",
    "c_territorial",
    "c_affinity",
    "cv_demand",
    "cv_production",
)


def test_canonicalization_follows_first_occurrence() -> None:
    canonical = canonicalize_solution([2, 2, 0, 1, 0], n_units=5, k=3)
    assert canonical.tolist() == [0, 0, 1, 2, 1]
    assert not canonical.flags.writeable


def test_equivalent_partitions_share_key_and_canonicalization_is_idempotent() -> None:
    first = solution_key([0, 0, 1, 1, 2, 2], n_units=6, k=3)
    second = solution_key([2, 2, 0, 0, 1, 1], n_units=6, k=3)
    assert first == second == (0, 0, 1, 1, 2, 2)
    assert solution_key(first, n_units=6, k=3) == first


def test_validated_solution_is_an_immutable_copy() -> None:
    source = np.array([0, 1, 1], dtype=np.int32)
    validated = validate_solution(source, n_units=3, k=2)
    source[0] = 1
    assert validated.tolist() == [0, 1, 1]
    assert validated.dtype == np.int64
    with pytest.raises(ValueError):
        validated[0] = 1
    with pytest.raises(ValueError):
        validated.setflags(write=True)


@pytest.mark.parametrize(
    ("solution", "message"),
    [
        ([0, 1], "3 posições"),
        ([[0, 1, 1]], "unidimensional"),
        ([0.0, 1.0, 1.0], "inteiros"),
        ([0, 1, 2], "intervalo"),
        ([0, 0, 0], "lotes vazios"),
        ([True, False, True], "inteiros"),
    ],
)
def test_invalid_solutions_are_rejected(solution: object, message: str) -> None:
    with pytest.raises(SolutionValidationError, match=message):
        validate_solution(solution, n_units=3, k=2)


@pytest.mark.parametrize("k", [1, 4, 2.0, True])
def test_invalid_k_is_rejected(k: object) -> None:
    with pytest.raises(ConfigurationError):
        validate_solution([0, 1, 1], n_units=3, k=k)  # type: ignore[arg-type]


def test_validated_solution_key_reproduz_o_caminho_publico_bit_a_bit() -> None:
    """F1-06 na réplica: a chave sem revalidação tem de ser a mesma chave.

    `solution_key` valida e depois renomeia. Quem já validou o mesmo vetor na
    mesma chamada paga a validação duas vezes, que é o padrão que o F1-06
    removeu do núcleo no pacote B6 e que a réplica em placa gráfica
    reintroduziu. `validated_solution_key` é a metade posterior à validação,
    publicada como nome próprio para que **nenhum nome privado atravesse a
    fronteira** entre o núcleo e a réplica.

    **O fixture precisa discriminar, e a propriedade é asseverada aqui dentro.**
    A lição do lote L4 é que instância pequena com matrizes zeradas torna a
    asserção verdadeira e vazia: nela renomear lotes não move bit algum. Este
    caso usa instância real e estado deliberadamente não canônico, e assevera as
    duas coisas que o tornam discriminante: que a renomeação de fato permuta os
    rótulos, e que a permutação de fato move bits da avaliação.
    """

    instance = load_artesp_instance(INSTANCIAS, 20)
    k = 5
    estado = [(3 * index + 4) % k for index in range(instance.n_units)]
    rotulos = np.array(estado, dtype=np.int64)
    canonica = canonicalize_solution(rotulos, n_units=instance.n_units, k=k)

    # Primeira propriedade discriminante: a renomeação permuta os rótulos.
    assert canonica.tolist() != rotulos.tolist()

    # Segunda propriedade discriminante: a permutação move bits da avaliação, o
    # que prova que a instância não é o caso degenerado do lote L4.
    bruta = evaluate_solution(instance, rotulos, k=k)
    renomeada = evaluate_solution(instance, canonica, k=k)
    assert any(
        getattr(bruta, campo).hex() != getattr(renomeada, campo).hex()
        for campo in CAMPOS_DE_AVALIACAO
    )

    # O oráculo: a chave é bit a bit a mesma que o caminho público produz.
    validados = validate_solution(rotulos, n_units=instance.n_units, k=k)
    assert validated_solution_key(validados, n_units=instance.n_units) == solution_key(
        estado, n_units=instance.n_units, k=k
    )

    # E o contrato dito no corpo da função vale: a validação é do chamador, logo
    # a função aceita rótulos já validados sem conferi-los de novo.
    assert validated_solution_key(
        canonica, n_units=instance.n_units
    ) == tuple(int(rotulo) for rotulo in canonica)
