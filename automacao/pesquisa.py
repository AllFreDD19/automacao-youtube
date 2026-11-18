"""Etapas 1 e 2: pesquisa de nichos e de vídeos de referência pela YouTube Data API."""
import math
import re
import statistics
from datetime import datetime, timedelta, timezone

import requests

from . import config, llm

API = "https://www.googleapis.com/youtube/v3"


def _get(endpoint, **params):
    if not config.YOUTUBE_API_KEY:
        raise SystemExit("Defina YOUTUBE_API_KEY no arquivo .env (Google Cloud > YouTube Data API v3)")
    params["key"] = config.YOUTUBE_API_KEY
    r = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube API {endpoint}: {r.status_code} {r.text[:300]}")
    return r.json()


def _duracao_seg(iso):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def buscar_videos(termo, quantidade=25, meses=6):
    """Busca vídeos médios/longos recentes e calcula métricas de desempenho."""
    depois = (datetime.now(timezone.utc) - timedelta(days=30 * meses)).strftime("%Y-%m-%dT%H:%M:%SZ")
    busca = _get(
        "search", part="snippet", q=termo, type="video", order="viewCount",
        maxResults=min(quantidade, 50), publishedAfter=depois,
        regionCode=config.REGIAO, relevanceLanguage=config.IDIOMA, videoDuration="medium",
    )
    ids = [i["id"]["videoId"] for i in busca.get("items", [])]
    if not ids:
        return []

    videos = _get("videos", part="snippet,statistics,contentDetails", id=",".join(ids))["items"]
    canais_ids = list({v["snippet"]["channelId"] for v in videos})
    canais = {
        c["id"]: c for c in _get("channels", part="snippet,statistics", id=",".join(canais_ids))["items"]
    }

    agora = datetime.now(timezone.utc)
    resultado = []
    for v in videos:
        st = v.get("statistics", {})
        canal = canais.get(v["snippet"]["channelId"], {})
        cst = canal.get("statistics", {})
        views = int(st.get("viewCount", 0))
        inscritos = int(cst.get("subscriberCount", 0) or 0)
        total_videos = max(int(cst.get("videoCount", 1) or 1), 1)
        media_canal = int(cst.get("viewCount", 0) or 0) / total_videos
        publicado = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
        dias = max((agora - publicado).days, 1)
        resultado.append({
            "id": v["id"],
            "url": f"https://www.youtube.com/watch?v={v['id']}",
            "titulo": v["snippet"]["title"],
            "canal": v["snippet"]["channelTitle"],
            "canal_id": v["snippet"]["channelId"],
            "publicado": v["snippet"]["publishedAt"][:10],
            "duracao_min": round(_duracao_seg(v["contentDetails"].get("duration")) / 60, 1),
            "views": views,
            "likes": int(st.get("likes", st.get("likeCount", 0)) or 0),
            "comentarios": int(st.get("commentCount", 0) or 0),
            "inscritos_canal": inscritos,
            "videos_canal": total_videos,
            "views_por_dia": round(views / dias),
            # Quantas vezes o vídeo superou a média do próprio canal: indica tema/título forte
            "outlier": round(views / max(media_canal, 1), 2),
            "views_por_inscrito": round(views / max(inscritos, 1), 2),
            "thumbnail": v["snippet"]["thumbnails"].get("high", {}).get("url", ""),
        })
    return resultado


def pontuar_nicho(videos):
    """Nota de oportunidade: demanda (views) x espaço para canais pequenos x força de outliers."""
    if not videos:
        return {"nota": 0}
    views = [v["views"] for v in videos]
    pequenos = [v for v in videos if v["inscritos_canal"] < 100_000]
    pequenos_bons = [v for v in pequenos if v["views"] >= 50_000]
    mediana_views = statistics.median(views)
    mediana_outlier = statistics.median(v["outlier"] for v in videos)
    frac_pequenos = len(pequenos_bons) / len(videos)
    nota = math.log10(max(mediana_views, 10)) * (1 + 2 * frac_pequenos) * math.sqrt(min(mediana_outlier, 20) + 1)
    return {
        "nota": round(nota, 2),
        "mediana_views": int(mediana_views),
        "mediana_outlier": round(mediana_outlier, 2),
        "canais_pequenos_com_sucesso": len(pequenos_bons),
        "canais_distintos": len({v["canal_id"] for v in videos}),
        "videos_analisados": len(videos),
    }


def sugerir_nichos(tema=None, quantidade=8):
    foco = f'dentro do tema "{tema}"' if tema else "em temas variados"
    prompt = f"""Sugira {quantidade} nichos para canais dark (sem rosto, narração + imagens/vídeos de banco)
no YouTube em português do Brasil, {foco}. Ignore nichos de música.
Priorize nichos com bom CPM, conteúdo evergreen e vídeos longos de 8 a 15 minutos.
Formato: {{"nichos": [{{"nome": "...", "termo_busca": "termo curto como alguém digitaria no YouTube",
"por_que": "...", "cpm_estimado": "baixo|medio|alto", "exemplos_de_temas": ["...", "...", "..."]}}]}}"""
    return llm.chat_json(prompt, "Você é um estrategista de canais do YouTube.")["nichos"]


def pesquisar_nichos(tema=None, quantidade=8):
    nichos = sugerir_nichos(tema, quantidade)
    for n in nichos:
        print(f"  analisando: {n['nome']} ({n['termo_busca']})")
        try:
            videos = buscar_videos(n["termo_busca"], quantidade=25)
        except RuntimeError as e:
            print(f"    erro: {e}")
            videos = []
        n["metricas"] = pontuar_nicho(videos)
        n["top_videos"] = sorted(videos, key=lambda v: v["outlier"], reverse=True)[:5]
    nichos.sort(key=lambda n: n["metricas"]["nota"], reverse=True)
    return nichos


def referencias(termo, quantidade=50, top=15):
    videos = buscar_videos(termo, quantidade=quantidade, meses=12)
    # Outliers primeiro: vídeos que bombaram acima do normal do canal são os melhores modelos
    videos.sort(key=lambda v: (v["outlier"], v["views_por_dia"]), reverse=True)
    return videos[:top]


def relatorio_nichos_md(nichos, tema=None):
    linhas = [f"# Pesquisa de nichos{f' — {tema}' if tema else ''}", "",
              f"Gerado em {datetime.now():%d/%m/%Y %H:%M}", "",
              "| # | Nicho | Nota | Mediana views | Outlier mediano | Canais pequenos c/ sucesso | CPM |",
              "|---|---|---|---|---|---|---|"]
    for i, n in enumerate(nichos, 1):
        m = n["metricas"]
        linhas.append(f"| {i} | {n['nome']} | {m.get('nota', 0)} | {m.get('mediana_views', 0):,} | "
                      f"{m.get('mediana_outlier', 0)} | {m.get('canais_pequenos_com_sucesso', 0)} | {n.get('cpm_estimado', '')} |")
    for i, n in enumerate(nichos, 1):
        linhas += ["", f"## {i}. {n['nome']}", "", f"**Busca:** `{n['termo_busca']}`", "", n.get("por_que", ""), "",
                   "**Ideias de temas:** " + "; ".join(n.get("exemplos_de_temas", [])), "", "**Vídeos de destaque:**"]
        for v in n.get("top_videos", []):
            linhas.append(f"- [{v['titulo']}]({v['url']}) — {v['canal']} · {v['views']:,} views · "
                          f"{v['inscritos_canal']:,} inscritos · outlier {v['outlier']}x")
    return "\n".join(linhas)


def relatorio_referencias_md(termo, videos):
    linhas = [f"# Referências — {termo}", "",
              "| Título | Canal | Views | Inscritos | Outlier | Views/dia | Duração |",
              "|---|---|---|---|---|---|---|"]
    for v in videos:
        titulo = v["titulo"].replace("|", "/")
        linhas.append(f"| [{titulo}]({v['url']}) | {v['canal']} | {v['views']:,} | {v['inscritos_canal']:,} | "
                      f"{v['outlier']}x | {v['views_por_dia']:,} | {v['duracao_min']} min |")
    return "\n".join(linhas)
