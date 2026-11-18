"""Abertura de retenção: 2 versões dos primeiros 30 a 45 segundos (chocante e misteriosa), pelo prompt do dono do
canal em prompts/abertura_retencao.md, e troca da abertura do roteiro pela versão escolhida.

Fluxo: roteiro -> `abertura <projeto>` (gera abertura.md) -> o usuário escolhe -> `abertura <projeto> --usar 1`
-> narrar. A abertura é o primeiro parágrafo do capítulo 1; o CTA de abertura e o resto do roteiro ficam como estão.
"""
import json
import re

from . import config, llm, roteiro as rot

PROMPT = config.RAIZ / "prompts" / "abertura_retencao.md"
# Banco de imagens não tem gráfico, texto nem linha do tempo; a IA de texto às vezes sugere assim mesmo
PALAVRAS_SEM_FOTO = re.compile(r"\b(timeline|graphic|graph|chart|diagram|infographic|text|title|map|logo|logos|"
                               r"countdown|number|numbers|animation|montage|\d{4})\b", re.I)


def _busca_fotografavel(busca, reserva):
    return reserva if not busca or PALAVRAS_SEM_FOTO.search(busca) else busca


def _preencher(r):
    thumb = r.get("thumbnail") or {}
    texto_thumb = thumb.get("cena") or " / ".join(x for x in (thumb.get("linha_topo"), thumb.get("linha_base")) if x)
    roteiro_completo = "\n\n".join(r.get("capitulos_texto", []))
    ficha = r.get("ficha", {})
    tema = f"{ficha.get('nicho_descricao', '')} | promessa: {ficha.get('promessa', '')}"
    return (PROMPT.read_text(encoding="utf-8")
            .replace("[TÍTULO]", r["titulo"])
            .replace("[TEXTO DA THUMB]", f"(sem texto) imagem: {texto_thumb}" if texto_thumb else
                     "(ainda não feita: a thumbnail mostra o assunto do título)")
            .replace("[TEMA]", tema)
            .replace("[IDIOMA]", r.get("idioma", "inglês"))
            .replace("[ROTEIRO OU RESUMO]", roteiro_completo[:24000]))


def gerar(r):
    """Devolve {"versoes": [...], "blocos": [...]} com as duas aberturas, prontas para mostrar e aplicar."""
    prompt = _preencher(r) + f"""

Responda em JSON (as indicações visuais, os loops e os blocos em português; a narração no idioma do vídeo):
{{"versoes": [
  {{"tipo": "chocante/dramática", "frases": [{{"narracao": "...", "visual": "cena curta em português",
    "busca_stock": "2 a 4 palavras em INGLÊS de um OBJETO, LUGAR ou AÇÃO REAL e fotografável que exista em banco de
    imagens (ex.: 'abandoned car dealership', 'octopus underwater'); NUNCA gráfico, texto, número, timeline, mapa
    desenhado ou anos", "busca_wiki": "nome exato em inglês se for algo específico e real (modelo, lugar, animal),
    senão vazio"}}],
    "loops": [{{"loop": "...", "responder_em": "capítulo/bloco"}}]}},
  {{"tipo": "misteriosa/curiosa", "frases": [...], "loops": [...]}}],
 "blocos": [{{"bloco": "nome", "conteudo": "uma linha", "revelacao_principal": false}}]}}
Cada versão: 30 a 45 segundos de fala (cerca de quatrocentos e cinquenta a seiscentos e cinquenta caracteres),
números por extenso, sem emojis."""
    return llm.chat_json(prompt, "Você é especialista em retenção de público no YouTube.", temperatura=0.8)


def para_markdown(r, resultado):
    linhas = [f"# Aberturas de retenção — {r['titulo']}", "",
              "Escolha uma e aplique com `.\\rodar.bat abertura <projeto> --usar 1` (ou 2), ANTES de narrar.", ""]
    for i, v in enumerate(resultado.get("versoes", []), 1):
        texto = " ".join(f["narracao"] for f in v.get("frases", []))
        linhas += [f"## Versão {i}: {v.get('tipo', '')}  ({len(texto)} caracteres, ~{len(texto) / 15:.0f} s)", ""]
        linhas += [f"{f['narracao']} **[{f.get('visual', '')}]**" for f in v.get("frases", [])]
        linhas += ["", "**Loops abertos:**", *[f"- {l.get('loop', '')} → responder em: {l.get('responder_em', '')}"
                                                for l in v.get("loops", [])], ""]
    linhas += ["## Divisão sugerida do restante do vídeo", ""]
    linhas += [f"{n}. **{b.get('bloco', '')}** — {b.get('conteudo', '')}"
               + (" ⭐ revelação principal" if b.get("revelacao_principal") else "")
               for n, b in enumerate(resultado.get("blocos", []), 1)]
    abertura_atual = (r.get("capitulos_texto") or [""])[0].split("\n\n")[0]
    linhas += ["", "## Abertura atual do roteiro (para comparar)", "", abertura_atual]
    return "\n".join(linhas)


def aplicar(r, resultado, numero):
    """Troca o primeiro parágrafo do capítulo 1 pela versão escolhida e refaz as cenas desse trecho.

    Só antes de narrar: depois de narrado, os ids das cenas e os áudios mudariam de lugar.
    """
    if any(c.get("audio") for c in r["cenas"]):
        raise SystemExit("O roteiro já foi narrado: aplique a abertura antes de narrar (ou apague a pasta audio/).")
    versao = resultado["versoes"][numero - 1]
    texto_novo = " ".join(f["narracao"].strip() for f in versao["frases"])
    paragrafos = r["capitulos_texto"][0].split("\n\n")
    antigo = paragrafos[0]
    r["capitulos_texto"][0] = "\n\n".join([texto_novo, *paragrafos[1:]])

    # As cenas do parágrafo antigo saem, comparando o texto exato: uma cena pode juntar o fim da abertura com o
    # começo do parágrafo seguinte (o CTA); nesse caso só a parte da abertura sai e o resto da cena fica
    normal = lambda s: " ".join(s.split())
    restante, removidas, sobra = normal(antigo), 0, None
    for cena in r["cenas"]:
        texto = normal(cena["narracao"])
        if not restante:
            break
        if restante.startswith(texto):
            restante = restante[len(texto):].strip()
        elif texto.startswith(restante):
            sobra = {**cena, "narracao": texto[len(restante):].strip()}
            restante = ""
        else:
            break
        removidas += 1
    if restante:
        raise SystemExit("As cenas não batem com o texto da abertura atual; troque a abertura à mão no roteiro.")
    base = r["cenas"][0] if r["cenas"] else {}
    novas = []
    for f in versao["frases"]:
        for trecho in rot._dividir_em_cenas(f["narracao"]):
            novas.append({"secao": base.get("secao", "Intro"), "capitulo": 1, "narracao": trecho, "visual": "stock",
                          "busca_stock": _busca_fotografavel(f.get("busca_stock", ""), base.get("busca_segura", "")),
                          "busca_segura": base.get("busca_segura", ""),
                          "busca_wiki": f.get("busca_wiki", ""), "prompt_imagem": f.get("visual", "")})
    r["cenas"] = novas + ([sobra] if sobra and sobra["narracao"] else []) + r["cenas"][removidas:]
    for n, cena in enumerate(r["cenas"], 1):
        cena["id"] = n
    r["abertura_retencao"] = {"versao": numero, "tipo": versao.get("tipo"), "loops": versao.get("loops", []),
                              "abertura_anterior": antigo}
    return removidas, len(novas)


def salvar_resultado(pasta, resultado):
    (pasta / "_aberturas.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")


def ler_resultado(pasta):
    arquivo = pasta / "_aberturas.json"
    if not arquivo.exists():
        raise SystemExit("Rode antes: .\\rodar.bat abertura <projeto> (gera as duas versões)")
    return json.loads(arquivo.read_text(encoding="utf-8"))
