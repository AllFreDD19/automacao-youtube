# Disciple (personagem do Le Disciple du Savoir)

- `referencias/`: imagens do personagem criadas pelo dono. As thumbs usam SEMPRE uma delas (nunca gerar o
  personagem por IA: tem que ser exatamente ele). Melhor: imagens SEM texto, personagem de um lado e espaço livre
  do outro.
- `fundos/`: bibliotecas à luz de velas sem pessoas (AI Horde) para o lado do texto.
- Uso: `thumb_impacto.disciple(destino, referencias/ref_X.png, "PALAVRA\nGRANDE", "AUTOR", "esquerda",
  fundos/fundo_N.jpg, inicio, fim)`. inicio/fim = onde o fundo novo encontra a imagem (fração da largura);
  ref_1: 0.53-0.585, ref_2: 0.475-0.515 (cobrem o texto que já vinha escrito nessas imagens).
