#!/usr/bin/env python
"""The BDI table catalog — every table B3 publishes, and what this project does about it.

B3's Boletim Diário serves its datasets as named tables under ``arquivos.b3.com.br/bdi/table``.
This module records **all of them**, each with the state it is in here: shipped, tracked by an
issue, or (transiently, until someone files one) uncovered.

## Why a versioned map instead of deriving it

The two sides speak different vocabularies and there is no mechanical bridge. This project's
backlog is keyed by the ``b3_*`` module names inherited from the stpstone monorepo
(``b3_bdi_derivatives_mark_to_market``); B3 keys by its own table names (``DerivativesMtM``). So
"is this table covered?" cannot be answered by matching strings — it needs a map somebody wrote
down once.

Worse, the backlog was **seeded from stpstone's coverage, not from B3's catalog**. Whatever
stpstone never wrapped was invisible: no issue, no reader, nothing red. The audit behind issue
#186 measured it — of B3's 69 tables, **32 had never been recorded anywhere**, including
``EconomicIndicators``, the table that a mistaken issue premise sent an implementation chasing.
A missing entry is a false negative: the suite stays green precisely because nothing is looking.

This file is the "looking". :mod:`check_bdi_catalog` compares it against B3's live index
(``GET /bdi/table/classifications``) and opens a tracking issue when they diverge — so the day B3
publishes a 70th table, it is *noticed* rather than silently absent for a year.

Maintainer-facing surface — English, like every other ``bin/`` module here.
"""

from __future__ import annotations

from typing import Final


#: Where B3 lists its own tables. The DATA route is a POST; this INDEX route is a **GET** and
#: answers 405 to a POST — the reverse of the readers' endpoint, and a trap worth naming here
#: rather than rediscovering. Host-only literals keep the check-urls hook from fetching it.
CLASSIFICATIONS_PATH: Final[str] = "/bdi/table/classifications"
BDI_HOST: Final[str] = "https://arquivos.b3.com.br"

#: States a table can be in. ``IMPLEMENTADA`` carries the reader module's name; ``ISSUE`` carries
#: the tracking issue(s). There is deliberately **no** "uncovered" state in the data: a table
#: without a destination is exactly the defect this catalog exists to prevent, so the checker
#: treats a missing reference as an error rather than a legitimate value.
STATE_IMPLEMENTED: Final[str] = "IMPLEMENTADA"
STATE_ISSUE: Final[str] = "ISSUE"

#: table name → (friendly name in pt-BR, B3's classification, state, reference).
#: Ordered alphabetically so a diff shows an insertion, never a reshuffle.
BDI_TABLES: Final[dict[str, tuple[str, str, str, str]]] = {
	"AnalyticalFramework2": (
		"Quadro analítico das posições em aberto",
		"Derivativos de bolsa",
		STATE_ISSUE,
		"#189",
	),
	"AverageChart": (
		"Médias diárias – volume em um ano (R$ em milhões)",
		"Resumo de ações",
		STATE_ISSUE,
		"#38",
	),
	"BTBLendingOpenPosition": (
		"Posições em aberto",
		"Empréstimos de ativos",
		STATE_IMPLEMENTED,
		"btb_lending_open_positions",
	),
	"BTBLoanBalance": ("Empréstimos registrados", "Empréstimos de ativos", STATE_ISSUE, "#5"),
	"BTBTrade": ("Negócios", "Empréstimos de ativos", STATE_ISSUE, "#6"),
	"CNLDistrionCoffeLocation": (
		"Distribuição dos locais de formação de lotes café Conilon",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#15",
	),
	"CNLHarvestCoffeApprov": (
		"Estatísticas de safras dos lotes de cafés certificados - aprovados - café Conilon",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#11",
	),
	"CNLValidLotsSettle": (
		"Lotes válidos para a liquidação de contratos - café Conilon",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#190",
	),
	"COEInventory": ("Estoque", "COE", STATE_ISSUE, "#191"),
	"COERegistration": ("Registro", "COE", STATE_ISSUE, "#192"),
	"ConsolidatedRecords": ("Negociação consolidada", "Renda fixa", STATE_ISSUE, "#193"),
	"ConsolidatedTradesDerivatives": (
		"Negócios consolidados do pregão",
		"Derivativos de bolsa",
		STATE_ISSUE,
		"#194",
	),
	"ConsolidatedTradesDerivativesAfter": (
		"Negócios consolidados do pregão não regular",
		"Derivativos de bolsa",
		STATE_ISSUE,
		"#195",
	),
	"ConsolidatedTradesEquities": (
		"Negócios consolidados do pregão",
		"Resumo de ações",
		STATE_ISSUE,
		"#35",
	),
	"ConsolidatedTradesRVAfter": (
		"Negócios consolidados do pregão não regular",
		"Resumo de ações",
		STATE_ISSUE,
		"#34",
	),
	"Custody": (
		"Ações custodiadas - programa de ADR",
		"Clearing e depositária",
		STATE_ISSUE,
		"#8",
	),
	"DIover": ("DI over", "Renda fixa", STATE_ISSUE, "#196"),
	"DailyAverageDerivatives2": ("Derivativos", "Resumo", STATE_ISSUE, "#18"),
	"DailyAverageStocks": ("Ações", "Resumo de ações", STATE_IMPLEMENTED, "stocks_summary"),
	"DeadlineDepositSecurities": (
		"Prazo para depósito de títulos",
		"Clearing e depositária",
		STATE_ISSUE,
		"#31",
	),
	"DebenturesBusiness": (
		"Negócios de VM de renda fixa realizados no Puma",
		"Renda fixa",
		STATE_ISSUE,
		"#22",
	),
	"DerivativesMtM": ("Derivativos - mark to market", "Resumo", STATE_ISSUE, "#13"),
	"DerivativesOperation2": ("Derivativos - resumo das operações", "Resumo", STATE_ISSUE, "#17"),
	"DistrionCoffeLocation": (
		"Distribuição dos locais de formação de lotes café tipo 4/5",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#14",
	),
	"EconomicIndicators": (
		"Indicadores econômicos",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#197",
	),
	"EletronicTerm": ("Termo eletrônico", "Derivativos de balcão", STATE_ISSUE, "#198"),
	"FlexibleOptions": ("Opções flexíveis", "Derivativos de balcão", STATE_ISSUE, "#199"),
	"Forward": ("Ações mais negociadas - a termo", "Maiores oscilações", STATE_ISSUE, "#12"),
	"ForwardMarket": ("Mercado a termo", "Resumo de ações", STATE_ISSUE, "#36"),
	"FugibleCustody": ("Custódia fungível", "Clearing e depositária", STATE_ISSUE, "#33"),
	"HarvestCoffeApprov": (
		"Estatísticas de safras dos lotes de cafés certificados - aprovados - café Arábica 4/5",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#10",
	),
	"HistoricalExchange": (
		"Histórico de taxas de câmbio (Resolução BCB nº 120)",
		"Indicadores e informativos",
		STATE_IMPLEMENTED,
		"historical_exchange",
	),
	"INDEXES": (
		"Evolução dos índices",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#23,#25,#29",
	),
	"IOPV": (
		"Comportamento dos valores de referência das cotas dos ETFs (IOPV)",
		"Resumo de ações",
		STATE_ISSUE,
		"#28",
	),
	"IbovespaStockBiggestHighs": (
		"Ações do IBOVESPA - maiores altas",
		"Maiores oscilações",
		STATE_ISSUE,
		"#27",
	),
	"IbovespaStockBiggestLow": (
		"Ações do IBOVESPA - maiores baixas",
		"Maiores oscilações",
		STATE_ISSUE,
		"#26",
	),
	"InCash": ("Ações mais negociadas - à vista", "Maiores oscilações", STATE_ISSUE, "#39"),
	"InCashMarketBiggestHighs": (
		"Mercado à vista - maiores altas",
		"Maiores oscilações",
		STATE_ISSUE,
		"#21",
	),
	"InCashMarketBiggestLow": (
		"Mercado à vista - maiores baixas",
		"Maiores oscilações",
		STATE_ISSUE,
		"#20",
	),
	"InstrumentRegistration": ("Cadastro de instrumentos", "Renda fixa", STATE_ISSUE, "#200"),
	"InstrumentsDerivatives": (
		"Cadastro de instrumentos",
		"Derivativos de bolsa",
		STATE_ISSUE,
		"#201",
	),
	"InstrumentsEquities": ("Cadastro de instrumentos", "Resumo de ações", STATE_ISSUE, "#202"),
	"MarginScenarios": (
		"Cenários de margem para ativos líquidos",
		"Resumo de ações",
		STATE_ISSUE,
		"#37",
	),
	"NegotiStrategi": ("Negociação de estratégias", "Resumo de ações", STATE_ISSUE, "#42"),
	"OTCInventoryCCP": ("Estoque com CCP", "Derivativos de balcão", STATE_ISSUE, "#203"),
	"OTCInventoryWCCP": ("Estoque sem CCP", "Derivativos de balcão", STATE_ISSUE, "#204"),
	"OTCRegistrationCCP": ("Registro com CCP", "Derivativos de balcão", STATE_ISSUE, "#205"),
	"OTCRegistrationWCCP": ("Registro sem CCP", "Derivativos de balcão", STATE_ISSUE, "#206"),
	"OpenPositionsEquities": ("Posições em aberto", "Derivativos de bolsa", STATE_ISSUE, "#207"),
	"OptionsPurshase": (
		"Ações mais negociadas - opções de compra",
		"Maiores oscilações",
		STATE_ISSUE,
		"#9",
	),
	"OptionsSelling": (
		"Ações mais negociadas - opções de venda",
		"Maiores oscilações",
		STATE_ISSUE,
		"#16",
	),
	"Previa": (
		"Prévia das carteiras teóricas de índices",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#208",
	),
	"PreviaQuadrimestral": (
		"Composição das carteiras de índices",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#24",
	),
	"ProventionCreditVariable": (
		"Crédito de proventos",
		"Clearing e depositária",
		STATE_ISSUE,
		"#32",
	),
	"Register": ("Registro", "Renda fixa", STATE_ISSUE, "#209"),
	"Renewals": ("Renovações", "Empréstimos de ativos", STATE_ISSUE, "#7"),
	"Repodebenture": ("Debêntures negociações compromissadas", "Renda fixa", STATE_ISSUE, "#210"),
	"RepurchaseDealings": ("Negociações compromissadas", "Renda fixa", STATE_ISSUE, "#211"),
	"SaleOff": ("Liquidação", "Renda fixa", STATE_ISSUE, "#212"),
	"SharesInvesVolum": (
		"Participação dos investidores",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#213",
	),
	"SharesInvesVolumMonthly": (
		"Participação dos investidores mensal",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#214",
	),
	"Stock": ("Estoque", "Renda fixa", STATE_ISSUE, "#215"),
	"StocksOperationSummary": (
		"Ações - resumo das operações",
		"Resumo de ações",
		STATE_ISSUE,
		"#30",
	),
	"SwapFlex": ("Swap", "Derivativos de balcão", STATE_ISSUE, "#216"),
	"TDA": ("TDA - Valores nominais", "Renda fixa", STATE_ISSUE, "#217"),
	"TickByTickDerivatives": ("Negócio a negócio", "Derivativos de bolsa", STATE_ISSUE, "#218"),
	"TickByTickVariableIncome": ("Negócio a negócio", "Resumo de ações", STATE_ISSUE, "#219"),
	"Trade": ("Negócio a negócio", "Renda fixa", STATE_ISSUE, "#220"),
	"ValidLotsSettle": (
		"Lotes válidos para a liquidação de contratos - café Arábica",
		"Indicadores e informativos",
		STATE_ISSUE,
		"#19",
	),
}
