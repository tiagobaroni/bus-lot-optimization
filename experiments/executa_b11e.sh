#!/usr/bin/env bash
# Encadeia os cinco lotes da B11-E com as barreiras, e para no primeiro problema.
#
# Semantica dos codigos de saida da CLI, que e o que torna este script confiavel:
#   0   tudo certo
#   3   houve falha de cenario
#   130 interrompido por sinal
#   2   erro de configuracao, congelamento ou proveniencia
#
# Uso direto:
#   cd /home/baroni/workspace/bus-lot-optimization
#   nohup bash experiments/executa_b11e.sh > _temp/b11e.log 2>&1 &
#   tail -f _temp/b11e.log

set -u
B11E_REPOSITORY_ROOT=${B11E_REPOSITORY_ROOT:-/home/baroni/workspace/bus-lot-optimization}
B11E_BARRIER_DIR=${B11E_BARRIER_DIR:-results/operational/benchmark_main/barriers}
cd "$B11E_REPOSITORY_ROOT" || exit 1

PAUSA_ENTRE_LOTES=${PAUSA_ENTRE_LOTES:-300}   # segundos, para carga e temperatura
CMD=(uv run python -m experiments.run_benchmark)

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

parar() {
    log "=========================================================="
    log "PARADO: $*"
    log "A campanha NAO foi concluida. Nada foi desfeito: os"
    log "resultados ja gravados permanecem e a retomada os ignora."
    log "=========================================================="
    exit 1
}

ETAPA="verificacao inicial"
trap 'parar "sinal recebido durante $ETAPA"' INT TERM
log "=========================================================="
log "B11-E: cinco lotes, 1620 cenarios, 16 workers"
log "Estimativa: 13 a 15 h no total, 2,6 a 3 h por lote"
log "=========================================================="

if [ -n "$(git status --porcelain)" ]; then
    parar "arvore de trabalho suja. A campanha exige arvore limpa."
fi
log "arvore limpa"

log "conferindo prontidao..."
if ! "${CMD[@]}" readiness > _temp/b11e_readiness.json 2>&1; then
    cat _temp/b11e_readiness.json
    parar "readiness recusou"
fi
python3 -c "
import json,sys
d=json.load(open('_temp/b11e_readiness.json'))
assert d['ready'] is True, 'ready nao e true'
assert d['git_dirty'] is False, 'arvore suja'
assert d['partition']['scenarios'] == 1620, 'cenarios != 1620'
assert type(d['existing_results']) is int and d['existing_results'] >= 0, 'existing_results invalido'
print(f\"  ready=True, 1620 cenarios, {d['existing_results']} resultados existentes\")
" || parar "readiness nao bate com o esperado"

INICIO=$(date +%s)

for LOTE in 1 2 3 4 5; do
    log "----------------------------------------------------------"
    log "LOTE $LOTE de 5: iniciando execucao"
    log "----------------------------------------------------------"

    BARREIRA=$(printf '%s/batch-%02d.json' "$B11E_BARRIER_DIR" "$LOTE")
    if [ -f "$BARREIRA" ]; then
        ETAPA="revalidacao da barreira do lote $LOTE"
        log "lote $LOTE: barreira existente; revalidando antes de pular..."
        if ! "${CMD[@]}" barrier --batch "$LOTE"; then
            parar "a barreira existente do lote $LOTE falhou na revalidacao. O lote seguinte NAO pode ser liberado."
        fi
        log "lote $LOTE: barreira revalidada; execucao e pausa dispensadas"
        continue
    fi

    ETAPA="execute do lote $LOTE"
    "${CMD[@]}" execute --batch "$LOTE"
    CODIGO=$?

    case $CODIGO in
        0)  log "lote $LOTE: execucao completa, sem falhas" ;;
        3)  log "lote $LOTE: houve falhas. Chamando retry, que e a unica"
            log "  tentativa adicional permitida por cenario."
            ETAPA="retry do lote $LOTE"
            "${CMD[@]}" retry --batch "$LOTE"
            CODIGO_RETRY=$?
            if [ $CODIGO_RETRY -ne 0 ]; then
                parar "lote $LOTE ainda tem falhas depois do retry (codigo $CODIGO_RETRY). Uma segunda falha do mesmo cenario bloqueia a campanha por desenho: diagnostique antes de qualquer nova tentativa."
            fi
            log "lote $LOTE: retry resolveu as falhas" ;;
        130) parar "lote $LOTE foi interrompido por sinal. Retomar e seguro: basta executar este script de novo, que os resultados validos serao ignorados." ;;
        2)  parar "lote $LOTE recusou por configuracao, congelamento ou proveniencia. NAO contorne: diagnostique. Provavel causa e alguem ter tocado arquivo do escopo protegido." ;;
        *)  parar "lote $LOTE devolveu codigo inesperado $CODIGO" ;;
    esac

    ETAPA="barreira do lote $LOTE"
    log "lote $LOTE: validando a barreira..."
    if ! "${CMD[@]}" barrier --batch "$LOTE"; then
        parar "a barreira do lote $LOTE reprovou. O lote seguinte NAO pode ser liberado."
    fi
    log "lote $LOTE: BARREIRA APROVADA"

    DECORRIDO=$(( $(date +%s) - INICIO ))
    log "lote $LOTE concluido. Decorrido total: $(( DECORRIDO / 3600 ))h $(( (DECORRIDO % 3600) / 60 ))min"

    if [ "$LOTE" -lt 5 ]; then
        log "pausa de ${PAUSA_ENTRE_LOTES}s antes do lote seguinte, para carga e temperatura"
        sleep "$PAUSA_ENTRE_LOTES"
    fi
done

ETAPA="finalize"
log "----------------------------------------------------------"
log "as cinco barreiras passaram. Consolidando a campanha..."
if ! "${CMD[@]}" finalize; then
    parar "finalize reprovou"
fi

TOTAL=$(( $(date +%s) - INICIO ))
log "=========================================================="
log "B11-E CONCLUIDA em $(( TOTAL / 3600 ))h $(( (TOTAL % 3600) / 60 ))min"
log "Os 1620 cenarios estao validados e consolidados."
log "NADA foi commitado: o commit dos resultados e decisao sua."
log "=========================================================="
