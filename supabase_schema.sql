-- =====================================================================
-- Controladoria Jurídica — estrutura do banco (Supabase / PostgreSQL)
-- Cole tudo no SQL Editor do Supabase e clique em "Run".
-- Pode rodar mais de uma vez sem problema.
-- =====================================================================

-- ---------- PROCESSOS ----------
create table if not exists public.processos (
    id               bigint generated always as identity primary key,
    created_at       timestamptz not null default now(),
    numero           text not null unique,
    cliente          text not null,
    parte_contraria  text,
    descricao        text,
    ativo            boolean not null default true
);

-- ---------- PRAZOS ----------
create table if not exists public.prazos (
    id            bigint generated always as identity primary key,
    created_at    timestamptz not null default now(),
    tipo          text not null,
    titulo        text not null,
    processo      text not null references public.processos (numero) on update cascade,
    cliente       text,
    responsavel   text not null,
    data_fatal    date not null,
    data_interna  date,
    prioridade    text not null default 'Normal',
    descricao     text,
    concluido     boolean not null default false,
    concluido_em  timestamptz,
    arquivado     boolean not null default false,
    constraint prazo_interno_antes_da_fatal
        check (data_interna is null or data_interna <= data_fatal)
);

-- ---------- AUDIÊNCIAS ----------
create table if not exists public.audiencias (
    id              bigint generated always as identity primary key,
    created_at      timestamptz not null default now(),
    processo        text not null references public.processos (numero) on update cascade,
    autor           text,
    reu             text,
    sala            text,
    data_audiencia  date not null,
    hora_inicio     time not null,
    hora_termino    time not null,
    formato         text not null default 'Presencial',
    tipo            text not null default 'Inicial',
    status          text not null default 'Agendada',
    observacoes     text,
    responsavel     text
);

create index if not exists prazos_data_fatal_idx on public.prazos (data_fatal);
create index if not exists audiencias_data_idx   on public.audiencias (data_audiencia);
create index if not exists prazos_processo_idx   on public.prazos (processo);

-- ---------- SEGURANÇA ----------
-- RLS ligado e SEM políticas: ninguém acessa pela chave pública (publishable/anon).
-- O app usa a chave SECRETA (sb_secret_...), que fica só nos Secrets do Streamlit.
alter table public.processos enable row level security;
alter table public.prazos     enable row level security;
alter table public.audiencias enable row level security;

revoke all on public.processos, public.prazos, public.audiencias from anon, authenticated;

-- Libera as tabelas para a API de dados usando a chave secreta
-- (necessário nos projetos novos do Supabase, que não expõem tabelas automaticamente).
grant select, insert, update, delete on public.processos, public.prazos, public.audiencias to service_role;
