#!/usr/bin/env bash
# Studio Reels · prepara o ambiente em qualquer projeto/sessão (idempotente)
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
python3 -m pip install -q --break-system-packages -r requirements.txt 2>/dev/null || python3 -m pip install -q -r requirements.txt
command -v ffmpeg >/dev/null || echo "! ffmpeg ausente (necessário para reels)"
python3 studio.py doctor
echo "Motor pronto em: $HERE"
echo "export STUDIO_REELS_HOME=\"$HERE\""
