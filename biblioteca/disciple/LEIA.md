# Disciple (personagem do Le Disciple du Savoir)

- `referencias/`: imagens do personagem criadas pelo dono. As thumbs usam SEMPRE uma delas (nunca gerar o
  personagem por IA: tem que ser exatamente ele). Melhor: imagens SEM texto, personagem de um lado e espaço livre
  do outro.
- `fundos/`: bibliotecas à luz de velas sem pessoas (AI Horde) para o lado do texto.
- Uso: `thumb_impacto.disciple(destino, referencias/ref_X.png, "PALAVRA\nGRANDE", "AUTOR", "esquerda",
  fundos/fundo_N.jpg, inicio, fim)`. inicio/fim = onde o fundo novo encontra a imagem (fração da largura);
  medidos a partir da BORDA DO LADO DO TEXTO (texto à direita: 0.515 = fundo novo cobre de 48,5% da largura em
  diante). ref_1: 0.53-0.585, ref_2: 0.475-0.515 (texto à esquerda); ref_6: 0.515-0.55 (texto à direita). Cobrem o
  texto que já vinha escrito nessas imagens. ref_7 parece outro homem: não usar.
- Exemplo com tema e tom: projetos/disciple-thumbs/carnet_2.jpg ("~LE CARNET\n~SECRET DE\nL'EMPEREUR", y_centro=0.34,
  tom=(60, 18, 80) púrpura imperial, fundo tenda_2.jpg).
