# **Filings B3**

<img src="assets/b3-brasil-bolsa-balcao.png" alt="Filings B3" class="hero-logo">

Simple and efficient Python library to interact with B3 (Brazil's exchange) public datasets.
Each reader turns one trading session into a typed, contract-validated `pandas.DataFrame`
carrying provenance — money as exact `Decimal`, never a lossy `float`.

---

## Contents

| Section | Description |
|---------|-------------|
| [Usage](usage.md) | Installation, imports, and the guarantees every reader makes |
| [Examples](examples.md) | Task-oriented, copy-paste recipes |
| [API Reference](api/index.md) | Every public reader and symbol |

---

## Quick start

```bash
pip install filings-b3
```

```python
from datetime import date
from filings_b3 import BdiBtbLendingOpenPositionsReader

df = BdiBtbLendingOpenPositionsReader(date(2025, 1, 2)).read()
```

---

Part of the `filings-*` family. Generated from the **lib-minimal** template via
[BlueprintX](https://github.com/guilhermegor/BlueprintX).
