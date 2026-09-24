"""
Controladoria Jurídica - VERSÃO FINAL COM 4 ABAS
"""
# ============================================
# CONTROLADORIA JURÍDICA - SISTEMA DE PRAZOS
# Versão: 2.1 - Atualizado: 24/09/2026
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

FORMATOS_AUDIENCIA = ["Presencial", "Virtual"]
TIPOS_AUDIENCIA = ["Inicial", "Continuação", "Sentença", "Outra"]
STATUS_AUDIENCIA = ["Agendada", "Realizada", "Cancelada"]

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
    st.session_state.setdefault("sel_prazo_idx", 0)
    # Note: Audiência modal states are now scoped to each prefix and initialized in tabela_audiencias()

def acesso_liberado() -> bool:
    senha_correta = st.secrets.get("APP_PASSWORD")
    
    # ===== AVISAR SE SENHA NÃO ESTÁ CONFIGURADA =====
    if not senha_correta:
        st.title("⚖️ Controladoria Jurídica")
        st.error("🔴 ERRO: APP_PASSWORD não configurada em .streamlit/secrets.toml")
        st.info("Configure a senha no arquivo secrets.toml e redeploy o app.")
        st.stop()
    
    # ===== SE JÁ AUTENTICADO, LIBERA =====
    if st.session_state.get("autenticado"):
        return True
    
    # ===== TELA DE LOGIN =====
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

@st.cache_data(ttl=60, show_spinner="Carregando audiências…")
def carregar_audiencias() -> pd.DataFrame:
    try:
        resp = supabase().table(TABELA_AUDIENCIAS).select("*").order("data_audiencia").execute()
        if not resp.data:
            return pd.DataFrame(columns=COLUNAS_AUDIENCIAS)
        df = pd.DataFrame(resp.data, columns=COLUNAS_AUDIENCIAS)
        df["data_audiencia"] = pd.to_datetime(df["data_audiencia"], errors="coerce").dt.date
        return df
    except Exception as e:
        st.error(f"Erro ao carregar audiências: {e}")
        return pd.DataFrame(columns=COLUNAS_AUDIENCIAS)

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

def inserir_audiencia(registro: dict) -> None:
    supabase().table(TABELA_AUDIENCIAS).insert(registro).execute()
    carregar_audiencias.clear()

def atualizar_audiencia(id_audiencia: int, campos: dict) -> None:
    if campos:
        supabase().table(TABELA_AUDIENCIAS).update(campos).eq("id", id_audiencia).execute()
    carregar_audiencias.clear()

def excluir_audiencia(id_audiencia: int) -> None:
    supabase().table(TABELA_AUDIENCIAS).delete().eq("id", id_audiencia).execute()
    carregar_audiencias.clear()

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

def gerar_csv_pauta(df_prazos: pd.DataFrame, df_processos: pd.DataFrame = None):
    """Gera CSV com pauta de prazos e descrição dos processos"""
    if df_prazos.empty:
        return pd.DataFrame()
    
    # Preparar dados
    df_export = df_prazos[["cliente", "processo", "titulo", "data_fatal"]].copy()
    
    # Extrair primeiro nome do cliente
    df_export["cliente_primeiro"] = df_export["cliente"].apply(lambda x: x.split()[0] if pd.notna(x) else "")
    
    # Se temos dados de processos, fazer merge para trazer descrição
    if df_processos is not None:
        processos_desc = df_processos[["numero", "descricao"]].copy()
        df_export = df_export.merge(processos_desc, left_on="processo", right_on="numero", how="left")
        df_export["descricao"] = df_export["descricao"].fillna("-")
    else:
        df_export["descricao"] = "-"
    
    # Reorganizar colunas na ordem desejada
    df_export = df_export[["cliente_primeiro", "processo", "titulo", "data_fatal", "descricao"]]
    
    # Converter data_fatal para string com formato DD/MM/YYYY
    try:
        df_export["data_fatal"] = pd.to_datetime(df_export["data_fatal"]).dt.strftime("%d/%m/%Y")
    except:
        df_export["data_fatal"] = df_export["data_fatal"].astype(str)
    
    # Renomear colunas
    df_export = df_export.rename(columns={
        "cliente_primeiro": "Cliente",
        "processo": "Nº Processo",
        "titulo": "Título",
        "data_fatal": "Data Fatal",
        "descricao": "Descrição"
    })
    
    return df_export

def gerar_excel_bonito(df_prazos: pd.DataFrame, df_processos: pd.DataFrame = None):
    """Gera Excel bonito com pauta de prazos formatado"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    import tempfile
    
    if df_prazos.empty:
        return None
    
    # Preparar dados
    df_export = df_prazos[["cliente", "processo", "titulo", "data_fatal"]].copy()
    
    # Extrair primeiro nome do cliente
    df_export["cliente"] = df_export["cliente"].apply(lambda x: x.split()[0] if pd.notna(x) else "")
    
    # Se temos dados de processos, fazer merge para trazer descrição
    if df_processos is not None:
        processos_desc = df_processos[["numero", "descricao"]].copy()
        df_export = df_export.merge(processos_desc, left_on="processo", right_on="numero", how="left")
        df_export["descricao"] = df_export["descricao"].fillna("-")
    else:
        df_export["descricao"] = "-"
    
    # Converter data_fatal para string com formato DD/MM/YYYY
    try:
        df_export["data_fatal"] = pd.to_datetime(df_export["data_fatal"]).dt.strftime("%d/%m/%Y")
    except:
        df_export["data_fatal"] = df_export["data_fatal"].astype(str)
    
    # Reordenar colunas
    df_export = df_export[["cliente", "processo", "titulo", "data_fatal", "descricao"]]
    
    # Criar workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Pauta"
    
    # Definir estilos
    header_fill = PatternFill(start_color="1f4788", end_color="1f4788", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    
    # Cabeçalhos
    headers = ["Cliente", "Nº Processo", "Título", "Data Fatal", "Descrição"]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = border
    
    # Dados
    for row_num, (idx, row) in enumerate(df_export.iterrows(), 2):
        ws.cell(row=row_num, column=1).value = row["cliente"]
        ws.cell(row=row_num, column=1).alignment = left_align
        ws.cell(row=row_num, column=1).border = border
        
        ws.cell(row=row_num, column=2).value = row["processo"]
        ws.cell(row=row_num, column=2).alignment = left_align
        ws.cell(row=row_num, column=2).border = border
        
        ws.cell(row=row_num, column=3).value = row["titulo"]
        ws.cell(row=row_num, column=3).alignment = left_align
        ws.cell(row=row_num, column=3).border = border
        
        ws.cell(row=row_num, column=4).value = row["data_fatal"]
        ws.cell(row=row_num, column=4).alignment = center_align
        ws.cell(row=row_num, column=4).border = border
        
        ws.cell(row=row_num, column=5).value = row["descricao"]
        ws.cell(row=row_num, column=5).alignment = left_align
        ws.cell(row=row_num, column=5).border = border
    
    # Ajustar largura das colunas
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 35
    
    # Salvar em arquivo temporário
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        wb.save(tmp.name)
        return tmp.name

def gerar_audiencias_excel(df_audiencias: pd.DataFrame):
    """Gera Excel bonito com agenda de audiências formatado"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    import tempfile

    if df_audiencias.empty:
        return None

    # Preparar dados
    df_export = df_audiencias[["processo", "autor", "reu", "sala", "data_audiencia", "hora_inicio", "hora_termino", "formato", "tipo", "status"]].copy()

    # Converter datas e horas para string
    try:
        df_export["data_audiencia"] = pd.to_datetime(df_export["data_audiencia"]).dt.strftime("%d/%m/%Y")
    except:
        df_export["data_audiencia"] = df_export["data_audiencia"].astype(str)

    df_export["hora_inicio"] = df_export["hora_inicio"].astype(str)
    df_export["hora_termino"] = df_export["hora_termino"].astype(str)

    # Criar workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Audiências"

    # Definir estilos
    header_fill = PatternFill(start_color="1f4788", end_color="1f4788", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # Cabeçalhos
    headers = ["Nº Processo", "Autor", "Réu", "Sala", "Data", "Início", "Término", "Formato", "Tipo", "Status"]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = border

    # Dados
    for row_num, (idx, row) in enumerate(df_export.iterrows(), 2):
        ws.cell(row=row_num, column=1).value = row["processo"]
        ws.cell(row=row_num, column=1).alignment = left_align
        ws.cell(row=row_num, column=1).border = border

        ws.cell(row=row_num, column=2).value = row["autor"]
        ws.cell(row=row_num, column=2).alignment = left_align
        ws.cell(row=row_num, column=2).border = border

        ws.cell(row=row_num, column=3).value = row["reu"]
        ws.cell(row=row_num, column=3).alignment = left_align
        ws.cell(row=row_num, column=3).border = border

        ws.cell(row=row_num, column=4).value = row["sala"]
        ws.cell(row=row_num, column=4).alignment = center_align
        ws.cell(row=row_num, column=4).border = border

        ws.cell(row=row_num, column=5).value = row["data_audiencia"]
        ws.cell(row=row_num, column=5).alignment = center_align
        ws.cell(row=row_num, column=5).border = border

        ws.cell(row=row_num, column=6).value = row["hora_inicio"]
        ws.cell(row=row_num, column=6).alignment = center_align
        ws.cell(row=row_num, column=6).border = border

        ws.cell(row=row_num, column=7).value = row["hora_termino"]
        ws.cell(row=row_num, column=7).alignment = center_align
        ws.cell(row=row_num, column=7).border = border

        ws.cell(row=row_num, column=8).value = row["formato"]
        ws.cell(row=row_num, column=8).alignment = center_align
        ws.cell(row=row_num, column=8).border = border

        ws.cell(row=row_num, column=9).value = row["tipo"]
        ws.cell(row=row_num, column=9).alignment = center_align
        ws.cell(row=row_num, column=9).border = border

        ws.cell(row=row_num, column=10).value = row["status"]
        ws.cell(row=row_num, column=10).alignment = center_align
        ws.cell(row=row_num, column=10).border = border

    # Ajustar largura das colunas
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 12
    ws.column_dimensions['H'].width = 15
    ws.column_dimensions['I'].width = 15
    ws.column_dimensions['J'].width = 15

    # Salvar em arquivo temporário
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        wb.save(tmp.name)
        return tmp.name

def tabela_status(df: pd.DataFrame, processos_df: pd.DataFrame = None, prefix: str = "main") -> None:
    if df.empty:
        st.info("Nenhum registro.")
        return

    df_vis = df.copy()

    # ===== INICIALIZAR ESTADO MODAL SCOPED AO PREFIX =====
    modal_key_aberta = f"prazo_modal_{prefix}_aberta"
    modal_key_id = f"prazo_modal_{prefix}_id"
    modal_key_modo = f"prazo_modal_{prefix}_modo"

    st.session_state.setdefault(modal_key_aberta, False)
    st.session_state.setdefault(modal_key_id, None)
    st.session_state.setdefault(modal_key_modo, None)

    # ===== EXTRAIR PRIMEIRO NOME DO CLIENTE =====
    df_vis["cliente_primeiro"] = df_vis["cliente"].apply(lambda x: x.split()[0] if x else "")

    # ===== ADICIONAR PARTE CONTRÁRIA (SE HOUVER PROCESSOS) =====
    if processos_df is not None:
        # Remover duplicatas do processos antes de fazer merge
        processos_parte = processos_df[["numero", "parte_contraria"]].drop_duplicates(subset=["numero"], keep="first").copy()
        df_vis = df_vis.merge(processos_parte, left_on="processo", right_on="numero", how="left")

        # Extrair primeiro nome da parte contrária
        df_vis["parte_primeiro"] = df_vis["parte_contraria"].apply(lambda x: x.split()[0] if pd.notna(x) and x else "")

        # Concatenar cliente + parte
        df_vis["cliente_parte"] = df_vis.apply(
            lambda row: f"{row['cliente_primeiro']} / {row['parte_primeiro']}" if row['parte_primeiro'] else row['cliente_primeiro'],
            axis=1
        )
    else:
        df_vis["cliente_parte"] = df_vis["cliente_primeiro"]

    df_vis["data_interna_fmt"] = df_vis["data_interna"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "")
    df_vis["data_fatal_fmt"] = df_vis["data_fatal"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "")

    # ===== REMOVER D.ÚTEIS, TIPO E RESPONSÁVEL =====
    # ===== REMOVER DUPLICATAS DE EXIBIÇÃO =====
    colunas_vis = [
        "id", "situacao", "titulo", "processo", "cliente_parte",
        "data_interna_fmt", "data_fatal_fmt", "responsavel", "prioridade",
    ]
    vis = (
        df_vis.assign(_p=df_vis["prioridade"].map(ORDEM_PRIORIDADE))
        .sort_values(["dias_uteis"])[colunas_vis]
        .drop_duplicates(subset=["processo", "titulo", "data_fatal_fmt"], keep="first")
        .set_index("id")
        .rename(columns={
            "data_interna_fmt": "Prazo Interno",
            "data_fatal_fmt": "Data Fatal",
            "situacao": "Situação",
            "titulo": "Título",
            "processo": "Nº Processo",
            "cliente_parte": "Cliente / Parte Contrária",
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

    # ===== CRIAR OPÇÕES SIMPLES =====
    if df_ativos.empty:
        st.info("Nenhum prazo ativo.")
        return

    # Criar lista de strings para exibir
    opcoes_display = ["📌 Selecione um prazo..."]
    opcoes_ids = [None]

    for _, row in df_ativos.iterrows():
        opcoes_display.append(f"{row['cliente']} | {row['titulo']} | {row['data_fatal'].strftime('%d/%m/%Y')}")
        opcoes_ids.append(row['id'])

    id_sel_idx = col1.selectbox(
        "Clique no prazo para ver detalhes:",
        options=range(len(opcoes_display)),
        format_func=lambda x: opcoes_display[x],
        key=f"sel_prazo_idx_{prefix}"
    )

    if col2.button("📂 Ver Detalhes", use_container_width=True, type="primary", key=f"btn_det_prazo_{prefix}"):
        if st.session_state.get(f"sel_prazo_idx_{prefix}", 0) > 0:  # Índice 0 é a opção vazia
            id_sel = opcoes_ids[st.session_state.get(f"sel_prazo_idx_{prefix}", 0)]
            st.session_state[modal_key_id] = id_sel
            st.session_state[modal_key_modo] = "detalhes"
            st.session_state[modal_key_aberta] = True
            st.rerun()
        else:
            st.warning("⚠️ Selecione um prazo primeiro!")

    if st.session_state.get(modal_key_aberta) and st.session_state.get(modal_key_id):
        id_prazo = st.session_state[modal_key_id]
        prazo = df[df["id"] == id_prazo].iloc[0]

        st.divider()
        st.subheader(f"⚙️ {prazo['titulo']}")

        # ===== MODAL DE DETALHES DO PRAZO =====
        if st.session_state.get(modal_key_modo) == "detalhes":
            st.info("📋 Detalhes Completos do Prazo")
            
            # Buscar parte contrária e descrição do processo
            parte_contraria = ""
            descricao_processo = ""
            if processos_df is not None and prazo['processo']:
                proc_match = processos_df[processos_df['numero'] == prazo['processo']]
                if not proc_match.empty:
                    parte_contraria = proc_match.iloc[0]['parte_contraria']
                    descricao_processo = proc_match.iloc[0]['descricao']
            
            col1, col2 = st.columns(2)
            col1.write(f"**Cliente:** {prazo['cliente']}")
            col2.write(f"**Nº Processo:** {prazo['processo']}")
            
            if parte_contraria:
                st.write(f"**Parte Contrária:** {parte_contraria}")
            
            if descricao_processo:
                st.write(f"**Ação:** {descricao_processo}")
            
            col1, col2 = st.columns(2)
            col1.write(f"**Responsável:** {prazo['responsavel']}")
            col2.write(f"**Prioridade:** {prazo['prioridade']}")
            
            col1, col2 = st.columns(2)
            col1.write(f"**Prazo Interno:** {prazo['data_interna'].strftime('%d/%m/%Y') if pd.notna(prazo['data_interna']) else 'Não definido'}")
            col2.write(f"**Data Fatal:** {prazo['data_fatal'].strftime('%d/%m/%Y')}")
            
            st.write(f"**Tipo:** {prazo['tipo']}")
            
            # ===== DESCRIÇÃO/OBSERVAÇÕES EXISTENTES =====
            if prazo['descricao']:
                st.divider()
                st.subheader("📌 Observações Anteriores")
                st.info(prazo['descricao'])
            
            st.divider()
            st.subheader("📝 O QUE DEVE SER FEITO")
            
            with st.form(f"form_dicas_{id_prazo}"):
                dicas = st.text_area(
                    "Anote aqui as dicas, passos e informações para cumprir este prazo:",
                    value=prazo['descricao'] or "",
                    height=150,
                    placeholder="Ex: \n- Buscar artigos CPC 150-200\n- Citar jurisprudência STJ\n- Anexar RG, CPF e comprovante de residência\n- Enviar ao tribunal até 15h",
                    key=f"dicas_{id_prazo}"
                )
                
                if st.form_submit_button("💾 Salvar Dicas", use_container_width=True, type="primary"):
                    atualizar_campos({id_prazo: {"descricao": dicas}})
                    st.session_state.aviso = "✅ Dicas salvas!"
                    st.session_state.editor_v += 1
                    st.rerun()
            
            st.divider()
            st.subheader("⚙️ Ações")
            
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("✏️ Editar Prazo", use_container_width=True, type="secondary", key=f"btn_edit_{prefix}_{id_prazo}"):
                    st.session_state[modal_key_modo] = "editar"
                    st.rerun()

            with col2:
                if st.button("✅ Concluído", use_container_width=True, type="primary", key=f"btn_concluido_{prefix}_{id_prazo}"):
                    st.session_state[modal_key_modo] = "concluir_com_obs"
                    st.rerun()

            with col3:
                if st.button("📦 Arquivar", use_container_width=True, type="secondary", key=f"btn_arquivar_{prefix}_{id_prazo}"):
                    st.session_state[modal_key_modo] = "confirmar_arquivar"
                    st.rerun()

            with col4:
                if st.button("❌ Excluir", use_container_width=True, type="secondary", key=f"btn_excluir_{prefix}_{id_prazo}"):
                    st.session_state[modal_key_modo] = "confirmar_excluir"
                    st.rerun()

            st.divider()
            col_fechar = st.columns([3, 1])
            with col_fechar[1]:
                if st.button("🔙 Fechar", use_container_width=True, type="secondary", key=f"btn_fechar_{prefix}_{id_prazo}"):
                    st.session_state[modal_key_aberta] = False
                    st.session_state[modal_key_modo] = None
                    st.rerun()
        
        elif st.session_state.get(modal_key_modo) == "editar":
            with st.form(f"form_{prefix}_{id_prazo}"):
                # ===== EDITAR TODOS OS CAMPOS =====
                novo_titulo = st.text_input("Título", value=prazo["titulo"], key=f"edit_titulo_{prefix}_{id_prazo}")

                col1, col2 = st.columns(2)
                with col1:
                    novo_responsavel = st.selectbox("Responsável", RESPONSAVEIS, index=RESPONSAVEIS.index(prazo["responsavel"]), key=f"edit_resp_{prefix}_{id_prazo}")
                with col2:
                    nova_prioridade = st.selectbox("Prioridade", PRIORIDADES, index=PRIORIDADES.index(prazo["prioridade"]), key=f"edit_prio_{prefix}_{id_prazo}")

                col1, col2 = st.columns(2)
                nova_interna = col1.date_input("Prazo Interno", value=prazo["data_interna"], format="DD/MM/YYYY", key=f"edit_interna_{prefix}_{id_prazo}")
                nova_fatal = col2.date_input("Data Fatal", value=prazo["data_fatal"], format="DD/MM/YYYY", key=f"edit_fatal_{prefix}_{id_prazo}")

                nova_descricao = st.text_area("Observações", value=prazo["descricao"] or "", key=f"edit_desc_{prefix}_{id_prazo}")

                # ===== PREVIEW DE SITUAÇÃO (TEMPO REAL) =====
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
                    st.info(f"📌 Nova Situação: {sit}")

                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                        atualizar_campos({id_prazo: {
                            "titulo": novo_titulo,
                            "responsavel": novo_responsavel,
                            "prioridade": nova_prioridade,
                            "data_fatal": nova_fatal.isoformat(),
                            "data_interna": nova_interna.isoformat() if nova_interna else None,
                            "descricao": nova_descricao or None
                        }})
                        st.session_state.aviso = "✅ Prazo atualizado!"
                        st.session_state[modal_key_aberta] = False
                        st.session_state.editor_v += 1
                        st.rerun()
                with c2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state[modal_key_modo] = "detalhes"
                        st.rerun()
        
        elif st.session_state.get(modal_key_modo) == "confirmar_arquivar":
            st.warning("⚠️ Tem certeza que deseja arquivar?")
            st.write(f"**Cliente:** {prazo['cliente']}")
            st.write(f"**Título (Prazo):** {prazo['titulo']}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ SIM, Arquivar", use_container_width=True, type="primary", key=f"btn_sim_arq_{prefix}_{id_prazo}"):
                    arquivar_prazo(id_prazo)
                    carregar_prazos.clear()
                    carregar_processos.clear()
                    st.session_state.aviso = "✅ Arquivado!"
                    st.session_state[modal_key_aberta] = False

                    st.session_state.editor_v += 1
                    st.rerun()
            with c2:
                if st.button("❌ NÃO, Cancelar", use_container_width=True, key=f"btn_nao_arq_{prefix}_{id_prazo}"):
                    st.session_state[modal_key_modo] = "detalhes"
                    st.rerun()
        
        elif st.session_state.get(modal_key_modo) == "concluir_com_obs":
            st.warning("📝 Adicione anotações sobre este prazo antes de concluir")
            st.write(f"**Cliente:** {prazo['cliente']}")
            st.write(f"**Título (Prazo):** {prazo['titulo']}")

            with st.form(f"form_concluir_{prefix}_{id_prazo}"):
                anotacoes = st.text_area(
                    "O que foi feito neste prazo?",
                    placeholder="Ex: Petição inicial enviada com documentos anexados...",
                    height=120,
                    key=f"anol_{prefix}_{id_prazo}"
                )

                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("✅ Concluir com Anotações", type="primary", use_container_width=True):
                        # Concatena anotações com observações antigas (se houver)
                        obs_antiga = prazo['descricao'] or ""
                        if obs_antiga:
                            obs_nova = f"{obs_antiga}\n\n✅ CONCLUÍDO: {anotacoes}"
                        else:
                            obs_nova = f"✅ CONCLUÍDO: {anotacoes}"

                        atualizar_campos({id_prazo: {
                            "concluido": True,
                            "concluido_em": dt.datetime.now(TZ).isoformat(),
                            "descricao": obs_nova
                        }})
                        st.session_state.aviso = "✅ Prazo concluído com anotações!"
                        st.session_state[modal_key_aberta] = False

                        st.session_state.editor_v += 1
                        st.rerun()

                with c2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state[modal_key_modo] = "detalhes"
                        st.rerun()
        
        elif st.session_state.get(modal_key_modo) == "confirmar_excluir":
            st.error("🔴 ATENÇÃO: Excluir é permanente!")
            st.write(f"**Cliente:** {prazo['cliente']}")
            st.write(f"**Título (Prazo):** {prazo['titulo']}")
            st.caption("⚠️ Esta ação NÃO pode ser desfeita!")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🗑️ SIM, Excluir", use_container_width=True, type="primary", key=f"btn_sim_exc_{prefix}_{id_prazo}"):
                    excluir_prazo(id_prazo)
                    carregar_prazos.clear()
                    carregar_processos.clear()
                    st.session_state.aviso = "✅ Prazo excluído!"
                    st.session_state[modal_key_aberta] = False

                    st.session_state.editor_v += 1
                    st.rerun()
            with c2:
                if st.button("❌ NÃO, Cancelar", use_container_width=True, key=f"btn_nao_exc_{prefix}_{id_prazo}"):
                    st.session_state[modal_key_modo] = "detalhes"
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
            processos_ativos["numero"].str.contains(busca, case=False, regex=False)
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
    
    # ===== BUSCA DE ATALHOS (FORA DO FORM - TEMPO REAL) =====
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
    
    # ===== FORMULÁRIO (DENTRO DO FORM) =====
    with st.form(f"cad_{v}"):
        tipo = st.selectbox("Tipo *", TIPOS, index=0, key=f"t_{v}")

        responsavel = st.radio("Responsável *", RESPONSAVEIS, horizontal=True, key=f"r_{v}")
        c1, c2 = st.columns(2)
        data_interna = c1.date_input("Prazo Interno", value=None, format="DD/MM/YYYY", key=f"i_{v}")
        data_fatal = c2.date_input("Data Fatal *", value=None, format="DD/MM/YYYY", key=f"f_{v}")

        prioridade = st.select_slider("Prioridade", PRIORIDADES, value="Normal", key=f"pr_{v}")
        st.text_area("Observações", value="", key=f"d_{v}")

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
                # ===== LIMPAR FORMULÁRIO =====
                st.session_state.form_v += 1
                st.session_state.aviso = "✅ Prazo salvo com sucesso!"
                st.rerun()

def dashboard_completo(df_prazos: pd.DataFrame, df_audiencias: pd.DataFrame, df_processos: pd.DataFrame) -> None:
    """Dashboard interativo com métricas clicáveis"""
    st.markdown("# 📊 DASHBOARD CONTROLADORIA")
    st.divider()

    # ===== INICIALIZAR ESTADO =====
    st.session_state.setdefault("dashboard_filtro", None)

    # ===== ENRIQUECER DADOS =====
    if not df_prazos.empty:
        df_prazos = enriquecer(df_prazos)

    # ===== CALCULAR MÉTRICAS PRAZOS =====
    pend = df_prazos[~df_prazos["concluido"] & ~df_prazos["arquivado"]] if not df_prazos.empty else pd.DataFrame()
    vencidos = pend[pend["faixa"] == "Vencido"] if not pend.empty else pd.DataFrame()
    hoje_prazos = pend[pend["faixa"] == "Hoje"] if not pend.empty else pd.DataFrame()

    aud_agendadas = df_audiencias[df_audiencias["status"] == "Agendada"] if not df_audiencias.empty else pd.DataFrame()
    aud_realizadas = df_audiencias[df_audiencias["status"] == "Realizada"] if not df_audiencias.empty else pd.DataFrame()
    aud_canceladas = df_audiencias[df_audiencias["status"] == "Cancelada"] if not df_audiencias.empty else pd.DataFrame()

    # ===== LINHA 1: PRAZOS =====
    st.markdown("## 📋 PRAZOS")
    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        with st.container(border=True):
            st.markdown("### 🔴 VENCIDOS")
            st.metric("", len(vencidos), label_visibility="collapsed")
            if st.button("Ver Detalhes", key="btn_vencidos", use_container_width=True):
                st.session_state.dashboard_filtro = "vencidos"

    with col2:
        with st.container(border=True):
            st.markdown("### 🟠 HOJE")
            st.metric("", len(hoje_prazos), label_visibility="collapsed")
            if st.button("Ver Detalhes", key="btn_hoje", use_container_width=True):
                st.session_state.dashboard_filtro = "hoje"

    with col3:
        with st.container(border=True):
            st.markdown("### 📋 PENDENTES")
            st.metric("", len(pend), label_visibility="collapsed")
            if st.button("Ver Detalhes", key="btn_pendentes", use_container_width=True):
                st.session_state.dashboard_filtro = "pendentes"

    st.divider()

    # ===== LINHA 2: AUDIÊNCIAS =====
    st.markdown("## 📅 AUDIÊNCIAS")
    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        with st.container(border=True):
            st.markdown("### 📅 AGENDADAS")
            st.metric("", len(aud_agendadas), label_visibility="collapsed")
            if st.button("Ver Detalhes", key="btn_agendadas", use_container_width=True):
                st.session_state.dashboard_filtro = "agendadas"

    with col2:
        with st.container(border=True):
            st.markdown("### ✅ REALIZADAS")
            st.metric("", len(aud_realizadas), label_visibility="collapsed")
            if st.button("Ver Detalhes", key="btn_realizadas", use_container_width=True):
                st.session_state.dashboard_filtro = "realizadas"

    with col3:
        with st.container(border=True):
            st.markdown("### ❌ CANCELADAS")
            st.metric("", len(aud_canceladas), label_visibility="collapsed")
            if st.button("Ver Detalhes", key="btn_canceladas", use_container_width=True):
                st.session_state.dashboard_filtro = "canceladas"

    st.divider()

    # ===== EXIBIR DETALHES SELECIONADOS =====
    if st.session_state.dashboard_filtro:
        filtro = st.session_state.dashboard_filtro

        st.markdown("---")
        col_voltar = st.columns([3, 1])
        with col_voltar[1]:
            if st.button("🔙 Voltar", use_container_width=True, key="btn_voltar_dash"):
                st.session_state.dashboard_filtro = None
                st.rerun()

        st.markdown("---")

        # ===== PRAZOS VENCIDOS =====
        if filtro == "vencidos":
            st.subheader("🔴 Prazos Vencidos")
            if vencidos.empty:
                st.info("Nenhum prazo vencido!")
            else:
                tabela_status(vencidos, df_processos, prefix="dash_vencidos")

        # ===== PRAZOS HOJE =====
        elif filtro == "hoje":
            st.subheader("🟠 Prazos de Hoje")
            if hoje_prazos.empty:
                st.info("Nenhum prazo para hoje!")
            else:
                tabela_status(hoje_prazos, df_processos, prefix="dash_hoje")

        # ===== PRAZOS PENDENTES =====
        elif filtro == "pendentes":
            st.subheader("📋 Prazos Pendentes")
            if pend.empty:
                st.info("Nenhum prazo pendente!")
            else:
                tabela_status(pend, df_processos, prefix="dash_pendentes")

        # ===== AUDIÊNCIAS AGENDADAS =====
        elif filtro == "agendadas":
            st.subheader("📅 Audiências Agendadas")
            if aud_agendadas.empty:
                st.info("Nenhuma audiência agendada!")
            else:
                tabela_audiencias(aud_agendadas, prefix="dash_agendadas")

        # ===== AUDIÊNCIAS REALIZADAS =====
        elif filtro == "realizadas":
            st.subheader("✅ Audiências Realizadas")
            if aud_realizadas.empty:
                st.info("Nenhuma audiência realizada!")
            else:
                tabela_audiencias(aud_realizadas, prefix="dash_realizadas")

        # ===== AUDIÊNCIAS CANCELADAS =====
        elif filtro == "canceladas":
            st.subheader("❌ Audiências Canceladas")
            if aud_canceladas.empty:
                st.info("Nenhuma audiência cancelada!")
            else:
                tabela_audiencias(aud_canceladas, prefix="dash_canceladas")

def sidebar_nova_audiencia(processos_df: pd.DataFrame) -> None:
    """Formulário para nova audiência na barra lateral"""
    st.subheader("📅 Nova Audiência")
    v = st.session_state.form_v

    processos_ativos = processos_df[processos_df["ativo"]].sort_values("numero")

    st.write("**Nº Processo ***")
    busca = st.text_input(
        "Digite o número do processo",
        value="",
        placeholder="Ex: 5014993 ou 5028905",
        key=f"busca_proc_aud_{v}",
        label_visibility="collapsed"
    )

    processo = None
    autor = ""
    reu = ""

    if busca:
        processos_filtrados = processos_ativos[
            processos_ativos["numero"].str.contains(busca, case=False, regex=False)
        ]

        if not processos_filtrados.empty:
            st.caption(f"📋 {len(processos_filtrados)} processo(s) encontrado(s):")

            processo = st.selectbox(
                "Selecione:",
                options=processos_filtrados["numero"].values,
                index=0 if len(processos_filtrados) > 0 else None,
                label_visibility="collapsed",
                key=f"sel_proc_aud_{v}"
            )
        else:
            st.warning(f"❌ Nenhum processo encontrado com '{busca}'")

    if processo:
        autor = processos_ativos[processos_ativos["numero"] == processo]["cliente"].values[0]
        reu = processos_ativos[processos_ativos["numero"] == processo]["parte_contraria"].values[0]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Autor**")
            st.markdown(f"### **{autor}**")
        with col2:
            st.markdown(f"**Réu**")
            st.markdown(f"### **{reu}**")

        st.success(f"✅ Processo selecionado: **{processo}**")

    # ===== FORMULÁRIO =====
    with st.form(f"cad_aud_{v}"):
        col1, col2 = st.columns(2)
        with col1:
            data = col1.date_input("Data *", value=None, format="DD/MM/YYYY", key=f"aud_data_{v}")
        with col2:
            sala = col2.text_input("Sala (Local) *", value="", placeholder="Ex: Sala 101", key=f"aud_sala_{v}")

        col1, col2 = st.columns(2)
        with col1:
            hora_ini = col1.time_input("Hora Início *", key=f"aud_hora_ini_{v}")
        with col2:
            hora_fim = col2.time_input("Hora Término *", key=f"aud_hora_fim_{v}")

        col1, col2 = st.columns(2)
        with col1:
            formato = col1.selectbox("Formato *", FORMATOS_AUDIENCIA, index=0, key=f"aud_formato_{v}")
        with col2:
            tipo = col2.selectbox("Tipo *", TIPOS_AUDIENCIA, index=0, key=f"aud_tipo_{v}")

        responsavel = st.radio("Responsável *", RESPONSAVEIS, horizontal=True, key=f"aud_resp_{v}")

        obs = st.text_area("Observações", value="", placeholder="Ex: Traz documentação, etc...", key=f"aud_obs_{v}")

        if st.form_submit_button("💾 Salvar", type="primary"):
            if not processo or not data or not sala or not hora_ini or not hora_fim:
                st.error("Preencha todos os campos obrigatórios!")
            elif hora_ini >= hora_fim:
                st.error("Hora início deve ser menor que hora término!")
            else:
                inserir_audiencia({
                    "processo": processo,
                    "autor": autor,
                    "reu": reu,
                    "sala": sala,
                    "data_audiencia": data.isoformat(),
                    "hora_inicio": hora_ini.isoformat(),
                    "hora_termino": hora_fim.isoformat(),
                    "formato": formato,
                    "tipo": tipo,
                    "status": "Agendada",
                    "observacoes": obs or None,
                    "responsavel": responsavel
                })
                # ===== LIMPAR FORMULÁRIO =====
                st.session_state.form_v += 1
                st.session_state.aviso = "✅ Audiência salva com sucesso!"
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
    
    # ===== BARRA DE BUSCA =====
    col1, col2 = st.columns([3, 1])
    with col1:
        busca = st.text_input(
            "🔍 Buscar por número de processo ou nome do cliente:",
            placeholder="Ex: 5014993 ou HELENA",
            key="busca_processo",
            label_visibility="collapsed"
        )
    
    # ===== FILTRAR PROCESSOS =====
    if busca:
        processos_filtrados = processos_unicos[
            (processos_unicos["numero"].str.contains(busca, case=False, na=False, regex=False)) |
            (processos_unicos["cliente"].str.contains(busca, case=False, na=False, regex=False))
        ]
    else:
        processos_filtrados = processos_unicos
    
    # ===== RESUMO =====
    with col2:
        st.metric("Resultados", len(processos_filtrados))
    
    if processos_filtrados.empty:
        st.warning(f"❌ Nenhum processo encontrado com '{busca}'")
        return
    
    st.caption(f"Clique para expandir e ver todos os prazos do processo:")
    
    # ===== EXPANDIR CADA PROCESSO =====
    for idx, proc in processos_filtrados.iterrows():
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
                    prazos_abertos = enriquecer(prazos_abertos).sort_values("dias_uteis")
                    
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

def tabela_audiencias(df: pd.DataFrame, prefix: str = "main") -> None:
    """Exibe tabela de audiências agendadas"""
    if df.empty:
        st.info("Nenhuma audiência cadastrada.")
        return

    df_vis = df.copy()

    # ===== INICIALIZAR ESTADO MODAL SCOPED AO PREFIX =====
    modal_key_aberta = f"aud_modal_{prefix}_aberta"
    modal_key_id = f"aud_modal_{prefix}_id"
    modal_key_modo = f"aud_modal_{prefix}_modo"

    st.session_state.setdefault(modal_key_aberta, False)
    st.session_state.setdefault(modal_key_id, None)
    st.session_state.setdefault(modal_key_modo, None)

    # ===== FORMATAR DATAS E HORAS =====
    df_vis["data_fmt"] = df_vis["data_audiencia"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "")
    df_vis["hora_ini_fmt"] = df_vis["hora_inicio"].astype(str)
    df_vis["hora_fim_fmt"] = df_vis["hora_termino"].astype(str)

    # ===== COLUNAS A EXIBIR =====
    colunas_vis = [
        "id", "processo", "autor", "reu", "sala", "data_fmt", "hora_ini_fmt", "hora_fim_fmt",
        "formato", "tipo", "status", "responsavel"
    ]

    vis = df_vis[colunas_vis].set_index("id").rename(columns={
        "data_fmt": "Data",
        "hora_ini_fmt": "Início",
        "hora_fim_fmt": "Término",
        "processo": "Nº Processo",
        "autor": "Autor",
        "reu": "Réu",
        "sala": "Sala",
        "formato": "Formato",
        "tipo": "Tipo",
        "status": "Status",
        "responsavel": "Responsável"
    })

    st.dataframe(vis, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("⚙️ Gerenciar Audiência")

    if df.empty:
        st.info("Nenhuma audiência ativa.")
        return

    col1, col2 = st.columns([2, 1])

    # ===== CRIAR OPÇÕES SIMPLES =====
    opcoes_display = ["📌 Selecione uma audiência..."]
    opcoes_ids = [None]

    for _, row in df.iterrows():
        opcoes_display.append(f"{row['processo']} | {row['data_audiencia'].strftime('%d/%m/%Y %H:%M')} | {row['sala']}")
        opcoes_ids.append(row['id'])

    id_sel_idx = col1.selectbox(
        "Clique na audiência para ver detalhes:",
        options=range(len(opcoes_display)),
        format_func=lambda x: opcoes_display[x],
        key=f"sel_audiencia_idx_{prefix}"
    )

    if col2.button("📂 Ver Detalhes", use_container_width=True, type="primary", key=f"btn_aud_det_{prefix}"):
        if st.session_state.get(f"sel_audiencia_idx_{prefix}", 0) > 0:
            id_sel = opcoes_ids[st.session_state.get(f"sel_audiencia_idx_{prefix}", 0)]
            st.session_state[modal_key_id] = id_sel
            st.session_state[modal_key_modo] = "detalhes"
            st.session_state[modal_key_aberta] = True
            st.rerun()
        else:
            st.warning("⚠️ Selecione uma audiência primeiro!")

    # ===== MODAL DE DETALHES =====
    if st.session_state.get(modal_key_aberta) and st.session_state.get(modal_key_id):
        id_audiencia = st.session_state[modal_key_id]
        audiencia = df[df["id"] == id_audiencia].iloc[0]

        st.divider()
        st.subheader(f"📅 {audiencia['processo']} - {audiencia['data_audiencia'].strftime('%d/%m/%Y')}")

        if st.session_state.get(modal_key_modo) == "detalhes":
            st.info("📋 Detalhes Completos da Audiência")

            col1, col2 = st.columns(2)
            col1.write(f"**Nº Processo:** {audiencia['processo']}")
            col2.write(f"**Sala:** {audiencia['sala']}")

            col1, col2 = st.columns(2)
            col1.write(f"**Autor:** {audiencia['autor']}")
            col2.write(f"**Réu:** {audiencia['reu']}")

            col1, col2 = st.columns(2)
            col1.write(f"**Data:** {audiencia['data_audiencia'].strftime('%d/%m/%Y')}")
            col2.write(f"**Horário:** {audiencia['hora_inicio']} às {audiencia['hora_termino']}")

            col1, col2 = st.columns(2)
            col1.write(f"**Formato:** {audiencia['formato']}")
            col2.write(f"**Tipo:** {audiencia['tipo']}")

            col1, col2 = st.columns(2)
            col1.write(f"**Status:** {audiencia['status']}")
            col2.write(f"**Responsável:** {audiencia['responsavel']}")

            if audiencia['observacoes']:
                st.divider()
                st.subheader("📌 Observações")
                st.info(audiencia['observacoes'])

            st.divider()
            st.subheader("⚙️ Ações")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("✏️ Editar", use_container_width=True, type="secondary", key=f"btn_edit_aud_{prefix}_{id_audiencia}"):
                    st.session_state[modal_key_modo] = "editar"
                    st.rerun()

            with col2:
                if st.button("✅ Realizada", use_container_width=True, type="primary", key=f"btn_realizada_{prefix}_{id_audiencia}"):
                    atualizar_audiencia(id_audiencia, {"status": "Realizada"})
                    st.session_state.aviso = "✅ Audiência marcada como realizada!"
                    st.session_state[modal_key_aberta] = False
                    st.rerun()

            with col3:
                if st.button("❌ Cancelar", use_container_width=True, type="secondary", key=f"btn_cancelar_{prefix}_{id_audiencia}"):
                    atualizar_audiencia(id_audiencia, {"status": "Cancelada"})
                    st.session_state.aviso = "⚠️ Audiência cancelada!"
                    st.session_state[modal_key_aberta] = False
                    st.rerun()

            with col4:
                if st.button("🗑️ Excluir", use_container_width=True, type="secondary", key=f"btn_excluir_{prefix}_{id_audiencia}"):
                    st.session_state[modal_key_modo] = "confirmar_excluir"
                    st.rerun()

            st.divider()
            col_fechar = st.columns([3, 1])
            with col_fechar[1]:
                if st.button("🔙 Fechar", use_container_width=True, type="secondary", key=f"btn_fechar_{prefix}_{id_audiencia}"):
                    st.session_state[modal_key_aberta] = False
                    st.rerun()

        elif st.session_state.get(modal_key_modo) == "editar":
            with st.form(f"form_edit_aud_{prefix}_{id_audiencia}"):
                col1, col2 = st.columns(2)
                with col1:
                    nova_data = st.date_input("Data", value=audiencia["data_audiencia"], format="DD/MM/YYYY", key=f"edit_data_aud_{prefix}_{id_audiencia}")
                with col2:
                    nova_sala = st.text_input("Sala", value=audiencia["sala"], key=f"edit_sala_{prefix}_{id_audiencia}")

                col1, col2 = st.columns(2)
                with col1:
                    nova_hora_ini = st.time_input("Hora Início", value=pd.to_datetime(audiencia["hora_inicio"]).time() if isinstance(audiencia["hora_inicio"], str) else audiencia["hora_inicio"], key=f"edit_hora_ini_{prefix}_{id_audiencia}")
                with col2:
                    nova_hora_fim = st.time_input("Hora Término", value=pd.to_datetime(audiencia["hora_termino"]).time() if isinstance(audiencia["hora_termino"], str) else audiencia["hora_termino"], key=f"edit_hora_fim_{prefix}_{id_audiencia}")

                col1, col2 = st.columns(2)
                with col1:
                    novo_formato = st.selectbox("Formato", FORMATOS_AUDIENCIA, index=FORMATOS_AUDIENCIA.index(audiencia["formato"]), key=f"edit_formato_{prefix}_{id_audiencia}")
                with col2:
                    novo_tipo = st.selectbox("Tipo", TIPOS_AUDIENCIA, index=TIPOS_AUDIENCIA.index(audiencia["tipo"]), key=f"edit_tipo_{prefix}_{id_audiencia}")

                nova_obs = st.text_area("Observações", value=audiencia["observacoes"] or "", height=100, key=f"edit_obs_{prefix}_{id_audiencia}")

                c1, c2 = st.columns(2)
                with c1:
                    if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                        atualizar_audiencia(id_audiencia, {
                            "data_audiencia": nova_data.isoformat(),
                            "hora_inicio": nova_hora_ini.isoformat(),
                            "hora_termino": nova_hora_fim.isoformat(),
                            "sala": nova_sala,
                            "formato": novo_formato,
                            "tipo": novo_tipo,
                            "observacoes": nova_obs or None
                        })
                        st.session_state.aviso = "✅ Audiência atualizada!"
                        st.session_state[modal_key_aberta] = False
                        st.rerun()
                with c2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state[modal_key_modo] = "detalhes"
                        st.rerun()

        elif st.session_state.get(modal_key_modo) == "confirmar_excluir":
            st.error("🔴 ATENÇÃO: Excluir é permanente!")
            st.write(f"**Processo:** {audiencia['processo']}")
            st.write(f"**Data:** {audiencia['data_audiencia'].strftime('%d/%m/%Y')} às {audiencia['hora_inicio']}")
            st.caption("⚠️ Esta ação NÃO pode ser desfeita!")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🗑️ SIM, Excluir", use_container_width=True, type="primary", key=f"btn_sim_excluir_{prefix}_{id_audiencia}"):
                    excluir_audiencia(id_audiencia)
                    st.session_state.aviso = "✅ Audiência excluída!"
                    st.session_state[modal_key_aberta] = False
                    st.rerun()
            with c2:
                if st.button("❌ NÃO, Cancelar", use_container_width=True, key=f"btn_nao_excluir_{prefix}_{id_audiencia}"):
                    st.session_state[modal_key_modo] = "detalhes"
                    st.rerun()

def main() -> None:
    init_estado()
    if not acesso_liberado():
        st.stop()

    try:
        df_prazos = carregar_prazos()
        df_processos = carregar_processos()
        df_audiencias = carregar_audiencias()
    except Exception as exc:
        st.error(f"Erro: {exc}")
        st.stop()

    with st.sidebar:
        st.title("⚖️ Controladoria")
        aba = st.radio("Opção:", ["Novo Prazo", "Nova Audiência", "Novo Processo", "Dashboard"], key="aba")
        st.divider()
        
        if st.button("🔄 Recarregar Dados", use_container_width=True):
            carregar_prazos.clear()
            carregar_processos.clear()
            carregar_audiencias.clear()
            st.rerun()
        
        st.divider()
        
        if aba == "Novo Prazo":
            sidebar_novo_prazo(df_processos)
        elif aba == "Nova Audiência":
            sidebar_nova_audiencia(df_processos)
        elif aba == "Novo Processo":
            st.subheader("⚖️ Novo Processo")
            v = st.session_state.form_v
            with st.form("proc"):
                numero = st.text_input("Nº CNJ *", value="", placeholder="0000000-00.0000.0.00.0000", key=f"pnumero_{v}")
                cliente = st.text_input("Cliente *", value="", key=f"pcliente_{v}")
                parte = st.text_input("Parte Adversária *", value="", key=f"pparte_{v}")
                descricao = st.text_area("Descrição", value="", key=f"pdesc_{v}")
                if st.form_submit_button("Salvar", type="primary"):
                    if numero and cliente and parte:
                        inserir_processo({"numero": numero, "cliente": cliente, "parte_contraria": parte, "descricao": descricao or None, "ativo": True})
                        # ===== LIMPAR FORMULÁRIO =====
                        st.session_state.form_v += 1
                        st.session_state.aviso = "✅ Processo salvo com sucesso!"
                        st.rerun()
                    else:
                        st.error("Preencha todos!")
        else:
            # ===== DASHBOARD COMPLETO =====
            dashboard_completo(df_prazos, df_audiencias, df_processos)

    st.title("⚖️ Controladoria Jurídica")
    st.caption(f"Hoje: {hoje():%d/%m/%Y}")

    if st.session_state.aviso:
        st.toast(st.session_state.aviso)
        st.session_state.aviso = None

    if df_prazos.empty:
        st.info("Nenhum prazo.")
        st.stop()

    df_prazos = enriquecer(df_prazos)
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📅 Prazos", "📋 Relatório", "📋 Pauta", "🔄 Desarquivar", "📋 Processos", "📅 Audiências"])

    with tab1:
        tabela_status(df_prazos[~df_prazos["arquivado"]], df_processos, prefix="tab_prazos")
    
    with tab2:
        st.subheader("📋 Relatório de Prazos")
        
        prazos_concluidos = df_prazos[df_prazos["concluido"]]
        prazos_arquivados = df_prazos[df_prazos["arquivado"]]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Concluídos", len(prazos_concluidos))
        col2.metric("📦 Arquivados", len(prazos_arquivados))
        col3.metric("🟢 Total", len(df_prazos))
        
        st.divider()
        st.markdown("**Prazos Concluídos:**")
        if prazos_concluidos.empty:
            st.info("Nenhum prazo concluído ainda.")
        else:
            cols_viz = ["titulo", "cliente", "data_fatal", "responsavel"]
            st.dataframe(prazos_concluidos[cols_viz], use_container_width=True, hide_index=True)
            
            # ===== BOTÃO PARA REATIVAR PRAZO CONCLUÍDO =====
            st.divider()
            st.subheader("🔄 Reativar Prazo")
            
            col1, col2 = st.columns([2, 1])
            id_reativar = col1.selectbox(
                "Selecione um prazo concluído para reativar:",
                options=prazos_concluidos["id"].values,
                format_func=lambda x: f"{prazos_concluidos[prazos_concluidos['id'] == x]['cliente'].values[0]} | {prazos_concluidos[prazos_concluidos['id'] == x]['titulo'].values[0]} | {prazos_concluidos[prazos_concluidos['id'] == x]['data_fatal'].values[0].strftime('%d/%m/%Y')}",
                key="sel_reativar"
            )
            
            if col2.button("🔄 Reativar", use_container_width=True, type="secondary"):
                atualizar_campos({id_reativar: {"concluido": False, "concluido_em": None}})
                st.session_state.aviso = "✅ Prazo reativado!"
                st.session_state.editor_v += 1
                st.rerun()
    
    with tab3:
        st.subheader("📋 Pauta de Prazos")
        
        # Filtrar prazos não arquivados e não concluídos
        prazos_ativos = df_prazos[~df_prazos["arquivado"] & ~df_prazos["concluido"]].copy()
        
        # Calcular datas (ANTES de usar)
        data_hoje = pd.Timestamp.now(tz="America/Sao_Paulo").date()
        data_semana = pd.Timestamp.now(tz="America/Sao_Paulo").date() + pd.Timedelta(days=7)
        
        if prazos_ativos.empty:
            st.info("✅ Nenhum prazo ativo no momento!")
        else:
            # Filtrar por período
            prazos_hoje = prazos_ativos[prazos_ativos["data_fatal"] == data_hoje]
            prazos_semana = prazos_ativos[(prazos_ativos["data_fatal"] > data_hoje) & (prazos_ativos["data_fatal"] <= data_semana)]
            prazos_futuro = prazos_ativos[prazos_ativos["data_fatal"] > data_semana]
            
            # Exibir HOJE
            if not prazos_hoje.empty:
                st.markdown("### 🔴 **HOJE** (" + data_hoje.strftime("%d/%m/%Y") + ")")
                for _, p in prazos_hoje.iterrows():
                    col1, col2 = st.columns([3, 1])
                    col1.markdown(f"""
                    **{p['titulo']}** | {p['cliente']} / {p.get('parte_contraria', 'N/A')}
                    
                    Responsável: {p['responsavel']} | Prioridade: {p['prioridade']}
                    """)
                st.divider()
            
            # Exibir PRÓXIMOS 7 DIAS
            if not prazos_semana.empty:
                st.markdown("### 🟠 **PRÓXIMOS 7 DIAS**")
                for _, p in prazos_semana.iterrows():
                    dias_faltam = (p['data_fatal'] - data_hoje).days
                    col1, col2 = st.columns([3, 1])
                    col1.markdown(f"""
                    **{p['titulo']}** | {p['cliente']} ({dias_faltam} dia{'s' if dias_faltam != 1 else ''})
                    
                    Data Fatal: {p['data_fatal'].strftime('%d/%m/%Y')} | Responsável: {p['responsavel']}
                    """)
                st.divider()
            
            # Exibir FUTURO
            if not prazos_futuro.empty:
                st.markdown("### 🟡 **FUTURO** (após 7 dias)")
                for _, p in prazos_futuro.iloc[:10].iterrows():  # Mostrar apenas os 10 primeiros
                    col1, col2 = st.columns([3, 1])
                    col1.markdown(f"""
                    **{p['titulo']}** | {p['cliente']}
                    
                    Data Fatal: {p['data_fatal'].strftime('%d/%m/%Y')} | Responsável: {p['responsavel']}
                    """)
        
        # Botões de exportação
        st.divider()
        st.subheader("📥 Exportar Pauta")
        
        # Gerar Excel bonito
        excel_path = gerar_excel_bonito(prazos_ativos, df_processos)
        
        if excel_path:
            with open(excel_path, "rb") as f:
                st.download_button(
                    label="📊 Baixar Pauta em Excel",
                    data=f.read(),
                    file_name=f"pauta_prazos_{data_hoje.strftime('%d_%m_%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        else:
            st.info("Sem dados para exportar")
    
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
    
    with tab5:
        gerenciar_processos(df_processos, df_prazos)

    with tab6:
        st.subheader("📅 Audiências Agendadas")

        if df_audiencias.empty:
            st.info("Nenhuma audiência agendada.")
        else:
            # Filtrar por status
            audiencias_agendadas = df_audiencias[df_audiencias["status"] == "Agendada"].sort_values("data_audiencia")
            audiencias_realizadas = df_audiencias[df_audiencias["status"] == "Realizada"].sort_values("data_audiencia", ascending=False)
            audiencias_canceladas = df_audiencias[df_audiencias["status"] == "Cancelada"].sort_values("data_audiencia", ascending=False)

            col1, col2, col3 = st.columns(3)
            col1.metric("📅 Agendadas", len(audiencias_agendadas))
            col2.metric("✅ Realizadas", len(audiencias_realizadas))
            col3.metric("❌ Canceladas", len(audiencias_canceladas))

            st.divider()

            # Abas por status
            aud_tab1, aud_tab2, aud_tab3 = st.tabs([
                f"📅 Agendadas ({len(audiencias_agendadas)})",
                f"✅ Realizadas ({len(audiencias_realizadas)})",
                f"❌ Canceladas ({len(audiencias_canceladas)})"
            ])

            with aud_tab1:
                if audiencias_agendadas.empty:
                    st.info("✅ Nenhuma audiência agendada!")
                else:
                    tabela_audiencias(audiencias_agendadas, prefix="tab_agendadas")

            with aud_tab2:
                if audiencias_realizadas.empty:
                    st.info("Nenhuma audiência realizada ainda.")
                else:
                    tabela_audiencias(audiencias_realizadas, prefix="tab_realizadas")

            with aud_tab3:
                if audiencias_canceladas.empty:
                    st.info("Nenhuma audiência cancelada.")
                else:
                    tabela_audiencias(audiencias_canceladas, prefix="tab_canceladas")

            # Exportar
            st.divider()
            st.subheader("📥 Exportar Audiências")

            excel_path = gerar_audiencias_excel(df_audiencias)

            if excel_path:
                with open(excel_path, "rb") as f:
                    st.download_button(
                        label="📊 Baixar Audiências em Excel",
                        data=f.read(),
                        file_name=f"audiencias_{hoje().strftime('%d_%m_%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

if __name__ == "__main__":
    main()
