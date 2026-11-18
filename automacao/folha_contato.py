"""Folha de contato: uma miniatura por cena com número e busca, para revisar visuais de uma olhada."""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config

LARG, ALT, COLUNAS = 240, 135, 8
NOTA_SUSPEITA = 0.22  # nota do CLIP abaixo disso: provavelmente sem relação com a cena


def _quadro(cena, pasta_projeto):
    arquivo = pasta_projeto / cena["visual_arquivo"]
    if cena.get("visual_tipo") != "video":
        return Image.open(arquivo).convert("RGB")
    saida = Path(tempfile.gettempdir()) / f"quadro_{cena['id']}_{arquivo.stem}.jpg"
    subprocess.run([config.ffmpeg(), "-y", "-loglevel", "error", "-ss", "1", "-i", str(arquivo),
                    "-frames:v", "1", "-vf", "scale=480:-1", str(saida)], check=True)
    return Image.open(saida).convert("RGB")


def gerar(roteiro, pasta_projeto, destino=None):
    # O segundo visual das falas longas entra logo depois do primeiro, com "b" no número (ex.: "12b")
    cenas = []
    for c in roteiro["cenas"]:
        if c.get("visual_arquivo"):
            cenas.append(c)
        if c.get("visual_extra"):
            cenas.append({"id": f"{c['id']}b", "visual_arquivo": c["visual_extra"], "visual_tipo": c.get("visual_extra_tipo"),
                          "nota": c.get("nota_extra"), "busca_stock": c.get("busca_stock"), "busca_wiki": c.get("busca_wiki")})
    linhas = (len(cenas) + COLUNAS - 1) // COLUNAS
    folha = Image.new("RGB", (COLUNAS * LARG, linhas * (ALT + 22)), "white")
    desenho = ImageDraw.Draw(folha)
    fonte = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 13)
    for k, cena in enumerate(cenas):
        x, y = (k % COLUNAS) * LARG, (k // COLUNAS) * (ALT + 22)
        try:
            img = _quadro(cena, pasta_projeto)
            img.thumbnail((LARG, ALT))
            folha.paste(img, (x, y))
        except Exception:
            desenho.rectangle([x, y, x + LARG, y + ALT], fill="gray")
        # [V] = vídeo; a nota do CLIP (0 a ~0,4) vem antes da busca, e nota baixa sai em vermelho para revisar primeiro
        nota = cena.get("nota")
        rotulo = (f"{cena['id']}{' [V]' if cena.get('visual_tipo') == 'video' else ''}"
                  f"{f' {nota:.2f}' if nota is not None else ''} {cena.get('busca_wiki') or cena.get('busca_stock', '')}")
        cor = "red" if nota is not None and nota < NOTA_SUSPEITA else "black"
        desenho.text((x + 3, y + ALT + 3), rotulo[:34], font=fonte, fill=cor)
    destino = destino or pasta_projeto / "folha_cenas.jpg"
    folha.save(destino, quality=85)
    return destino
