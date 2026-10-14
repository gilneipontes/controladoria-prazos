"""Testes do cálculo de prazos (dias úteis, feriados, recesso e faixas de urgência).

Rodar a partir da pasta do projeto:
    pytest -v

Os testes não usam banco nem internet. A data de referência (hoje) é sempre passada
explicitamente, então o resultado não muda com o dia em que os testes rodam.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculo_prazos import FERIADOS, calcular_urgencia  # noqa: E402


def calcular(data_ref: str, data_fatal: str, concluido: bool = False) -> pd.Series:
    """Calcula as métricas de um único prazo a partir de uma data de referência."""
    df = pd.DataFrame({
        "data_fatal": [pd.Timestamp(data_fatal)],
        "concluido": [concluido],
    })
    resultado = calcular_urgencia(df, np.datetime64(data_ref, "D"), FERIADOS)
    return resultado.iloc[0]


# ----- Dias corridos e faixas de urgência -----

def test_prazo_que_vence_hoje_esta_na_faixa_hoje():
    r = calcular("2026-10-14", "2026-10-14")
    assert r["dias_corridos"] == 0
    assert r["faixa"] == "Hoje"


def test_prazo_vencido_tem_dias_corridos_negativos():
    r = calcular("2026-10-14", "2026-10-13")
    assert r["dias_corridos"] == -1
    assert r["faixa"] == "Vencido"


def test_prazo_concluido_fica_concluido_mesmo_vencido():
    r = calcular("2026-10-14", "2026-10-01", concluido=True)
    assert r["faixa"] == "Concluído"


@pytest.mark.parametrize("dias, faixa", [
    (1, "Até 3 dias"),
    (3, "Até 3 dias"),
    (4, "Até 7 dias"),
    (7, "Até 7 dias"),
    (8, "Futuro"),
])
def test_faixas_de_urgencia_por_dias_corridos(dias, faixa):
    ref = pd.Timestamp("2026-10-14")
    fatal = (ref + pd.Timedelta(days=dias)).strftime("%Y-%m-%d")
    assert calcular("2026-10-14", fatal)["faixa"] == faixa


# ----- Dias úteis -----

def test_dias_uteis_nao_contam_fim_de_semana():
    # Sexta 16/10/2026 -> segunda 19/10/2026: só a sexta conta como dia útil
    r = calcular("2026-10-16", "2026-10-19")
    assert r["dias_corridos"] == 3
    assert r["dias_uteis"] == 1


def test_dias_uteis_descontam_feriado_nacional():
    # Sexta 04/09/2026 -> terça 08/09/2026. Segunda 07/09 é feriado (Independência).
    # Conta: sexta (1). Sábado, domingo e segunda não contam, terça é o vencimento.
    r = calcular("2026-09-04", "2026-09-08")
    assert r["dias_uteis"] == 1


def test_dias_uteis_descontam_recesso_forense():
    # Sexta 18/12/2026 -> segunda 28/12/2026. Recesso de 20/12 a 20/01 (art. 220 CPC):
    # 21 a 24/12 são recesso, 25/12 é feriado. Só a sexta 18/12 conta.
    r = calcular("2026-12-18", "2026-12-28")
    assert r["dias_uteis"] == 1


def test_virada_de_ano_inteira_no_recesso_nao_tem_dias_uteis():
    # 31/12/2026 -> 05/01/2027: todo o período cai em recesso ou feriado de 01/01.
    r = calcular("2026-12-31", "2027-01-05")
    assert r["dias_uteis"] == 0


def test_mesmo_dia_tem_zero_dias_uteis():
    r = calcular("2026-10-14", "2026-10-14")
    assert r["dias_uteis"] == 0


# ----- Caso de borda que precisa de decisão jurídica -----

def test_vencimento_em_fim_de_semana_conta_ate_a_sexta_anterior():
    """Caso de comportamento atual, não de regra jurídica validada.

    Hoje o sistema não ajusta a data fatal que cai em sábado ou domingo: a contagem
    de dias úteis para no dia anterior. Antes de considerar esse comportamento
    correto, validar com o advogado responsável qual regra o escritório segue.
    """
    # Quinta 15/10/2026 -> sábado 17/10/2026: quinta e sexta são dias úteis.
    r = calcular("2026-10-15", "2026-10-17")
    assert r["dias_uteis"] == 2
