"""
Controladoria Jurídica - VERSÃO COMPLETA
SEMANA 1 + Aba Audiências (com auto-criação de Prazos Admin)
"""
# ============================================
# CONTROLADORIA JURÍDICA - COMPLETA
# Versão: 5.0 - COM AUDIÊNCIAS - 26/09/2026
# ✅ SEMANA 1 (PASSO 2-6)
# ✅ Dashboard KPIs
# ✅ Google Calendar Sync (opcional)
# ✅ Aba Audiências (NOVO!)
# ✅ Auto-criação de Prazos Admin
# ============================================

from __future__ import annotations

import datetime as dt
import hmac
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
from supabase import Client, create_client

# ===== IMPORTS PARA GOOGLE CALENDAR =====
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except ImportError:
    Credentials = build = None

# ===== CONFIG =====
st.set_page_config(page_title="Controladoria Jurídica", page_icon="⚖️", layout="wide")

TZ = ZoneInfo("America/Sao_Paulo")
TABELA_PRAZOS = "prazos"
TABELA_PROCESSOS = "processos"
TABELA_AUDIENCIAS = "audiencias"

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

FORMATOS_AUDIENCIA = ["Presencial", "Virtual"]
TIPOS_AUDIENCIA = ["Inicial", "Continuação", "Sentença", "Outra"]
STATUS_AUDIENCIA = ["Agendada", "Realizada", "Cancelada"]

FERIADOS = np.array([
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-04-03", "2026-04-21",
    "2026-05-01", "2026-06-04", "2026-09-07", "2026-10-12", "2026-11-02",
    "2026-11-15", "2026-11-20", "2026-12-25",
    "2027-01-01", "2027-02-08", "2027-02-09", "2027-03-26", "2027-04-21",
    "2027-05-01", "2027-06-03", "2027-09-07", "2027-10-12", "2027-11-02",
    "2027-11-15", "2027-11-20", "2027-12-25",
    "2028-01-01", "2028-02-28", "2028-03-01", "2028-04-14", "2028-04-21",
    "2028-05-01", "2028-05-30", "2028-09-07", "2028-10-12", "2028-11-02",
    "2028-11-15", "2028-11-20", "2028-12-25",
    "2026-12-20", "2026-12-21", "2026-12-22", "2026-12-23", "2026-12-24", "2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31",
    "2027-01-04", "2027-01-05", "2027-01-06", "2027-01-07", "2027-01-08", "2027-01-11", "2027-01-12", "2027-01-13", "2027-01-14", "2027-01-15", "2027-01-18", "2027-01-19", "2027-01-20",
    "2026-09-20", "2027-09-20", "2028-09-20",
], dtype="datetime64[D]")

COLUNAS_PRAZOS = [
    "id", "created_at", "tipo", "titulo", "processo", "cliente", "responsavel",
    "data_fatal", "data_interna", "prioridade", "descricao", "concluido", "concluido_em",
    "arquivado",
]

COLUNAS_PROCESSOS = ["id", "created_at", "numero", "cliente", "parte_contraria", "descricao", "ativo"]

COLUNAS_AUDIENCIAS = [
    "id", "created_at", "processo", "autor", "reu", "sala", "data_audiencia",
    "hora_inicio", "hora_termino", "formato", "tipo", "status", "observacoes", "responsavel"
]

ATALHOS = {
    "PET-INI": "Petição Inicial",
    "EMEND-INI": "Emenda à Petição Inicial",
    "CONT": "Contestação",
    "REPL": "Réplica à Contestação",
    "MANIF": "Manifestação",
    "APEL": "Apelação",
    "AGR": "Agravo",
    "EXECUCAO": "Execução",
    "HABEAS": "Habeas Corpus",
}

# ===== SUPABASE =====
@st.cache_resource
def init_supabase() -> Client:
    # Tentar múltiplas opções de chave
    chave = None
    if "supabase_key" in st.secrets:
        chave = st.secrets["supabase_key"]
    elif "supabase_anon_key" in st.secrets:
        chave = st.secrets["supabase_anon_key"]
    elif "SUPABASE_ANON_KEY" in st.secrets:
        chave = st.secrets["SUPABASE_ANON_KEY"]
    else:
        st.error("❌ Chave do Supabase não encontrada nos secrets. Verifique a configuração no Streamlit Cloud.")
        st.stop()

    return create_client(
        "https://vqlwhgpldiahglqfeqnrc.supabase.co",
        chave
    )

supabase = init_supabase()

# ===== SESSION STATE =====
st.session_state.setdefault("form_v", 0)
st.session_state.setdefault("editor_v", 0)
st.session_state.setdefault("aviso", "")

# ===== DIAS ÚTEIS =====
def dias_uteis_restantes(data_fatal: dt.date) -> int:
    hoje = dt.date.today()
    if data_fatal < hoje:
        return -1
    return int(np.busday_count(hoje, data_fatal, holidays=FERIADOS))

# ===== CARREGAR DADOS =====
@st.cache_data(ttl=60)
def carregar_prazos() -> pd.DataFrame:
    try:
        resp = supabase.table(TABELA_PRAZOS).select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            df["data_fatal"] = pd.to_datetime(df["data_fatal"], utc=True).dt.date
            df["data_interna"] = pd.to_datetime(df["data_interna"], utc=True, errors="coerce").dt.date
            df["concluido_em"] = pd.to_datetime(df["concluido_em"], utc=True, errors="coerce").dt.date
            return df
    except Exception as e:
        st.error(f"Erro ao carregar prazos: {e}")
    return pd.DataFrame(columns=COLUNAS_PRAZOS)

@st.cache_data(ttl=60)
def carregar_processos() -> pd.DataFrame:
    try:
        resp = supabase.table(TABELA_PROCESSOS).select("*").execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar processos: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=60)
def carregar_audiencias() -> pd.DataFrame:
    try:
        resp = supabase.table(TABELA_AUDIENCIAS).select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            df["data_audiencia"] = pd.to_datetime(df["data_audiencia"], utc=True).dt.date
            return df
    except Exception as e:
        st.error(f"Erro ao carregar audiências: {e}")
    return pd.DataFrame(columns=COLUNAS_AUDIENCIAS)

# ===== ENRIQUECER =====
def enriquecer(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    
    df = df.copy()
    hoje = dt.date.today()
    
    def calcula_faixa(row):
        if row["concluido"]:
            return "Concluído"
        if row["data_fatal"] < hoje:
            return "Vencido"
        dias = (row["data_fatal"] - hoje).days
        if dias == 0:
            return "Hoje"
        elif dias <= 3:
            return "Até 3 dias"
        elif dias <= 7:
            return "Até 7 dias"
        else:
            return "Futuro"
    
    df["faixa"] = df.apply(calcula_faixa, axis=1)
    df["dias_uteis"] = df["data_fatal"].apply(dias_uteis_restantes)
    return df

# ===== GOOGLE CALENDAR SYNC =====
def sincronizar_google_calendar(prazo: dict, action: str = "create") -> bool:
    if not build or not st.secrets.get("google_calendar_json"):
        return False
    
    try:
        import json
        creds_dict = json.loads(st.secrets["google_calendar_json"])
        creds = Credentials.from_service_account_info(creds_dict)
        service = build("calendar", "v3", credentials=creds)
        
        evento = {
            "summary": f"⚖️ {prazo['titulo']} - {prazo['cliente']}",
            "description": f"Processo: {prazo['processo']}\nResponsável: {prazo['responsavel']}\nPrioridade: {prazo['prioridade']}",
            "start": {"date": prazo["data_fatal"].isoformat()},
            "end": {"date": (prazo["data_fatal"] + dt.timedelta(days=1)).isoformat()},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "notification", "minutes": 24 * 60 * 3}]
            }
        }
        
        if action == "create":
            service.events().insert(calendarId="primary", body=evento).execute()
        
        return True
    except Exception as e:
        return False

# ===== INSERIR PRAZO =====
def inserir_prazo(dados: dict) -> None:
    try:
        supabase.table(TABELA_PRAZOS).insert(dados).execute()
        carregar_prazos.clear()
        
        prazo_novo = {
            "titulo": dados["titulo"],
            "cliente": dados["cliente"],
            "responsavel": dados["responsavel"],
            "processo": dados["processo"],
            "prioridade": dados["prioridade"],
            "data_fatal": dt.datetime.fromisoformat(dados["data_fatal"]).date()
        }
        sincronizar_google_calendar(prazo_novo, "create")
        
    except Exception as e:
        st.error(f"Erro ao inserir prazo: {e}")

# ===== INSERIR AUDIÊNCIA =====
def inserir_audiencia(dados: dict) -> None:
    """Insere audiência E cria prazo admin automaticamente"""
    try:
        supabase.table(TABELA_AUDIENCIAS).insert(dados).execute()
        carregar_audiencias.clear()
        
        # 🎯 AUTO-CRIAR PRAZO ADMINISTRATIVO
        prazo_admin = {
            "tipo": "Admin",
            "titulo": f"📅 Audiência - Processo {dados['processo']}",
            "processo": dados["processo"],
            "cliente": dados.get("autor", "Cliente"),
            "responsavel": dados["responsavel"],
            "data_fatal": dados["data_audiencia"],
            "data_interna": None,
            "prioridade": "Alta",
            "descricao": f"Sala: {dados['sala']} | Hora: {dados['hora_inicio']}",
            "concluido": False,
            "arquivado": False,
        }
        
        # Inserir prazo
        supabase.table(TABELA_PRAZOS).insert(prazo_admin).execute()
        carregar_prazos.clear()
        
    except Exception as e:
        st.error(f"Erro ao inserir audiência: {e}")

# ===== ATUALIZAR CAMPOS =====
def atualizar_campos(updates: dict[int, dict]) -> None:
    try:
        for prazo_id, campos in updates.items():
            supabase.table(TABELA_PRAZOS).update(campos).eq("id", prazo_id).execute()
        carregar_prazos.clear()
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")

# ===== ARQUIVAR PRAZO =====
def arquivar_prazo(prazo_id: int) -> None:
    try:
        supabase.table(TABELA_PRAZOS).update({"arquivado": True}).eq("id", prazo_id).execute()
        carregar_prazos.clear()
    except Exception as e:
        st.error(f"Erro ao arquivar: {e}")

# ===== EXCLUIR PRAZO =====
def excluir_prazo(prazo_id: int) -> None:
    try:
        supabase.table(TABELA_PRAZOS).delete().eq("id", prazo_id).execute()
        carregar_prazos.clear()
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")

# ===== DASHBOARD KPIs =====
def dashboard_kpis(df_prazos: pd.DataFrame) -> None:
    st.markdown("# 📊 DASHBOARD - KPIs & PERFORMANCE")
    st.divider()
    
    if df_prazos.empty:
        st.info("📭 Nenhum prazo registrado ainda")
        return
    
    df_prazos = enriquecer(df_prazos)
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_prazos = len(df_prazos)
    prazos_concluidos = len(df_prazos[df_prazos["concluido"]])
    taxa_sucesso = (prazos_concluidos / total_prazos * 100) if total_prazos > 0 else 0
    prazos_ativos = len(df_prazos[~df_prazos["concluido"] & ~df_prazos["arquivado"]])
    
    with col1:
        st.metric("📋 Total de Prazos", total_prazos)
    with col2:
        st.metric("✅ Concluídos", prazos_concluidos)
    with col3:
        st.metric("⏳ Ativos", prazos_ativos)
    with col4:
        st.metric("🎯 Taxa de Sucesso", f"{taxa_sucesso:.1f}%")
    
    st.divider()
    
    st.markdown("## 👥 Produtividade por Responsável")
    
    df_ativos = df_prazos[~df_prazos["concluido"] & ~df_prazos["arquivado"]]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📌 Prazos Ativos")
        for responsavel in RESPONSAVEIS:
            count = len(df_ativos[df_ativos["responsavel"] == responsavel])
            st.write(f"**{responsavel}:** {count} prazo(s)")
    
    with col2:
        st.markdown("### ✅ Prazos Concluídos")
        for responsavel in RESPONSAVEIS:
            count = len(df_prazos[(df_prazos["responsavel"] == responsavel) & (df_prazos["concluido"])])
            st.write(f"**{responsavel}:** {count} prazo(s)")
    
    st.divider()
    
    st.markdown("## ⏱️ Performance - Prazos no Prazo vs Atrasados")
    
    df_concluidos = df_prazos[df_prazos["concluido"]].copy()
    
    if not df_concluidos.empty:
        no_prazo = len(df_concluidos[df_concluidos["concluido_em"] <= df_concluidos["data_fatal"]])
        atrasados = len(df_concluidos) - no_prazo
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🎯 Concluído no Prazo", no_prazo)
        with col2:
            st.metric("⚠️ Concluído com Atraso", atrasados)
        
        if len(df_concluidos) > 0:
            pct_no_prazo = (no_prazo / len(df_concluidos)) * 100
            st.progress(pct_no_prazo / 100, text=f"{pct_no_prazo:.1f}% cumprimento de prazos")
    
    st.divider()
    
    st.markdown("## 🚨 Distribuição por Urgência")
    
    vencidos = len(df_ativos[df_ativos["faixa"] == "Vencido"])
    hoje_prazos = len(df_ativos[df_ativos["faixa"] == "Hoje"])
    ate_3_dias = len(df_ativos[df_ativos["faixa"] == "Até 3 dias"])
    ate_7_dias = len(df_ativos[df_ativos["faixa"] == "Até 7 dias"])
    futuro = len(df_ativos[df_ativos["faixa"] == "Futuro"])
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("🔴 Vencidos", vencidos)
    with col2:
        st.metric("🟠 Hoje", hoje_prazos)
    with col3:
        st.metric("🟡 Até 3d", ate_3_dias)
    with col4:
        st.metric("🔵 Até 7d", ate_7_dias)
    with col5:
        st.metric("🟢 Futuro", futuro)

# ===== TABELA DE STATUS =====
def tabela_status(df: pd.DataFrame, prefix: str, filtro_responsavel: str = None) -> None:
    if df.empty:
        st.info("📭 Nenhum prazo encontrado")
        return
    
    df = enriquecer(df)
    
    if filtro_responsavel and filtro_responsavel != "Todos":
        df = df[df["responsavel"] == filtro_responsavel]
        if df.empty:
            st.info(f"📭 Nenhum prazo para {filtro_responsavel}")
            return
    
    df = df.sort_values("data_fatal")
    
    for _, prazo in df.iterrows():
        id_prazo = prazo["id"]
        modal_key_aberta = f"modal_{prefix}_{id_prazo}_aberta"
        modal_key_modo = f"modal_{prefix}_{id_prazo}_modo"
        
        st.session_state.setdefault(modal_key_aberta, False)
        st.session_state.setdefault(modal_key_modo, "detalhes")
        
        col1, col2, col3, col4, col5, col6 = st.columns([1.5, 2, 1.2, 1, 1.2, 0.8])
        
        with col1:
            faixa_emoji = FAIXAS.get(prazo["faixa"], "❓")
            st.markdown(f"**{faixa_emoji}**")
        
        with col2:
            st.markdown(f"**{prazo['titulo']}**  \n_{prazo['cliente']}_")
        
        with col3:
            st.markdown(f"**{prazo['data_fatal'].strftime('%d/%m/%Y')}**")
        
        with col4:
            dias = prazo.get("dias_uteis", 0)
            if dias >= 0:
                st.markdown(f"**{dias}d**")
            else:
                st.markdown("⏰")
        
        with col5:
            st.markdown(f"_{prazo['responsavel']}_")
        
        with col6:
            if st.button("👁️", key=f"btn_view_{prefix}_{id_prazo}", use_container_width=True):
                st.session_state[modal_key_aberta] = not st.session_state[modal_key_aberta]
                st.rerun()
        
        if st.session_state[modal_key_aberta]:
            st.divider()
            st.subheader(f"⚙️ {prazo['titulo']}")
            
            if st.session_state.get(modal_key_modo) == "detalhes":
                st.info("📋 Detalhes Completos")
                col1, col2 = st.columns(2)
                col1.write(f"**Cliente:** {prazo['cliente']}")
                col2.write(f"**Processo:** {prazo['processo']}")
                col1.write(f"**Responsável:** {prazo['responsavel']}")
                col2.write(f"**Prioridade:** {prazo['prioridade']}")
                
                st.divider()
                col_fechar = st.columns([3, 1])
                with col_fechar[1]:
                    if st.button("🔙 Fechar", use_container_width=True, key=f"btn_fechar_{prefix}_{id_prazo}"):
                        st.session_state[modal_key_aberta] = False
                        st.rerun()

# ===== MAIN =====
def main():
    st.markdown("# ⚖️ CONTROLADORIA JURÍDICA")
    
    df_prazos = carregar_prazos()
    df_processos = carregar_processos()
    df_audiencias = carregar_audiencias()
    
    if st.session_state.aviso:
        st.success(st.session_state.aviso)
        st.session_state.aviso = ""
    
    with st.sidebar:
        st.divider()
        sidebar_novo_prazo(df_processos)
    
    tab_dashboard, tab_ativos, tab_concluidos, tab_processos, tab_audiencias = st.tabs([
        "📊 Dashboard",
        "📌 Ativos",
        "✅ Concluídos",
        "📋 Processos",
        "📅 Audiências"
    ])
    
    with tab_dashboard:
        dashboard_kpis(df_prazos)
    
    with tab_ativos:
        st.markdown("## 📌 PRAZOS ATIVOS")
        st.divider()
        
        st.session_state.setdefault("filtro_tab1", "Todos")
        filtro_tab1 = st.selectbox("Filtrar por responsável", ["Todos"] + RESPONSAVEIS, key="select_filtro_tab1", index=0)
        
        df_ativos = df_prazos[~df_prazos["concluido"] & ~df_prazos["arquivado"]]
        if filtro_tab1 != "Todos":
            df_ativos = df_ativos[df_ativos["responsavel"] == filtro_tab1]
        
        if not df_ativos.empty:
            st.markdown("### Gerenciar Prazos")
            st.session_state.setdefault("filtro_gerenciar_ativos", "Todos")
            filtro_resp_gerenciar = st.selectbox("Selecione um responsável", ["Todos"] + RESPONSAVEIS, key="select_filtro_gerenciar_ativos", label_visibility="collapsed")
            tabela_status(df_ativos, "ativos", filtro_resp_gerenciar)
        else:
            st.info("📭 Nenhum prazo ativo")
    
    with tab_concluidos:
        st.markdown("## ✅ PRAZOS CONCLUÍDOS")
        st.divider()
        
        st.session_state.setdefault("filtro_tab2", "Todos")
        filtro_tab2 = st.selectbox("Filtrar por responsável", ["Todos"] + RESPONSAVEIS, key="select_filtro_tab2", index=0)
        
        df_concluidos = df_prazos[df_prazos["concluido"]]
        if filtro_tab2 != "Todos":
            df_concluidos = df_concluidos[df_concluidos["responsavel"] == filtro_tab2]
        
        if not df_concluidos.empty:
            tabela_status(df_concluidos, "concluidos", None)
        else:
            st.info("📭 Nenhum prazo concluído")
    
    with tab_processos:
        st.markdown("## 📋 PROCESSOS")
        st.info("Em desenvolvimento...")
    
    with tab_audiencias:
        st.markdown("## 📅 AUDIÊNCIAS")
        st.divider()
        
        # ABAS: Cadastro e Listagem
        sub_tab_novo, sub_tab_lista = st.tabs(["➕ Nova Audiência", "📋 Listar"])
        
        with sub_tab_novo:
            st.subheader("📅 Cadastrar Audiência")
            
            with st.form("form_audiencia"):
                col1, col2 = st.columns(2)
                
                with col1:
                    processo_aud = st.text_input("Processo *", placeholder="Ex: 5014993")
                
                with col2:
                    responsavel_aud = st.radio("Responsável *", RESPONSAVEIS, horizontal=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    data_aud = st.date_input("Data da Audiência *", format="DD/MM/YYYY")
                with col2:
                    hora_inicio_aud = st.time_input("Hora *")
                
                col1, col2 = st.columns(2)
                with col1:
                    sala_aud = st.text_input("Sala/Local *", placeholder="Ex: 5º Andar, Sala 501")
                with col2:
                    formato_aud = st.selectbox("Formato *", FORMATOS_AUDIENCIA)
                
                col1, col2 = st.columns(2)
                with col1:
                    tipo_aud = st.selectbox("Tipo de Audiência *", TIPOS_AUDIENCIA)
                with col2:
                    status_aud = st.selectbox("Status *", STATUS_AUDIENCIA)
                
                autor_aud = st.text_input("Autor (Cliente) *", placeholder="Nome do cliente/autor")
                reu_aud = st.text_input("Réu *", placeholder="Nome do réu")
                observacoes_aud = st.text_area("Observações", placeholder="Informações adicionais...")
                
                # ===== VALIDAÇÃO =====
                submit_aud = st.form_submit_button("💾 Salvar Audiência", type="primary", use_container_width=True)
                
                if submit_aud:
                    # Validar campos obrigatórios
                    if not processo_aud or not data_aud or not hora_inicio_aud or not sala_aud or not autor_aud or not reu_aud:
                        st.error("❌ Preencha TODOS os campos obrigatórios (*)")
                    else:
                        # Inserir audiência
                        inserir_audiencia({
                            "processo": processo_aud,
                            "responsavel": responsavel_aud,
                            "data_audiencia": data_aud.isoformat(),
                            "hora_inicio": hora_inicio_aud.isoformat(),
                            "hora_termino": None,
                            "sala": sala_aud,
                            "formato": formato_aud,
                            "tipo": tipo_aud,
                            "status": status_aud,
                            "autor": autor_aud,
                            "reu": reu_aud,
                            "observacoes": observacoes_aud or None,
                        })
                        st.session_state.aviso = "✅ Audiência criada! Prazo administrativo inserido automaticamente."
                        st.rerun()
        
        with sub_tab_lista:
            st.subheader("📋 Audiências Cadastradas")
            
            if not df_audiencias.empty:
                for _, aud in df_audiencias.iterrows():
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([2, 1.5, 1.5])
                        
                        with col1:
                            st.markdown(f"**Processo:** {aud['processo']}")
                            st.markdown(f"**Autor:** {aud['autor']} | **Réu:** {aud['reu']}")
                        
                        with col2:
                            st.markdown(f"**Data:** {aud['data_audiencia'].strftime('%d/%m/%Y')}")
                            st.markdown(f"**Hora:** {aud['hora_inicio']}")
                        
                        with col3:
                            st.markdown(f"**Responsável:** {aud['responsavel']}")
                            st.markdown(f"**Status:** {aud['status']}")
            else:
                st.info("📭 Nenhuma audiência cadastrada")

# ===== NOVO PRAZO (SIDEBAR) =====
def sidebar_novo_prazo(processos_df: pd.DataFrame) -> None:
    st.subheader("📋 Novo Prazo")
    v = st.session_state.form_v
    
    processos_ativos = processos_df[processos_df["ativo"]].sort_values("numero") if not processos_df.empty else pd.DataFrame()
    
    st.write("**Nº Processo ***")
    busca = st.text_input("Digite o número do processo", value="", placeholder="Ex: 5014993", key=f"busca_proc_{v}", label_visibility="collapsed")
    
    processo = None
    cliente = ""
    
    if busca and not processos_ativos.empty:
        processos_filtrados = processos_ativos[processos_ativos["numero"].str.contains(busca, case=False, regex=False)]
        if not processos_filtrados.empty:
            st.caption(f"📋 {len(processos_filtrados)} processo(s) encontrado(s):")
            processo = st.selectbox("Selecione:", options=processos_filtrados["numero"].values, label_visibility="collapsed", key=f"sel_proc_{v}")
            if processo:
                cliente = processos_ativos[processos_ativos["numero"] == processo]["cliente"].values[0]
                st.success(f"✅ Processo selecionado: **{processo}**")
    
    st.write("**Título ***")
    busca_titulo = st.text_input("Digite para filtrar atalhos", value="", placeholder="Ex: PET, CONT", key=f"busca_{v}", label_visibility="collapsed")
    
    titulo = ""
    if busca_titulo:
        atalhos_filtrados = {k: v for k, v in ATALHOS.items() if busca_titulo.upper() in k}
        if atalhos_filtrados:
            titulo_atalho = st.selectbox("Atalhos:", options=list(atalhos_filtrados.keys()), format_func=lambda x: f"{x} — {atalhos_filtrados[x]}", key=f"ta_{v}", label_visibility="collapsed")
            titulo = atalhos_filtrados[titulo_atalho]
    else:
        st.caption("👉 Digite para ver atalhos")
    
    if titulo:
        st.caption(f"📌 Selecionado: **{titulo}**")
    
    with st.form(f"cad_{v}"):
        tipo = st.selectbox("Tipo *", TIPOS, index=0, key=f"t_{v}")
        responsavel = st.radio("Responsável *", RESPONSAVEIS, horizontal=True, key=f"r_{v}")
        
        c1, c2 = st.columns(2)
        data_interna = c1.date_input("Prazo Interno", value=None, format="DD/MM/YYYY", key=f"i_{v}")
        data_fatal = c2.date_input("Data Fatal *", value=None, format="DD/MM/YYYY", key=f"f_{v}")
        
        prioridade = st.select_slider("Prioridade", PRIORIDADES, value="Normal", key=f"pr_{v}")
        st.text_area("Observações", value="", key=f"d_{v}")
        
        col_salvar, col_apagar = st.columns(2)
        
        submit = False
        with col_salvar:
            submit = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)
        
        if submit:
            if not processo or not data_fatal or not titulo:
                st.error("Preencha processo, data fatal e título!")
            elif data_interna and data_interna > data_fatal:
                st.error("Prazo interno deve ser ≤ data fatal!")
            else:
                df_prazos = carregar_prazos()
                prazo_existe = df_prazos[
                    (df_prazos["processo"] == processo) &
                    (df_prazos["titulo"] == titulo) &
                    (~df_prazos["concluido"]) &
                    (~df_prazos["arquivado"])
                ]
                
                if not prazo_existe.empty:
                    st.error(f"⚠️ Este prazo já existe!")
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
                    st.session_state.form_v += 1
                    st.session_state.aviso = "✅ Prazo salvo!"
                    st.rerun()
    
    col_spacer, col_btn_limpar = st.columns([2, 1])
    with col_btn_limpar:
        if st.button("🗑️ Apagar", use_container_width=True, type="secondary"):
            st.session_state.form_v += 1
            st.rerun()

if __name__ == "__main__":
    main()
