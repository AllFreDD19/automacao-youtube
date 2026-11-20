#!/usr/bin/env bash
# Prepara o Linux da nuvem (Claude Code) para a ferramenta. Rodar uma vez no começo de cada sessão nova:
#   bash instalar_nuvem.sh
# Leva ~1 min. O modelo do Whisper (~1,6 GB) baixa sozinho na primeira transcrição.
set -e
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { apt-get update -q && apt-get install -y -q ffmpeg; }
fc-match Arial | grep -qi liberation || apt-get install -y -q fonts-liberation >/dev/null 2>&1 \
  || { apt-get update -q >/dev/null 2>&1 && apt-get install -y -q fonts-liberation >/dev/null; }
pip install -q --root-user-action=ignore faster-whisper==1.2.1 edge-tts==7.3.1 yt-dlp==2026.10.26 "rembg[cpu]" openai python-dotenv requests pillow numpy
mkdir -p projetos musicas
python3 -c "import automacao.config, faster_whisper, edge_tts; print('ferramenta OK (nuvem)')"
