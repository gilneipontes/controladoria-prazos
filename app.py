import streamlit as st
from supabase import create_client, Client

# Configuração da página para exibir corretamente em dispositivos móveis e desktop
st.set_page_config(page_title="Controladoria de Prazos", page_icon="⚖️", layout="wide")

# Conexão com o Supabase
SUPABASE_URL = "https://yazrhjrjynbfxfbiwjst.supabase.co"
SUPABASE_KEY = "sb_publishable_liXURv5apqJwI26xSITUhQ_gHJA_oA7"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Título do Painel
st.title("⚖️ Controladoria Jurídica - Prazos e Tarefas")

# Busca os registos na tabela 'prazos' ordenados por data fatal
try:
    response = supabase.table("prazos").select("*").order("data_limite_fatal", desc=False).execute()
    prazos = response.data
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados: {e}")
    prazos = []

if not prazos:
    st.info("Nenhum prazo cadastrado até o momento. O sistema exibirá os registos assim que forem inseridos no banco de dados!")
else:
    for item in prazos:
        status_label = item.get('status', '🔴 Pendente')
        processo = item.get('processo_cnj', 'N/A')
        data_fatal = item.get('data_limite_fatal', 'N/A')
        
        with st.expander(f"📌 Processo: {processo} | Fatal: {data_fatal} | Status: {status_label}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Cliente:** {item.get('cliente', 'Não informado')}")
                st.write(f"**Juízo:** {item.get('comarca_vara', 'Não informado')}")
                st.write(f"**Classe:** {item.get('classe_acao', 'Não informado')}")
                st.write(f"**Disponibilização:** {item.get('data_disponibilizacao', 'N/A')}")
            
            with col2:
                st.write("**Resumo / Determinação:**")
                st.write(item.get('teor_resumido', 'Sem resumo.'))
            
            st.markdown("---")
            st.write("📋 **Tarefas Administrativas & Operacionais:**")
            tarefas = item.get('tarefas_admin', [])
            if tarefas:
                for idx, t in enumerate(tarefas):
                    st.checkbox(t, key=f"t_{item.get('id', idx)}_{idx}")
            else:
                st.write("Nenhuma tarefa acessória associada.")
