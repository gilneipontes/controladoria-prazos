"""
Módulo de Filtros Avançados para Controladoria Jurídica
Fornece componentes para filtrar prazos por múltiplos critérios
"""

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")


def renderizar_filtros_sidebar(df_prazos: pd.DataFrame, responsaveis: list, tipos: list, prioridades: list) -> dict:
    """
    Renderiza os filtros avançados na sidebar e retorna os valores selecionados.

    Args:
        df_prazos: DataFrame com todos os prazos
        responsaveis: Lista de responsáveis
        tipos: Lista de tipos de prazos
        prioridades: Lista de prioridades

    Returns:
        dict com os filtros aplicados
    """

    # Inicializar session state para filtros
    if
