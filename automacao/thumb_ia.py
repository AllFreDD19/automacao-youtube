"""Thumbnail no estilo "mega obra": ilustração vibrante gerada por IA + bandeira real do país tremulando no canto.

Referência do usuário: canais que mostram construções gigantes (pontes, elevadores em penhascos) com cena hiper
saturada, luz forte, operários de colete laranja, bandeira em destaque no canto superior esquerdo e nenhum texto.
A IA (FLUX.1-dev da NVIDIA, créditos grátis) desenha a cena SEM bandeira, porque erra estrelas e listras; a bandeira
oficial vem do Wikimedia Commons e recebe ondulação, sombra e mastro aqui.
"""
import io

import requests
from PIL import Image, ImageEnhance, ImageFilter

from . import llm, visuais

LARGURA, ALTURA = 1280, 720
# Fotografia, não ilustração: "3D digital illustration" e "glossy" davam cara de desenho (pedido do usuário em
# 2026-10-12: "mais realista"). As cores continuam vivas, que é o que prende o olho na thumbnail.
ESTILO = ("photorealistic aerial drone photograph, shot on a professional DSLR camera, 24mm wide angle lens, natural "
          "bright sunlight with golden hour warmth, deep blue sky with white clouds, lush green vegetation, vivid "
          "natural colors, realistic textures of steel, concrete, rock and water, real people at true scale, sharp "
          "focus, high dynamic range, National Geographic style, epic scale, busy real construction site, "
          "empty clear sky in the upper left corner, no text, no flags, no letters, no watermark")


# ---------- cena ----------

def descrever_cena(roteiro):
    """Pede ao modelo de texto a cena em inglês e o país em destaque, a partir do título e da promessa do vídeo.

    Devolve {"cena": "...", "pais": "China" | ""}.
    """
    ficha = roteiro.get("ficha", {})
    fatos = "; ".join(ficha.get("fatos_principais", [])[:8])
    inicio = (roteiro.get("capitulos_texto") or [""])[0][:1200]
    # Regra do usuário (2026-10-12): a thumb SEMPRE conecta com o título e com o conteúdo do vídeo, o mais realista
    # possível, e com a bandeira do país em questão ao fundo
    prompt = f"""Título do vídeo: {roteiro['titulo']}
Promessa: {ficha.get('promessa', '')}
Fatos principais: {fatos}
Começo do roteiro: {inicio}

1. Descreva em INGLÊS, em 2 frases, a cena da thumbnail. Ela TEM que mostrar exatamente o assunto do título (o mesmo
objeto, lugar, animal, máquina ou feito, com as características citadas no título e no roteiro), para quem vê a
thumbnail e lê o título entender na hora que são a mesma coisa. Estilo "mega obra / maravilha impressionante":
o assunto em escala gigante e em ação (sendo construído, operando, em movimento), visto de perto, com detalhes em
primeiro plano (máquinas, pessoas pequenas para dar escala, animais, veículos — o que fizer sentido) e uma paisagem
espetacular e real ao fundo. REALISTA e plausível, como uma foto tirada no local: nada de fantasia, exagero
impossível ou elementos que não existem no assunto. Nada de texto, letreiros ou bandeiras. Seja concreto e visual.
2. Diga o país em destaque no vídeo, com o nome em INGLÊS como no Wikipedia ("China", "United States", "Germany");
se o vídeo não é sobre um país específico, deixe "".
Formato: {{"cena": "...", "pais": "..."}}"""
    resposta = llm.chat_json(prompt, "Você é diretor de arte de thumbnails virais do YouTube.", temperatura=0.8)
    return {"cena": resposta.get("cena", ""), "pais": (resposta.get("pais") or "").strip()}


def gerar_cena(cena, destino, semente=7):
    """Gera a ilustração (1344x768) com o FLUX.1-dev da NVIDIA."""
    return visuais.imagem_nvidia(f"{cena}, {ESTILO}", destino, semente)


# ---------- bandeira ----------

def baixar_bandeira(pais):
    """Bandeira oficial do Wikimedia Commons ("Flag of China.svg", "Flag of the United States.svg"...), em PNG."""
    nome = pais.strip().replace(" ", "_")
    for arquivo in (f"Flag_of_{nome}.svg", f"Flag_of_the_{nome}.svg"):
        try:
            r = requests.get(f"https://commons.wikimedia.org/wiki/Special:FilePath/{arquivo}",
                             params={"width": 900}, headers=visuais.WIKI_HEADERS, timeout=30)
            if r.ok and r.headers.get("content-type", "").startswith("image/"):
                return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except requests.RequestException:
            continue
    raise RuntimeError(f'Bandeira não encontrada no Wikimedia para "{pais}" (use o nome em inglês, ex.: "Germany")')


def ondular(bandeira, largura=360, ondas=2.2, amplitude=0.09):
    """Tecido ao vento: dobras diagonais (a onda corre na horizontal e inclina com a altura), que crescem para a
    ponta solta, com luz e sombra fortes nas cristas e vales, como nas thumbnails de referência."""
    import numpy as np
    alt = round(largura * bandeira.height / bandeira.width)
    origem = np.asarray(bandeira.resize((largura, alt), Image.LANCZOS)).astype(np.float32)
    amp = alt * amplitude
    margem = int(amp * 2) + 2
    altura_saida = alt + 2 * margem
    ys, xs = np.mgrid[0:altura_saida, 0:largura].astype(np.float32)
    forca = 0.2 + 0.8 * xs / largura           # junto ao mastro quase não mexe
    fase = 2 * np.pi * (ondas * xs / largura + 0.35 * ys / altura_saida)
    # De onde vem cada pixel do tecido (deslocamento vertical forte + leve encolhimento horizontal nas dobras)
    origem_y = ys - margem - amp * forca * np.sin(fase)
    origem_x = xs - 0.25 * amp * forca * np.cos(fase)
    dentro = (origem_y >= 0) & (origem_y < alt - 1) & (origem_x >= 0) & (origem_x < largura - 1)
    oy = np.clip(origem_y, 0, alt - 1).astype(int)
    ox = np.clip(origem_x, 0, largura - 1).astype(int)
    pixels = origem[oy, ox]
    # Sombreamento: vale escuro e crista com brilho puxando para o branco. Só multiplicar não basta: cores já no
    # máximo (o vermelho da China) não clareiam, e o tecido parecia chapado
    onda = np.cos(fase)
    luz = 0.88 + 0.30 * forca * onda
    brilho = np.clip(onda, 0, 1) ** 2 * 0.28 * forca
    rgb = pixels[..., :3] * luz[..., None]
    pixels[..., :3] = np.clip(rgb + (255 - rgb) * brilho[..., None], 0, 255)
    pixels[..., 3] = np.where(dentro, pixels[..., 3], 0)
    tecido = Image.fromarray(pixels.astype(np.uint8), "RGBA")
    # Borda suave (antisserrilhado) depois do mapeamento por vizinho mais próximo
    alfa = tecido.split()[3].filter(ImageFilter.GaussianBlur(0.8))
    tecido.putalpha(alfa)
    return tecido


def _dissolver(alfa, inicio_x=0.55, inicio_y=0.5):
    """Some aos poucos para a direita e para baixo (na direção da obra), sem corte seco sobre a cena."""
    import numpy as np
    a = np.asarray(alfa).astype(np.float32)
    h, w = a.shape
    xs = np.linspace(0, 1, w)[None, :]
    ys = np.linspace(0, 1, h)[:, None]
    fx = 1 - np.clip((xs - inicio_x) / (1 - inicio_x), 0, 1)
    fy = 1 - np.clip((ys - inicio_y) / (1 - inicio_y), 0, 1)
    mascara = (fx * fy) ** 1.4  # curva suave: o centro da bandeira fica cheio
    return Image.fromarray((a * mascara).astype(np.uint8), "L")


def colocar_bandeira(fundo, bandeira, largura=340, sobra_esquerda=40, sobra_topo=18, inclinacao=-4,
                     opacidade=0.97, desfoque=1.4):
    """Bandeira em segundo plano no canto superior esquerdo (pedido do usuário: sem mastro, mais sutil).

    Ela sai pelas bordas, como se continuasse fora do quadro, e se dissolve na direção da obra; fica levemente
    desfocada (o foco é a obra) e com a cor puxada para a luz da cena, para parecer parte da foto e não um adesivo.
    Transparência forte foi descartada: a obra aparecia "atravessando" o tecido como um fantasma.
    """
    tecido = ondular(bandeira, largura).rotate(inclinacao, resample=Image.BICUBIC, expand=True)
    tecido = tecido.filter(ImageFilter.GaussianBlur(desfoque))
    # Cor média do céu atrás dela tinge levemente o tecido (mesma luz da cena)
    regiao = fundo.crop((0, 0, tecido.width, tecido.height)).convert("RGB").resize((1, 1), Image.BOX)
    tom = Image.new("RGB", tecido.size, regiao.getpixel((0, 0)))
    cores = Image.blend(tecido.convert("RGB"), tom, 0.12)
    cores = ImageEnhance.Color(cores).enhance(0.92)
    alfa = _dissolver(tecido.split()[3].point(lambda a: int(a * opacidade)))
    tecido = Image.merge("RGBA", (*cores.split(), alfa))
    # Sair pelas bordas = colar a partir de um recorte (o PIL não aceita posição negativa)
    fundo.alpha_composite(tecido, (0, 0), (sobra_esquerda, sobra_topo))
    return fundo


# ---------- composição ----------

def realcar(img):
    """O "punch" das thumbnails de referência: mais cor, contraste e nitidez."""
    # Mais suave que antes (1,35 de cor): exagero de saturação devolvia a cara de pintura à foto realista
    img = ImageEnhance.Color(img).enhance(1.18)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=70, threshold=2))
    return img


def montar(cena_arquivo, pais, destino):
    fundo = Image.open(cena_arquivo).convert("RGB")
    # Preenche 1280x720 cortando o excesso (a IA gera 1344x768)
    escala = max(LARGURA / fundo.width, ALTURA / fundo.height)
    fundo = fundo.resize((round(fundo.width * escala), round(fundo.height * escala)), Image.LANCZOS)
    esq, topo = (fundo.width - LARGURA) // 2, (fundo.height - ALTURA) // 2
    fundo = realcar(fundo.crop((esq, topo, esq + LARGURA, topo + ALTURA))).convert("RGBA")
    if pais:
        colocar_bandeira(fundo, baixar_bandeira(pais))
    fundo.convert("RGB").save(destino, "JPEG", quality=93)
    return destino


# ---------- estilo "destaque" (referência do usuário em 2026-10-12: canal de pickups no México) ----------
# Âncora fictício (IA) numa coluna à esquerda, faixa vermelha com texto branco no topo, cena realista à direita com a
# bandeira sutil, faixa branca com texto preto na base. O âncora é uma pessoa INVENTADA: nunca parecer jornalista real.
ANCORA = ("photorealistic head and shoulders portrait of a fictional Latin American television news anchor man in his "
          "forties, dark navy suit and tie, serious concerned expression looking straight at the camera, centered in "
          "the frame, blurred city skyline at dusk behind him, professional studio lighting, shallow depth of field, "
          "no text, no logos, no microphone")
VERMELHO = (200, 16, 32)
COLUNA = 360          # largura do âncora
FAIXA_TOPO = 108      # altura da faixa vermelha
FAIXA_BASE = (300, 612, LARGURA - 14, ALTURA - 14)  # caixa branca (esquerda, topo, direita, base)


ESTILO_DESTAQUE = ("photorealistic photograph shot on a professional DSLR camera at eye level, harsh bright natural "
                   "light, vivid but natural colors, sharp focus, high dynamic range, dramatic and emotional moment, "
                   "no text, no signs, no letters, no flags, no logos, no brand badges, no watermark")


def descrever_destaque(roteiro):
    """Cena, fundo do âncora, país e 3 pares de texto da thumbnail, tirados do título e do conteúdo do vídeo.

    Devolve {"cena": "...", "fundo_ancora": "...", "pais": "...", "textos": [["TOPO", "BASE"], ...]}.
    """
    ficha = roteiro.get("ficha", {})
    fatos = "; ".join(ficha.get("fatos_principais", [])[:8])
    inicio = (roteiro.get("capitulos_texto") or [""])[0][:1200]
    idioma = roteiro.get("idioma", "inglês")
    prompt = f"""Título do vídeo: {roteiro['titulo']}
Promessa: {ficha.get('promessa', '')}
Fatos principais: {fatos}
Começo do roteiro: {inicio}

Thumbnail no estilo de canal de notícias: um âncora de TV à esquerda, faixa vermelha com texto no topo, uma cena
realista grande à direita e faixa branca com texto na base. Tudo tem que conectar com o TÍTULO e o conteúdo do vídeo.
1. "cena": em INGLÊS, 2 frases. Uma foto realista, ao nível dos olhos, do assunto exato do título num momento que
   chama atenção e traduz a promessa (o problema, o perigo, o espanto, a grandiosidade), com uma pessoa reagindo se
   fizer sentido, no lugar/país do vídeo. Plausível como foto real: nada de fantasia. Sem texto, placas, bandeiras,
   logos ou marcas (carros, máquinas e produtos SEM logotipo). O gerador de imagem BLOQUEIA (devolve tela preta)
   violência, acidente no momento do impacto, feridos, sangue, mortos e crianças em perigo: mostre a tensão de forma
   segura (pane com fumaça ou vapor, peça quebrada, pessoa adulta preocupada com as mãos na cabeça, tempestade
   chegando, multidão olhando), nunca vítimas. Nada de crianças na cena.
2. "fundo_ancora": em INGLÊS, até 12 palavras: o fundo desfocado atrás do âncora, ligado ao tema/lugar do vídeo
   (ex.: "blurred skyline of Tokyo at night", "blurred African savanna at sunset").
3. "pais": país em destaque, nome em INGLÊS como no Wikipedia ("Mexico", "Germany"); "" se o vídeo não é sobre um país.
   Só quando o TÍTULO é sobre aquele país (ex.: "Worst Cars to Buy in Mexico"). País de onde vêm um teste, uma
   fonte ou uma marca citada NÃO conta (ex.: teste alemão num vídeo sobre pneus em geral = "").
4. "textos": 3 pares [topo, base] em {idioma}, MAIÚSCULAS. topo: 2 a 4 palavras com o assunto do título; base: 2 a 5
   palavras com o gancho (alerta, choque, curiosidade). Fiel ao roteiro: nada de números, fatos ou promessas que o
   vídeo não entrega, nada mais exagerado do que o roteiro diz (ex.: não chamar de "mortal" o que o vídeo chama de
   "pouco seguro") e nada que acuse uma marca ou pessoa real. Um dos pares pode seguir o modelo "ONLY A FOOL WOULD
   BUY THESE" / "DON'T BUY THESE IN 2026!" quando o tema for compra ou escolha.
Formato: {{"cena": "...", "fundo_ancora": "...", "pais": "...", "textos": [["...", "..."], ["...", "..."], ["...", "..."]]}}"""
    for _ in range(3):
        r = llm.chat_json(prompt, "Você é diretor de arte de thumbnails virais do YouTube.", temperatura=0.8)
        textos = [t for t in r.get("textos", []) if len(t) == 2 and len(t[0].split()) <= 4 and len(t[1].split()) <= 6]
        if r.get("cena") and textos:
            return {"cena": r["cena"], "fundo_ancora": r.get("fundo_ancora") or "blurred city skyline at dusk",
                    "pais": (r.get("pais") or "").strip(), "textos": textos}
        prompt += "\nATENÇÃO: responda com cena e 3 pares de texto curtos (topo até 4 palavras, base até 5)."
    raise RuntimeError("o modelo de texto não devolveu cena e textos para a thumbnail")


def gerar_ancora(destino, semente=7, fundo="blurred city skyline at dusk"):
    return visuais.imagem_nvidia(ANCORA.replace("blurred city skyline at dusk", fundo), destino, semente)


def borrar_logo(arquivo, x, y, largura=48, altura=38):
    """Apaga um logotipo que a IA desenhou (centro em x, y): o FLUX põe Toyota, Honda, Renault mesmo pedindo
    "no logos", e logo real + título negativo soa como acusação à marca. Conferir cada thumbnail antes de entregar."""
    from PIL import ImageDraw
    im = Image.open(arquivo)
    caixa = (x - largura // 2, y - altura // 2, x + largura // 2, y + altura // 2)
    regiao = im.crop(caixa).filter(ImageFilter.GaussianBlur(9))
    mascara = Image.new("L", regiao.size, 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, *regiao.size), fill=255)
    im.paste(regiao, caixa[:2], mascara.filter(ImageFilter.GaussianBlur(3)))
    im.save(arquivo, "JPEG", quality=93)


def _cobrir(img, largura, altura, foco_x=0.5):
    """Redimensiona para cobrir largura x altura e corta o excesso (foco_x = onde fica o centro do corte)."""
    escala = max(largura / img.width, altura / img.height)
    img = img.resize((round(img.width * escala), round(img.height * escala)), Image.LANCZOS)
    esq = round((img.width - largura) * foco_x)
    topo = (img.height - altura) // 2
    return img.crop((esq, topo, esq + largura, topo + altura))


def _texto_na_caixa(desenho, texto, caixa, cor, tamanho_max):
    from .thumbnail import _fonte_que_cabe
    esq, topo, dir_, base = caixa
    fonte = _fonte_que_cabe(texto, tamanho_max, dir_ - esq - 30)
    x0, y0, x1, y1 = desenho.textbbox((0, 0), texto, font=fonte)
    x = esq + (dir_ - esq - (x1 - x0)) / 2 - x0
    y = topo + (base - topo - (y1 - y0)) / 2 - y0
    desenho.text((x, y), texto, font=fonte, fill=cor)


def montar_destaque(cena_arquivo, ancora_arquivo, pais, texto_topo, texto_base, destino):
    from PIL import ImageDraw
    thumb = Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 255))
    # Cena à direita, abaixo da faixa vermelha, com a bandeira sutil no canto dela
    cena = realcar(_cobrir(Image.open(cena_arquivo).convert("RGB"), LARGURA - COLUNA, ALTURA - FAIXA_TOPO))
    cena = cena.convert("RGBA")
    if pais:
        colocar_bandeira(cena, baixar_bandeira(pais), largura=300)
    thumb.alpha_composite(cena, (COLUNA, FAIXA_TOPO))
    # Âncora na coluna da esquerda, de cima a baixo
    ancora = realcar(_cobrir(Image.open(ancora_arquivo).convert("RGB"), COLUNA, ALTURA)).convert("RGBA")
    thumb.alpha_composite(ancora, (0, 0))
    desenho = ImageDraw.Draw(thumb)
    # Linha fina separando o âncora da cena
    desenho.rectangle((COLUNA - 3, 0, COLUNA + 1, ALTURA), fill=(255, 255, 255, 255))
    # Faixa vermelha do topo, texto branco
    desenho.rectangle((COLUNA + 2, 0, LARGURA, FAIXA_TOPO), fill=VERMELHO)
    _texto_na_caixa(desenho, texto_topo.upper(), (COLUNA + 2, 6, LARGURA, FAIXA_TOPO - 4), (255, 255, 255), 92)
    # Caixa branca da base (avança sobre o âncora, como na referência), texto preto
    sombra = Image.new("RGBA", thumb.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rectangle(tuple(v + 6 for v in FAIXA_BASE), fill=(0, 0, 0, 140))
    thumb.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(5)))
    desenho = ImageDraw.Draw(thumb)
    desenho.rectangle(FAIXA_BASE, fill=(255, 255, 255, 255))
    _texto_na_caixa(desenho, texto_base.upper(), FAIXA_BASE, (0, 0, 0), 84)
    thumb.convert("RGB").save(destino, "JPEG", quality=93)
    return destino


def _sem_preta(gerar_imagem, semente, tentativas=3):
    """O FLUX devolve imagem toda preta quando o filtro de conteúdo dele dispara: tenta outras sementes."""
    from PIL import ImageStat
    for n in range(tentativas):
        arquivo = gerar_imagem(semente + n)
        if arquivo and max(ImageStat.Stat(Image.open(arquivo).convert("L")).mean) > 12:
            return arquivo
        print(f"  a IA devolveu imagem preta ou nada (semente {semente + n}), tentando outra")
    return None


def gerar_destaque(roteiro, pasta_projeto, pais=None, cena=None, variacoes=3):
    """PADRÃO desde 2026-10-12: `variacoes` thumbnails no estilo destaque, tudo tirado do título e do roteiro.

    pais: nome em inglês; None = descobrir pelo título; "" = sem bandeira. cena: descrição em inglês; None = do título.
    """
    sugestao = descrever_destaque(roteiro)
    cena_do_usuario = bool(cena)
    cena = cena or sugestao["cena"]
    pais = sugestao["pais"] if pais is None else pais
    pasta = pasta_projeto / "thumbnail"
    pasta.mkdir(exist_ok=True)
    gerados = []
    for i in range(1, variacoes + 1):
        topo, base = sugestao["textos"][(i - 1) % len(sugestao["textos"])]
        bruto = _sem_preta(lambda s: visuais.imagem_nvidia(f"{cena}, {ESTILO_DESTAQUE}",
                                                            pasta / f"destaque_cena_{i}.jpg", s), i * 101)
        if not bruto and not cena_do_usuario:  # filtro do FLUX barrou a cena: pede outra, mais leve, uma vez
            print("  cena barrada pela IA de imagem; pedindo uma cena nova")
            cena = descrever_destaque(roteiro)["cena"]
            cena_do_usuario = True  # não troca de novo
            bruto = _sem_preta(lambda s: visuais.imagem_nvidia(f"{cena}, {ESTILO_DESTAQUE}",
                                                                pasta / f"destaque_cena_{i}.jpg", s), i * 101 + 50)
        ancora = _sem_preta(lambda s: gerar_ancora(pasta / f"destaque_ancora_{i}.jpg", s, sugestao["fundo_ancora"]),
                            i * 77)
        if not (bruto and ancora):
            print(f"  thumbnail {i}: a IA não devolveu imagem")
            continue
        destino = pasta_projeto / f"thumbnail_{i}.jpg"
        try:
            gerados.append(montar_destaque(bruto, ancora, pais, topo, base, destino))
        except RuntimeError as e:  # bandeira não achada: entrega sem ela em vez de parar
            print(f"  {e}; thumbnail {i} sai sem bandeira")
            gerados.append(montar_destaque(bruto, ancora, "", topo, base, destino))
    roteiro["thumbnail"] = {"estilo": "destaque", "cena": cena, "pais": pais, "textos": sugestao["textos"],
                            "fundo_ancora": sugestao["fundo_ancora"]}
    return gerados


# ---------- estilo "cinema" (PADRÃO desde 2026-10-12, referência do usuário: "15 CARS TO AVOID", "THEY HIDE THESE
# TIRES", "THE SCREAM OF DEATH") ----------
# Cena cinematográfica realista ocupando a thumb inteira, o assunto de um lado e, do outro, duas linhas grandes em
# Impact: a primeira branca, a segunda vermelha ou amarela, com contorno preto e sombra. Sem âncora e sem faixas
# (o usuário achou o estilo destaque, com o personagem, "muito ruim").
# "film still"/"cinema camera" faziam o FLUX desenhar tarjas pretas de cinema e cena escura demais (marder-auto):
# pedir quadro cheio e luz quente forte; _sem_tarjas corta o que sobrar
ESTILO_CINEMA = ("dramatic photorealistic photograph, full frame image edge to edge, bright warm golden key light on the "
                 "main subject with strong contrast, volumetric light, smoke or dust in the air when it fits, shallow "
                 "depth of field, sharp detailed main subject, rich saturated but realistic colors, no black bars, "
                 "no letterbox, no text, no signs, no letters, no flags, no logos, no brand badges, no watermark")
CORES_DESTAQUE = {"vermelho": (232, 28, 36), "amarelo": (255, 214, 0)}


def descrever_cinema(roteiro):
    """Cena, lado do assunto e 3 pares de texto, tirados do título e do conteúdo do vídeo.

    Devolve {"cena": "...", "lado": "esquerda" | "direita", "textos": [["LINHA 1", "LINHA 2", "vermelho"], ...]}.
    """
    ficha = roteiro.get("ficha", {})
    fatos = "; ".join(ficha.get("fatos_principais", [])[:8])
    inicio = (roteiro.get("capitulos_texto") or [""])[0][:1200]
    idioma = roteiro.get("idioma", "inglês")
    prompt = f"""Título do vídeo: {roteiro['titulo']}
Promessa: {ficha.get('promessa', '')}
Fatos principais: {fatos}
Começo do roteiro: {inicio}

Thumbnail cinematográfica: uma cena realista e dramática ocupando a imagem inteira, com o assunto de um lado e o outro
lado mais escuro e limpo, onde entram duas linhas grandes de texto. Exemplos aprovados pelo dono do canal: um homem
desesperado ao lado de um carro velho soltando fumaça numa estrada do deserto ("15 CARS / TO AVOID"); um pneu novo
com etiqueta de preço numa oficina escura ("THEY HIDE / THESE TIRES"); um Stuka mergulhando sobre um campo de
batalha em chamas ("THE SCREAM / OF DEATH").
1. "cena": em INGLÊS, 2 frases. O assunto EXATO do título, grande e nítido, num momento que traduz a promessa (perigo,
   choque, mistério), com luz de cinema. Plausível como foto real: nada de fantasia. Diga em que lado da imagem fica o
   assunto ("on the left side of the frame") e que o outro lado é mais escuro e vazio. Sem texto, placas, bandeiras,
   logos ou marcas. O gerador BLOQUEIA (tela preta) violência, sangue, feridos, mortos e crianças: mostre a tensão de
   forma segura (fumaça, vapor, peça quebrada, adulto preocupado, noite ameaçadora).
2. "lado": "esquerda" ou "direita", o lado do ASSUNTO (o texto vai no lado oposto).
3. "textos": 3 trios [linha1, linha2, cor] em {idioma}, MAIÚSCULAS, cada linha com 1 a 3 palavras curtas; linha2 é
   a parte forte do gancho; cor da linha2 = "vermelho" (perigo, alerta) ou "amarelo" (curiosidade, segredo). Fiel ao
   roteiro: nada que o vídeo não entrega, nada mais exagerado do que ele diz, nada que acuse marca ou pessoa real.
Formato: {{"cena": "...", "lado": "...", "textos": [["...", "...", "vermelho"], ["...", "...", "amarelo"], ["...", "...", "vermelho"]]}}"""
    for _ in range(3):
        r = llm.chat_json(prompt, "Você é diretor de arte de thumbnails virais do YouTube.", temperatura=0.8)
        textos = [t for t in r.get("textos", []) if len(t) >= 2 and len(t[0].split()) <= 3 and len(t[1].split()) <= 3]
        if r.get("cena") and textos:
            return {"cena": r["cena"], "lado": "direita" if r.get("lado") == "direita" else "esquerda",
                    "textos": [[t[0], t[1], t[2] if len(t) > 2 and t[2] in CORES_DESTAQUE else "vermelho"]
                               for t in textos]}
        prompt += "\nATENÇÃO: responda com cena, lado e 3 trios de texto curtos (até 3 palavras por linha)."
    raise RuntimeError("o modelo de texto não devolveu cena e textos para a thumbnail")


def _sem_tarjas(img, limite=10):
    """Corta tarjas pretas de cinema (linhas quase pretas em cima e embaixo) que o FLUX às vezes desenha."""
    cinza = img.convert("L")
    linhas = [sum(cinza.crop((0, y, img.width, y + 1)).getdata()) / img.width for y in range(img.height)]
    topo = next((y for y, v in enumerate(linhas) if v > limite), 0)
    base = next((y for y, v in enumerate(reversed(linhas)) if v > limite), 0)
    if topo + base < img.height * 0.4:
        img = img.crop((0, topo, img.width, img.height - base))
    return img


def montar_cinema(cena_arquivo, linha1, linha2, cor, destino, lado_assunto="esquerda", pais=""):
    """Cena inteira + escurecimento suave do lado do texto + duas linhas em Impact com contorno e sombra."""
    from PIL import ImageDraw
    from .thumbnail import _fonte_que_cabe
    thumb = realcar(_cobrir(_sem_tarjas(Image.open(cena_arquivo).convert("RGB")), LARGURA, ALTURA,
                            foco_x=0.35 if lado_assunto == "esquerda" else 0.65)).convert("RGBA")
    if pais:  # bandeira só se pedida (--pais); os exemplos do usuário não têm
        colocar_bandeira(thumb, baixar_bandeira(pais), largura=300)
    # Gradiente escuro do lado do texto, para as letras saltarem sem esconder o assunto
    grad = Image.new("L", (LARGURA, 1))
    for x in range(LARGURA):
        t = x / LARGURA if lado_assunto == "esquerda" else 1 - x / LARGURA
        grad.putpixel((x, 0), int(170 * max(0.0, (t - 0.35) / 0.65) ** 1.4))
    sombra_lado = Image.new("RGBA", thumb.size, (0, 0, 0, 255))
    sombra_lado.putalpha(grad.resize(thumb.size))
    thumb.alpha_composite(sombra_lado)
    largura_texto = 600
    centro_x = LARGURA - 40 - largura_texto / 2 if lado_assunto == "esquerda" else 40 + largura_texto / 2
    linhas = [(linha1.upper(), (255, 255, 255)), (linha2.upper(), CORES_DESTAQUE.get(cor, CORES_DESTAQUE["vermelho"]))]
    fontes = [_fonte_que_cabe(t, 170, largura_texto) for t, _ in linhas]
    alturas = [f.getbbox(t)[3] - f.getbbox(t)[1] for f, (t, _) in zip(fontes, linhas)]
    espaco = 14
    y = (ALTURA - sum(alturas) - espaco) / 2
    camada_sombra = Image.new("RGBA", thumb.size, (0, 0, 0, 0))
    posicoes = []
    for (texto, cor_linha), fonte, alt in zip(linhas, fontes, alturas):
        x = centro_x - fonte.getlength(texto) / 2
        y0 = y - fonte.getbbox(texto)[1]
        posicoes.append((x, y0, texto, fonte, cor_linha))
        ImageDraw.Draw(camada_sombra).text((x + 8, y0 + 10), texto, font=fonte, fill=(0, 0, 0, 200),
                                           stroke_width=max(5, fonte.size // 16), stroke_fill=(0, 0, 0, 200))
        y += alt + espaco
    thumb.alpha_composite(camada_sombra.filter(ImageFilter.GaussianBlur(9)))
    desenho = ImageDraw.Draw(thumb)
    for x, y0, texto, fonte, cor_linha in posicoes:
        desenho.text((x, y0), texto, font=fonte, fill=cor_linha, stroke_width=max(5, fonte.size // 16),
                     stroke_fill=(0, 0, 0))
    thumb.convert("RGB").save(destino, "JPEG", quality=93)
    return destino


def gerar_cinema(roteiro, pasta_projeto, pais="", cena=None, variacoes=3):
    """PADRÃO desde 2026-10-12: `variacoes` thumbnails no estilo cinema, tudo tirado do título e do roteiro.
    pais: só com --pais (padrão sem bandeira); cena: descrição em inglês; None = do título."""
    sugestao = descrever_cinema(roteiro)
    cena_do_usuario = bool(cena)
    cena = cena or sugestao["cena"]
    pasta = pasta_projeto / "thumbnail"
    pasta.mkdir(exist_ok=True)
    gerados = []
    for i in range(1, variacoes + 1):
        linha1, linha2, cor = sugestao["textos"][(i - 1) % len(sugestao["textos"])]
        bruto = _sem_preta(lambda s: visuais.imagem_nvidia(f"{cena}, {ESTILO_CINEMA}",
                                                            pasta / f"cinema_cena_{i}.jpg", s), i * 101)
        if not bruto and not cena_do_usuario:  # filtro do FLUX barrou a cena: pede outra uma vez
            print("  cena barrada pela IA de imagem; pedindo uma cena nova")
            cena = descrever_cinema(roteiro)["cena"]
            cena_do_usuario = True
            bruto = _sem_preta(lambda s: visuais.imagem_nvidia(f"{cena}, {ESTILO_CINEMA}",
                                                                pasta / f"cinema_cena_{i}.jpg", s), i * 101 + 50)
        if not bruto:
            print(f"  thumbnail {i}: a IA não devolveu imagem")
            continue
        gerados.append(montar_cinema(bruto, linha1, linha2, cor, pasta_projeto / f"thumbnail_{i}.jpg",
                                     sugestao["lado"], pais or ""))
    roteiro["thumbnail"] = {"estilo": "cinema", "cena": cena, "lado": sugestao["lado"], "pais": pais or "",
                            "textos": sugestao["textos"]}
    return gerados


def gerar(roteiro, pasta_projeto, pais=None, cena=None, variacoes=3):
    """Gera `variacoes` thumbnails (cenas com sementes diferentes) para o projeto.

    pais: nome em inglês ("China"); None = descobrir pelo título; "" = sem bandeira.
    cena: descrição em inglês; None = criar a partir do título.
    """
    if cena is None or pais is None:
        sugestao = descrever_cena(roteiro)
        cena = cena or sugestao["cena"]
        pais = sugestao["pais"] if pais is None else pais
    pasta = pasta_projeto / "thumbnail"
    pasta.mkdir(exist_ok=True)
    gerados = []
    for i in range(1, variacoes + 1):
        bruto = gerar_cena(cena, pasta / f"ia_{i}.jpg", semente=i * 101)
        if not bruto:
            continue
        try:
            gerados.append(montar(bruto, pais, pasta_projeto / f"thumbnail_{i}.jpg"))
        except RuntimeError as e:  # bandeira não achada: entrega a thumbnail sem ela em vez de parar
            print(f"  {e}; thumbnail {i} sai sem bandeira")
            gerados.append(montar(bruto, "", pasta_projeto / f"thumbnail_{i}.jpg"))
    roteiro["thumbnail"] = {"estilo": "ia", "cena": cena, "pais": pais}
    return gerados
