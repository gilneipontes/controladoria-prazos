import pandas as pd
import streamlit as st

def renderizar_filtros_sidebar(df_prazos, responsaveis, tipos, prioridades):
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

    st.session_state.filtros_ativos["responsavel"] = st.sidebar.multiselect(
        "👤 Responsável",
        options=responsaveis,
        default=st.session_state.filtros_ativos.get("responsavel", []),
        key="filtro_responsavel",
    )

    opcoes_status = ["Ativo", "Concluído", "Arquivado"]
    st.session_state.filtros_ativos["status"] = st.sidebar.multiselect(
        "✅ Status",
        options=opcoes_status,
        default=st.session_state.filtros_ativos.get("status", []),
        key="filtro_status",
    )

    st.session_state.filtros_ativos["tipo"] = st.sidebar.multiselect(
        "📋 Tipo",
        options=tipos,
        default=st.session_state.filtros_ativos.get("tipo", []),
        key="filtro_tipo",
    )

    st.session_state.filtros_ativos["prioridade"] = st.sidebar.multiselect(
        "🎯 Prioridade",
        options=prioridades,
        default=st.session_state.filtros_ativos.get("prioridade", []),
        key="filtro_prioridade",
    )

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

    st.session_state.filtros_ativos["cliente"] = st.sidebar.text_input(
        "🏢 Cliente",
        value=st.session_state.filtros_ativos.get("cliente", ""),
        key="filtro_cliente",
    )

    st.session_state.filtros_ativos["numero_processo"] = st.sidebar.text_input(
        "⚖️ Processo",
        value=st.session_state.filtros_ativos.get("numero_processo", ""),
        key="filtro_processo",
    )

    if st.sidebar.button("🔄 Limpar Filtros", use_container_width=True):
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

    return st.session_state.filtros_ativos


def aplicar_filtros(df_prazos, filtros):
    df_filtrado = df_prazos.copy()

    if filtros.get("responsavel"):
        df_filtrado = df_filtrado[df_filtrado["responsavel"].isin(filtros["responsavel"])]

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

    if filtros.get("tipo"):
        df_filtrado = df_filtrado[df_filtrado["tipo"].isin(filtros["tipo"])]

    if filtros.get("prioridade"):
        df_filtrado = df_filtrado[df_filtrado["prioridade"].isin(filtros["prioridade"])]

    if filtros.get("data_inicio"):
        df_filtrado = df_filtrado[df_filtrado["data_fatal"] >= pd.Timestamp(filtros["data_inicio"])]

    if filtros.get("data_fim"):
        df_filtrado = df_filtrado[df_filtrado["data_fatal"] <= pd.Timestamp(filtros["data_fim"])]

    if filtros.get("cliente"):
        df_filtrado = df_filtrado[df_filtrado["cliente"].str.lower().str.contains(filtros["cliente"].lower(), na=False)]

    if filtros.get("numero_processo"):
        df_filtrado = df_filtrado[df_filtrado["processo"].str.contains(filtros["numero_processo"], na=False)]

    return df_filtrado


def exibir_resumo_filtros(df_original, df_filtrado):
    qtd_total = len(df_original)
    qtd_filtrada = len(df_filtrado)
    percentual = (qtd_filtrada / qtd_total * 100) if qtd_total > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Prazos", qtd_total)
    col2.metric("Resultado da Busca", qtd_filtrada)
    col3.metric("Percentual", f"{percentual:.1f}%")

    if qtd_filtrada == 0:
        st.warning("⚠️ Nenhum prazo encontrado. Ajuste os filtros.")
    else:
        st.success(f"✅ {qtd_filtrada} prazo(s) encontrado(s)")
