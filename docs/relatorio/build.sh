#!/usr/bin/env bash
# docs/relatorio/build.sh
set -euo pipefail
cd "$(dirname "$0")"
latexmk -pdf -interaction=nonstopmode -halt-on-error relatorio.tex
echo "PDF gerado: $(pwd)/relatorio.pdf"
