import pytest

from metaheuristica_gpu.run import _exclusive_gpu, main


def test_cli_rejeita_id_ausente():
    assert main(["execute"]) == 2


def test_lock_impede_duas_execucoes():
    with _exclusive_gpu():
        with pytest.raises(RuntimeError, match="execução GPU ativa"):
            with _exclusive_gpu():
                pass
