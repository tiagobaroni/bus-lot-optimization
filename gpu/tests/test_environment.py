from metaheuristica_gpu.environment import inspect_gpu_environment


def test_real_gpu_environment_supports_float64_cuda12() -> None:
    environment = inspect_gpu_environment()
    assert environment.cuda_runtime.startswith("12.")
    assert environment.compute_capability == "8.6"
    assert environment.float64_kernel_passed is True
