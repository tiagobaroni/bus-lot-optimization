"""Geração dos estilos QML consumidos pelo QGIS (B15)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import quoteattr

QGIS_VERSION = "3.40.0"

# ColorBrewer Dark2, qualitativa de oito classes: cobre K de 3 a 8 sem repetir
# cor, e a mesma posição significa o mesmo lote em todos os painéis porque o
# alinhamento de rótulos tornou o índice comparável.
LOT_COLORS = [
    "#1b9e77", "#d95f02", "#7570b3", "#e7298a",
    "#66a61e", "#e6ab02", "#a6761d", "#666666",
]
NESTING_COLORS = {"20_60_150": "#084594", "60_150": "#6baed6", "so_150": "#c6dbef"}
CONTEXT_GRAY = "#bdbdbd"


def _rgba(color: str) -> str:
    value = color.lstrip("#")
    red, green, blue = (int(value[index:index + 2], 16) for index in (0, 2, 4))
    return f"{red},{green},{blue},255"


def _symbol(name: str, symbol_type: str, color: str) -> str:
    if symbol_type == "line":
        properties = [
            ("line_color", _rgba(color)), ("line_style", "solid"),
            ("line_width", "0.86"), ("line_width_unit", "MM"),
            ("capstyle", "round"), ("joinstyle", "round"),
        ]
        layer_class, alpha = "SimpleLine", "1"
    else:
        properties = [
            ("color", _rgba(color)), ("style", "solid"),
            ("outline_color", "70,70,70,255"), ("outline_style", "solid"),
            ("outline_width", "0.26"), ("outline_width_unit", "MM"),
            ("joinstyle", "miter"),
        ]
        layer_class, alpha = "SimpleFill", "0.45"
    body = "".join(
        f'          <prop k="{key}" v="{value}"/>\n' for key, value in properties
    )
    return (
        f'      <symbol alpha="{alpha}" clip_to_extent="1" name="{name}" '
        f'type="{symbol_type}">\n'
        f'        <layer class="{layer_class}" enabled="1" locked="0" pass="0">\n'
        f'{body}'
        f'        </layer>\n'
        f'      </symbol>\n'
    )


def _document(renderer: str) -> str:
    return (
        "<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>\n"
        f'<qgis version="{QGIS_VERSION}" styleCategories="Symbology">\n'
        f"{renderer}"
        "</qgis>\n"
    )


def categorized_qml(
    *, attribute: str, symbol_type: str, categories: list[tuple[object, str, str]]
) -> str:
    """QML de simbologia categorizada, no formato aceito pelo QGIS 3.40."""

    lines = [
        f'  <renderer-v2 type="categorizedSymbol" attr={quoteattr(attribute)} '
        'enableorderby="0" forceraster="0" referencescale="-1" symbollevels="0">\n',
        "    <categories>\n",
    ]
    for position, (value, label, _) in enumerate(categories):
        lines.append(
            f"      <category value={quoteattr(str(value))} "
            f"label={quoteattr(label)} symbol=\"{position}\" render=\"true\"/>\n"
        )
    lines.append("    </categories>\n")
    lines.append("    <symbols>\n")
    lines.extend(
        _symbol(str(position), symbol_type, color)
        for position, (_, _, color) in enumerate(categories)
    )
    lines.append("    </symbols>\n")
    lines.append("  </renderer-v2>\n")
    return _document("".join(lines))


def single_symbol_qml(*, symbol_type: str, color: str) -> str:
    """QML de símbolo único, para camada de contexto sem legenda por classe."""

    renderer = (
        '  <renderer-v2 type="singleSymbol" enableorderby="0" forceraster="0" '
        'referencescale="-1" symbollevels="0">\n'
        "    <symbols>\n"
        f"{_symbol('0', symbol_type, color)}"
        "    </symbols>\n"
        "  </renderer-v2>\n"
    )
    return _document(renderer)


def _plain_writer(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def write_style_files(
    directory: Path,
    *,
    panels: list[tuple[str, str, int]],
    nesting: list[tuple[str, str]],
    writer: Callable[[Path, str], Path] | None = None,
) -> dict[str, Path]:
    """Escreve os doze estilos: aninhamento, nove painéis, envoltórias, terminais.

    `writer` recebe (caminho, conteúdo) e devolve o caminho escrito. A CLI passa
    a escrita atômica de `export_maps`; o default serve a chamador que não se
    importe. A injeção existe para satisfazer a restrição global de atomicidade
    sem que este módulo importe `export_maps`, o que fecharia um ciclo.
    """

    directory.mkdir(parents=True, exist_ok=True)
    write = writer if writer is not None else _plain_writer
    written: dict[str, Path] = {}

    def _write(name: str, content: str) -> None:
        written[name] = write(directory / f"{name}.qml", content)

    _write("itinerarios_aninhamento", categorized_qml(
        attribute="aninhamento", symbol_type="line",
        categories=[(value, label, NESTING_COLORS[value]) for value, label in nesting],
    ))
    for name, attribute, k in panels:
        _write(name, categorized_qml(
            attribute=attribute, symbol_type="line",
            categories=[(lot, f"Lote {lot}", LOT_COLORS[lot]) for lot in range(k)],
        ))
    _write("envoltorias", categorized_qml(
        attribute="lot", symbol_type="fill",
        categories=[(lot, f"Lote {lot}", color) for lot, color in enumerate(LOT_COLORS)],
    ))
    _write("terminais_contexto",
           single_symbol_qml(symbol_type="fill", color=CONTEXT_GRAY))
    return written
