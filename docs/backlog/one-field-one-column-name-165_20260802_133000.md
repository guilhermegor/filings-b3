# Ledger — um campo, um nome de coluna (#165)

Branch: `fix/165-one-field-one-column-name`
Issue: #165
Iniciado: 2026-08-02

## O defeito

Auditoria dos 8 _readers_ **já publicados** contra o Catálogo de Mensagens v2.6 (durante #150–#158)
encontrou o mesmo campo publicado com **dois nomes** entre _readers_ do **mesmo** arquivo — o que a
convenção escrita da família já proibia, sem nenhum portão executável para sustentá-la.

Publicado da **0.1.5 à 0.2.1**, com a suíte verde o tempo todo.

## O que a verificação encontrou além do relatado

O _issue_ descrevia uma colisão. Ao escrever o portão apareceu a **metade pior**: o nome `TP`
resolvia para **três** caminhos distintos.

```
one path, several column names:
  UndrlygInstrmId/OthrId/Tp/Prtry -> ['TP', 'UNDRLYG_INSTRM_ID_TP']

one column name, several paths:
  TP -> ['OptnExrcInstrmId/OthrId/Tp/Prtry', 'Tp', 'UndrlygInstrmId/OthrId/Tp/Prtry']
```

O terceiro é o `Tp` **legítimo** de `IntlBdInf` — um campo de verdade, que continua `TP`. Ou seja,
empilhar os quadros da família fundia **três campos sem relação** numa coluna só. Por isso o portão
tem **duas** direções, não uma.

## Feito

- [x] `instruments_file_fxd_incm.py`: `TP` → `UNDRLYG_INSTRM_ID_TP` (+ contrato)
- [x] `instruments_file_exrc_eqts.py`: `TP` → `OPTN_EXRC_INSTRM_ID_TP` (o contrato não o exigia)
- [x] `IntlBdInf` **intocado** — o `TP` de lá é o _tag_ `Tp` real do bloco
- [x] Dois testes novos: um caminho → um nome; um nome → um caminho
- [x] **Verificado que os portões falham** com o código anterior (restaurando os dois _readers_ de
      `main`): ambos ficaram vermelhos com a mensagem exata acima. Um teste de regressão que não
      falha no defeito não é um teste.
- [x] Comentários dos dois _readers_ reescritos: a regra fraca ("qualificado só onde o nome nu
      colidiria") era exatamente a brecha; agora é "toda folha alcançada **através** de um
      contêiner de referência é qualificada por ele".
- [x] Nota de migração em `docs/api/.../instruments_file_fxd_incm.md`,
      `.../instruments_file_exrc_eqts.md` e no `README.md`
- [x] **361 testes passando**

## Release

**Minor** (`0.2.1` → `0.3.0`): é quebra de contrato publicado, e neste repositório 0.x a quebra
toma o _minor_ — mesma forma do #163 (`0.1.6` → `0.2.0`).

## Aberto

- [ ] Commit + PR (`Closes #165`) + `/release`
- [ ] #167 (`read_xml` em _stream_), #147 (moeda no consolidado), #159–#161 (ouro), #136 (bot-merge)
