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

PYTHON_BIN="${TRIPOSR_SETUP_PYTHON:-}"
if [ -z "${PYTHON_BIN}" ]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

"${PYTHON_BIN}" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade "pip<26" "setuptools<82" wheel
python -m pip install torch torchvision torchaudio
python -m pip install \
  "numpy<2" \
  "Pillow==10.1.0" \
  "omegaconf==2.3.0" \
  "einops==0.7.0" \
  "transformers==4.35.0" \
  "trimesh==4.0.5" \
  "huggingface-hub==0.17.3" \
  "imageio[ffmpeg]" \
  "rembg" \
  "onnxruntime" \
  "moderngl==5.10.0" \
  "git+https://github.com/tatsy/torchmcubes.git"

if [ ! -f "${TRIPOSR_DIR}/xatlas.py" ]; then
  cat > "${TRIPOSR_DIR}/xatlas.py" <<'PY'
"""Local shim for TripoSR runs without texture baking."""

def export(*_args, **_kwargs):
    raise RuntimeError(
        "xatlas is not installed. Run without --bake-texture, or install xatlas "
        "before enabling texture baking."
    )
PY
fi

cat <<EOF

TripoSR is installed at:
  ${TRIPOSR_DIR}

Python used:
  ${PYTHON_BIN}

Use it from Remirdy with:
  export TRIPOSR_DIR="${TRIPOSR_DIR}"
  export REMIRDY_IMAGE_TO_3D_PROVIDER=local
  export REMIRDY_LOCAL_IMAGE_TO_3D_COMMAND='bash ${PROJECT_DIR}/scripts/run_triposr_to_glb.sh "{image}" "{output}"'

EOF
