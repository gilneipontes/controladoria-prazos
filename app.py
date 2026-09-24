"""
Controladoria Jurídica - VERSÃO FINAL COM 4 ABAS
"""
from __future__ import annotations

import datetime as dt
import hmac
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
from supabase import Client, create_client

# ===== CONFIG =====
st.set_page_config(page_title="Controladoria Jurídica", page_icon="⚖️", layout="wide")

TZ = ZoneInfo("America/Sao_Paulo")
TABELA_PRAZOS = "prazos"
TABELA_PROCESSOS = "processos"

RESPONSAVEIS = ["Dr. Gilnei", "Dra. Jéssica"]
TIPOS = ["Prazo Processual", "Data Fatal", "Tarefa Operacional", "Admin"]
PRIORIDADES = ["Baixa", "Normal", "Alta"]
ORDEM_PRIORIDADE = {"Alta": 0, "Normal": 1, "Baixa": 2}

FAIXAS = {
    "Vencido": "🔴 Vencido",
    "Hoje": "🟠 Vence hoje",
    "Até 3 dias": "🟡 Até 3 dias",
    "Até 7 dias": "🔵 Até 7 dias",
    "Futuro": "🟢 Mais de 7 dias",
    "Concluído": "✅ Concluído",
}

FERIADOS = np.array([
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-04-03", "2026-04-21",
    "2026-05-01", "2026-06-04", "2026-09-07", "2026-10-12", "2026-11-02",
    "2026-11-15", "2026-11-20", "2026-12-25",
], dtype="datetime64[D]")

COLUNAS_PRAZOS = [
    "id", "created_at", "tipo", "titulo", "processo", "cliente", "responsavel",
    "data_fatal", "data_interna", "prioridade", "descricao", "concluido", "concluido_em",
    "arquivado",
]

COLUNAS_PROCESSOS = ["id", "created_at", "numero", "cliente", "parte_contraria", "descricao", "ativo"]

ATALHOS = {
    "PET-INI": "Petição Inicial",
    "EMEND-INI": "Emenda à Petição Inicial",
    "RECL-TRAB": "Reclamação Trabalhista (Inicial)",
    "EMEND-TRAB": "Emenda à Reclamação Trabalhista",
    "CONT": "Contestação",
    "CONT-TRAB": "Contestação Trabalhista",
    "REPL": "Réplica à Contestação",
    "CONTR-DOC": "Manifestação sobre Documentos",
    "RECONV": "Reconvenção",
    "IMP-VALI": "Impugnação ao Valor da Causa",
    "EX-INCOMP": "Exceção de Incompetência",
    "EX-PREEXEC": "Exceção de Pré-Executividade",
    "SPEC-PROV": "Especificação de Provas",
    "ROL-TEST": "Rol de Testemunhas",
    "QUESITOS": "Quesitos para Perícia",
    "QUES-TRAB": "Quesitos Trabalhistas",
    "MANIFEST-LAUDO": "Manifestação sobre Laudo",
    "MANIF": "Manifestação",
    "MEMORIAIS": "Alegações Finais",
    "RAZOES-FIN": "Razões Finais",
    "APEL": "Apelação",
    "CONTR-APEL": "Contrarrazões de Apelação",
    "RO": "Recurso Ordinário",
    "CONTR-RO": "Contrarrazões de RO",
    "RR": "Recurso de Revista",
    "CONTR-RR": "Contrarrazões de RR",
    "AG-INST": "Agravo de Instrumento",
    "CONTR-AG": "Contraminuta de Agravo",
    "AG-INT": "Agravo Interno",
    "EMB-DECL": "Embargos de Declaração",
    "RESP": "Recurso Especial",
    "RE": "Recurso Extraordinário",
    "CUMP-SENT": "Cumprimento de Sentença",
    "IMP-CUMP": "Impugnação ao Cumprimento",
    "EX-EXEC": "Execução de Título",
    "EMB-EXEC": "Embargos à Execução",
    "AG-PET": "Agravo de Petição",
    "CONTR-AG-PET": "Contrarrazões de AG-PET",
    "IMP-CALC": "Impugnação aos Cálculos",
    "MANIFEST-CALC": "Manifestação sobre Cálculos",
    "INDIC-BENS": "Indicação de Bens",
    "PET-JUNT": "Petição de Juntada",
    "TERMO-AUD": "Data de Audiência",
    "ACORDO": "Termo de Acordo",
    "PED-SUSP": "Pedido de Suspensão",
    "PET-EXT": "Pedido de Extinção",
    "ALVARA": "Expedição de Alvará",
}

def hoje() -> dt.date:
    return dt.datetime.now(TZ).date()

def init_estado() -> None:
    st.session_state.setdefault("form_v", 0)
    st.session_state.setdefault("editor_v", 0)
    st.session_state.setdefault("aviso", None)
    st.session_state.setdefault("modal_aberta", False)
    st.session_state.setdefault("id_modal", None)
    st.session_state.setdefault("modo_modal", None)

def acesso_liberado() -> bool:
    senha_correta = st.secrets.get("APP_PASSWORD")
    if not senha_correta or st.session_state.get("autenticado"):
        return True
    st.title("⚖️ Controladoria Jurídica")
    with st.form("login"):
        senha = st.text_input("Senha de acesso", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            if hmac.compare_digest(senha.encode(), senha_correta.encode()):
                st.session_state.autenticado = True
                st.rerun()
            st.error("Senha incorreta.")
    return False

@st.cache_resource
def supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_data(ttl=60, show_spinner="Carregando prazos…")
def carregar_prazos() -> pd.DataFrame:
    resp = supabase().table(TABELA_PRAZOS).select("*").order("data_fatal").execute()
    df = pd.DataFrame(resp.data, columns=COLUNAS_PRAZOS)
    for col in ("data_fatal", "data_interna"):
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    df["concluido"] = df["concluido"].fillna(False).astype(bool)
    df["arquivado"] = df["arquivado"].fillna(False).astype(bool)
    return df

@st.cache_data(ttl=60, show_spinner="Carregando processos…")
def carregar_processos() -> pd.DataFrame:
    resp = supabase().table(TABELA_PROCESSOS).select("*").order("numero").execute()
    df = pd.DataFrame(resp.data, columns=COLUNAS_PROCESSOS)
    df["ativo"] = df["ativo"].fillna(True).astype(bool)
    return df

def inserir_prazo(registro: dict) -> None:
    supabase().table(TABELA_PRAZOS).insert(registro).execute()
    carregar_prazos.clear()

def inserir_processo(registro: dict) -> None:
    supabase().table(TABELA_PROCESSOS).insert(registro).execute()
    carregar_processos.clear()

def atualizar_campos(atualizacoes: dict[int, dict]) -> None:
    for id_prazo, campos in atualizacoes.items():
        if campos:
            supabase().table(TABELA_PRAZOS).update(campos).eq("id", id_prazo).execute()
    carregar_prazos.clear()

def atualizar_processo(id_processo: int, campos: dict) -> None:
    if campos:
        supabase().table(TABELA_PROCESSOS).update(campos).eq("id", id_processo).execute()
    carregar_processos.clear()

def arquivar_prazo(id_prazo: int) -> None:
    supabase().table(TABELA_PRAZOS).update({"arquivado": True}).eq("id", id_prazo).execute()
    carregar_prazos.clear()

def excluir_prazo(id_prazo: int) -> None:
    supabase().table(TABELA_PRAZOS).delete().eq("id", id_prazo).execute()
    carregar_prazos.clear()

def enriquecer(df: pd.DataFrame) -> pd.DataFrame:
    ref = np.datetime64(hoje())
    fatal = df["data_fatal"].values.astype("datetime64[D]")
    df["dias_corridos"] = (fatal - ref).astype(int)
    df["dias_uteis"] = np.busday_count(ref, fatal, holidays=FERIADOS)
    d = df["dias_corridos"]
    df["faixa"] = np.select(
        [df["concluido"], d < 0, d == 0, d <= 3, d <= 7],
        ["Concluído", "Vencido", "Hoje", "Até 3 dias", "Até 7 dias"],
        default="Futuro",
    )
    df["situacao"] = df["faixa"].map(FAIXAS)
    return df

def tabela_status(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Nenhum registro.")
        return

    df_vis = df.copy()
    df_vis["data_interna_fmt"] = df_vis["data_interna"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "")
    df_vis["data_fatal_fmt"] = df_vis["data_fatal"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "")

    colunas_vis = [
        "id", "situacao", "titulo", "processo", "cliente", "data_interna_fmt",
        "data_fatal_fmt", "dias_uteis", "tipo", "responsavel", "prioridade",
    ]
    vis = (
        df_vis.assign(_p=df_vis["prioridade"].map(ORDEM_PRIORIDADE))
        .sort_values(["data_fatal", "_p"])[colunas_vis]
        .set_index("id")
        .rename(columns={
            "data_interna_fmt": "Prazo Interno",
            "data_fatal_fmt": "Data Fatal",
            "situacao": "Situação",
            "titulo": "Título",
            "processo": "Processo",
            "cliente": "Cliente",
            "dias_uteis": "D.Úteis",
            "tipo": "Tipo",
            "responsavel": "Responsável",
            "prioridade": "Prioridade"
        })
    )

    st.dataframe(vis, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("⚙️ Gerenciar Prazo")
    
    df_ativos = df[~df["arquivado"]]
    if df_ativos.empty:
        st.info("Nenhum prazo ativo.")
        return

    col1, col2 = st.columns([2, 1])
    id_sel = col1.selectbox(
        "Selecione:",
        options=df_ativos["id"].values,
        format_func=lambda x: f"{df_ativos[df_ativos['id'] == x]['cliente'].values[0]} | {df_ativos[df_ativos['id'] == x]['titulo'].values[0]} | {df_ativos[df_ativos['id'] == x]['data_fatal'].values[0].strftime('%d/%m/%Y')}",
        key="sel_prazo"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("✏️ Editar", use_container_width=True, type="secondary"):
            st.session_state.id_modal = id_sel
            st.session_state.modo_modal = "editar"
            st.session_state.modal_aberta = True
            st.rerun()
    
    with c2:
        if st.button("📦 Arquivar", use_container_width=True, type="secondary"):
            st.session_state.id_modal = id_sel
            st.session_state.modo_modal = "confirmar_arquivar"
            st.session_state.modal_aberta = True
            st.rerun()
    
    with c3:
        if st.button("❌ Excluir", use_container_width=True, type="secondary"):
            st.session_state.id_modal = id_sel
            st.session_state.modo_modal = "confirmar_excluir"
            st.session_state.modal_aberta = True
            st.rerun()

    if st.session_state.modal_aberta and st.session_state.id_modal:
        id_prazo = st.session_state.id_modal
        prazo = df[df["id"] == id_prazo].iloc[0]
        
        st.divider()
        st.subheader(f"⚙️ {prazo['titulo']}")
        
        if st.session_state.modo_modal == "editar":
            with st.form(f"form_{id_prazo}"):
                col1, col2 = st.columns(2)
                nova_fatal = col1.date_input("Data Fatal", value=prazo["data_fatal"], format="DD/MM/YYYY")
                nova_interna = col2.date_input("Prazo Interno", value=prazo["data_interna"], format="DD/MM/YYYY")
                
                if nova_fatal:
                    dias = (np.datetime64(nova_fatal) - np.datetime64(hoje())).astype(int)
                    if dias < 0:
                        sit = "🔴 Vencido"
                    elif dias == 0:
                        sit = "🟠 Hoje"
                    elif dias <= 3:
                        sit = "🟡 Até 3d"
                    elif dias <= 7:
                        sit = "🔵 Até 7d"
                    else:
                        sit = "🟢 Futuro"
                    st.info(f"Nova Situação: {sit}")
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                        atualizar_campos({id_prazo: {"data_fatal": nova_fatal.isoformat(), "data_interna": nova_interna.isoformat() if nova_interna else None}})
                        st.session_state.aviso = "✅ Atualizado!"
                        st.session_state.modal_aberta = False
                        st.session_state.editor_v += 1
                        st.rerun()
                with c2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.modal_aberta = False
                        st.rerun()
        
        elif st.session_state.modo_modal == "confirmar_arquivar":
            st.warning("⚠️ Tem certeza que deseja arquivar?")
            st.write(f"**Cliente:** {prazo['cliente']}")
            st.write(f"**Título (Prazo):** {prazo['titulo']}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ SIM, Arquivar", use_container_width=True, type="primary"):
                    arquivar_prazo(id_prazo)
                    carregar_prazos.clear()
                    carregar_processos.clear()
                    st.session_state.aviso = "✅ Arquivado!"
                    st.session_state.modal_aberta = False
                    st.session_state.editor_v += 1
                    st.rerun()
            with c2:
                if st.button("❌ NÃO, Cancelar", use_container_width=True):
                    st.session_state.modal_aberta = False
                    st.rerun()
        
        elif st.session_state.modo_modal == "confirmar_excluir":
            st.error("🔴 ATENÇÃO: Excluir é permanente!")
            st.write(f"**Cliente:** {prazo['cliente']}")
            st.write(f"**Título (Prazo):** {prazo['titulo']}")
            st.caption("⚠️ Esta ação NÃO pode ser desfeita!")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🗑️ SIM, Excluir", use_container_width=True, type="primary"):
                    excluir_prazo(id_prazo)
                    carregar_prazos.clear()
                    carregar_processos.clear()
                    st.session_state.aviso = "✅ Prazo excluído!"
                    st.session_state.modal_aberta = False
                    st.session_state.editor_v += 1
                    st.rerun()
            with c2:
                if st.button("❌ NÃO, Cancelar", use_container_width=True):
                    st.session_state.modal_aberta = False
                    st.rerun()

def sidebar_novo_prazo(processos_df: pd.DataFrame) -> None:
    st.subheader("📋 Novo Prazo")
    v = st.session_state.form_v
    
    processos_ativos = processos_df[processos_df["ativo"]].sort_values("numero")
    
    st.write("**Nº Processo ***")
    busca = st.text_input(
        "Digite o número do processo",
        value="",
        placeholder="Ex: 5014993 ou 5028905",
        key=f"busca_proc_{v}",
        label_visibility="collapsed"
    )
    
    processo = None
    cliente = ""
    parte_adversaria = ""
    
    if busca:
        processos_filtrados = processos_ativos[
            processos_ativos["numero"].str.contains(busca, case=False)
        ]
        
        if not processos_filtrados.empty:
            st.caption(f"📋 {len(processos_filtrados)} processo(s) encontrado(s):")
            
            processo = st.selectbox(
                "Selecione:",
                options=processos_filtrados["numero"].values,
                index=0 if len(processos_filtrados) > 0 else None,
                label_visibility="collapsed",
                key=f"sel_proc_{v}"
            )
        else:
            st.warning(f"❌ Nenhum processo encontrado com '{busca}'")
    
    if processo:
        cliente = processos_ativos[processos_ativos["numero"] == processo]["cliente"].values[0]
        parte_adversaria = processos_ativos[processos_ativos["numero"] == processo]["parte_contraria"].values[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Cliente**")
            st.markdown(f"### **{cliente}**")
        with col2:
            st.markdown(f"**Parte Adversária**")
            st.markdown(f"### **{parte_adversaria}**")
        
        st.success(f"✅ Processo selecionado: **{processo}**")
    
    with st.form(f"cad_{v}"):
        tipo = st.selectbox("Tipo *", TIPOS, key=f"t_{v}")
        
        st.write("**Título ***")
        busca_titulo = st.text_input(
            "Digite para filtrar atalhos jurídicos",
            value="",
            placeholder="Ex: PET, CONT, MANIF...",
            key=f"busca_{v}",
            label_visibility="collapsed"
        )
        
        titulo = ""
        if busca_titulo:
            atalhos_filtrados = {k: v for k, v in ATALHOS.items() if busca_titulo.upper() in k}
            if atalhos_filtrados:
                titulo_atalho = st.selectbox(
                    "Atalhos encontrados:",
                    options=list(atalhos_filtrados.keys()),
                    format_func=lambda x: f"{x} — {atalhos_filtrados[x]}",
                    key=f"ta_{v}",
                    label_visibility="collapsed"
                )
                titulo = atalhos_filtrados[titulo_atalho]
            else:
                st.warning("Nenhum atalho encontrado!")
        else:
            st.caption("👉 Digite acima para ver os atalhos disponíveis")
        
        if titulo:
            st.caption(f"📌 Selecionado: **{titulo}**")
        
        responsavel = st.radio("Responsável *", RESPONSAVEIS, horizontal=True, key=f"r_{v}")
        c1, c2 = st.columns(2)
        data_interna = c1.date_input("Prazo Interno", format="DD/MM/YYYY", key=f"i_{v}")
        data_fatal = c2.date_input("Data Fatal *", format="DD/MM/YYYY", key=f"f_{v}")
        
        prioridade = st.select_slider("Prioridade", PRIORIDADES, value="Normal", key=f"pr_{v}")
        st.text_area("Observações", key=f"d_{v}")
        
        if st.form_submit_button("💾 Salvar", type="primary"):
            if not processo or not data_fatal or not titulo:
                st.error("Preencha processo, data fatal e título!")
            elif data_interna and data_interna > data_fatal:
                st.error("Prazo interno deve ser ≤ data fatal!")
            else:
                inserir_prazo({
                    "tipo": tipo,
                    "titulo": titulo,
                    "processo": processo,
                    "cliente": cliente,
                    "responsavel": responsavel,
                    "data_fatal": data_fatal.isoformat(),
                    "data_interna": data_interna.isoformat() if data_interna else None,
                    "prioridade": prioridade,
                    "descricao": st.session_state.get(f"d_{v}") or None,
                    "arquivado": False,
                })
                st.session_state.aviso = f"✅ Prazo salvo!"
                st.session_state.form_v += 1
                st.rerun()

def gerenciar_processos(df_processos: pd.DataFrame, df_prazos: pd.DataFrame) -> None:
    if df_processos.empty:
        st.info("Nenhum processo cadastrado.")
        return
    
    st.subheader("📋 Processos Cadastrados")
    
    processos_ativos = df_processos[df_processos["ativo"]].copy()
    
    if processos_ativos.empty:
        st.info("Nenhum processo ativo.")
        return
    
    # ===== REMOVER DUPLICATAS =====
    processos_unicos = processos_ativos.drop_duplicates(subset=["numero"], keep="first").sort_values("numero")
    
    # ===== EXPANDIR CADA PROCESSO =====
    for idx, proc in processos_unicos.iterrows():
        todos_prazos = df_prazos[df_prazos["processo"] == proc["numero"]]
        prazos_abertos = todos_prazos[~todos_prazos["concluido"] & ~todos_prazos["arquivado"]]
        prazos_concluidos = todos_prazos[todos_prazos["concluido"]]
        prazos_arquivados = todos_prazos[todos_prazos["arquivado"]]
        
        qtd_abertos = len(prazos_abertos)
        qtd_concluidos = len(prazos_concluidos)
        qtd_arquivados = len(prazos_arquivados)
        
        titulo_expander = f"**{proc['numero']}** | {proc['cliente']} | 📋 {qtd_abertos}📋 ✅{qtd_concluidos} 📦{qtd_arquivados}"
        
        with st.expander(titulo_expander, expanded=False):
            
            # ===== INFORMAÇÕES DO PROCESSO (COLAPSÁVEL) =====
            with st.expander("📋 Informações & Edição do Processo", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Informações:**")
                    st.write(f"🔹 **Nº Processo:** `{proc['numero']}`")
                    st.write(f"👤 **Cliente:** {proc['cliente']}")
                    st.write(f"⚔️ **Parte Adversária:** {proc['parte_contraria']}")
                    if proc["descricao"]:
                        st.write(f"📌 **Descrição:** {proc['descricao']}")
                
                with col2:
                    st.markdown("**Editar:**")
                    with st.form(f"edit_{proc['id']}", clear_on_submit=False):
                        novo_cliente = st.text_input("Cliente", value=proc["cliente"], key=f"cli_{proc['id']}")
                        nova_parte = st.text_input("Parte Adversária", value=proc["parte_contraria"], key=f"parte_{proc['id']}")
                        nova_desc = st.text_area("Descrição", value=proc["descricao"] or "", height=100, key=f"desc_{proc['id']}")
                        
                        if st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True):
                            atualizar_processo(proc["id"], {
                                "cliente": novo_cliente,
                                "parte_contraria": nova_parte,
                                "descricao": nova_desc or None
                            })
                            st.success("✅ Processo atualizado!")
                            st.rerun()
            
            # ===== ABAS DOS PRAZOS =====
            st.divider()
            
            tab_abertos, tab_concluidos, tab_arquivados = st.tabs([
                f"📋 Em Aberto ({qtd_abertos})",
                f"✅ Concluídos ({qtd_concluidos})",
                f"📦 Arquivados ({qtd_arquivados})"
            ])
            
            # ===== ABA: EM ABERTO =====
            with tab_abertos:
                if prazos_abertos.empty:
                    st.info("✅ Nenhum prazo em aberto!")
                else:
                    prazos_abertos = enriquecer(prazos_abertos).sort_values("data_fatal")
                    
                    for p_idx, prazo in prazos_abertos.iterrows():
                        mostra_card_prazo(prazo)
            
            # ===== ABA: CONCLUÍDOS =====
            with tab_concluidos:
                if prazos_concluidos.empty:
                    st.info("Nenhum prazo concluído ainda.")
                else:
                    prazos_concluidos = enriquecer(prazos_concluidos).sort_values("data_fatal", ascending=False)
                    
                    for p_idx, prazo in prazos_concluidos.iterrows():
                        mostra_card_prazo(prazo)
            
            # ===== ABA: ARQUIVADOS =====
            with tab_arquivados:
                if prazos_arquivados.empty:
                    st.info("Nenhum prazo arquivado.")
                else:
                    prazos_arquivados = enriquecer(prazos_arquivados).sort_values("data_fatal", ascending=False)
                    
                    for p_idx, prazo in prazos_arquivados.iterrows():
                        mostra_card_prazo(prazo)

def mostra_card_prazo(prazo) -> None:
    """Mostra um card formatado de um prazo"""
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([0.8, 2, 1.2, 0.8])
        
        # ===== SITUAÇÃO =====
        with col1:
            st.markdown(f"### {prazo['situacao']}")
        
        # ===== TÍTULO E RESPONSÁVEL =====
        with col2:
            st.markdown(f"**{prazo['titulo']}**")
            st.caption(f"👤 {prazo['responsavel']}")
        
        # ===== DATAS =====
        with col3:
            data_interna_str = prazo['data_interna'].strftime("%d/%m") if pd.notna(prazo['data_interna']) else "—"
            data_fatal_str = prazo['data_fatal'].strftime("%d/%m/%Y")
            st.text(f"📌 {data_interna_str}\n🔚 {data_fatal_str}")
        
        # ===== PRIORIDADE =====
        with col4:
            prioridade_emoji = {"Alta": "🔴", "Normal": "🟡", "Baixa": "🟢"}
            emoji = prioridade_emoji.get(prazo['prioridade'], '⚪')
            st.markdown(f"**{emoji}**\n{prazo['prioridade']}")
        
        # ===== OBSERVAÇÕES =====
        if prazo['descricao']:
            st.divider()
            st.markdown(f"**📝 Observações:**")
            st.caption(prazo['descricao'])

def main() -> None:
    init_estado()
    if not acesso_liberado():
        st.stop()

    try:
        df_prazos = carregar_prazos()
        df_processos = carregar_processos()
    except Exception as exc:
        st.error(f"Erro: {exc}")
        st.stop()

    with st.sidebar:
        st.title("⚖️ Controladoria")
        aba = st.radio("Opção:", ["Novo Prazo", "Novo Processo", "Dashboard"], key="aba")
        st.divider()
        
        if st.button("🔄 Recarregar Dados", use_container_width=True):
            carregar_prazos.clear()
            carregar_processos.clear()
            st.rerun()
        
        st.divider()
        
        if aba == "Novo Prazo":
            sidebar_novo_prazo(df_processos)
        elif aba == "Novo Processo":
            st.subheader("⚖️ Novo Processo")
            v = st.session_state.form_v
            with st.form("proc"):
                numero = st.text_input("Nº CNJ *", placeholder="0000000-00.0000.0.00.0000", key=f"pnumero_{v}")
                cliente = st.text_input("Cliente *", key=f"pcliente_{v}")
                parte = st.text_input("Parte Adversária *", key=f"pparte_{v}")
                descricao = st.text_area("Descrição", key=f"pdesc_{v}")
                if st.form_submit_button("Salvar", type="primary"):
                    if numero and cliente and parte:
                        inserir_processo({"numero": numero, "cliente": cliente, "parte_contraria": parte, "descricao": descricao or None, "ativo": True})
                        st.success("✅ Salvo!")
                        st.session_state.form_v += 1
                        st.rerun()
                    else:
                        st.error("Preencha todos!")
        else:
            st.subheader("📊 Dashboard")
            if not df_prazos.empty:
                df_prazos = enriquecer(df_prazos)
                pend = df_prazos[~df_prazos["concluido"] & ~df_prazos["arquivado"]]
                col1, col2, col3 = st.columns(3)
                col1.metric("🔴 Vencidos", len(pend[pend["faixa"] == "Vencido"]))
                col2.metric("🟠 Hoje", len(pend[pend["faixa"] == "Hoje"]))
                col3.metric("📋 Pendentes", len(pend))

    st.title("⚖️ Controladoria Jurídica")
    st.caption(f"Hoje: {hoje():%d/%m/%Y}")

    if st.session_state.aviso:
        st.toast(st.session_state.aviso)
        st.session_state.aviso = None

    if df_prazos.empty:
        st.info("Nenhum prazo.")
        st.stop()

    df_prazos = enriquecer(df_prazos)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Prazos", "📋 Relatório", "🔄 Desarquivar", "📋 Processos"])
    
    with tab1:
        tabela_status(df_prazos[~df_prazos["arquivado"]])
    
    with tab2:
        arquivados = df_prazos[df_prazos["arquivado"]]
        if arquivados.empty:
            st.info("Nenhum arquivado.")
        else:
            st.write(f"**{len(arquivados)} prazos arquivados:**")
            st.dataframe(arquivados[["titulo", "data_fatal", "responsavel"]], use_container_width=True, hide_index=True)
    
    with tab3:
        st.subheader("🔄 Desarquivar Prazos")
        arquivados = df_prazos[df_prazos["arquivado"]]
        
        if arquivados.empty:
            st.info("Nenhum prazo arquivado.")
        else:
            st.write(f"**{len(arquivados)} prazos arquivados:**")
            
            col1, col2 = st.columns([2, 1])
            id_des = col1.selectbox(
                "Selecione para desarquivar:",
                options=arquivados["id"].values,
                format_func=lambda x: f"{arquivados[arquivados['id'] == x]['cliente'].values[0]} | {arquivados[arquivados['id'] == x]['titulo'].values[0]} | {arquivados[arquivados['id'] == x]['data_fatal'].values[0].strftime('%d/%m/%Y')}",
                key="sel_des"
            )
            
            if col2.button("🔄 Desarquivar", use_container_width=True, type="secondary"):
                supabase().table(TABELA_PRAZOS).update({"arquivado": False}).eq("id", id_des).execute()
                carregar_prazos.clear()
                st.success("✅ Prazo restaurado!")
                st.rerun()
    
    with tab4:
        gerenciar_processos(df_processos, df_prazos)

if __name__ == "__main__":
    main()
