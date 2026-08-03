# #171 — a regra de qualificação por container de referência, registrada nos readers

Branch: `docs/171-regra-qualificacao-container-referencia`. Closes #171.

## Checklist

- [x] Reescrever o comentário acima de `_DICT_PATHS` nos 6 readers por sub-bloco
- [x] Nomear os três containers de referência e citar #165 como origem da regra
- [ ] Sem `/release` ao mergear — `docs:` não altera artefato publicado

## O que mudou

Só o bloco de comentário acima de `_DICT_PATHS`, idêntico nos 6 readers por sub-bloco
(`adr`, `btc`, `eqty`, `eqty_fwd`, `optn_on_eqts`, `optn_on_spot_and_futures`) — +4 −3 cada.
Nenhum `_DICT_PATHS` tocado, nenhuma coluna afetada, nenhum teste afetado.

## Por que não é cosmético

A redação antiga — "qualificado pelo pai apenas onde a folha nua colidiria" — descreve o
**resultado** e não o **critério**, e o "apenas onde colidiria" sugere que a qualificação seria
uma *reação* a uma colisão já observada. Lida assim, ela autoriza o próximo reader a deixar um
`Tp`/`Prtry` nu enquanto nada colidir *ainda*.

A regra real é incondicional: toda folha alcançada **através** de um container de referência
(`UndrlygInstrmId`, `TrgtInstrmId`, `AsstSttlmInd`) é qualificada por esse container, porque essas
referências repetem a forma de identificação ISO-20022 do próprio registro. É exatamente essa
incondicionalidade que sustenta "um campo, um nome de coluna" (#165) — sem ela, o mesmo campo
ganharia um nome diferente em cada reader do mesmo arquivo, que é o defeito que #165 fechou.

Ou seja: o comentário documentava o sintoma de #165 em vez da invariante, e um comentário assim
convida a regressão que a issue anterior custou um BREAKING (0.3.0) para corrigir.

## Aberto

- Nada. A regra vale para os 6 readers por sub-bloco existentes; os readers de blocos sem
  container de referência não têm o comentário e não precisam dele.
