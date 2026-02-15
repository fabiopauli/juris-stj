"""Data models for STJ acordao records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Acordao:
    id: str
    numero_documento: str | None
    numero_processo: str
    numero_registro: str
    sigla_classe: str
    descricao_classe: str
    classe_padronizada: str | None
    orgao_julgador: str
    ministro_relator: str
    data_publicacao: str
    ementa: str
    tipo_decisao: str
    data_decisao: str
    decisao: str
    jurisprudencia_citada: str | None = None
    notas: str | None = None
    informacoes_complementares: str | None = None
    termos_auxiliares: str | None = None
    tese_juridica: str | None = None
    tema: str | None = None
    referencias_legislativas: str = ""
    acordaos_similares: str = ""

    @classmethod
    def from_json(cls, data: dict) -> Acordao:
        refs = data.get("referenciasLegislativas")
        if isinstance(refs, list):
            refs = json.dumps(refs, ensure_ascii=False) if refs else ""
        similares = data.get("acordaosSimilares")
        if isinstance(similares, list):
            similares = json.dumps(similares, ensure_ascii=False) if similares else ""
        return cls(
            id=str(data["id"]),
            numero_documento=data.get("numeroDocumento"),
            numero_processo=data.get("numeroProcesso", ""),
            numero_registro=data.get("numeroRegistro", ""),
            sigla_classe=data.get("siglaClasse", ""),
            descricao_classe=data.get("descricaoClasse", ""),
            classe_padronizada=data.get("classePadronizada"),
            orgao_julgador=data.get("nomeOrgaoJulgador", ""),
            ministro_relator=data.get("ministroRelator", ""),
            data_publicacao=data.get("dataPublicacao", ""),
            ementa=data.get("ementa", ""),
            tipo_decisao=data.get("tipoDeDecisao", ""),
            data_decisao=data.get("dataDecisao", ""),
            decisao=data.get("decisao", ""),
            jurisprudencia_citada=data.get("jurisprudenciaCitada"),
            notas=data.get("notas"),
            informacoes_complementares=data.get("informacoesComplementares"),
            termos_auxiliares=data.get("termosAuxiliares"),
            tese_juridica=data.get("teseJuridica"),
            tema=data.get("tema"),
            referencias_legislativas=refs or "",
            acordaos_similares=similares or "",
        )
