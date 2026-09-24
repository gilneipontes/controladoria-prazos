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

def gerar_pdf_pauta(df_prazos: pd.DataFrame):
    """Gera PDF com pauta de prazos"""
    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='CustomTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1f4788'), spaceAfter=12)
    heading_style = ParagraphStyle(name='CustomHeading', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#c7302d'), spaceAfter=8)
    
    # Elementos
    elements = []
    
    # Título
    elements.append(Paragraph("CONTROLADORIA JURÍDICA - PAUTA DE PRAZOS", title_style))
    data_hoje = pd.Timestamp.now(tz="America/Sao_Paulo").date()
    elements.append(Paragraph(f"Data: {data_hoje.strftime('%d de %B de %Y')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    if df_prazos.empty:
        elements.append(Paragraph("✅ Nenhum prazo ativo no momento.", styles['Normal']))
    else:
        # Separar por período
        prazos_hoje = df_prazos[df_prazos["data_fatal"] == data_hoje]
        semana = hoje + pd.Timedelta(days=7)
        prazos_semana = df_prazos[(df_prazos["data_fatal"] > data_hoje) & (df_prazos["data_fatal"] <= data_semana)]
        
        # HOJE
        if not prazos_hoje.empty:
            elements.append(Paragraph("🔴 HOJE", heading_style))
            data_hoje = [["TÍTULO", "CLIENTE", "RESPONSÁVEL", "PRIORIDADE"]]
            for _, p in prazos_hoje.iterrows():
                data_hoje.append([
                    p['titulo'],
                    p['cliente'][:30],  # Limitar a 30 caracteres
                    p['responsavel'],
                    p['prioridade']
                ])
            table = Table(data_hoje, colWidths=[1.8*inch, 1.5*inch, 1.2*inch, 0.8*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c7302d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2*inch))
        
        # PRÓXIMOS 7 DIAS
        if not prazos_semana.empty:
            elements.append(Paragraph("🟠 PRÓXIMOS 7 DIAS", heading_style))
            data_semana = [["TÍTULO", "CLIENTE", "DATA FATAL", "RESPONSÁVEL"]]
            for _, p in prazos_semana.iterrows():
                data_semana.append([
                    p['titulo'],
                    p['cliente'][:25],
                    p['data_fatal'].strftime('%d/%m'),
                    p['responsavel']
                ])
            table = Table(data_semana, colWidths=[1.8*inch, 1.5*inch, 1*inch, 1.2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ff9900')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table)
    
    # Gerar PDF
    doc.build(elements)
    buffer.seek(0)
    
    # Salvar em arquivo temporário
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(buffer.getvalue())
        return tmp.name

def gerar_excel_pauta(df_prazos: pd.DataFrame):
    """Gera Excel com pauta de prazos"""
    import tempfile
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Pauta"
    
    data_hoje = pd.Timestamp.now(tz="America/Sao_Paulo").date()
    
    # Cabeçalho
    ws['A1'] = "CONTROLADORIA JURÍDICA - PAUTA DE PRAZOS"
    ws['A1'].font = Font(size=14, bold=True, color="FFFFFF")
    ws['A1'].fill = PatternFill(start_color="1f4788", end_color="1f4788", fill_type="solid")
    ws.merge_cells('A1:E1')
    
    ws['A2'] = f"Data: {data_hoje.strftime('%d/%m/%Y')}"
    ws.merge_cells('A2:E2')
    
    # Cabeçalhos das colunas
    headers = ["DATA FATAL", "TÍTULO", "CLIENTE", "RESPONSÁVEL", "PRIORIDADE", "DIAS PARA VENCER"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col)
        cell.value = header
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="c7302d", end_color="c7302d", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Dados
    row = 5
    if not df_prazos.empty:
        df_sorted = df_prazos.sort_values("data_fatal")
        for _, p in df_sorted.iterrows():
            dias = (p['data_fatal'] - hoje).days
            ws.cell(row=row, column=1).value = p['data_fatal'].strftime("%d/%m/%Y")
            ws.cell(row=row, column=2).value = p['titulo']
            ws.cell(row=row, column=3).value = p['cliente']
            ws.cell(row=row, column=4).value = p['responsavel']
            ws.cell(row=row, column=5).value = p['prioridade']
            ws.cell(row=row, column=6).value = f"{dias} dia{'s' if dias != 1 else ''}"
            row += 1
    
    # Ajustar largura das colunas
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 15
    
    # Salvar em arquivo temporário
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        wb.save(tmp.name)
        return tmp.name

def tabela_status(df: pd.DataFrame, processos_df: pd.DataFrame = None) -> None:
    if df.empty:
        st.info("Nenhum registro.")
        return

    df_vis = df.copy()
    
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
        key="sel_prazo_idx"
    )

    if col2.button("📂 Ver Detalhes", use_container_width=True, type="primary"):
        if st.session_state.get("sel_prazo_idx", 0) > 0:  # Índice 0 é a opção vazia
            id_sel = opcoes_ids[st.session_state.sel_prazo_idx]
            st.session_state.id_modal = id_sel
            st.session_state.modo_modal = "detalhes"
            st.session_state.modal_aberta = True
            st.rerun()
        else:
            st.warning("⚠️ Selecione um prazo primeiro!")

    if st.session_state.modal_aberta and st.session_state.id_modal:
        id_prazo = st.session_state.id_modal
        prazo = df[df["id"] == id_prazo].iloc[0]
        
        st.divider()
        st.subheader(f"⚙️ {prazo['titulo']}")
        
        # ===== MODAL DE DETALHES DO PRAZO =====
        if st.session_state.modo_modal == "detalhes":
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
                if st.button("✏️ Editar Prazo", use_container_width=True, type="secondary"):
                    st.session_state.modo_modal = "editar"
                    st.rerun()
            
            with col2:
                if st.button("✅ Concluído", use_container_width=True, type="primary"):
                    st.session_state.modo_modal = "concluir_com_obs"
                    st.rerun()
            
            with col3:
                if st.button("📦 Arquivar", use_container_width=True, type="secondary"):
                    st.session_state.modo_modal = "confirmar_arquivar"
                    st.rerun()
            
            with col4:
                if st.button("❌ Excluir", use_container_width=True, type="secondary"):
                    st.session_state.modo_modal = "confirmar_excluir"
                    st.rerun()
            
            st.divider()
            col_fechar = st.columns([3, 1])
            with col_fechar[1]:
                if st.button("🔙 Fechar", use_container_width=True, type="secondary"):
                    st.session_state.modal_aberta = False
                    st.session_state.modo_modal = None
                    st.rerun()
        
        elif st.session_state.modo_modal == "editar":
            with st.form(f"form_{id_prazo}"):
                # ===== EDITAR TODOS OS CAMPOS =====
                novo_titulo = st.text_input("Título", value=prazo["titulo"], key=f"edit_titulo_{id_prazo}")
                
                col1, col2 = st.columns(2)
                with col1:
                    novo_responsavel = st.selectbox("Responsável", RESPONSAVEIS, index=RESPONSAVEIS.index(prazo["responsavel"]), key=f"edit_resp_{id_prazo}")
                with col2:
                    nova_prioridade = st.selectbox("Prioridade", PRIORIDADES, index=PRIORIDADES.index(prazo["prioridade"]), key=f"edit_prio_{id_prazo}")
                
                col1, col2 = st.columns(2)
                nova_interna = col1.date_input("Prazo Interno", value=prazo["data_interna"], format="DD/MM/YYYY", key=f"edit_interna_{id_prazo}")
                nova_fatal = col2.date_input("Data Fatal", value=prazo["data_fatal"], format="DD/MM/YYYY", key=f"edit_fatal_{id_prazo}")
                
                nova_descricao = st.text_area("Observações", value=prazo["descricao"] or "", key=f"edit_desc_{id_prazo}")
                
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
                        st.session_state.modal_aberta = False
                        st.session_state.editor_v += 1
                        st.rerun()
                with c2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.modo_modal = "detalhes"
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
                    st.session_state.modo_modal = "detalhes"
                    st.rerun()
        
        elif st.session_state.modo_modal == "concluir_com_obs":
            st.warning("📝 Adicione anotações sobre este prazo antes de concluir")
            st.write(f"**Cliente:** {prazo['cliente']}")
            st.write(f"**Título (Prazo):** {prazo['titulo']}")
            
            with st.form(f"form_concluir_{id_prazo}"):
                anotacoes = st.text_area(
                    "O que foi feito neste prazo?",
                    placeholder="Ex: Petição inicial enviada com documentos anexados...",
                    height=120,
                    key=f"anol_{id_prazo}"
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
                        st.session_state.modal_aberta = False
                        
                        st.session_state.editor_v += 1
                        st.rerun()
                
                with c2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.modo_modal = "detalhes"
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
                    st.session_state.modo_modal = "detalhes"
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
        tipo = st.selectbox("Tipo *", TIPOS, key=f"t_{v}")
        
        responsavel = st.radio("Responsável *", RESPONSAVEIS, horizontal=True, key=f"r_{v}")
        c1, c2 = st.columns(2)
        data_interna = c1.date_input("Prazo Interno", value=None, format="DD/MM/YYYY", key=f"i_{v}")
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
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Prazos", "📋 Relatório", "📋 Pauta", "🔄 Desarquivar", "📋 Processos"])
    
    with tab1:
        tabela_status(df_prazos[~df_prazos["arquivado"]], df_processos)
    
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
        
        if prazos_ativos.empty:
            st.info("✅ Nenhum prazo ativo no momento!")
        else:
            # Calcular datas
            data_data_hoje = pd.Timestamp.now(tz="America/Sao_Paulo").date()
            data_semana = pd.Timestamp.now(tz="America/Sao_Paulo").date() + pd.Timedelta(days=7)
            
            # Filtrar por período
            prazos_hoje = prazos_ativos[prazos_ativos["data_fatal"] == data_hoje]
            prazos_semana = prazos_ativos[(prazos_ativos["data_fatal"] > data_hoje) & (prazos_ativos["data_fatal"] <= data_semana)]
            prazos_futuro = prazos_ativos[prazos_ativos["data_fatal"] > data_semana]
            
            # Exibir HOJE
            if not prazos_hoje.empty:
                st.markdown("### 🔴 **HOJE** (" + data_data_hoje.strftime("%d/%m/%Y") + ")")
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
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📄 Exportar como PDF", use_container_width=True):
                # Gerar PDF
                pdf_path = gerar_pdf_pauta(prazos_ativos)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Baixar PDF",
                        data=f.read(),
                        file_name=f"pauta_prazos_{data_data_hoje.strftime('%d_%m_%Y')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
        
        with col2:
            if st.button("📊 Exportar como Excel", use_container_width=True):
                # Gerar Excel
                excel_path = gerar_excel_pauta(prazos_ativos)
                with open(excel_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Baixar Excel",
                        data=f.read(),
                        file_name=f"pauta_prazos_{data_data_hoje.strftime('%d_%m_%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
    
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

if __name__ == "__main__":
    main()
