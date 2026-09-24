"""
Controladoria Jurídica — Dr. Gilnei Coelho Pontes & Dra. Jéssica
Stack: Streamlit + Supabase

NOVA ESTRUTURA DA SIDEBAR:
1. Nº Processo (autocomplete) → puxa Cliente + Parte Adversária
2. Cliente e Parte Adversária (preenchidas automaticamente)
3. Tipo de Prazo (Prazo Processual, Data Fatal, Tarefa Operacional, Admin)
4. Título (seleção de atalhos jurídicos)
5. Responsável, Datas, Prioridade, Observações
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

# ───────────────────────── 1. Configuração ─────────────────────────
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

FERIADOS = np.array(
    [
        "2026-01-01", "2026-02-16", "2026-02-17", "2026-04-03", "2026-04-21",
        "2026-05-01", "2026-06-04", "2026-09-07", "2026-10-12", "2026-11-02",
        "2026-11-15", "2026-11-20", "2026-12-25",
    ],
    dtype="datetime64[D]",
)

CNJ_REGEX = re.compile(r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$")

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
    "CONTR-DOC": "Manifestação sobre Documentos (Réplica)",
    "RECONV": "Reconvenção",
    "IMP-VALI": "Impugnação ao Valor da Causa",
    "EX-INCOMP": "Exceção de Incompetência",
    "EX-PREEXEC": "Exceção de Pré-Executividade",
    "SPEC-PROV": "Especificação de Provas",
    "ROL-TEST": "Rol de Testemunhas",
    "QUESITOS": "Quesitos para Perícia",
    "QUES-TRAB": "Quesitos Trabalhistas (Médica/Engenharia)",
    "MANIFEST-LAUDO": "Manifestação sobre Laudo Pericial",
    "MANIFEST-PERIC": "Manifestação sobre Laudo Pericial",
    "MANIF": "Manifestação",
    "MEMORIAIS": "Alegações Finais / Memoriais",
    "RAZOES-FIN": "Razões Finais / Memoriais",
    "APEL": "Apelação",
    "CONTR-APEL": "Contrarrazões de Apelação",
    "RO": "Recurso Ordinário",
    "CONTR-RO": "Contrarrazões de Recurso Ordinário",
    "RR": "Recurso de Revista",
    "CONTR-RR": "Contrarrazões de Recurso de Revista",
    "AG-INST": "Agravo de Instrumento",
    "CONTR-AG": "Contraminuta de Agravo de Instrumento",
    "AIRO": "Agravo de Instrumento em Recurso Ordinário",
    "AG-INT": "Agravo Interno",
    "EMB-DECL": "Embargos de Declaração",
    "RESP": "Recurso Especial / Recurso Extraordinário",
    "RE": "Recurso Extraordinário",
    "CUMP-SENT": "Cumprimento de Sentença",
    "IMP-CUMP": "Impugnação ao Cumprimento de Sentença",
    "EX-EXEC": "Execução de Título Extrajudicial",
    "EMB-EXEC": "Embargos à Execução",
    "AG-PET": "Agravo de Petição",
    "CONTR-AG-PET": "Contrarrazões de Agravo de Petição",
    "EMB-EXEC-TRAB": "Embargos à Execução",
    "IMP-CALC": "Impugnação aos Cálculos",
    "MANIFEST-CALC": "Manifestação sobre Cálculos / Contador",
    "INDIC-BENS": "Indicação de Bens à Penhora",
    "PET-JUNT": "Petição de Juntada (Documentos/Procuração)",
    "TERMO-AUD": "Data de Audiência",
    "ACORDO": "Minuta / Termo de Acordo",
    "PED-SUSP": "Pedido de Suspensão / Sobreseimento",
    "PET-EXT": "Pedido de Extinção / Baixa",
    "ALVARA": "Requerimento de Expedição de Alvará",
}


def hoje() -> dt.date:
    return dt.datetime.now(TZ).date()


def init_estado() -> None:
    st.session_state.setdefault("form_v", 0)
    st.session_state.setdefault("editor_v", 0)
    st.session_state.setdefault("aviso", None)
    st.session_state.setdefault("id_arquivar_selecionado", None)


# ───────────────────────── 2. Acesso ─────────────────────────
def acesso_liberado() -> bool:
    """Se APP_PASSWORD existir nos secrets, exige senha antes de mostrar os dados."""
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


# ───────────────────────── 3. Camada de dados ─────────────────────────
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
    """Atualiza múltiplos campos de vários registros."""
    for id_prazo, campos in atualizacoes.items():
        if campos:
            supabase().table(TABELA_PRAZOS).update(campos).eq("id", id_prazo).execute()
    carregar_prazos.clear()


def arquivar_prazo(id_prazo: int) -> None:
    """Marca um prazo como arquivado."""
    supabase().table(TABELA_PRAZOS).update({"arquivado": True}).eq("id", id_prazo).execute()
    carregar_prazos.clear()


def desarquivar_prazo(id_prazo: int) -> None:
    """Remove o arquivo de um prazo."""
    supabase().table(TABELA_PRAZOS).update({"arquivado": False}).eq("id", id_prazo).execute()
    carregar_prazos.clear()


# ───────────────────────── 4. Regras de negócio ─────────────────────────
def enriquecer(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula dias restantes, dias úteis e a faixa de urgência de cada registro."""
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


def validar(titulo: str, processo: str, data_fatal, data_interna) -> list[str]:
    erros = []
    if not titulo.strip():
        erros.append("Informe o título.")
    if data_fatal is None:
        erros.append("Informe a data fatal.")
    if data_fatal and data_interna and data_interna > data_fatal:
        erros.append("O prazo interno precisa ser igual ou anterior à data fatal.")
    if processo.strip() and not CNJ_REGEX.match(processo.strip()):
        erros.append("Use o padrão CNJ no número do processo: 0000000-00.0000.0.00.0000.")
    return erros


# ───────────────────────── 5. SIDEBAR COM 3 ABAS ─────────────────────────

def sidebar_controle_prazos(processos_df: pd.DataFrame) -> None:
    """Aba 1: Controle de Prazos - NOVA ESTRUTURA
    
    Ordem:
    1. Nº Processo (autocomplete)
    2. Cliente e Parte Adversária (auto-puxadas)
    3. Tipo de Prazo
    4. Título (atalhos jurídicos)
    5. Responsável, Datas, Prioridade, Observações
    """
    st.subheader("📋 Novo Prazo")
    
    v = st.session_state.form_v
    
    with st.form(f"cadastro_{v}", border=False):
        # ===== 1. NÚMERO DO PROCESSO (autocomplete) =====
        processos_ativos = processos_df[processos_df["ativo"]]
        processos_lista = list(processos_ativos["numero"].values) if not processos_ativos.empty else []
        
        processo_selecionado = st.selectbox(
            "Nº do Processo *",
            options=processos_lista,
            key=f"processo_sel_{v}",
            help="Selecione o número CNJ do processo"
        )
        
        # ===== 2. CLIENTE E PARTE ADVERSÁRIA (puxadas automaticamente) =====
        if processo_selecionado and not processos_ativos.empty:
            info_processo = processos_ativos[processos_ativos["numero"] == processo_selecionado].iloc[0]
            cliente = info_processo["cliente"]
            parte_contraria = info_processo["parte_contraria"]
        else:
            cliente = ""
            parte_contraria = ""
        
        c1, c2 = st.columns(2)
        c1.text_input(
            "Cliente",
            value=cliente,
            disabled=True,
            key=f"cliente_readonly_{v}",
            help="Preenchido automaticamente"
        )
        c2.text_input(
            "Parte Adversária",
            value=parte_contraria,
            disabled=True,
            key=f"adversaria_readonly_{v}",
            help="Preenchido automaticamente"
        )
        
        # ===== 3. TIPO DE PRAZO =====
        tipo = st.selectbox(
            "Tipo de Prazo *",
            TIPOS,
            key=f"tipo_{v}",
            help="Escolha o tipo de prazo"
        )
        
        # ===== 4. TÍTULO (baseado em ATALHOS) =====
        st.write("**Título (Atalhos Jurídicos)**")
        titulo_atalho = st.selectbox(
            "Selecione o título/atalho *",
            options=list(sorted(ATALHOS.keys())),
            format_func=lambda x: f"{x} — {ATALHOS[x]}",
            key=f"titulo_atalho_{v}",
            help="Clique para ver todas as opções disponíveis"
        )
        
        titulo = ATALHOS[titulo_atalho]
        st.caption(f"📌 **{titulo}**")
        
        # ===== 5. RESPONSÁVEL =====
        responsavel = st.radio(
            "Responsável *",
            RESPONSAVEIS,
            horizontal=True,
            key=f"resp_{v}"
        )
        
        # ===== 6. DATAS =====
        c1, c2 = st.columns(2)
        data_fatal = c1.date_input(
            "Data Fatal *",
            value=None,
            format="DD/MM/YYYY",
            key=f"fatal_{v}"
        )
        data_interna = c2.date_input(
            "Prazo Interno",
            value=None,
            format="DD/MM/YYYY",
            key=f"int_{v}"
        )
        
        # ===== 7. PRIORIDADE =====
        prioridade = st.select_slider(
            "Prioridade",
            PRIORIDADES,
            value="Normal",
            key=f"prio_{v}"
        )
        
        # ===== 8. OBSERVAÇÕES =====
        descricao = st.text_area(
            "Observações",
            key=f"desc_{v}",
            height=80
        )
        
        enviar = st.form_submit_button("💾 Salvar Prazo", type="primary")

    if not enviar:
        return

    # Validações
    erros = []
    if not processo_selecionado:
        erros.append("Selecione o número do processo.")
    if not data_fatal:
        erros.append("Informe a data fatal.")
    if data_fatal and data_interna and data_interna > data_fatal:
        erros.append("O prazo interno precisa ser igual ou anterior à data fatal.")
    
    if erros:
        for e in erros:
            st.error(e)
        return

    # Salvar registro
    registro = {
        "tipo": tipo,
        "titulo": titulo.strip(),
        "processo": processo_selecionado,
        "cliente": cliente,
        "responsavel": responsavel,
        "data_fatal": data_fatal.isoformat(),
        "data_interna": data_interna.isoformat() if data_interna else None,
        "prioridade": prioridade,
        "descricao": descricao.strip() or None,
        "arquivado": False,
    }
    try:
        inserir_prazo(registro)
        st.session_state.aviso = f"✅ Prazo salvo: {titulo}"
        st.session_state.form_v += 1
        st.rerun()
    except Exception as exc:
        st.error(f"❌ Erro ao salvar: {exc}")


def sidebar_cadastro_processo() -> None:
    """Aba 2: Cadastro de Novo Processo"""
    st.subheader("⚖️ Novo Processo")
    
    v = st.session_state.form_v
    with st.form(f"proc_cadastro_{v}", border=False):
        numero = st.text_input(
            "Nº do Processo (CNJ) *",
            placeholder="0000000-00.0000.0.00.0000",
            key=f"proc_numero_{v}"
        )
        cliente = st.text_input(
            "Nome do Cliente *",
            placeholder="Nome exato conforme eproc/pje",
            key=f"proc_cliente_{v}"
        )
        parte_contraria = st.text_input(
            "Parte Contrária *",
            placeholder="Nome exato conforme eproc/pje",
            key=f"proc_parte_{v}"
        )
        descricao = st.text_area(
            "Descrição / Observações",
            key=f"proc_desc_{v}"
        )
        enviar = st.form_submit_button("💾 Salvar Processo", type="primary")

    if not enviar:
        return

    erros = []
    if not numero.strip():
        erros.append("Informe o número do processo.")
    if not cliente.strip():
        erros.append("Informe o nome do cliente.")
    if not parte_contraria.strip():
        erros.append("Informe o nome da parte contrária.")
    if numero.strip() and not CNJ_REGEX.match(numero.strip()):
        erros.append("Use o padrão CNJ: 0000000-00.0000.0.00.0000.")
    
    if erros:
        for e in erros:
            st.error(e)
        return

    registro = {
        "numero": numero.strip(),
        "cliente": cliente.strip(),
        "parte_contraria": parte_contraria.strip(),
        "descricao": descricao.strip() or None,
        "ativo": True,
    }
    try:
        inserir_processo(registro)
        st.session_state.aviso = f"✅ Processo salvo: {numero}"
        st.session_state.form_v += 1
        st.rerun()
    except Exception as exc:
        st.error(f"❌ Erro ao salvar: {exc}")


def sidebar_dashboard(df_prazos: pd.DataFrame) -> None:
    """Aba 3: Dashboard - Visão Geral Rápida"""
    st.subheader("📊 Dashboard - Visão Geral")
    
    if df_prazos.empty:
        st.info("Nenhum prazo cadastrado.")
        return
    
    df = enriquecer(df_prazos)
    pendentes = df[~df["concluido"] & ~df["arquivado"]]
    
    if pendentes.empty:
        st.success("✅ Nenhum prazo pendente!")
        return
    
    # Hoje
    st.write("**📅 HOJE**")
    vence_hoje = pendentes[pendentes["faixa"] == "Hoje"]
    col1, col2 = st.columns([1, 2])
    col1.metric("⏰ Vencem", len(vence_hoje))
    
    if not vence_hoje.empty:
        with col2:
            st.write("_Prazos que vencem hoje:_")
            for idx, row in vence_hoje.iterrows():
                st.write(f"🔴 **{row['titulo']}** ({row['responsavel']})")
    
    st.divider()
    
    # Próximos 7 dias
    st.write("**📆 PRÓXIMOS 7 DIAS**")
    vence_7 = pendentes[pendentes["faixa"].isin(["Até 3 dias", "Até 7 dias"])]
    st.metric("Próximos 7 dias", len(vence_7))
    
    st.divider()
    
    # Geral
    st.write("**📊 GERAL**")
    col1, col2, col3 = st.columns(3)
    vencidos = pendentes[pendentes["faixa"] == "Vencido"]
    col1.metric("🔴 Vencidos", len(vencidos))
    col2.metric("📋 Pendentes", len(pendentes))
    col3.metric("✅ Concluídos", len(df[df["concluido"] & ~df["arquivado"]]))


# ───────────────────────── 6. INTERFACE PRINCIPAL ─────────────────────────
def aplicar_filtros(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    c1, c2, c3, c4 = st.columns([1.2, 1.5, 1.3, 1.1])
    resp = c1.multiselect("Responsável", RESPONSAVEIS, default=RESPONSAVEIS)
    faixas = c2.multiselect(
        "Urgência", [k for k in FAIXAS if k != "Concluído"],
        format_func=FAIXAS.get, placeholder="Todas",
    )
    tipos = c3.multiselect("Tipo", TIPOS, placeholder="Todos")
    status = c4.radio("Status", ["Pendentes", "Concluídos", "Arquivados", "Todos"], horizontal=False)

    c5, c6 = st.columns([2, 1])
    busca = c5.text_input("Buscar", placeholder="Título, cliente ou nº do processo")
    periodo = c6.date_input("Data fatal entre", value=(), format="DD/MM/YYYY")

    resp = resp or RESPONSAVEIS
    m = df["responsavel"].isin(resp)
    if faixas:
        m &= df["faixa"].isin(faixas)
    if tipos:
        m &= df["tipo"].isin(tipos)
    
    if status == "Pendentes":
        m &= ~df["concluido"] & ~df["arquivado"]
    elif status == "Concluídos":
        m &= df["concluido"] & ~df["arquivado"]
    elif status == "Arquivados":
        m &= df["arquivado"]
    
    if len(periodo) == 2:
        m &= df["data_fatal"].between(periodo[0], periodo[1])
    if busca.strip():
        texto = (
            df["titulo"].fillna("") + " " + df["cliente"].fillna("") + " " + df["processo"].fillna("")
        ).str.lower()
        m &= texto.str.contains(busca.strip().lower(), regex=False)

    return df[m], resp


def painel_metricas(df: pd.DataFrame, resp: list[str]) -> None:
    pend = df[~df["concluido"] & ~df["arquivado"] & df["responsavel"].isin(resp)]
    vencidos = int((pend["faixa"] == "Vencido").sum())
    c = st.columns(4)
    c[0].metric("🔴 Vencidos", vencidos)
    c[1].metric("🟠 Hoje", int((pend["faixa"] == "Hoje").sum()))
    c[2].metric("🔵 Próx. 7d", int(pend["faixa"].isin(["Até 3 dias", "Até 7 dias"]).sum()))
    c[3].metric("📋 Pendentes", len(pend))
    if vencidos:
        st.error(f"⚠️ {vencidos} prazo(s) vencido(s)! Ação necessária.")


def tabela_status(df: pd.DataFrame) -> None:
    """
    Tabela de prazos com MODAL ao clicar checkbox:
    
    Fluxo:
    1. Clica checkbox ✅ → Abre janela com opções
    2. "Editar" → Abre campos de data + recalcula situação
    3. "Arquivar" → Pede confirmação → Arquiva
    4. "Cancelar" → Fecha tudo
    """
    if df.empty:
        st.info("Nenhum registro com esses filtros.")
        return

    # ===== ESTADO DA MODAL =====
    if "modal_aberta" not in st.session_state:
        st.session_state.modal_aberta = False
    if "id_modal" not in st.session_state:
        st.session_state.id_modal = None
    if "modo_modal" not in st.session_state:
        st.session_state.modo_modal = None  # None, "editar" ou "confirmar_arquivar"
    if "ultima_mudanca_processada" not in st.session_state:
        st.session_state.ultima_mudanca_processada = None

    colunas_vis = [
        "id", "concluido", "situacao", "titulo", "processo", "cliente", "data_fatal",
        "data_interna", "dias_uteis", "tipo", "responsavel", "prioridade", "descricao",
    ]
    vis = (
        df.assign(_p=df["prioridade"].map(ORDEM_PRIORIDADE))
        .sort_values(["concluido", "data_fatal", "_p"])[colunas_vis]
        .set_index("id")
    )

    # ===== TABELA EDITÁVEL (sem checkbox de conclusão) =====
    editado = st.data_editor(
        vis,
        key=f"editor_{st.session_state.editor_v}",
        hide_index=True,
        disabled=["situacao", "dias_uteis", "tipo", "responsavel", "concluido"],
        column_config={
            "concluido": st.column_config.CheckboxColumn(
                "✅",
                help="Clique para abrir opções (Editar ou Arquivar)"
            ),
            "situacao": "Situação",
            "titulo": st.column_config.TextColumn("Título", width="medium"),
            "processo": st.column_config.TextColumn("Processo", width="small"),
            "cliente": st.column_config.TextColumn("Cliente", width="small"),
            "data_fatal": st.column_config.DateColumn(
                "📅 Data Fatal",
                format="DD/MM/YYYY",
            ),
            "data_interna": st.column_config.DateColumn(
                "📅 Prazo Interno",
                format="DD/MM/YYYY",
            ),
            "dias_uteis": st.column_config.NumberColumn("D.Úteis"),
            "tipo": "Tipo",
            "responsavel": "Resp.",
            "prioridade": st.column_config.SelectboxColumn("Prio.", options=PRIORIDADES),
            "descricao": st.column_config.TextColumn("Observações", width="large"),
        },
    )

    # ===== DETECTAR CLIQUE NO CHECKBOX =====
    for idx in editado.index:
        id_linha = int(idx)
        if editado.loc[idx, "concluido"] != vis.loc[idx, "concluido"]:
            # Checkbox mudou! Mas só processa se não foi já processado
            if st.session_state.ultima_mudanca_processada != id_linha:
                st.session_state.modal_aberta = True
                st.session_state.id_modal = id_linha
                st.session_state.modo_modal = None
                st.session_state.ultima_mudanca_processada = id_linha  # Marca como processado
                st.rerun()

    # ===== MODAL/DIALOG =====
    if st.session_state.modal_aberta and st.session_state.id_modal:
        id_prazo = st.session_state.id_modal
        prazo = df[df["id"] == id_prazo].iloc[0]
        
        st.divider()
        st.subheader(f"⚙️ Gerenciar Prazo: {prazo['titulo']}")
        
        # MENU PRINCIPAL DA MODAL
        if st.session_state.modo_modal is None:
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if st.button("✏️ Editar", use_container_width=True, type="secondary"):
                    st.session_state.modo_modal = "editar"
                    st.rerun()
            
            with col2:
                if st.button("📦 Arquivar", use_container_width=True, type="secondary"):
                    st.session_state.modo_modal = "confirmar_arquivar"
                    st.rerun()
            
            with col3:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.session_state.modal_aberta = False
                    st.session_state.id_modal = None
                    st.session_state.modo_modal = None
                    st.session_state.ultima_mudanca_processada = None  # Limpar flag
                    st.rerun()

        # MODO EDITAR
        elif st.session_state.modo_modal == "editar":
            st.write(f"**Editando:** {prazo['titulo']}")
            
            with st.form(f"form_editar_{id_prazo}", border=True):
                st.write("Altere as datas e a situação recalculará automaticamente:")
                
                col1, col2 = st.columns(2)
                nova_data_fatal = col1.date_input(
                    "Data Fatal",
                    value=prazo["data_fatal"],
                    format="DD/MM/YYYY",
                    key=f"edit_fatal_{id_prazo}"
                )
                nova_data_interna = col2.date_input(
                    "Prazo Interno",
                    value=prazo["data_interna"],
                    format="DD/MM/YYYY",
                    key=f"edit_interna_{id_prazo}"
                )
                
                # Preview da situação nova
                if nova_data_fatal:
                    ref = np.datetime64(hoje())
                    fatal = np.datetime64(nova_data_fatal)
                    dias_corridos = (fatal - ref).astype(int)
                    dias_uteis = np.busday_count(ref, fatal, holidays=FERIADOS)
                    
                    # Calcular faixa
                    if dias_corridos < 0:
                        faixa_nova = "Vencido"
                        situacao_nova = "🔴 Vencido"
                    elif dias_corridos == 0:
                        faixa_nova = "Hoje"
                        situacao_nova = "🟠 Vence hoje"
                    elif dias_corridos <= 3:
                        faixa_nova = "Até 3 dias"
                        situacao_nova = "🟡 Até 3 dias"
                    elif dias_corridos <= 7:
                        faixa_nova = "Até 7 dias"
                        situacao_nova = "🔵 Até 7 dias"
                    else:
                        faixa_nova = "Futuro"
                        situacao_nova = "🟢 Mais de 7 dias"
                    
                    st.info(f"📊 Nova Situação: **{situacao_nova}** | Dias úteis: **{dias_uteis}**")
                
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    salvar_editar = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)
                with c2:
                    voltar_editar = st.form_submit_button("⬅️ Voltar", use_container_width=True)
                with c3:
                    st.write("")  # Espaço

            if salvar_editar:
                # Validar
                erros = []
                if nova_data_fatal is None:
                    erros.append("Data fatal é obrigatória.")
                if nova_data_fatal and nova_data_interna and nova_data_interna > nova_data_fatal:
                    erros.append("Prazo interno deve ser igual ou anterior à data fatal.")
                
                if erros:
                    for e in erros:
                        st.error(e)
                else:
                    # Salvar mudanças
                    mudancas = {
                        id_prazo: {
                            "data_fatal": nova_data_fatal.isoformat(),
                            "data_interna": nova_data_interna.isoformat() if nova_data_interna else None,
                        }
                    }
                    try:
                        atualizar_campos(mudancas)
                        st.session_state.aviso = f"✅ Datas atualizadas! Situação recalculada."
                        st.session_state.modal_aberta = False
                        st.session_state.id_modal = None
                        st.session_state.modo_modal = None
                        st.session_state.ultima_mudanca_processada = None  # Limpar flag
                        st.session_state.editor_v += 1
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Erro ao salvar: {exc}")
            
            if voltar_editar:
                st.session_state.modo_modal = None
                st.session_state.ultima_mudanca_processada = None  # Limpar flag
                st.rerun()

        # MODO CONFIRMAR ARQUIVAMENTO
        elif st.session_state.modo_modal == "confirmar_arquivar":
            st.warning("⚠️ Tem certeza que deseja arquivar este prazo?")
            st.write(f"**{prazo['titulo']}** | {prazo['processo']} | {prazo['data_fatal'].strftime('%d/%m/%Y')}")
            
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if st.button("✅ SIM, Arquivar", use_container_width=True, type="primary"):
                    try:
                        arquivar_prazo(id_prazo)
                        st.session_state.aviso = "✅ Prazo arquivado com sucesso!"
                        st.session_state.modal_aberta = False
                        st.session_state.id_modal = None
                        st.session_state.modo_modal = None
                        st.session_state.ultima_mudanca_processada = None  # Limpar flag
                        st.session_state.editor_v += 1
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Erro ao arquivar: {exc}")
            
            with col2:
                if st.button("❌ NÃO, Cancelar", use_container_width=True):
                    st.session_state.modo_modal = None
                    st.session_state.ultima_mudanca_processada = None  # Limpar flag
                    st.rerun()
            
            with col3:
                st.write("")  # Espaço

    # ===== EDITAR OUTROS CAMPOS (sem checkbox) =====
    st.divider()
    st.subheader("📝 Editar outros dados")
    
    mudancas = {}
    for idx in editado.index:
        alterado = {}
        
        if editado.loc[idx, "titulo"] != vis.loc[idx, "titulo"]:
            alterado["titulo"] = editado.loc[idx, "titulo"].strip() or None
        if editado.loc[idx, "processo"] != vis.loc[idx, "processo"]:
            alterado["processo"] = editado.loc[idx, "processo"].strip() or None
        if editado.loc[idx, "cliente"] != vis.loc[idx, "cliente"]:
            alterado["cliente"] = editado.loc[idx, "cliente"].strip() or None
        if editado.loc[idx, "prioridade"] != vis.loc[idx, "prioridade"]:
            alterado["prioridade"] = editado.loc[idx, "prioridade"]
        if editado.loc[idx, "descricao"] != vis.loc[idx, "descricao"]:
            alterado["descricao"] = editado.loc[idx, "descricao"].strip() or None
        
        if alterado:
            mudancas[int(idx)] = alterado

    if mudancas:
        c1, c2 = st.columns([3, 1])
        c1.warning(f"⚠️ Alterações não salvas: {len(mudancas)} prazo(s).")
        if c2.button("💾 Salvar tudo", type="primary"):
            try:
                atualizar_campos(mudancas)
                st.session_state.aviso = "✅ Prazos salvos!"
                st.session_state.editor_v += 1
                st.rerun()
            except Exception as exc:
                st.error(f"❌ Erro: {exc}")


def relatorio_arquivados(df: pd.DataFrame) -> None:
    """Relatório de arquivados"""
    arquivados = df[df["arquivado"]]
    
    if arquivados.empty:
        st.info("Nenhum prazo arquivado.")
        return
    
    st.subheader(f"📋 Relatório de Arquivados ({len(arquivados)})")
    
    colunas_rel = ["id", "titulo", "processo", "cliente", "responsavel", "data_fatal", "concluido_em", "prioridade"]
    rel = arquivados[colunas_rel].copy()
    rel = rel.rename(columns={
        "id": "ID", "titulo": "Título", "processo": "Processo", "cliente": "Cliente",
        "responsavel": "Responsável", "data_fatal": "Data Fatal", "concluido_em": "Concluído em", "prioridade": "Prioridade"
    })
    
    st.dataframe(rel, use_container_width=True, hide_index=True)


def aba_desarquivar(df: pd.DataFrame) -> None:
    """Aba de desarquivar"""
    arquivados = df[df["arquivado"]]
    
    if arquivados.empty:
        st.info("Nenhum prazo arquivado.")
        return
    
    st.subheader("🔄 Desarquivar prazo")
    st.write(f"Total de arquivados: **{len(arquivados)}**")
    st.divider()
    
    col1, col2 = st.columns([2, 1])
    
    id_desarquivar = col1.selectbox(
        "Selecione o prazo para desarquivar",
        options=arquivados["id"].values,
        format_func=lambda x: f"{arquivados[arquivados['id'] == x]['titulo'].values[0]} | {arquivados[arquivados['id'] == x]['processo'].values[0] or '-'} | {arquivados[arquivados['id'] == x]['data_fatal'].values[0].strftime('%d/%m/%Y')}",
        key="select_desarquivar"
    )
    
    if col2.button("🔄 Desarquivar", type="secondary", key="btn_desarquivar"):
        try:
            desarquivar_prazo(id_desarquivar)
            st.session_state.aviso = "✅ Prazo desarquivado!"
            st.session_state.editor_v += 1
            st.rerun()
        except Exception as exc:
            st.error(f"❌ Erro: {exc}")


def main() -> None:
    init_estado()
    if not acesso_liberado():
        st.stop()

    try:
        df_prazos = carregar_prazos()
        df_processos = carregar_processos()
    except Exception as exc:
        st.error(f"❌ Erro ao conectar ao Supabase: {exc}")
        st.stop()

    # ===== SIDEBAR COM 3 ABAS =====
    with st.sidebar:
        st.title("⚖️ Controladoria")
        
        aba = st.radio(
            "📌 Escolha uma opção:",
            ["Controle de Prazos", "Cadastro de Novo Processo", "Dashboard"],
            key="aba_sidebar"
        )
        
        st.divider()
        
        if aba == "Controle de Prazos":
            sidebar_controle_prazos(df_processos)
        elif aba == "Cadastro de Novo Processo":
            sidebar_cadastro_processo()
        elif aba == "Dashboard":
            sidebar_dashboard(df_prazos)
        
        st.divider()
        if st.button("🔄 Recarregar dados"):
            carregar_prazos.clear()
            carregar_processos.clear()
            st.rerun()

    # ===== CONTEÚDO PRINCIPAL =====
    st.title("⚖️ Controladoria Jurídica")
    st.caption(f"📅 Hoje é {hoje():%d/%m/%Y} (horário de Brasília)")

    if st.session_state.aviso:
        st.toast(st.session_state.aviso, icon="✅")
        st.session_state.aviso = None

    if df_prazos.empty:
        st.info("Nenhum prazo cadastrado ainda. Use a sidebar para adicionar!")
        st.stop()

    df_prazos = enriquecer(df_prazos)
    
    tab1, tab2, tab3 = st.tabs(["📅 Prazos", "📋 Relatório", "🔄 Desarquivar"])
    
    with tab1:
        topo = st.container()
        with st.expander("🔍 Filtros", expanded=True):
            filtrado, resp = aplicar_filtros(df_prazos)
        with topo:
            painel_metricas(df_prazos, resp)

        st.subheader(f"📋 Prazos e tarefas ({len(filtrado)})")
        tabela_status(filtrado)
    
    with tab2:
        relatorio_arquivados(df_prazos)
    
    with tab3:
        aba_desarquivar(df_prazos)


if __name__ == "__main__":
    main()
