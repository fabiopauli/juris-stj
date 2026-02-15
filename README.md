# STJ Search

Ferramenta de linha de comando para baixar, indexar e pesquisar espelhos de acórdãos do Superior Tribunal de Justiça (STJ), a partir do [Portal de Dados Abertos do STJ](https://dadosabertos.web.stj.jus.br/).

## O que faz

O STJ disponibiliza os espelhos de acórdãos de todos os órgãos julgadores em formato aberto (JSON). Cada espelho contém ementa, decisão, referências legislativas, jurisprudência citada, tese jurídica e demais metadados estruturados.

Esta ferramenta:

1. **Baixa** os dados de todos os 10 órgãos julgadores via API CKAN
2. **Indexa** em um banco SQLite local com busca full-text (FTS5)
3. **Pesquisa** com ranking de relevância (BM25), filtros e estatísticas

São aproximadamente **675 mil acórdãos** indexados localmente (~2.8 GB), cobrindo todo o histórico disponível no portal.

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gerenciador de pacotes)

## Instalação

```bash
git clone https://github.com/fabiopauli/juris-stj.git ai-stj
cd ai-stj
uv sync
```

As dependências (httpx, click, rich) são instaladas automaticamente.

## Uso

### Sincronizar dados

Baixa e indexa os espelhos de acórdãos. Na primeira execução, faz o download completo de todos os datasets. Nas execuções seguintes, baixa apenas os recursos novos (sincronização incremental).

```bash
# Sincronizar todos os 10 datasets
stj sync

# Sincronizar apenas um dataset específico
stj sync -d espelhos-de-acordaos-terceira-turma

# Forçar re-download de tudo
stj sync --force
```

**Datasets disponíveis:**

| Dataset | Órgão Julgador |
|---------|----------------|
| `espelhos-de-acordaos-corte-especial` | Corte Especial |
| `espelhos-de-acordaos-primeira-secao` | Primeira Seção |
| `espelhos-de-acordaos-segunda-secao` | Segunda Seção |
| `espelhos-de-acordaos-terceira-secao` | Terceira Seção |
| `espelhos-de-acordaos-primeira-turma` | Primeira Turma |
| `espelhos-de-acordaos-segunda-turma` | Segunda Turma |
| `espelhos-de-acordaos-terceira-turma` | Terceira Turma |
| `espelhos-de-acordaos-quarta-turma` | Quarta Turma |
| `espelhos-de-acordaos-quinta-turma` | Quinta Turma |
| `espelhos-de-acordaos-sexta-turma` | Sexta Turma |

### Pesquisar

Busca full-text nos campos ementa, decisão, informações complementares, termos auxiliares, notas e tese jurídica. Resultados ordenados por relevância (BM25).

```bash
# Busca simples
stj busca "dano moral"

# Busca com operadores FTS5
stj busca "dano AND moral AND coletivo"
stj busca "dano OR lucro"
stj busca '"prescricao intercorrente"'   # frase exata
stj busca "consumi*"                      # prefixo

# Filtrar por ministro relator
stj busca "dano moral" -m "NANCY ANDRIGHI"

# Filtrar por classe processual
stj busca "dano moral" -c REsp

# Filtrar por data de decisão (a partir de)
stj busca "dano moral" --desde 20230101

# Combinar filtros
stj busca "dano moral" -c REsp -m "RAUL" --desde 20240101

# Limitar quantidade de resultados (padrão: 20)
stj busca "dano moral" -n 50
```

### Estatísticas de busca

Exibe estatísticas agregadas dos resultados em vez de listar os acórdãos individualmente. Mostra distribuição por órgão julgador, classe processual, ministro relator e ano de julgamento.

```bash
# Estatísticas gerais da busca
stj busca "dano moral" --stats

# Estatísticas com filtros
stj busca "juros mora dano moral" --stats -c REsp --desde 20230101
```

Exemplo de saída:

```
╭──────────────── Stats: juros mora dano moral ────────────────╮
│ 809 matching records                                         │
╰──────────────────────────────────────────────────────────────╯
        By Orgao Julgador
┏━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━┓
┃ Orgao Julgador ┃ Count ┃    % ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━┩
│ QUARTA TURMA   │   565 │ 69.8 │
│ SEGUNDA TURMA  │   135 │ 16.7 │
│ TERCEIRA TURMA │    63 │  7.8 │
│ ...            │       │      │
└────────────────┴───────┴──────┘
```

### Visualizar um acórdão

Exibe todos os campos de um acórdão específico pelo seu ID.

```bash
stj ver 000782366
```

Campos exibidos: dados do processo, ementa, decisão, informações complementares, tese jurídica, jurisprudência citada, notas, termos auxiliares, referências legislativas e tema.

### Informações do banco

Exibe estatísticas gerais do banco de dados e o status de sincronização de cada dataset.

```bash
stj info
```

## Sintaxe de busca

A pesquisa utiliza o [FTS5 do SQLite](https://www.sqlite.org/fts5.html), que suporta:

| Sintaxe | Descrição | Exemplo |
|---------|-----------|---------|
| `termo` | Busca simples | `stj busca "prescricao"` |
| `termo1 termo2` | AND implícito | `stj busca "dano moral"` |
| `termo1 AND termo2` | AND explícito | `stj busca "dano AND coletivo"` |
| `termo1 OR termo2` | OU | `stj busca "prescricao OR decadencia"` |
| `"frase exata"` | Frase exata | `stj busca '"dano moral coletivo"'` |
| `prefixo*` | Busca por prefixo | `stj busca "consumi*"` |
| `NOT termo` | Exclusão | `stj busca "dano NOT material"` |

A busca é **insensível a acentos** para consultas sem acento: pesquisar `acao` encontra tanto `acao` quanto `ação`. Consultas acentuadas exigem correspondência exata.

## Arquitetura

```
src/stj_search/
  __init__.py
  config.py       # URLs da API CKAN, nomes dos datasets, caminhos
  models.py       # Dataclass Acordao com factory from_json()
  db.py           # Schema SQLite, FTS5, upsert, busca, estatísticas
  client.py       # Chamadas à API CKAN, download de JSON e ZIP
  sync.py         # Orquestrador com barras de progresso (rich)
  cli.py          # Comandos CLI (click): sync, busca, ver, info
```

### Decisões técnicas

- **SQLite + FTS5**: banco embutido, sem dependências externas. A tabela FTS5 usa _external content_ com triggers, evitando duplicação de texto e reduzindo o tamanho do banco pela metade.
- **`unicode61 remove_diacritics 2`**: tokenizador que permite busca insensível a acentos quando a consulta não tem acentos.
- **`INSERT OR REPLACE` no `id`**: deduplicação natural entre arquivos mensais sobrepostos.
- **Tabela `sync_state`**: rastreia recursos já baixados por dataset, permitindo sincronização incremental.
- **Download de ZIP via streaming**: evita picos de memória em arquivos históricos grandes (100MB+).
- **Ranking BM25**: ordenação por relevância nativa do FTS5.
- **Retry com backoff**: tentativas automáticas em caso de erros transientes do servidor (522, timeouts).

## Campos dos espelhos

| Campo | Descrição |
|-------|-----------|
| `id` | Identificador único do acórdão |
| `numeroProcesso` | Número do processo no STJ |
| `numeroRegistro` | Número de registro no STJ |
| `siglaClasse` | Sigla da classe processual (REsp, HC, AgInt, etc.) |
| `descricaoClasse` | Nome completo da classe processual |
| `nomeOrgaoJulgador` | Órgão colegiado responsável pelo julgamento |
| `ministroRelator` | Ministro relator do acórdão |
| `ementa` | Resumo da decisão elaborado pelo relator |
| `tipoDeDecisao` | Tipo: acórdão ou decisão monocrática |
| `dataDecisao` | Data da sessão de julgamento (YYYYMMDD) |
| `decisao` | Resultado do julgamento com informações de votação |
| `jurisprudenciaCitada` | Decisões citadas como fundamentação |
| `notas` | Índice de assuntos e alterações |
| `informacoesComplementares` | Teses extraídas do inteiro teor |
| `termosAuxiliares` | Termos alternativos do Tesauro Jurídico do STJ |
| `teseJuridica` | Tese firmada em precedentes qualificados |
| `tema` | Número do tema repetitivo |
| `referenciasLegislativas` | Atos normativos referenciados |
| `acordaosSimilares` | Acórdãos similares do mesmo relator/órgão |
| `dataPublicacao` | Data e fonte de publicação |

Fonte: [Dicionário de dados do STJ](https://dadosabertos.web.stj.jus.br/)

## Fonte dos dados

Todos os dados são obtidos do [Portal de Dados Abertos do STJ](https://dadosabertos.web.stj.jus.br/), disponibilizados sob licença [Creative Commons Atribuição (CC-BY)](https://creativecommons.org/licenses/by/4.0/).

## Licença

MIT
