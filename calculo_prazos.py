"""Regras de cálculo de prazos (dias úteis, feriados e faixas de urgência).

Módulo separado do app para poder ser testado sem subir o Streamlit nem o banco.
Tudo aqui é função pura: recebe a data de referência como parâmetro.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FAIXAS = {
    "Vencido": "🔴 Vencido",
    "Hoje": "🟠 Vence hoje",
    "Até 3 dias": "🟡 Até 3 dias",
    "Até 7 dias": "🔵 Até 7 dias",
    "Futuro": "🟢 Mais de 7 dias",
    "Concluído": "✅ Concluído",
}

FERIADOS = np.array([
    # 2026
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-04-03", "2026-04-21",
    "2026-05-01", "2026-06-04", "2026-09-07", "2026-10-12", "2026-11-02",
    "2026-11-15", "2026-11-20", "2026-12-25",
    # 2027
    "2027-01-01", "2027-02-08", "2027-02-09", "2027-03-26", "2027-04-21",
    "2027-05-01", "2027-06-03", "2027-09-07", "2027-10-12", "2027-11-02",
    "2027-11-15", "2027-11-20", "2027-12-25",
    # 2028
    "2028-01-01", "2028-02-28", "2028-03-01", "2028-04-14", "2028-04-21",
    "2028-05-01", "2028-05-30", "2028-09-07", "2028-10-12", "2028-11-02",
    "2028-11-15", "2028-11-20", "2028-12-25",
    # Recesso Forense (20/12 a 20/01 - Art. 220 CPC)
    "2026-12-20", "2026-12-21", "2026-12-22", "2026-12-23", "2026-12-24", "2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31",
    "2027-01-04", "2027-01-05", "2027-01-06", "2027-01-07", "2027-01-08", "2027-01-11", "2027-01-12", "2027-01-13", "2027-01-14", "2027-01-15", "2027-01-18", "2027-01-19", "2027-01-20",
    "2028-12-20", "2028-12-21", "2028-12-22", "2028-12-23", "2028-12-24", "2028-12-28", "2028-12-29", "2028-12-30", "2028-12-31",
    "2029-01-04", "2029-01-05", "2029-01-06", "2029-01-07", "2029-01-08", "2029-01-11", "2029-01-12", "2029-01-13", "2029-01-14", "2029-01-15", "2029-01-18", "2029-01-19", "2029-01-20",
    # Feriados Estaduais RS
    "2026-09-20", "2027-09-20", "2028-09-20",
], dtype="datetime64[D]")



def calcular_urgencia(df: pd.DataFrame, ref, feriados=None) -> pd.DataFrame:
    """Preenche dias_corridos, dias_uteis, faixa e situacao a partir de data_fatal.

    dias_uteis conta os dias úteis de ref (inclusive) até data_fatal (exclusive),
    descontando sábados, domingos e os feriados informados.
    """
    if feriados is None:
        feriados = FERIADOS
    ref = np.datetime64(ref, "D")
    fatal = df["data_fatal"].values.astype("datetime64[D]")
    df["dias_corridos"] = (fatal - ref).astype(int)
    df["dias_uteis"] = np.busday_count(ref, fatal, holidays=feriados)
    d = df["dias_corridos"]
    df["faixa"] = np.select(
        [df["concluido"], d < 0, d == 0, d <= 3, d <= 7],
        ["Concluído", "Vencido", "Hoje", "Até 3 dias", "Até 7 dias"],
        default="Futuro",
    )
    df["situacao"] = df["faixa"].map(FAIXAS)
    return df
