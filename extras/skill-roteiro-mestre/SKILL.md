---
name: roteiro-mestre
description: Prompt Mestre Universal de Roteiro do usuário (multinicho e multi-idioma) para vídeos de canais dark do YouTube. Use sempre que for escrever, revisar ou planejar um roteiro de vídeo, ficha de planejamento, títulos para roteiro, ou ao mexer no gerador de roteiros da ferramenta de automação de vídeos (C:\Users\User\Videos\automacao-youtube).
---

# Roteiro Mestre

As regras completas estão em `C:\Users\User\Videos\automacao-youtube\prompts\roteiro_mestre.md`.
Esse arquivo é a fonte única: leia-o inteiro antes de escrever ou revisar qualquer roteiro e siga-o à risca.
A ferramenta de automação também lê esse mesmo arquivo; se o usuário pedir para mudar as regras, edite ele.

## Quando o usuário pede um roteiro direto no chat

1. Monte o BLOCO DE ENTRADA com o que ele informou; campos vazios recebem os padrões do prompt
   (4 capítulos; caracteres: 11.000 para 15 min ou 22.000 para 30 min, nunca 40.000) ou são deduzidos da referência.
2. Execute as etapas 1, 2 e 3 e mostre a ficha de planejamento (em português) antes do texto.
3. Escreva o roteiro no idioma definido e passe pelo CHECKLIST FINAL antes de entregar.
4. Desde 2026-10-24 o usuário grava a própria voz: entregar o roteiro (roteiro.md + `para_gravar.txt`, só o texto
   falado, sem títulos nem números de capítulo) e parar. Não narrar nem editar sem pedido.
   Para gerar pela ferramenta: `.\rodar.bat roteiro <projeto> --referencia "<título ou link>" --idioma <idioma>`
   (ver `LEIA-ME.md` do projeto).

## Pontos que mais falham e merecem atenção

- Prompt Mestre atualizado em 2026-10-11 (novo modelo do usuário). Os três pontos que mais pesam, e que valem também
  para roteiros escritos à mão (ex.: `modelos/montar_video_lista.py`), não só para os gerados pela ferramenta:
  1. Primeiro parágrafo (~600-700 caracteres, 30 a 45 s) = ABERTURA DE RETENÇÃO (atualizado em 2026-10-12, prompt do
     usuário em `prompts/abertura_retencao.md`): 1a frase confirma o título e a imagem da thumb com o elemento mais
     forte; sem saudação nem pedido de inscrição; tensão; pelo menos 2 loops de curiosidade (respondidos depois, em
     capítulos definidos na ficha); transição forte. Resumo do título sim, desfecho nunca: a revelação principal fica
     no último terço. Em lista/contagem, nunca dizer qual é o número um.
     Ao escrever à mão, mostrar ao usuário 2 versões da abertura (chocante e misteriosa) antes de narrar; com o
     roteiro já em roteiro.json, `.\rodar.bat abertura <projeto>` gera as 2 e `--usar 1|2` aplica.
  2. REGRA DOS 3 CTAs (usuário, 2026-10-24, igual à Fábrica de Vídeos; detalhes de estilo na skill `cta-organico`):
     CTA 1 logo DEPOIS da abertura (curto: inscrição com motivo + pergunta para os comentários; nunca dentro dos
     primeiros 30 a 45 s); CTA 2 no fim do capítulo 2 (like + inscrição + pergunta); CTA 3 no final (like + inscrição
     + sininho + pergunta + sugestões de temas). Fim dos capítulos 1 e 3: só gancho, sem pedir nada.
  3. Gatilho de curiosidade em todo ponto de interseção (troca de item/assunto, antes de revelações, antes do CTA),
     variando o tipo e sempre pago depois; em C e D nunca inventar fato para criar suspense.
- Números por extenso (a narração por voz lê dígitos mal).
- Fatos, datas e citações inventados nos nichos C e D.
- Anacronismos nos nichos A e D.
- Tamanho: ~735 caracteres por minuto (11.000 ≈ 15 min; 22.000 ≈ 30 min). Pergunte se o vídeo é de 15 ou 30 min
  quando o pedido não disser.
- Custo zero: use apenas serviços gratuitos (lista completa no CLAUDE.md do projeto).
