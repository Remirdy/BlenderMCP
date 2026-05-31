#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_MODELS_DIR="$(cd "${PROJECT_DIR}/.." && pwd)/ai_models"
MODELS_DIR="${REMIRDY_MODELS_DIR:-${DEFAULT_MODELS_DIR}}"
TRIPOSR_DIR="${TRIPOSR_DIR:-${MODELS_DIR}/TripoSR}"

mkdir -p "${MODELS_DIR}"

if [ ! -d "${TRIPOSR_DIR}/.git" ]; then
  git clone https://github.com/VAST-AI-Research/TripoSR.git "${TRIPOSR_DIR}"
fi

cd "${TRIPOSR_DIR}"

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install torch torchvision torchaudio
python -m pip install -r requirements.txt
python -m pip install git+https://github.com/tatsy/torchmcubes.git

cat <<EOF

TripoSR is installed at:
  ${TRIPOSR_DIR}

Use it from Remirdy with:
  export TRIPOSR_DIR="${TRIPOSR_DIR}"
  export REMIRDY_IMAGE_TO_3D_PROVIDER=local
  export REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND='bash ${PROJECT_DIR}/scripts/run_triposr_to_glb.sh "{image}" "{output}"'

EOF
