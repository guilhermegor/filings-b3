# #68 — migrate b3_instruments_file (BVBG.028.02) into search_trading_session

Branch: `feat/68-instruments-file-reader`. Bootstraps the **first concrete reader** of the
`search_trading_session` section (its base `_base_pregao_reader.py` already exists).

## Key findings (from investigation)

- **Mislabeled backlog**: the issue-body "🕸 headless browser" line is **boilerplate copied into
  every dataset issue**. The stpstone base `ABCB3SearchByTradingSession.get_response` uses **plain
  `requests.get`** — Wine/`parse_raw_ex_file` is only for the `.ex_` datasets (e.g. #50). So #68
  needs **no browser and no `scraping` extra**.
- **Source shape**: `https://www.b3.com.br/pesquisapregao/download?filelist=IN{yymmdd}.zip`. The ZIP
  holds a **raw BVBG.028.02 InstrumentReport XML** (ISO-20022 / `bvmf.100.02`), NOT a tabular CSV —
  so `_BasePregaoReader`'s tabular `read_table` path does **not** fit. #68 introduces **XML
  ingestion**.
- **Decision (user)**: add a reusable **`_internal/utils/xml_reader.py`** seam (keeps the XML parser
  dependency — `lxml`/stdlib ElementTree — out of the public source, mirroring how `tabular_reader`
  hides pandas). `InstrumentsFileReader` reads the ZIP member via this seam; the 8 sibling variants
  (#69–#77) reuse it.
- **Keystone**: #68 is the root of the 9-variant instruments family (#68–#77).

## Authoritative layout sources (live-fetched)

- **UP2DATA field mapping XLSX** (the flat layout + XML-path per column, with examples) —
  `https://www.b3.com.br/data/files/1A/45/CC/29/4C11881036DB3088AC094EA8/BVBG.028%20para%20UP2DATA.xlsx`
  → sheet **`InstrumentsConsolidatedFile`** is #68's target schema (52 fields).
- **Message catalog PDF v2.6** (101 pp, full nested structure) —
  `https://www.b3.com.br/data/files/0B/A1/CA/73/86072710547B5127AC094EA8/Catalogo-de-Mensagens-Cadastro-de-Instrumento-Versao-2.6.pdf`
  (the old `bvmfnet.com.br` URL is dead; this is the current B3 location).

The pesquisapregao IN file is the raw BVBG.028 XML; `InstrumentsConsolidatedFile` is **B3's own
canonical flattening** of that XML, so this sheet is authoritative for **both** the `FileContract`
columns AND the XML-path→column extraction map. Columns are typed `str` for fidelity except the
date and decimal columns noted below.

## InstrumentsConsolidatedFile — 52 fields (col · Campo · Abrev · Card · Type · XMLpath)

The XMLpath uses "ou" (OR) alternatives: the consolidated file interleaves 7 sub-block types
(`EqtyInf`, `FutrCtrctsInf`, `OptnOnSpotAndFutrsInf`, `OptnOnEqtsInf`, `SpotGoldInf`, `StrtgyInf`,
`FxdIncmNonTrdblInf`) under `<InstrmInf>`; a flat column pulls from whichever sub-block the row has.

1 ReportDate/RptDt [1..1] ISODate — RptParams>RptDtAndTm>Dt  **(date col)**
2 TickerSymbol/TckrSymb [1..1] — InstrmInf>{sub}>TckrSymb
3 Asset/Asst [1..1] Max30 — FinInstrmAttrCmon>Asst
4 AssetDescription/AsstDesc [1..1] Max100 — FinInstrmAttrCmon>AsstDesc
5 SegmentName/SgmtNm [1..1] — FinInstrmAttrCmon>Sgmt
6 MarketName/MktNm [1..1] — FinInstrmAttrCmon>Mkt
7 SecurityCategoryName/SctyCtgyNm [0..1] — InstrmInf>{sub}>SctyCtgy
8 ExpirationDate/XprtnDt [1..1] ISODate — InstrmInf>{sub}>XprtnDt  **(date col)**
9 ExpirationCode/XprtnCd [1..1] Max4 — InstrmInf>{sub}>XprtnCd
10 TradingStartDate/TradgStartDt [1..1] ISODate — InstrmInf>{sub}>TradgStartDt  **(date col)**
11 TradingEndDate/TradgEndDt [1..1] ISODate — InstrmInf>{sub}>TradgEndDt  **(date col)**
12 BaseCode/BaseCd [0..1] int — FutrCtrctsInf>BaseCd
13 ConversionCriteriaName/ConvsCritNm [0..1] — FutrCtrctsInf>ConvsCrit
14 MaturityDateTargetPoint/MtrtyDtTrgtPt [0..1] int — FutrCtrctsInf>MtrtyDtTrgtPt
15 RequiredConversionIndicator/ReqrdConvsInd [1..1] YesNo — FutrCtrctsInf>ReqrdConvsInd
16 ISIN/ISIN [1..1] — InstrmInf>{sub}>ISIN
17 CFICode/CFICd [1..1] Max6 — InstrmInf>{sub}>CFICd
18 DeliveryNoticeStartDate/DlvryNtceStartDt [0..1] ISODate — FutrCtrctsInf>DlvryNtceStartDt  **(date)**
19 DeliveryNoticeEndDate/DlvryNtceEndDt [0..1] ISODate — FutrCtrctsInf>DlvryNtceEndDt  **(date)**
20 OptionType/OptnTp [1..1] — InstrmInf>{OptnOnEqtsInf|OptnOnSpotAndFutrsInf}>OptnTp
21 ContractMultiplier/CtrctMltplr [1..1] Decimal — InstrmInf>{sub}>CtrctMltplr (Strtgy: SttlmIndMltplr)  **(decimal)**
22 AssetQuotationQuantity/AsstQtnQty [0..1] Decimal — InstrmInf>{sub}>AsstQtnQty  **(decimal)**
23 AllocationRoundLot/AllcnRndLot [1..1] int — InstrmInf>{sub}>AllcnRndLot
24 TradingCurrency/TradgCcy [1..1] — InstrmInf>{sub}>TradgCcy
25 DeliveryTypeName/DlvryTpNm [1..1] — InstrmInf>{OptnOnEqtsInf|FutrCtrctsInf}>DlvryTp
26 WithdrawalDays/WdrwlDays [1..1] int — InstrmInf>{sub}>WdrwlDays
27 WorkingDays/WrkgDays [1..1] int — InstrmInf>{sub}>WrkgDays
28 CalendarDays/ClnrDays [1..1] int — InstrmInf>{sub}>ClnrDays
29 RolloverBasePriceName/RlvrBasePricNm [1..1] — StrtgyInf>RlvrBasePricCd
30 OpeningFuturePositionDay/OpngFutrPosDay [0..1] int — StrtgyInf>OpngFutrPosDay
31 SideTypeCode1/SdTpCd1 [1..1] — StrtgyInf>StrtgyLegList>LegId[1]>SdTpCd
32 UnderlyingTickerSymbol1/UndrlygTckrSymb1 [1..1] — StrtgyInf>StrtgyLegList>LegId[1]>UndrlygInstrmId
33 SideTypeCode2/SdTpCd2 [1..1] — StrtgyInf>StrtgyLegList>LegId[2]>SdTpCd
34 UnderlyingTickerSymbol2/UndrlygTckrSymb2 [1..1] — StrtgyInf>StrtgyLegList>LegId[2]>UndrlygInstrmId
35 PureGoldWeight/PureGoldWght [0..1] Decimal — InstrmInf>{sub}>PureGoldWght  **(decimal)**
36 ExercisePrice/ExrcPric [1..1] 10-dec amount — InstrmInf>{OptnOnEqtsInf|OptnOnSpotAndFutrsInf}>ExrcPric  **(decimal)**
37 OptionStyle/OptnStyle [1..1] — OptnOnEqtsInf>OptnStyle | OptnOnSpotAndFutrsInf>ExrcStyle
38 ValueTypeName/ValTpNm [1..1] — InstrmInf>{FutrCtrctsInf|StrtgyInf}>ValTpCd
39 PremiumUpfrontIndicator/PrmUpfrntInd [1..1] YesNo — InstrmInf>{OptnOnSpotAndFutrsInf|OptnOnEqtsInf}>PrmUpfrntInd
40 OpeningPositionLimitDate/OpngPosLmtDt [1..1] ISODate — OptnOnSpotAndFutrsInf>OpngPosLmtDt  **(date)**
41 DistributionIdentification/DstrbtnId [1..1] int — InstrmInf>{OptnOnEqtsInf|EqtyInf}>DstrbtnId
42 PriceFactor/PricFctr [1..1] int — InstrmInf>{EqtyInf|OptnOnEqtsInf}>PricFctr
43 DaysToSettlement/DaysToSttlm [1..1] Max4 — InstrmInf>{OptnOnEqtsInf|EqtyInf}>DaysToSttlm
44 SeriesTypeName/SrsTpNm [0..1] Max50 — OptnOnEqtsInf>SrsTp
45 ProtectionFlag/PrtcnFlg [1..1] YesNo — OptnOnEqtsInf>PrtcnFlg
46 AutomaticExerciseIndicator/AutomtcExrcInd [1..1] YesNo — OptnOnEqtsInf>AutomtcExrcInd
47 SpecificationCode/SpcfctnCd [1..1] Max10 — EqtyInf>SpcfctnCd
48 CorporationName/CrpnNm [1..1] Max250 — EqtyInf>CrpnNm
49 CorporateActionStartDate/CorpActnStartDt [1..1] ISODate — EqtyInf>CorpActnStartDt  **(date)**
50 CustodyTreatmentTypeName/CtdyTrtmntTpNm [1..1] — EqtyInf>CtdyTrtmntTp
51 MarketCapitalisation/MktCptlstn [1..1] amount — EqtyInf>MktCptlstn  **(decimal)**
52 CorporateGovernanceLevelName/CorpGovnLvlNm [1..1] Max50 — EqtyInf>GovnInd

### Column casing
UP2DATA "Abreviação" is the BVBG PascalCase tag. Per section convention, the reader emits
UPPER_SNAKE_CASE column names derived from the **field name** (e.g. `TICKER_SYMBOL`,
`SECURITY_CATEGORY_NAME`) — confirm the exact casing rule against `daily_bulletin` (which converts
PascalCase tag → UPPER_SNAKE via `utils/text.pascal_to_upper_snake`).

## ⚠ Live-verify blocker (must resolve before finalizing the contract)

The project rule: layout from B3's published spec **then confirmed against a live response**. The
live confirm is currently blocked — the env clock reads 2026-07 and B3's pesquisapregao serves an
**empty ZIP** (`PK` + 22 bytes) for those future-dated days; stpstone ships no captured XML fixture.
**Before merge**, capture ONE real `IN{yymmdd}.zip` (a genuine recent B3 business day) as a test
fixture and reconcile the flattened columns against this 52-field layout (verbatim-pinned fixture,
per `fixtures-verbatim-exclude-whitespace-hooks` discipline).

## Build plan (TDD)

- [x] `_internal/utils/xml_reader.py` seam — `read_xml(path, row_tag, dict_paths, dtypes, contract,
      dict_scalars, date_cols, decimal_cols)`. Namespace-agnostic (local-name match), OR-alternative
      resolution, scalar broadcast, shared contract+dtype tail. Parses via **defusedxml** (trust
      boundary), not bare `xml.etree`. 3 unit tests (synthetic 2-record XML). Committed `7138bc3`.
- [x] `contracts/search_trading_session/instruments_file.py` — `INSTRUMENTS_FILE` **subset**
      contract (7 universal identity cols required; `bool_full_column=False`). Registered in the
      section + top-level contracts `__init__`.
- [x] `search_trading_session/instruments_file.py` — `InstrumentsFileReader` implements the
      `IngestionReader` port directly (XML doesn't fit the tabular base). Full 52-field path spec
      from the UP2DATA layout as module constants; `_ROW_TAG` isolated for reconcile. `build_url` =
      `IN{date_ref:%y%m%d}.zip`; read = download → unzip → single-XML → `read_xml` → provenance.
      `list_date_cols` (8) + `list_decimal_cols` (5); rest `str`.
- [x] Public API: exported from `search_trading_session/__init__` + root re-export; boundary gate
      `_PUBLIC_SURFACE` + `_SECTION_SURFACE` updated (58 passed).
- [x] Docs: `docs/api/search_trading_session/{index,instruments_file}.md` + nav; api map updated
      (section now "1 reader"). `.codespellrc` extended with pt-BR terms.
- [x] Tests: unit — `test_xml_reader.py` (seam) + `test_instruments_file.py` (reader, download
      mocked, synthetic IN.zip). No per-reader network integration test (matches daily_bulletin;
      live-verify is the manual pre-merge step below). Full suite 207 passed; ruff/mypy/typing clean.
- [ ] On merge: `/release-py` (feat → minor per pre-1.0).

## ⚠ PRE-MERGE LIVE RECONCILE — do NOT merge until done

The code is built against the **authoritative UP2DATA layout** and proven by a synthetic fixture,
but three things are unverifiable without a real IN file (the dev clock is future-dated → B3 serves
an empty ZIP). Before merge, capture ONE genuine `IN{yymmdd}.zip` from a real recent B3 business day
and reconcile:

1. **`_ROW_TAG`** (currently `"InstrmRcrd"`, an assumption) — confirm the actual repeating
   instrument-record element's local name. Single-point-of-change constant in the reader.
2. **The single-XML-member assumption** and its encoding — confirm the ZIP holds exactly one `.xml`.
3. **Column casing + the 52 XML paths** — confirm the flattened header matches `INSTRUMENTS_FILE`
   and each field's path/alternatives resolve. Pin the real file as a verbatim test fixture
   (per `fixtures-verbatim-exclude-whitespace-hooks`).

## Generalizable lesson (queued, capture on build)
The `xml_reader` seam (stdlib-ElementTree XML→DataFrame under a FileContract, parser hidden like
`tabular_reader` hides pandas) is a **python-common scaffold candidate** — sibling to
`tabular-reader-seam.md`. Capture into the BlueprintX store when it lands.
