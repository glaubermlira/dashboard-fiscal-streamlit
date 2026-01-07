import streamlit as st
import pandas as pd
import numpy as np
import os
import unicodedata

# -----------------------------------------
# Configuração da página
# -----------------------------------------
st.set_page_config(
    page_title="Dashboard Fiscal • Inteligência de Faturamento",
    layout="wide"
)

st.title("📊 Dashboard Fiscal • Análise e Intelligence")
st.write("Painel fiscal preparado para múltiplos layouts de planilhas.")

# -----------------------------------------
# Funções utilitárias
# -----------------------------------------

def normalizar(texto):
    """Remove acentuação e caracteres que atrapalham o matching."""
    if not isinstance(texto, str):
        return texto
    texto = unicodedata.normalize("NFD", texto)
    texto = ''.join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )
    texto = texto.lower().replace(" ", "").replace("_", "").replace("-", "")
    return texto

def localizar_coluna(possiveis, df):
    """
    Tenta localizar no DataFrame colunas parecidas
    com as palavras-chave informadas.
    """
    for alvo in possiveis:
        alvo_norm = normalizar(alvo)
        for col in df.columns:
            if normalizar(col) == alvo_norm:
                return col
    return None

def validar_campos(obrigatorios, col_map):
    faltando = [c for c in obrigatorios if col_map.get(c) is None]
    if faltando:
        st.error(f"⚠️ O arquivo não possui as colunas essenciais:")
        st.error(", ".join(faltando))
        st.write("📋 Colunas detectadas no arquivo:", df.columns.tolist())
        st.stop()

# -----------------------------------------
# Upload ou arquivo padrão
# -----------------------------------------
DEFAULT_FILE = "relatorio_nfe_default.xlsx"

file = st.file_uploader(
    "📥 Envie uma planilha (Excel/CSV) — ou deixe em branco para usar a padrão",
    type=["xlsx","csv"]
)

if file:
    st.success(f"Arquivo recebido: {file.name}")
    df = pd.read_excel(file) if file.name.lower().endswith(".xlsx") else pd.read_csv(file)
else:
    st.warning("Nenhum arquivo enviado. Usando arquivo padrão.")
    if not os.path.exists(DEFAULT_FILE):
        st.error(f"Arquivo padrão não encontrado: {DEFAULT_FILE}")
        st.stop()
    df = pd.read_excel(DEFAULT_FILE)

# -----------------------------------------
# DETECÇÃO AUTOMÁTICA DE COLUNAS
# -----------------------------------------

col = {
    "data": localizar_coluna(["data", "data_emissao", "emissao"], df),
    "cliente": localizar_coluna(["cliente", "razao_social", "nome_cliente"], df),
    "valor": localizar_coluna(["valor_total","valor_nf","total","valor"], df),
    "produto": localizar_coluna(["produto","descricao","item","servico"], df),
    "segmento": localizar_coluna(["segmento","categoria","setor"], df),
    "cfop": localizar_coluna(["cfop"], df),
    "cst": localizar_coluna(["cst","csosn"], df),
}

validar_campos(["data","cliente","valor"], col)

# -----------------------------------------
# NORMALIZAÇÃO DO DATAFRAME
# -----------------------------------------
df.columns = [c.strip() for c in df.columns]

df["Data"] = pd.to_datetime(df[col["data"]], errors="coerce")
df["Cliente"] = df[col["cliente"]]
df["ValorNF"] = pd.to_numeric(df[col["valor"]], errors="coerce").fillna(0)

optional_cols = {}
if col.get("produto"): optional_cols["Produto"] = col["produto"]
if col.get("segmento"): optional_cols["Segmento"] = col["segmento"]
if col.get("cfop"): optional_cols["CFOP"] = col["cfop"]
if col.get("cst"): optional_cols["CST"] = col["cst"]

for novo, antigo in optional_cols.items():
    df[novo] = df[antigo]

df = df.dropna(subset=["Data","Cliente"])

# -----------------------------------------
# HARD ANDROID EXPLAINER
# -----------------------------------------
with st.expander("📋 Mapeamento de Colunas"):
    st.write("Colunas originais:", list(df.columns))
    st.write("Mapeadas como:", col)

# -----------------------------------------
# Campos derivados
# -----------------------------------------
df["ano"] = df["Data"].dt.year
df["mes"] = df["Data"].dt.to_period("M")
df["trimestre"] = df["Data"].dt.to_period("Q")
df["mes_num"] = df["Data"].dt.month
df["freq"] = 1

# -----------------------------------------
# KPIs
# -----------------------------------------
st.header("📌 Indicadores de Desempenho")

faturamento_total = df["ValorNF"].sum()
mensal = df.groupby("mes")["ValorNF"].sum().sort_index()
faturamento_mensal = mensal.iloc[-1] if len(mensal) else 0
clientes_ativos = df["Cliente"].nunique()
ticket_medio = faturamento_total / len(df) if len(df) else 0
top5 = df.groupby("Cliente")["ValorNF"].sum().sort_values(ascending=False).head(5)
concentracao_top5 = top5.sum() / faturamento_total if faturamento_total > 0 else 0

col1,col2,col3,col4,col5 = st.columns(5)
col1.metric("💰 Faturamento Total", f"R$ {faturamento_total:,.2f}")
col2.metric("🗓️ Faturamento Mensal Atual", f"R$ {faturamento_mensal:,.2f}")
col3.metric("👥 Clientes Ativos", clientes_ativos)
col4.metric("💳 Ticket Médio", f"R$ {ticket_medio:,.2f}")
col5.metric("⚠️ Concentração Top 5", f"{concentracao_top5:.2%}")
st.divider()

# -----------------------------------------
# Análises Pedidas
# -----------------------------------------
st.subheader("📈 Evolução Temporal do Faturamento")
st.line_chart(mensal)

st.subheader("📊 Top 10 Clientes por Faturamento")
top10 = df.groupby("Cliente")["ValorNF"].sum().sort_values(ascending=False).head(10)
st.bar_chart(top10)

st.subheader("🔎 Matriz Cliente: Valor x Frequência")
matriz = df.groupby("Cliente").agg(valor_total=("ValorNF","sum"), freq=("freq","sum"))
st.scatter_chart(matriz)

st.subheader("📆 Sazonalidade — Receita Mensal")
sazonalidade = df.groupby("mes_num")["ValorNF"].sum().reindex(range(1,13), fill_value=0)
st.bar_chart(sazonalidade)

st.subheader("📊 Evolução Trimestral de Receita")
trimestral = df.groupby("trimestre")["ValorNF"].sum()
st.line_chart(trimestral)

st.subheader("📦 Distribuição de Ticket Médio por Cliente")
ticket = df.groupby("Cliente")["ValorNF"].mean()
st.bar_chart(ticket)

st.subheader("🏆 Curva ABC de Clientes")
abc = df.groupby("Cliente")["ValorNF"].sum().sort_values(ascending=False).reset_index()
abc["%"] = abc["ValorNF"] / abc["ValorNF"].sum()
abc["%_acum"] = abc["%"].cumsum()
abc["Classe"] = abc["%_acum"].apply(lambda x: "A" if x<=0.8 else ("B" if x<=0.95 else "C"))
st.dataframe(abc)

st.info("📊 Dashboard pronto para uso em produção.")
