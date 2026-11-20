"""Cenas animadas no estilo de motion design minimalista (referência do dono: canal "O Mundo e Tudo ao Redor").

Uma ilustração plana gerada por IA (silhuetas, paleta azul-noite, sem texto) ganha movimento: câmera aproximando
devagar, leve deslize lateral e uma camada de partículas (neve, estrelas piscando, poeira, brasas ou chuva) que
cai/sobe em velocidades diferentes, dando profundidade. Tudo em Python + FFmpeg, sem placa de vídeo e sem custo.

No roteiro.json, uma cena vira animação com:
    "visual": "animacao",
    "prompt_animacao": "lone man silhouette on a beach looking at a huge full moon",  (em inglês, sem texto)
    "efeito": "estrelas"          (neve | estrelas | poeira | brasas | chuva | nenhum; padrão: poeira)
Use nas cenas abstratas, de ideia, metáfora ou sem foto boa; pessoas e lugares reais continuam em foto/vídeo.

Texto na tela (vale para qualquer cena, foto, vídeo ou animação): "texto_tela": ["antes da", "luz elétrica"]
(linha pequena em cima, palavra-chave grande embaixo, canto inferior esquerdo, com fade).
"""
import io
import math
import random
import subprocess
import time
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageFilter

from . import config

LARGURA, ALTURA, FPS = 1920, 1080, 30
FAIXA_CINEMA = round((ALTURA - LARGURA / 2.39) / 2)  # 138 px: faixas pretas de cinema (2,39:1)
ESTILO = (", minimalist flat vector illustration, simple shapes and silhouettes, deep navy blue night palette, "
          "soft glow, cinematic composition, muted colors, no text, no letters, no watermark")
EFEITOS = ("neve", "estrelas", "poeira", "brasas", "chuva", "nenhum")
ZOOM_FINAL = 1.07  # aproximação total ao longo da cena (lenta: não chama atenção, só dá vida)


def gerar_imagem(prompt, destino, semente):
    """Ilustração plana 16:9. FLUX da NVIDIA se escolhido no .env; senão Pollinations (grátis, sem chave).

    Pollinations devolve 1024x576 com marca d'água no canto inferior direito: corta 9% de baixo e amplia (no estilo
    plano a ampliação não aparece)."""
    from . import visuais
    texto = prompt + ESTILO
    bruto = None
    if config.NVIDIA_API_KEY and config.IMAGEM_PROVEDOR == "nvidia":
        try:
            bruto, corte = visuais.flux_nvidia({"prompt": texto, "mode": "base", "cfg_scale": 3.5, "width": 1344,
                                                "height": 768, "steps": 30}), 0.0
        except Exception as e:
            print(f"    FLUX falhou ({e.__class__.__name__}); usando Pollinations")
    if bruto is None:
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(texto)
               + f"?width=1920&height=1080&nologo=true&model=flux&seed={semente}")
        for tentativa in range(5):
            try:
                r = requests.get(url, timeout=240)
                if r.ok and r.headers.get("content-type", "").startswith("image/"):
                    bruto, corte = r.content, 0.09
                    break
            except requests.RequestException:
                pass
            # Pollinations responde 429/503 quando está cheio: espera crescente
            time.sleep(15 * (tentativa + 1))
    if bruto is None:
        return None
    im = Image.open(io.BytesIO(bruto)).convert("RGB")
    im = im.crop((0, 0, im.width, int(im.height * (1 - corte))))
    r = max(LARGURA / im.width, ALTURA / im.height)
    im = im.resize((math.ceil(im.width * r), math.ceil(im.height * r)), Image.LANCZOS)
    x, y = (im.width - LARGURA) // 2, (im.height - ALTURA) // 2
    im.crop((x, y, x + LARGURA, y + ALTURA)).save(destino, quality=93)
    return destino


def _particulas(efeito, rnd):
    """Lista de partículas [x, y, tamanho, velocidade, fase]; quanto maior, mais rápida (perto da câmera)."""
    qtd = {"neve": 260, "estrelas": 220, "poeira": 120, "brasas": 90, "chuva": 320}.get(efeito, 0)
    ps = []
    for _ in range(qtd):
        tam = rnd.uniform(1.0, 3.4)
        ps.append([rnd.uniform(0, LARGURA), rnd.uniform(0, ALTURA), tam, tam * rnd.uniform(14, 24),
                   rnd.uniform(0, 6.28)])
    return ps


def _desenhar(d, efeito, ps, q):
    for p in ps:
        x, y, tam, vel, fase = p
        if efeito == "neve":
            p[1] = (y + vel / FPS) % ALTURA
            p[0] = (x + math.sin(q / 45 + fase) * 0.5) % LARGURA
            d.ellipse((p[0], p[1], p[0] + tam, p[1] + tam), fill=(255, 255, 255, int(55 * tam)))
        elif efeito == "estrelas":
            if y > ALTURA * 0.6:  # estrelas só no céu
                continue
            brilho = 0.55 + 0.45 * math.sin(q / (12 + 8 * tam) + fase)
            t = tam * 0.6
            d.ellipse((x, y, x + t, y + t), fill=(255, 255, 255, int(200 * brilho)))
        elif efeito == "poeira":
            p[1] = (y - vel * 0.25 / FPS) % ALTURA
            p[0] = (x + vel * 0.35 / FPS + math.sin(q / 60 + fase) * 0.3) % LARGURA
            alfa = int(28 * tam * (0.6 + 0.4 * math.sin(q / 30 + fase)))
            d.ellipse((p[0], p[1], p[0] + tam * 1.4, p[1] + tam * 1.4), fill=(255, 236, 200, alfa))
        elif efeito == "brasas":
            p[1] = (y - vel * 0.9 / FPS) % ALTURA
            p[0] = (x + math.sin(q / 25 + fase) * 0.8) % LARGURA
            alfa = int(70 * tam * (0.5 + 0.5 * math.sin(q / 9 + fase)))
            d.ellipse((p[0], p[1], p[0] + tam, p[1] + tam), fill=(255, 140, 40, min(alfa, 230)))
        elif efeito == "chuva":
            p[1] = (y + vel * 6 / FPS) % ALTURA
            p[0] = (x + vel * 1.2 / FPS) % LARGURA
            d.line((p[0], p[1], p[0] - tam * 2, p[1] - tam * 9), fill=(200, 215, 255, int(30 * tam)), width=1)


def renderizar(imagem, destino, duracao, efeito="poeira", semente=0):
    """Vídeo mudo de `duracao` s a partir da ilustração (sem faixas nem texto: entram na edição)."""
    efeito = efeito if efeito in EFEITOS else "poeira"
    rnd = random.Random(semente)
    base = Image.open(imagem).convert("RGB")
    margem = ZOOM_FINAL + 0.04  # folga para o deslize lateral
    base = base.resize((int(LARGURA * margem), int(ALTURA * margem)), Image.LANCZOS)
    ps = _particulas(efeito, rnd)
    lado = 1 if semente % 2 else -1
    n = max(1, int(duracao * FPS))
    ff = subprocess.Popen([config.ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{LARGURA}x{ALTURA}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                           "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", str(destino)],
                          stdin=subprocess.PIPE)
    try:
        for q in range(n):
            t = q / n
            suave = t * t * (3 - 2 * t)  # começa e termina devagar
            z = 1.0 + (ZOOM_FINAL - 1.0) * suave
            # A base é ~11% maior que a tela: o recorte (que encolhe com o zoom) sempre cabe, mesmo deslizando
            w, h = int(LARGURA / z), int(ALTURA / z)
            cx = base.width / 2 + lado * 0.02 * LARGURA * (suave - 0.5)
            cy = base.height / 2
            caixa = (int(cx - w / 2), int(cy - h / 2), int(cx - w / 2) + w, int(cy - h / 2) + h)
            quadro = base.crop(caixa).resize((LARGURA, ALTURA), Image.BILINEAR)
            if ps:
                cam = Image.new("RGBA", (LARGURA, ALTURA))
                _desenhar(ImageDraw.Draw(cam), efeito, ps, q)
                quadro = Image.alpha_composite(quadro.convert("RGBA"), cam).convert("RGB")
            ff.stdin.write(quadro.tobytes())
    finally:
        ff.stdin.close()
        ff.wait()
    if ff.returncode != 0:
        raise RuntimeError(f"animação falhou: {destino}")
    return destino


def texto_png(linhas, destino, faixas=True):
    """PNG transparente 1920x1080 com o texto da cena no canto inferior esquerdo, acima da faixa de cinema."""
    pequena, grande = (list(linhas) + [""])[:2] if isinstance(linhas, (list, tuple)) else ("", str(linhas))
    im = Image.new("RGBA", (LARGURA, ALTURA))
    d = ImageDraw.Draw(im)
    f1, f2 = config.fonte_texto(28, True), config.fonte_texto(70, True)
    base_y = ALTURA - (FAIXA_CINEMA if faixas else 0) - 60
    x = 96
    if grande:
        caixa = d.textbbox((0, 0), grande.upper(), font=f2)
        y2 = base_y - (caixa[3] - caixa[1])
    else:
        y2 = base_y
    sombra = Image.new("RGBA", (LARGURA, ALTURA))
    ds = ImageDraw.Draw(sombra)
    for alvo, cor in ((ds, (0, 0, 0, 170)), (d, (255, 255, 255, 255))):
        dx = 3 if alvo is ds else 0
        if pequena:
            alvo.text((x + dx, y2 - 44 + dx), pequena.upper(), font=f1, fill=cor[:3] + (int(cor[3] * 0.85),))
        if grande:
            alvo.text((x + dx, y2 - caixa[1] + dx), grande.upper(), font=f2, fill=cor)
    sombra = sombra.filter(ImageFilter.GaussianBlur(4))
    Image.alpha_composite(sombra, im).save(destino)
    return destino
