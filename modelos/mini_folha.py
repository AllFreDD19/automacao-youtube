"""Monta uma folha só com as cenas pedidas (principal e extra). Uso: mini_folha.py <pasta_projeto> <saida> ids..."""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, r"C:\Users\User\Videos\automacao-youtube")
from automacao import config  # noqa: E402

pasta, saida, ids = Path(sys.argv[1]), sys.argv[2], {int(i) for i in sys.argv[3:]}
r = json.loads((pasta / "roteiro.json").read_text(encoding="utf-8"))
itens = []
for c in r["cenas"]:
    if c["id"] in ids:
        for campo, suf in (("visual_arquivo", ""), ("visual_extra", "b")):
            if c.get(campo):
                itens.append((f"{c['id']}{suf} {c.get('busca_wiki') or c.get('busca_stock')}", pasta / c[campo]))
W, H = 300, 190
folha = Image.new("RGB", (W * 6, (H + 20) * ((len(itens) + 5) // 6)), "white")
for n, (rot, arq) in enumerate(itens):
    if arq.suffix.lower() in (".mp4", ".webm", ".mov"):
        tmp = Path(saida).with_suffix(".frame.jpg")
        subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", "-ss", "1", "-i", str(arq), "-frames:v", "1",
                        str(tmp)])
        im = Image.open(tmp)
        rot = "[V] " + rot
    else:
        im = Image.open(arq)
    im = im.convert("RGB")
    im.thumbnail((W, H))
    x, y = (n % 6) * W, (n // 6) * (H + 20)
    folha.paste(im, (x, y))
    ImageDraw.Draw(folha).text((x + 2, y + H + 4), rot[:45], fill="black")
folha.save(saida, quality=88)
print(len(itens), "visuais")
