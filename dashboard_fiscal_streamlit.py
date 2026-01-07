import streamlit as st
import pandas as pd
import numpy as np
import os

# ==========================================
# CONFIGURAÇÃO DO APP
# ==========================================

st.set_page_config(
    page_title="Dashboard Fiscal — Inteligência de Faturamento",
    layout="wide"
)

st.title("📊 Dashboard Fiscal — Inteligência de Faturamento & Compliance")
st.write("Modelo analítico consolidado para gestão fiscal, financeira e comercial")

DEFAULT_FILE = "relatorio_nfe_default.xlsx"


# ==========================================
# FUNÇÃO DE CARREGAMENTO
# ==========================================

def load_dataframe(source):
    try:
        if isinstance(source, str):
            return pd.read_excel(source)

        name = source.name.lower()

        if name.endswith(".xlsx"):
            return pd.read_excel(source)
        return pd.read_csv(source)

    except Exception as e:
        st.error("Erro ao carregar dados")
        st.exception(e)
        st.stop()


# ==========================================
# UPLOAD + ARQUIVO PADRÃO
# ==========================================

st.subheader("📂 Fonte de Dados")

file = st.file_uploader(
    "Envie o relatório fiscal (Excel/CSV) — ou deixe vazio para usar o arquivo padrão",
    type=["xlsx", "csv"]
)

if file:
    st.success(f"Arquivo carregado: {file.name}")
    df = load_dataframe(file)

else:
    st.warning("Nenhum arquivo carregado — usando arquivo padrão")

    if not os.path.exists(DEFAULT_FILE):
        st.error("Arquivo padrão não encontrado no repositório.")
        st.stop()

    df = load_dataframe(DEFAULT_FILE)


# ==========================================
# NORMALIZAÇÃO DE COLUNAS
# ==========================================

df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]

MAP = {
    "data": ["data", "data_emissao", "dt_emissao"],
    "valor": ["valor", "valor_total", "total_nf", "valor_nf"],
    "cliente": ["cliente", "razao_social", "razaosocial", "nome_cliente"],
    "segmento": ["segmento", "categoria_cliente", "setor"],
    "produto": ["produto", "descricao_produto", "item", "servico"],
    "cfop": ["cfop"],
    "cst": ["cst"]
}

def find_col(options):
    for o in options:
        if o in df.columns:
            return o
    return None

col = {k: find_col(v) for k, v in MAP.items()}

if col["data"]:
    df[col["data"]] = pd.to_datetime(df[col["data"]], errors="coerce")
    df = df.dropna(subset=[col["data"]])


# ==========================================
# CAMPOS DERIVADOS
# ==========================================

df["ano"] = df[col["data"]].dt.year
df["mes"] = df[col["data"]].dt.to_period("M")
df["trimestre"] = df[col["data"]].dt.to_period("Q")
df["mes_num"] = df[col["data"]].dt.month

# KPI auxiliares
df["freq"] = 1


# ==========================================
# KPIs PRINCIPAIS
# ==========================================

st.header("📌 Indicadores-Chave de Desempenho (KPIs)")

faturamento_total = df[col["valor"]].sum()

mensal = (
    df.groupby("mes")[col["valor"]]
    .sum()
    .sort_index()
)

faturamento_mensal = mensal.iloc[-1] if len(mensal) else 0

clientes_ativos = df[col["cliente"]].nunique()

ticket_medio = faturamento_total / len(df) if len(df) > 0 else 0

top5 = (
    df.groupby(col["cliente"])[col["valor"]]
    .sum()
    .sort_values(ascending=False)
    .head(5)
)

concentracao_top5 = top5.sum() / faturamento_total if faturamento_total > 0 else 0


col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("💰 Faturamento Total", f"R$ {faturamento_total:,.2f}")
col2.metric("📆 Faturamento Mensal Atual", f"R$ {faturamento_mensal:,.2f}")
col3.metric("👥 Clientes Ativos", clientes_ativos)
col4.metric("💳 Ticket Médio", f"R$ {ticket_medio:,.2f}")
col5.metric("⚠️ Concentração Top 5", f"{concentracao_top5:.2%}")


st.divider()


# ==========================================
# 1️⃣ EVOLUÇÃO TEMPORAL DO FATURAMENTO
# ==========================================

st.subheader("📈 Evolução Temporal do Faturamento")

st.line_chart(mensal)


# ==========================================
# 2️⃣ COMPOSIÇÃO POR SEGMENTO
# ==========================================

if col["segmento"]:
    st.subheader("🏷️ Composição por Segmento de Mercado")

    seg = (
        df.groupby(col["segmento"])[col["valor"]]
        .sum()
        .sort_values(ascending=False)
    )

    st.bar_chart(seg)


# ==========================================
# 3️⃣ MATRIZ CLIENTE — VALOR vs FREQUÊNCIA
# ==========================================

st.subheader("🔎 Matriz Cliente: Valor x Frequência")

cliente_matrix = (
    df.groupby(col["cliente"])
    .agg(
        valor_total=(col["valor"], "sum"),
        frequencia=("freq", "sum")
    )
)

st.scatter_chart(cliente_matrix)


# ==========================================
# 4️⃣ TOP 10 CLIENTES
# ==========================================

st.subheader("🥇 Top 10 Clientes por Faturamento")

top10 = cliente_matrix.sort_values("valor_total", ascending=False).head(10)

st.bar_chart(top10["valor_total"])

st.dataframe(top10)


# ==========================================
# 5️⃣ SAZONALIDADE ANUAL
# ==========================================

st.subheader("📆 Sazonalidade Mensal do Faturamento")

sazonalidade = (
    df.groupby("mes_num")[col["valor"]]
    .sum()
    .reindex(range(1, 13), fill_value=0)
)

st.bar_chart(sazonalidade)


# ==========================================
# 6️⃣ HIERARQUIA DE CLIENTES (ABC)
# ==========================================

st.subheader("🏆 Hierarquia de Clientes — Curva ABC")

clientes = (
    df.groupby(col["cliente"])[col["valor"]]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)

clientes["%_participacao"] = clientes[col["valor"]] / clientes[col["valor"]].sum()
clientes["%_acumulado"] = clientes["%_participacao"].cumsum()

def classifica(x):
    if x <= 0.8: return "A"
    if x <= 0.95: return "B"
    return "C"

clientes["classe_abc"] = clientes["%_acumulado"].apply(classifica)

st.dataframe(clientes)


# ==========================================
# 7️⃣ EVOLUÇÃO TRIMESTRAL
# ==========================================

st.subheader("📊 Evolução Trimestral de Receita")

trimestre = (
    df.groupby("trimestre")[col["valor"]]
    .sum()
)

st.line_chart(trimestre)


# ==========================================
# 8️⃣ DISTRIBUIÇÃO DE TICKET MÉDIO
# ==========================================

st.subheader("📦 Distribuição de Ticket Médio por Cliente")

ticket = (
    df.groupby(col["cliente"])[col["valor"]]
    .mean()
)

st.bar_chart(ticket)


# ==========================================
# 9️⃣ SAZONALIDADE + RISCO DE CONCENTRAÇÃO
# ==========================================

st.subheader("⚠️ Indicadores de Sazonalidade e Risco")

sazonalidade_pct = sazonalidade / sazonalidade.sum()

st.write("📌 Sazonalidade (%) por mês")
st.dataframe(sazonalidade_pct.apply(lambda x: f"{x:.2%}"))


st.info("Modelo projetado para análise fiscal estratégica e tomada de decisão.")
