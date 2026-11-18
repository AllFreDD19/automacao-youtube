"""Thumbnail no estilo dos vídeos virais: foto de fundo, texto grande branco com contorno preto
e palavras de destaque em amarelo (uma linha no topo, outra na base). Tudo gratuito: Pixabay + Pillow."""
import json
import re

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from . import config, llm, visuais

LARGURA, ALTURA = 1280, 720
FONTE = config.FONTE_TITULO
AMARELO, BRANCO, PRETO = (255, 214, 0), (255, 255, 255), (0, 0, 0)


def textos(roteiro):
    ficha = roteiro.get("ficha", {})
    prompt = f"""Título do vídeo: {roteiro['titulo']}
Promessa: {ficha.get('promessa', '')}
Fatos principais: {json.dumps(ficha.get('fatos_principais', []), ensure_ascii=False)}
Início do roteiro: {roteiro['capitulos_texto'][0][:1200] if roteiro.get('capitulos_texto') else ''}

Crie o texto de uma thumbnail chamativa do YouTube, em {roteiro.get('idioma', 'português')}, no estilo de canais virais:
- "linha_topo": 2 a 4 palavras em MAIÚSCULAS, a ideia mais forte (curiosidade, alerta ou choque);
- "linha_base": 2 a 5 palavras em MAIÚSCULAS que completem o gancho, sem repetir o título;
- "destaques": 1 ou 2 palavras dessas linhas para pintar de amarelo (as mais fortes);
- "buscas_fundo": 3 buscas diferentes em INGLÊS (1 a 3 palavras simples) para achar a foto de fundo num banco
  de imagens. A foto tem que mostrar o ASSUNTO PRINCIPAL de forma concreta e reconhecível (o próprio carro, a
  pessoa, o lugar, o objeto), nunca algo abstrato ou secundário. Ex.: para SUVs desvalorizados, "range rover",
  "suv", "used cars row"; para um castelo, "castle", "medieval castle".
O texto precisa ser fiel ao conteúdo do roteiro: não prometa números, preços ou fatos que o vídeo não entrega.
Formato: {{"linha_topo": "...", "linha_base": "...", "destaques": ["..."], "buscas_fundo": ["...", "...", "..."]}}"""
    for _ in range(3):
        t = llm.chat_json(prompt, "Você é especialista em thumbnails e CTR no YouTube.", temperatura=0.9)
        # Texto comprido vira letra pequena e a thumbnail perde força: insiste no limite de palavras
        if len(t.get("linha_topo", "").split()) <= 4 and len(t.get("linha_base", "").split()) <= 5:
            return t
        prompt += "\nATENÇÃO: o texto anterior ficou longo demais. linha_topo com NO MÁXIMO 4 palavras, linha_base com NO MÁXIMO 5."
    return t


def _fonte_que_cabe(texto, tamanho_max, largura_max):
    tamanho = tamanho_max
    while tamanho > 40:
        fonte = ImageFont.truetype(FONTE, tamanho)
        if fonte.getlength(texto) <= largura_max:
            return fonte
        tamanho -= 4
    return ImageFont.truetype(FONTE, 40)


def _linha(desenho, texto, y, tamanho_max, destaques):
    fonte = _fonte_que_cabe(texto, tamanho_max, LARGURA - 80)
    contorno = max(4, fonte.size // 14)
    x = (LARGURA - fonte.getlength(texto)) / 2
    espaco = fonte.getlength(" ")
    for palavra in texto.split():
        limpa = re.sub(r"[^\w£$€%]", "", palavra).upper()
        cor = AMARELO if limpa in destaques else BRANCO
        desenho.text((x, y), palavra, font=fonte, fill=cor, stroke_width=contorno, stroke_fill=PRETO)
        x += fonte.getlength(palavra) + espaco
    return fonte.size


def _escurecer_faixas(img):
    """Gradiente escuro no topo e na base para o texto saltar da foto."""
    sombra = Image.new("L", (1, ALTURA))
    for y in range(ALTURA):
        dist = min(y, ALTURA - y) / (ALTURA * 0.32)
        sombra.putpixel((0, y), int(170 * max(0.0, 1 - dist)))
    camada = Image.new("RGB", (LARGURA, ALTURA), PRETO)
    return Image.composite(camada, img, sombra.resize((LARGURA, ALTURA)))


def desenhar(fundo, linha_topo, linha_base, destaques, destino):
    img = ImageOps.fit(Image.open(fundo).convert("RGB"), (LARGURA, ALTURA), Image.LANCZOS)
    img = ImageEnhance.Color(img).enhance(1.25)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = _escurecer_faixas(img)
    desenho = ImageDraw.Draw(img)
    destaques = {re.sub(r"[^\w£$€%]", "", d).upper() for d in destaques}
    _linha(desenho, linha_topo.upper(), 22, 140, destaques)
    fonte_base = _fonte_que_cabe(linha_base.upper(), 110, LARGURA - 80)
    _linha(desenho, linha_base.upper(), ALTURA - fonte_base.size - 45, 110, destaques)
    img.save(destino, "JPEG", quality=92)
    return destino


def gerar_thumbnails(roteiro, pasta_projeto, variacoes=3):
    t = textos(roteiro)
    pasta = pasta_projeto / "thumbnail"
    pasta.mkdir(exist_ok=True)
    usados, gerados = set(), []
    for i, busca in enumerate(t.get("buscas_fundo", [])[:variacoes], 1):
        fundo = visuais.imagem_pixabay(busca, pasta / f"fundo_{i}.jpg", usados)
        if not fundo:
            continue
        gerados.append(desenhar(fundo, t["linha_topo"], t["linha_base"], t.get("destaques", []),
                                pasta_projeto / f"thumbnail_{i}.jpg"))
        print(f"  thumbnail_{i}.jpg  (fundo: {busca})")
    if not gerados:
        # Sem foto no Pixabay: usa a primeira imagem das cenas do vídeo
        cena = next((c for c in roteiro["cenas"] if c.get("visual_tipo") == "imagem"), None)
        if cena:
            gerados.append(desenhar(pasta_projeto / cena["visual_arquivo"], t["linha_topo"], t["linha_base"],
                                    t.get("destaques", []), pasta_projeto / "thumbnail_1.jpg"))
    roteiro["thumbnail"] = t
    return gerados
