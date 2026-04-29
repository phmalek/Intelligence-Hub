#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/generate_market_utm_forms.py"
SOURCE_FILE="${SCRIPT_DIR}/Porsche_UTM Adoption Feedback_March26_UPDATED_with_Owner_and_Blockers.xlsx"

if [[ ! -f "${SOURCE_FILE}" ]]; then
  echo "Source workbook not found: ${SOURCE_FILE}"
  exit 1
fi

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

usage() {
  echo "Usage:"
  echo "  $0 generate <market_code|all> <output_folder>"
  echo "  $0 consolidate <responses_folder> <output_file>"
  echo
  echo "Examples:"
  echo "  $0 generate all market_forms_apr"
  echo "  $0 generate PCGB market_forms_pcgb"
  echo "  $0 consolidate market_forms_apr utm_consolidated_apr.xlsx"
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

COMMAND="$1"

case "${COMMAND}" in
  generate)
    if [[ $# -ne 3 ]]; then
      usage
      exit 1
    fi
    MARKET="$2"
    OUT_DIR="$3"
    mkdir -p "${SCRIPT_DIR}/${OUT_DIR}"
    "${PYTHON_BIN}" "${PY_SCRIPT}" generate \
      --source "${SOURCE_FILE}" \
      --market "${MARKET}" \
      --outdir "${SCRIPT_DIR}/${OUT_DIR}"
    ;;
  consolidate)
    if [[ $# -ne 3 ]]; then
      usage
      exit 1
    fi
    RESPONSES_DIR="$2"
    OUTPUT_FILE="$3"
    "${PYTHON_BIN}" "${PY_SCRIPT}" consolidate \
      --responses "${SCRIPT_DIR}/${RESPONSES_DIR}" \
      --output "${SCRIPT_DIR}/${OUTPUT_FILE}"
    ;;
  *)
    usage
    exit 1
    ;;
esac
