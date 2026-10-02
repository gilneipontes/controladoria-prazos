# ============================================
# FUNÇÃO DE BACKUP - COPIE E COLE NO app.py
# ============================================
# Adicione esta função ANTES da função main()
# (antes da linha 3764)

@st.cache_data(ttl=300)
def carregar_backup_data():
    """Busca dados de todas as 3 tabelas para backup"""
    try:
        sb = supabase()

        # Busca os dados das 3 tabelas
        processos = sb.table(TABELA_PROCESSOS).select("*").execute().data or []
        prazos = sb.table(TABELA_PRAZOS).select("*").execute().data or []
        audiencias = sb.table(TABELA_AUDIENCIAS).select("*").execute().data or []

        return processos, prazos, audiencias
    except Exception as e:
        st.error(f"Erro ao carregar dados para backup: {e}")
        return [], [], []


def fazer_backup_completo():
    """Cria arquivo CSV combinado com dados de todas as tabelas"""
    try:
        processos, prazos, audiencias = carregar_backup_data()

        # Converte para DataFrames
        df_processos = pd.DataFrame(processos) if processos else pd.DataFrame()
        df_prazos = pd.DataFrame(prazos) if prazos else pd.DataFrame()
        df_audiencias = pd.DataFrame(audiencias) if audiencias else pd.DataFrame()

        # Adiciona uma coluna de tabela para identificar a origem dos dados
        if not df_processos.empty:
            df_processos.insert(0, '_tabela', 'PROCESSOS')
        if not df_prazos.empty:
            df_prazos.insert(0, '_tabela', 'PRAZOS')
        if not df_audiencias.empty:
            df_audiencias.insert(0, '_tabela', 'AUDIENCIAS')

        # Combina todos os dados em um único DataFrame
        # (as linhas serão sobre tabelas diferentes, então podem ter colunas diferentes)
        dfs = [df_processos, df_prazos, df_audiencias]
        dfs = [df for df in dfs if not df.empty]

        if dfs:
            # Usa concat com full outer join
            df_backup = pd.concat(dfs, axis=0, ignore_index=True, sort=False)
        else:
            df_backup = pd.DataFrame()

        # Converte para CSV
        if not df_backup.empty:
            csv_data = df_backup.to_csv(index=False, sep=';', encoding='utf-8-sig')
            return csv_data
        else:
            return "Nenhum dado para fazer backup"

    except Exception as e:
        st.error(f"Erro ao criar backup: {e}")
        return None


def fazer_backup_separado():
    """Cria 3 CSVs separados (um por tabela)"""
    try:
        processos, prazos, audiencias = carregar_backup_data()

        # Converte para DataFrames
        df_processos = pd.DataFrame(processos) if processos else pd.DataFrame()
        df_prazos = pd.DataFrame(prazos) if prazos else pd.DataFrame()
        df_audiencias = pd.DataFrame(audiencias) if audiencias else pd.DataFrame()

        # Cria CSVs separados
        csv_processos = df_processos.to_csv(index=False, sep=';', encoding='utf-8-sig') if not df_processos.empty else ""
        csv_prazos = df_prazos.to_csv(index=False, sep=';', encoding='utf-8-sig') if not df_prazos.empty else ""
        csv_audiencias = df_audiencias.to_csv(index=False, sep=';', encoding='utf-8-sig') if not df_audiencias.empty else ""

        # Combina os 3 em um único arquivo com separadores visuais
        backup_completo = f"""=== BACKUP COMPLETO - {dt.datetime.now(TZ).strftime('%d/%m/%Y %H:%M')} ===

--- TABELA: PROCESSOS ({len(df_processos)} registros) ---
{csv_processos}

--- TABELA: PRAZOS ({len(df_prazos)} registros) ---
{csv_prazos}

--- TABELA: AUDIÊNCIAS ({len(df_audiencias)} registros) ---
{csv_audiencias}
"""
        return backup_completo

    except Exception as e:
        st.error(f"Erro ao criar backup: {e}")
        return None


# ============================================
# ADICIONE ESTE CÓDIGO NA SIDEBAR (depois do botão "🔄 Recarregar Dados")
# Procure pela linha 3833 no app.py
# ============================================

# NO LOCAL INDICADO, ADICIONE:
"""
        # ===== BACKUP =====
        st.caption("💾 BACKUP")

        col_backup1, col_backup2 = st.columns(2)

        with col_backup1:
            if st.button("📥 Backup Combinado", use_container_width=True):
                backup_data = fazer_backup_completo()
                if backup_data:
                    timestamp = dt.datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
                    nome_arquivo = f"backup_completo_{timestamp}.csv"
                    st.download_button(
                        label="⬇️ Baixar CSV",
                        data=backup_data,
                        file_name=nome_arquivo,
                        mime="text/csv",
                        use_container_width=True,
                    )

        with col_backup2:
            if st.button("📋 Backup Detalhado", use_container_width=True):
                backup_data = fazer_backup_separado()
                if backup_data:
                    timestamp = dt.datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
                    nome_arquivo = f"backup_detalhado_{timestamp}.txt"
                    st.download_button(
                        label="⬇️ Baixar TXT",
                        data=backup_data,
                        file_name=nome_arquivo,
                        mime="text/plain",
                        use_container_width=True,
                    )

        st.divider()
"""

# ============================================
# INSTRUÇÕES DE INSTALAÇÃO:
# ============================================
#
# 1. Copie as funções:
#    - carregar_backup_data()
#    - fazer_backup_completo()
#    - fazer_backup_separado()
#
# 2. Cole ANTES da função main() (antes da linha 3764)
#
# 3. Na sidebar, procure por este trecho (linha ~3833):
#    if st.button("🔄 Recarregar Dados", use_container_width=True):
#
# 4. DEPOIS desse trecho (depois do st.divider() que vem depois),
#    adicione o código da seção "ADICIONE ESTE CÓDIGO NA SIDEBAR"
#
# 5. Faça commit no GitHub
#
# 6. Streamlit Cloud atualiza em 1-2 minutos
#
# 7. Pronto! O botão de backup estará disponível!
#
# ============================================
