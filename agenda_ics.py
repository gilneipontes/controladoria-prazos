"""Gera um arquivo de agenda (.ics) com os prazos, para importar no Google Calendar,
Outlook ou iPhone. Cada prazo vira um evento de dia inteiro na data fatal, com um
lembrete no dia anterior.

Função pura: não usa Streamlit nem banco. Recebe o DataFrame pronto.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

_LIMITE_LINHA = 75  # RFC 5545: linhas longas devem ser quebradas


def _texto(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor)


def _escapar(valor) -> str:
    """Escapa caracteres que têm significado especial no formato iCalendar."""
    t = _texto(valor)
    return (
        t.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _quebrar_linha(linha: str) -> list[str]:
    """Quebra linhas com mais de 75 bytes. Continuações começam com espaço."""
    partes = []
    atual = ""
    bytes_atual = 0
    limite = _LIMITE_LINHA
    for caractere in linha:
        tamanho = len(caractere.encode("utf-8"))
        if bytes_atual + tamanho > limite:
            partes.append(atual)
            atual = " " + caractere  # continuação começa com espaço (RFC 5545)
            bytes_atual = 1 + tamanho
            limite = _LIMITE_LINHA
        else:
            atual += caractere
            bytes_atual += tamanho
    partes.append(atual)
    return partes


def _linha(conteudo: str) -> list[str]:
    return _quebrar_linha(conteudo)


def gerar_ics(df: pd.DataFrame, agora: dt.datetime | None = None,
              nome_calendario: str = "Prazos") -> bytes:
    """Gera o conteúdo do arquivo .ics para as linhas do DataFrame de prazos.

    Espera as colunas: id, data_fatal, titulo, cliente, processo, responsavel,
    descricao. Linhas sem data_fatal são ignoradas.
    """
    carimbo = (agora or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%dT%H%M%SZ")

    saida = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Controladoria Juridica//Prazos//PT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    saida += _linha(f"X-WR-CALNAME:{_escapar(nome_calendario)}")

    if df is not None and not df.empty:
        for _, p in df.iterrows():
            if pd.isna(p.get("data_fatal")):
                continue

            data = pd.Timestamp(p["data_fatal"]).date()
            inicio = data.strftime("%Y%m%d")
            fim = (data + dt.timedelta(days=1)).strftime("%Y%m%d")

            titulo = _texto(p.get("titulo")) or "Prazo"
            cliente = _texto(p.get("cliente"))
            resumo = f"PRAZO: {titulo}" + (f" - {cliente}" if cliente else "")

            descricao = "\n".join([
                f"Processo: {_texto(p.get('processo')) or '-'}",
                f"Responsável: {_texto(p.get('responsavel')) or '-'}",
                f"Prioridade: {_texto(p.get('prioridade')) or '-'}",
                f"Observações: {_texto(p.get('descricao')) or '-'}",
            ])

            saida.append("BEGIN:VEVENT")
            saida += _linha(f"UID:prazo-{_texto(p.get('id'))}@controladoria-prazos")
            saida.append(f"DTSTAMP:{carimbo}")
            saida.append(f"DTSTART;VALUE=DATE:{inicio}")
            saida.append(f"DTEND;VALUE=DATE:{fim}")
            saida += _linha(f"SUMMARY:{_escapar(resumo)}")
            saida += _linha(f"DESCRIPTION:{_escapar(descricao)}")
            saida.append("BEGIN:VALARM")
            saida.append("TRIGGER:-P1D")
            saida.append("ACTION:DISPLAY")
            saida += _linha("DESCRIPTION:Prazo vence amanhã")
            saida.append("END:VALARM")
            saida.append("END:VEVENT")

    saida.append("END:VCALENDAR")
    return ("\r\n".join(saida) + "\r\n").encode("utf-8")
