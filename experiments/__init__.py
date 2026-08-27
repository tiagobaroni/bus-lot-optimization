"""Ferramentas para configurar e executar os experimentos."""

import os


THREAD_LIMIT_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "ARROW_NUM_THREADS",
)

# Duas das sete não têm efeito e são mantidas por simetria com o enunciado da
# restrição. `ARROW_NUM_THREADS` não é variável reconhecida pelo Apache Arrow:
# quem controla `pa.cpu_count()` é `OMP_NUM_THREADS`, e a contenção efetiva do
# Arrow vem dela mais as chamadas explícitas de `pa.set_cpu_count(1)` e
# `pa.set_io_thread_count(1)` feitas no worker. `VECLIB_MAXIMUM_THREADS` é do
# Accelerate da Apple e é inócua em Linux, que é a plataforma fixada.
INEFFECTIVE_THREAD_VARIABLES = ("ARROW_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")

# O ambiente recebido é capturado **antes** da escrita abaixo, e não depois.
# Reler as mesmas chaves do mesmo `os.environ` no mesmo processo devolve o que
# este bloco acabou de escrever, o que documenta a intenção deste processo e não
# a configuração recebida, e não pode falhar.
INHERITED_THREAD_LIMITS: dict[str, str | None] = {
    variable: os.environ.get(variable) for variable in THREAD_LIMIT_VARIABLES
}

for _variable in THREAD_LIMIT_VARIABLES:
    os.environ[_variable] = "1"
