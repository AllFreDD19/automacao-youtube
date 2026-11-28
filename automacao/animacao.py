"""Cenas animadas no estilo de motion design minimalista (referência do dono: canal "O Mundo e Tudo ao Redor").

Uma ilustração plana gerada por IA (silhuetas, paleta azul-noite, sem texto) ganha movimento: câmera aproximando
devagar, leve deslize lateral e uma camada de partículas (neve, estrelas piscando, poeira, brasas ou chuva) que
cai/sobe em velocidades diferentes, dando profundidade. Tudo em Python + FFmpeg, sem placa de vídeo e sem custo.

No roteiro.json, uma cena vira animação com:
    "visual": "animacao",
    "prompt_animacao": "lone man silhouette on a beach looking at a huge full moon",  (em inglês, sem texto)
    "efeito": "estrelas"          (neve | estrelas | poeira | brasas | chuva | nenhum; padrão: o da paleta)
Paleta (uma por vídeo, para todas as cenas animadas ficarem no mesmo tom): "paleta_animacao" no roteiro.json
(investigacao, reflexao, aprendizado, natureza, misterio, melancolia, epico); sem ela, a do canal.
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
# Estilo FIXO de todas as animações (pedido do dono: mesmo traço em qualquer cenário); só a paleta muda com o tom
ESTILO = (", minimalist flat vector illustration, simple geometric shapes and clean silhouettes, subtle paper grain, "
          "soft volumetric glow, limited color palette of {cores}, cinematic wide composition, "
          "no text, no letters, no watermark")

# Paletas pela psicologia das cores. "sombra/meio/luz" = mapa de cores aplicado por cima da imagem gerada (55%):
# a IA varia o colorido de uma imagem para outra; o mapa deixa o vídeo inteiro no mesmo tom.
PALETAS = {
    # crime, conspiração, segredo, investigação: vermelho escuro e preto (perigo, alerta, tensão)
    "investigacao": {"cores": "deep crimson red and near-black shadows", "sombra": (8, 4, 6), "meio": (92, 14, 22),
                     "luz": (236, 190, 170), "efeito": "poeira"},
    # livros, análise, filosofia (Le Disciple): âmbar e ocre neutros (sabedoria, calor, atenção calma)
    "reflexao": {"cores": "warm amber, muted ochre yellow and dark brown", "sombra": (22, 15, 8),
                 "meio": (150, 104, 40), "luz": (250, 228, 180), "efeito": "poeira"},
    # aprendizado, ciência, explicação: azul (confiança, clareza, foco)
    "aprendizado": {"cores": "deep navy blue and soft cyan", "sombra": (5, 10, 26), "meio": (34, 74, 140),
                    "luz": (210, 232, 255), "efeito": "estrelas"},
    # temas agradáveis, natureza, saúde, equilíbrio: verde (calma, crescimento)
    "natureza": {"cores": "deep forest green and soft mint", "sombra": (6, 18, 12), "meio": (40, 110, 70),
                 "luz": (215, 245, 220), "efeito": "poeira"},
    # mistérios, enigmas, o desconhecido: índigo e roxo (mistério, imaginação)
    "misterio": {"cores": "deep indigo and muted violet", "sombra": (10, 6, 24), "meio": (70, 44, 130),
                 "luz": (225, 210, 255), "efeito": "estrelas"},
    # perda, fim de uma era, despedida: azul-acinzentado sem saturação (tristeza, nostalgia)
    "melancolia": {"cores": "desaturated slate blue and cold grey", "sombra": (12, 14, 18), "meio": (78, 90, 108),
                   "luz": (220, 226, 232), "efeito": "neve"},
    # impérios, poder, guerra, grandeza: dourado e preto (poder, riqueza, drama)
    "epico": {"cores": "burnished gold, bronze and deep black", "sombra": (8, 6, 4), "meio": (120, 82, 30),
              "luz": (255, 222, 150), "efeito": "brasas"},
}
PREFIXO = ("Minimalist flat 2D vector illustration, paper-cut silhouette art: dark flat foreground silhouettes "
           "against a softly glowing gradient background, backlit, no realistic details: ")
PALETAS_CANAIS = {"imperios": "epico", "le-disciple": "reflexao"}  # quando o roteiro não escolhe
MISTURA_PALETA = 0.55


def paleta_do_roteiro(roteiro):
    """Paleta única do vídeo (todas as cenas animadas iguais): "paleta_animacao" do roteiro ou a do canal."""
    nome = roteiro.get("paleta_animacao") or PALETAS_CANAIS.get(roteiro.get("canal", ""), "aprendizado")
    return nome if nome in PALETAS else "aprendizado"


def aplicar_paleta(im, nome):
    from PIL import ImageOps
    p = PALETAS[nome]
    cinza = ImageOps.autocontrast(im.convert("L"), cutoff=1)
    mapa = ImageOps.colorize(cinza, black=p["sombra"], mid=p["meio"], white=p["luz"])
    final = Image.blend(im, mapa, MISTURA_PALETA)
    # Vinheta suave: bordas escuras em todas as cenas, para o vídeo parecer uma coisa só
    vinheta = Image.radial_gradient("L").resize(im.size).point(lambda v: int(255 - max(0, v - 90) * 0.9))
    return Image.composite(final, Image.new("RGB", im.size, p["sombra"]), vinheta)
EFEITOS = ("neve", "estrelas", "poeira", "brasas", "chuva", "nenhum")
ZOOM_FINAL = 1.07  # aproximação total ao longo da cena (lenta: não chama atenção, só dá vida)


def gerar_imagem(prompt, destino, semente, paleta="aprendizado"):
    """Ilustração plana 16:9. FLUX da NVIDIA se escolhido no .env; senão Pollinations (grátis, sem chave).

    Pollinations devolve 1024x576 com marca d'água no canto inferior direito: corta 9% de baixo e amplia (no estilo
    plano a ampliação não aparece)."""
    from . import visuais
    paleta = paleta if paleta in PALETAS else "aprendizado"
    # O estilo vem ANTES da cena: no fim do texto a IA às vezes ignorava e fazia foto realista (biblioteca clara)
    texto = PREFIXO + prompt + ESTILO.format(cores=PALETAS[paleta]["cores"])
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
    aplicar_paleta(im.crop((x, y, x + LARGURA, y + ALTURA)), paleta).save(destino, quality=93)
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


def _desenhar(d, efeito, ps, q, cor_luz=(255, 236, 200)):
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
            d.ellipse((p[0], p[1], p[0] + tam * 1.4, p[1] + tam * 1.4), fill=(*cor_luz, alfa))
        elif efeito == "brasas":
            p[1] = (y - vel * 0.9 / FPS) % ALTURA
            p[0] = (x + math.sin(q / 25 + fase) * 0.8) % LARGURA
            alfa = int(70 * tam * (0.5 + 0.5 * math.sin(q / 9 + fase)))
            d.ellipse((p[0], p[1], p[0] + tam, p[1] + tam), fill=(255, 140, 40, min(alfa, 230)))
        elif efeito == "chuva":
            p[1] = (y + vel * 6 / FPS) % ALTURA
            p[0] = (x + vel * 1.2 / FPS) % LARGURA
            d.line((p[0], p[1], p[0] - tam * 2, p[1] - tam * 9), fill=(200, 215, 255, int(30 * tam)), width=1)


def renderizar(imagem, destino, duracao, efeito="poeira", semente=0, paleta=None):
    """Vídeo mudo de `duracao` s a partir da ilustração (sem faixas nem texto: entram na edição)."""
    if efeito not in EFEITOS:
        efeito = PALETAS[paleta]["efeito"] if paleta in PALETAS else "poeira"
    cor_luz = PALETAS[paleta]["luz"] if paleta in PALETAS else (255, 236, 200)
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
                _desenhar(ImageDraw.Draw(cam), efeito, ps, q, cor_luz)
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
    base_y = ALTURA - (FAIXA_CINEMA + 60 if faixas else 170)  # sem faixas: acima da legenda
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
