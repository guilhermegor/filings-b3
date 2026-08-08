# filings-b3 <img src="assets/b3-logo.png" align="right" width="200" style="border-radius: 15px;" alt="filings-b3">

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyPI Version](https://img.shields.io/pypi/v/filings-b3)
[![Snyk Vulnerabilities](https://snyk.io/test/github/guilhermegor/filings-b3/badge.svg)](https://snyk.io/test/github/guilhermegor/filings-b3)
[![Snyk License](https://snyk.io/advisor/python/filings-b3/badge.svg)](https://snyk.io/advisor/python/filings-b3)
![PyPI Downloads](https://static.pepy.tech/badge/filings-b3)
[![Linting](https://img.shields.io/badge/linting-ruff_|_codespell-blue)](https://github.com/astral-sh/ruff)
![Formatting: isort](https://img.shields.io/badge/formatting-isort-%231674b1)
![Test Coverage](./coverage.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Open Issues](https://img.shields.io/github/issues/guilhermegor/filings-b3)
![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-darkgreen.svg)

Biblioteca Python simples e eficiente para acessar os conjuntos de dados públicos da B3 (a bolsa
brasileira). Cada _reader_ transforma um pregão em um `pandas.DataFrame` tipado, validado por
contrato e com proveniência — valores monetários como `Decimal` exato, nunca um `float` com perda.

## ✨ Principais recursos

### 📊 Readers do Boletim Diário (BDI)
- [`BdiStocksSummaryReader`](https://guilhermegor.github.io/filings-b3/api/daily_bulletin/stocks_summary/) — o resumo por pregão do mercado à vista de ações (`DailyAverageStocks`).
- [`BdiBtbLendingOpenPositionsReader`](https://guilhermegor.github.io/filings-b3/api/daily_bulletin/btb_lending_open_positions/) — o retrato das posições em aberto de empréstimo de ativos (BTB) (`BTBLendingOpenPosition`).

### 🗂️ Readers da Pesquisa por Pregão

O arquivo de instrumentos do pregão (`IN{aammdd}.zip`, BVBG.028.02) é **um download lido de dezoito
formas**: cada registro aninha os seus campos sob exatamente um de 20 blocos `InstrmInf`. O
_download_ é um zip dentro de um zip, com um XML por _snapshot_ intradiário do pregão — todo
_reader_ lê o de maior `CreDtAndTm`, o definitivo, porque os _snapshots_ são cumulativos.

- [`InstrumentsFileReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file/) — todos os tipos sob o layout de 52 colunas publicado pela B3.
- **Por tipo**, cada um com a lista *completa* de campos do seu bloco:
  [`InstrumentsFileEqtyReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_eqty/) (ações),
  [`InstrumentsFileOptnOnEqtsReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_optn_on_eqts/) (opções sobre ações),
  [`InstrumentsFileOptnOnSpotAndFuturesReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_optn_on_spot_and_futures/) (opções sobre disponível e futuros),
  [`InstrumentsFileExrcEqtsReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_exrc_eqts/) (exercício de opções),
  [`InstrumentsFileEqtyFwdReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_eqty_fwd/) (termo de ações),
  [`InstrumentsFileFxdIncmReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_fxd_incm/) (renda fixa),
  [`InstrumentsFileAdrReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_adr/) (ADRs),
  [`InstrumentsFileBtcReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_btc/) (BTC),
  [`InstrumentsFileFutrCtrctsReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_futr_ctrcts/) (contratos futuros),
  [`InstrumentsFileDrvsOptnExrcReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_drvs_optn_exrc/) (exercício de opções sobre derivativos),
  [`InstrumentsFileStrtgyReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_strtgy/) (estratégias, com as duas pernas),
  [`InstrumentsFileNtlBdReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_ntl_bd/) (títulos públicos nacionais),
  [`InstrumentsFileIntlBdReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_intl_bd/) (títulos internacionais),
  [`InstrumentsFileFxdIncmNonTrdblReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_fxd_incm_non_trdbl/) (renda fixa não negociável),
  [`InstrumentsFileOtcReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_otc/) (balcão),
  [`InstrumentsFileCshReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_csh/) (disponível) e
  [`InstrumentsFileFicReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_file_fic/) (fundos de investimento).
- [`InstrumentsLayoutMetaReader`](https://guilhermegor.github.io/filings-b3/api/search_trading_session/instruments_layout_meta/) — _snapshot_ tipado do layout autoritativo da B3, para o _datalake_ e para o job semanal de deriva de contrato.

### 🔒 Fidelidade por construção
- **Tipagem explícita** — toda coluna tipada na carga, nunca a inferência do pandas.
- **Decimais exatos** — dinheiro e qualquer valor cuja parte fracionária importa é `decimal.Decimal`, nunca um `float` binário.
- **Contratos** — uma fonte que remove uma coluna obrigatória falha de forma barulhenta com `ContractError`, verificado contra os layouts publicados pela própria B3.

### 🧾 Proveniência & camada bronze
- Seis colunas de proveniência em todo _frame_ (`url`, `updated_at`, `source_key`, `package_version`, `ingestion_run_id`, `content_hash`).
- Passe `path_raw=` para reter cada página bruta da fonte para a camada bronze de um _datalake_.

## 🚀 Primeiros passos

### Pré-requisitos
- Python 3.10+
- Poetry (recomendado)
- Opcional: Makefile

### Instalação

**Opção 1: Pip (recomendado)**
```bash
pip install filings-b3
```

**Opção 2: Build a partir do código-fonte**
```bash
git clone https://github.com/guilhermegor/filings-b3.git
cd filings-b3
pyenv install 3.12.2
pyenv local 3.12.2
poetry install --no-root
poetry shell
```

### Uso básico
```python
from datetime import date
from filings_b3.daily_bulletin import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()
print(df[["TCKR_SYMB", "STOCK_BALANCE", "BALANCE"]].head())
```

Cada _reader_ é importado pela sua **macro-seção** (`filings_b3.daily_bulletin`,
`filings_b3.search_trading_session`, …) — a única forma pública. A raiz do pacote não exporta
_readers_.

> ⚠️ **Mudança na 0.3.0** — duas colunas do arquivo de instrumentos foram **renomeadas**, porque um
> mesmo campo vinha publicado com dois nomes diferentes entre _readers_ do mesmo arquivo, quebrando
> um `UNION ALL` sobre a família ([#165](https://github.com/guilhermegor/filings-b3/issues/165)).
> Só o **nome da coluna** mudou — caminho de origem e valores são os mesmos.
>
> | Reader | Antes | Agora |
> |---|---|---|
> | `InstrumentsFileFxdIncmReader` | `TP` | `UNDRLYG_INSTRM_ID_TP` |
> | `InstrumentsFileExrcEqtsReader` | `TP` | `OPTN_EXRC_INSTRM_ID_TP` |
>
> O `TP` de `InstrumentsFileIntlBdReader` **não** muda: ali é o _tag_ `Tp` de verdade do bloco.

> ⚠️ **Mudança na 0.2.0** — até a 0.1.x cada _reader_ também era reexportado de forma plana na raiz
> (`from filings_b3 import BdiBtbLendingOpenPositionsReader`). Isso **foi removido**: com seis
> macro-seções e ~105 datasets previstos, a raiz viraria uma lista de mais de cem nomes. Troque o
> _import_ pela seção correspondente.

`date_ref` é **obrigatório** — o endpoint do BDI é endereçado por data, então não existe um padrão
"mais recente". Veja a [documentação](https://guilhermegor.github.io/filings-b3/) para cada _reader_
e mais receitas.

### Rodando os testes
```bash
poetry run pytest tests/unit/ -v
poetry run pytest tests/integration/ -v
```

## 📂 Estrutura do projeto
```
filings-b3/
├── .github/
│   ├── workflows/
│   ├── CODEOWNERS
│   └── PULL_REQUEST_TEMPLATE.md
├── assets/
│   └── b3-logo.png
├── bin/
├── docs/
├── src/filings_b3/
│   ├── daily_bulletin/          # readers do Boletim Diário do Pregão (BDI)
│   ├── search_trading_session/  # readers da Pesquisa por Pregão
│   └── _internal/               # privado: contracts, utils, ports
├── tests/
│   ├── unit/
│   ├── integration/
│   └── performance/
├── LICENSE
├── Makefile
├── poetry.lock
├── pyproject.toml
├── README.md
└── requirements.txt
```

## 👨‍💻 Autores
- guilhermegor — [GitHub](https://github.com/guilhermegor) | [LinkedIn](https://www.linkedin.com/in/guilhermegor)

## 📜 Licença
Este projeto é licenciado sob a Licença MIT — veja [LICENSE](LICENSE).

## 🔗 Links úteis
- [Documentação](https://guilhermegor.github.io/filings-b3/)
- [Repositório no GitHub](https://github.com/guilhermegor/filings-b3)
- [Rastreador de issues](https://github.com/guilhermegor/filings-b3/issues)
