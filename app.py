"""
Controladoria Jurídica - SEMANA 1 EM PROGRESSO
PASSO 1: Cards com cores dinâmicas ✅
PASSO 2: Visão Cards Hierárquica ✅
PASSO 3: Modal com Ficha Integral do Cliente (3 abas) ✅
PASSO 4: Tabela de Auditoria - EM CONSTRUÇÃO
PASSO 5: Ações rápidas dentro do Modal - EM CONSTRUÇÃO
PASSO 6: Visão Calendário/Agenda - EM CONSTRUÇÃO
"""
# ============================================
# CONTROLADORIA JURÍDICA - SISTEMA DE PRAZOS
# Versão: 4.0 - SEMANA 1 EM PROGRESSO - 28/09/2026
# PASSOS IMPLEMENTADOS: 1, 2, 3
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

# Advogados responsáveis. Cada escritório pode definir os seus no Streamlit
# (Settings → Secrets), com uma linha assim:  RESPONSAVEIS = ["Dr. Fulano", "Dra. Beltrana"]
# Se não definir, usa a lista abaixo.
RESPONSAVEIS_PADRAO = ["Dr. Gilnei", "Dra. Jéssica"]
try:
    RESPONSAVEIS = [str(n).strip() for n in st.secrets.get("RESPONSAVEIS", RESPONSAVEIS_PADRAO) if str(n).strip()]
except Exception:
    RESPONSAVEIS = list(RESPONSAVEIS_PADRAO)
if not RESPONSAVEIS:
    RESPONSAVEIS = list(RESPONSAVEIS_PADRAO)
TIPOS = ["Prazo Processual", "Data Fatal", "Tarefa Operacional", "Admin"]
PRIORIDADES = ["Baixa", "Normal", "Alta"]
ORDEM_PRIORIDADE = {"Alta": 0, "Normal": 1, "Baixa": 2}

# ===== FASES DO PROCESSO =====
FASES_PROCESSO = [
    "Fase de Conhecimento",
    "Fase de Cumprimento de Sentença",
    "Fase de Recursos",
    "Fase de Execução",
]

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

COLUNAS_PROCESSOS = ["id", "created_at", "numero", "cliente", "parte_contraria", "descricao", "fase", "ativo"]

COLUNAS_AUDIENCIAS = [
    "id", "created_at", "processo", "autor", "reu", "sala", "data_audiencia",
    "hora_inicio", "hora_termino", "formato", "tipo", "status", "observacoes", "responsavel"
]

FORMATOS_AUDIENCIA = ["Presencial", "Virtual"]
TIPOS_AUDIENCIA = ["Inicial", "Continuação", "Sentença", "Outra"]
STATUS_AUDIENCIA = ["Agendada", "Realizada", "Cancelada"]

# ===== ATALHOS DE TÍTULO (lista que aparece na busca do "Novo Prazo") =====
ATALHOS = {
    "RECL-TRAB": "Reclamação Trabalhista (Inicial)",
    "CONT-TRAB": "Contestação Trabalhista",
    "CONT-CIV": "Contestação Cível",
    "RECONV": "Reconvenção",
    "REPLICA": "Réplica",
    "EMB-EXEC": "Embargos à Execução",
    "ADJUD-COMP": "Adjudicação Compulsória",
    "USUCAPIÃO": "Ação de Usucapião",
    "INVENTÁRIO": "Ação de Inventário e Partilha",
    "MANIF-LAUDO": "Manifestação sobre Laudo Pericial",
    "SPEC-PROV": "Especificação de Provas",
    "AUD-INICIAL": "Audiência Trabalhista (Inicial / Una)",
    "AUD-INSTR": "Audiência de Instrução",
    "AUD-CONC": "Audiência de Conciliação / Mediação (Art. 334 CPC)",
    "RAZ-FIN": "Razões Finais (Memoriais)",
    "IMP-JUST": "Impugnação à Justiça Gratuita",
    "IMP-VAL": "Impugnação ao Valor da Causa",
    "IMP-CUMP": "Impugnação ao Cumprimento de Sentença",
    "CALC-LIQ": "Manifestação sobre Cálculos de Liquidação",
    "IMP-CALC-879": "Impugnação de Cálculos (Art. 879, § 2º CLT)",
    "APELAÇÃO": "Apelação Cível",
    "CONTR-APEL": "Contrarrazões de Apelação",
    "REC-ORD": "Recurso Ordinário (RO)",
    "CONTR-RO": "Contrarrazões ao Recurso Ordinário (RO)",
    "REC-REV": "Recurso de Revista (RR)",
    "CONTR-RR": "Contrarrazões ao Recurso de Revista (RR)",
    "AG-INSTR": "Agravo de Instrumento",
    "CONTR-AG-INSTR": "Contrarrazões ao Agravo de Instrumento",
    "AG-PET": "Agravo de Petição (Fase de Execução)",
    "AG-INT": "Agravo Interno",
    "CONTR-AG-INT": "Contrarrazões ao Agravo Interno",
    "EMB-DECL": "Embargos de Declaração",
    "EMB-DECL-TRAB": "Embargos de Declaração Trabalhista",
    "RECURSO-ESP": "Recurso Especial (REsp)",
    "RECURSO-EXT": "Recurso Extraordinário (RExt)",
}

# Títulos usados só pelo "Colar Despacho" quando a peça não está na lista acima
TITULOS_EXTRAS_DESPACHO = {
    "CONTR-AG": "Contraminuta de Agravo",
    "EMEND-INI": "Emenda à Petição Inicial",
    "ROL-TEST": "Rol de Testemunhas",
    "QUESITOS": "Quesitos para Perícia",
    "MANIFEST-LAUDO": "Manifestação sobre Laudo",
    "IMP-CALC": "Impugnação aos Cálculos",
    "CONTR-DOC": "Manifestação sobre Documentos",
    "INDIC-BENS": "Indicação de Bens",
    "CUMP-SENT": "Cumprimento de Sentença",
    "TERMO-AUD": "Data de Audiência",
    "ALVARA": "Expedição de Alvará",
    "ACORDO": "Termo de Acordo",
    "PED-SUSP": "Pedido de Suspensão",
    "PET-JUNT": "Petição de Juntada",
    "MANIF": "Manifestação",
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
    st.session_state.setdefault("aba_selecionada", "🏠 Início")
    # Controle para recolher a barra lateral só uma vez por cliente selecionado
    st.session_state.setdefault("sidebar_recolhida_para", None)
    # ===== PASSO 4 E 5: FILTROS POR RESPONSÁVEL =====
    st.session_state.setdefault("filtro_tab1", "Todos")
    st.session_state.setdefault("filtro_tab2", "Todos")
    st.session_state.setdefault("filtro_gerenciar", "Todos")

def acesso_liberado() -> bool:
    senha_correta = st.secrets.get("APP_PASSWORD")

    if not senha_correta:
        st.title("⚖️ Controladoria Jurídica")
        st.error("🔴 ERRO: APP_PASSWORD não configurada em .streamlit/secrets.toml")
        st.info("Configure a senha no arquivo secrets.toml e redeploy o app.")
        st.stop()

    if st.session_state.get("autenticado"):
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


# =====================================================================
# 🎨 APARÊNCIA: cada escritório escolhe as cores do seu sistema
# As cores ficam salvas no banco (tabela "configuracoes"), então valem
# para todas as pessoas do escritório, em qualquer computador ou celular.
# =====================================================================
TABELA_CONFIG = "configuracoes"

TEMAS_PRONTOS = {
    "Escuro (padrão)":  {"fundo": "#0E1117", "cartoes": "#262730", "texto": "#FAFAFA", "destaque": "#FF4B4B", "lateral": "#262730"},
    "Claro":            {"fundo": "#FFFFFF", "cartoes": "#F0F2F6", "texto": "#31333F", "destaque": "#FF4B4B", "lateral": "#F0F2F6"},
    "Azul jurídico":    {"fundo": "#F4F7FC", "cartoes": "#E3EAF5", "texto": "#0F1F3D", "destaque": "#1F3A68", "lateral": "#1F3A68"},
    "Azul e dourado":   {"fundo": "#0F1F3D", "cartoes": "#1B2F57", "texto": "#F5F1E6", "destaque": "#C9A227", "lateral": "#0A1630"},
    "Verde":            {"fundo": "#F5FAF6", "cartoes": "#E1EFE4", "texto": "#14301D", "destaque": "#2E7D4F", "lateral": "#1F4D33"},
    "Vinho":            {"fundo": "#FBF7F7", "cartoes": "#F1E4E6", "texto": "#3A1219", "destaque": "#7B1E2E", "lateral": "#5A1522"},
    "Grafite":          {"fundo": "#1E1F22", "cartoes": "#2B2D31", "texto": "#E8E8E8", "destaque": "#4F8CFF", "lateral": "#17181A"},
}
TEMA_PADRAO = "Escuro (padrão)"
NOMES_CORES = {
    "fundo": "Fundo da tela",
    "cartoes": "Campos e cartões",
    "texto": "Texto",
    "destaque": "Botões e destaques",
    "lateral": "Barra lateral",
}


def _luminancia(cor_hex: str) -> float:
    cor_hex = cor_hex.lstrip("#")
    canais = [int(cor_hex[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contraste(cor1: str, cor2: str) -> float:
    l1, l2 = sorted((_luminancia(cor1), _luminancia(cor2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _misturar(cor1: str, cor2: str, peso: float) -> str:
    """Mistura duas cores (peso = quanto da cor2)."""
    a = [int(cor1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(cor2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * peso):02X}" for x, y in zip(a, b))


def _cor_legivel_sobre(fundo: str) -> str:
    """Branco ou quase-preto, o que for mais legível sobre o fundo."""
    return "#FAFAFA" if _contraste(fundo, "#FAFAFA") >= _contraste(fundo, "#1A1A1A") else "#1A1A1A"


@st.cache_data(ttl=300, show_spinner=False)
def carregar_tema() -> dict:
    """Lê as cores do escritório no banco. Se não houver, usa o padrão."""
    try:
        resp = supabase().table(TABELA_CONFIG).select("*").eq("chave", "tema").execute()
        if resp.data:
            valor = resp.data[0]["valor"] or {}
            if all(k in valor for k in NOMES_CORES):
                return {k: str(valor[k]).upper() for k in NOMES_CORES}
    except Exception:
        pass
    return dict(TEMAS_PRONTOS[TEMA_PADRAO])


def salvar_tema(tema: dict) -> str | None:
    """Grava as cores no banco. Devolve uma mensagem de erro, ou None se deu certo."""
    try:
        supabase().table(TABELA_CONFIG).upsert(
            {"chave": "tema", "valor": tema, "atualizado_em": dt.datetime.now(TZ).isoformat()}
        ).execute()
        carregar_tema.clear()
        return None
    except Exception as exc:
        if "configuracoes" in str(exc) or "does not exist" in str(exc) or "PGRST205" in str(exc):
            return "A tabela de configurações ainda não existe no banco de dados. Ela é criada pelo arquivo supabase_schema.sql."
        return f"Não foi possível salvar: {exc}"


@st.cache_resource
def _tema_em_uso() -> dict:
    return {}


def aplicar_tema(tema: dict) -> None:
    """Aplica as cores ao sistema inteiro (telas, tabelas, campos e barra lateral)."""
    lateral = tema["lateral"]
    texto_lateral = _cor_legivel_sobre(lateral)
    opcoes = {
        "base": "dark" if _luminancia(tema["fundo"]) < 0.4 else "light",
        "primaryColor": tema["destaque"],
        "backgroundColor": tema["fundo"],
        "secondaryBackgroundColor": tema["cartoes"],
        "textColor": tema["texto"],
        "sidebar.backgroundColor": lateral,
        "sidebar.textColor": texto_lateral,
        "sidebar.secondaryBackgroundColor": _misturar(lateral, texto_lateral, 0.12),
        "sidebar.primaryColor": tema["destaque"] if _contraste(tema["destaque"], lateral) >= 2 else _misturar(tema["destaque"], texto_lateral, 0.45),
    }
    em_uso = _tema_em_uso()
    if em_uso == opcoes:
        return
    for chave, valor in opcoes.items():
        st._config.set_option(f"theme.{chave}", valor)
    em_uso.clear()
    em_uso.update(opcoes)
    st.rerun()  # recarrega a tela uma vez para as novas cores aparecerem


def _previa_tema(tema: dict) -> None:
    lateral, texto_lateral = tema["lateral"], _cor_legivel_sobre(tema["lateral"])
    texto_botao = _cor_legivel_sobre(tema["destaque"])
    st.markdown(
        f"""
        <div style="display:flex;border-radius:8px;overflow:hidden;border:1px solid #8884;font-size:11px;height:92px">
          <div style="background:{lateral};color:{texto_lateral};width:34%;padding:8px;font-weight:600">⚖️ Menu</div>
          <div style="background:{tema['fundo']};color:{tema['texto']};flex:1;padding:8px">
            <div style="font-weight:700;margin-bottom:6px">Controladoria</div>
            <div style="background:{tema['cartoes']};border-radius:4px;padding:3px 6px;margin-bottom:6px">Campo / cartão</div>
            <span style="background:{tema['destaque']};color:{texto_botao};border-radius:4px;padding:2px 8px">Botão</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def painel_aparencia() -> None:
    """Painel na barra lateral para o escritório escolher as cores."""
    atual = carregar_tema()
    with st.expander("🎨 Aparência do sistema"):
        nome_atual = next((n for n, t in TEMAS_PRONTOS.items() if t == atual), "Personalizado")
        opcoes = list(TEMAS_PRONTOS) + ["Personalizado"]
        escolha = st.selectbox("Tema", opcoes, index=opcoes.index(nome_atual), key="tema_escolha")

        base = atual if escolha == "Personalizado" else TEMAS_PRONTOS[escolha]
        novo = dict(base)
        if escolha == "Personalizado":
            st.caption("Clique em cada quadrado para escolher a cor:")
            for chave, rotulo in NOMES_CORES.items():
                novo[chave] = st.color_picker(rotulo, value=base[chave], key=f"cor_{chave}").upper()

        st.caption("Prévia:")
        _previa_tema(novo)

        if _contraste(novo["texto"], novo["fundo"]) < 4.5 or _contraste(novo["texto"], novo["cartoes"]) < 3:
            st.warning("⚠️ O texto vai ficar difícil de ler com essas cores. Escolha um texto mais claro ou mais escuro.")

        if novo != atual:
            if st.button("💾 Aplicar para todo o escritório", type="primary", key="tema_salvar", use_container_width=True):
                erro = salvar_tema(novo)
                if erro:
                    st.error(erro)
                else:
                    st.session_state.aviso = "🎨 Cores do escritório atualizadas!"
                    st.rerun()
        else:
            st.caption("✅ Estas são as cores em uso.")

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

def atualizar_prazo(id_prazo: int, campos: dict) -> None:
    """Atualiza um prazo específico no Supabase"""
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
    if df_prazos.empty:
        return pd.DataFrame()

    df_export = df_prazos[["cliente", "processo", "titulo", "data_fatal"]].copy()
    df_export["cliente_primeiro"] = df_export["cliente"].apply(lambda x: x.split()[0] if pd.notna(x) else "")

    if df_processos is not None:
        processos_desc = df_processos[["numero", "descricao"]].copy()
        df_export = df_export.merge(processos_desc, left_on="processo", right_on="numero", how="left")
        df_export["descricao"] = df_export["descricao"].fillna("-")
    else:
        df_export["descricao"] = "-"

    df_export = df_export[["cliente_primeiro", "processo", "titulo", "data_fatal", "descricao"]]

    try:
        df_export["data_fatal"] = pd.to_datetime(df_export["data_fatal"]).dt.strftime("%d/%m/%Y")
    except:
        df_export["data_fatal"] = df_export["data_fatal"].astype(str)

    df_export = df_export.rename(columns={
        "cliente_primeiro": "Cliente",
        "processo": "Nº Processo",
        "titulo": "Título",
        "data_fatal": "Data Fatal",
        "descricao": "Descrição"
    })

    return df_export

def resumo_o_que_fazer(texto, limite: int = 200) -> str:
    """
    Resume as observações do prazo para a pauta impressa:
    - tira as linhas automáticas da leitura de despacho (⏱️ Prazo / 📄 Despacho);
    - mantém o que o usuário escreveu;
    - se só houver o trecho do despacho, usa uma versão curta dele.
    """
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return "-"
    texto = str(texto).strip()
    if not texto:
        return "-"

    linhas_usuario, trecho_despacho = [], ""
    for linha in texto.splitlines():
        l = linha.strip()
        if not l:
            continue
        if l.startswith("⏱️ Prazo:") or l.startswith("⏱ Prazo:"):
            continue
        if l.startswith("📄 Despacho:"):
            trecho_despacho = l.replace("📄 Despacho:", "").strip()
            continue
        linhas_usuario.append(l)

    resumo = " / ".join(linhas_usuario) if linhas_usuario else trecho_despacho
    resumo = re.sub(r"\s+", " ", resumo).strip()
    if not resumo:
        return "-"
    if len(resumo) > limite:
        resumo = resumo[:limite].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
    return resumo

def gerar_excel_bonito(df_prazos: pd.DataFrame, df_processos: pd.DataFrame = None):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    import tempfile

    if df_prazos.empty:
        return None

    df_export = df_prazos[["cliente", "processo", "titulo", "data_fatal", "descricao"]].copy()
    df_export = df_export.rename(columns={"descricao": "o_que_fazer"})
    df_export["cliente"] = df_export["cliente"].apply(lambda x: x.split()[0] if pd.notna(x) and x else "")
    df_export["o_que_fazer"] = df_export["o_que_fazer"].apply(resumo_o_que_fazer)

    # Tipo de ação: vem do cadastro do processo
    if df_processos is not None and not df_processos.empty:
        processos_desc = (
            df_processos[["numero", "descricao"]]
            .drop_duplicates(subset=["numero"], keep="first")
            .rename(columns={"descricao": "acao"})
        )
        df_export = df_export.merge(processos_desc, left_on="processo", right_on="numero", how="left")
        df_export["acao"] = df_export["acao"].fillna("-").replace("", "-")
    else:
        df_export["acao"] = "-"

    try:
        df_export["data_fatal"] = pd.to_datetime(df_export["data_fatal"]).dt.strftime("%d/%m/%Y")
    except:
        df_export["data_fatal"] = df_export["data_fatal"].astype(str)

    colunas = [
        ("cliente", "Cliente", 15, "left"),
        ("processo", "Nº Processo", 28, "left"),
        ("titulo", "Prazo", 24, "left"),
        ("data_fatal", "Data Fatal", 13, "center"),
        ("acao", "Ação", 26, "left"),
        ("o_que_fazer", "O que fazer", 55, "left"),
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "Pauta"

    header_fill = PatternFill(start_color="1f4788", end_color="1f4788", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    alinhamentos = {
        "center": Alignment(horizontal="center", vertical="center", wrap_text=True),
        "left": Alignment(horizontal="left", vertical="center", wrap_text=True),
    }

    for col_num, (_, titulo, largura, _) in enumerate(colunas, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = titulo
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = alinhamentos["center"]
        cell.border = border
        ws.column_dimensions[cell.column_letter].width = largura

    for row_num, (_, row) in enumerate(df_export.iterrows(), 2):
        for col_num, (campo, _, _, alinhamento) in enumerate(colunas, 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.value = row[campo]
            cell.alignment = alinhamentos[alinhamento]
            cell.border = border

    # Impressão: paisagem, cabeçalho repetido em cada página e ajuste à largura da folha
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "1:1"
    ws.freeze_panes = "A2"

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        wb.save(tmp.name)
        return tmp.name

def gerar_audiencias_excel(df_audiencias: pd.DataFrame):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    import tempfile

    if df_audiencias.empty:
        return None

    df_export = df_audiencias[["processo", "autor", "reu", "sala", "data_audiencia", "hora_inicio", "hora_termino", "formato", "tipo", "status"]].copy()

    try:
        df_export["data_audiencia"] = pd.to_datetime(df_export["data_audiencia"]).dt.strftime("%d/%m/%Y")
    except:
        df_export["data_audiencia"] = df_export["data_audiencia"].astype(str)

    df_export["hora_inicio"] = df_export["hora_inicio"].astype(str)
    df_export["hora_termino"] = df_export["hora_termino"].astype(str)

    wb = Workbook()
    ws = wb.active
    ws.title = "Audiências"

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

    headers = ["Nº Processo", "Autor", "Réu", "Sala", "Data", "Início", "Término", "Formato", "Tipo", "Status"]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = border

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

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        wb.save(tmp.name)
        return tmp.name

def tabela_status(df: pd.DataFrame, processos_df: pd.DataFrame = None, prefix: str = "main", filtro_responsavel: str = None) -> None:
    """
    PASSO 2: Coluna "Dias Úteis" ✅
    PASSO 3: Filtro por responsável ✅
    """
    if df.empty:
        st.info("Nenhum registro.")
        return

    df_vis = df.copy()

    modal_key_aberta = f"prazo_modal_{prefix}_aberta"
    modal_key_id = f"prazo_modal_{prefix}_id"
    modal_key_modo = f"prazo_modal_{prefix}_modo"

    st.session_state.setdefault(modal_key_aberta, False)
    st.session_state.setdefault(modal_key_id, None)
    st.session_state.setdefault(modal_key_modo, None)

    # ===== PASSO 3: FILTRO POR RESPONSÁVEL =====
    if filtro_responsavel and filtro_responsavel != "Todos":
        df_vis = df_vis[df_vis["responsavel"] == filtro_responsavel]

    if df_vis.empty:
        st.info(f"Nenhum registro para {filtro_responsavel if filtro_responsavel else 'este filtro'}.")
        return

    df_vis["cliente_primeiro"] = df_vis["cliente"].apply(lambda x: x.split()[0] if x else "")

    if processos_df is not None:
        processos_parte = processos_df[["numero", "parte_contraria"]].drop_duplicates(subset=["numero"], keep="first").copy()
        df_vis = df_vis.merge(processos_parte, left_on="processo", right_on="numero", how="left")
        df_vis["parte_primeiro"] = df_vis["parte_contraria"].apply(lambda x: x.split()[0] if pd.notna(x) and x else "")
        df_vis["cliente_parte"] = df_vis.apply(
            lambda row: f"{row['cliente_primeiro']} / {row['parte_primeiro']}" if row['parte_primeiro'] else row['cliente_primeiro'],
            axis=1
        )
    else:
        df_vis["cliente_parte"] = df_vis["cliente_primeiro"]

    df_vis["data_interna_fmt"] = df_vis["data_interna"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "")
    df_vis["data_fatal_fmt"] = df_vis["data_fatal"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "")

    # ===== PASSO 2: COLUNA DIAS ÚTEIS =====
    colunas_vis = [
        "id", "situacao", "titulo", "processo", "cliente_parte",
        "data_interna_fmt", "data_fatal_fmt", "dias_uteis",
        "responsavel", "prioridade",
    ]

    vis = (
        df_vis.assign(_p=df_vis["prioridade"].map(ORDEM_PRIORIDADE))
        .sort_values(["dias_uteis"])[colunas_vis]
        .drop_duplicates(subset=["processo", "titulo", "data_fatal_fmt"], keep="first")
        .set_index("id")
        .rename(columns={
            "id": "ID",
            "situacao": "Situação",
            "titulo": "Título",
            "processo": "Nº Processo",
            "cliente_parte": "Cliente / Parte Contrária",
            "data_interna_fmt": "Prazo Interno",
            "data_fatal_fmt": "Data Fatal",
            "dias_uteis": "Dias Úteis",
            "responsavel": "Responsável",
            "prioridade": "Prioridade"
        })
    )

    st.dataframe(vis, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("⚙️ Gerenciar Prazo")

    df_ativos = df[~df["arquivado"]].copy()

    # ===== MERGE COM PARTE CONTRÁRIA PARA A SEÇÃO GERENCIAR =====
    if processos_df is not None and not processos_df.empty:
        processos_gerenciar = processos_df[["numero", "parte_contraria"]].drop_duplicates(subset=["numero"], keep="first").copy()
        df_ativos = df_ativos.merge(processos_gerenciar, left_on="processo", right_on="numero", how="left")

    if df_ativos.empty:
        st.info("Nenhum prazo ativo.")
        return

    # ===== PASSO 3: FILTRO POR RESPONSÁVEL NA SEÇÃO GERENCIAR =====
    filtro_gerenciar_key = f"filtro_gerenciar_{prefix}"
    st.session_state.setdefault(filtro_gerenciar_key, "Todos")

    st.write("**Filtrar por responsável:**")
    filtro_resp_gerenciar = st.selectbox(
        "Selecione um responsável",
        ["Todos"] + RESPONSAVEIS,
        key=f"select_filtro_gerenciar_{prefix}",
        label_visibility="collapsed"
    )
    st.session_state[filtro_gerenciar_key] = filtro_resp_gerenciar

    df_ativos_filtrado = df_ativos.copy()
    if filtro_resp_gerenciar and filtro_resp_gerenciar != "Todos":
        df_ativos_filtrado = df_ativos_filtrado[df_ativos_filtrado["responsavel"] == filtro_resp_gerenciar]

    col1, col2 = st.columns([2, 1])

    opcoes_display = ["📌 Selecione um prazo..."]
    opcoes_ids = [None]

    for _, row in df_ativos_filtrado.iterrows():
        # Montar a exibição com cliente, parte contrária (se houver) e título
        cliente_display = row['cliente']
        if pd.notna(row.get('parte_contraria', '')) and row.get('parte_contraria', ''):
            cliente_display = f"{cliente_display} / {row['parte_contraria']}"

        opcoes_display.append(f"{cliente_display} | {row['titulo']} | {row['data_fatal'].strftime('%d/%m/%Y')}")
        opcoes_ids.append(row['id'])

    if len(opcoes_display) == 1:
        st.info(f"Nenhum prazo para {filtro_resp_gerenciar if filtro_resp_gerenciar != 'Todos' else 'exibir'}.")
        return

    id_sel_idx = col1.selectbox(
        "Clique no prazo para ver detalhes:",
        options=range(len(opcoes_display)),
        format_func=lambda x: opcoes_display[x],
        key=f"sel_prazo_idx_{prefix}"
    )

    if col2.button("📂 Ver Detalhes", use_container_width=True, type="primary", key=f"btn_det_prazo_{prefix}"):
        if st.session_state.get(f"sel_prazo_idx_{prefix}", 0) > 0:
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

        if st.session_state.get(modal_key_modo) == "detalhes":
            st.info("📋 Detalhes Completos do Prazo")

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
                novo_titulo = st.text_input("Título", value=prazo["titulo"], key=f"edit_titulo_{prefix}_{id_prazo}")

                col1, col2 = st.columns(2)
                with col1:
                    novo_responsavel = st.selectbox("Responsável", RESPONSAVEIS, index=RESPONSAVEIS.index(prazo["responsavel"]) if prazo["responsavel"] in RESPONSAVEIS else 0, key=f"edit_resp_{prefix}_{id_prazo}")
                with col2:
                    nova_prioridade = st.selectbox("Prioridade", PRIORIDADES, index=PRIORIDADES.index(prazo["prioridade"]), key=f"edit_prio_{prefix}_{id_prazo}")

                col1, col2 = st.columns(2)
                nova_interna = col1.date_input("Prazo Interno", value=prazo["data_interna"], format="DD/MM/YYYY", key=f"edit_interna_{prefix}_{id_prazo}")
                nova_fatal = col2.date_input("Data Fatal", value=prazo["data_fatal"], format="DD/MM/YYYY", key=f"edit_fatal_{prefix}_{id_prazo}")

                nova_descricao = st.text_area("Observações", value=prazo["descricao"] or "", key=f"edit_desc_{prefix}_{id_prazo}")

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

def sidebar_novo_prazo(
    processos_df: pd.DataFrame,
    processo_fixo: str | None = None,
    titulo_fixo: str | None = None,
    obs_inicial: str = "",
) -> None:
    """
    PASSO 6: Impedir duplicação de prazos ✅
    """
    v = st.session_state.form_v

    processos_ativos = processos_df[processos_df["ativo"]].sort_values("numero")

    processo = None
    cliente = ""
    parte_adversaria = ""

    if processo_fixo:
        # Processo já escolhido (ex.: lançado de dentro de Processos Cadastrados)
        processo = processo_fixo
    else:
        st.write("**Nº Processo** \\*")

        # Campo de texto com botão de LIMPAR
        col_busca, col_limpar = st.columns([9, 1])

        with col_busca:
            busca_proc = st.text_input(
                "Digite o número ou cliente",
                value="",
                key=f"busca_proc_{v}",
                label_visibility="collapsed",
                placeholder="Digite 3+ letras para buscar...",
                max_chars=100
            )

        with col_limpar:
            if st.button("🗑️", key=f"limpar_proc_{v}", help="Limpar pesquisa", use_container_width=True):
                st.session_state[f"busca_proc_{v}"] = ""
                st.rerun()

        # Se digitou 3+ caracteres, mostrar selectbox com opções
        if len(busca_proc) >= 3:
            busca_lower = busca_proc.lower().strip()

            # Filtrar processos por NÚMERO ou CLIENTE
            processos_filtrados = processos_ativos[
                (processos_ativos["numero"].str.contains(busca_lower, case=False, na=False, regex=False)) |
                (processos_ativos["cliente"].str.contains(busca_lower, case=False, na=False, regex=False))
            ]

            if not processos_filtrados.empty:
                st.caption(f"📋 {len(processos_filtrados)} processo(s) encontrado(s):")

                # Selectbox com as opções (mostrando número e cliente)
                processo = st.selectbox(
                    "Selecione:",
                    options=processos_filtrados["numero"].values,
                    format_func=lambda x: f"{x} — {processos_filtrados[processos_filtrados['numero']==x]['cliente'].values[0]}",
                    index=0,
                    label_visibility="collapsed",
                    key=f"sel_proc_{v}"
                )
            else:
                st.warning(f"❌ Nenhum processo encontrado com '{busca_proc}'")

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

    titulo = ""
    if titulo_fixo:
        # Título já escolhido (ex.: sugerido pela leitura do despacho)
        titulo = titulo_fixo
    else:
        st.write("**Título** \\*")
        busca_titulo = st.text_input(
            "Digite para filtrar atalhos jurídicos",
            value="",
            placeholder="Ex: RO, recurso, contestação, manifestação...",
            key=f"busca_{v}",
            label_visibility="collapsed"
        )

        if busca_titulo:
            # Busca pelo código (RO, CONT...) OU pelo nome (recurso, contestação...), sem ligar para acentos
            termo = remover_acentos(busca_titulo.strip())
            encontrados = [
                k for k in ATALHOS
                if termo in remover_acentos(k) or termo in remover_acentos(ATALHOS[k])
            ]
            # Ordem: código exato (ex.: RO) > código que começa igual > nome que começa igual > o resto
            encontrados.sort(key=lambda k: (
                remover_acentos(k) != termo and f"({termo})" not in remover_acentos(ATALHOS[k]),
                not remover_acentos(k).startswith(termo),
                not remover_acentos(ATALHOS[k]).startswith(termo),
            ))
            atalhos_filtrados = {k: ATALHOS[k] for k in encontrados}
            texto_livre = busca_titulo.strip()
            opcao_livre = f"✏️ Usar como digitado: {texto_livre}"
            opcoes_titulo = list(atalhos_filtrados.keys()) + [opcao_livre]
            if not atalhos_filtrados:
                st.caption("Nenhum atalho com esse nome. Você pode usar o texto como digitado.")
            titulo_atalho = st.selectbox(
                "Atalhos encontrados:",
                options=opcoes_titulo,
                format_func=lambda x: x if x == opcao_livre else f"{x} — {atalhos_filtrados[x]}",
                key=f"ta_{v}",
                label_visibility="collapsed"
            )
            titulo = texto_livre if titulo_atalho == opcao_livre else atalhos_filtrados[titulo_atalho]
        else:
            st.caption("👉 Digite acima para ver os atalhos disponíveis")

    if titulo:
        st.caption(f"📌 Selecionado: **{titulo}**")

    with st.form(f"cad_{v}"):
        tipo = st.selectbox("Tipo *", TIPOS, index=0, key=f"t_{v}")

        responsavel = st.radio("Responsável *", RESPONSAVEIS, horizontal=True, key=f"r_{v}")
        c1, c2 = st.columns(2)
        data_interna = c1.date_input("Prazo Interno", value=None, format="DD/MM/YYYY", key=f"i_{v}")
        data_fatal = c2.date_input("Data Fatal *", value=None, format="DD/MM/YYYY", key=f"f_{v}")

        prioridade = st.select_slider("Prioridade", PRIORIDADES, value="Normal", key=f"pr_{v}")
        chave_obs = f"d_{v}_{abs(hash(obs_inicial)) % 10**8}" if obs_inicial else f"d_{v}"
        observacoes = st.text_area("Observações", value=obs_inicial, key=chave_obs, height=150 if obs_inicial else None)

        c1, c2 = st.columns(2)
        with c1:
            if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
                if not processo or not data_fatal or not titulo:
                    st.error("Preencha processo, data fatal e título!")
                elif data_interna and data_interna > data_fatal:
                    st.error("Prazo interno deve ser ≤ data fatal!")
                else:
                    # ===== PASSO 6: VERIFICAR DUPLICAÇÃO =====
                    df_prazos = carregar_prazos()
                    prazo_existe = df_prazos[
                        (df_prazos["processo"] == processo) &
                        (df_prazos["titulo"] == titulo) &
                        (~df_prazos["concluido"]) &
                        (~df_prazos["arquivado"])
                    ]

                    if not prazo_existe.empty:
                        data_venc = prazo_existe.iloc[0]["data_fatal"].strftime("%d/%m/%Y")
                        st.error(f"⚠️ Este prazo já existe! Vencimento: {data_venc}")
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
                            "descricao": observacoes or None,
                            "arquivado": False,
                        })
                        st.session_state.form_v += 1
                        st.session_state.aviso = "✅ Prazo salvo com sucesso!"
                        st.rerun()
        with c2:
            if st.form_submit_button("🗑️ Limpar", use_container_width=True):
                st.session_state.form_v += 1
                st.rerun()

def dashboard_completo(df_prazos: pd.DataFrame, df_audiencias: pd.DataFrame, df_processos: pd.DataFrame) -> None:
    st.markdown("# 📊 DASHBOARD CONTROLADORIA")
    st.divider()

    st.session_state.setdefault("dashboard_filtro", None)

    if not df_prazos.empty:
        df_prazos = enriquecer(df_prazos)

    pend = df_prazos[~df_prazos["concluido"] & ~df_prazos["arquivado"]] if not df_prazos.empty else pd.DataFrame()
    vencidos = pend[pend["faixa"] == "Vencido"] if not pend.empty else pd.DataFrame()
    hoje_prazos = pend[pend["faixa"] == "Hoje"] if not pend.empty else pd.DataFrame()

    aud_agendadas = df_audiencias[df_audiencias["status"] == "Agendada"] if not df_audiencias.empty else pd.DataFrame()
    aud_realizadas = df_audiencias[df_audiencias["status"] == "Realizada"] if not df_audiencias.empty else pd.DataFrame()
    aud_canceladas = df_audiencias[df_audiencias["status"] == "Cancelada"] if not df_audiencias.empty else pd.DataFrame()

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

    if st.session_state.dashboard_filtro:
        filtro = st.session_state.dashboard_filtro

        st.markdown("---")
        col_voltar = st.columns([3, 1])
        with col_voltar[1]:
            if st.button("🔙 Voltar", use_container_width=True, key="btn_voltar_dash"):
                st.session_state.dashboard_filtro = None
                st.rerun()

        st.markdown("---")

        if filtro == "vencidos":
            st.subheader("🔴 Prazos Vencidos")
            if vencidos.empty:
                st.info("Nenhum prazo vencido!")
            else:
                tabela_status(vencidos, df_processos, prefix="dash_vencidos")

        elif filtro == "hoje":
            st.subheader("🟠 Prazos de Hoje")
            if hoje_prazos.empty:
                st.info("Nenhum prazo para hoje!")
            else:
                tabela_status(hoje_prazos, df_processos, prefix="dash_hoje")

        elif filtro == "pendentes":
            st.subheader("📋 Prazos Pendentes")
            if pend.empty:
                st.info("Nenhum prazo pendente!")
            else:
                tabela_status(pend, df_processos, prefix="dash_pendentes")

        elif filtro == "agendadas":
            st.subheader("📅 Audiências Agendadas")
            if aud_agendadas.empty:
                st.info("Nenhuma audiência agendada!")
            else:
                tabela_audiencias(aud_agendadas, prefix="dash_agendadas")

        elif filtro == "realizadas":
            st.subheader("✅ Audiências Realizadas")
            if aud_realizadas.empty:
                st.info("Nenhuma audiência realizada!")
            else:
                tabela_audiencias(aud_realizadas, prefix="dash_realizadas")

        elif filtro == "canceladas":
            st.subheader("❌ Audiências Canceladas")
            if aud_canceladas.empty:
                st.info("Nenhuma audiência cancelada!")
            else:
                tabela_audiencias(aud_canceladas, prefix="dash_canceladas")

def sidebar_nova_audiencia(processos_df: pd.DataFrame) -> None:
    v = st.session_state.form_v

    processos_ativos = processos_df[processos_df["ativo"]].sort_values("numero")

    st.write("**Processo ou cliente** \\*")
    busca = st.text_input(
        "Digite o número do processo ou o nome do cliente",
        value="",
        placeholder="Ex: 5014993 ou HELENA",
        key=f"busca_proc_aud_{v}",
        label_visibility="collapsed"
    ).strip()

    processo = None
    autor = ""
    reu = ""

    if busca:
        # Busca por NOME do cliente ou da parte contrária (ignora maiúsculas e acentos)
        busca_sem_acentos = remover_acentos(busca)
        mascara_nome = (
            processos_ativos["cliente"].apply(remover_acentos).str.contains(busca_sem_acentos, na=False, regex=False) |
            processos_ativos["parte_contraria"].apply(remover_acentos).str.contains(busca_sem_acentos, na=False, regex=False)
        )

        # Busca por NÚMERO (com ou sem pontos e traços)
        mascara_numero = processos_ativos["numero"].fillna("").str.contains(busca, case=False, regex=False)
        digitos = re.sub(r"\D", "", busca)
        if len(digitos) >= 3:
            mascara_numero = mascara_numero | processos_ativos["numero"].fillna("").str.replace(r"\D", "", regex=True).str.contains(digitos, regex=False)

        processos_filtrados = processos_ativos[mascara_nome | mascara_numero]

        if not processos_filtrados.empty:
            st.caption(f"📋 {len(processos_filtrados)} processo(s) encontrado(s):")

            clientes_por_numero = dict(zip(processos_filtrados["numero"], processos_filtrados["cliente"]))
            processo = st.selectbox(
                "Selecione:",
                options=processos_filtrados["numero"].values,
                format_func=lambda x: f"{x} — {clientes_por_numero.get(x, '')}",
                index=0,
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

        c1, c2 = st.columns(2)
        with c1:
            if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
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
                    st.session_state.form_v += 1
                    st.session_state.aviso = "✅ Audiência salva com sucesso!"
                    st.rerun()
        with c2:
            if st.form_submit_button("🗑️ Limpar", use_container_width=True):
                st.session_state.form_v += 1
                st.rerun()

def _so_digitos(texto) -> str:
    """Mantém apenas os números (ignora pontos, traços e espaços)."""
    if pd.isna(texto):
        return ""
    return re.sub(r"\D", "", str(texto))

def gerenciar_processos(df_processos: pd.DataFrame, df_prazos: pd.DataFrame) -> None:
    """
    Aba Processos:
    - Sem busca: mostra apenas o TOTAL de processos cadastrados (sem listar).
    - Com busca (nome do cliente ou número): lista só os processos encontrados,
      expansíveis, com a situação atual e os prazos de cada um.
    """

    if df_processos.empty:
        st.info("Nenhum processo cadastrado.")
        return

    processos_ativos = df_processos[df_processos["ativo"]].copy()

    if processos_ativos.empty:
        st.info("Nenhum processo ativo.")
        return

    processos_unicos = processos_ativos.drop_duplicates(subset=["numero"], keep="first").sort_values("numero")
    total_processos = len(processos_unicos)

    col1, col2 = st.columns([3, 1])
    with col1:
        busca = st.text_input(
            "🔍 Buscar por número de processo ou nome do cliente:",
            placeholder="Ex: 5014993 ou HELENA",
            key="busca_processo",
            label_visibility="collapsed"
        ).strip()

    processos_filtrados = processos_unicos.iloc[0:0]

    if busca:
        # Busca por NOME (ignora maiúsculas e acentos)
        busca_sem_acentos = remover_acentos(busca)
        mascara_nome = processos_unicos["cliente"].apply(remover_acentos).str.contains(
            busca_sem_acentos, na=False, regex=False
        )

        # Busca por NÚMERO (com ou sem pontuação)
        mascara_numero = processos_unicos["numero"].fillna("").str.contains(
            busca, case=False, na=False, regex=False
        )
        digitos = _so_digitos(busca)
        if len(digitos) >= 3:
            mascara_numero = mascara_numero | processos_unicos["numero"].apply(_so_digitos).str.contains(
                digitos, na=False, regex=False
            )

        processos_filtrados = processos_unicos[mascara_nome | mascara_numero]

    with col2:
        if busca:
            st.metric("Resultados", len(processos_filtrados))
        else:
            st.metric("Total de processos", total_processos)

    # ===== SEM BUSCA: NÃO LISTA NADA =====
    if not busca:
        st.caption("🔎 Digite o número do processo ou o nome do cliente para consultar como ele está agora.")
        return

    if processos_filtrados.empty:
        st.warning(f"❌ Nenhum processo encontrado com '{busca}'")
        return

    st.caption("Clique para expandir e ver todos os prazos do processo:")

    # Se só encontrou um processo, já abre direto
    abrir_unico = len(processos_filtrados) == 1

    for idx, proc in processos_filtrados.iterrows():
        todos_prazos = df_prazos[df_prazos["processo"] == proc["numero"]]
        prazos_abertos = todos_prazos[~todos_prazos["concluido"] & ~todos_prazos["arquivado"]]
        prazos_concluidos = todos_prazos[todos_prazos["concluido"]]
        prazos_arquivados = todos_prazos[todos_prazos["arquivado"]]

        qtd_abertos = len(prazos_abertos)
        qtd_concluidos = len(prazos_concluidos)
        qtd_arquivados = len(prazos_arquivados)

        titulo_expander = f"**{proc['numero']}** | {proc['cliente']} | 📋 {qtd_abertos} ✅ {qtd_concluidos} 📦 {qtd_arquivados}"

        # Verificar se este é o processo que deve abrir automaticamente
        abrir_automatico = abrir_unico or proc["numero"] == st.session_state.get("processo_abrir_automatico", None)

        with st.expander(titulo_expander, expanded=abrir_automatico):

            with st.expander("📋 Informações & Edição do Processo", expanded=True):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Informações:**")
                    st.write(f"🔹 **Nº Processo:** `{proc['numero']}`")
                    st.write(f"👤 **Cliente:** {proc['cliente']}")
                    st.write(f"⚔️ **Parte Adversária:** {proc['parte_contraria']}")
                    # Exibir fase atual
                    fase_atual = proc.get("fase", "Não definida")
                    st.write(f"📊 **Fase:** {fase_atual}")
                    if proc["descricao"]:
                        st.write(f"📌 **Descrição:** {proc['descricao']}")

                with col2:
                    st.markdown("**Editar:**")
                    with st.form(f"edit_{proc['id']}", clear_on_submit=False):
                        novo_cliente = st.text_input("Cliente", value=proc["cliente"], key=f"cli_{proc['id']}")
                        nova_parte = st.text_input("Parte Adversária", value=proc["parte_contraria"], key=f"parte_{proc['id']}")

                        # ===== SELETOR DE FASE =====
                        fase_atual = proc.get("fase", FASES_PROCESSO[0])
                        # Se a fase atual não está na lista (caso legado), usa a primeira opção
                        try:
                            fase_index = FASES_PROCESSO.index(fase_atual)
                        except ValueError:
                            fase_index = 0

                        nova_fase = st.selectbox(
                            "Fase do Processo",
                            FASES_PROCESSO,
                            index=fase_index,
                            key=f"fase_{proc['id']}"
                        )

                        nova_desc = st.text_area("Descrição", value=proc["descricao"] or "", height=80, key=f"desc_{proc['id']}")

                        if st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True):
                            atualizar_processo(proc["id"], {
                                "cliente": novo_cliente,
                                "parte_contraria": nova_parte,
                                "fase": nova_fase,
                                "descricao": nova_desc or None
                            })
                            st.success("✅ Processo atualizado!")
                            st.rerun()

            st.divider()

            tab_abertos, tab_concluidos, tab_arquivados = st.tabs([
                f"📋 Em Aberto ({qtd_abertos})",
                f"✅ Concluídos ({qtd_concluidos})",
                f"📦 Arquivados ({qtd_arquivados})"
            ])

            with tab_abertos:
                st.button(
                    "➕ Lançar Prazo",
                    key=f"lancar_prazo_{proc['id']}",
                    type="primary",
                    use_container_width=True,
                    on_click=definir_lancar_prazo,
                    args=(proc["numero"],),
                )

                if prazos_abertos.empty:
                    st.info("✅ Nenhum prazo em aberto!")
                else:
                    prazos_abertos = enriquecer(prazos_abertos.copy()).sort_values("dias_uteis")

                    for p_idx, prazo in prazos_abertos.iterrows():
                        mostra_card_prazo(prazo, df_processos)

            with tab_concluidos:
                if prazos_concluidos.empty:
                    st.info("Nenhum prazo concluído ainda.")
                else:
                    prazos_concluidos = enriquecer(prazos_concluidos.copy()).sort_values("data_fatal", ascending=False)

                    for p_idx, prazo in prazos_concluidos.iterrows():
                        mostra_card_prazo(prazo, df_processos)

            with tab_arquivados:
                if prazos_arquivados.empty:
                    st.info("Nenhum prazo arquivado.")
                else:
                    prazos_arquivados = enriquecer(prazos_arquivados.copy()).sort_values("data_fatal", ascending=False)

                    for p_idx, prazo in prazos_arquivados.iterrows():
                        mostra_card_prazo(prazo, df_processos)

def mostra_card_prazo(prazo, df_processos: pd.DataFrame = None) -> None:
    with st.container(border=True):
        # ===== BUSCAR PARTE CONTRÁRIA =====
        parte_contraria = ""
        if df_processos is not None and not df_processos.empty and prazo.get('processo'):
            proc = df_processos[df_processos['numero'] == prazo['processo']]
            if not proc.empty:
                parte_contraria = proc.iloc[0]['parte_contraria']

        col1, col2, col3, col4 = st.columns([0.8, 2, 1.2, 0.8])

        with col1:
            st.markdown(f"### {prazo['situacao']}")

        with col2:
            st.markdown(f"**{prazo['titulo']}**")
            st.caption(f"👤 {prazo['responsavel']}")
            if parte_contraria:
                st.caption(f"⚔️ {parte_contraria[:30]}")

        with col3:
            data_interna_str = prazo['data_interna'].strftime("%d/%m") if pd.notna(prazo['data_interna']) else "—"
            data_fatal_str = prazo['data_fatal'].strftime("%d/%m/%Y")
            st.text(f"📌 {data_interna_str}\n🔚 {data_fatal_str}")

        with col4:
            prioridade_emoji = {"Alta": "🔴", "Normal": "🟡", "Baixa": "🟢"}
            emoji = prioridade_emoji.get(prazo['prioridade'], '⚪')
            st.markdown(f"**{emoji}**\n{prazo['prioridade']}")

        if prazo['descricao']:
            st.divider()
            st.markdown(f"**📝 Observações:**")
            st.caption(prazo['descricao'])

def tabela_audiencias(df: pd.DataFrame, prefix: str = "main") -> None:
    if df.empty:
        st.info("Nenhuma audiência cadastrada.")
        return

    df_vis = df.copy()

    modal_key_aberta = f"aud_modal_{prefix}_aberta"
    modal_key_id = f"aud_modal_{prefix}_id"
    modal_key_modo = f"aud_modal_{prefix}_modo"

    st.session_state.setdefault(modal_key_aberta, False)
    st.session_state.setdefault(modal_key_id, None)
    st.session_state.setdefault(modal_key_modo, None)

    df_vis["data_fmt"] = df_vis["data_audiencia"].apply(lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "")
    df_vis["hora_ini_fmt"] = df_vis["hora_inicio"].astype(str)
    df_vis["hora_fim_fmt"] = df_vis["hora_termino"].astype(str)

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

# ===== BUSCA INTELIGENTE E ROBUSTA =====
def remover_acentos(texto: str) -> str:
    """Remove acentos para busca mais robusta"""
    if pd.isna(texto):
        return ""
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto))
                   if unicodedata.category(c) != 'Mn').lower()

@st.dialog("✏️ Editar Prazo", width="large")
def janela_editar_prazo(id_prazo: int, df_prazos: pd.DataFrame, df_processos: pd.DataFrame) -> None:
    """Janela para corrigir um prazo lançado errado."""
    formulario_editar_prazo(id_prazo, df_prazos, df_processos)


def formulario_editar_prazo(id_prazo: int, df_prazos: pd.DataFrame, df_processos: pd.DataFrame, ao_cancelar=None) -> None:
    """Campos de edição de um prazo (usado nas janelas de edição e de consulta)."""
    encontrados = df_prazos[df_prazos["id"] == id_prazo]
    if encontrados.empty:
        st.warning("Este prazo não foi encontrado. Clique em 🔄 Recarregar Dados.")
        return
    prazo = encontrados.iloc[0]
    k = f"ed_{id_prazo}"

    # ===== BUSCAR PARTE CONTRÁRIA =====
    parte_contraria = ""
    if df_processos is not None and not df_processos.empty and prazo.get('processo'):
        proc = df_processos[df_processos['numero'] == prazo['processo']]
        if not proc.empty:
            parte_contraria = proc.iloc[0]['parte_contraria']

    # Exibir cabeçalho com cliente, processo e parte contrária
    header_text = f"👤 {prazo['cliente']}  ·  📌 {prazo['processo']}"
    if parte_contraria:
        header_text += f"  ·  ⚔️ {parte_contraria}"
    st.caption(header_text)

    # --- Processo (caso tenha sido lançado no processo errado) ---
    processos = df_processos[df_processos["ativo"]] if not df_processos.empty else df_processos
    numeros = list(dict.fromkeys(processos["numero"].astype(str))) if not processos.empty else []
    if prazo["processo"] not in numeros:
        numeros = [str(prazo["processo"])] + numeros
    clientes = dict(zip(df_processos["numero"].astype(str), df_processos["cliente"])) if not df_processos.empty else {}
    processo = st.selectbox(
        "Processo",
        numeros,
        index=numeros.index(str(prazo["processo"])),
        format_func=lambda n: f"{n} — {clientes.get(n, prazo['cliente'])}",
        key=f"{k}_proc",
    )

    # --- Título: pode digitar ou escolher um atalho (o atalho preenche o campo) ---
    st.session_state.setdefault(f"{k}_titulo", str(prazo["titulo"]))

    def _usar_atalho() -> None:
        escolhido = st.session_state.get(f"{k}_atalho")
        if escolhido in ATALHOS:
            st.session_state[f"{k}_titulo"] = ATALHOS[escolhido]

    st.selectbox(
        "Trocar o título por um atalho (opcional)",
        ["— manter o título abaixo —"] + list(ATALHOS.keys()),
        format_func=lambda c: c if c.startswith("—") else f"{c} — {ATALHOS[c]}",
        key=f"{k}_atalho",
        on_change=_usar_atalho,
    )
    titulo = st.text_input("Título *", key=f"{k}_titulo")

    c1, c2 = st.columns(2)
    tipo = c1.selectbox("Tipo", TIPOS, index=TIPOS.index(prazo["tipo"]) if prazo["tipo"] in TIPOS else 0, key=f"{k}_tipo")
    responsavel = c2.selectbox(
        "Responsável", RESPONSAVEIS,
        index=RESPONSAVEIS.index(prazo["responsavel"]) if prazo["responsavel"] in RESPONSAVEIS else 0,
        key=f"{k}_resp",
    )

    c3, c4 = st.columns(2)
    data_interna = c3.date_input(
        "Prazo Interno",
        value=prazo["data_interna"] if pd.notna(prazo["data_interna"]) else None,
        format="DD/MM/YYYY", key=f"{k}_interna",
    )
    data_fatal = c4.date_input("Data Fatal *", value=prazo["data_fatal"], format="DD/MM/YYYY", key=f"{k}_fatal")

    prioridade = st.select_slider(
        "Prioridade", PRIORIDADES,
        value=prazo["prioridade"] if prazo["prioridade"] in PRIORIDADES else "Normal",
        key=f"{k}_prio",
    )
    descricao_atual = prazo["descricao"] if isinstance(prazo["descricao"], str) else ""
    descricao = st.text_area("Observações", value=descricao_atual, key=f"{k}_desc")

    b1, b2 = st.columns(2)
    if b1.button("💾 Salvar alterações", type="primary", use_container_width=True, key=f"{k}_salvar"):
        if not titulo.strip():
            st.error("O título não pode ficar em branco.")
        elif not data_fatal:
            st.error("Informe a data fatal.")
        elif data_interna and data_interna > data_fatal:
            st.error("O prazo interno deve ser igual ou anterior à data fatal.")
        else:
            atualizar_prazo(int(id_prazo), {
                "processo": processo,
                "cliente": clientes.get(processo, prazo["cliente"]),
                "titulo": titulo.strip(),
                "tipo": tipo,
                "responsavel": responsavel,
                "data_interna": data_interna.isoformat() if data_interna else None,
                "data_fatal": data_fatal.isoformat(),
                "prioridade": prioridade,
                "descricao": descricao.strip() or None,
            })
            _limpar_janela_edicao(k)
            st.session_state.pop(f"ver_prazo_modo_{id_prazo}", None)
            st.session_state.aviso = "✅ Prazo corrigido!"
            st.rerun()
    if b2.button("Cancelar", use_container_width=True, key=f"{k}_cancelar"):
        _limpar_janela_edicao(k)
        if ao_cancelar:
            ao_cancelar()
        st.rerun()


def _limpar_janela_edicao(prefixo: str) -> None:
    for chave in [c for c in st.session_state if str(c).startswith(prefixo + "_")]:
        del st.session_state[chave]


@st.dialog("📂 Prazo", width="large")
def janela_ver_prazo(id_prazo: int, df_prazos: pd.DataFrame, df_processos: pd.DataFrame) -> None:
    """Consulta completa de um prazo, com opção de editar."""
    modo_chave = f"ver_prazo_modo_{id_prazo}"
    if st.session_state.get(modo_chave) == "editar":
        st.markdown("#### ✏️ Editando o prazo")
        formulario_editar_prazo(
            id_prazo, df_prazos, df_processos,
            ao_cancelar=lambda: st.session_state.pop(modo_chave, None),
        )
        return

    encontrados = df_prazos[df_prazos["id"] == id_prazo]
    if encontrados.empty:
        st.warning("Este prazo não foi encontrado. Clique em 🔄 Recarregar Dados.")
        return
    prazo = enriquecer(encontrados.copy()).iloc[0]

    parte = ""
    acao = ""
    if not df_processos.empty:
        proc = df_processos[df_processos["numero"] == prazo["processo"]]
        if not proc.empty:
            parte = proc.iloc[0]["parte_contraria"] or ""
            acao = proc.iloc[0]["descricao"] or ""

    st.markdown(f"### {prazo['titulo']}")
    st.markdown(f"**Situação:** {prazo['situacao']}  ·  **{int(prazo['dias_uteis'])}** dia(s) útil(eis)")

    c1, c2 = st.columns(2)
    c1.markdown(f"**👤 Cliente:** {prazo['cliente']}")
    c2.markdown(f"**⚔️ Parte contrária:** {parte or '—'}")
    c1.markdown(f"**📌 Processo:** `{prazo['processo']}`")
    c2.markdown(f"**⚖️ Ação:** {acao or '—'}")
    c1.markdown(f"**🗓️ Prazo interno:** {formatar_data_brasil(prazo['data_interna']) or '—'}")
    c2.markdown(f"**🔚 Data fatal:** {formatar_data_brasil(prazo['data_fatal'])}")
    c1.markdown(f"**👨‍⚖️ Responsável:** {prazo['responsavel']}")
    c2.markdown(f"**⚡ Prioridade:** {prazo['prioridade']}")
    st.markdown(f"**🏷️ Tipo:** {prazo['tipo']}")

    st.markdown("**📝 Observações:**")
    if isinstance(prazo["descricao"], str) and prazo["descricao"].strip():
        st.info(prazo["descricao"])
    else:
        st.caption("Sem observações.")

    b1, b2 = st.columns(2)
    if b1.button("✏️ Editar este prazo", type="primary", use_container_width=True, key=f"ver_editar_{id_prazo}"):
        st.session_state[modo_chave] = "editar"
        st.rerun(scope="fragment")
    if b2.button("Fechar", use_container_width=True, key=f"ver_fechar_{id_prazo}"):
        st.rerun()


def dashboard_cards_hierarquico(df_prazos: pd.DataFrame, df_audiencias: pd.DataFrame, df_processos: pd.DataFrame = None) -> None:
    """
    PASSO 2: Visão Cards Hierárquica
    PASSO 3: Integração com Modal de Ficha Integral
    Agrupa prazos e audiências por cliente em cards aninhados.
    """
    if df_processos is None:
        df_processos = pd.DataFrame()
    st.markdown("# 📌 Visão Cards")
    st.caption("🎯 Organize seus dados por cliente com cards hierárquicos")

    # Enriquecer prazos com cores
    if not df_prazos.empty:
        df_prazos = enriquecer(df_prazos)

    # ===== PRAZOS EM ABERTO, DO VENCIMENTO MAIS PRÓXIMO PARA O MAIS DISTANTE =====
    if df_prazos.empty:
        prazos_em_aberto = df_prazos
    else:
        prazos_em_aberto = df_prazos[~df_prazos["arquivado"] & ~df_prazos["concluido"]].sort_values("data_fatal")

    # ===== AUDIÊNCIAS PROGRAMADAS (futuras, não realizadas nem canceladas), EM ORDEM DE DATA E HORA =====
    if df_audiencias.empty:
        df_aud_ativas = df_audiencias
    else:
        hoje_data = pd.Timestamp.now(tz="America/Sao_Paulo").date()
        df_aud_ativas = df_audiencias[
            (df_audiencias["status"] != "Realizada") &
            (df_audiencias["status"] != "Cancelada") &
            (pd.to_datetime(df_audiencias["data_audiencia"]).dt.date >= hoje_data)
        ].copy()
        df_aud_ativas["_ordem_hora"] = df_aud_ativas["hora_inicio"].astype(str)
        df_aud_ativas = df_aud_ativas.sort_values(["data_audiencia", "_ordem_hora"])

    col_prazos, col_audiencias = st.columns(2, gap="large")

    # ===== SEÇÃO PRAZOS =====
    with col_prazos:
        with st.expander(f"📋 **PRAZOS** · {len(prazos_em_aberto)} em aberto", expanded=True):
            if prazos_em_aberto.empty:
                st.info("✅ Nenhum prazo em aberto.")
            else:
                # ===== ORDENAR CLIENTES POR DATA FATAL MAIS PRÓXIMA =====
                clientes_com_datas = []
                for cliente in prazos_em_aberto["cliente"].dropna().unique():
                    prazos_cliente = prazos_em_aberto[prazos_em_aberto["cliente"] == cliente]
                    data_proxima = prazos_cliente["data_fatal"].min()
                    clientes_com_datas.append((cliente, data_proxima, prazos_cliente))

                # Ordenar clientes pela data mais próxima
                clientes_com_datas.sort(key=lambda x: x[1])

                for cliente, _, prazos_abertos in clientes_com_datas:
                    qtd_abertos = len(prazos_abertos)
                    proximo = prazos_abertos.iloc[0]["data_fatal"].strftime("%d/%m")

                    # Só mostrar card se houver prazos abertos
                    if qtd_abertos > 0:
                        with st.expander(f"👤 **{cliente}** | 📋 {qtd_abertos} | 🔚 próximo: {proximo}"):
                            st.markdown("**📋 Prazos Pendentes:**")
                            cols = st.columns(2, gap="small")

                            for idx, (_, prazo) in enumerate(prazos_abertos.iterrows()):
                                col = cols[idx % 2]
                                with col:
                                    cor_fundo, emoji_status, texto_urgencia = _definir_cor_prazo(prazo)

                                    # ===== BUSCAR PARTE CONTRÁRIA =====
                                    parte_contraria = ""
                                    if not df_processos.empty and prazo['processo']:
                                        proc = df_processos[df_processos['numero'] == prazo['processo']]
                                        if not proc.empty:
                                            parte_contraria = proc.iloc[0]['parte_contraria']

                                    with st.container(border=True):
                                        st.markdown(f"<div style='font-size: 16px;'>{emoji_status}</div>", unsafe_allow_html=True)
                                        st.markdown(f"<b style='font-size: 13px;'>{prazo['titulo'][:30]}</b>", unsafe_allow_html=True)
                                        st.markdown(f"<small style='color: #888;'>👤 {cliente[:25]}</small>", unsafe_allow_html=True)
                                        if parte_contraria:
                                            st.markdown(f"<small style='color: #666;'>⚔️ {parte_contraria[:25]}</small>", unsafe_allow_html=True)
                                        st.markdown(f"<small style='color: #888;'>{prazo['data_fatal'].strftime('%d/%m')}</small>", unsafe_allow_html=True)
                                        st.markdown(f"<div style='background-color: {cor_fundo}; padding: 2px 4px; border-radius: 3px; text-align: center; font-size: 9px; font-weight: bold; color: white;'>{texto_urgencia[:8]}</div>", unsafe_allow_html=True)

                                        # PASSO 3: Botão para abrir modal do cliente
                                        if st.button("👁️ Ver Ficha", key=f"ficha_{prazo['id']}", use_container_width=True):
                                            st.session_state.modal_cliente = cliente
                                            st.rerun()

    # ===== SEÇÃO AUDIÊNCIAS =====
    with col_audiencias:
        with st.expander(f"📅 **AUDIÊNCIAS** · {len(df_aud_ativas)} agendada(s)", expanded=True):
            if df_audiencias.empty:
                st.info("Nenhuma audiência cadastrada.")
            else:
                if df_aud_ativas.empty:
                    st.info("✅ Nenhuma audiência programada!")
                else:
                    # ===== ORDENAR CLIENTES POR DATA DE AUDIÊNCIA MAIS PRÓXIMA =====
                    clientes_com_datas_aud = []
                    for cliente in df_aud_ativas["autor"].dropna().unique():
                        audiencias_cliente = df_aud_ativas[df_aud_ativas["autor"] == cliente]
                        data_proxima_aud = pd.to_datetime(audiencias_cliente["data_audiencia"]).min()
                        clientes_com_datas_aud.append((cliente, data_proxima_aud, audiencias_cliente))

                    # Ordenar clientes pela data mais próxima
                    clientes_com_datas_aud.sort(key=lambda x: x[1])

                    for cliente, _, audiencias_cliente in clientes_com_datas_aud:
                        qtd_audiencias = len(audiencias_cliente)
                        proxima = audiencias_cliente.iloc[0]["data_audiencia"].strftime("%d/%m")

                        # Card do cliente
                        if qtd_audiencias > 0:
                            with st.expander(f"👤 **{cliente}** | 📅 {qtd_audiencias} | 🗓️ próxima: {proxima}"):
                                cols = st.columns(1, gap="small")

                                for idx, (_, aud) in enumerate(audiencias_cliente.iterrows()):
                                    with st.container(border=True):
                                        col1, col2 = st.columns([1, 1])

                                        with col1:
                                            st.markdown(f"**📌 Processo:** `{aud['processo']}`")
                                            st.markdown(f"**⚖️ Réu:** {aud['reu']}")

                                        with col2:
                                            st.markdown(f"**📅 Data:** {aud['data_audiencia'].strftime('%d/%m/%Y')}")
                                            st.markdown(f"**🕐 Horário:** {aud['hora_inicio']} - {aud['hora_termino']}")

                                        # Status badge
                                        status_colors = {"Agendada": "#3498db", "Realizada": "#2ecc71", "Cancelada": "#e74c3c"}
                                        status_color = status_colors.get(aud["status"], "#95a5a6")
                                        st.markdown(f"<div style='background-color: {status_color}; padding: 4px 8px; border-radius: 3px; text-align: center; font-size: 11px; font-weight: bold; color: white;'>{aud['status']}</div>", unsafe_allow_html=True)

@st.dialog("📋 Ficha Integral do Cliente", width="large")
def modal_ficha_cliente(cliente: str, df_prazos: pd.DataFrame, df_processos: pd.DataFrame, df_audiencias: pd.DataFrame) -> None:
    """
    PASSO 3: Modal com Ficha Integral do Cliente (3 abas)
    Aba 1: Resumo e Status
    Aba 2: Prazos Detalhados com Ações
    Aba 3: Audiências e Timeline
    """
    if not cliente or cliente.strip() == "":
        st.error("Cliente não fornecido")
        return

    # Filtrar dados do cliente
    prazos_cliente = df_prazos[df_prazos["cliente"] == cliente].copy()
    processos_cliente = df_processos[df_processos["cliente"] == cliente].copy()
    audiencias_cliente = df_audiencias[df_audiencias["autor"] == cliente].copy()

    # Enriquecer prazos
    if not prazos_cliente.empty:
        prazos_cliente = enriquecer(prazos_cliente)

    tab1, tab2, tab3 = st.tabs(["📊 Resumo", "📋 Prazos", "📅 Audiências"])

    # ===== ABA 1: RESUMO E STATUS =====
    with tab1:
        st.markdown(f"## 👤 {cliente}")

        col1, col2, col3, col4 = st.columns(4)

        prazos_abertos = prazos_cliente[~prazos_cliente["concluido"] & ~prazos_cliente["arquivado"]]
        prazos_concluidos = prazos_cliente[prazos_cliente["concluido"]]
        prazos_vencidos = prazos_abertos[prazos_abertos["faixa"] == "Vencido"]

        col1.metric("📋 Prazos Ativos", len(prazos_abertos))
        col2.metric("✅ Concluídos", len(prazos_concluidos))
        col3.metric("🔴 Vencidos", len(prazos_vencidos))
        col4.metric("⚖️ Processos", len(processos_cliente))

        st.divider()

        if not processos_cliente.empty:
            st.markdown("### 📝 Processos do Cliente")

            for _, proc in processos_cliente.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        st.markdown(f"**{proc['numero']}**")
                        st.caption(f"⚔️ {proc['parte_contraria']}")

                    with col2:
                        if proc['descricao']:
                            st.caption(f"📌 {proc['descricao']}")
                        else:
                            st.caption("—")

                    with col3:
                        prazos_proc = prazos_cliente[prazos_cliente["processo"] == proc["numero"]]
                        st.metric("Prazos", len(prazos_proc[~prazos_proc["concluido"] & ~prazos_proc["arquivado"]]), label_visibility="collapsed")
        else:
            st.info("Nenhum processo cadastrado para este cliente")

    # ===== ABA 2: PRAZOS DETALHADOS COM AÇÕES =====
    with tab2:
        st.markdown("### 📋 Prazos Detalhados")

        if prazos_abertos.empty and prazos_concluidos.empty:
            st.info("Nenhum prazo cadastrado para este cliente")
        else:
            # Separar abertos e concluídos
            if not prazos_abertos.empty:
                st.markdown("#### 📌 Prazos Pendentes")

                for _, prazo in prazos_abertos.iterrows():
                    cor_fundo, emoji_status, texto_urgencia = _definir_cor_prazo(prazo)

                    # ===== BUSCAR PARTE CONTRÁRIA =====
                    parte_contraria = ""
                    if df_processos is not None and not df_processos.empty and prazo.get('processo'):
                        proc = df_processos[df_processos['numero'] == prazo['processo']]
                        if not proc.empty:
                            parte_contraria = proc.iloc[0]['parte_contraria']

                    with st.container(border=True):
                        col1, col2 = st.columns([4, 1])

                        with col1:
                            st.markdown(f"{emoji_status} **{prazo['titulo']}**")

                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.caption(f"📌 Processo: `{prazo['processo']}`")
                                st.caption(f"👤 Responsável: {prazo['responsavel']}")
                                if parte_contraria:
                                    st.caption(f"⚔️ Parte Contrária: {parte_contraria[:40]}")

                            with col_info2:
                                st.caption(f"📅 Data Fatal: {prazo['data_fatal'].strftime('%d/%m/%Y')}")
                                st.caption(f"⏱️ Dias Úteis: {prazo['dias_uteis']}")

                            if prazo['descricao']:
                                st.info(f"📝 {prazo['descricao']}", icon="📝")

                        with col2:
                            st.markdown(f"<div style='background-color: {cor_fundo}; padding: 8px; border-radius: 4px; text-align: center; font-size: 12px; font-weight: bold; color: white; margin-top: 10px;'>{texto_urgencia}</div>", unsafe_allow_html=True)

                            # Botão de editar - usa session state para evitar conflito de layout
                            if st.button("✏️ Editar", key=f"editar_ficha_{prazo['id']}", use_container_width=True):
                                st.session_state.editar_prazo_id = int(prazo["id"])
                                st.session_state.modal_aberto = False
                                st.rerun()

                st.divider()

            # Concluídos
            if not prazos_concluidos.empty:
                st.markdown("#### ✅ Prazos Concluídos")

                for _, prazo in prazos_concluidos.iterrows():
                    # ===== BUSCAR PARTE CONTRÁRIA =====
                    parte_contraria = ""
                    if df_processos is not None and not df_processos.empty and prazo.get('processo'):
                        proc = df_processos[df_processos['numero'] == prazo['processo']]
                        if not proc.empty:
                            parte_contraria = proc.iloc[0]['parte_contraria']

                    with st.container(border=True):
                        col1, col2 = st.columns([4, 1])

                        with col1:
                            st.markdown(f"✅ **{prazo['titulo']}**")

                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.caption(f"📌 Processo: `{prazo['processo']}`")
                                st.caption(f"👤 Responsável: {prazo['responsavel']}")
                                if parte_contraria:
                                    st.caption(f"⚔️ Parte Contrária: {parte_contraria[:40]}")

                            with col_info2:
                                try:
                                    if pd.notna(prazo['concluido_em']):
                                        data_conc = pd.Timestamp(prazo['concluido_em']).strftime('%d/%m/%Y')
                                    else:
                                        data_conc = "—"
                                except:
                                    data_conc = "—"
                                st.caption(f"✅ Concluído em: {data_conc}")
                                st.caption(f"📅 Data Fatal: {prazo['data_fatal'].strftime('%d/%m/%Y')}")

                        with col2:
                            st.markdown("<div style='background-color: #2ecc71; padding: 8px; border-radius: 4px; text-align: center; font-size: 12px; font-weight: bold; color: white; margin-top: 10px;'>✅ OK</div>", unsafe_allow_html=True)

    # ===== ABA 3: AUDIÊNCIAS E TIMELINE =====
    with tab3:
        st.markdown("### 📅 Audiências")

        if audiencias_cliente.empty:
            st.info("Nenhuma audiência cadastrada para este cliente")
        else:
            for _, aud in audiencias_cliente.iterrows():
                status_colors = {"Agendada": "#3498db", "Realizada": "#2ecc71", "Cancelada": "#e74c3c"}
                status_color = status_colors.get(aud["status"], "#95a5a6")

                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.markdown(f"**📌 Processo:** `{aud['processo']}`")

                        col_info1, col_info2 = st.columns(2)
                        with col_info1:
                            st.caption(f"⚖️ Réu: {aud['reu']}")
                            st.caption(f"📍 Sala: {aud['sala']}")

                        with col_info2:
                            st.caption(f"📅 Data: {aud['data_audiencia'].strftime('%d/%m/%Y')}")
                            st.caption(f"🕐 Horário: {aud['hora_inicio']} às {aud['hora_termino']}")

                        st.caption(f"📋 Tipo: {aud['tipo']} | Formato: {aud['formato']}")

                        if aud['observacoes']:
                            st.info(f"📝 {aud['observacoes']}")

                    with col2:
                        st.markdown(f"<div style='background-color: {status_color}; padding: 8px; border-radius: 4px; text-align: center; font-size: 12px; font-weight: bold; color: white; margin-top: 10px;'>{aud['status']}</div>", unsafe_allow_html=True)

def formatar_data_brasil(data) -> str:
    """Formata data para DD/MM/YYYY de forma robusta"""
    try:
        if pd.isna(data):
            return ""
        # Se já é string, tenta converter
        if isinstance(data, str):
            ts = pd.to_datetime(data)
        else:
            ts = pd.Timestamp(data)
        return ts.strftime("%d/%m/%Y")
    except:
        return str(data)

def relatorio_prazos_ativos(df_prazos: pd.DataFrame, df_processos: pd.DataFrame) -> None:
    """
    Relatório de Prazos Ativos/Pendentes com Filtros e Export
    """
    st.markdown("### 📋 Prazos Ativos")
    st.caption("Prazos pendentes a fazer")

    if df_prazos.empty:
        st.info("Nenhum prazo cadastrado.")
        return

    # Filtrar apenas ativos (não concluído e não arquivado)
    prazos_ativos = df_prazos[(~df_prazos["concluido"]) & (~df_prazos["arquivado"])].copy()

    if prazos_ativos.empty:
        st.success("✅ Nenhum prazo pendente! Tudo em dia!")
        return

    st.divider()

    # ===== FILTROS =====
    col1, col2, col3 = st.columns(3)

    with col1:
        data_inicio = st.date_input(
            "📅 Data Início",
            value=pd.Timestamp.now(tz="America/Sao_Paulo").date(),
            key="rel_ativos_data_inicio"
        )

    with col2:
        data_fim = st.date_input(
            "📅 Data Fim",
            value=pd.Timestamp.now(tz="America/Sao_Paulo").date() + pd.Timedelta(days=90),
            key="rel_ativos_data_fim"
        )

    with col3:
        responsaveis_unicos = ["Todos"] + sorted(df_prazos["responsavel"].dropna().unique().tolist())
        filtro_responsavel = st.selectbox(
            "👤 Responsável",
            responsaveis_unicos,
            key="rel_ativos_responsavel"
        )

    col4, col5 = st.columns(2)

    with col4:
        clientes_unicos = ["Todos"] + sorted(df_prazos["cliente"].dropna().unique().tolist())
        filtro_cliente = st.selectbox(
            "👤 Cliente",
            clientes_unicos,
            key="rel_ativos_cliente"
        )

    with col5:
        urgencias = ["Todos", "🔴 Vencido", "🟠 Vence hoje", "🟡 Até 3 dias", "🔵 Até 7 dias", "🟢 Mais de 7 dias"]
        filtro_urgencia = st.selectbox(
            "⚡ Urgência",
            urgencias,
            key="rel_ativos_urgencia"
        )

    st.divider()

    # ===== APLICAR FILTROS =====
    df_filtrado = prazos_ativos.copy()

    # Filtro de data
    if pd.notna(data_inicio):
        df_filtrado = df_filtrado[pd.to_datetime(df_filtrado["data_fatal"]).dt.date >= data_inicio]
    if pd.notna(data_fim):
        df_filtrado = df_filtrado[pd.to_datetime(df_filtrado["data_fatal"]).dt.date <= data_fim]

    # Filtro de responsável
    if filtro_responsavel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["responsavel"] == filtro_responsavel]

    # Filtro de cliente
    if filtro_cliente != "Todos":
        df_filtrado = df_filtrado[df_filtrado["cliente"] == filtro_cliente]

    # Filtro de urgência (requer enriquecer dados)
    if filtro_urgencia != "Todos":
        df_filtrado_enriquecido = enriquecer(df_filtrado)
        faixas_mapeadas = {v: k for k, v in FAIXAS.items() if k != "Concluído"}
        chave_faixa = [k for k, v in FAIXAS.items() if v == filtro_urgencia][0] if filtro_urgencia in FAIXAS.values() else None
        if chave_faixa:
            df_filtrado = df_filtrado_enriquecido[df_filtrado_enriquecido["faixa"] == chave_faixa]

    # ===== MÉTRICAS =====
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 Total Ativos", len(df_filtrado))
    col2.metric("📅 Período", f"{data_inicio.strftime('%d/%m')} a {data_fim.strftime('%d/%m')}")
    col3.metric("👤 Responsável", filtro_responsavel if filtro_responsavel != "Todos" else "Todos")
    col4.metric("🏢 Cliente", filtro_cliente if filtro_cliente != "Todos" else "Todos")

    st.divider()

    if df_filtrado.empty:
        st.info("Nenhum prazo encontrado com os filtros aplicados.")
        return

    # ===== TABELA DE RESULTADOS =====
    st.markdown("### 📋 Prazos Listados")

    # Preparar dados para exibição
    df_exibicao = df_filtrado[[
        "titulo", "cliente", "processo", "responsavel",
        "data_fatal", "descricao", "prioridade"
    ]].copy()

    # Formatar datas
    df_exibicao["data_fatal"] = df_exibicao["data_fatal"].apply(formatar_data_brasil)

    # Calcular dias faltando
    dias_faltando = []
    for _, row in df_filtrado.iterrows():
        try:
            data_fatal = pd.to_datetime(row["data_fatal"]).date()
            hoje_date = pd.Timestamp.now(tz="America/Sao_Paulo").date()
            dias = (data_fatal - hoje_date).days
            dias_faltando.append(dias)
        except:
            dias_faltando.append(None)

    df_exibicao["Dias Faltam"] = dias_faltando

    # Renomear colunas para exibição
    df_exibicao = df_exibicao.rename(columns={
        "titulo": "Prazo",
        "cliente": "Cliente",
        "processo": "Processo",
        "responsavel": "Responsável",
        "data_fatal": "Data Fatal",
        "descricao": "Descrição",
        "prioridade": "Prioridade"
    })

    # Exibir tabela (clique na caixinha da linha para abrir o prazo)
    st.caption("👉 Clique na caixinha à esquerda de uma linha para abrir o prazo, consultar e editar.")
    evento = st.dataframe(
        df_exibicao,
        use_container_width=True,
        height=400,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tabela_prazos_listados",
    )

    linhas = evento.selection.rows if evento is not None else []
    if linhas:
        selecionado = df_filtrado.iloc[linhas[0]]
        st.success(f"Selecionado: **{selecionado['titulo']}** — {selecionado['cliente']} — fatal {formatar_data_brasil(selecionado['data_fatal'])}")
        if st.button("📂 Abrir prazo", type="primary", use_container_width=True, key="abrir_prazo_listado"):
            janela_ver_prazo(int(selecionado["id"]), df_prazos, df_processos)

    st.divider()

    # ===== EXPORT EM EXCEL =====
    st.markdown("### 📥 Exportar Pauta")

    excel_path = gerar_excel_bonito(df_filtrado, df_processos)

    if excel_path:
        with open(excel_path, "rb") as f:
            st.download_button(
                label="📊 Baixar Pauta em Excel",
                data=f.read(),
                file_name=f"pauta_ativos_{data_inicio.strftime('%d_%m_%Y')}_a_{data_fim.strftime('%d_%m_%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

def relatorio_prazos_concluidos(df_prazos: pd.DataFrame, df_processos: pd.DataFrame) -> None:
    """
    PASSO 2.5: Relatório de Prazos Concluídos com Filtros e Export
    """
    st.markdown("### ✅ Prazos Concluídos")
    st.caption("Histórico e análise de prazos finalizados")

    if df_prazos.empty:
        st.info("Nenhum prazo cadastrado.")
        return

    # Filtrar apenas concluídos
    prazos_concluidos = df_prazos[df_prazos["concluido"] == True].copy()

    if prazos_concluidos.empty:
        st.warning("Nenhum prazo concluído ainda.")
        return

    st.divider()

    # ===== BUSCA RÁPIDA POR CLIENTE =====
    col_busca, col_vazio = st.columns([3, 2])

    with col_busca:
        busca_cliente = st.text_input("🔍 Buscar Cliente:", key="busca_concluidos", placeholder="Digite o nome do cliente...")

        if busca_cliente.strip():
            # Filtrar clientes que correspondem à busca
            clientes_filtrados = sorted([
                c for c in prazos_concluidos["cliente"].dropna().unique()
                if busca_cliente.lower() in c.lower()
            ])

            if clientes_filtrados:
                cliente_selecionado = st.selectbox(
                    "Selecione:",
                    clientes_filtrados,
                    key="cliente_sel_concluidos"
                )
            else:
                st.warning("Nenhum cliente encontrado com esse nome.")
                cliente_selecionado = None
        else:
            cliente_selecionado = None

    # ===== RESUMO DO CLIENTE SELECIONADO =====
    if cliente_selecionado:
        prazos_cliente = prazos_concluidos[prazos_concluidos["cliente"] == cliente_selecionado]

        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Prazos Concluídos", len(prazos_cliente))
        col2.metric("📋 Responsáveis", prazos_cliente["responsavel"].nunique())

        # Calcular período com segurança
        try:
            datas_validas = pd.to_datetime(prazos_cliente["concluido_em"]).dropna()
            if len(datas_validas) > 0:
                data_min = datas_validas.min().strftime('%d/%m')
                data_max = datas_validas.max().strftime('%d/%m')
                periodo = f"{data_min} a {data_max}"
            else:
                periodo = "—"
        except:
            periodo = "—"

        col3.metric("📅 Período", periodo)

        st.divider()

    # ===== FILTROS =====
    col1, col2, col3 = st.columns(3)

    with col1:
        data_inicio = st.date_input(
            "📅 Data Início",
            value=pd.Timestamp.now(tz="America/Sao_Paulo").date() - pd.Timedelta(days=30),
            key="rel_data_inicio"
        )

    with col2:
        data_fim = st.date_input(
            "📅 Data Fim",
            value=pd.Timestamp.now(tz="America/Sao_Paulo").date(),
            key="rel_data_fim"
        )

    with col3:
        responsaveis_unicos = ["Todos"] + sorted(df_prazos["responsavel"].dropna().unique().tolist())
        filtro_responsavel = st.selectbox(
            "👤 Responsável",
            responsaveis_unicos,
            key="rel_responsavel"
        )

    st.divider()

    # ===== APLICAR FILTROS =====
    df_filtrado = prazos_concluidos.copy()

    # Filtro GLOBAL de cliente (vem da busca no topo)
    # Se cliente foi selecionado na busca, filtrar APENAS ele
    if cliente_selecionado:
        df_filtrado = df_filtrado[df_filtrado["cliente"] == cliente_selecionado]

    # Filtro de data
    if pd.notna(data_inicio):
        df_filtrado = df_filtrado[pd.to_datetime(df_filtrado["concluido_em"]).dt.date >= data_inicio]
    if pd.notna(data_fim):
        df_filtrado = df_filtrado[pd.to_datetime(df_filtrado["concluido_em"]).dt.date <= data_fim]

    # Filtro de responsável
    if filtro_responsavel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["responsavel"] == filtro_responsavel]

    # ===== MÉTRICAS =====
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ Total Concluídos", len(df_filtrado))
    col2.metric("📅 Período", f"{data_inicio.strftime('%d/%m')} a {data_fim.strftime('%d/%m')}")
    col3.metric("👤 Responsável", filtro_responsavel if filtro_responsavel != "Todos" else "Todos")
    col4.metric("🏢 Cliente", cliente_selecionado if cliente_selecionado else "Todos")

    st.divider()

    if df_filtrado.empty:
        st.info("Nenhum prazo encontrado com os filtros aplicados.")
        return

    # ===== TABELA DE RESULTADOS =====
    st.markdown("### 📋 Prazos Concluídos")

    # Exibir cada prazo com botão para abrir detalhes
    for idx, (_, prazo) in enumerate(df_filtrado.iterrows()):
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])

        with col1:
            st.write(f"**{prazo['titulo'][:25]}**")
        with col2:
            st.write(f"📌 {prazo['cliente'][:20]}")
        with col3:
            st.write(f"📋 {prazo['processo']}")
        with col4:
            data_fatal = formatar_data_brasil(prazo['data_fatal'])
            data_conc = formatar_data_brasil(prazo['concluido_em'])
            st.write(f"{data_fatal} → {data_conc}")
        with col5:
            st.write(f"👤 {prazo['responsavel'][:12]}")
        with col6:
            if st.button("👁️ Ver", key=f"ver_prazo_{prazo['id']}"):
                st.session_state[f"modal_prazo_id_{idx}"] = prazo['id']
                st.session_state[f"modal_prazo_aberta_{idx}"] = True
                st.rerun()

        # Modal para ver detalhes
        if st.session_state.get(f"modal_prazo_aberta_{idx}", False):
            with st.container(border=True):
                st.markdown(f"## 📌 {prazo['titulo']}")

                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Cliente:** {prazo['cliente']}")
                    st.write(f"**Processo:** {prazo['processo']}")
                    st.write(f"**Data Fatal:** {formatar_data_brasil(prazo['data_fatal'])}")

                with col2:
                    st.write(f"**Responsável:** {prazo['responsavel']}")
                    st.write(f"**Prioridade:** {prazo['prioridade']}")
                    st.write(f"**Concluído em:** {formatar_data_brasil(prazo['concluido_em'])}")

                st.divider()
                st.markdown("### 📝 Anotações/Descrição:")
                st.info(prazo['descricao'] if prazo['descricao'] else "Sem anotações")

                st.divider()
                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("✏️ Editar", use_container_width=True, key=f"btn_edit_conc_{prazo['id']}"):
                        st.info("Funcionalidade de edição será implementada em breve!")
                        st.session_state[f"modal_prazo_aberta_{idx}"] = False
                        st.rerun()

                with col2:
                    st.write("")  # Espaçamento

                with col3:
                    if st.button("❌ Fechar", use_container_width=True, key=f"btn_fechar_conc_{prazo['id']}"):
                        st.session_state[f"modal_prazo_aberta_{idx}"] = False
                        st.rerun()

    st.divider()

    # ===== EXPORT EM EXCEL =====
    st.markdown("### 📥 Exportar Relatório")

    excel_path = gerar_excel_bonito(df_filtrado, df_processos)

    if excel_path:
        with open(excel_path, "rb") as f:
            st.download_button(
                label="📊 Baixar em Excel",
                data=f.read(),
                file_name=f"relatorio_concluidos_{data_inicio.strftime('%d_%m_%Y')}_a_{data_fim.strftime('%d_%m_%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    st.divider()

    # ===== AÇÕES EM LOTE =====
    st.markdown("### 🗑️ Arquivar Prazos Concluídos")
    st.info("Arquive os prazos concluídos para manter a interface limpa. Você pode restaurá-los depois na aba 'Pauta'.")

    if st.button("📦 Arquivar Todos Filtrados", use_container_width=True, type="secondary"):
        ids_para_arquivar = df_filtrado["id"].tolist()
        if ids_para_arquivar:
            campos_atualizacao = {id_prazo: {"arquivado": True} for id_prazo in ids_para_arquivar}
            atualizar_campos(campos_atualizacao)
            st.session_state.aviso = f"✅ {len(ids_para_arquivar)} prazo(s) arquivado(s)!"
            st.rerun()

def relatorio_audiencias(df_audiencias: pd.DataFrame) -> None:
    """
    Relatório de Audiências com Filtros e Export
    """
    st.markdown("### 📅 Audiências")
    st.caption("Acompanhe audiências programadas e realizadas")

    if df_audiencias.empty:
        st.info("Nenhuma audiência cadastrada.")
        return

    st.divider()

    # ===== FILTROS =====
    col1, col2, col3 = st.columns(3)

    with col1:
        data_inicio = st.date_input(
            "📅 Data Início",
            value=pd.Timestamp.now(tz="America/Sao_Paulo").date(),
            key="rel_aud_data_inicio"
        )

    with col2:
        data_fim = st.date_input(
            "📅 Data Fim",
            value=pd.Timestamp.now(tz="America/Sao_Paulo").date() + pd.Timedelta(days=90),
            key="rel_aud_data_fim"
        )

    with col3:
        statuses = ["Todos"] + sorted(df_audiencias["status"].dropna().unique().tolist())
        filtro_status = st.selectbox(
            "🎯 Status",
            statuses,
            key="rel_aud_status"
        )

    col4, col5 = st.columns(2)

    with col4:
        formatos = ["Todos"] + sorted(df_audiencias["formato"].dropna().unique().tolist())
        filtro_formato = st.selectbox(
            "💻 Formato",
            formatos,
            key="rel_aud_formato"
        )

    with col5:
        tipos = ["Todos"] + sorted(df_audiencias["tipo"].dropna().unique().tolist())
        filtro_tipo = st.selectbox(
            "📋 Tipo",
            tipos,
            key="rel_aud_tipo"
        )

    st.divider()

    # ===== APLICAR FILTROS =====
    df_filtrado = df_audiencias.copy()

    # Filtro de data
    if pd.notna(data_inicio):
        df_filtrado = df_filtrado[pd.to_datetime(df_filtrado["data_audiencia"]).dt.date >= data_inicio]
    if pd.notna(data_fim):
        df_filtrado = df_filtrado[pd.to_datetime(df_filtrado["data_audiencia"]).dt.date <= data_fim]

    # Filtro de status
    if filtro_status != "Todos":
        df_filtrado = df_filtrado[df_filtrado["status"] == filtro_status]

    # Filtro de formato
    if filtro_formato != "Todos":
        df_filtrado = df_filtrado[df_filtrado["formato"] == filtro_formato]

    # Filtro de tipo
    if filtro_tipo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["tipo"] == filtro_tipo]

    # ===== MÉTRICAS =====
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📅 Total", len(df_filtrado))
    col2.metric("📅 Período", f"{data_inicio.strftime('%d/%m')} a {data_fim.strftime('%d/%m')}")
    col3.metric("🎯 Status", filtro_status if filtro_status != "Todos" else "Todos")
    col4.metric("💻 Formato", filtro_formato if filtro_formato != "Todos" else "Todos")

    st.divider()

    if df_filtrado.empty:
        st.info("Nenhuma audiência encontrada com os filtros aplicados.")
        return

    # ===== TABELA DE RESULTADOS =====
    st.markdown("### 📋 Audiências Listadas")

    # Preparar dados para exibição
    df_exibicao = df_filtrado[[
        "processo", "autor", "reu", "data_audiencia", "hora_inicio",
        "hora_termino", "sala", "tipo", "formato", "status"
    ]].copy()

    # Formatar datas de audiência
    df_exibicao["data_audiencia"] = df_exibicao["data_audiencia"].apply(formatar_data_brasil)

    # Renomear colunas
    df_exibicao = df_exibicao.rename(columns={
        "processo": "Processo",
        "autor": "Autor",
        "reu": "Réu",
        "data_audiencia": "Data",
        "hora_inicio": "Início",
        "hora_termino": "Término",
        "sala": "Sala",
        "tipo": "Tipo",
        "formato": "Formato",
        "status": "Status"
    })

    # Exibir tabela
    st.dataframe(
        df_exibicao,
        use_container_width=True,
        height=400,
        hide_index=True
    )

def relatórios_dashboard(df_prazos: pd.DataFrame, df_processos: pd.DataFrame, df_audiencias: pd.DataFrame) -> None:
    """
    PASSO 2.5: Dashboard de Relatórios com 3 abas
    - Prazos Ativos
    - Prazos Concluídos
    - Audiências
    """
    st.markdown("# 📊 Relatórios")
    st.caption("Extraia pautas e relatórios de seu sistema")

    tab1, tab2, tab3 = st.tabs(["📋 Prazos Ativos", "✅ Concluídos", "📅 Audiências"])

    with tab1:
        relatorio_prazos_ativos(df_prazos, df_processos)

    with tab2:
        relatorio_prazos_concluidos(df_prazos, df_processos)

    with tab3:
        relatorio_audiencias(df_audiencias)

def gerenciar_clientes(df_processos: pd.DataFrame, df_prazos: pd.DataFrame) -> None:
    """Gerencia visualização de clientes (catálogo)."""
    st.subheader("👤 Cadastro de Clientes")

    if df_processos.empty:
        st.info("Nenhum cliente cadastrado.")
        return

    processos_ativos = df_processos[df_processos["ativo"]].copy()

    if processos_ativos.empty:
        st.info("Nenhum cliente ativo.")
        return

    # Obter lista única de clientes com seus processos
    clientes_unicos = sorted(processos_ativos["cliente"].dropna().unique())

    for cliente in clientes_unicos:
        processos_cliente = processos_ativos[processos_ativos["cliente"] == cliente].sort_values("numero")
        total_processos = len(processos_cliente)

        # Contar prazos por status
        prazos_cliente = df_prazos[df_prazos["cliente"] == cliente]
        prazos_abertos = prazos_cliente[~prazos_cliente["concluido"] & ~prazos_cliente["arquivado"]]
        prazos_concluidos = prazos_cliente[prazos_cliente["concluido"]]

        qtd_abertos = len(prazos_abertos)
        qtd_concluidos = len(prazos_concluidos)

        titulo_expander = f"👤 **{cliente}** | ⚖️ {total_processos} | 📋 {qtd_abertos} | ✅ {qtd_concluidos}"

        with st.expander(titulo_expander, expanded=False):
            st.markdown("**Processos do Cliente:**")

            for idx, proc in processos_cliente.iterrows():
                col1, col2, col3 = st.columns([2, 2, 1])

                with col1:
                    st.markdown(f"**{proc['numero']}**")

                with col2:
                    st.caption(f"⚔️ {proc['parte_contraria']}")

                with col3:
                    prazos_proc = df_prazos[df_prazos["processo"] == proc["numero"]]
                    prazos_abertos_proc = prazos_proc[~prazos_proc["concluido"] & ~prazos_proc["arquivado"]]
                    st.metric("Prazos", len(prazos_abertos_proc), label_visibility="collapsed")

            st.divider()
            st.markdown("**📝 Detalhes por Processo:**")

            for idx, proc in processos_cliente.iterrows():
                with st.expander(f"📌 {proc['numero']}", expanded=False):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**Informações:**")
                        st.write(f"🔹 **Nº:** `{proc['numero']}`")
                        st.write(f"👤 **Cliente:** {proc['cliente']}")
                        st.write(f"⚔️ **Adversário:** {proc['parte_contraria']}")
                        if proc["descricao"]:
                            st.write(f"📌 **Descrição:** {proc['descricao']}")

                    with col2:
                        prazos_proc = df_prazos[df_prazos["processo"] == proc["numero"]]
                        if not prazos_proc.empty:
                            st.markdown("**Prazos Associados:**")
                            for p_idx, prazo in prazos_proc.iterrows():
                                status = "✅" if prazo["concluido"] else "📋"
                                st.caption(f"{status} {prazo['titulo']}")
                        else:
                            st.info("Nenhum prazo associado")

def abrir_janela(nome: str) -> None:
    """Callback dos botões de cadastro: marca qual janela abrir."""
    st.session_state.janela_aberta = nome
    st.session_state.lancar_prazo_processo = None
    st.session_state.despacho_resultado = None

def formulario_novo_processo() -> None:
    v = st.session_state.form_v
    with st.form("proc"):
        numero = st.text_input("Nº CNJ *", value="", placeholder="0000000-00.0000.0.00.0000", key=f"pnumero_{v}")
        cliente = st.text_input("Cliente *", value="", key=f"pcliente_{v}")
        parte = st.text_input("Parte Adversária *", value="", key=f"pparte_{v}")

        # ===== NOVA: Seletor de Fase =====
        fase = st.selectbox(
            "Fase do Processo *",
            FASES_PROCESSO,
            index=0,
            key=f"pfase_{v}"
        )

        descricao = st.text_area("Descrição", value="", key=f"pdesc_{v}")
        if st.form_submit_button("💾 Salvar", type="primary", use_container_width=True):
            if numero and cliente and parte and fase:
                inserir_processo({
                    "numero": numero,
                    "cliente": cliente,
                    "parte_contraria": parte,
                    "fase": fase,
                    "descricao": descricao or None,
                    "ativo": True
                })
                st.session_state.form_v += 1
                st.session_state.aviso = "✅ Processo salvo com sucesso!"
                st.rerun()
            else:
                st.error("Preencha todos os campos obrigatórios!")

@st.dialog("📋 Novo Prazo", width="large")
def janela_novo_prazo(processos_df: pd.DataFrame) -> None:
    sidebar_novo_prazo(processos_df)

@st.dialog("📅 Nova Audiência", width="large")
def janela_nova_audiencia(processos_df: pd.DataFrame) -> None:
    sidebar_nova_audiencia(processos_df)

@st.dialog("⚖️ Novo Processo", width="large")
def janela_novo_processo() -> None:
    formulario_novo_processo()

# ===== LEITURA DE DESPACHO (regras, sem IA e sem enviar o texto para fora) =====
# Cada regra: (código do atalho, padrões procurados no texto sem acentos, prazo legal em dias úteis ou None)
REGRAS_DESPACHO = [
    ("CONTR-APEL", [r"contrarraz\w*.{0,80}apela", r"apela\w*.{0,120}contrarraz", r"intime-se o apelado"], 15),
    ("CONTR-AG-INSTR", [r"contraminuta", r"contrarraz\w*.{0,80}agravo"], 15),
    ("CONTR-RO", [r"contrarraz\w*.{0,80}recurso ordinario"], 8),
    ("EMEND-INI", [r"emend\w*.{0,40}inicial"], 15),
    ("REPLICA", [r"replica", r"(manifest|diga)\w*.{0,60}contestac", r"sobre a contestac"], 15),
    ("SPEC-PROV", [r"especific\w*.{0,40}provas", r"provas que pretende\w* produzir", r"provas a produzir"], None),
    ("ROL-TEST", [r"rol de testemunhas", r"arrol\w* testemunhas"], None),
    ("QUESITOS", [r"quesitos", r"assistente tecnico"], 15),
    ("MANIF-LAUDO", [r"(manifest|diga)\w*.{0,60}laudo", r"sobre o laudo", r"laudo pericial"], 15),
    ("IMP-CALC-879", [r"impugn\w*.{0,40}calculo"], None),
    ("CALC-LIQ", [r"(manifest|diga)\w*.{0,60}calculo", r"sobre os calculos", r"calculos apresentados"], None),
    ("CONTR-DOC", [r"(manifest|diga)\w*.{0,60}documentos", r"sobre os documentos", r"documentos juntados"], None),
    ("RAZ-FIN", [r"memoriais", r"alegacoes finais"], 15),
    ("RAZ-FIN", [r"razoes finais"], None),
    ("INDIC-BENS", [r"indi\w*.{0,30}bens", r"bens (passiveis de|a) penhora"], None),
    ("IMP-CUMP", [r"impugn\w*.{0,40}cumprimento", r"art\.? ?525"], 15),
    ("CUMP-SENT", [r"cumprimento de sentenca", r"art\.? ?523"], None),
    ("APELAÇÃO", [r"julgo (procedente|improcedente|parcialmente)", r"\bsentenca\b.{0,200}(publique-se|registre-se)", r"extingo o (processo|feito)"], 15),
    ("EMB-DECL", [r"embargos de declarac", r"julgo (procedente|improcedente|parcialmente)"], 5),
    ("TERMO-AUD", [r"audiencia.{0,80}(designo|designada|marcada|para o dia|redesign)", r"designo audiencia"], None),
    ("ALVARA", [r"alvara"], None),
    ("ACORDO", [r"acordo", r"conciliac"], None),
    ("PED-SUSP", [r"suspens\w* (do|o) (processo|feito)"], None),
    ("PET-JUNT", [r"\bjunt(e|em|ar|ando)\b", r"\bcomprov(e|em|ar)\b", r"traga\w* aos autos", r"apresent\w* (o |os )?documento", r"recolh\w*.{0,40}(custas|despesa|preparo|condução|conducao|guia)"], None),
    ("MANIF", [r"manifeste-se", r"manifestem-se", r"\bdiga\b", r"\bdigam\b", r"para (que )?(se )?manifest", r"vista (a|as) parte", r"\binform(e|em|ar)\b", r"intime\w*.{0,60}para"], None),
]

_NUMEROS_EXTENSO = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
    "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
    "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20,
    "trinta": 30, "quarenta": 40, "quarenta e cinco": 45, "sessenta": 60, "noventa": 90,
}

def _dias_no_texto(texto_norm: str) -> list[str]:
    """Encontra prazos em dias escritos no despacho (ex.: 'prazo de 10 dias', 'quinze dias úteis')."""
    extenso = "|".join(sorted(_NUMEROS_EXTENSO, key=len, reverse=True))
    padrao = rf"\b(\d{{1,3}}|{extenso})\s*(?:\([^)]{{0,30}}\)\s*)?(dias?(?:\s+uteis|\s+corridos)?|horas)\b"
    achados = []
    for m in re.finditer(padrao, texto_norm):
        n = m.group(1)
        n = int(n) if n.isdigit() else _NUMEROS_EXTENSO[n]
        unidade = m.group(2).replace("dia ", "dias ").replace("uteis", "úteis")
        rotulo = f"{n} {unidade if unidade != 'dia' else 'dia'}"
        if rotulo not in achados:
            achados.append(rotulo)
    return achados

def _frases(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.;:!?])\s+|\n+", texto)
    return [p.strip() for p in partes if len(p.strip()) > 3]

def interpretar_despacho(texto: str, processos_df: pd.DataFrame) -> dict:
    """
    Lê o despacho e devolve:
    - processo: número encontrado no texto e cadastrado no app (ou None)
    - sugestoes: lista de possíveis prazos, na ordem em que aparecem no texto
    """
    texto_norm = remover_acentos(texto)
    frases = _frases(texto)
    frases_norm = [remover_acentos(f) for f in frases]
    dias_gerais = _dias_no_texto(texto_norm)

    # Processo pelo número CNJ (com ou sem pontuação)
    processo = None
    for m in re.finditer(r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}", texto):
        digitos = re.sub(r"\D", "", m.group(0))
        if not processos_df.empty:
            achado = processos_df[processos_df["numero"].fillna("").str.replace(r"\D", "", regex=True) == digitos]
            if not achado.empty:
                processo = achado.iloc[0]["numero"]
                break

    sugestoes = []
    for codigo, padroes, prazo_legal in REGRAS_DESPACHO:
        posicao = None
        for padrao in padroes:
            m = re.search(padrao, texto_norm)
            if m and (posicao is None or m.start() < posicao):
                posicao = m.start()
        if posicao is None:
            continue

        # Frase do despacho onde a regra apareceu
        trecho = ""
        for f, fn in zip(frases, frases_norm):
            if any(re.search(p, fn) for p in padroes):
                trecho = f
                break

        dias_trecho = _dias_no_texto(remover_acentos(trecho)) if trecho else []
        if dias_trecho:
            prazo_txt = f"{dias_trecho[0]} (indicado no despacho)"
        elif dias_gerais:
            prazo_txt = f"{dias_gerais[0]} (indicado no despacho)"
        elif prazo_legal:
            prazo_txt = f"{prazo_legal} dias úteis (prazo legal — conferir)"
        else:
            prazo_txt = "5 dias úteis se não houver prazo expresso (art. 218, § 3º, CPC — conferir)"

        sugestoes.append({
            "codigo": codigo,
            "titulo": ATALHOS.get(codigo) or TITULOS_EXTRAS_DESPACHO.get(codigo, codigo),
            "prazo": prazo_txt,
            "trecho": trecho,
            "posicao": posicao,
        })

    # Mais específicos primeiro (na ordem do texto); "Manifestação" genérica sempre por último
    sugestoes.sort(key=lambda x: (x["codigo"] == "MANIF", x["posicao"]))

    return {"processo": processo, "sugestoes": sugestoes}

def _observacao_sugerida(sugestao: dict) -> str:
    linhas = [f"⏱️ Prazo: {sugestao['prazo']}"]
    if sugestao["trecho"]:
        linhas.append(f"📄 Despacho: {sugestao['trecho']}")
    return "\n".join(linhas)

def ler_despacho() -> None:
    """Callback do botão Interpretar."""
    st.session_state.despacho_resultado = interpretar_despacho(
        st.session_state.get("texto_despacho", ""),
        st.session_state.get("_processos_despacho", pd.DataFrame()),
    )

@st.dialog("📝 Colar Despacho", width="large")
def janela_despacho(processos_df: pd.DataFrame) -> None:
    st.session_state["_processos_despacho"] = processos_df

    st.text_area(
        "Cole aqui o texto do despacho (ou da intimação):",
        key="texto_despacho",
        height=180,
        placeholder="Ex.: Intimem-se as partes para que, no prazo de 10 dias, manifestem-se acerca das provas que pretendem produzir...",
    )
    st.button("🔎 Interpretar despacho", type="primary", use_container_width=True, on_click=ler_despacho)

    resultado = st.session_state.get("despacho_resultado")
    if not resultado:
        st.caption("💡 As datas você preenche no formulário. O app sugere o título, o processo e as observações.")
        return

    st.divider()

    if not resultado["sugestoes"]:
        st.warning("Não identifiquei um prazo específico neste texto. Escolha o título manualmente abaixo.")
        sugestao = None
    else:
        st.markdown("#### 🎯 Possíveis prazos")
        opcoes = list(range(len(resultado["sugestoes"])))
        idx = st.radio(
            "Escolha o prazo a lançar:",
            options=opcoes,
            format_func=lambda i: f"{resultado['sugestoes'][i]['titulo']} — {resultado['sugestoes'][i]['prazo']}",
            key="sugestao_despacho_idx",
        )
        sugestao = resultado["sugestoes"][idx]

    if resultado["processo"]:
        st.success(f"📌 Processo identificado no texto: **{resultado['processo']}**")
    else:
        st.info("Número do processo não encontrado no texto (ou não cadastrado). Busque o processo abaixo.")

    st.markdown("#### ➕ Lançar Prazo")
    sidebar_novo_prazo(
        processos_df,
        processo_fixo=resultado["processo"],
        titulo_fixo=sugestao["titulo"] if sugestao else None,
        obs_inicial=_observacao_sugerida(sugestao) if sugestao else "",
    )

def definir_lancar_prazo(numero: str | None) -> None:
    """Callback: abre (numero) ou fecha (None) o formulário de prazo dentro da janela de processos."""
    st.session_state.lancar_prazo_processo = numero

@st.dialog("🗂️ Processos Cadastrados", width="large")
def janela_processos(df_processos: pd.DataFrame, df_prazos: pd.DataFrame) -> None:
    numero = st.session_state.get("lancar_prazo_processo")

    if numero:
        # ===== LANÇAR PRAZO NO PROCESSO ESCOLHIDO =====
        st.button(
            "🔙 Voltar à pesquisa",
            key="voltar_pesquisa_processos",
            on_click=definir_lancar_prazo,
            args=(None,),
        )

        st.markdown("### ➕ Lançar Prazo")
        sidebar_novo_prazo(df_processos, processo_fixo=numero)
    else:
        gerenciar_processos(df_processos, df_prazos)

def selecionar_menu(opcao: str) -> None:
    """Callback dos botões do menu lateral: guarda a opção escolhida."""
    st.session_state.aba_selecionada = opcao

def limpar_busca_cliente() -> None:
    """Callback para limpar a busca de cliente."""
    st.session_state.busca_temp_text = ""
    st.session_state.busca_cliente_sidebar = ""
    st.session_state.processo_abrir_automatico = None
    st.session_state.cliente_selecionado_dropdown = None
    st.session_state.sidebar_recolhida_para = None

def recolher_sidebar_no_celular() -> None:
    """
    Recolhe a barra lateral automaticamente em telas pequenas (celular),
    dando foco total à tela principal. No computador não faz nada.
    """
    import streamlit.components.v1 as components

    components.html(
        """
        <script>
        (function () {
            const pai = window.parent;
            if (!pai || pai.innerWidth > 768) return;  // só no celular
            const doc = pai.document;
            const seletores = [
                '[data-testid="stSidebarCollapseButton"] button',
                'section[data-testid="stSidebar"] [data-testid="baseButton-headerNoPadding"]',
                'section[data-testid="stSidebar"] button[kind="headerNoPadding"]'
            ];
            setTimeout(function () {
                for (const s of seletores) {
                    const botao = doc.querySelector(s);
                    if (botao) { botao.click(); break; }
                }
            }, 300);
        })();
        </script>
        """,
        height=0,
    )

def buscar_por_cliente(df_prazos: pd.DataFrame, df_audiencias: pd.DataFrame, cliente_busca: str) -> tuple:
    """
    Filtra prazos e audiências com busca INTELIGENTE e ROBUSTA:
    - Case-insensitive (maiúsculas/minúsculas)
    - Remove acentos para comparação
    - Busca parcial em múltiplos campos
    - Trata espaços extras
    """
    if not cliente_busca or cliente_busca.strip() == "":
        return df_prazos, df_audiencias

    busca_lower = cliente_busca.lower().strip()
    busca_sem_acentos = remover_acentos(busca_lower)

    # Filtrar prazos - busca em MÚLTIPLOS campos
    if not df_prazos.empty:
        mascara = (
            df_prazos["cliente"].fillna("").apply(remover_acentos).str.contains(busca_sem_acentos, na=False, regex=True) |
            df_prazos["cliente"].fillna("").str.lower().str.contains(busca_lower, na=False) |
            df_prazos["processo"].fillna("").str.lower().str.contains(busca_lower, na=False) |
            df_prazos["titulo"].fillna("").str.lower().str.contains(busca_lower, na=False) |
            df_prazos["descricao"].fillna("").str.lower().str.contains(busca_lower, na=False)
        )
        df_prazos_filtrados = df_prazos[mascara]
    else:
        df_prazos_filtrados = pd.DataFrame()

    # Filtrar audiências - busca em MÚLTIPLOS campos
    if not df_audiencias.empty:
        mascara_aud = (
            df_audiencias["processo"].fillna("").str.lower().str.contains(busca_lower, na=False) |
            df_audiencias["autor"].fillna("").str.lower().str.contains(busca_lower, na=False) |
            df_audiencias["reu"].fillna("").str.lower().str.contains(busca_lower, na=False) |
            df_audiencias["observacoes"].fillna("").str.lower().str.contains(busca_lower, na=False)
        )
        df_audiencias_filtradas = df_audiencias[mascara_aud]
    else:
        df_audiencias_filtradas = pd.DataFrame()

    return df_prazos_filtrados, df_audiencias_filtradas

def _definir_cor_prazo(prazo: dict) -> tuple[str, str, str]:
    """
    Define cor, emoji e texto de urgência baseado no status do prazo.
    Retorna: (cor_hex, emoji, texto_urgencia)
    """
    if prazo['concluido']:
        return "#2ecc71", "✅", "CONCLUÍDO"

    faixa = prazo.get('faixa', 'Futuro')

    if faixa == "Vencido":
        return "#e74c3c", "🔴", "VENCIDO"
    elif faixa == "Hoje":
        return "#e67e22", "🟠", "VENCE HOJE"
    elif faixa == "Até 3 dias":
        return "#f39c12", "🟡", "ATENÇÃO: 3 DIAS"
    elif faixa == "Até 7 dias":
        return "#3498db", "🔵", "7 DIAS"
    else:
        return "#95a5a6", "🟢", "EM DIA"

def renderizar_cards_prazos(df_prazos: pd.DataFrame, df_processos: pd.DataFrame = None) -> None:
    """
    Renderiza prazos como MINI CARDS CLICÁVEIS em GRID (5 colunas).
    Ao clicar, abre expander com TODOS os detalhes + o que precisa fazer.
    """
    if df_prazos.empty:
        st.info("📭 Nenhum prazo cadastrado.")
        return

    # Filtrar apenas prazos não arquivados
    df_exibir = df_prazos[~df_prazos["arquivado"]].copy()

    if df_exibir.empty:
        st.info("📭 Nenhum prazo ativo.")
        return

    # Enriquecer com informações de dias
    df_exibir = enriquecer(df_exibir)

    # Separar por status
    concluidos = df_exibir[df_exibir["concluido"]]
    pendentes = df_exibir[~df_exibir["concluido"]].sort_values("data_fatal")

    # ===== ABAS DE VISUALIZAÇÃO =====
    tab_pendentes, tab_concluidos = st.tabs([
        f"📋 Pendentes ({len(pendentes)})",
        f"✅ Concluídos ({len(concluidos)})"
    ])

    # ===== ABA PENDENTES (LAYOUT EM GRID 5 COLUNAS - ULTRA COMPACTO) =====
    with tab_pendentes:
        if pendentes.empty:
            st.success("✅ Nenhum prazo pendente!")
        else:
            # Renderizar em 5 colunas (MUITO mais compacto!)
            num_cols = 5
            cols = st.columns(num_cols, gap="small")

            for idx, (_, prazo) in enumerate(pendentes.iterrows()):
                col = cols[idx % num_cols]

                with col:
                    cor_fundo, emoji_status, texto_urgencia = _definir_cor_prazo(prazo)

                    # ===== BUSCAR PARTE CONTRÁRIA =====
                    parte_contraria = ""
                    if df_processos is not None and not df_processos.empty and prazo.get('processo'):
                        proc = df_processos[df_processos['numero'] == prazo['processo']]
                        if not proc.empty:
                            parte_contraria = proc.iloc[0]['parte_contraria']

                    # MINI CARD (ultra compacto)
                    with st.container(border=True):
                        # Emoji de status
                        st.markdown(f"<div style='font-size: 18px; line-height: 1.2;'>{emoji_status}</div>", unsafe_allow_html=True)

                        # TÍTULO GRANDE E LEGÍVEL (pelo menos 30 chars com quebra natural)
                        st.markdown(f"<div style='font-size: 12px; font-weight: bold; line-height: 1.4; word-wrap: break-word; margin: 4px 0;'>{prazo['titulo'][:35]}</div>", unsafe_allow_html=True)

                        # NOME DO CLIENTE (em destaque mas menor)
                        cliente_exib = prazo['cliente'] if prazo['cliente'] else "Sem cliente"
                        st.markdown(f"<div style='font-size: 11px; color: #666; font-weight: 500; margin: 2px 0;'>👤 {cliente_exib[:25]}</div>", unsafe_allow_html=True)

                        # ✨ PARTE CONTRÁRIA (se houver)
                        if parte_contraria:
                            st.markdown(f"<div style='font-size: 10px; color: #999; margin: 2px 0;'>⚔️ {parte_contraria[:20]}</div>", unsafe_allow_html=True)

                        # Data apenas (2 dígitos/mês)
                        data_str = prazo['data_fatal'].strftime("%d/%m")
                        st.markdown(f"<small style='color: #888;'>{data_str}</small>", unsafe_allow_html=True)

                        # Mini badge de urgência
                        st.markdown(f"<div style='background-color: {cor_fundo}; padding: 3px 6px; border-radius: 3px; text-align: center; font-size: 10px; font-weight: bold; color: white; margin: 4px 0;'>{texto_urgencia[:8]}</div>", unsafe_allow_html=True)

                        # Botão para abrir detalhes
                        if st.button("👁️ Ver", key=f"modal_{prazo['id']}", use_container_width=True, help="Clique para ver tudo"):
                            st.session_state.modal_aberta = True
                            st.session_state.id_modal = prazo['id']
                            st.session_state.modo_modal = None
                            st.rerun()

    # ===== ABA CONCLUÍDOS (GRID 5 COLUNAS) =====
    with tab_concluidos:
        if concluidos.empty:
            st.info("Nenhum prazo concluído ainda.")
        else:
            num_cols = 5
            cols = st.columns(num_cols, gap="small")

            for idx, (_, prazo) in enumerate(concluidos.iterrows()):
                col = cols[idx % num_cols]

                with col:
                    # ===== BUSCAR PARTE CONTRÁRIA =====
                    parte_contraria = ""
                    if df_processos is not None and not df_processos.empty and prazo.get('processo'):
                        proc = df_processos[df_processos['numero'] == prazo['processo']]
                        if not proc.empty:
                            parte_contraria = proc.iloc[0]['parte_contraria']

                    with st.container(border=True):
                        st.markdown(f"<div style='font-size: 18px; line-height: 1.2;'>✅</div>", unsafe_allow_html=True)
                        # TÍTULO GRANDE E LEGÍVEL (pelo menos 30 chars com quebra natural)
                        st.markdown(f"<div style='font-size: 12px; font-weight: bold; line-height: 1.4; word-wrap: break-word; margin: 4px 0;'>{prazo['titulo'][:35]}</div>", unsafe_allow_html=True)
                        # NOME DO CLIENTE (em destaque mas menor)
                        cliente_exib = prazo['cliente'] if prazo['cliente'] else "Sem cliente"
                        st.markdown(f"<div style='font-size: 11px; color: #666; font-weight: 500; margin: 2px 0;'>👤 {cliente_exib[:25]}</div>", unsafe_allow_html=True)

                        # ✨ PARTE CONTRÁRIA (se houver)
                        if parte_contraria:
                            st.markdown(f"<div style='font-size: 10px; color: #999; margin: 2px 0;'>⚔️ {parte_contraria[:20]}</div>", unsafe_allow_html=True)
                        try:
                            if pd.notna(prazo['concluido_em']):
                                data_conc = pd.Timestamp(prazo['concluido_em']).strftime("%d/%m")
                            else:
                                data_conc = "—"
                        except:
                            data_conc = "—"
                        st.markdown(f"<small style='color: #888;'>{data_conc}</small>", unsafe_allow_html=True)

                        if st.button("👁️ Ver", key=f"modal_conc_{prazo['id']}", use_container_width=True, help="Clique para ver"):
                            st.session_state.modal_aberta = True
                            st.session_state.id_modal = prazo['id']
                            st.session_state.modo_modal = None
                            st.rerun()

    # ===== MODAL COM DETALHES COMPLETOS =====
    if st.session_state.get("modal_aberta") and st.session_state.get("id_modal"):
        id_prazo = st.session_state.id_modal
        prazo = df_prazos[df_prazos["id"] == id_prazo]

        if not prazo.empty:
            prazo = prazo.iloc[0]
            modal_detalhes_prazo(prazo, id_prazo, df_prazos, df_processos)
            st.stop()

@st.dialog("📋 Detalhes Completos", width="large")
def modal_detalhes_prazo(prazo, id_prazo: int, df_prazos: pd.DataFrame, df_processos: pd.DataFrame) -> None:
    """Modal com detalhes completos de um prazo e ações rápidas."""

    st.markdown(f"#### {prazo['titulo']}")

    # ===== SEÇÃO 1: INFORMAÇÕES PRINCIPAIS =====
    st.subheader("📌 Informações da Tarefa")

    # ===== BUSCAR PARTE CONTRÁRIA =====
    parte_contraria = ""
    if df_processos is not None and not df_processos.empty and prazo.get('processo'):
        proc = df_processos[df_processos['numero'] == prazo['processo']]
        if not proc.empty:
            parte_contraria = proc.iloc[0]['parte_contraria']

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**🔹 Processo:** `{prazo['processo']}`")
        st.write(f"**👤 Cliente:** {prazo['cliente']}")
        if parte_contraria:
            st.write(f"**⚔️ Parte Contrária:** {parte_contraria}")
        st.write(f"**👨‍⚖️ Responsável:** {prazo['responsavel']}")
    with col2:
        st.write(f"**📅 Data Fatal:** {prazo['data_fatal'].strftime('%d/%m/%Y')}")
        prioridade_emoji = {"Alta": "🔴", "Normal": "🟡", "Baixa": "🟢"}.get(prazo['prioridade'], '⚪')
        st.write(f"**{prioridade_emoji} Prioridade:** {prazo['prioridade']}")
        st.write(f"**📝 Tipo:** {prazo['tipo']}")

    # ===== SEÇÃO 2: O QUE FAZER (OBSERVAÇÕES - DESTAQUE) =====
    st.divider()
    st.subheader("✅ O QUE PRECISA SER FEITO")

    if prazo['descricao']:
        st.success(prazo['descricao'])
    else:
        st.warning("⚠️ Nenhuma observação anotada. Clique em 'Editar' para adicionar o que precisa fazer!")

    # ===== SEÇÃO 3: INFORMAÇÕES ADICIONAIS =====
    st.divider()
    st.subheader("📊 Informações Adicionais")

    col1, col2 = st.columns(2)
    with col1:
        data_interna_str = prazo['data_interna'].strftime("%d/%m/%Y") if pd.notna(prazo['data_interna']) else "Não definido"
        st.write(f"**⏰ Prazo Interno:** {data_interna_str}")
        dias_uteis = prazo.get('dias_uteis', '?')
        st.write(f"**📅 Dias Úteis:** {dias_uteis}")
    with col2:
        faixa = prazo.get('faixa', 'Desconhecido')
        st.write(f"**🎯 Situação:** {prazo.get('situacao', faixa)}")
        if prazo['concluido']:
            try:
                if pd.notna(prazo['concluido_em']):
                    data_conc = pd.Timestamp(prazo['concluido_em']).strftime("%d/%m/%Y")
                else:
                    data_conc = "—"
            except:
                data_conc = "—"
            st.write(f"**✅ Concluído em:** {data_conc}")

    # ===== SEÇÃO 4: AÇÕES =====
    st.divider()
    st.subheader("⚙️ Ações Rápidas")

    col_acao1, col_acao2, col_acao3 = st.columns(3)

    with col_acao1:
        if not prazo['concluido']:
            if st.button("✅ Concluir Agora", use_container_width=True, key=f"btn_concl_{id_prazo}", type="primary"):
                atualizar_prazo(id_prazo, {"concluido": True, "concluido_em": dt.datetime.now(TZ).isoformat()})
                st.session_state.aviso = f"✅ '{prazo['titulo']}' concluído!"
                st.session_state.modal_aberta = False
                st.rerun()

    with col_acao2:
        if st.button("✏️ Editar Prazo", use_container_width=True, key=f"btn_edit_{id_prazo}"):
            st.session_state.modo_modal = "editar_prazo"
            st.rerun()

    with col_acao3:
        if st.button("🔙 Fechar", use_container_width=True, key=f"btn_fechar_{id_prazo}"):
            st.session_state.modal_aberta = False
            st.rerun()

    # ===== MODO EDIÇÃO: TODOS OS CAMPOS DO PRAZO =====
    if st.session_state.get("modo_modal") == "editar_prazo":
        st.divider()
        st.subheader("✏️ Editar Prazo")

        with st.form(f"form_edit_prazo_{id_prazo}"):
            novo_titulo = st.text_input("Título *", value=prazo["titulo"] or "")

            col_e1, col_e2 = st.columns(2)
            with col_e1:
                novo_tipo = st.selectbox(
                    "Tipo",
                    TIPOS,
                    index=TIPOS.index(prazo["tipo"]) if prazo["tipo"] in TIPOS else 0,
                )
                novo_responsavel = st.selectbox(
                    "Responsável",
                    RESPONSAVEIS,
                    index=RESPONSAVEIS.index(prazo["responsavel"]) if prazo["responsavel"] in RESPONSAVEIS else 0,
                )
            with col_e2:
                nova_interna = st.date_input(
                    "Prazo Interno",
                    value=prazo["data_interna"] if pd.notna(prazo["data_interna"]) else None,
                    format="DD/MM/YYYY",
                )
                nova_fatal = st.date_input(
                    "Data Fatal *",
                    value=prazo["data_fatal"],
                    format="DD/MM/YYYY",
                )

            nova_prioridade = st.select_slider(
                "Prioridade",
                PRIORIDADES,
                value=prazo["prioridade"] if prazo["prioridade"] in PRIORIDADES else "Normal",
            )

            nova_obs = st.text_area(
                "O que precisa ser feito (observações):",
                value=prazo["descricao"] or "",
                height=150,
                placeholder="Ex:\n- Buscar documentação no tribunal\n- Enviar petição até 15h\n- Anexar comprovantes\n- Ligar para cliente",
            )

            col_form1, col_form2 = st.columns(2)
            with col_form1:
                salvar = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)
            with col_form2:
                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)

        if salvar:
            if not novo_titulo.strip() or not nova_fatal:
                st.error("Preencha o título e a data fatal!")
            elif nova_interna and nova_interna > nova_fatal:
                st.error("O prazo interno deve ser igual ou anterior à data fatal!")
            else:
                atualizar_prazo(id_prazo, {
                    "titulo": novo_titulo.strip(),
                    "tipo": novo_tipo,
                    "responsavel": novo_responsavel,
                    "prioridade": nova_prioridade,
                    "data_interna": nova_interna.isoformat() if nova_interna else None,
                    "data_fatal": nova_fatal.isoformat(),
                    "descricao": nova_obs or None,
                })
                st.session_state.aviso = "✅ Prazo atualizado!"
                st.session_state.modo_modal = None
                st.rerun()

        if cancelar:
            st.session_state.modo_modal = None
            st.rerun()

def main() -> None:
    init_estado()
    aplicar_tema(carregar_tema())
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
        # ===== CADASTROS: abrem em janela no centro da tela =====
        st.caption("➕ CADASTRAR")
        acoes_cadastro = {
            "📋 Novo Prazo": "novo_prazo",
            "📅 Nova Audiência": "nova_audiencia",
            "⚖️ Novo Processo": "novo_processo",
            "📝 Colar Despacho": "despacho",
        }
        for rotulo, janela in acoes_cadastro.items():
            st.button(
                rotulo,
                key=f"acao_{janela}",
                use_container_width=True,
                on_click=abrir_janela,
                args=(janela,),
            )

        st.caption("🧭 NAVEGAR")
        opcoes_menu = ["🏠 Início", "🎴 Cards", "📊 Relatórios", "📈 Dashboard"]

        # Garante que um valor antigo não quebre o menu
        if st.session_state.aba_selecionada not in opcoes_menu:
            st.session_state.aba_selecionada = opcoes_menu[0]

        # ===== MENU TOUCH-FRIENDLY: um botão de largura total por opção =====
        for opcao in opcoes_menu:
            st.button(
                opcao,
                key=f"menu_{opcao}",
                use_container_width=True,
                type="primary" if opcao == st.session_state.aba_selecionada else "secondary",
                on_click=selecionar_menu,
                args=(opcao,),
            )

        aba = st.session_state.aba_selecionada

        # ===== PESQUISA DE PROCESSOS: abre em janela no centro da tela =====
        st.button(
            "🗂️ Processos Cadastrados",
            key="acao_processos",
            use_container_width=True,
            on_click=abrir_janela,
            args=("processos",),
        )
        st.divider()

        if st.button("🔄 Recarregar Dados", use_container_width=True):
            carregar_prazos.clear()
            carregar_processos.clear()
            carregar_audiencias.clear()
            carregar_tema.clear()
            st.rerun()

        painel_aparencia()

        st.divider()

        # Busca por cliente removida da barra lateral (use 🗂️ Processos Cadastrados)
        cliente_busca = ""

        if aba == "🏠 Início":
            # Tela principal com as abas (Ativos, Concluídos, Pauta...)
            pass
        elif aba == "🎴 Cards":
            # PASSO 2: Visão Cards Hierárquica (sem filtro global, mostra tudo por cliente)
            pass  # Renderizado no main area abaixo
        elif aba == "📊 Relatórios":
            # PASSO 2.5: Dashboard de Relatórios (renderizado no main area abaixo)
            pass
        elif aba == "📈 Dashboard":
            # ===== APLICAR FILTRO DE BUSCA NO DASHBOARD =====
            df_prazos_filtrados, df_audiencias_filtradas = buscar_por_cliente(
                df_prazos, df_audiencias, cliente_busca
            )

            if cliente_busca:
                st.info(f"🔎 Filtrando por: **{cliente_busca}**")

            dashboard_completo(df_prazos_filtrados, df_audiencias_filtradas, df_processos)

    st.title("⚖️ Controladoria Jurídica")
    st.caption(f"Hoje: {hoje():%d/%m/%Y}")

    # ===== JANELAS DE CADASTRO (modal no centro da tela) =====
    janela = st.session_state.pop("janela_aberta", None)
    if janela == "novo_prazo":
        janela_novo_prazo(df_processos)
    elif janela == "nova_audiencia":
        janela_nova_audiencia(df_processos)
    elif janela == "novo_processo":
        janela_novo_processo()
    elif janela == "despacho":
        janela_despacho(df_processos)
    elif janela == "processos":
        janela_processos(df_processos, df_prazos)

    # ===== VERIFICAR SE PRECISA ABRIR MODAL DO CLIENTE =====
    if st.session_state.get("modal_cliente"):
        cliente_modal = st.session_state.pop("modal_cliente")
        modal_ficha_cliente(cliente_modal, df_prazos, df_processos, df_audiencias)

    # ===== VERIFICAR SE PRECISA ABRIR JANELA DE EDITAR (após modal fechar) =====
    if st.session_state.get("editar_prazo_id"):
        id_editar = st.session_state.pop("editar_prazo_id")
        janela_editar_prazo(id_editar, df_prazos, df_processos)

    if st.session_state.aviso:
        st.toast(st.session_state.aviso)
        st.session_state.aviso = None

    # ===== PASSO 2: RENDERIZAR VISÃO CARDS HIERÁRQUICA =====
    if aba == "🎴 Cards":
        dashboard_cards_hierarquico(df_prazos, df_audiencias, df_processos)
        st.stop()

    # ===== PASSO 2.5: RENDERIZAR DASHBOARD DE RELATÓRIOS =====
    if aba == "📊 Relatórios":
        relatórios_dashboard(df_prazos, df_processos, df_audiencias)
        st.stop()

    # ===== APLICAR FILTRO DE BUSCA NAS TABS =====
    df_prazos_filtrados, df_audiencias_filtradas = buscar_por_cliente(
        df_prazos, df_audiencias, cliente_busca
    )

    if cliente_busca:
        st.info(f"🔎 Filtrando por: **{cliente_busca}**")
        if df_prazos_filtrados.empty:
            st.warning("Nenhum prazo encontrado para este cliente.")
            st.stop()
    elif df_prazos.empty:
        st.info("Nenhum prazo.")
        st.stop()

    df_prazos = enriquecer(df_prazos_filtrados) if not df_prazos_filtrados.empty else pd.DataFrame()

    tab1, tab2, tab3, tab4, tab6 = st.tabs(["📋 Ativos", "✅ Concluídos", "📋 Pauta", "📦 Arquivo", "📅 Audiências"])

    with tab1:
        # ===== PASSO 1: CARDS COM CORES DINÂMICAS =====
        st.write("**Filtrar por responsável:**")
        filtro_tab1 = st.selectbox(
            "Selecione",
            ["Todos"] + RESPONSAVEIS,
            key="filtro_ativos",
            label_visibility="collapsed"
        )

        prazos_ativos = df_prazos[~df_prazos["concluido"] & ~df_prazos["arquivado"]]

        # Aplicar filtro de responsável se não for "Todos"
        if filtro_tab1 != "Todos":
            prazos_ativos = prazos_ativos[prazos_ativos["responsavel"] == filtro_tab1]

        # ===== RENDERIZAR CARDS EM VEZ DE TABELA =====
        renderizar_cards_prazos(prazos_ativos, df_processos)

    with tab2:
        # ===== PASSO 5: FILTRO NA TAB 2 =====
        st.subheader("📋 Relatório de Prazos")

        prazos_concluidos = df_prazos[df_prazos["concluido"]]
        prazos_arquivados = df_prazos[df_prazos["arquivado"]]

        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Concluídos", len(prazos_concluidos))
        col2.metric("📦 Arquivados", len(prazos_arquivados))
        col3.metric("🟢 Total", len(df_prazos))

        st.divider()
        st.markdown("**Prazos Concluídos:**")

        # Filtro para concluídos
        st.write("**Filtrar por responsável:**")
        filtro_tab2 = st.selectbox(
            "Selecione",
            ["Todos"] + RESPONSAVEIS,
            key="filtro_concluidos",
            label_visibility="collapsed"
        )

        if prazos_concluidos.empty:
            st.info("Nenhum prazo concluído ainda.")
        else:
            tabela_status(prazos_concluidos, df_processos, prefix="tab_concluidos", filtro_responsavel=filtro_tab2)

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

        prazos_ativos = df_prazos[~df_prazos["arquivado"] & ~df_prazos["concluido"]].copy()

        data_hoje = pd.Timestamp.now(tz="America/Sao_Paulo").date()
        data_semana = pd.Timestamp.now(tz="America/Sao_Paulo").date() + pd.Timedelta(days=7)

        if prazos_ativos.empty:
            st.info("✅ Nenhum prazo ativo no momento!")
        else:
            prazos_hoje = prazos_ativos[prazos_ativos["data_fatal"] == data_hoje]
            prazos_semana = prazos_ativos[(prazos_ativos["data_fatal"] > data_hoje) & (prazos_ativos["data_fatal"] <= data_semana)]
            prazos_futuro = prazos_ativos[prazos_ativos["data_fatal"] > data_semana]

            if not prazos_hoje.empty:
                st.markdown("### 🔴 **HOJE** (" + data_hoje.strftime("%d/%m/%Y") + ")")
                for _, p in prazos_hoje.iterrows():
                    col1, col2 = st.columns([3, 1])
                    col1.markdown(f"""
                    **{p['titulo']}** | {p['cliente']} / {p.get('parte_contraria', 'N/A')}

                    Responsável: {p['responsavel']} | Prioridade: {p['prioridade']}
                    """)
                st.divider()

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

            if not prazos_futuro.empty:
                st.markdown("### 🟡 **FUTURO** (após 7 dias)")
                for _, p in prazos_futuro.iloc[:10].iterrows():
                    col1, col2 = st.columns([3, 1])
                    col1.markdown(f"""
                    **{p['titulo']}** | {p['cliente']}

                    Data Fatal: {p['data_fatal'].strftime('%d/%m/%Y')} | Responsável: {p['responsavel']}
                    """)

        st.divider()
        st.subheader("📥 Exportar Pauta")

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

    with tab4:
        prazos_arquivados = df_prazos[df_prazos["arquivado"]]
        if prazos_arquivados.empty:
            st.info("Nenhum prazo arquivado.")
        else:
            st.subheader("📦 Prazos Arquivados")
            tabela_status(prazos_arquivados, df_processos, prefix="tab_arquivados")

    with tab6:
        st.subheader("📅 Audiências Agendadas")

        if df_audiencias.empty:
            st.info("Nenhuma audiência agendada.")
        else:
            audiencias_agendadas = df_audiencias[df_audiencias["status"] == "Agendada"].sort_values("data_audiencia")
            audiencias_realizadas = df_audiencias[df_audiencias["status"] == "Realizada"].sort_values("data_audiencia", ascending=False)
            audiencias_canceladas = df_audiencias[df_audiencias["status"] == "Cancelada"].sort_values("data_audiencia", ascending=False)

            col1, col2, col3 = st.columns(3)
            col1.metric("📅 Agendadas", len(audiencias_agendadas))
            col2.metric("✅ Realizadas", len(audiencias_realizadas))
            col3.metric("❌ Canceladas", len(audiencias_canceladas))

            st.divider()

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
