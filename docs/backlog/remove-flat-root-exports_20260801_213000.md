# #163 — remover a reexportação plana dos readers na raiz

Branch: `refactor/163-remove-flat-root-exports`. Closes #163. **Quebra de compatibilidade → 0.2.0.**

## Checklist

- [x] `src/filings_b3/__init__.py` — `__all__ = ["__version__"]`, _imports_ dos _readers_ removidos
- [x] Docstrings das duas seções (`daily_bulletin`, `search_trading_session`)
- [x] Exemplos de _docstring_ que ensinavam a forma plana (2 _readers_ do BDI)
- [x] `test_api_boundary.py` — teste **invertido** + um novo, mais amplo
- [x] `test_stocks_summary.py` / `test_btb_lending_open_positions.py` — 2 testes invertidos
- [x] Docs publicados: `index.md`, `usage.md`, `examples.md`, `api/index.md`, `README.md`
- [x] Suíte 298 passed; ruff, mypy, mkdocs --strict limpos
- [ ] `/release` ao mergear → **MINOR → 0.2.0**

## O que mudou

```python
# única forma pública
from filings_b3.daily_bulletin import BdiStocksSummaryReader
from filings_b3.search_trading_session import InstrumentsFileReader

# agora levanta ImportError
from filings_b3 import InstrumentsFileReader
```

`filings_b3.__all__ == ["__version__"]`, e `filings_b3.__version__` continua funcionando.

## Isto REVERTE uma decisão deliberada, não corrige um descuido

A reexportação plana veio da **#122** (PR #131, 0.1.3), que tornou os dois caminhos públicos e
estáveis — seção como preferida, raiz como conveniência retrocompatível. Havia inclusive um teste
de fronteira **exigindo** que toda exportação de seção estivesse na raiz.

Registrado aqui e nos _docstrings_ para que ninguém "conserte" isto depois achando que os
_exports_ da raiz se perderam por acidente.

O que mudou desde a #122: `search_trading_session` saiu de 2 para 11 _readers_ (#68, #139,
#69–#77) e a raiz cresceu junto. Com 6 macro-seções e ~105 datasets no _backlog_, a superfície
plana viraria uma lista de mais de cem nomes — o oposto do que a organização por seção resolve.

## Decisão: quebra limpa, sem depreciação

Avaliadas as duas formas; escolhida a quebra direta (decisão do usuário):

| | Quebra limpa (escolhida) | Depreciar e remover na 0.3.0 |
|---|---|---|
| Estado final | imediato | um ciclo depois |
| Custo | quebra o _import_ plano | `__getattr__` + avisos + testes por um _release_ |
| Protege quem? | — | um consumidor conhecido (`marketdata-fm`) |

Com o pacote na 0.1.x e um único consumidor conhecido, o _shim_ custaria manutenção para proteger
quem provavelmente não existe.

## O teste de fronteira inverteu

`test_every_section_export_is_reexported_at_the_root` **exigia** o que agora é proibido. Virou
`test_no_section_export_leaks_back_into_the_root`, e ganhou um irmão mais amplo,
`test_the_root_exports_no_readers_at_all`: o teste por seção só pega uma seção **já listada** em
`_SECTION_SURFACE` voltando à raiz; o novo pega a raiz ganhando **qualquer** _export_ com cara de
_reader_, inclusive de uma macro-seção futura ainda não listada.

Mesma inversão nos dois testes por _reader_ (`test_reader_is_exported_from_the_package_root` →
`..._from_its_section_and_not_from_the_root`), que agora afirmam os dois lados: resolve pela seção,
**não** resolve pela raiz.

## Não tocado de propósito

`docs/backlog/macro-section-public-api_20260725_192729.md` e
`public-layout-decision_20260722_181203.md` citam a forma plana, mas são **registros históricos** —
descrevem o que era verdade quando foram escritos. Reescrevê-los apagaria o registro de que a #122
foi uma decisão consciente, que é justamente o contexto que este PR precisa preservar.

## Verificação de aceite (todos confirmados)

- `from filings_b3 import InstrumentsFileReader` → `ImportError: cannot import name …`
- `from filings_b3.search_trading_session import InstrumentsFileReader` → OK
- `filings_b3.__all__ == ["__version__"]` → OK
- `filings_b3.__version__` resolve → OK
- Suíte completa **298 passed**; `ruff`, `mypy src`, `mkdocs --strict` limpos
