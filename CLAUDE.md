# Automação de vídeos para canais dark (YouTube)

Ferramenta em Python que produz vídeos completos: roteiro → narração → visuais → edição → thumbnail.
Uso e comandos: ver `LEIA-ME.md`. Rodar com `.\rodar.bat <comando>`; chaves em `.env` (o dono preenche, nunca pedir no chat).

## Decisões do dono (valem para todos os canais)
- Conversa no chat: sempre em português (Brasil), inclusive explicações técnicas e resumos.
- Meta: expandir para mais canais. Cada canal novo ganha uma seção em "Canais" (copiar o modelo no fim da seção).
- Meta de cada canal: 1.000 inscritos. Ritmo: 1 a 2 vídeos por dia em cada canal.
- Roteiros seguem o Prompt Mestre em `prompts/roteiro_mestre.md` (não alterar sem pedido): abertura de retenção nos
  primeiros 30-45 s (1a frase confirma título e thumb, 2+ loops de curiosidade, revelação só no último terço) e
  regra dos 3 CTAs (depois da abertura, no meio do vídeo e no final).
  Quando a seção do canal (em "Canais") disser outra coisa (formato, capítulos, CTAs), vale a seção do canal.
- Custo zero: só serviços gratuitos (Nemotron e FLUX com créditos NVIDIA, Clipchamp, Edge TTS, Kokoro e Piper locais,
  Pixabay, Pexels, Wikimedia, NASA, Openverse, Unsplash, FFmpeg, CLIP e Whisper locais).

## Tamanho dos roteiros
- Os vídeos têm 15 ou 30 minutos. Perguntar qual, se o pedido não disser.
- Velocidade real medida nas narrações dos canais (2026-11-19), que a voz Remy reproduz:
  - Impérios Caídos: ~946 caracteres/min. 15 min = ~14.000 caracteres; 30 min = ~28.000.
  - Le Disciple: ~1.120 caracteres/min. 15 min = ~17.000 caracteres; 30 min = ~33.500.
  - Outros canais/vozes: ~735 caracteres/min (conta antiga) até medir a voz deles.
- Ao preencher o BLOCO DE ENTRADA do Prompt Mestre, usar esse total no campo de caracteres; nunca o padrão de 40.000.

## Canais
Antes de escrever roteiro, título, thumbnail ou descrição, identificar de qual canal é o pedido e seguir a seção dele.
Se o canal não for dito, perguntar. Campos "[preencher]": perguntar ao dono, nunca inventar.

### Le Disciple du Savoir (@LeDiscipleduSavoir, ID UCe06mEV939UUr0k6-vYs7Qg)
- Tema: filosofia e sabedoria antiga (estoicismo, desenvolvimento pessoal), narração personificada (sábio barbudo, ~50 anos).
- Idioma: francês. Voz: William Multilingual (`en-AU-WilliamMultilingualNeural`, falando francês) +11%, tom -2Hz,
  eq leve, pela ferramenta: `rodar voz le-disciple <texto.txt>` (escolhida pelo dono em 2026-11-20, opção 4 da
  comparação com o áudio original do canal; antes era Remy +8%, que variava demais o tom). O original: F0 108 Hz,
  variação 16 Hz, centroide 1.117 Hz; a William com esses ajustes deu 106 Hz, 22 Hz e 1.109 Hz.
- Formato: roteiro em narração contínua, sem capítulos, listas ou títulos internos; 1 a 3 CTAs fluidas no meio do texto.
- Abertura fixa (jingle) em todo vídeo. CTA padrão: "Rejoignez la communauté des personnes qui pensent différemment".
- Entregáveis por vídeo: roteiro, título principal + 3 alternativas, miniatura, 25 prompts de imagens em ordem cronológica
  (alternando o Disciple da biblioteca e imagens conceituais), descrição com 6 hashtags, anúncio para a comunidade.
- Temas: nunca repetir os já usados (lista de temas no histórico do canal e em `temas_usados.md`).
- Pauta (pedido do dono em 2026-11-22): 2 vídeos por dia. Um de filosofia, sociologia, cultura ou meditação
  (guiada) e um de releitura/análise de um livro.
- Tamanho: vídeos de 15 ou 30 minutos (ver "Tamanho dos roteiros"). Meta: 1.000 inscritos; 1 a 2 vídeos por dia.

### Impérios Caídos (@imperioscaidosofficial, ID UCZpm9Q4UMAOhZQ0erHwrWug)
- Tema: ascensão e queda de impérios e civilizações, guerras, mistérios da história, documentários cinematográficos
  (nicho D do Prompt Mestre: documentário narrativo real, não inventar fatos, datas, números nem citações).
- Idioma: espanhol. Voz: Remy Multilingual (-9%) pela ferramenta: `rodar voz imperios <texto.txt>`
  (substitui o Clipchamp desde 2026-11-19; aprovada pelo dono). Música de fundo baixa no clima "tenso" (pedido do
  dono em 2026-11-20; até então era sem música); o vídeo da URSS ficou como está.
- Formato: Prompt Mestre completo (4 capítulos, 3 CTAs).
- Tamanho: vídeos de 15 ou 30 minutos (ver "Tamanho dos roteiros"). Meta: 1.000 inscritos; 1 a 2 vídeos por dia.
- Pauta (pedido do dono em 2026-11-22): 2 vídeos por dia. Um de tema antigo/atemporal (história, mito ou lenda
  antiga, o nosso planeta, um herói, o universo) e um de tema ATUAL (ex.: guerra na Ucrânia, um grande ataque
  hacker). O atual não precisa ser do dia: começa explicando por que aquilo acontece, o que ocorreu até agora e por
  que continua; pode passar de 15 min se precisar. Fatos recentes: pesquisar na web na hora (WebSearch) e citar a
  data ("hasta noviembre de 2026"); nunca confiar só na memória do modelo, que tem data de corte.
- Temas já feitos: `temas_usados.md` (não repetir os dessa lista; atualizar a cada vídeo).
- O dono lê o roteiro antes da edição quando quiser: mandar o roteiro assim que ficar pronto.
- Toda descrição leva a seção "Fuentes" (pedido do dono em 2026-11-22): SÓ o título do artigo/obra e quem publica
  (ex.: "Tercera guerra púnica (Wikipedia)", "Al Jazeera / Reuters, «...» (17/11/2026)"), SEM link. Fica em
  `projetos/<pasta>/fontes.json` (copiar para o campo "fontes" do roteiro.json antes do `editar`). Antes, conferir
  que a fonte existe (com o User-Agent da ferramenta; nunca fingir ser navegador). Obras antigas pelo nome.
- Thumbs épicas: 7 estilos de fonte/cor em `ESTILOS_EPICOS` (imperial, fogo, gelo, sangue, bronze, manchete,
  classico); cada opção de um vídeo com um estilo diferente, escolhido pelo tema (pedido do dono: estavam parecidas).

### Fora da Missão (nome sugerido; @handle e ID: [preencher]; ainda não criado)
- Tema: gameplay do dono em vídeos de tutorial ou demonstração (explicar missão, mostrar o que dá para fazer ou o que existe no jogo).
  Jogo principal: GTA VI (lançamento 19/11/2026); depois, outros jogos. Idioma: português (Brasil). Público geral.
- Tipos de vídeo: missão (como passar, passo a passo), easter eggs e segredos, react (reação do narrador à
  própria gameplay e às descobertas). React a trailer ou vídeo de terceiros: só com pedido do dono, trechos curtos e
  comentário dominando (risco de Content ID); nunca reagir a vídeo de outro canal do YouTube.
  O nome não leva "GTA" (marca da Rockstar/Take-Two) para o canal poder mudar de jogo sem trocar de nome.
- Formato: o dono entrega a gameplay (vídeo) na pasta do projeto. Dois tipos: (1) narrado, com roteiro que descreve o que
  acontece na imagem; (2) curto, só com música de fundo e texto na tela, sem narração.
- Como "ver" o vídeo: nunca assumir o que acontece sem olhar. Extrair quadros com FFmpeg (1 a cada 2-3 s, mais denso nas trocas
  de cena), descrever cada trecho a partir dos quadros e só então escrever o roteiro; transcrever a fala do jogo com
  `automacao/transcrever.py`. Nomes de itens, missões e locais: conferir na tela ou perguntar ao dono, nunca inventar.
- Edição: cortes por trecho com FFmpeg, legenda palavra a palavra (`automacao/historia.py`) quando houver narração; música de
  fundo baixa (-18 dB) com licença livre, da pasta `musicas/` que o dono preenche (guardar o crédito para a descrição).
- Direitos: gameplay do próprio dono; checar a política de conteúdo do estúdio do jogo antes de monetizar.
- Entregáveis por vídeo: roteiro (se narrado), título principal + 3 alternativas, miniatura (quadro do jogo), descrição com
  créditos da música.
- Tamanho: vídeos longos (horizontais, 1920x1080) de 10 a 15 minutos; roteiro narrado ~7.300 a 11.000 caracteres.
- Curtos: de 30 a 60 s, verticais (1080x1920), tirados da mesma gameplay (o melhor momento, texto grande na tela).
  Servem para YouTube Shorts, Instagram Reels e TikTok sem mudar o arquivo. Música: só faixas cuja licença
  permita usar fora do YouTube (a Biblioteca de Áudio do YouTube pode não valer no Instagram/TikTok); nos dois,
  dá para usar a música do próprio app em vez da nossa.
- Meta: 1.000 inscritos; 1 a 2 vídeos longos por dia, mais os curtos à parte.
- Identidade: mascote ORIGINAL (arquétipo de líder durão, sarcástico e calmo; opções em `canal_jogos/`, comando
  `jogo mascote`). Nunca usar personagem de outra obra (ex.: Yami de Black Clover) nem imitar a voz de dublador ou
  pessoa real: voz grave genérica do Clipchamp.
- Cortes de live (`automacao/live.py`, `rodar live info|baixar|momentos`): só lives do dono. Twitch e Kick
  funcionam na nuvem (yt-dlp; baixa só o trecho com `--de/--ate`; live no ar: `--minutos N`); YouTube só no
  Windows (bot check aqui). `momentos` mede o áudio, ranqueia os trechos mais animados, transcreve só eles e
  gera `momentos.md` + quadros; depois os escolhidos vão para `roteiro_jogo.json` e `jogo curtos`/`montar`.
- Ferramenta: `automacao/jogos.py` (`.\rodar.bat jogo preparar|gravar|montar|curtos|thumb <projeto>`, ver LEIA-ME).
  Para escrever o `roteiro_jogo.json`: rodar `preparar`, ABRIR as imagens de `folhas/` e ler `mapa.md`; cada trecho
  usa só o que aparece nos quadros daquele intervalo. Abertura de retenção e 3 CTAs curtos (regra geral) também valem.

### Modelo para canal novo
```
### <Nome> (<@handle>, ID <UC...>)
- Tema:
- Idioma / Voz:
- Formato dos roteiros (capítulos, CTAs):
- Entregáveis por vídeo:
- Tamanho dos roteiros / Meta de inscritos:
```

## Como a ferramenta funciona (técnico)
- Roda em dois lugares: no Windows do dono (`.\rodar.bat`, placa RTX 3050, chaves no `.env`) e no Claude Code na
  nuvem (Linux, sem placa, `./rodar.sh`; repositório github.com/AllFreDD19/automacao-youtube). Código no GitHub;
  vídeos, áudios e projetos ficam fora dele (`.gitignore`). Na nuvem:
  - Sessão nova: rodar `bash instalar_nuvem.sh` antes de tudo (ffmpeg, fontes e pacotes Python).
  - Sem `.env`: a chave da NVIDIA é uma credencial do ambiente (o proxy injeta), mas o FLUX responde 401
    "Unauthorized access" aqui (testado de novo em 2026-11-20 com a chave atualizada) enquanto o `testar_chaves.py`
    dá OK no Windows com a mesma conta: FLUX só no Windows; não insistir nem pedir a chave de novo. Imagens de IA aqui: Pollinations (`image.pollinations.ai`, grátis, sem chave;
    põe marca d'água no canto inferior direito: recortar). Pixabay e YouTube API usam a chave na URL: só no Windows.
  - Roteiros: escritos pelo Claude direto (Nemotron fica para o Windows).
  - Whisper no processador (`automacao/transcrever.py` escolhe sozinho), ~1,5x o tempo do áudio.
  - Fontes: Anton (`fontes/`, parecida com a Impact) e Liberation Sans no lugar da Arial; `config.py` escolhe.
  - Edge TTS funciona pelo proxy (`config.PROXY`).
  - Arquivos do dono (gameplay, narração do Clipchamp) chegam pelo chat em `/root/.claude/uploads/...`: copiar para
    `projetos/<nome>/gameplay/` e `projetos/<nome>/narracao_usuario.mp3`. Entregar com SendUserFile.
- Narração: Kokoro local (inglês, voz am_michael); Piper local para espanhol (es_ES-davefx-medium), alemão
  (de_DE-thorsten_emotional-medium#neutral) e francês (fr_FR-tom-medium), modelos em `vozes_piper/` (baixados pelo
  instalar.ps1); Edge TTS para os demais idiomas. Canais: `rodar voz <canal> <texto.txt>` gera o áudio inteiro
  com a voz de `config.VOZES_CANAIS` (parágrafos = blocos com pausa de 0,45 s), saída `narracao_usuario.mp3`.
  edge-tts 7.3.1 (a 7.2.8 recebe 403). Nomes próprios lidos errado: campo "pronuncia_piper" do roteiro.json.
- Visuais: Wikimedia (foto exata, campo `busca_wiki`), Pixabay, Pexels, NASA, Openverse e Unsplash concorrem; o CLIP
  (`automacao/relevancia.py`) dá nota a cada candidato e escolhe o melhor. Créditos vão sozinhos para a descrição
  (não apagar ao publicar: a licença exige).
  - Wikimedia: só responde com contato no User-Agent (`config.USER_AGENT`, link do repositório, aprovado pelo dono);
    sem contato a nuvem levava 429 o tempo todo. No máximo 3 pedidos ao mesmo tempo; respeitar o Retry-After.
    Nunca trocar de User-Agent para fugir do limite.
  - Flickr pelo Openverse (`source=flickr`) achou boas fotos históricas quando o Wikimedia faltou.
  - Vídeos de banco: Pexels (chave pelo cabeçalho; na nuvem é credencial do ambiente, rodar com
    `PEXELS_API_KEY=proxy-injected`; em 2026-11-20 ainda dava "Invalid API key": o valor salvo precisa ser só a
    chave, sem "Bearer"). Vídeos do Commons (cinejornais, arquivo; busca automática nas cenas "stock"): só as
    versões convertidas (720p etc.), o original dá 429; na nuvem o upload.wikimedia.org ainda pede ~2 min entre
    arquivos de vídeo (lento, mas a ferramenta espera). Filmes históricos em domínio público: Internet Archive,
    só das coleções `universal_newsreels` e `prelinger` (nas outras a licença declarada costuma estar errada).
  - ffmpeg lendo endereço da internet na nuvem: passar `-http_proxy config.PROXY` (ele não lê HTTPS_PROXY).
- Estilo dos documentários (aprovado em 2026-11-20, referência: canal "O Mundo e Tudo ao Redor"), Impérios e Le
  Disciple: misturado. Fotos e vídeos reais na maior parte; cenas animadas (`automacao/animacao.py`: ilustração
  plana por IA + câmera lenta + partículas) nas cenas abstratas, de ideia, metáfora ou sem foto boa. Faixas pretas de
  cinema no vídeo todo (legenda dentro da faixa de baixo) e texto no canto inferior esquerdo nos momentos-chave.
  No roteiro.json: `"canal": "imperios"|"le-disciple"`, cena animada `"visual": "animacao"` + `"prompt_animacao"`
  (inglês) + `"efeito"` (neve, estrelas, poeira, brasas, chuva, nenhum), e `"texto_tela": ["linha pequena",
  "PALAVRA-CHAVE"]` em ~1 cena a cada 1-2 min (datas, nomes, números marcantes). Pessoa real nunca em animação.
  - Animações: estilo SEMPRE o mesmo (pedido do dono): silhueta recortada em papel, plana, contra fundo com
    brilho (prefixo e sufixo fixos em `animacao.py`); nos prompts, descrever a cena como silhuetas contra a luz,
    sem pedir outro estilo. Muda só a paleta, uma por vídeo (`"paleta_animacao"`), escolhida pela psicologia das
    cores conforme o tom do roteiro: investigacao (vermelho escuro e preto: crime, segredo, conspiração),
    reflexao (âmbar/ocre neutro: livros, análise, filosofia; padrão do Le Disciple), aprendizado (azul),
    natureza (verde: temas agradáveis, calma), misterio (índigo/roxo), melancolia (azul-acinzentado: perda, fim de
    era), epico (dourado e preto: impérios, poder, guerra; padrão do Impérios). Um mapa de cores aplicado por cima
    deixa todas as cenas no mesmo tom, mesmo quando a IA varia.
- Música de fundo (`automacao/musica.py`, `rodar musica baixar`): pasta `musicas/<clima>/` (tenso, melancolico,
  sereno, misterio), faixas de Kevin MacLeod (CC BY 4.0, vale fora do YouTube), normalizadas; volume baixo e ainda
  abaixado sob a voz. Clima: `"tom_musica"` no roteiro.json, senão o do canal (`config.MUSICA_CANAIS`);
  `"nenhuma"` desliga. Créditos entram na descrição sozinhos. Climas montados pelo nome das faixas, sem ouvir:
  o dono pode trocar.
- Ritmo: uma frase por cena (~8 s); fala > 9 s ganha segundo visual na metade. Meta de 50% das cenas em vídeo
  (é meta: imagem certa vale mais que vídeo sem relação).
- Edição: transições por xfade (fusão entre cenas; zoom/flash na virada de seção), só na imagem: o áudio fica intacto.
- Thumbnail: padrão desde 2026-11-20 é o estilo "impacto" (`automacao/thumb_impacto.py`, referências do dono:
  MrBeast e GameplayRJ): um foco gigante recortado (rembg) com contorno claro e brilho, fundo do tema saturado e
  desfocado com vinheta, 1 a 3 palavras enormes com contorno preto que NÃO repetem o título, amarelo/branco/azul
  (sem o vermelho/branco do YouTube), legível na prévia de celular (`*_celular.png`). Sempre 3 conceitos
  diferentes para o Testar e comparar do YouTube: `rosto` (personagem GENÉRICO expressivo, nunca pessoa real),
  `objeto` (símbolo do tema) e `antes_depois`. Conceitos em `projetos/<pasta>/conceitos_thumb.json`. O estilo
  antigo "cinema" (`thumb_ia.py`) continua disponível.
  - Impérios Caídos (referência do dono em 2026-11-21, thumb do próprio canal youtu.be/LbIO0YgQ3jQ): estilo
    `epico` em `thumb_impacto.py`: cenário de cinema na thumb inteira + personagem GENÉRICO gerado à parte,
    recortado e posto grande do lado oposto ao texto (luz de contorno suave, sem contorno de adesivo), gradação
    azul-petróleo/laranja; texto em Cinzel Black (`fontes/`, OFL): 1a linha dourada metálica com reticências
    ("MIL AÑOS..."), 1-2 linhas prateadas, ornamento dourado. Frases curtas = letras grandes. Fazer 3-4 opções.
    O gerador grátis erra roupa e época (marinheiro de uniforme moderno, chapéu de fantasia): conferir cada uma
    e descrever o personagem com época, roupa e expressão.
- Vídeo de HISTÓRIA com a voz gravada pelo dono: fundo contínuo de paisagens de drone + legenda palavra a palavra
  (`python -m automacao.historia projetos\<pasta> campo castelo floresta montanha`; antes, uma vez:
  `python -m automacao.paisagens restaurar` para baixar os clipes). Documentário com a voz do dono:
  `modelos/doc_voz.py`.
- Modelos de roteiro escrito à mão e de revisão: `modelos/` (montar_video_lista, trocar_visuais, visuais,
  reaproveitar, mini_folha, wiki_acervo, para_gravar).

## Lições (o que sempre revisar antes de entregar)
- O Nemotron inventa fatos, números e anedotas: ler `roteiro.md` antes de narrar; em vídeos com dados, escrever o
  roteiro à mão com fatos verificados.
- Conferir `folha_cenas.jpg`: notas do CLIP abaixo de 0,22 saem em vermelho. No máximo 2 rodadas de troca; o que
  sobrar, reaproveitar um visual bom do próprio vídeo (sempre depois da última busca).
- Máquina/lugar específico com poucas fotos livres: baixar as fotos reais antes e pôr direto nas cenas que falam dele.
- Thumbnails com logo de marca real + palavra negativa podem soar como acusação à marca; nunca usar pessoa real em
  imagem fabricada.
- Nunca usar trechos de vídeos de outros canais do YouTube (Content ID, strikes e "conteúdo reutilizado").
- Vídeo de Roma (2026-11-20): a busca pelo nome trouxe fotos modernas com o mesmo nome (papa atual em "Pope Leo",
  políticos em "Zeno", balsa chamada "Adrianople", cartaz do filme "Attila" com atores reais, vídeo aéreo de
  prédios). Sempre abrir a folha e trocar: pessoa real -> foto real boa do próprio vídeo; resto -> animação.
- Na nuvem o Wikimedia libera cerca de 1 download por minuto: 135 cenas levaram ~2 h e 30 falharam. Planejar
  mais animações (~40%) e reaproveitar fotos boas em vez de insistir; a 2a rodada quase não rendeu.
- Dois vídeos de uma vez (2026-11-21, Astecas e Cartago): nunca rodar duas buscas de fotos ao mesmo tempo (passa de
  3 pedidos simultâneos ao Wikimedia). Fluxo que funcionou: roteiro e narração dos dois; animações de ambos em
  paralelo (Pollinations não é Wikimedia); fotos de um vídeo por vez, só ~25-30 cenas-chave por vídeo (o resto
  animação); thumbs no AI Horde em paralelo. Cerca de 5 h para os dois. Conferir sempre a folha (vieram foto de
  foguete, satélite, jornal e cocar de índio norte-americano num guerreiro tlaxcalteca na thumb).
- Le Disciple (2026-11-22, meditação estoica e Frankl): o Whisper pulou os primeiros ~26 s da narração (cena 1 ficou com
  28 s e as seguintes quase sem áudio): conferir a duração das 3 primeiras cenas depois do `alinhar`. Animações de troca
  não podem se chamar `cena_XXX_b.jpg` (é o nome do segundo visual das falas longas). O Wikimedia de novo trouxe
  Wernher von Braun para "busto"/"Türkheim" e uma estação meteorológica: abrir sempre a folha, inclusive os segundos visuais.
