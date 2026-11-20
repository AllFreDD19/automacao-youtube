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
