# Controladoria Jurídica

Sistema de controle de prazos, audiências e processos do escritório (Streamlit + Supabase).

## Funcionalidades
- Cadastro de processos (nº CNJ, cliente, parte adversária), sem números duplicados
- Cadastro de prazos com atalhos de peças e bloqueio de prazo repetido
- Situação por cores: vencido, hoje, até 3 dias, até 7 dias, futuro
- Dias úteis calculados com feriados nacionais automáticos, feriados do RS e recesso forense (20/12 a 20/01)
- Painel do prazo: dicas "o que deve ser feito", editar, concluir com anotações, arquivar e excluir
- Audiências: cadastro, agendadas/realizadas/canceladas
- Pauta do dia e da semana, com exportação para Excel (prazos e audiências)
- Dashboard com contadores
- Filtro por responsável
- Acesso protegido por senha

## Arquivos
| Arquivo | Para que serve |
|---|---|
| `app.py` | O sistema |
| `requirements.txt` | Bibliotecas que o Streamlit instala |
| `supabase_schema.sql` | Cria as 3 tabelas no Supabase |
| `.gitignore` | Impede que senhas sejam enviadas ao GitHub |

## Ajustes rápidos (topo do `app.py`)
- `RESPONSAVEIS`: nomes dos advogados
- `FERIADOS_LOCAIS`: feriados estaduais/municipais, formato (mês, dia)
- `FERIADOS_AVULSOS`: dias sem expediente no tribunal, formato "AAAA-MM-DD"

## Senhas e chaves
Ficam **somente** em Streamlit Cloud → Settings → Secrets:
```
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_KEY = "sb_secret_..."
APP_PASSWORD = "senha-do-escritorio"
```
