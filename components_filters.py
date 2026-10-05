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
    """

    # Inicializar session state para filtros
    if "filtros_ativos" not in st.session_state:
        st.session_state.filtros_ativos = {
            "responsavel": [],
            "status": [],
            "tipo": [],
            "prioridade": [],
            "data_inicio": None,
            "data_fim": None,
            "cliente": "",
            "numero_processo": "",
        }

    st.sidebar.divider()
    st.sidebar.markdown("### 🔍 FILTROS AVANÇADOS")

    # ===== RESPONSÁVEL =====
    st.session_state.filtros_ativos["responsavel"] = st.sidebar.multiselect(
        "👤 Responsável",
        options=responsaveis,
        default=st.session_state.filtros_ativos.get("responsavel", []),
        key="filtro_responsavel",
    )

    # ===== STATUS =====
    opcoes_status = ["Ativo", "Concluído", "Arquivado"]
    st.session_state.filtros_ativos["status"] = st.sidebar.multiselect(
        "✅ Status",
        options=opcoes_status,
        default=st.session_state.filtros_ativos.get("status", []),
        key="filtro_status",
    )

    # ===== TIPO =====
    st.session_state.filtros_ativos["tipo"] = st.sidebar.multiselect(
        "📋 Tipo",
        options=tipos,
        default=st.session_state.filtros_ativos.get("tipo", []),
        key="filtro_tipo",
    )

    # ===== PRIORIDADE =====
    st.session_state.filtros_ativos["prioridade"] = st.sidebar.multiselect(
        "🎯 Prioridade",
        options=prioridades,
        default=st.session_state.filtros_ativos.get("prioridade", []),
        key="filtro_prioridade",
    )

    # ===== FAIXA DE DATA =====
    st.sidebar.markdown("**📅 Faixa de Data**")
    col1, col2 = st.sidebar.columns(2)

    with col1:
        st.session_state.filtros_ativos["data_inicio"] = st.date_input(
            "De",
            value=st.session_state.filtros_ativos.get("data_inicio"),
            key="filtro_data_inicio",
        )

    with col2:
        st.session_state.filtros_ativos["data_fim"] = st.date_input(
            "Até",
            value=st.session_state.filtros_ativos.get("data_fim"),
            key="filtro_data_fim",
        )

    # ===== BUSCA POR CLIENTE =====
    st.session_state.filtros_ativos["cliente"] = st.sidebar.text_input(
        "🏢 Cliente (parcial)",
        value=st.session_state.filtros_ativos.get("cliente", ""),
        placeholder="Ex: Silva",
        key="filtro_cliente",
    )

    # ===== BUSCA POR PROCESSO =====
    st.session_state.filtros_ativos["numero_processo"] = st.sidebar.text_input(
        "⚖️ Processo (parcial)",
        value=st.session_state.filtros_ativos.get("numero_processo", ""),
        placeholder="Ex: 0001234",
        key="filtro_processo",
    )

    # ===== BOTÕES DE AÇÃO =====
    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("🔄 Limpar Filtros", use_container_width=True, key="btn_limpar_filtros"):
            st.session_state.filtros_ativos = {
                "responsavel": [],
                "status": [],
                "tipo": [],
                "prioridade": [],
                "data_inicio": None,
                "data_fim": None,
                "cliente": "",
                "numero_processo": "",
            }
            st.rerun()

    with col2:
        qtd_filtros = sum([
            len(st.session_state.filtros_ativos.get("responsavel", [])),
            len(st.session_state.filtros_ativos.get("status", [])),
            len(st.session_state.filtros_ativos.get("tipo", [])),
            len(st.session_state.filtros_ativos.get("prioridade", [])),
            1 if st.session_state.filtros_ativos.get("cliente") else 0,
            1 if st.session_state.filtros_ativos.get("numero_processo") else 0,
            1 if st.session_state.filtros_ativos.get("data_inicio") else 0,
            1 if st.session_state.filtros_ativos.get("data_fim") else 0,
        ])

        st.sidebar.metric("Filtros Ativos", qtd_filtros)

    return st.session_state.filtros_ativos


def aplicar_filtros(df_prazos: pd.DataFrame, filtros: dict) -> pd.DataFrame:
    """
    Aplica os filtros ao DataFrame de prazos.
    """

    df_filtrado = df_prazos.copy()

    # Filtro por responsável
    if filtros.get("responsavel"):
        df_filtrado = df_filtrado[df_filtrado["responsavel"].isin(filtros["responsavel"])]

    # Filtro por status
    if filtros.get("status"):
        status_filters = []
        for status in filtros["status"]:
            if status == "Ativo":
                status_filters.append((~df_filtrado["concluido"]) & (~df_filtrado["arquivado"]))
            elif status == "Concluído":
                status_filters.append(df_filtrado["concluido"])
            elif status == "Arquivado":
                status_filters.append(df_filtrado["arquivado"])

        if status_filters:
            df_filtrado = df_filtrado[pd.concat(status_filters, axis=1).any(axis=1)]

    # Filtro por tipo
    if filtros.get("tipo"):
        df_filtrado = df_filtrado[df_filtrado["tipo"].isin(filtros["tipo"])]

    # Filtro por prioridade
    if filtros.get("prioridade"):
        df_filtrado = df_filtrado[df_filtrado["prioridade"].isin(filtros["prioridade"])]

    # Filtro por faixa de data
    if filtros.get("data_inicio"):
        data_inicio = pd.Timestamp(filtros["data_inicio"])
        df_filtrado = df_filtrado[df_filtrado["data_fatal"] >= data_inicio]

    if filtros.get("data_fim"):
        data_fim = pd.Timestamp(filtros["data_fim"])
        df_filtrado = df_filtrado[df_filtrado["data_fatal"] <= data_fim]

    # Filtro por cliente (parcial, case-insensitive)
    if filtros.get("cliente"):
        cliente_search = filtros["cliente"].lower()
        df_filtrado = df_filtrado[
            df_filtrado["cliente"].str.lower().str.contains(cliente_search, na=False)
        ]

    # Filtro por número de processo (parcial)
    if filtros.get("numero_processo"):
        processo_search = filtros["numero_processo"]
        df_filtrado = df_filtrado[
            df_filtrado["processo"].str.contains(processo_search, na=False)
        ]

    return df_filtrado


def exibir_resumo_filtros(df_original: pd.DataFrame, df_filtrado: pd.DataFrame) -> None:
    """
    Exibe um resumo dos resultados dos filtros.
    """

    qtd_total = len(df_original)
    qtd_filtrada = len(df_filtrado)
    percentual = (qtd_filtrada / qtd_total * 100) if qtd_total > 0 else 0

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total de Prazos", qtd_total)

    with col2:
        st.metric("Resultado da Busca", qtd_filtrada)

    with col3:
        st.metric("Percentual", f"{percentual:.1f}%")

    if qtd_filtrada == 0:
        st.warning("⚠️ Nenhum prazo encontrado com os filtros selecionados. Tente ajustar os critérios.")
    else:
        st.success(f"✅ {qtd_filtrada} prazo{'s' if qtd_filtrada != 1 else ''} encontrado{'s' if qtd_filtrada != 1 else ''}")
