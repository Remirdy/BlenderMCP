#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 /path/to/input.png /path/to/output.glb" >&2
  exit 2
fi

IMAGE_PATH="$1"
OUTPUT_GLB="$2"

if [ -f "${OUTPUT_GLB}" ]; then
  echo "Output GLB already exists at ${OUTPUT_GLB}, skipping reconstruction."
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_TRIPOSR_DIR="$(cd "${PROJECT_DIR}/.." && pwd)/ai_models/TripoSR"
TRIPOSR_DIR="${TRIPOSR_DIR:-${REMIRDY_TRIPOSR_DIR:-${DEFAULT_TRIPOSR_DIR}}}"
TRIPOSR_PYTHON="${TRIPOSR_PYTHON:-${TRIPOSR_DIR}/.venv/bin/python}"
DEVICE="${TRIPOSR_DEVICE:-cpu}"
MC_RESOLUTION="${TRIPOSR_MC_RESOLUTION:-256}"
TEXTURE_RESOLUTION="${TRIPOSR_TEXTURE_RESOLUTION:-2048}"
FOREGROUND_RATIO="${TRIPOSR_FOREGROUND_RATIO:-0.85}"
BAKE_TEXTURE="${TRIPOSR_BAKE_TEXTURE:-0}"
NO_REMOVE_BG="${TRIPOSR_NO_REMOVE_BG:-0}"

if [ ! -f "${IMAGE_PATH}" ]; then
  echo "Input image not found: ${IMAGE_PATH}" >&2
  exit 3
fi

if [ ! -f "${TRIPOSR_DIR}/run.py" ]; then
  echo "TripoSR was not found at ${TRIPOSR_DIR}." >&2
  echo "Run scripts/install_triposr_local.sh or set TRIPOSR_DIR." >&2
  exit 4
fi

if [ ! -x "${TRIPOSR_PYTHON}" ]; then
  echo "TripoSR Python was not found at ${TRIPOSR_PYTHON}." >&2
  echo "Run scripts/install_triposr_local.sh or set TRIPOSR_PYTHON." >&2
  exit 5
fi

OUT_DIR="$(dirname "${OUTPUT_GLB}")"
WORK_DIR="${OUT_DIR}/.$(basename "${OUTPUT_GLB}" .glb)_triposr"
mkdir -p "${WORK_DIR}" "${OUT_DIR}"
rm -rf "${WORK_DIR}/0"
mkdir -p "${WORK_DIR}/0"

cd "${TRIPOSR_DIR}"

ARGS=(
  run.py "${IMAGE_PATH}"
  --device "${DEVICE}" \
  --output-dir "${WORK_DIR}" \
  --model-save-format glb \
  --mc-resolution "${MC_RESOLUTION}" \
  --foreground-ratio "${FOREGROUND_RATIO}"
)

if [ "${NO_REMOVE_BG}" = "1" ]; then
  ARGS+=(--no-remove-bg)
fi

if [ "${BAKE_TEXTURE}" = "1" ]; then
  ARGS+=(--bake-texture --texture-resolution "${TEXTURE_RESOLUTION}")
fi

"${TRIPOSR_PYTHON}" "${ARGS[@]}"

GENERATED_GLB="${WORK_DIR}/0/mesh.glb"
if [ ! -f "${GENERATED_GLB}" ]; then
  echo "TripoSR finished, but no GLB was written at ${GENERATED_GLB}" >&2
  find "${WORK_DIR}" -maxdepth 3 -type f >&2 || true
  exit 6
fi

cp "${GENERATED_GLB}" "${OUTPUT_GLB}"
echo "Wrote ${OUTPUT_GLB}"
