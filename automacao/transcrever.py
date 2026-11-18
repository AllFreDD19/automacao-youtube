"""Transcreve um áudio com o horário de cada palavra (faster-whisper large-v3 na placa de vídeo).

    .venv\\Scripts\\python.exe -m automacao.transcrever <audio> <saida.json> <idioma>
Saída: lista [{"w": palavra, "s": início, "e": fim}, ...]. Usado para casar a voz gravada pelo usuário com o roteiro.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from . import config

# o ctranslate2 pede as DLLs do CUDA 12 (pacotes nvidia-cublas-cu12 e nvidia-cudnn-cu12 do venv)
_nvidia = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
for _bin in _nvidia.glob("*/bin"):
    os.environ["PATH"] = str(_bin) + os.pathsep + os.environ["PATH"]
    os.add_dll_directory(str(_bin))

from faster_whisper import BatchedInferencePipeline, WhisperModel  # noqa: E402


def transcrever(audio, saida, idioma):
    # o decodificador do faster-whisper falha em alguns mp3: o FFmpeg entrega o áudio já lido
    bruto = subprocess.run([config.ffmpeg(), "-v", "error", "-i", str(audio), "-f", "f32le", "-ac", "1", "-ar", "16000",
                            "-"], capture_output=True, check=True).stdout
    som = np.frombuffer(bruto, dtype=np.float32)
    print(f"áudio: {len(som) / 16000 / 60:.1f} min", flush=True)
    t0 = time.time()
    # turbo + int8: o large-v3 em float16 lotava os 4 GB da RTX 3050 e andava a 1x o tempo real (86 min de áudio
    # = ~80 min); para casar com o roteiro já escrito a precisão do turbo sobra
    modelo = BatchedInferencePipeline(WhisperModel("large-v3-turbo", device="cuda", compute_type="int8_float16"))
    # sem condition_on_previous_text: com ele o Whisper perde a pontuação e repete frases em áudios longos
    segmentos, _ = modelo.transcribe(som, language=idioma, word_timestamps=True, batch_size=8,
                                     condition_on_previous_text=False)
    palavras = []
    for seg in segmentos:
        palavras += [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for w in seg.words or []]
        if len(palavras) % 500 < len(seg.words or []):
            print(f"   {seg.end / 60:.1f} min transcritos", flush=True)
    Path(saida).write_text(json.dumps(palavras, ensure_ascii=False), encoding="utf-8")
    print(f"{len(palavras)} palavras em {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    transcrever(sys.argv[1], sys.argv[2], sys.argv[3])
