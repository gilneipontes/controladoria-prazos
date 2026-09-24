"""
Controladoria Jurídica — Dr. Gilnei Coelho Pontes & Dra. Jéssica
Stack: Streamlit + Supabase

Estrutura:
  1. Configuração e constantes
  2. Acesso (senha opcional via st.secrets)
  3. Camada de dados (Supabase: leitura com cache, escrita invalidando cache)
  4. Regras de negócio (urgência, dias úteis, validação)
  5. Interface (formulário lateral, filtros, métricas, tabela editável)
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
TABELA = "prazos"

RESPONSAVEIS = ["Dr. Gilnei", "Dra. Jéssica"]
TIPOS = ["Prazo processual", "Data fatal", "Tarefa operacional"]
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

COLUNAS = [
    "id", "created_at", "tipo", "titulo", "processo", "cliente", "responsavel",
    "data_fatal", "data_interna", "prioridade", "descricao", "concluido", "concluido_em",
    "arquivado",
]


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
    resp = supabase().table(TABELA).select("*").order("data_fatal").execute()
    df = pd.DataFrame(resp.data, columns=COLUNAS)
    for col in ("data_fatal", "data_interna"):
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    df["concluido"] = df["concluido"].fillna(False).astype(bool)
    df["arquivado"] = df["arquivado"].fillna(False).astype(bool)
    return df


def inserir(registro: dict) -> None:
    supabase().table(TABELA).insert(registro).execute()
    carregar_prazos.clear()


def atualizar_campos(atualizacoes: dict[int, dict]) -> None:
    """Atualiza múltiplos campos de vários registros."""
    for id_prazo, campos in atualizacoes.items():
        if campos:
            supabase().table(TABELA).update(campos).eq("id", id_prazo).execute()
    carregar_prazos.clear()


def arquivar_prazo(id_prazo: int) -> None:
    """Marca um prazo como arquivado."""
    supabase().table(TABELA).update({"arquivado": True}).eq("id", id_prazo).execute()
    carregar_prazos.clear()


def desarquivar_prazo(id_prazo: int) -> None:
    """Remove o arquivo de um prazo."""
    supabase().table(TABELA).update({"arquivado": False}).eq("id", id_prazo).execute()
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


# ───────────────────────── 5. Interface ─────────────────────────
def formulario_cadastro() -> None:
    v = st.session_state.form_v
    with st.sidebar:
        st.header("Novo prazo ou tarefa")
        with st.form(f"cadastro_{v}", border=False):
            tipo = st.selectbox("Tipo", TIPOS, key=f"tipo_{v}")
            titulo = st.text_input(
                "Título *", placeholder="Ex.: Contestação, juntar procuração", key=f"titulo_{v}"
            )
            processo = st.text_input(
                "Nº do processo", placeholder="0000000-00.0000.0.00.0000", key=f"proc_{v}"
            )
            cliente = st.text_input("Cliente", key=f"cli_{v}")
            responsavel = st.radio("Responsável *", RESPONSAVEIS, horizontal=True, key=f"resp_{v}")
            c1, c2 = st.columns(2)
            data_fatal = c1.date_input(
                "Data fatal *", value=None, format="DD/MM/YYYY", key=f"fatal_{v}"
            )
            data_interna = c2.date_input(
                "Prazo interno", value=None, format="DD/MM/YYYY", key=f"int_{v}",
                help="Data de segurança para concluir antes do vencimento.",
            )
            prioridade = st.select_slider("Prioridade", PRIORIDADES, value="Normal", key=f"prio_{v}")
            descricao = st.text_area("Observações", key=f"desc_{v}")
            enviar = st.form_submit_button("Salvar prazo", type="primary")

        if not enviar:
            return

        erros = validar(titulo, processo, data_fatal, data_interna)
        if erros:
            for e in erros:
                st.error(e)
            return

        registro = {
            "tipo": tipo,
            "titulo": titulo.strip(),
            "processo": processo.strip() or None,
            "cliente": cliente.strip() or None,
            "responsavel": responsavel,
            "data_fatal": data_fatal.isoformat(),
            "data_interna": data_interna.isoformat() if data_interna else None,
            "prioridade": prioridade,
            "descricao": descricao.strip() or None,
            "arquivado": False,
        }
        try:
            inserir(registro)
        except Exception as exc:
            st.error(f"O prazo não foi salvo. Detalhe do banco: {exc}")
            return

        st.session_state.aviso = f"Prazo salvo: {registro['titulo']} ({responsavel})"
        st.session_state.form_v += 1
        st.rerun()


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
    c[0].metric("Vencidos", vencidos)
    c[1].metric("Vencem hoje", int((pend["faixa"] == "Hoje").sum()))
    c[2].metric("Próximos 7 dias", int(pend["faixa"].isin(["Até 3 dias", "Até 7 dias"]).sum()))
    c[3].metric("Pendentes", len(pend))
    if vencidos:
        st.error(f"{vencidos} prazo(s) vencido(s) sem conclusão. Filtre por urgência para revisar.")


def tabela_status(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Nenhum registro com esses filtros. Ajuste os filtros ou cadastre um prazo na barra lateral.")
        return

    colunas_vis = [
        "id", "concluido", "situacao", "titulo", "processo", "cliente", "data_fatal",
        "data_interna", "dias_uteis", "tipo", "responsavel", "prioridade", "descricao",
    ]
    vis = (
        df.assign(_p=df["prioridade"].map(ORDEM_PRIORIDADE))
        .sort_values(["concluido", "data_fatal", "_p"])[colunas_vis]
        .set_index("id")
    )

    editado = st.data_editor(
        vis,
        key=f"editor_{st.session_state.editor_v}",
        hide_index=True,
        disabled=["situacao", "dias_uteis", "tipo", "responsavel"],
        column_config={
            "concluido": st.column_config.CheckboxColumn("Feito", help="Marque para concluir"),
            "situacao": "Situação",
            "titulo": st.column_config.TextColumn("Título", width="medium"),
            "processo": st.column_config.TextColumn("Processo", width="small"),
            "cliente": st.column_config.TextColumn("Cliente", width="small"),
            "data_fatal": st.column_config.DateColumn("Data fatal", format="DD/MM/YYYY"),
            "data_interna": st.column_config.DateColumn("Prazo interno", format="DD/MM/YYYY"),
            "dias_uteis": st.column_config.NumberColumn("Dias úteis"),
            "tipo": "Tipo",
            "responsavel": "Responsável",
            "prioridade": st.column_config.SelectboxColumn("Prioridade", options=PRIORIDADES),
            "descricao": st.column_config.TextColumn("Observações", width="large"),
        },
    )

    mudancas = {}
    for idx in editado.index:
        alterado = {}
        if editado.loc[idx, "concluido"] != vis.loc[idx, "concluido"]:
            alterado["concluido"] = editado.loc[idx, "concluido"]
            if editado.loc[idx, "concluido"]:
                alterado["concluido_em"] = dt.datetime.now(TZ).isoformat()
            else:
                alterado["concluido_em"] = None
        if editado.loc[idx, "titulo"] != vis.loc[idx, "titulo"]:
            alterado["titulo"] = editado.loc[idx, "titulo"].strip() or None
        if editado.loc[idx, "processo"] != vis.loc[idx, "processo"]:
            alterado["processo"] = editado.loc[idx, "processo"].strip() or None
        if editado.loc[idx, "cliente"] != vis.loc[idx, "cliente"]:
            alterado["cliente"] = editado.loc[idx, "cliente"].strip() or None
        if editado.loc[idx, "data_fatal"] != vis.loc[idx, "data_fatal"]:
            alterado["data_fatal"] = editado.loc[idx, "data_fatal"].isoformat()
        if editado.loc[idx, "data_interna"] != vis.loc[idx, "data_interna"]:
            data = editado.loc[idx, "data_interna"]
            alterado["data_interna"] = data.isoformat() if data else None
        if editado.loc[idx, "prioridade"] != vis.loc[idx, "prioridade"]:
            alterado["prioridade"] = editado.loc[idx, "prioridade"]
        if editado.loc[idx, "descricao"] != vis.loc[idx, "descricao"]:
            alterado["descricao"] = editado.loc[idx, "descricao"].strip() or None
        
        if alterado:
            mudancas[int(idx)] = alterado

    if mudancas:
        c1, c2 = st.columns([3, 1])
        c1.warning(f"Alterações não salvas: {len(mudancas)} prazo(s) modificado(s).")
        if c2.button("Salvar tudo", type="primary"):
            try:
                atualizar_campos(mudancas)
            except Exception as exc:
                st.error(f"Não foi salvo. Detalhe: {exc}")
                return
            st.session_state.aviso = "Prazos salvos!"
            st.session_state.editor_v += 1
            st.rerun()

    st.divider()
    st.subheader("📦 Arquivar prazo")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    id_selecionado = col1.selectbox(
        "Selecione o prazo para arquivar",
        options=df["id"].values,
        format_func=lambda x: f"{df[df['id'] == x]['titulo'].values[0]} | Proc: {df[df['id'] == x]['processo'].values[0] or '-'} | Cliente: {df[df['id'] == x]['cliente'].values[0] or '-'} | Data: {df[df['id'] == x]['data_fatal'].values[0]}",
        key="select_arquivar_prazo"
    )
    
    st.session_state.id_arquivar_selecionado = id_selecionado
    
    if col2.button("📦 Arquivar", type="secondary", key="btn_arquivar"):
        st.rerun()
    
    if col3.button("✅ Confirmar", type="primary", key="btn_confirmar_arquivar"):
        if st.session_state.id_arquivar_selecionado:
            try:
                arquivar_prazo(st.session_state.id_arquivar_selecionado)
                st.session_state.aviso = "Prazo arquivado!"
                st.session_state.editor_v += 1
                st.session_state.id_arquivar_selecionado = None
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi arquivado. Detalhe: {exc}")


def relatorio_arquivados(df: pd.DataFrame) -> None:
    """Mostra relatório dos prazos arquivados."""
    arquivados = df[df["arquivado"]]
    
    if arquivados.empty:
        st.info("Nenhum prazo arquivado.")
        return
    
    st.subheader(f"📋 Relatório de Arquivados ({len(arquivados)})")
    
    colunas_rel = ["id", "titulo", "processo", "cliente", "responsavel", "data_fatal", "concluido_em", "prioridade"]
    rel = arquivados[colunas_rel].copy()
    rel = rel.rename(columns={
        "id": "ID",
        "titulo": "Título",
        "processo": "Processo",
        "cliente": "Cliente",
        "responsavel": "Responsável",
        "data_fatal": "Data Fatal",
        "concluido_em": "Concluído em",
        "prioridade": "Prioridade"
    })
    
    st.dataframe(rel, use_container_width=True, hide_index=True)


def aba_desarquivar(df: pd.DataFrame) -> None:
    """Aba para desarquivar prazos."""
    arquivados = df[df["arquivado"]]
    
    if arquivados.empty:
        st.info("Nenhum prazo arquivado para desarquivar.")
        return
    
    st.subheader("🔄 Desarquivar prazo")
    st.write(f"Total de arquivados: **{len(arquivados)}**")
    st.divider()
    
    col1, col2 = st.columns([2, 1])
    
    id_desarquivar = col1.selectbox(
        "Selecione o prazo para desarquivar",
        options=arquivados["id"].values,
        format_func=lambda x: f"{arquivados[arquivados['id'] == x]['titulo'].values[0]} | Proc: {arquivados[arquivados['id'] == x]['processo'].values[0] or '-'} | Cliente: {arquivados[arquivados['id'] == x]['cliente'].values[0] or '-'} | Data: {arquivados[arquivados['id'] == x]['data_fatal'].values[0]}",
        key="select_desarquivar"
    )
    
    if col2.button("🔄 Desarquivar", type="secondary", key="btn_desarquivar"):
        try:
            desarquivar_prazo(id_desarquivar)
            st.session_state.aviso = "Prazo desarquivado!"
            st.session_state.editor_v += 1
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi desarquivado. Detalhe: {exc}")


def main() -> None:
    init_estado()
    if not acesso_liberado():
        st.stop()

    formulario_cadastro()
    with st.sidebar:
        st.divider()
        if st.button("Recarregar dados", help="Busca alterações feitas pela outra pessoa"):
            carregar_prazos.clear()
            st.rerun()

    st.title("⚖️ Controladoria Jurídica")
    st.caption(f"Hoje é {hoje():%d/%m/%Y} (horário de Brasília)")

    if st.session_state.aviso:
        st.toast(st.session_state.aviso, icon="✅")
        st.session_state.aviso = None

    try:
        df = carregar_prazos()
    except Exception as exc:
        st.error(f"Não foi possível conectar ao banco. Verifique os secrets do Supabase. Detalhe: {exc}")
        st.stop()

    if df.empty:
        st.info("Nenhum prazo cadastrado ainda. Use o formulário na barra lateral para começar.")
        return

    df = enriquecer(df)
    
    tab1, tab2, tab3 = st.tabs(["📅 Prazos", "📋 Relatório", "🔄 Desarquivar"])
    
    with tab1:
        topo = st.container()
        with st.expander("Filtros", expanded=True):
            filtrado, resp = aplicar_filtros(df)
        with topo:
            painel_metricas(df, resp)

        st.subheader(f"Prazos e tarefas ({len(filtrado)})")
        tabela_status(filtrado)
    
    with tab2:
        relatorio_arquivados(df)
    
    with tab3:
        aba_desarquivar(df)


main()
