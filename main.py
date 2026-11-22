"""Automação de vídeos para canais dark do YouTube.

Uso rápido:
  python main.py nichos --tema "curiosidades"        pesquisa e ranqueia nichos
  python main.py novo "mistérios da história"        cria projeto: referências + modelos de títulos
  python main.py roteiro <projeto> --titulo 3        roteiro (Prompt Mestre) com o título nº 3
  python main.py roteiro <projeto> --referencia "título ou link" --idioma italiano
  python main.py abertura <projeto>                  2 aberturas de retenção; --usar 1|2 aplica (antes de narrar)
  python main.py narrar <projeto>                    gera a narração
  python main.py visuais <projeto>                   baixa vídeos de banco e gera imagens
  python main.py editar <projeto>                    monta o vídeo final
  python main.py tudo --referencia "título ou link"  faz tudo de uma vez
"""
import argparse
import json
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from automacao import (abertura, apresentador, config, edicao, folha_contato, jogos, live, musica, narracao, pesquisa, roteiro,
                       thumb_ia, thumbnail, visuais)

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)


def slug(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:50]


def pasta(nome):
    p = config.PASTA_PROJETOS / nome
    if not p.exists():
        existentes = ", ".join(x.name for x in config.PASTA_PROJETOS.glob("*") if x.is_dir()) or "nenhum"
        raise SystemExit(f'Projeto "{nome}" não existe. Projetos: {existentes}')
    return p


def ler(p, arquivo):
    return json.loads((p / arquivo).read_text(encoding="utf-8"))


def salvar(p, arquivo, dados):
    (p / arquivo).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- comandos ----------

def cmd_nichos(a):
    print("Pesquisando nichos...")
    nichos = pesquisa.pesquisar_nichos(a.tema, a.quantidade)
    destino = config.PASTA_PROJETOS / "_pesquisas"
    destino.mkdir(parents=True, exist_ok=True)
    nome = f"nichos_{datetime.now():%Y%m%d_%H%M}"
    (destino / f"{nome}.md").write_text(pesquisa.relatorio_nichos_md(nichos, a.tema), encoding="utf-8")
    (destino / f"{nome}.json").write_text(json.dumps(nichos, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nRanking:")
    for i, n in enumerate(nichos, 1):
        print(f"  {i}. {n['nome']:<40} nota {n['metricas']['nota']:>6}  busca: \"{n['termo_busca']}\"")
    print(f"\nRelatório completo: {destino / (nome + '.md')}")


def cmd_novo(a):
    p = config.PASTA_PROJETOS / (a.nome or slug(a.nicho))
    p.mkdir(parents=True, exist_ok=True)
    print(f"Projeto: {p.name}\nBuscando referências para \"{a.nicho}\"...")
    refs = pesquisa.referencias(a.nicho)
    salvar(p, "referencias.json", refs)
    (p / "referencias.md").write_text(pesquisa.relatorio_referencias_md(a.nicho, refs), encoding="utf-8")
    for v in refs[:5]:
        print(f"  {v['outlier']:>6}x  {v['titulo']}")

    print("Criando modelos de títulos...")
    titulos = roteiro.gerar_titulos(a.nicho, refs)
    titulos["nicho"] = a.nicho
    salvar(p, "titulos.json", titulos)
    print("\nPadrões encontrados:")
    for pad in titulos["padroes"]:
        print(f"  - {pad}")
    print("\nTítulos sugeridos:")
    for i, t in enumerate(titulos["titulos"], 1):
        print(f"  {i:>2}. {t['titulo']}   [thumb: {t['texto_thumb']}]")
    print(f'\nPróximo passo: python main.py roteiro {p.name} --titulo <número>')
    return p


def cmd_roteiro(a):
    p = config.PASTA_PROJETOS / a.projeto
    referencia = a.referencia
    if not referencia:
        if not (p / "titulos.json").exists():
            raise SystemExit('Informe --referencia "título ou link", ou rode antes: python main.py novo "<nicho>"')
        referencia = ler(p, "titulos.json")["titulos"][a.titulo - 1]["titulo"]
    p.mkdir(parents=True, exist_ok=True)

    entrada = {
        "idioma": a.idioma or config.IDIOMA_ROTEIRO,
        "referencia": referencia,
        "nicho": a.nicho or "",
        "capitulos": a.capitulos or config.CAPITULOS,
        "caracteres": a.caracteres or config.CARACTERES,
        "meta": a.meta or config.META_CANAL,
        "observacoes": a.obs or "",
    }
    minutos = entrada["caracteres"] / roteiro.CARACTERES_POR_MINUTO
    print(f"Roteiro: {referencia}\n  {entrada['idioma']} · {entrada['capitulos']} capítulos · "
          f"{entrada['caracteres']:,} caracteres (≈ {minutos:.0f} min de vídeo)")
    r = roteiro.gerar_roteiro(entrada, p)
    salvar(p, "roteiro.json", r)
    (p / "ficha.md").write_text(roteiro.ficha_md(r["ficha"], entrada), encoding="utf-8")
    (p / "roteiro.md").write_text(roteiro.roteiro_md(r), encoding="utf-8")
    (p / "para_gravar.txt").write_text(roteiro.para_gravar(r), encoding="utf-8")
    (p / "revisao.md").write_text(roteiro.revisao_md(r), encoding="utf-8")
    print(f"\nFicha: {p / 'ficha.md'}\nRoteiro: {p / 'roteiro.md'}\nPara gravar: {p / 'para_gravar.txt'}"
          f"\nRevisão/checklist: {p / 'revisao.md'}")
    print(f"{len(r['cenas'])} cenas. Revise antes de narrar se quiser.")
    return p


def cmd_narrar(a):
    p = pasta(a.projeto)
    r = ler(p, "roteiro.json")
    print("Narrando...")
    salvar(p, "roteiro.json", narracao.narrar_cenas(r, p, a.voz))


def cmd_visuais(a, com_apresentador=False):
    p = pasta(a.projeto)
    r = ler(p, "roteiro.json")
    if r.get("ficha"):
        roteiro.completar_palavras_chave(r)
        salvar(p, "roteiro.json", r)
    # O apresentador usa a placa de vídeo e os visuais usam a internet: rodam ao mesmo tempo
    paralelo = None
    if com_apresentador:
        paralelo = ThreadPoolExecutor(max_workers=1).submit(apresentador.gerar, r, p)
    print("Buscando/gerando visuais...")
    try:
        visuais.gerar_visuais(r, p)
        if paralelo:
            paralelo.result()
    finally:
        salvar(p, "roteiro.json", r)  # guarda o progresso mesmo se parar no meio
    print(f"Folha para revisar as cenas: {folha_contato.gerar(r, p)}")


def cmd_editar(a):
    p = pasta(a.projeto)
    r = ler(p, "roteiro.json")
    if any("duracao" not in c for c in r["cenas"]):
        raise SystemExit("Rode antes: python main.py narrar " + p.name)
    print("Editando vídeo...")
    video = edicao.editar(r, p)
    caps = edicao.capitulos(r)
    rotulo = {"en": "Chapters", "it": "Capitoli", "de": "Kapitel", "fr": "Chapitres"}.get(r.get("idioma_codigo"), "Capítulos")
    texto = [r["titulo"], "", r.get("descricao_youtube", ""), "", f"{rotulo}:", *caps, ""]
    # Fotos do Wikimedia Commons exigem crédito (autor, licença e link) na descrição
    creditos = list({cr["arquivo"]: cr for c in r["cenas"] for cr in (c.get("credito"), c.get("credito_extra"))
                     if cr}.values())
    if creditos:
        texto += ["Image and footage credits:",
                  *[f"- {c['arquivo']} by {c['autor']}, {c['licenca']}, {c['url']}" for c in creditos], ""]
    # Fontes consultadas (artigos e sites de referência): pedido do dono em 2026-11-22, em todo vídeo
    if r.get("fontes"):
        rotulo_f = {"es": "Fuentes", "fr": "Sources", "en": "Sources", "it": "Fonti"}.get(r.get("idioma_codigo"), "Fontes")
        texto += [f"{rotulo_f}:", *[f"- {f}" for f in r["fontes"]], ""]
    if r.get("musica_creditos"):
        texto += ["Music:", *r["musica_creditos"], ""]
    texto.append("Tags: " + ", ".join(r.get("tags", [])))
    (p / "descricao_youtube.txt").write_text("\n".join(texto), encoding="utf-8")
    print(f"\nPronto! Vídeo: {video}\nDescrição e capítulos: {p / 'descricao_youtube.txt'}")


def cmd_apresentador(a):
    p = pasta(a.projeto)
    r = ler(p, "roteiro.json")
    if any("duracao" not in c for c in r["cenas"]):
        raise SystemExit("Rode antes: python main.py narrar " + p.name)
    print("Apresentador de IA...")
    salvar(p, "roteiro.json", apresentador.gerar(r, p))


def cmd_thumb(a):
    p = pasta(a.projeto)
    r = ler(p, "roteiro.json")
    estilo = getattr(a, "estilo", "cinema")
    pais = getattr(a, "pais", None)
    pais = None if pais is None else pais.strip()
    if estilo == "texto":
        # Estilo antigo: foto de banco + texto grande
        print("Criando thumbnails (foto + texto)...")
        gerados = thumbnail.gerar_thumbnails(r, p)
        print(f"Texto: {r['thumbnail']['linha_topo']} / {r['thumbnail']['linha_base']}")
    elif estilo == "obra":
        # Padrão anterior (até 2026-10-12): foto realista por IA + bandeira, sem texto
        print("Criando thumbnails (foto IA + bandeira, sem texto)...")
        gerados = thumb_ia.gerar(r, p, pais=pais, cena=getattr(a, "cena", None))
        t = r["thumbnail"]
        print(f"Cena: {t['cena']}\nBandeira: {t['pais'] or '(nenhuma)'}")
    elif estilo == "cinema":
        # PADRÃO desde 2026-10-12 (2ª mudança do dia): cena cinematográfica inteira + 2 linhas grandes de texto
        print("Criando thumbnails (cena cinematográfica IA + texto grande)...")
        gerados = thumb_ia.gerar_cinema(r, p, pais=pais or "", cena=getattr(a, "cena", None))
        t = r["thumbnail"]
        print(f"Cena: {t['cena']}\nAssunto à {t['lado']}; bandeira: {t['pais'] or '(nenhuma)'}")
        for n, (l1, l2, cor) in enumerate(t["textos"], 1):
            print(f"Texto {n}: {l1} / {l2} ({cor})")
        print("CONFIRA cada thumbnail: a IA às vezes desenha logo de marca real (apagar com thumb_ia.borrar_logo)")
    else:
        # Estilo destaque (padrão por algumas horas em 2026-10-12; o usuário achou o âncora "muito ruim")
        print("Criando thumbnails (âncora + faixas de texto + cena IA + bandeira)...")
        gerados = thumb_ia.gerar_destaque(r, p, pais=pais, cena=getattr(a, "cena", None))
        t = r["thumbnail"]
        print(f"Cena: {t['cena']}\nFundo do âncora: {t['fundo_ancora']}\nBandeira: {t['pais'] or '(nenhuma)'}")
        for n, (topo, base) in enumerate(t["textos"], 1):
            print(f"Texto {n}: {topo} / {base}")
        print("CONFIRA cada thumbnail: a IA às vezes desenha logo de marca real (apagar com thumb_ia.borrar_logo)")
    salvar(p, "roteiro.json", r)
    print(f"{len(gerados)} thumbnail(s) em {p}")


def cmd_abertura(a):
    """Abertura de retenção (prompts/abertura_retencao.md): gera 2 versões ou aplica a escolhida, antes de narrar."""
    p = pasta(a.projeto)
    r = ler(p, "roteiro.json")
    if a.usar:
        resultado = abertura.ler_resultado(p)
        saiu, entrou = abertura.aplicar(r, resultado, a.usar)
        salvar(p, "roteiro.json", r)
        (p / "roteiro.md").write_text(roteiro.roteiro_md(r), encoding="utf-8")
        (p / "para_gravar.txt").write_text(roteiro.para_gravar(r), encoding="utf-8")
        print(f"Abertura versão {a.usar} aplicada: {saiu} cena(s) antigas trocadas por {entrou} nova(s).")
        # Em roteiro escrito à mão a abertura antiga pode ocupar mais de um parágrafo: conferir repetição
        seguinte = r["capitulos_texto"][0].split("\n\n")[1:2]
        if seguinte:
            print(f"\nConfira se o parágrafo seguinte não repete a abertura nova (se repetir, corte no roteiro):\n"
                  f"  {seguinte[0][:400]}")
        print(f"Próximo passo: .\\rodar.bat narrar {p.name}")
        return
    print("Gerando 2 aberturas de retenção (chocante e misteriosa)...")
    resultado = abertura.gerar(r)
    abertura.salvar_resultado(p, resultado)
    (p / "abertura.md").write_text(abertura.para_markdown(r, resultado), encoding="utf-8")
    for i, v in enumerate(resultado.get("versoes", []), 1):
        print(f"\n--- Versão {i}: {v.get('tipo', '')}\n" + " ".join(f["narracao"] for f in v.get("frases", [])))
    print(f"\nDetalhes (visuais, loops e blocos): {p / 'abertura.md'}")
    print(f"Para usar uma: .\\rodar.bat abertura {p.name} --usar 1   (ou 2)")


def cmd_tudo(a):
    if a.referencia:
        a.projeto = a.nome or slug(a.referencia)[:40]
    elif not a.nicho:
        raise SystemExit('Informe um nicho ou --referencia "título ou link"')
    else:
        a.projeto = cmd_novo(a).name
    cmd_roteiro(a)
    cmd_narrar(a)
    cmd_visuais(a, com_apresentador=config.APRESENTADOR)
    cmd_editar(a)
    cmd_thumb(a)


def cmd_voz(a):
    """Narra um texto com a voz do canal (no lugar do Clipchamp)."""
    from pathlib import Path
    perfil = config.VOZES_CANAIS[a.canal]
    origem = Path(a.texto)
    if not origem.exists():
        raise SystemExit(f"Texto não encontrado: {origem}")
    destino = Path(a.saida) if a.saida else origem.with_name("narracao_usuario.mp3")
    narracao.narrar_texto(origem.read_text(encoding="utf-8-sig"), destino, a.voz or perfil["voz"],
                          a.velocidade or perfil["velocidade"], a.tom or perfil.get("tom", "+0Hz"),
                          a.eq or perfil.get("eq"))


def cmd_musica(a):
    musica.baixar(a.climas or None) if a.acao == "baixar" else musica.listar()


def cmd_vozes(a):
    for v in narracao.listar_vozes():
        print(f"  {v['ShortName']:<28} {v['Gender']}")


def _opcoes_roteiro(s):
    """Campos do BLOCO DE ENTRADA do Prompt Mestre."""
    s.add_argument("--referencia", help="título OU link de vídeo/artigo de referência")
    s.add_argument("--titulo", type=int, default=1, help="sem --referencia: nº do título sugerido pelo comando novo")
    s.add_argument("--idioma", help=f"ex.: italiano, espanhol, inglês (padrão: {config.IDIOMA_ROTEIRO})")
    s.add_argument("--nicho", help="romance histórico, drama contemporâneo, curiosidades, documentário histórico...")
    s.add_argument("--capitulos", type=int, help=f"padrão: {config.CAPITULOS}")
    s.add_argument("--caracteres", type=int, help=f"padrão: {config.CARACTERES} (≈ 735 caracteres por minuto)")
    s.add_argument("--meta", help='meta do canal para o CTA, ex.: "canal novo, meta de 500 inscritos"')
    s.add_argument("--obs", help="observações extras: público, tom, restrições")


def main():
    ap = argparse.ArgumentParser(description="Automação de vídeos para canais dark do YouTube")
    sub = ap.add_subparsers(dest="comando", required=True)

    s = sub.add_parser("nichos", help="pesquisa e ranqueia nichos")
    s.add_argument("--tema", help="área geral (ex.: história, finanças, mistérios)")
    s.add_argument("--quantidade", type=int, default=8)
    s.set_defaults(func=cmd_nichos)

    s = sub.add_parser("novo", help="cria projeto com referências e títulos")
    s.add_argument("nicho", help='termo de busca do nicho, ex.: "mistérios da história"')
    s.add_argument("--nome", help="nome da pasta do projeto")
    s.set_defaults(func=cmd_novo)

    for nome, func, ajuda in [("roteiro", cmd_roteiro, "escreve o roteiro"),
                              ("narrar", cmd_narrar, "gera a narração"),
                              ("visuais", cmd_visuais, "baixa/gera os visuais"),
                              ("editar", cmd_editar, "monta o vídeo final"),
                              ("thumb", cmd_thumb, "cria as thumbnails"),
                              ("abertura", cmd_abertura, "2 aberturas de retenção (antes de narrar); --usar 1|2"),
                              ("apresentador", cmd_apresentador, "rosto de IA falando nas cenas de interação")]:
        s = sub.add_parser(nome, help=ajuda)
        s.add_argument("projeto")
        s.set_defaults(func=func)
        if nome == "roteiro":
            _opcoes_roteiro(s)
        if nome == "narrar":
            s.add_argument("--voz", help="ex.: pt-BR-FranciscaNeural (veja: python main.py vozes)")
        if nome == "abertura":
            s.add_argument("--usar", type=int, choices=[1, 2], help="aplica a versão escolhida ao roteiro")
        if nome == "thumb":
            s.add_argument("--pais", help='país da bandeira, em inglês ("China", "Germany"); "" = sem bandeira. Sem a opção: '
                                          "no estilo cinema (padrão) sai sem bandeira; nos estilos destaque e obra, "
                                          "o país é descoberto pelo título")
            s.add_argument("--cena", help="descrição da cena em inglês (sem a opção, é criada a partir do título)")
            s.add_argument("--estilo", choices=["cinema", "destaque", "obra", "texto"], default="cinema",
                           help="cinema = cena cinematográfica IA + 2 linhas de texto grande (padrão); "
                                "destaque = âncora + faixas de texto + cena IA + bandeira; "
                                "obra = foto IA + bandeira, sem texto; texto = foto de banco + texto grande")

    s = sub.add_parser("tudo", help="faz todas as etapas (a partir de um nicho ou de uma --referencia)")
    s.add_argument("nicho", nargs="?", default="", help="nicho para pesquisar (dispensável com --referencia)")
    s.add_argument("--nome", help="nome da pasta do projeto")
    s.add_argument("--voz")
    _opcoes_roteiro(s)
    s.set_defaults(func=cmd_tudo)

    s = sub.add_parser("jogo", help="canal de jogos: preparar | gravar | montar | curtos | thumb | mascote")
    jogos.opcoes(s)

    s = sub.add_parser("live", help="cortes de live: info | baixar | momentos (Twitch e Kick; YouTube no Windows)")
    live.opcoes(s)

    s = sub.add_parser("voz", help="narra um texto com a voz do canal (no lugar do Clipchamp)")
    s.add_argument("canal", choices=sorted(config.VOZES_CANAIS))
    s.add_argument("texto", help="arquivo .txt (parágrafos separados por linha em branco)")
    s.add_argument("--saida", help="arquivo de áudio (padrão: narracao_usuario.mp3 ao lado do texto)")
    s.add_argument("--voz", help="outra voz do Edge, ex.: en-US-AndrewMultilingualNeural")
    s.add_argument("--velocidade", help='ex.: "+8%%"')
    s.add_argument("--tom", help='ex.: "-2Hz" (mais grave)')
    s.add_argument("--eq", choices=sorted(narracao.EQ_VOZ), help="equalização do timbre")
    s.set_defaults(func=cmd_voz)

    s = sub.add_parser("musica", help="biblioteca de música de fundo por clima (musicas/<clima>/)")
    s.add_argument("acao", choices=["baixar", "listar"])
    s.add_argument("climas", nargs="*", help=f"só estes climas: {', '.join(musica.CATALOGO)}")
    s.set_defaults(func=cmd_musica)

    s = sub.add_parser("vozes", help="lista vozes em português")
    s.set_defaults(func=cmd_vozes)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
