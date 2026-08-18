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

for _variable in THREAD_LIMIT_VARIABLES:
    os.environ[_variable] = "1"
