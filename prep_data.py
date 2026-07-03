"""
Data-preparatie voor de bpost Aalst DND-piloot monitoring.

Leest de bronbestanden in ./bron/ en schrijft schone, valideerde CSV's naar ./data/.
Enkel pandas en openpyxl (geen internet, geen andere packages).

Elke validatie die faalt geeft een duidelijke AssertionError. Er wordt niets
stilzwijgend gecorrigeerd: afwijkingen worden gelogd, niet aangepast.
"""

import re
from pathlib import Path

import pandas as pd

BRON = Path(__file__).parent / "bron"
DATA = Path(__file__).parent / "data"

PILOOT_START = pd.Timestamp("2026-09-21")
DENSE_PREFIXES = ("JL", "JM")
NONDENSE_PREFIXES = ("JT", "JU")


def _time_to_str(value):
    """Normaliseert een uurwaarde (str 'H:MM' of datetime.time) naar 'HH:MM'."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        h, m = value.split(":")
        return f"{int(h):02d}:{int(m):02d}"
    return f"{value.hour:02d}:{value.minute:02d}"


def prep_dim_dienst():
    """
    DimDienst — grain: 1 rij per rondenummer (JLxxx en JMxxx apart, JTxxx/JUxxx apart).
    Bronnen:
      - diensten_met_detail_ronden_en_extra_info.xlsx (Blad1): dense + non-dense basis.
      - diensten_met_uitreikingsgebied_en_LS_dagen.xlsx (Blad1): levert voor non-dense
        diensten Zone/Gemeente ('dynamisch') en de volledige Opmerking (incl. vrije dag),
        want de Opmerking-tekst in bron 1 is voor alle non-dense rijen identiek afgekapt.
    """
    fn1 = BRON / "diensten_met_detail_ronden_en_extra_info.xlsx"
    assert fn1.exists(), f"Bronbestand ontbreekt: {fn1}"
    raw = pd.read_excel(fn1, sheet_name="Blad1", header=None)

    header_rows = raw.index[raw[0] == "dienst"].tolist()
    assert len(header_rows) == 2, (
        f"Verwacht 2 headerrijen ('dienst') in Blad1, gevonden: {len(header_rows)}. "
        "Sheetlayout is gewijzigd t.o.v. verwacht formaat."
    )
    h_dense, h_nondense = header_rows

    dense = raw.iloc[h_dense + 1 : h_nondense - 1].copy()
    dense.columns = [
        "DienstNr", "RondeKey", "DagType", "Voertuig", "BeginUur",
        "EindUur", "Zone", "Gemeente", "Opmerking",
    ]
    dense = dense.dropna(subset=["RondeKey"])
    assert len(dense) == 122, f"Verwacht 122 dense rijen (61 diensten x 2 dagen), gevonden: {len(dense)}"
    assert dense["DienstNr"].nunique() == 61, (
        f"Verwacht 61 unieke dense DienstNr, gevonden: {dense['DienstNr'].nunique()}"
    )
    dense["Type"] = "dense"

    nondense = raw.iloc[h_nondense + 1 :].copy()
    nondense.columns = [
        "DienstNr", "RondeKey", "_dag", "Voertuig", "BeginUur",
        "EindUur", "_zone", "_gemeente", "Opmerking",
    ]
    nondense = nondense.dropna(subset=["RondeKey"])
    assert len(nondense) == 19, f"Verwacht 19 non-dense rijen (17 JT + 2 JU), gevonden: {len(nondense)}"
    nondense["Type"] = "non-dense"
    nondense["DagType"] = "elke dag"
    nondense = nondense.drop(columns=["_dag", "_zone", "_gemeente"])

    fn2 = BRON / "diensten_met_uitreikingsgebied_en_LS_dagen.xlsx"
    assert fn2.exists(), f"Bronbestand ontbreekt: {fn2}"
    raw2 = pd.read_excel(fn2, sheet_name="Blad1", header=None)
    nd_header_idx = raw2.index[(raw2[0] == "dienst nr") & (raw2[6] == "opmerking")].tolist()
    assert len(nd_header_idx) == 1, (
        f"Verwacht exact 1 non-dense headerrij ('dienst nr' + 'opmerking') in uitreikingsgebied-bestand, "
        f"gevonden: {len(nd_header_idx)}"
    )
    nd_extra = raw2.iloc[nd_header_idx[0] + 1 :, :7].copy()
    nd_extra.columns = ["RondeKey", "_begin", "_eind", "_dagnr", "_voertuig", "Zone", "Opmerking"]
    nd_extra = nd_extra.dropna(subset=["RondeKey"])
    assert len(nd_extra) == 19, (
        f"Verwacht 19 non-dense rijen in uitreikingsgebied-bestand, gevonden: {len(nd_extra)}"
    )
    assert set(nd_extra["Zone"].unique()) == {"dynamisch"}, (
        "Verwachtte 'dynamisch' als Zone/Gemeente voor alle non-dense diensten in "
        f"uitreikingsgebied-bestand, gevonden: {nd_extra['Zone'].unique()}"
    )
    nd_extra = nd_extra.set_index("RondeKey")
    nondense = nondense.set_index("RondeKey")
    nondense["Zone"] = nd_extra["Zone"]
    nondense["Gemeente"] = nd_extra["Zone"]
    nondense["Opmerking"] = nd_extra["Opmerking"]
    nondense = nondense.reset_index()

    dim = pd.concat([dense, nondense], ignore_index=True, sort=False)
    dim["DienstNr"] = dim["DienstNr"].astype(int)
    dim["BeginUur"] = dim["BeginUur"].apply(_time_to_str)
    dim["EindUur"] = dim["EindUur"].apply(_time_to_str)
    dim["Opmerking"] = dim["Opmerking"].where(dim["Opmerking"].notna(), None)

    opm_lower = dim["Opmerking"].fillna("").str.strip().str.lower()
    dim["HeeftDepRit"] = opm_lower.str.startswith("dep")
    dim["HeeftExtraTaak"] = (opm_lower != "") & ~opm_lower.str.startswith("dep") & ~opm_lower.str.startswith("paksat")

    dim["VrijeDag"] = None
    is_nd = dim["Type"] == "non-dense"
    dim.loc[is_nd, "VrijeDag"] = dim.loc[is_nd, "Opmerking"].str.extract(
        r"[Vv]rije dag:\s*(\w+)", expand=False
    )

    cols = [
        "RondeKey", "DienstNr", "DagType", "Type", "Zone", "Gemeente", "Voertuig",
        "BeginUur", "EindUur", "Opmerking", "HeeftDepRit", "HeeftExtraTaak", "VrijeDag",
    ]
    dim = dim[cols].sort_values(["Type", "DienstNr", "RondeKey"]).reset_index(drop=True)

    assert dim["RondeKey"].is_unique, "RondeKey is niet uniek in DimDienst — duplicaten gevonden."
    assert (dim["Type"] == "dense").sum() == 122
    assert dim.loc[dim["Type"] == "dense", "DienstNr"].nunique() == 61
    assert (dim["Type"] == "non-dense").sum() == 19

    return dim


def prep_fact_baseline(dim_dienst):
    """
    FactBaseline — grain: 1 rij per ronde.
    Bron: pakken_en_bussen_samengevat.xlsx, sheet 'ronde totaal'.
    Het blad bevat 2 herhaalde headerrijen (plakwerk uit meerdere exports) — die worden genegeerd.
    """
    fn = BRON / "pakken_en_bussen_samengevat.xlsx"
    assert fn.exists(), f"Bronbestand ontbreekt: {fn}"
    raw = pd.read_excel(fn, sheet_name="ronde totaal", header=0)
    raw = raw.iloc[:, :5]
    raw.columns = ["DienstNr", "RondeKey", "RondeNr", "Bussen", "Pakken"]
    raw = raw[raw["DienstNr"] != "Dienst"]
    raw = raw.dropna(subset=["RondeKey"]).copy()

    raw["RondeType"] = raw["RondeNr"].str.split("-").str[0]
    valid_types = {"Res", "Dep", "Mix", "Rbu"}
    onbekend = set(raw["RondeType"].unique()) - valid_types
    assert not onbekend, f"Onbekende RondeType-prefixen gevonden: {onbekend}"

    fact = raw[["RondeKey", "RondeNr", "RondeType", "Bussen", "Pakken"]].reset_index(drop=True)

    dense_keys = set(dim_dienst.loc[dim_dienst["Type"] == "dense", "RondeKey"])
    dense_in_fact = dense_keys & set(fact["RondeKey"])
    ontbrekend = sorted(dense_keys - dense_in_fact)
    if ontbrekend:
        print(
            f"  WAARSCHUWING: {len(ontbrekend)} dense RondeKey(s) hebben geen baseline-rij in "
            f"pakken_en_bussen_samengevat.xlsx: {ontbrekend}"
        )

    totaal_bussen = fact["Bussen"].sum()
    assert abs(totaal_bussen - 77105) <= 50, (
        f"Som Bussen ({totaal_bussen}) wijkt te veel af van verwachte ~77.105"
    )

    return fact, ontbrekend, totaal_bussen


def prep_bridge_oud_nieuw():
    """
    BridgeOudNieuw — forward fill op Dienst/DienstNr/RondeNr (merged-cell-stijl leeg
    bij vervolgrijen). Rijen zonder OudRondeNr worden gedropt.
    """
    fn = BRON / "vergelijking_oude_en_nieuwe_ronden_procentueel.xlsx"
    assert fn.exists(), f"Bronbestand ontbreekt: {fn}"
    raw = pd.read_excel(fn, sheet_name="Blad1", header=0)
    raw = raw.iloc[:, :6]
    raw.columns = ["Dienst", "DienstNr", "NieuwRondeNr", "OudRondeNr", "PctOud", "PctNieuw"]

    raw[["Dienst", "DienstNr", "NieuwRondeNr"]] = raw[["Dienst", "DienstNr", "NieuwRondeNr"]].ffill()

    voor_drop = len(raw)
    raw = raw.dropna(subset=["OudRondeNr"]).copy()
    aantal_gedropt = voor_drop - len(raw)

    raw["PctNieuw"] = pd.to_numeric(raw["PctNieuw"])
    bridge = raw[["OudRondeNr", "NieuwRondeNr", "PctNieuw"]].reset_index(drop=True)

    sommen = bridge.groupby("NieuwRondeNr")["PctNieuw"].sum()
    afwijkingen = sommen[(sommen - 100).abs() > 5]
    if len(afwijkingen):
        print(f"  WAARSCHUWING: {len(afwijkingen)} NieuwRondeNr met PctNieuw-som buiten 100 ± 5:")
        for ronde, som in afwijkingen.items():
            print(f"    {ronde}: som = {som:.1f}")

    return bridge, aantal_gedropt, sommen


def prep_dim_straat():
    """DimStraat — sheet 'per dienst en ronde'. Voetnoot-/legenderijen (lege Dienst) worden gedropt."""
    fn = BRON / "sorteerlijst.xlsx"
    assert fn.exists(), f"Bronbestand ontbreekt: {fn}"
    raw = pd.read_excel(fn, sheet_name="per dienst en ronde", header=0)
    raw.columns = ["Dienst", "RondeNr", "Postcode", "Deelgemeente", "Straat", "Nummerbereik"]

    straat = raw.dropna(subset=["Dienst"]).copy()
    straat["Postcode"] = straat["Postcode"].astype(int).astype(str)
    straat["Deelgemeente"] = straat["Deelgemeente"].str.strip()
    straat["Nummerbereik"] = straat["Nummerbereik"].replace("", None)

    return straat[["RondeNr", "Postcode", "Deelgemeente", "Straat", "Nummerbereik"]].reset_index(drop=True)


def prep_dim_date():
    """DimDate — 2025-01-01 t/m 2027-12-31. WekenSindsStart: week van 21/09/2026 = 0."""
    dates = pd.date_range("2025-01-01", "2027-12-31", freq="D")
    df = pd.DataFrame({"Date": dates})
    df["Jaar"] = df["Date"].dt.year
    df["Maand"] = df["Date"].dt.strftime("%B")
    df["MaandNr"] = df["Date"].dt.month
    df["WeekISO"] = df["Date"].dt.isocalendar().week.astype(int)
    df["Weekdag"] = df["Date"].dt.strftime("%A")
    df["IsWerkdag"] = df["Date"].dt.dayofweek < 5

    monday_of_row = df["Date"] - pd.to_timedelta(df["Date"].dt.dayofweek, unit="D")
    monday_of_start = PILOOT_START - pd.Timedelta(days=PILOOT_START.dayofweek)
    df["WekenSindsStart"] = ((monday_of_row - monday_of_start).dt.days // 7).astype(int)

    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    return df


def main():
    DATA.mkdir(exist_ok=True)
    print("=== Stap 1: data-preparatie ===\n")

    print("[1/5] DimDienst")
    dim_dienst = prep_dim_dienst()
    dim_dienst.to_csv(DATA / "DimDienst.csv", index=False, encoding="utf-8")
    print(f"  {len(dim_dienst)} rijen -> data/DimDienst.csv")
    print(f"  waarvan dense: {(dim_dienst['Type'] == 'dense').sum()}, "
          f"non-dense: {(dim_dienst['Type'] == 'non-dense').sum()}")
    print(f"  unieke dense DienstNr: {dim_dienst.loc[dim_dienst['Type'] == 'dense', 'DienstNr'].nunique()}")

    print("\n[2/5] FactBaseline")
    fact_baseline, ontbrekend, totaal_bussen = prep_fact_baseline(dim_dienst)
    fact_baseline.to_csv(DATA / "FactBaseline.csv", index=False, encoding="utf-8")
    print(f"  {len(fact_baseline)} rijen -> data/FactBaseline.csv")
    print(f"  som Bussen: {totaal_bussen} (target ≈ 77.105)")
    print(f"  som Pakken: {fact_baseline['Pakken'].sum():.2f}")
    print(f"  RondeType-verdeling: {fact_baseline['RondeType'].value_counts().to_dict()}")
    if ontbrekend:
        print(f"  dense RondeKeys zonder baseline-data: {ontbrekend}")

    print("\n[3/5] BridgeOudNieuw")
    bridge, aantal_gedropt, sommen = prep_bridge_oud_nieuw()
    bridge.to_csv(DATA / "BridgeOudNieuw.csv", index=False, encoding="utf-8")
    print(f"  {len(bridge)} rijen -> data/BridgeOudNieuw.csv (rijen gedropt zonder OudRondeNr: {aantal_gedropt})")
    print(f"  {sommen.between(95, 105).sum()}/{len(sommen)} NieuwRondeNr binnen 100 ± 5")

    print("\n[4/5] DimStraat")
    dim_straat = prep_dim_straat()
    dim_straat.to_csv(DATA / "DimStraat.csv", index=False, encoding="utf-8")
    print(f"  {len(dim_straat)} rijen -> data/DimStraat.csv")
    print(f"  unieke RondeNr: {dim_straat['RondeNr'].nunique()}")

    print("\n[5/5] DimDate")
    dim_date = prep_dim_date()
    dim_date.to_csv(DATA / "DimDate.csv", index=False, encoding="utf-8")
    print(f"  {len(dim_date)} rijen -> data/DimDate.csv")
    week0 = dim_date[dim_date["WekenSindsStart"] == 0]
    print(f"  week 0 loopt van {week0['Date'].min()} t/m {week0['Date'].max()}")

    print("\n=== Klaar ===")


if __name__ == "__main__":
    main()
