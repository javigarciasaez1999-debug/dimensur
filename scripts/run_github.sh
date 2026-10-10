#!/usr/bin/env bash
set -euo pipefail

# No comprobar date/hora actual: un evento schedule sigue siendo válido tarde.
command=(python main.py)
case "${GITHUB_EVENT_NAME:-}" in
  schedule)
    # Reejecutar un run completado seleccionaría la siguiente fila Crear.
    # La recuperación de un fallo debe hacerse revisando la fila, manualmente.
    if [ "${GITHUB_RUN_ATTEMPT:-1}" != "1" ]; then
      echo "::error::No se repite una publicación programada. Revisa el resultado anterior y utiliza una ejecución manual con fila explícita si procede."
      exit 2
    fi
    MODE=publish
    command+=(--publish --only-create)
    ;;
  workflow_dispatch)
    MODE="${INPUT_MODE:-dry-run}"
    case "$MODE" in
      publish) command+=(--publish) ;;
      dry-run) command+=(--dry-run) ;;
      *) echo "::error::Modo no válido: $MODE"; exit 2 ;;
    esac
    if [ -n "${INPUT_ROW:-}" ]; then
      if [[ ! "$INPUT_ROW" =~ ^[0-9]+$ ]] || [ "$INPUT_ROW" -lt 2 ]; then
        echo "::error::La fila debe ser un entero igual o mayor que 2."
        exit 2
      fi
      command+=(--row "$INPUT_ROW")
    fi
    ;;
  *) echo "::error::Evento no permitido para publicar."; exit 2 ;;
esac

if [ "$MODE" = "publish" ] && [ -z "${DIMENSUR_API_TOKEN:-}" ]; then
  echo "::error::Falta el secret DIMENSUR_API_TOKEN; no se inicia una publicación."
  exit 2
fi

exec "${command[@]}"
