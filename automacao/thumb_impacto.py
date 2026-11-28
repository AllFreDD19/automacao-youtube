"""Thumbnails no estilo "impacto" (referências do dono: MrBeast, GameplayRJ), sem custo.

O que esses canais fazem e esta ferramenta reproduz:
- UM foco gigante (rosto expressivo ou objeto), recortado e com contorno claro + brilho, que salta do fundo;
- fundo simples, saturado e um pouco desfocado (cenário do tema), com vinheta;
- 1 a 3 palavras ENORMES (fonte grossa, contorno preto grosso), que NÃO repetem o título;
- cores complementares fortes (amarelo/laranja sobre azul/escuro), sem o vermelho/branco do próprio YouTube;
- legível em ~168x94 (tamanho no celular); nada importante no canto inferior direito (tempo do vídeo).

Regras do canal: rosto só de personagem GENÉRICO (soldado, camponês), nunca de pessoa real em imagem fabricada;
sem promessa falsa (o YouTube testa as thumbs pelo tempo assistido, clickbait perde).

O foco é gerado sobre fundo liso e recortado com o rembg (modelo local grátis).
Fontes: Pollinations (grátis). No Windows, com IMAGEM_PROVEDOR=nvidia, o FLUX dá imagens mais nítidas.

Uso (python -m automacao.thumb_impacto <projeto> --conceitos conceitos.json) ou pelas funções:
  rosto(...)       rosto/personagem expressivo de um lado + cenário + texto do outro
  objeto(...)      objeto-símbolo no centro (coroa, espada...) + texto
  antes_depois(...) duas cenas lado a lado com seta
"""
import io
import json
import sys
import time
import urllib.parse
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from . import config

L, A = 1280, 720
AMARELO, LARANJA, AZUL_CLARO, BRANCO = (255, 221, 0), (255, 140, 0), (90, 200, 255), (255, 255, 255)
CORES = {"amarelo": AMARELO, "laranja": LARANJA, "azul": AZUL_CLARO, "branco": BRANCO}


# ---------------------------------------------------------------- imagens

def ia(prompt, largura=1280, altura=720, semente=1, verde=False):
    """Imagem do Pollinations (ou FLUX no Windows). verde=True: personagem/objeto isolado em fundo verde."""
    if verde:
        prompt += ", isolated on a plain light grey studio background, sharp edges, studio lighting"
    prompt += ", ultra detailed, vivid saturated colors, high contrast, no text, no watermark"
    if config.NVIDIA_API_KEY and config.IMAGEM_PROVEDOR == "nvidia":
        try:
            from . import visuais
            dados = visuais.flux_nvidia({"prompt": prompt, "mode": "base", "cfg_scale": 3.5, "steps": 30,
                                         "width": 1024 if altura > largura else 1344,
                                         "height": 1344 if altura > largura else 768})
            return Image.open(io.BytesIO(dados)).convert("RGB")
        except Exception as e:  # noqa: BLE001
            print(f"  FLUX falhou ({e.__class__.__name__}), usando Pollinations")
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
           + f"?width={largura}&height={altura}&nologo=true&model=flux&seed={semente}")
    for tentativa in range(5):
        try:
            r = requests.get(url, timeout=240)
            if r.ok and r.headers.get("content-type", "").startswith("image/"):
                im = Image.open(io.BytesIO(r.content)).convert("RGB")
                return im.crop((0, 0, im.width, int(im.height * 0.92)))  # marca d'água embaixo à direita
        except requests.RequestException:
            pass
        time.sleep(15 * (tentativa + 1))
    raise RuntimeError("Pollinations não respondeu")


_sessao_rembg = None


def recortar(im):
    """Tira o fundo do personagem/objeto: rembg (modelo local grátis, ~180 MB baixados uma vez); sem ele, o
    recorte por fundo verde (pior: a IA nem sempre faz o verde puro)."""
    global _sessao_rembg
    try:
        from rembg import new_session, remove
        if _sessao_rembg is None:
            _sessao_rembg = new_session("isnet-general-use")
        saida = remove(im, session=_sessao_rembg)
        alfa = saida.getchannel("A").point(lambda v: 0 if v < 25 else v)
        saida.putalpha(alfa)
        caixa = alfa.point(lambda v: 255 if v > 40 else 0).getbbox()
        return saida.crop(caixa) if caixa else saida
    except ImportError:
        print("  rembg não instalado (pip install rembg[cpu]); usando recorte por verde")
        return recortar_verde(im)


def recortar_verde(im):
    """Fundo verde -> transparente, com borda suavizada e sem 'vazamento' verde no contorno."""
    a = np.asarray(im.convert("RGB")).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    verde = (g > 90) & (g > r + 35) & (g > b + 35)
    alfa = Image.fromarray(np.where(verde, 0, 255).astype(np.uint8))
    alfa = alfa.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MedianFilter(7)).filter(ImageFilter.GaussianBlur(1.2))
    g2 = np.minimum(g, np.maximum(r, b) + 10)  # tira o reflexo verde da borda
    rgb = np.stack([r, g2, b], -1).clip(0, 255).astype(np.uint8)
    saida = Image.fromarray(rgb).convert("RGBA")
    saida.putalpha(alfa)
    caixa = alfa.point(lambda v: 255 if v > 40 else 0).getbbox()
    return saida.crop(caixa) if caixa else saida


def realcar(im, saturacao=1.35, contraste=1.15, brilho=1.05):
    im = ImageEnhance.Color(im).enhance(saturacao)
    im = ImageEnhance.Contrast(im).enhance(contraste)
    return ImageEnhance.Brightness(im).enhance(brilho)


def cobrir(im, largura=L, altura=A, foco_x=0.5):
    r = max(largura / im.width, altura / im.height)
    im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
    x = int((im.width - largura) * foco_x)
    y = (im.height - altura) // 2
    return im.crop((x, y, x + largura, y + altura))


def fundo(im, desfoque=3, escurecer=0.85, foco_x=0.5):
    base = realcar(cobrir(im, foco_x=foco_x), 1.4, 1.2, escurecer).filter(ImageFilter.GaussianBlur(desfoque))
    # Vinheta: bordas escuras puxam o olho para o centro
    vin = Image.radial_gradient("L").resize((L, A)).point(lambda v: min(255, int(v * 1.25)))
    preto = Image.new("RGB", (L, A))
    return Image.composite(preto, base, vin.point(lambda v: int(v * 0.75)))


def colar_com_contorno(tela, sujeito, x, y, altura, cor=BRANCO, espessura=10, brilho=(255, 200, 60)):
    """Sujeito recortado com contorno grosso e um brilho atrás (o 'sticker' típico dessas thumbs)."""
    r = altura / sujeito.height
    s = realcar(sujeito.resize((int(sujeito.width * r), altura), Image.LANCZOS).convert("RGBA"), 1.25, 1.12, 1.05)
    alfa = s.getchannel("A")
    pad = espessura * 4
    alfa_g = Image.new("L", (s.width + 2 * pad, s.height + 2 * pad))
    alfa_g.paste(alfa, (pad, pad))
    contorno = alfa_g.filter(ImageFilter.MaxFilter(espessura * 2 + 1))
    halo = alfa_g.filter(ImageFilter.MaxFilter(espessura * 4 + 1)).filter(ImageFilter.GaussianBlur(espessura * 2))
    camada = Image.new("RGBA", alfa_g.size)
    camada.paste(Image.new("RGBA", alfa_g.size, brilho + (230,)), (0, 0), halo)
    camada.paste(Image.new("RGBA", alfa_g.size, cor + (255,)), (0, 0), contorno)
    camada.alpha_composite(s, (pad, pad))
    tela.alpha_composite(camada, (int(x - pad), int(y - pad)))
    return (int(x), int(y), int(x + s.width), int(y + s.height))


# ---------------------------------------------------------------- texto e setas

def _fonte(tamanho):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(str(config.FONTE_TITULO), tamanho)
    except OSError:
        return config.fonte_texto(tamanho, True)


def texto_grande(tela, linhas, x, y, largura_max, cores=None, inclinacao=-3, caixa_ultima=None):
    """Palavras enormes com contorno preto grosso e sombra; cada linha ocupa a largura disponível.
    caixa_ultima=(r,g,b): a última linha vai dentro de uma tarja colorida (destaque)."""
    cores = cores or [BRANCO] * (len(linhas) - 1) + [AMARELO]
    camada = Image.new("RGBA", tela.size)
    d = ImageDraw.Draw(camada)
    for i, (txt, cor) in enumerate(zip(linhas, cores)):
        tam = 260
        while tam > 40:
            f = _fonte(tam)
            if d.textlength(txt, font=f) <= largura_max:
                break
            tam -= 6
        caixa = d.textbbox((0, 0), txt, font=f)
        alt = caixa[3] - caixa[1]
        borda = max(8, tam // 11)
        if caixa_ultima and i == len(linhas) - 1:
            d.rounded_rectangle((x - 14, y - 6, x + caixa[2] + 14, y + alt + 18), radius=14, fill=caixa_ultima + (255,))
        d.text((x + 8, y - caixa[1] + 10), txt, font=f, fill=(0, 0, 0, 160), stroke_width=borda, stroke_fill=(0, 0, 0, 160))
        d.text((x, y - caixa[1]), txt, font=f, fill=cor, stroke_width=borda, stroke_fill=(0, 0, 0))
        y += alt + 22
    if inclinacao:
        camada = camada.rotate(inclinacao, resample=Image.BICUBIC, center=(x, y))
    tela.alpha_composite(camada)
    return y


def seta(tela, de, ate, cor=AMARELO, grossura=26):
    """Seta grossa com contorno preto (aponta para o detalhe que importa)."""
    import math
    d = ImageDraw.Draw(tela)
    ang = math.atan2(ate[1] - de[1], ate[0] - de[0])
    ponta = 3.2 * grossura
    base = (ate[0] - ponta * math.cos(ang), ate[1] - ponta * math.sin(ang))
    lado = (ponta * 0.6 * math.sin(ang), ponta * 0.6 * math.cos(ang))
    tri = [ate, (base[0] + lado[0], base[1] - lado[1]), (base[0] - lado[0], base[1] + lado[1])]
    d.line([de, base], fill=(0, 0, 0), width=grossura + 14)
    d.polygon(tri, fill=(0, 0, 0), outline=(0, 0, 0), width=8)
    d.line([de, base], fill=cor, width=grossura)
    d.polygon(tri, fill=cor)


# ---------------------------------------------------------------- modelos de thumbnail

def rosto(destino, cenario, personagem, linhas, lado="direita", semente=1, cores=None, caixa=None):
    """Personagem genérico expressivo (recortado) de um lado, cenário atrás, palavras do outro lado."""
    tela = fundo(ia(cenario, semente=semente), foco_x=0.5).convert("RGBA")
    suj = recortar(ia(personagem, 832, 1024, semente=semente + 7, verde=True))
    altura = int(A * 1.02)
    largura = int(suj.width * altura / suj.height)
    x = L - largura + 30 if lado == "direita" else -30
    colar_com_contorno(tela, suj, x, A - altura + 40, altura)
    tx = 50 if lado == "direita" else L - 50 - int(L * 0.5)
    texto_grande(tela, linhas, tx, 90, int(L * 0.5), cores=cores, caixa_ultima=caixa)
    return _salvar(tela, destino)


def objeto(destino, cenario, coisa, linhas, semente=1, cores=None, caixa=None):
    """Objeto-símbolo grande à direita (com brilho), cenário atrás, texto à esquerda."""
    tela = fundo(ia(cenario, semente=semente), desfoque=4).convert("RGBA")
    suj = recortar(ia(coisa, 1024, 1024, semente=semente + 3, verde=True))
    # Objeto largo (canhão, navio) não pode passar de ~metade da thumb, senão cobre o texto
    altura = min(int(A * 0.82), int(L * 0.5 * suj.height / suj.width))
    colar_com_contorno(tela, suj, L - int(suj.width * altura / suj.height) - 40, (A - altura) // 2, altura,
                       cor=AMARELO, brilho=(255, 120, 0))
    texto_grande(tela, linhas, 50, 120, int(L * 0.52), cores=cores, caixa_ultima=caixa)
    return _salvar(tela, destino)


def antes_depois(destino, cena_antes, cena_depois, linha_antes, linha_depois, semente=1):
    """Duas metades (glória x ruína) separadas por uma faixa, com rótulos e seta."""
    tela = Image.new("RGBA", (L, A))
    esq = realcar(cobrir(ia(cena_antes, semente=semente), L // 2, A), 1.45, 1.2)
    dir_ = realcar(cobrir(ia(cena_depois, semente=semente + 1), L // 2, A), 1.2, 1.25, 0.8)
    tela.paste(esq, (0, 0))
    tela.paste(dir_, (L // 2, 0))
    d = ImageDraw.Draw(tela)
    d.polygon([(L // 2 - 14, 0), (L // 2 + 14, 0), (L // 2 + 14, A), (L // 2 - 14, A)], fill=(0, 0, 0))
    texto_grande(tela, [linha_antes], 40, 40, L // 2 - 80, cores=[AMARELO], inclinacao=0)
    texto_grande(tela, [linha_depois], L // 2 + 40, 40, L // 2 - 80, cores=[AZUL_CLARO], inclinacao=0)
    seta(tela, (L // 2 - 150, A - 170), (L // 2 + 170, A - 170))
    return _salvar(tela, destino)


def _salvar(tela, destino):
    final = tela.convert("RGB")
    final.save(destino, quality=95)
    # Prévia do tamanho no celular, para conferir se as palavras ainda se leem
    final.resize((168, 94), Image.LANCZOS).save(Path(destino).with_name(Path(destino).stem + "_celular.png"))
    return destino


if __name__ == "__main__":
    # python -m automacao.thumb_impacto projetos/<pasta> conceitos.json
    pasta, conceitos = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    for i, c in enumerate(conceitos, 1):
        tipo = c.pop("tipo")
        destino = pasta / f"thumb_impacto_{i}.jpg"
        {"rosto": rosto, "objeto": objeto, "antes_depois": antes_depois}[tipo](destino, **c)
        print(destino)


# ---------------------------------------------------------------- estilo "épico" (padrão do Impérios Caídos)
# Referência do dono (thumb do próprio canal, 2026-11-21): cena de cinema realista na thumb inteira, personagem
# grande de um lado integrado ao cenário, noite azulada com pontos de luz quente; do outro lado, fonte serifada
# épica: 1a linha dourada metálica com reticências, linhas seguintes prateadas, ornamento dourado embaixo.
FONTE_EPICA = config.PASTA_FONTES / "Cinzel-Black.ttf"
OURO = [(255, 246, 190), (255, 214, 90), (214, 150, 30), (150, 92, 18)]
PRATA = [(255, 255, 255), (236, 238, 242), (190, 196, 206), (150, 156, 168)]


# Estilos de texto das thumbs épicas (pedido do dono em 2026-11-22: as thumbs estavam parecidas demais). Cada opção
# de um vídeo usa um estilo diferente e a combinação muda de vídeo para vídeo. Fontes do Google Fonts (OFL, fontes/).
ESTILOS_EPICOS = {
    "imperial": {"fonte": "Cinzel-Black.ttf", "l1": OURO, "l2": PRATA, "c1": (40, 22, 6), "c2": (20, 22, 28), "orn": (232, 178, 60)},
    "fogo": {"fonte": "PlayfairDisplay-Black.ttf", "l1": [(255, 244, 190), (255, 176, 40), (226, 78, 22), (128, 24, 10)],
             "l2": [(255, 250, 236), (240, 226, 196), (206, 186, 150)], "c1": (50, 10, 4), "c2": (40, 18, 8), "orn": (255, 140, 40)},
    "gelo": {"fonte": "Oswald-Bold.ttf", "l1": [(244, 252, 255), (156, 214, 255), (62, 142, 222), (24, 70, 140)],
             "l2": [(255, 255, 255), (222, 232, 244), (176, 190, 210)], "c1": (6, 18, 40), "c2": (8, 16, 30), "orn": (140, 200, 255)},
    "sangue": {"fonte": "CinzelDecorative-Black.ttf", "l1": [(255, 206, 196), (224, 44, 44), (142, 12, 16), (70, 4, 8)],
               "l2": OURO, "c1": (30, 2, 4), "c2": (40, 22, 6), "orn": (232, 178, 60)},
    "bronze": {"fonte": "Marcellus-Regular.ttf", "l1": [(255, 240, 214), (250, 186, 120), (214, 128, 64), (150, 76, 32)],
               "l2": [(255, 252, 240), (238, 230, 210), (200, 188, 160)], "c1": (40, 16, 4), "c2": (36, 26, 14), "orn": (214, 130, 70)},
    "manchete": {"fonte": "BebasNeue-Regular.ttf", "l1": [(255, 248, 170), (255, 222, 40), (240, 180, 0)],
                 "l2": [(255, 255, 255), (236, 236, 236)], "c1": (20, 14, 0), "c2": (10, 10, 10), "orn": (255, 214, 0)},
    "classico": {"fonte": "AbrilFatface-Regular.ttf", "l1": [(232, 255, 224), (126, 206, 126), (40, 122, 72), (14, 60, 34)],
                 "l2": OURO, "c1": (6, 28, 14), "c2": (40, 22, 6), "orn": (232, 178, 60)},
}
_fonte_atual = [FONTE_EPICA]


def _fonte_epica(tamanho):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(str(_fonte_atual[0]), tamanho)
    except OSError:
        return _fonte(tamanho)


def _degrade(largura, altura, cores):
    """Degradê vertical por várias cores (efeito metálico)."""
    img = Image.new("RGB", (1, len(cores)))
    for i, c in enumerate(cores):
        img.putpixel((0, i), c)
    return img.resize((largura, altura), Image.BICUBIC)


def _linha_metalica(tela, txt, cx, y, tamanho, cores, contorno=(40, 22, 6)):
    """Texto centrado em cx com degradê metálico, contorno escuro, brilho no topo e sombra. Devolve a altura."""
    f = _fonte_epica(tamanho)
    d0 = ImageDraw.Draw(tela)
    caixa = d0.textbbox((0, 0), txt, font=f, stroke_width=max(3, tamanho // 22))
    w, h = caixa[2] - caixa[0] + 20, caixa[3] - caixa[1] + 20
    x = int(cx - w / 2)
    borda = max(3, tamanho // 22)
    mascara = Image.new("L", (w, h))
    ImageDraw.Draw(mascara).text((10 - caixa[0], 10 - caixa[1]), txt, font=f, fill=255)
    contorno_m = Image.new("L", (w, h))
    ImageDraw.Draw(contorno_m).text((10 - caixa[0], 10 - caixa[1]), txt, font=f, fill=255,
                                    stroke_width=borda, stroke_fill=255)
    # Sombra larga e suave (descola do fundo)
    sombra = Image.new("RGBA", (w + 60, h + 60))
    sombra.paste(Image.new("RGBA", (w, h), (0, 0, 0, 230)), (36, 40), contorno_m.filter(ImageFilter.MaxFilter(5)))
    tela.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(10)), (x - 30, y - 30))
    camada = Image.new("RGBA", (w, h))
    camada.paste(Image.new("RGBA", (w, h), contorno + (255,)), (0, 0), contorno_m)
    metal = _degrade(w, h, cores).convert("RGBA")
    camada.paste(metal, (0, 0), mascara)
    # Brilho fino na parte de cima das letras (parece relevo)
    topo = ImageChops.subtract(mascara, mascara.transform(mascara.size, Image.AFFINE, (1, 0, 0, 0, 1, -3)))
    camada.paste(Image.new("RGBA", (w, h), (255, 255, 240, 160)), (0, 0), topo.filter(ImageFilter.GaussianBlur(0.6)))
    tela.alpha_composite(camada, (x, y))
    return h


def _ornamento(tela, cx, y, largura, cor=(232, 178, 60)):
    """Linha dourada fina com uma estrela de quatro pontas no meio."""
    d = ImageDraw.Draw(tela)
    for lado in (-1, 1):
        for k in range(0, largura // 2 - 30, 2):
            alfa = int(255 * (1 - k / (largura / 2)))
            px = cx + lado * (30 + k)
            d.line([(px, y), (px + lado * 2, y)], fill=cor + (alfa,), width=3)
    r = 22
    d.polygon([(cx, y - r), (cx + 6, y - 6), (cx + r, y), (cx + 6, y + 6), (cx, y + r), (cx - 6, y + 6),
               (cx - r, y), (cx - 6, y - 6)], fill=cor + (255,), outline=(70, 40, 8))


def gradacao_cinema(im, suave=False):
    """Sombras azul-petróleo e luzes quentes (o look de filme da referência), mais nitidez e vinheta leve.
    Imagem escura (o gerador às vezes entrega noite fechada) ganha exposição antes."""
    if suave:  # imagem do AI Horde já vem com cor de cinema: só nitidez e vinheta leve
        im = realcar(im, 1.06, 1.06, 1.0).filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=3))
        vin = Image.radial_gradient("L").resize(im.size).point(lambda v: int(min(255, v * 1.1) * 0.4))
        return Image.composite(Image.new("RGB", im.size), im, vin)
    media = np.asarray(im.convert("L")).mean()
    if media < 95:
        im = ImageEnhance.Brightness(im).enhance(min(1.8, 95 / max(media, 20)))
    im = realcar(im, 1.15, 1.18, 1.0)
    cinza = ImageOps.grayscale(im)
    sombras = Image.new("RGB", im.size, (20, 48, 78))
    luzes = Image.new("RGB", im.size, (255, 196, 120))
    im = Image.composite(im, Image.blend(im, sombras, 0.22), cinza.point(lambda v: min(255, v * 2)))
    im = Image.composite(Image.blend(im, luzes, 0.12), im, cinza.point(lambda v: max(0, (v - 150) * 2)))
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=130, threshold=2))
    vin = Image.radial_gradient("L").resize(im.size).point(lambda v: int(min(255, v * 1.15) * 0.5))
    return Image.composite(Image.new("RGB", im.size), im, vin)


def _enquadrar_personagem(im, lado_pessoa, alvo=0.28):
    """Corta a cena larga em 16:9 pondo o personagem principal (achado pelo rembg) a ~28% da borda do seu lado.
    Se ele nasceu do lado do texto, a imagem é espelhada antes (cena sem letras: espelhar não estraga nada)."""
    r = A / im.height
    im = im.resize((int(im.width * r) + 1, A), Image.LANCZOS)

    def centro(img):
        try:
            alfa = np.asarray(recortar_mascara(img)).astype(float)
            cols = alfa.sum(axis=0)
            return float((cols * np.arange(len(cols))).sum() / max(cols.sum(), 1))
        except Exception:  # noqa: BLE001
            return img.width / 2
    cx = centro(im)
    if (lado_pessoa == "left" and cx > im.width * 0.5) or (lado_pessoa == "right" and cx < im.width * 0.5):
        im, cx = ImageOps.mirror(im), im.width - cx
    if im.width <= L:
        return cobrir(im)
    destino_x = alvo * L if lado_pessoa == "left" else (1 - alvo) * L
    x0 = int(min(max(cx - destino_x, 0), im.width - L))
    return im.crop((x0, 0, x0 + L, A))


def recortar_mascara(im):
    from rembg import new_session, remove
    global _sessao_rembg
    if _sessao_rembg is None:
        _sessao_rembg = new_session("isnet-general-use")
    return remove(im, session=_sessao_rembg, only_mask=True)


def _personagem_integrado(tela_rgb, personagem, lado_pessoa, semente):
    """Personagem gerado à parte, recortado (rembg) e posto grande do lado certo, com luz de contorno suave e
    sombra difusa, para parecer parte da cena (não um adesivo)."""
    suj = recortar(ia(personagem + ", medium shot from the waist up, plain simple background, face lit by warm "
                      "light, cinematic", 832, 1024, semente=semente + 5))
    altura = int(A * 0.98)
    s = suj.resize((int(suj.width * altura / suj.height), altura), Image.LANCZOS)
    if s.width > int(L * 0.55):  # muito largo: limita e mantém a base no chão
        r = L * 0.55 / s.width
        s = s.resize((int(s.width * r), int(s.height * r)), Image.LANCZOS)
    x = int(L * 0.02) if lado_pessoa == "left" else L - s.width - int(L * 0.02)
    y = A - s.height + 6
    base = tela_rgb.convert("RGBA")
    alfa = s.getchannel("A")
    halo = Image.new("L", (s.width + 80, s.height + 80))
    halo.paste(alfa, (40, 40))
    sombra = Image.new("RGBA", halo.size, (0, 0, 0, 0))
    sombra.paste(Image.new("RGBA", halo.size, (0, 0, 0, 170)), (0, 0), halo.filter(ImageFilter.GaussianBlur(25)))
    base.alpha_composite(sombra, (x - 40 + 12, y - 40 + 10))
    luz = Image.new("RGBA", halo.size, (0, 0, 0, 0))
    luz.paste(Image.new("RGBA", halo.size, (255, 190, 110, 120)), (0, 0),
              halo.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(10)))
    base.alpha_composite(luz, (x - 40, y - 40))
    base.alpha_composite(s, (x, y))
    return base.convert("RGB")


# AI Horde (aihorde.net): rede comunitária grátis, sem cadastro (chave anônima "0000000000"; com conta grátis a fila
# anda mais rápido: AI_HORDE_KEY no .env). Juggernaut XL dá cenas de cinema realistas, bem mais naturais que o
# Pollinations, que em 2026-11-21 só oferecia o modelo "sana". ~5 min por imagem na fila anônima.
HORDE = "https://aihorde.net/api/v2"
HORDE_MODELO = "Juggernaut XL"
NEGATIVO = ("cartoon, anime, illustration, painting, 3d render, text, letters, watermark, logo, deformed, extra fingers, "
            "extra limbs, blurry face, modern clothes, sunglasses")


def ia_horde_lote(prompts, largura=1536, altura=640, passos=30, limite_s=1800, fontes=None, forca=0.55):
    """Pede todas as imagens de uma vez ao AI Horde e espera; devolve uma lista de PIL.Image (None se falhou).
    fontes: lista (mesmo tamanho de prompts) de imagens de partida (img2img; None = só texto); forca = quanto a IA
    pode mudar a imagem de partida (0.3 quase igual, 0.7 muda muito; o rosto se perde acima de ~0.5)."""
    import os
    cab = {"apikey": os.getenv("AI_HORDE_KEY") or "0000000000", "Client-Agent": f"automacao-youtube:1.1:{config.USER_AGENT.split('(')[1].split(')')[0]}"}
    ids = []
    for k, pr in enumerate(prompts):
        corpo = {"prompt": f"{pr} ### {NEGATIVO}", "models": [HORDE_MODELO], "r2": True, "nsfw": False,
                 "censor_nsfw": True, "params": {"width": largura, "height": altura, "steps": passos, "cfg_scale": 6,
                                                 "sampler_name": "k_euler_a", "n": 1}}
        if fontes and fontes[k] is not None:
            import base64
            buf = io.BytesIO()
            Image.open(fontes[k]).convert("RGB").resize((largura, altura)).save(buf, "WEBP", quality=92)
            corpo["source_image"] = base64.b64encode(buf.getvalue()).decode()
            corpo["source_processing"] = "img2img"
            corpo["params"]["denoising_strength"] = forca
        try:
            r = requests.post(f"{HORDE}/generate/async", json=corpo, headers=cab, timeout=60)
            ids.append(r.json().get("id") if r.ok else None)
            if not r.ok:
                print(f"  AI Horde recusou: {r.status_code} {r.text[:150]}")
        except requests.RequestException:
            ids.append(None)
    t0, prontos = time.time(), {}
    while time.time() - t0 < limite_s and len(prontos) < sum(1 for i in ids if i):
        time.sleep(15)
        for i in ids:
            if not i or i in prontos:
                continue
            try:
                c = requests.get(f"{HORDE}/generate/check/{i}", headers=cab, timeout=30).json()
            except (requests.RequestException, ValueError):
                continue
            if c.get("faulted"):
                prontos[i] = None
            elif c.get("done"):
                try:
                    st = requests.get(f"{HORDE}/generate/status/{i}", headers=cab, timeout=60).json()
                    url = st["generations"][0]["img"]
                    prontos[i] = Image.open(io.BytesIO(requests.get(url, timeout=120).content)).convert("RGB")
                except Exception:  # noqa: BLE001
                    prontos[i] = None
        print(f"  AI Horde: {sum(1 for v in prontos.values() if v)} de {len(prompts)} prontas "
              f"({int(time.time() - t0)} s)", flush=True)
    return [prontos.get(i) if i else None for i in ids]


def epicos(pasta, opcoes, lado_texto="direita", numeros=None, estilos=None):
    """Várias opções de thumb épica de uma vez (todas as cenas pedidas juntas ao AI Horde).
    opcoes: [{"cena": "...", "ouro": "MIL AÑOS...", "prata": ["Y CAYÓ EN", "UNA MAÑANA"]}, ...]"""
    lado_pessoa = "left" if lado_texto == "direita" else "right"
    prompts = [("cinematic film still, " + o["cena"] + f", the main character on the {lado_pessoa} side of the frame, "
                "medium shot from the waist up, face clearly visible and lit by warm light, other people and the "
                "setting visible behind, teal and orange color grade, dramatic rim light, shallow depth of field, "
                "photorealistic, highly detailed") for o in opcoes]
    imagens = ia_horde_lote(prompts)
    saidas = []
    numeros = numeros or list(range(1, len(opcoes) + 1))
    for n, o, im, pr in zip(numeros, opcoes, imagens, prompts):
        if im is None:
            print(f"  opção {n}: AI Horde falhou, usando Pollinations")
            im = ia(pr, 1680, 720, semente=n)
        destino = Path(pasta) / f"thumb_epica_{n}.jpg"
        im.save(Path(pasta) / f"thumb_epica_{n}_cena.jpg", quality=95)  # para reajustar texto sem gerar de novo
        # Estilos diferentes em cada opção, e começando num ponto diferente para cada vídeo
        nomes = list(ESTILOS_EPICOS)
        base = sum(map(ord, Path(pasta).name)) % len(nomes)
        estilo = (estilos[n - 1] if estilos and n - 1 < len(estilos) else o.get("estilo")) or nomes[(base + 3 * (n - 1)) % len(nomes)]
        epico(destino, o["cena"], o["ouro"], o["prata"], lado_texto, imagem=im, estilo=estilo)
        saidas.append(destino)
    return saidas


def epico(destino, cena, linha_ouro, linhas_prata, lado_texto="direita", semente=1, personagem=None, imagem=None,
          estilo="imperial"):
    """Thumb no estilo do canal: cena inteira + personagem grande do lado oposto ao texto + texto épico metálico.
    imagem: cena já gerada (AI Horde); personagem: GENÉRICO, gerado à parte e recortado (nunca pessoa real)."""
    lado_pessoa = "left" if lado_texto == "direita" else "right"
    if imagem is not None:
        # Cena inteira de uma vez (o mais natural, como a referência): só enquadra e dá o acabamento leve
        tela = gradacao_cinema(_enquadrar_personagem(imagem, lado_pessoa), suave=True).convert("RGBA")
    elif personagem:
        fundo_ = cobrir(ia(cena + ", wide establishing shot, no people in the foreground, cinematic film still, "
                           "dramatic light, highly detailed", semente=semente))
        tela = gradacao_cinema(_personagem_integrado(fundo_, personagem, lado_pessoa, semente)).convert("RGBA")
    else:
        prompt = (cena + ", medium shot from the waist up, the main character occupies about a third of the frame "
                  "with the face clearly visible and lit by warm light, cinematic film still, dramatic rim light, "
                  "teal and orange color grade, shallow depth of field, highly detailed")
        # Cena mais larga que 16:9: margem para pôr o personagem do lado certo
        tela = gradacao_cinema(_enquadrar_personagem(ia(prompt, 1680, 720, semente=semente), lado_pessoa)).convert("RGBA")
    # Escurece levemente o lado do texto para as letras saltarem
    grad = Image.linear_gradient("L").rotate(90 if lado_texto == "direita" else -90).resize((L, A))
    escuro = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    escuro.putalpha(grad.point(lambda v: int(max(0, v - 110) * 0.9)))
    tela.alpha_composite(escuro)
    cx = int(L * 0.72) if lado_texto == "direita" else int(L * 0.28)
    largura = int(L * 0.5)
    # Tamanhos: a linha dourada é a maior; as prateadas ~65% dela, todas cabendo na largura
    d = ImageDraw.Draw(tela)

    def cabe(txt, maximo):
        t = maximo
        while t > 30 and d.textlength(txt, font=_fonte_epica(t)) > largura:
            t -= 4
        return t
    est = ESTILOS_EPICOS.get(estilo, ESTILOS_EPICOS["imperial"])
    _fonte_atual[0] = config.PASTA_FONTES / est["fonte"]
    t_ouro = cabe(linha_ouro, 170)
    t_prata = min(cabe(l, int(t_ouro * 0.72)) for l in linhas_prata) if linhas_prata else 0
    altura_total = t_ouro * 1.15 + len(linhas_prata) * t_prata * 1.12 + 50
    y = int(A * 0.5 - altura_total / 2)
    y += _linha_metalica(tela, linha_ouro, cx, y, t_ouro, est["l1"], contorno=est["c1"]) - 6
    for l in linhas_prata:
        y += _linha_metalica(tela, l, cx, y, t_prata, est["l2"], contorno=est["c2"]) - 8
    _ornamento(tela, cx, y + 24, int(largura * 0.92), cor=est["orn"])
    print(f"  {Path(destino).name}: estilo {estilo}")
    return _salvar(tela, destino)


# ---------------------------------------------------------------- estilo "disciple" (Le Disciple du Savoir)
# Pedido do dono (2026-11-23): o personagem tem que ser EXATAMENTE o Disciple criado para o canal (sábio de barba
# grisalha, manto escuro). Gerador grátis não repete um rosto, então a thumb usa SEMPRE uma imagem real do personagem
# (biblioteca/disciple/): o lado dele fica intacto e o outro lado recebe um fundo de biblioteca à luz de velas (AI Horde,
# sem pessoas), fundido em degradê. Texto como nas referências: palavra grande dourada metálica (Cinzel Black),
# ornamento dourado e o nome do autor/tema em prateado espaçado embaixo.
PASTA_DISCIPLE = config.RAIZ / "biblioteca" / "disciple"
# Versão curta (cabe no limite de ~75 palavras do SDXL) do prompt fixo do personagem: biblioteca/disciple/personagem.md
DISCIPLE_PROMPT = ("photo of a mature European scholar about 60 years old, long oval face, high wrinkled forehead, "
                   "thick curly dark-brown hair with heavy silver at the temples, thick dark eyebrows, deep-set "
                   "hazel-green eyes, straight slightly broad nose, dense curly salt-and-pepper beard and thick "
                   "mustache, weathered olive skin with pores and wrinkles, calm intelligent penetrating gaze")
FUNDO_DISCIPLE = ("dark old library at night lit by candles, shelves of antique leather books, a marble bust of a "
                  "philosopher in the shadows, brass armillary sphere, warm golden candle light, dust in the air, "
                  "no people, cinematic, photorealistic, highly detailed")


def fundos_disciple(qtd=3):
    """Gera (uma vez) fundos de biblioteca sem pessoas em biblioteca/disciple/fundos/."""
    pasta = PASTA_DISCIPLE / "fundos"
    pasta.mkdir(parents=True, exist_ok=True)
    existentes = sorted(pasta.glob("fundo_*.jpg"))
    if len(existentes) >= qtd:
        return existentes
    imgs = ia_horde_lote([FUNDO_DISCIPLE + f", variation {i}" for i in range(qtd - len(existentes))], 1344, 768)
    for i, im in enumerate(imgs):
        if im is not None:
            im.save(pasta / f"fundo_{len(existentes) + i + 1}.jpg", quality=95)
    return sorted(pasta.glob("fundo_*.jpg"))


def _espacado(txt):
    return " ".join(txt)


def disciple(destino, personagem, palavra, autor=None, lado_texto="esquerda", fundo=None, inicio=0.42, fim=0.58,
             y_centro=0.5, tom=None, area=None, so_imagem=False, estilo="imperial"):
    """personagem: imagem do Disciple (o lado dele é mantido como está); lado_texto: onde vai o texto (o lado
    oposto ao personagem). palavra: 1-2 palavras grandes em dourado (pode ter quebra com '\\n'); autor: linha
    prateada pequena (ex.: 'SÉNÈQUE'). Linha que começa com '~' sai prateada (ex.: '~LE CARNET SECRET\nDE
    L'EMPEREUR'). y_centro: altura do bloco de texto (0.3 = terço de cima). tom: cor (r, g, b) misturada nas sombras
    para dar o clima do tema (ex.: (70, 20, 90) = púrpura imperial). area: (x0, y0, x1, y1) em frações: troca só
    esse retângulo (bordas esfumadas) pelo fundo novo, para não cortar mão ou ombro que invadem o lado do texto."""
    base = cobrir(Image.open(personagem).convert("RGB"))
    if fundo:
        f = cobrir(Image.open(fundo).convert("RGB"))
        f = ImageEnhance.Brightness(f).enhance(0.72)  # o fundo novo fica no tom escuro das imagens do personagem
        if lado_texto == "direita":
            f = f.transpose(Image.FLIP_LEFT_RIGHT)
        # máscara: 255 = fundo novo (lado do texto), 0 = imagem do personagem; degradê no meio
        grad = Image.linear_gradient("L").rotate(90).resize((L, A))  # 255 à esquerda -> 0 à direita
        a0, a1 = int(L * inicio), int(L * fim)
        lut = [255 if x <= a0 else 0 if x >= a1 else int(255 * (a1 - x) / (a1 - a0)) for x in range(L)]
        linha = Image.new("L", (L, 1))
        linha.putdata(lut)
        mascara = linha.resize((L, A))
        if lado_texto == "direita":
            mascara = mascara.transpose(Image.FLIP_LEFT_RIGHT)
        if area:
            mascara = Image.new("L", (L, A), 0)
            for x0, y0, x1, y1 in (area if isinstance(area[0], (list, tuple)) else [area]):
                ImageDraw.Draw(mascara).rectangle([int(x0 * L) - 50, int(y0 * A) - 50, int(x1 * L) + 50,
                                                   int(y1 * A) + 50], fill=255)
            mascara = mascara.filter(ImageFilter.GaussianBlur(45))
        base = Image.composite(f, base, mascara)
        if not area:  # sombra suave sobre a emenda: esconde a diferença de luz entre os dois fundos
            meio = int(L * (inicio + fim) / 2)
            meio = L - meio if lado_texto == "direita" else meio
            faixa = Image.new("L", (L, A), 0)
            ImageDraw.Draw(faixa).rectangle([meio - 70, 0, meio + 70, A], fill=150)
            base = Image.composite(Image.new("RGB", (L, A), (0, 0, 0)), base, faixa.filter(ImageFilter.GaussianBlur(60)))
    if tom:
        cinza = base.convert("L")
        sombra = cinza.point(lambda v: int(max(0, 150 - v) * 0.9))  # mais forte nas partes escuras
        base = Image.composite(Image.new("RGB", (L, A), tom), base, sombra)
    if so_imagem:  # imagem limpa do Disciple (sem texto) para usar nas cenas dos vídeos
        base.save(destino, quality=95)
        return destino
    tela = base.convert("RGBA")
    # escurece o lado do texto para as letras saltarem
    grad = Image.linear_gradient("L").rotate(-90 if lado_texto == "esquerda" else 90).resize((L, A))
    escuro = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    escuro.putalpha(grad.point(lambda v: int(max(0, v - 120) * 0.8)))
    tela.alpha_composite(escuro)
    cx = int(L * 0.27) if lado_texto == "esquerda" else int(L * 0.73)
    largura = int(L * 0.48)
    d = ImageDraw.Draw(tela)
    est = ESTILOS_EPICOS.get(estilo, ESTILOS_EPICOS["imperial"])  # fonte e cores variam por thumb (dono, 2026-11-28)
    _fonte_atual[0] = config.PASTA_FONTES / est["fonte"]

    def cabe(txt, maximo):
        t = maximo
        while t > 30 and d.textlength(txt, font=_fonte_epica(t)) > largura:
            t -= 4
        return t
    linhas = palavra.split("\n")
    t_ouro = min(cabe(l.lstrip("~"), 150) for l in linhas)
    t_autor = cabe(_espacado(autor), 46) if autor else 0
    altura = len(linhas) * t_ouro * 1.12 + (t_autor * 1.6 + 40 if autor else 0) + 40
    y = max(20, int(A * y_centro - altura / 2))
    for l in linhas:
        prata = l.startswith("~")
        y += _linha_metalica(tela, l.lstrip("~"), cx, y, t_ouro, est["l2"] if prata else est["l1"],
                             contorno=est["c2"] if prata else est["c1"]) - 8
    _ornamento(tela, cx, y + 22, int(largura * 0.95), cor=est["orn"])
    if autor:
        _linha_metalica(tela, _espacado(autor), cx, y + 50, t_autor, est["l2"], contorno=est["c2"])
    print(f"  {Path(destino).name}: estilo disciple")
    return _salvar(tela, destino)
