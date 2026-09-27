import streamlit as st
from supabase import create_client
import hmac

st.set_page_config(page_title="Teste", page_icon="🧪")

# Login
if not st.session_state.get("autenticado"):
    st.title("🧪 Teste Conexão Supabase")
    with st.form("login"):
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            senha_correta = st.secrets.get("APP_PASSWORD", "Gcp401718@@")
            if hmac.compare_digest(senha.encode(), senha_correta.encode()):
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    st.stop()

st.title("🧪 Teste Conexão Supabase")

st.write("**Credenciais:**")
st.code(f"""
URL: {st.secrets.get('SUPABASE_URL')}
KEY: {st.secrets.get('SUPABASE_KEY')[:30]}...
""")

st.divider()

try:
    st.write("🔄 Tentando conectar ao Supabase...")
    client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    st.success("✅ Cliente criado!")

    st.write("🔄 Tentando acessar tabela 'prazos'...")
    resp = client.table("prazos").select("*").limit(1).execute()
    st.success(f"✅ Sucesso! {len(resp.data)} linha(s) retornada(s)")
    st.write(resp.data)

except Exception as e:
    st.error(f"❌ Erro: {type(e).__name__}")
    st.error(str(e))
    import traceback
    st.code(traceback.format_exc())
