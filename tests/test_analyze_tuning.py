"""Reprodutibilidade byte a byte e modo de verificação da análise oficial.

Todos os casos rodam sobre uma **raiz sintética em `tmp_path`**, montada aqui
mesmo: nada é lido de `_temp/` nem de `results/`, que o Git ignora, e nada é
escrito na raiz do repositório. A instância declarada pela configuração
sintética tem caminho que **não existe** na raiz real, de modo que, se o
redirecionamento da raiz falhar, `load_campaign` recusa a configuração em vez de
a análise sobrescrever `experiments/configs/frozen_parameters.toml`, que é
arquivo protegido pelo congelamento.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from experiments import config as config_module
from experiments.analyze_tuning import analyze, main, verify_analysis
from experiments.config import load_campaign
from experiments.scenarios import file_sha256

from tests.test_tuning_analysis import synthetic_runs


ROOT = Path(__file__).parents[1]
INSTANCE_RELATIVE = "data/instances/tuning_sintetico.json"
ARTIFACT_RELATIVES = (
    "results/tables/tuning_summary.parquet",
    "results/tables/tuning_parameter_effects.parquet",
    "results/tables/tuning_selection.json",
    "experiments/configs/frozen_parameters.toml",
)
COMMIT = "0" * 40
WORKERS = 16


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _synthetic_config(root: Path) -> Path:
    """Copia a configuração oficial de tuning apontando para instância própria."""

    _write(root / INSTANCE_RELATIVE, '{"name": "instancia_sintetica"}\n')
    original = (ROOT / "experiments/configs/tuning.toml").read_text(encoding="utf-8")
    text = original.replace(
        'path = "data/instances/artesp_rmsp_60.json"',
        f'path = "{INSTANCE_RELATIVE}"',
    )
    assert text != original, "a configuração oficial de tuning mudou de instância"
    config_path = root / "experiments/configs/tuning.toml"
    _write(config_path, text)
    return config_path


def build_tuning_root(root: Path) -> Path:
    """Monta raiz de tuning completa e devolve o caminho da configuração."""

    config_path = _synthetic_config(root)
    config = load_campaign(config_path, repository_root=root)
    provenance = json.dumps(
        {"official": True, "git_commit": COMMIT, "campaign_workers": WORKERS},
        sort_keys=True,
    )
    runs = synthetic_runs(config).assign(provenance_json=provenance)
    checkpoints = pd.DataFrame([
        {"scenario_id": identifier, "checkpoint": index, "incumbent_cost": float(index)}
        for identifier in runs["scenario_id"]
        for index in range(1, 101)
    ])
    tables = root / "results/tables"
    tables.mkdir(parents=True, exist_ok=True)
    runs_path = tables / "tuning_runs.parquet"
    checkpoints_path = tables / "tuning_checkpoints.parquet"
    runs.to_parquet(runs_path, index=False)
    checkpoints.to_parquet(checkpoints_path, index=False)
    manifest = {
        "schema_version": 1,
        "campaign": config.name,
        "purpose": config.purpose,
        "config_sha256": file_sha256(config.source_path),
        "expected": 440,
        "completed": 440,
        "complete": True,
        "official": True,
        "runs": {
            "path": str(runs_path.relative_to(root)),
            "sha256": file_sha256(runs_path),
        },
        "checkpoints": {
            "path": str(checkpoints_path.relative_to(root)),
            "sha256": file_sha256(checkpoints_path),
        },
    }
    (tables / "tuning_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    assert len(runs) == 440 and len(checkpoints) == 44_000
    return config_path


@pytest.fixture
def tuning_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Raiz sintética já redirecionada, com o redirecionamento conferido."""

    root = tmp_path.resolve()
    config_path = build_tuning_root(root)
    monkeypatch.setattr(config_module, "REPOSITORY_ROOT", root)
    loaded = load_campaign(config_path)
    assert loaded.repository_root == root, (
        "o redirecionamento da raiz falhou e a análise escreveria na raiz real"
    )
    return root, config_path


def _digests(root: Path) -> dict[str, str]:
    return {
        relative: file_sha256(root / relative) for relative in ARTIFACT_RELATIVES
    }


def test_analise_repetida_produz_artefatos_byte_a_byte_identicos(tuning_root) -> None:
    """Insumos idênticos precisam produzir os quatro artefatos idênticos.

    A seção 28 de `docs/experiments.md` trata reprodutibilidade como propriedade
    verificável dos artefatos, e o congelamento protege
    `experiments/configs/frozen_parameters.toml` por sha256. Com o carimbo de
    tempo dentro do documento de seleção, o sha do documento muda a cada
    execução, o TOML protegido muda junto e a campanha fica bloqueada sem que
    decisão alguma tenha mudado.
    """

    root, config_path = tuning_root

    first = analyze(config_path)
    first_digests = _digests(root)
    second = analyze(config_path)
    second_digests = _digests(root)

    assert first_digests == second_digests
    assert first == second


INSTANTE = frozenset({
    "timestamp", "datetime", "date", "utc", "clock",
    "started", "finished", "generated", "created", "modified",
})


def _chaves_de_instante(node: object, prefix: str = "") -> list[str]:
    """Nomes de campo que sugerem instante de execução, em qualquer profundidade.

    A varredura é recursiva e por vocabulário, e não só pelo sufixo `_at` no
    primeiro nível: um carimbo reintroduzido dentro de `sources`, ou batizado
    `timestamp` ou `generated`, reabre o `F9-3` do mesmo jeito, e o caso de
    igualdade byte a byte só o pegaria quando as duas execuções caíssem em
    instantes diferentes.

    O casamento é por **token**, e não por substring, senão `mean_runtime_seconds`
    entraria por conter "time" e a guarda acusaria o documento correto. Duração
    não é instante.
    """

    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            caminho = f"{prefix}.{key}" if prefix else key
            tokens = set(key.lower().split("_"))
            if key.lower().endswith("_at") or tokens & INSTANTE:
                found.append(caminho)
            found.extend(_chaves_de_instante(value, caminho))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_chaves_de_instante(value, f"{prefix}[{index}]"))
    return found


def test_a_guarda_de_instante_reconhece_carimbo_aninhado_e_de_outro_nome() -> None:
    """Caso negativo da própria guarda, para ela não passar por vácuo.

    Sem isto, `_chaves_de_instante` poderia devolver lista vazia sempre e o caso
    acima continuaria verde, que é a forma canônica do padrão `F2-02`.
    """

    assert _chaves_de_instante({"selected_at": "x"}) == ["selected_at"]
    assert _chaves_de_instante({"sources": {"run": {"timestamp": 1}}}) == [
        "sources.run.timestamp"
    ]
    assert _chaves_de_instante({"winners": [{"generated": 1}]}) == [
        "winners[0].generated"
    ]
    assert _chaves_de_instante({"campaign_commit": "0" * 40, "n_runs": 440}) == []
    # Duração não é instante, e o casamento por substring erraria aqui.
    assert _chaves_de_instante({"tolerance": {"mean_runtime_seconds": 0.1}}) == []


def test_documento_de_selecao_nao_carrega_carimbo_de_tempo(tuning_root) -> None:
    """O carimbo não pode voltar para dentro do que o sha256 resume.

    Este caso é o guarda contra a reintrodução: qualquer campo com instante de
    execução dentro do documento reabre o achado `F9-3`, e o teste de igualdade
    acima só o pega quando as duas execuções caem em segundos diferentes.
    """

    root, config_path = tuning_root
    selection = analyze(config_path)
    document = json.loads(
        (root / "results/tables/tuning_selection.json").read_text(encoding="utf-8")
    )
    assert document == selection
    assert "selected_at" not in document
    assert not _chaves_de_instante(document)


def _tree_snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    """Inode, mtime e conteúdo de cada arquivo sob a raiz.

    Conteúdo sozinho não bastaria: uma verificação defeituosa que reescrevesse
    os mesmos bytes no destino oficial passaria despercebida, e é justamente
    isso que o modo de verificação existe para não fazer sob congelamento. O
    inode muda em toda escrita, porque `os.replace` troca a entrada.
    """

    snapshot: dict[str, tuple[int, int, str]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            status = path.stat()
            snapshot[str(path.relative_to(root))] = (
                status.st_ino, status.st_mtime_ns, file_sha256(path)
            )
    return snapshot


def test_modo_de_verificacao_nao_escreve_artefato_algum(tuning_root) -> None:
    """Reexecutar a análise sob congelamento não pode tocar arquivo protegido."""

    root, config_path = tuning_root
    analyze(config_path)
    before = _tree_snapshot(root)

    selection, divergent = verify_analysis(config_path)

    assert divergent == []
    assert selection == json.loads(
        (root / "results/tables/tuning_selection.json").read_text(encoding="utf-8")
    )
    assert _tree_snapshot(root) == before


def test_modo_de_verificacao_acusa_divergencia_e_nomeia_o_artefato(tuning_root) -> None:
    """Divergência de conteúdo é acusada, e mesmo assim nada é reescrito.

    A alteração abaixo é de conteúdo do documento oficial, não da entrada: o
    TOML congelado em disco continua íntegro e coerente com o sha do documento
    recomputado, de modo que só o documento diverge. Um comparador que
    respondesse pelo destino, e não pelo conteúdo, não distinguiria os dois.
    """

    root, config_path = tuning_root
    analyze(config_path)
    selection_path = root / "results/tables/tuning_selection.json"
    document = json.loads(selection_path.read_text(encoding="utf-8"))
    document["campaign_workers"] = document["campaign_workers"] + 1
    selection_path.write_text(
        json.dumps(document, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    before = _tree_snapshot(root)

    _, divergent = verify_analysis(config_path)

    assert divergent == ["results/tables/tuning_selection.json"]
    assert _tree_snapshot(root) == before


def test_modo_de_verificacao_trata_artefato_ausente_como_divergente(tuning_root) -> None:
    """Sem análise anterior, os quatro artefatos são acusados, e nenhum é criado."""

    root, config_path = tuning_root
    before = _tree_snapshot(root)

    _, divergent = verify_analysis(config_path)

    assert divergent == sorted(ARTIFACT_RELATIVES)
    assert _tree_snapshot(root) == before


def test_cli_de_verificacao_devolve_zero_no_identico_e_um_no_divergente(
    tuning_root, capsys
) -> None:
    """A interface de operador precisa separar os dois desfechos por código."""

    root, config_path = tuning_root
    analyze(config_path)
    arguments = ["--config", str(config_path), "--verify"]

    assert main(arguments) == 0
    identical = capsys.readouterr()
    assert json.loads(identical.out)["campaign_commit"] == COMMIT
    assert "idênticos" in identical.err

    frozen_path = root / "experiments/configs/frozen_parameters.toml"
    frozen_path.write_text(
        frozen_path.read_text(encoding="utf-8") + "# comentário estranho\n",
        encoding="utf-8",
    )
    before = _tree_snapshot(root)

    assert main(arguments) == 1
    assert "experiments/configs/frozen_parameters.toml" in capsys.readouterr().err
    assert _tree_snapshot(root) == before


def test_cli_oficial_escreve_os_artefatos_e_devolve_zero(tuning_root, capsys) -> None:
    """O ramo sem `--verify` é o comando que o `README.md` documenta.

    Ele não tinha teste algum: a impressão do documento na saída padrão, o
    instante na saída de erro e o código de retorno passariam verdes se
    quebrassem.
    """

    root, config_path = tuning_root
    arguments = ["--config", str(config_path)]

    assert main(arguments) == 0

    captured = capsys.readouterr()
    documento = json.loads(captured.out)
    assert documento["campaign_commit"] == COMMIT
    assert not _chaves_de_instante(documento)
    assert "análise executada em " in captured.err
    assert "divergentes" not in captured.err

    # O instante fica fora do documento, que é o ponto do achado, mas precisa
    # aparecer em algum lugar: é o que a segunda metade da correção prometeu.
    assert captured.err.strip().endswith("Z")

    digests = _digests(root)
    assert main(arguments) == 0
    assert _digests(root) == digests
