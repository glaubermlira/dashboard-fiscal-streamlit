import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(
    page_title="Dashboard Fiscal • Faturamento e Compliance",
    layout="wide"
)

st.title("📊 Dashboard Fiscal Interativo — Análise de Faturamento")
st.write("Modelo base para análise fiscal, financeira e operacional")

# ==============================
# ARQUIVO DEFAULT + UPLOAD OPCIONAL
# ==============================

DEFAULT_FILE = "relatorio_nfe_default.xlsx"

st.subheader("📂 Fonte de Dados")

file = st.file_uploader(
    "Envie o relatório fiscal (ou deixe em branco para usar o arquivo padrão)",
    type=["xlsx", "csv"]
)

def load_dataframe(source):
    try:
        if isinstance(source, str):
            return pd.read_excel(source)

        name = source.name.lower()

        if name.endswith(".xlsx"):
            return pd.read_excel(source)
        return pd.read_csv(source)

    except Exception as e:
        st.error("❌ Erro ao carregar os dados.")
        st.exception(e)
        st.stop()


# 1) PRIORIDADE: arquivo enviado
if file is not None:
    st.success(f"Arquivo carregado: {file.name}")
    df = load_dataframe(file)

# 2) SENÃO: usa arquivo padrão do repositório
else:
    st.warning("Nenhum arquivo enviado — usando o arquivo padrão da pasta")

    if not os.path.exists(DEFAULT_FILE):
            st.error(f"❌ Arquivo padrão não encontrado: {DEFAULT_FILE}")
            st.stop()

    df = load_dataframe(DEFAULT_FILE)


# ==============================
# NORMALIZAÇÃO DE COLUNAS
# ==============================

df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]

MAP = {
    "data": ["data", "data_emissao", "dt_emissao"],
    "valor": ["total", "valor_total", "valor_nf"],
    "cliente": ["cliente", "razao_social", "razão_social/nome"],
    "produto": ["produto", "descricao_produto", "item", "servico"],
    "cfop": ["cfop"],
    "cst": ["cst"],
}

def find_col(opts):
    for c in opts:
        if c in df.columns:
            return c
    return None

col = {k: find_col(v) for k, v in MAP.items()}

if col["data"]:
    df[col["data"]] = pd.to_datetime(df[col["data"]], errors="coerce")
    df = df.dropna(subset=[col["data"]])

# ==============================
# MAPEAMENTO FLEXÍVEL
# ==============================

MAP = {
    "data": ["data", "data_emissao", "dt_emissao"],
    "valor": ["total", "valor_total", "valor_nf"],
    "cliente": ["cliente", "razao_social", "razão_social/nome"],
    "produto": ["produto", "descricao_produto", "item", "servico"],
    "cfop": ["cfop"],
    "cst": ["cst"],
}

def find_col(possibilities):
    for p in possibilities:
        if p in df.columns:
            return p
    return None

col = {k: find_col(v) for k, v in MAP.items()}

# ==============================
# VALIDA CAMPOS OBRIGATÓRIOS
# ==============================

required_cols = ["valor", "cliente"]

missing = [c for c in required_cols if col[c] is None]

if missing:
    st.error(f"❌ O arquivo não contém as colunas necessárias: {missing}")
    st.stop()

# Garante que valor é numérico
df[col["valor"]] = pd.to_numeric(df[col["valor"]], errors="coerce").fillna(0)

# Converte data se existir
if col["data"]:
    df[col["data"]] = pd.to_datetime(df[col["data"]], errors="coerce")

# ==============================
# KPIs PRINCIPAIS
# ==============================

faturamento_total = df[col["valor"]].sum()
qtd_notas = len(df)
qtd_clientes = df[col["cliente"]].nunique()

col1, col2, col3 = st.columns(3)

col1.metric("💰 Faturamento Total", f"R$ {faturamento_total:,.2f}")
col2.metric("🧾 Total de Notas", qtd_notas)
col3.metric("👥 Clientes Únicos", qtd_clientes)

st.divider()

# ==============================
# FATURAMENTO MENSAL
# ==============================

if col["data"]:
    mensal = (
        df.set_index(col["data"])
        .resample("M")[col["valor"]]
        .sum()
    )

    st.subheader("📈 Evolução Mensal do Faturamento")
    st.line_chart(mensal)

st.divider()

# ==============================
# CURVA ABC — CLIENTES
# ==============================

st.subheader("🏆 Curva ABC — Clientes")

clientes = (
    df.groupby(col["cliente"])[col["valor"]]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)

clientes["%_participacao"] = clientes[col["valor"]] / clientes[col["valor"]].sum()
clientes["%_acumulado"] = clientes["%_participacao"].cumsum()

def classifica_abc(x):
    if x <= 0.8: return "A"
    if x <= 0.95: return "B"
    return "C"

clientes["classe_abc"] = clientes["%_acumulado"].apply(classifica_abc)

st.write("Distribuição de Receita por Cliente")
st.bar_chart(clientes.set_index(col["cliente"])[col["valor"]])

st.write("Tabela ABC — Clientes")
st.dataframe(clientes)

# ==============================
# CURVA ABC — PRODUTOS
# ==============================

if col["produto"]:
    st.subheader("📦 Curva ABC — Produtos / Serviços")

    produtos = (
        df.groupby(col["produto"])[col["valor"]]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )

    produtos["%_participacao"] = produtos[col["valor"]] / produtos[col["valor"]].sum()
    produtos["%_acumulado"] = produtos["%_participacao"].cumsum()
    produtos["classe_abc"] = produtos["%_acumulado"].apply(classifica_abc)

    st.bar_chart(produtos.set_index(col["produto"])[col["valor"]])
    st.dataframe(produtos)

st.divider()

# ==============================
# ANÁLISE DE CONCENTRAÇÃO DE RISCO FISCAL
# ==============================

st.subheader("⚠️ Análise de Concentração de Risco Fiscal")

top5_clientes = clientes.head(5)
concentracao = top5_clientes[col["valor"]].sum() / faturamento_total

st.write(f"📌 **Top 5 clientes representam {concentracao:.2%} do faturamento**")

if concentracao > 0.60:
    st.error("🚨 Alto risco de dependência comercial")
elif concentracao > 0.40:
    st.warning("⚠️ Nível moderado de concentração — atenção")
else:
    st.success("🟢 Risco baixo — carteira diversificada")

st.write("Top 5 clientes (risco monitorado)")
st.table(top5_clientes)

# CFOP
if col["cfop"]:
    st.subheader("📑 Concentração Fiscal por CFOP")
    cfop = (
        df.groupby(col["cfop"])[col["valor"]]
        .sum()
        .sort_values(ascending=False)
    )
    st.bar_chart(cfop)

# CST
if col["cst"]:
    st.subheader("🧾 Exposição Tributária por CST")
    cst = (
        df.groupby(col["cst"])[col["valor"]]
        .sum()
        .sort_values(ascending=False)
    )
    st.bar_chart(cst)

st.divider()

# ==============================
# 🔮 PROJEÇÕES E CENÁRIOS
# ==============================

if col["data"]:

    st.subheader("🔮 Projeções e Cenários de Faturamento")

    mensal = (
        df.set_index(col["data"])
        .resample("M")[col["valor"]]
        .sum()
    ).dropna()

    st.write("Histórico consolidado (base da projeção)")
    st.line_chart(mensal)

    mensal_pct = mensal.pct_change().dropna()

    if len(mensal_pct) == 0:
        st.info("⚠️ Não há dados suficientes para projeção.")
    else:
        crescimento_medio = mensal_pct.mean()
        volatilidade = mensal_pct.std()

        st.write(f"📌 Crescimento médio histórico: **{crescimento_medio:.2%}**")
        st.write(f"📊 Volatilidade: **{volatilidade:.2%}**")

        meses_proj = st.slider("Período de projeção (meses)", 3, 24, 12)

        ultimo_valor = mensal.iloc[-1]

        cenarios = {
            "Conservador": crescimento_medio - (volatilidade * 0.75),
            "Base": crescimento_medio,
            "Otimista": crescimento_medio + (volatilidade * 0.75)
        }

        projecoes = {}

        for nome, taxa in cenarios.items():
            valores = [ultimo_valor]
            for _ in range(meses_proj):
                valores.append(valores[-1] * (1 + taxa))
            projecoes[nome] = valores[1:]

        index_future = pd.date_range(
            start=mensal.index[-1] + pd.offsets.MonthBegin(),
            periods=meses_proj,
            freq="MS"
        )

        df_proj = pd.DataFrame(projecoes, index=index_future)

        st.write("📈 Projeção de Cenários")
        st.line_chart(df_proj)

        st.write("📊 Tabela de Projeções")
        st.dataframe(df_proj.style.format("R$ {:.2f}"))

        st.subheader("🧮 Simulador de Cenário Planejado")

        taxa_planejada = st.number_input(
            "Informe a taxa de crescimento desejada (%)",
            value=float(crescimento_medio * 100),
            step=0.5
        ) / 100

        plano = [ultimo_valor]
        for _ in range(meses_proj):
            plano.append(plano[-1] * (1 + taxa_planejada))

        df_proj["Planejado"] = plano[1:]

        st.write("📌 Comparativo Estratégico")
        st.line_chart(df_proj[["Conservador", "Base", "Otimista", "Planejado"]])

st.info("🔍 Este dashboard pode ser usado como modelo base para futuras análises fiscais.")
