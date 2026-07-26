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

- [ ] `_internal/utils/xml_reader.py` seam: parse an XML file/bytes → `pd.DataFrame` given a
      **row anchor** (repeating `<InstrmInf>` parent) + an ordered **column→path spec** with
      per-row OR-alternative resolution. Keep parser import (`xml.etree.ElementTree` — stdlib, no new
      dep) inside the seam. Unit-test with a **synthetic minimal XML** (2–3 instrument types).
- [ ] `contracts/search_trading_session/instruments_file.py`: `FileContract` pinning the 52-col
      header (subset of required vs full-column — decide against the live fixture).
- [ ] `search_trading_session/instruments_file.py`: `InstrumentsFileReader` — `build_url` =
      `{PREGAO_DOWNLOAD_BASE}?filelist=IN{date_ref:%y%m%d}.zip`; override the read to unzip → XML →
      `xml_reader` → typed/contract/provenance. `list_date_cols` + `list_decimal_cols` per the marks
      above.
- [ ] Public API: export `InstrumentsFileReader` from `search_trading_session/__init__` (add to
      `_SECTION_SURFACE` in `test_api_boundary.py`) + root re-export.
- [ ] Docs: `docs/api/search_trading_session/{index,instruments_file}.md` + nav; update the api map.
- [ ] Tests: unit (seam + reader with the pinned fixture), integration mirroring package structure.
- [ ] On merge: `/release-py` (feat → minor per pre-1.0).

## Generalizable lesson (queued, capture on build)
The `xml_reader` seam (stdlib-ElementTree XML→DataFrame under a FileContract, parser hidden like
`tabular_reader` hides pandas) is a **python-common scaffold candidate** — sibling to
`tabular-reader-seam.md`. Capture into the BlueprintX store when it lands.
