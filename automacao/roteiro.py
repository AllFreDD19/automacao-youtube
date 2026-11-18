"""Etapas 3 e 4: modelos de títulos e roteiro seguindo o Prompt Mestre (prompts/roteiro_mestre.md).

Fluxo do roteiro: referência -> ficha de planejamento -> capítulos escritos em partes ->
revisão de cada capítulo (anacronismos, fatos inventados, números) -> checklist final ->
divisão em cenas com palavras-chave de imagem.
"""
import json
import math
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

from . import config, llm

PROMPT_MESTRE = config.RAIZ / "prompts" / "roteiro_mestre.md"
HISTORICO_ABERTURAS = config.PASTA_PROJETOS / "_aberturas.json"
CARACTERES_POR_MINUTO = 735  # medido com a voz do Edge TTS a +5%
CARACTERES_POR_PARTE = 3000  # cada capítulo é escrito em partes desse tamanho
# Uma frase por cena (só frases bem curtas se juntam): a tela muda a cada ~8 s. Frase longa não é cortada no meio,
# para não estragar a entonação da narração; ela ganha um segundo visual na metade (visuais._segundos_visuais)
CARACTERES_POR_CENA = 100
LIMITE_TITULO = 100          # o YouTube aceita até 100 caracteres no título

# Tipos de abertura da REGRA DE DIVERSIDADE do Prompt Mestre
ABERTURAS_NARRATIVAS = ["in medias res", "confronto direto", "descoberta de um segredo",
                        "humilhação ou injustiça pública", "flashback breve com retorno ao presente", "decisão urgente"]
ABERTURAS_INFORMATIVAS = ["pergunta provocadora", "fato chocante", "cena reconstruída de um momento histórico",
                          "in medias res", "descoberta de um segredo", "flashback breve com retorno ao presente"]

IDIOMAS = {
    "português": ("pt", "pt-BR-AntonioNeural"), "portugues": ("pt", "pt-BR-AntonioNeural"),
    "italiano": ("it", "it-IT-DiegoNeural"),
    "espanhol": ("es", "es-ES-AlvaroNeural"),
    "inglês": ("en", "en-US-AndrewNeural"), "ingles": ("en", "en-US-AndrewNeural"),
    "alemão": ("de", "de-DE-ConradNeural"), "alemao": ("de", "de-DE-ConradNeural"),
    "francês": ("fr", "fr-FR-HenriNeural"), "frances": ("fr", "fr-FR-HenriNeural"),
}


def _sistema():
    return ("Você é um roteirista profissional de canais dark do YouTube. Siga rigorosamente o PROMPT MESTRE abaixo. "
            "Nesta automação cada pedido executa só uma parte do trabalho; obedeça ao formato pedido em cada um.\n\n"
            + PROMPT_MESTRE.read_text(encoding="utf-8"))


# ---------- títulos (a partir das referências do YouTube) ----------

def gerar_titulos(nicho, referencias, quantidade=10):
    lista = "\n".join(f"- {v['titulo']} ({v['views']:,} views, outlier {v['outlier']}x)" for v in referencias)
    prompt = f"""Nicho: {nicho}
Títulos de referência que performaram muito acima da média dos canais:
{lista}

1. Identifique os padrões que fazem esses títulos funcionarem (estrutura, gatilhos, tamanho, palavras).
2. Crie {quantidade} títulos ORIGINAIS para um novo vídeo longo neste nicho seguindo esses padrões
   (máx. 70 caracteres, sem copiar os de referência).
3. Para cada título, sugira um texto curto de thumbnail (até 4 palavras) e o tema central do vídeo.

Formato: {{"padroes": ["..."], "titulos": [{{"titulo": "...", "gatilho": "curiosidade|medo|polêmica|...",
"texto_thumb": "...", "tema": "..."}}]}}"""
    return llm.chat_json(prompt, "Você é especialista em títulos e CTR no YouTube.", temperatura=0.9)


# ---------- referência ----------

def _texto_html(html):
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    titulo = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    texto = re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html)).strip()
    return (titulo.group(1).strip() if titulo else ""), texto


def _eh_link(referencia):
    return referencia.lower().startswith(("http://", "https://"))


def _parecidos(titulo, referencia):
    """Mais da metade das palavras significativas em comum = cópia da referência."""
    palavras = lambda t: {p for p in re.findall(r"\w+", t.lower()) if len(p) > 2}
    a, b = palavras(titulo), palavras(referencia)
    return bool(a and b) and len(a & b) / min(len(a), len(b)) > 0.5


def ler_referencia(referencia):
    """Transforma a referência (título ou link) no texto que vai para o BLOCO DE ENTRADA."""
    if not referencia.lower().startswith(("http://", "https://")):
        return f"(TÍTULO) {referencia}"
    try:
        if "youtube.com" in referencia or "youtu.be" in referencia:
            o = requests.get("https://www.youtube.com/oembed", params={"url": referencia, "format": "json"}, timeout=20)
            o.raise_for_status()
            dados = o.json()
            texto = f"(LINK de vídeo) {referencia}\nTítulo: {dados['title']}\nCanal: {dados.get('author_name', '')}"
            vid = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", referencia)
            if vid and config.YOUTUBE_API_KEY:
                r = requests.get("https://www.googleapis.com/youtube/v3/videos",
                                 params={"part": "snippet", "id": vid.group(1), "key": config.YOUTUBE_API_KEY}, timeout=20)
                itens = r.json().get("items", []) if r.ok else []
                if itens:
                    texto += f"\nDescrição: {itens[0]['snippet']['description'][:3000]}"
            return texto + "\n(Somente título/descrição disponíveis; o conteúdo falado do vídeo não foi acessado.)"
        r = requests.get(referencia, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        titulo, texto = _texto_html(r.text)
        return f"(LINK de artigo) {referencia}\nTítulo: {titulo}\nTexto: {texto[:6000]}"
    except Exception as e:
        return (f"(LINK) {referencia}\nO link NÃO pôde ser acessado ({e.__class__.__name__}). Informe isso na ficha "
                "e trabalhe só com o que está disponível, sem inventar o conteúdo do link.")


def _aberturas_recentes():
    try:
        return json.loads(HISTORICO_ABERTURAS.read_text(encoding="utf-8"))[-6:]
    except (OSError, ValueError):
        return []


def _registrar_abertura(tipo):
    historico = _aberturas_recentes() + [tipo]
    HISTORICO_ABERTURAS.parent.mkdir(parents=True, exist_ok=True)
    HISTORICO_ABERTURAS.write_text(json.dumps(historico[-20:], ensure_ascii=False), encoding="utf-8")


# ---------- ficha ----------

def gerar_ficha(entrada):
    recentes = ", ".join(_aberturas_recentes()) or "nenhuma"
    prompt = f"""BLOCO DE ENTRADA
IDIOMA: {entrada['idioma']}
REFERÊNCIA: {ler_referencia(entrada['referencia'])}
NICHO: {entrada.get('nicho') or '(não informado: classifique)'}
CAPÍTULOS: {entrada['capitulos']}
TOTAL DE CARACTERES: {entrada['caracteres']}
META DO CANAL (CTA): {entrada.get('meta') or '(não informada)'}
OBSERVAÇÕES EXTRAS: {entrada.get('observacoes') or '(nenhuma)'}
Aberturas usadas nos roteiros mais recentes (escolha um tipo diferente): {recentes}

Execute as ETAPAS 1, 2 e 3 e devolva a FICHA DE PLANEJAMENTO. Textos da ficha em português, exceto
"titulo_final" e "titulo_no_idioma", que ficam no IDIOMA. Use este JSON:
"titulo_final" deve ter NO MÁXIMO {LIMITE_TITULO} caracteres e ser chamativo para o YouTube.
{{"titulo_final": "...", "nicho": "A|B|C|D|E", "nicho_descricao": "...", "registro": "...",
"promessa": "uma frase", "contexto": "A/D: ano, lugar/Estado, regime legal e social; B: país, cidade, época; C: tema, recorte",
"fatos_principais": ["só para C/D: fatos reais e verificáveis"],
"personagens": [{{"nome": "...", "titulo_cargo": "...", "idade": "...", "papel": "...", "motivacao": "..."}}],
"abertura": "tipo escolhido", "referencia_acessivel": true, "observacao_referencia": "...",
"resumo_titulo": "rascunho do resumo do título para o primeiro parágrafo (duas ou três frases, sem revelar o desfecho)",
"loops_abertura": [{{"loop": "pergunta ou mistério aberto na abertura", "responder_no_capitulo": 3}}],
"revelacao_principal": {{"o_que": "a resposta completa da promessa", "capitulo": 4}},
"pontos_intersecao": [{{"capitulo": 1, "ponto": "transição prevista", "gatilho": "tipo de gatilho", "ideia": "o que intriga"}}],
"capitulos": [{{"numero": 1, "titulo_no_idioma": "nome curto para os capítulos do YouTube", "resumo": "uma linha"}}]}}"""
    ficha = llm.chat_json(prompt, _sistema(), temperatura=0.8)
    ref = re.search(r"Título: (.+)", ler_referencia(entrada["referencia"])) if _eh_link(entrada["referencia"]) else None
    if ref and _parecidos(ficha["titulo_final"], ref.group(1)):
        # Etapa 1: com link, o título tem que ser NOVO, só inspirado no molde da referência
        novo = llm.chat_json(
            f'Título da referência: "{ref.group(1)}"\nTítulo proposto (parecido demais): "{ficha["titulo_final"]}"\n'
            f"Promessa do vídeo: {ficha.get('promessa', '')}\n"
            f"Crie um título NOVO e original em {entrada['idioma']}, com o mesmo apelo, mas com outra estrutura e "
            f"outras palavras, no máximo {LIMITE_TITULO} caracteres. Formato: {{\"titulo\": \"...\"}}",
            "Você é especialista em títulos e CTR no YouTube.", temperatura=0.9)
        ficha["titulo_final"] = novo.get("titulo") or ficha["titulo_final"]
    if len(ficha["titulo_final"]) > LIMITE_TITULO:
        ficha["titulo_final"] = ficha["titulo_final"][:LIMITE_TITULO].rsplit(" ", 1)[0].rstrip(" ,-:")
    # Regra de diversidade: o modelo às vezes ignora o histórico, então a troca é garantida aqui
    usadas = [a.lower() for a in _aberturas_recentes()[-3:]]
    if ficha.get("abertura", "").lower() in usadas:
        opcoes = ABERTURAS_NARRATIVAS if ficha.get("nicho") in ("A", "B") else ABERTURAS_INFORMATIVAS
        livres = [a for a in opcoes if a.lower() not in usadas]
        ficha["abertura"] = random.choice(livres or opcoes)
    if len(ficha.get("capitulos", [])) != entrada["capitulos"]:
        raise RuntimeError(f"A ficha veio com {len(ficha.get('capitulos', []))} capítulos em vez de {entrada['capitulos']}")
    return ficha


def ficha_md(ficha, entrada):
    linhas = [f"# Ficha de planejamento — {ficha['titulo_final']}", "",
              f"- **Nicho:** {ficha['nicho']} — {ficha.get('nicho_descricao', '')}",
              f"- **Idioma / registro:** {entrada['idioma']} — {ficha.get('registro', '')}",
              f"- **Promessa:** {ficha.get('promessa', '')}",
              f"- **Contexto:** {ficha.get('contexto', '')}",
              f"- **Abertura:** {ficha.get('abertura', '')}",
              f"- **Referência:** {entrada['referencia']}"
              + ("" if ficha.get("referencia_acessivel", True) else " (NÃO acessível)")]
    if ficha.get("observacao_referencia"):
        linhas.append(f"- **Sobre a referência:** {ficha['observacao_referencia']}")
    if ficha.get("fatos_principais"):
        linhas += ["", "## Fatos principais", *[f"- {f}" for f in ficha["fatos_principais"]]]
    if ficha.get("personagens"):
        linhas += ["", "## Personagens"]
        linhas += [f"- **{p['nome']}** ({p.get('titulo_cargo', '')}, {p.get('idade', '')}): {p.get('papel', '')} — "
                   f"{p.get('motivacao', '')}" for p in ficha["personagens"]]
    if ficha.get("resumo_titulo"):
        linhas += ["", "## Resumo do título (primeiro parágrafo)", ficha["resumo_titulo"]]
    if ficha.get("loops_abertura"):
        linhas += ["", "## Loops de curiosidade da abertura"]
        linhas += [f"- {l.get('loop', '')} → responder no capítulo {l.get('responder_no_capitulo', '?')}"
                   for l in ficha["loops_abertura"]]
    if ficha.get("revelacao_principal"):
        rp = ficha["revelacao_principal"]
        linhas += ["", f"## Revelação principal (capítulo {rp.get('capitulo', '?')})", rp.get("o_que", "")]
    if ficha.get("pontos_intersecao"):
        linhas += ["", "## Pontos de interseção e gatilhos"]
        linhas += [f"- Cap. {p.get('capitulo', '?')}: {p.get('ponto', '')} → **{p.get('gatilho', '')}**: {p.get('ideia', '')}"
                   for p in ficha["pontos_intersecao"]]
    linhas += ["", "## Capítulos", *[f"{c['numero']}. **{c['titulo_no_idioma']}** — {c['resumo']}" for c in ficha["capitulos"]]]
    return "\n".join(linhas)


# ---------- escrita ----------

def _decodificar_escapes(texto):
    """O modelo às vezes devolve "\\u2019" literal no texto; a voz leria isso em voz alta."""
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), texto)


def _limpar_texto(texto):
    texto = _decodificar_escapes(texto)
    texto = re.sub(r"(?m)^\s*(#+.*|\*\*\*+|---+|capítulo\s+\d+.*|chapter\s+\d+.*|\d+\s*)$", "", texto, flags=re.I)
    texto = texto.replace("**", "").replace("*", "").replace("_", " ")
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def _escrever_parte(ficha, entrada, cap, total_caps, parte, total_partes, alvo, texto_cap, final_anterior):
    modulo = "NARRATIVO" if ficha["nicho"] in ("A", "B") else "INFORMATIVO"
    instr = [f'Escreva a PARTE {parte} de {total_partes} do CAPÍTULO {cap["numero"]} de {total_caps}: {cap["resumo"]}',
             f"Siga o MÓDULO {modulo} para o capítulo {cap['numero']}.",
             "Coloque um GATILHO DE CURIOSIDADE em cada ponto de interseção (mudança de cena, de tempo, de assunto ou de "
             "fato, antes de revelações e antes do CTA), variando o tipo e pagando os gatilhos já abertos."]
    gatilhos = [p for p in ficha.get("pontos_intersecao", []) if str(p.get("capitulo")) == str(cap["numero"])]
    if gatilhos:
        instr.append(f"Gatilhos planejados na ficha para este capítulo: {json.dumps(gatilhos, ensure_ascii=False)}")
    if cap["numero"] == 1 and parte == 1:
        instr.append(f'Comece com uma abertura do tipo "{ficha.get("abertura", "")}". O PRIMEIRO PARÁGRAFO (cerca de '
                     "seiscentos a setecentos caracteres, 30 a 45 segundos) é a ABERTURA: segue a REGRA DE ABERTURA "
                     "(resumo do título: o que acontece, nunca como termina) e a REGRA DE RETENÇÃO DA ABERTURA: "
                     "primeira frase confirma a promessa do título com o elemento mais chocante ou curioso; depois "
                     "tensão; depois pelo menos dois loops de curiosidade; e fecha com uma transição forte. Frases "
                     "curtas. Sem saudação e sem pedido de inscrição"
                     + (f'. Rascunho da ficha: "{ficha["resumo_titulo"]}"' if ficha.get("resumo_titulo") else "")
                     + (f". Loops planejados: {json.dumps(ficha['loops_abertura'], ensure_ascii=False)}"
                        if ficha.get("loops_abertura") else "") + ".")
        instr.append("Logo DEPOIS da abertura (primeiro parágrafo), faça o CTA 1: duas a três frases curtas, inscrição com "
                     f"um motivo concreto ligado ao tema (meta do canal: {entrada.get('meta') or 'crescer o canal'}) e uma "
                     "pergunta específica sobre o tema para os comentários.")
    revelacao = ficha.get("revelacao_principal") or {}
    if revelacao and str(revelacao.get("capitulo")) != str(cap["numero"]):
        instr.append(f'NÃO revele ainda a resposta principal da promessa ("{revelacao.get("o_que", "")}"): ela é guardada '
                     f'para o capítulo {revelacao.get("capitulo")}.')
    loops_aqui = [l for l in ficha.get("loops_abertura", []) if str(l.get("responder_no_capitulo")) == str(cap["numero"])]
    if loops_aqui:
        instr.append(f"Responda neste capítulo os loops abertos na abertura: {json.dumps(loops_aqui, ensure_ascii=False)}")
    if parte < total_partes:
        instr.append("NÃO termine o capítulo nem faça CTA: pare num ponto natural para a próxima parte continuar.")
    else:
        # Regra dos 3 CTAs (24/10/2026): abertura, meio (fim do capítulo do meio) e final; os outros só com gancho
        meta = entrada.get('meta') or 'crescer o canal'
        if cap["numero"] == total_caps:
            instr.append(f"Termine com o CTA 3 (meta do canal: {meta}): like, inscrição, sininho, uma pergunta específica "
                         "para os comentários e o pedido de sugestões de temas para os próximos vídeos, saindo do que foi "
                         "contado, sem dizer a palavra capítulo.")
            instr.append("É o FINAL do roteiro: fechamento total, sem gancho para outro episódio.")
        elif cap["numero"] == max(1, total_caps // 2):
            instr.append(f"Termine com o CTA 2, do meio do vídeo (meta do canal: {meta}): like, inscrição e uma pergunta "
                         "específica sobre o tema, saindo de um fato forte e voltando com um gancho para a segunda metade, "
                         "sem dizer a palavra capítulo.")
        else:
            instr.append("Termine só com um gancho de curiosidade para o próximo trecho. NÃO peça like, inscrição nem "
                         "comentário aqui.")
    if texto_cap:
        instr.append(f'Texto já escrito neste capítulo (continue exatamente de onde parou, sem repetir): "...{texto_cap[-1500:]}"')
    elif final_anterior:
        instr.append(f'Final do capítulo anterior (para dar continuidade, sem repetir): "...{final_anterior[-800:]}"')

    prompt = f"""FICHA DE PLANEJAMENTO (respeite nomes, cargos, datas e idades):
{json.dumps(ficha, ensure_ascii=False)}

{chr(10).join(instr)}

Tamanho: cerca de {alvo} caracteres, ou seja, por volta de {_frases(alvo)} frases. Não passe de {_frases(alvo * 1.1)} frases.
Escreva SOMENTE o texto a ser narrado, 100% em {entrada['idioma']}, contínuo, sem títulos, listas, marcações
ou emojis, com todos os números por extenso."""
    texto = _limpar_texto(llm.chat(prompt, _sistema(), temperatura=0.85, max_tokens=4096))
    if len(texto) < alvo * 0.7:
        # Modelos costumam encurtar: pede a continuação uma vez
        falta = alvo - len(texto)
        mais = llm.chat(prompt + f'\n\nVocê já escreveu: "...{texto[-1200:]}"\nContinue a partir daí com mais '
                        f"{falta} caracteres, sem repetir nada.", _sistema(), temperatura=0.85, max_tokens=4096)
        texto += " " + _limpar_texto(mais)
    return texto


CARACTERES_POR_FRASE = 110  # média aproximada; modelos controlam tamanho melhor por nº de frases


def _frases(caracteres):
    return max(3, round(caracteres / CARACTERES_POR_FRASE))


def _contar_frases(texto):
    return len([f for f in re.split(r"(?<=[.!?…])\s+", texto) if f.strip()])


def _ajustar_tamanho(ficha, entrada, numero, texto, alvo):
    """Capítulo muito maior que o pedido desequilibra o vídeo: pede uma versão condensada."""
    if len(texto) <= alvo * 1.3:
        return texto
    prompt = f"""FICHA: {json.dumps(ficha, ensure_ascii=False)}

O CAPÍTULO {numero} abaixo tem {_contar_frases(texto)} frases ({len(texto)} caracteres), mas deve ter
NO MÁXIMO {_frases(alvo)} frases (cerca de {alvo} caracteres). Reescreva-o condensado: mantenha só os acontecimentos
essenciais, os nomes, o tom e o CTA final; corte descrições secundárias e repetições.
Escreva SOMENTE o texto narrado, 100% em {entrada['idioma']}, contínuo, sem títulos, listas, marcações
ou emojis, com todos os números por extenso.

CAPÍTULO {numero}:
{texto}"""
    novo = _limpar_texto(llm.chat(prompt, _sistema(), temperatura=0.6, max_tokens=8192))
    return novo if alvo * 0.6 <= len(novo) < len(texto) else texto


def _revisar_capitulo(ficha, entrada, numero, texto):
    """Verificação obrigatória: anacronismos, fatos inventados, números, idioma, CTA, consistência."""
    com_digitos = [f for f in re.split(r"(?<=[.!?])\s+", texto) if re.search(r"\d", f)]
    total = len(ficha["capitulos"])
    if numero == 1 and total > 1:
        cta = ("O CTA 1 logo após o primeiro parágrafo é obrigatório, não o apague; o FINAL deste capítulo NÃO pode pedir "
               "like, inscrição nem comentário (só um gancho): se pedir, apague esse pedido.")
    elif numero == total:
        cta = ("O FINAL precisa ter o CTA 3 (like, inscrição, sininho, pergunta para os comentários e pedido de sugestões "
               "de temas); aponte se faltar.")
    elif numero == max(1, total // 2):
        cta = "O FINAL precisa ter o CTA 2 (like, inscrição e uma pergunta específica sobre o tema); aponte se faltar."
    else:
        cta = ("Este capítulo NÃO pode ter pedido de like, inscrição ou comentário (só um gancho no final): se tiver, "
               "apague esse pedido.")
    prompt = f"""FICHA: {json.dumps(ficha, ensure_ascii=False)}

Revise o CAPÍTULO {numero} abaixo conforme os ALERTAS UNIVERSAIS, REGRAS GERAIS e REGRAS DE OURO:
anacronismos, fatos/datas/citações inventados (nichos C e D), números que não estão por extenso,
trechos fora do idioma {entrada['idioma']}, erros de gramática (gênero e concordância de substantivos e artigos,
ex.: em italiano é "la dote", não "il dote"), nomes/cargos/idades diferentes da ficha,
CONTEÚDO REPETIDO (um parágrafo ou ideia que já foi dita antes no capítulo, inclusive com outras palavras): nesse caso
dê "trecho_corrigido" vazio ("") para apagar a repetição, frase por frase.
CTAs (regra dos três CTAs): {cta}
{"Confira também se o primeiro parágrafo resume o título sem revelar o desfecho, se a primeira frase confirma a promessa do título, se não há saudação nem pedido de inscrição dentro dele e se abre pelo menos dois loops de curiosidade." if numero == 1 else ""}
Gatilhos de curiosidade: aponte gatilhos que nunca são pagos, frases-clichê repetidas e gatilhos que inventam fatos (nichos C e D).
Atenção especial a fatos técnicos atribuídos ao produto/pessoa/época errados (ex.: defeito de um motor atribuído a outro).
Frases com dígitos encontradas (devem ir por extenso): {json.dumps(com_digitos, ensure_ascii=False)}

Para cada problema, copie o trecho_original EXATAMENTE como está no texto (curto, só a frase afetada)
e dê o trecho_corrigido. Se não houver problemas, devolva lista vazia.
Formato: {{"problemas": [{{"tipo": "...", "trecho_original": "...", "trecho_corrigido": "...", "motivo": "..."}}]}}

CAPÍTULO {numero}:
{texto}"""
    problemas = llm.chat_json(prompt, _sistema(), temperatura=0.2, pensar=True).get("problemas", [])
    aplicados = []
    for p in problemas:
        novo_texto = _trocar(texto, p.get("trecho_original", ""), p.get("trecho_corrigido", ""))
        if novo_texto is not None:
            texto = novo_texto
            aplicados.append(p)
        else:
            p["nao_aplicada"] = True
            aplicados.append(p)
    return texto, aplicados, len(problemas)


_ASPAS = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"}


def _trocar(texto, original, novo):
    """Aplica a correção mesmo se o modelo copiou o trecho com aspas/espaços/pontuação final diferentes.

    Devolve o texto corrigido, ou None se o trecho não foi encontrado.
    """
    if not original or novo is None:
        return None  # novo == "" é permitido: apaga o trecho (ex.: conteúdo repetido)
    if original in texto:
        return texto.replace(original, novo, 1)
    # Monta uma busca tolerante: espaços flexíveis, aspas retas = curvas, sem exigir a pontuação final
    nucleo = original.strip().rstrip(".!?,;:").strip()
    partes = []
    for ch in nucleo:
        if ch.isspace():
            if not partes or partes[-1] != r"\s+":
                partes.append(r"\s+")
        elif ch in "'’‘":
            partes.append("['’‘]")
        elif ch in '"“”':
            partes.append('["“”]')
        elif ch in "-–—":
            partes.append("[-–—]")
        else:
            partes.append(re.escape(ch))
    achado = re.search("".join(partes), texto, flags=re.IGNORECASE)
    if not achado:
        return None
    substituto = novo.strip()
    if texto[achado.end():achado.end() + 1] in tuple(".!?,;:"):
        # A pontuação final ficou fora da busca e continua no texto; evita duplicar
        substituto = substituto.rstrip(".!?,;:")
    return texto[:achado.start()] + substituto + texto[achado.end():]


def _checklist(ficha, entrada, capitulos_texto):
    completo = "\n\n".join(f"[{i}]\n{t}" for i, t in enumerate(capitulos_texto, 1))
    prompt = f"""FICHA: {json.dumps(ficha, ensure_ascii=False)}
Tamanho pedido por capítulo: cerca de {entrada['caracteres'] // entrada['capitulos']} caracteres.
Tamanhos reais: {[len(t) for t in capitulos_texto]}

Aplique o CHECKLIST FINAL ao roteiro abaixo.
Formato: {{"itens": [{{"item": "...", "ok": true, "observacao": "..."}}]}}

ROTEIRO:
{completo}"""
    return llm.chat_json(prompt, _sistema(), temperatura=0.2, pensar=True).get("itens", [])


def _corrigir_checklist(ficha, entrada, capitulos_texto, falhas):
    """"Se qualquer item falhar, corrigir antes de entregar": troca pontual dos trechos problemáticos."""
    completo = "\n\n".join(f"[{i}]\n{t}" for i, t in enumerate(capitulos_texto, 1))
    lista = "\n".join(f"- {f.get('item')}: {f.get('observacao')}" for f in falhas)
    prompt = f"""FICHA: {json.dumps(ficha, ensure_ascii=False)}

O CHECKLIST FINAL apontou estas falhas no roteiro abaixo:
{lista}

Corrija cada falha com trocas pontuais de texto (não reescreva capítulos inteiros; tamanho não precisa ser corrigido).
Copie o trecho_original EXATAMENTE como está no roteiro e dê o trecho_corrigido, 100% em {entrada['idioma']}.
Formato: {{"problemas": [{{"tipo": "...", "capitulo": 1, "trecho_original": "...", "trecho_corrigido": "...", "motivo": "..."}}]}}

ROTEIRO:
{completo}"""
    problemas = llm.chat_json(prompt, _sistema(), temperatura=0.2, pensar=True).get("problemas", [])
    aplicados = []
    for p in problemas:
        for i, texto in enumerate(capitulos_texto):
            novo_texto = _trocar(texto, p.get("trecho_original", ""), p.get("trecho_corrigido", ""))
            if novo_texto is not None:
                capitulos_texto[i] = novo_texto
                aplicados.append(p)
                break
        else:
            p["nao_aplicada"] = True
            aplicados.append(p)
    return aplicados


# ---------- cenas ----------

def _dividir_em_cenas(texto):
    frases = [f.strip() for f in re.split(r"(?<=[.!?…])\s+", texto.replace("\n", " ")) if f.strip()]
    cenas, atual = [], ""
    for f in frases:
        if atual and len(atual) + len(f) > CARACTERES_POR_CENA:
            cenas.append(atual)
            atual = f
        else:
            atual = f"{atual} {f}".strip()
    if atual:
        cenas.append(atual)
    return cenas


def completar_palavras_chave(roteiro, ao_progredir=print):
    """Cenas sem busca de imagem (o modelo às vezes devolve menos itens que o pedido): pede de novo só para elas."""
    for tentativa in range(3):
        faltando = [c for c in roteiro["cenas"] if not c.get("busca_stock")]
        if not faltando:
            return
        ao_progredir(f"  completando busca de imagem de {len(faltando)} cena(s)...")
        for cena, chave in zip(faltando, _palavras_chave(roteiro["ficha"], [c["narracao"] for c in faltando], lote_max=8)):
            if chave.get("busca_stock"):
                cena["visual"] = chave.get("visual") if chave.get("visual") in ("stock", "ia") else "ia"
                cena["busca_stock"] = chave["busca_stock"]
                cena["busca_segura"] = chave.get("busca_segura", "")
                cena["busca_wiki"] = chave.get("busca_wiki", "")
                cena["prompt_imagem"] = chave.get("prompt_imagem", "")


def _palavras_chave(ficha, textos, lote_max=12):
    """Pede ao modelo a busca de imagem de cada cena (com época/lugar da ficha), em lotes paralelos.

    Lotes menores devolvem a quantidade certa de itens com mais frequência e rodam juntos.
    """
    lotes = [textos[i:i + lote_max] for i in range(0, len(textos), lote_max)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        resultados = list(pool.map(lambda lote: _palavras_chave_lote(ficha, lote), lotes))
    return [item for lote in resultados for item in lote]


def _palavras_chave_lote(ficha, lote):
    prompt = f"""Contexto do vídeo: {ficha.get('contexto', '')} | {ficha['titulo_final']}
Para cada trecho de narração abaixo, escolha o visual (o vídeo final deve ter cerca de METADE das cenas em "stock",
com movimento, alternando com as imagens):
- "stock" = vídeo de banco com movimento (paisagens, multidões, natureza, cidade, mar, fogo, cavalos...);
- "ia" = imagem estática (retratos, objetos, documentos, interiores de época, cenas específicas).
Dê "busca_stock": 2 a 4 palavras simples em INGLÊS que funcionem num banco de imagens, refletindo a
época e o lugar com palavras de estilo, NUNCA com anos ou números (ex.: "victorian ballroom", "medieval castle night",
"baroque church interior", "vintage letter candle"). Prefira o OBJETO CONCRETO do trecho (o carro, a pessoa, o
lugar) a conceitos; nos trechos de pedido de inscrição use uma imagem do tema do vídeo, nunca "subscribe button".
Dê também "busca_segura": 1 a 2 palavras em INGLÊS, concretas e que COM CERTEZA existem num banco de fotos,
sempre ligadas ao assunto do vídeo (ex.: "porsche 911", "engine bay", "mechanic", "used cars", "castle", "roman soldier").
Ela é usada quando a busca específica não acha nada; nunca use conceitos abstratos nela.
Dê também "prompt_imagem" em inglês, cinematográfico e detalhado, sem texto na imagem.
Dê também "busca_wiki": quando o trecho fala de um modelo, pessoa, lugar ou objeto ESPECÍFICO e real, o nome exato
para buscar no Wikimedia Commons (ex.: "Saab 900", "Pontiac G8", "Jaguar E-Type", "Colosseum"); senão, "".
Devolva exatamente {len(lote)} itens, na mesma ordem.
Formato: {{"cenas": [{{"visual": "stock|ia", "busca_stock": "...", "busca_segura": "...", "busca_wiki": "...", "prompt_imagem": "..."}}]}}

TRECHOS:
{json.dumps(lote, ensure_ascii=False)}"""
    itens = llm.chat_json(prompt, "Você é editor de vídeo e pesquisador de imagens.", temperatura=0.5)["cenas"]
    return (itens + [{}] * len(lote))[:len(lote)]


def _descricao(ficha, entrada, inicio):
    capitulos = "; ".join(f"{c['titulo_no_idioma']}: {c['resumo']}" for c in ficha["capitulos"])
    prompt = f"""Título: {ficha['titulo_final']}
Promessa: {ficha.get('promessa', '')}
Capítulos: {capitulos}
Início do roteiro: {inicio[:1500]}

Escreva em {entrada['idioma']} uma descrição otimizada para o YouTube (2 a 3 parágrafos, sem emojis) e 15 tags.
Seja fiel ao roteiro: não cite números, preços, datas ou dados que não estejam no texto acima e não diga que o
vídeo "analisa dados" se ele não faz isso.
Formato: {{"descricao": "...", "tags": ["..."]}}"""
    return llm.chat_json(prompt, "Você é especialista em SEO para YouTube.", temperatura=0.6)


# ---------- principal ----------

def gerar_roteiro(entrada, pasta_projeto, ao_progredir=print):
    """entrada: idioma, referencia, nicho, capitulos, caracteres, meta, observacoes.

    Salva o progresso em _parcial.json a cada capítulo: se cair no meio, rodar de novo continua de onde parou.
    """
    idioma = entrada["idioma"].lower()
    codigo, voz = IDIOMAS.get(idioma, ("pt", config.VOZ))

    arquivo_parcial = pasta_projeto / "_parcial.json"
    parcial = {}
    if arquivo_parcial.exists():
        parcial = json.loads(arquivo_parcial.read_text(encoding="utf-8"))
        if parcial.get("entrada") != entrada:
            parcial = {}  # pedido diferente: começa do zero
        else:
            ao_progredir(f"  retomando: {len(parcial.get('brutos', []))} capítulo(s) já escritos")

    def salvar_parcial():
        arquivo_parcial.write_text(json.dumps(parcial, ensure_ascii=False), encoding="utf-8")

    if "ficha" not in parcial:
        ao_progredir("  montando ficha de planejamento...")
        parcial = {"entrada": entrada, "ficha": gerar_ficha(entrada), "brutos": [], "revisados": {}}
        salvar_parcial()
    ficha = parcial["ficha"]
    for n, cap in enumerate(ficha["capitulos"], 1):
        # O modelo às vezes muda o nome dos campos; garante os que o resto do código usa
        cap["numero"] = n
        cap["titulo_no_idioma"] = cap.get("titulo_no_idioma") or cap.get("titulo") or cap.get("nome") or str(n)
        cap["resumo"] = cap.get("resumo") or cap.get("descricao") or cap["titulo_no_idioma"]
    ao_progredir(f"  título: {ficha['titulo_final']} | nicho {ficha['nicho']} | abertura: {ficha.get('abertura')}")

    total = entrada["capitulos"]
    alvo_cap = entrada["caracteres"] // total
    partes = max(1, math.ceil(alvo_cap / CARACTERES_POR_PARTE))
    # "brutos" = capítulos escritos; "revisados" = já passaram pela revisão (chave = nº do capítulo)
    brutos = parcial.setdefault("brutos", [])
    revisados = parcial.setdefault("revisados", {})

    def revisar(numero, texto):
        ao_progredir(f"  revisando capítulo {numero} em paralelo ({len(texto):,} caracteres)...")
        corrigido, aplicados, encontrados = _revisar_capitulo(ficha, entrada, numero, texto)
        feitos = sum(1 for a in aplicados if not a.get("nao_aplicada"))
        ao_progredir(f"    capítulo {numero}: {encontrados} problema(s) apontado(s), {feitos} corrigido(s)")
        return numero, corrigido, aplicados

    # A revisão (lenta, com raciocínio) de um capítulo roda enquanto o seguinte é escrito.
    # A escrita continua em sequência porque cada capítulo parte do final do anterior.
    with ThreadPoolExecutor(max_workers=total) as pool:
        futuros = [pool.submit(revisar, i, t) for i, t in enumerate(brutos, 1) if str(i) not in revisados]
        for cap in ficha["capitulos"][len(brutos):]:
            texto = ""
            for p in range(1, partes + 1):
                ao_progredir(f"  escrevendo capítulo {cap['numero']}/{total} — parte {p}/{partes}")
                final_anterior = brutos[-1] if brutos else ""
                novo = _escrever_parte(ficha, entrada, cap, total, p, partes, alvo_cap // partes, texto, final_anterior)
                texto = f"{texto}\n\n{novo}".strip()
            if len(texto) > alvo_cap * 1.3:
                ao_progredir(f"  condensando capítulo {cap['numero']} ({len(texto):,} → ~{alvo_cap:,} caracteres)...")
                texto = _ajustar_tamanho(ficha, entrada, cap["numero"], texto, alvo_cap)
            brutos.append(texto)
            salvar_parcial()
            futuros.append(pool.submit(revisar, cap["numero"], texto))
        for futuro in as_completed(futuros):
            numero, corrigido, aplicados = futuro.result()
            revisados[str(numero)] = {"texto": corrigido, "correcoes": aplicados}
            salvar_parcial()

    capitulos_texto = [revisados[str(n)]["texto"] for n in range(1, total + 1)]
    revisoes = [{"capitulo": n, "correcoes": revisados[str(n)]["correcoes"]} for n in range(1, total + 1)]

    ao_progredir("  aplicando checklist final...")
    checklist = _checklist(ficha, entrada, capitulos_texto)
    falhas = [i for i in checklist if not i.get("ok") and "tamanho" not in str(i.get("item", "")).lower()]
    for item in checklist:
        if not item.get("ok"):
            ao_progredir(f"    falhou: {item.get('item')} — {item.get('observacao')}")
    if falhas:
        ao_progredir("  corrigindo as falhas do checklist...")
        aplicados = _corrigir_checklist(ficha, entrada, capitulos_texto, falhas)
        feitos = sum(1 for a in aplicados if not a.get("nao_aplicada"))
        ao_progredir(f"    {feitos} correção(ões) aplicada(s) de {len(aplicados)}")
        revisoes.append({"capitulo": "checklist", "correcoes": aplicados})

    ao_progredir("  dividindo em cenas e escolhendo imagens...")
    cenas = []
    for cap, texto in zip(ficha["capitulos"], capitulos_texto):
        for trecho in _dividir_em_cenas(texto):
            cenas.append({"secao": cap["titulo_no_idioma"], "capitulo": cap["numero"], "narracao": trecho})
    with ThreadPoolExecutor(max_workers=1) as pool:
        # A descrição do YouTube sai enquanto as buscas de imagem são escolhidas
        futuro_seo = pool.submit(_descricao, ficha, entrada, capitulos_texto[0])
        for cena, chave in zip(cenas, _palavras_chave(ficha, [c["narracao"] for c in cenas])):
            cena["visual"] = chave.get("visual") if chave.get("visual") in ("stock", "ia") else "ia"
            cena["busca_stock"] = chave.get("busca_stock", "")
            cena["busca_segura"] = chave.get("busca_segura", "")
            cena["busca_wiki"] = chave.get("busca_wiki", "")
            cena["prompt_imagem"] = chave.get("prompt_imagem", "")
        for n, cena in enumerate(cenas, 1):
            cena["id"] = n
        completar_palavras_chave({"ficha": ficha, "cenas": cenas}, ao_progredir)
        seo = futuro_seo.result()
    _registrar_abertura(ficha.get("abertura", ""))
    arquivo_parcial.unlink(missing_ok=True)
    return {
        "titulo": ficha["titulo_final"],
        "idioma": entrada["idioma"],
        "idioma_codigo": codigo,
        "voz": voz,
        "nicho": ficha["nicho"],
        "entrada": entrada,
        "ficha": ficha,
        "capitulos_texto": capitulos_texto,
        "revisoes": revisoes,
        "checklist": checklist,
        "descricao_youtube": seo.get("descricao", ""),
        "tags": seo.get("tags", []),
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "cenas": cenas,
    }


def roteiro_md(roteiro):
    caracteres = sum(len(t) for t in roteiro["capitulos_texto"])
    linhas = [f"# {roteiro['titulo']}", "",
              f"{len(roteiro['capitulos_texto'])} capítulos · {caracteres:,} caracteres · "
              f"≈ {caracteres / CARACTERES_POR_MINUTO:.0f} min de narração · {len(roteiro['cenas'])} cenas", ""]
    for i, texto in enumerate(roteiro["capitulos_texto"], 1):
        linhas += [str(i), "", texto, ""]
    return "\n".join(linhas)


def para_gravar(roteiro):
    """Só o texto lido em voz alta (sem título, números de capítulo nem contagens): o usuário grava a própria voz
    a partir dele (pedido de 24/10/2026)."""
    return "\n\n".join(t.strip() for t in roteiro["capitulos_texto"]) + "\n"


def revisao_md(roteiro):
    linhas = ["# Revisão e checklist", "", "## Checklist final", ""]
    for item in roteiro["checklist"]:
        linhas.append(f"- {'OK' if item.get('ok') else 'FALHOU'} — {item.get('item')}"
                      + (f": {item['observacao']}" if item.get("observacao") else ""))
    linhas += ["", "## Correções aplicadas automaticamente"]
    for r in roteiro["revisoes"]:
        nome = "Correções do checklist final" if r["capitulo"] == "checklist" else f"Capítulo {r['capitulo']}"
        linhas += ["", f"### {nome}"]
        if not r["correcoes"]:
            linhas.append("- nenhuma")
        for c in r["correcoes"]:
            aviso = " **— NÃO APLICADA, corrigir à mão**" if c.get("nao_aplicada") else ""
            linhas.append(f"- **{c.get('tipo')}**: \"{c.get('trecho_original', '')}\" → \"{c.get('trecho_corrigido', '')}\" "
                          f"({c.get('motivo', '')}){aviso}")
    return "\n".join(linhas)
