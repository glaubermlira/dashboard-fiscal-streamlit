import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ==============================
# FUNÇÕES DE SUPORTE
# ==============================

def normalizar_colunas(df):
    mapping = {}

    cols_norm = {c.lower().strip(): c for c in df.columns}

    def pick(options, default=None):
        for o in options:
            if o.lower() in cols_norm:
                return cols_norm[o.lower()]
        return default

    mapping["data"] = pick(["data", "emissão", "data emissão"])
    mapping["cliente"] = pick(["razão social/nome", "cliente", "nome", "razao social"])
    mapping["valor"] = pick(["total", "valor total", "venda", "valor"])
    mapping["cfop"] = pick(["cfop"])
    mapping["produto"] = pick(["produto", "item", "descrição produto"])
    mapping["documento"] = pick(["nº", "numero", "nf", "nota"])

    return mapping


def preparar_dataframe(df, col):
    if col["data"]:
        df["__data__"] = pd.to_datetime(df[col["data"]], errors="coerce", dayfirst=True)
        df["ano"] = df["__data__"].dt.year
        df["mes"] = df["__data__"].dt.month
    else:
        df["ano"] = None
        df["mes"] = None

    df["valor_num"] = pd.to_numeric(df[col["valor"]], errors="coerce").fillna(0)

    df["cliente_norm"] = (
        df[col["cliente"]].astype(str).str.strip().str.upper()
        if col["cliente"] else "DESCONHECIDO"
    )

    return df


# ==============================
# EXPORTAÇÃO EXCEL
# ==============================

def exportar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="dados")
    return output.getvalue()


# ==============================
# EXPORTAÇÃO PDF (ReportLab)
# ==============================

def exportar_pdf(df, titulo="Relatório"):
    output = BytesIO()
    doc = SimpleDocTemplate(output)
    styles = getSampleStyleSheet()

    story = []
    story.append(Paragraph(titulo, styles["Title"]))
    story.append(Spacer(1, 10))

    tabela = [list(df.columns)] + df.astype(str).values.tolist()

    t = Table(tabela)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0),( -1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1),
         [colors.whitesmoke, colors.lightyellow])
    ]))

    story.append(t)
    doc.build(story)

    return output.getvalue()


# ==============================
# CURVA ABC
# ==============================

def curva_abc(df, chave, valor_col="valor_num"):
    agrupado = df.groupby(chave)[valor_col].sum().reset_index()
    agrupado = agrupado.sort_values(valor_col, ascending=False)
    total = agrupado[valor_col].sum()

    agrupado["percent"] = agrupado[valor_col] / total
    agrupado["acumulado"] = agrupado["percent"].cumsum()

    def classe(v):
        if v <= 0.8: return "A"
        if v <= 0.95: return "B"
        return "C"

    agrupado["classe"] = agrupado["acumulado"].apply(classe)
    return agrupado


# ==============================
# APP
# ==============================

st.set_page_config("Dashboard Fiscal", layout="wide")
st.title("📊 Dashboard Fiscal & Faturamento")

st.sidebar.header("Upload de Arquivo")
file = st.sidebar.file_uploader("Selecione o arquivo", type=["xlsx", "csv"])

if not file:
    st.info("Envie um arquivo para iniciar a análise.")
    st.stop()

df = pd.read_excel(file) if file.name.endswith("xlsx") else pd.read_csv(file)

col = normalizar_colunas(df)

essenciais = ["data", "cliente", "valor"]
faltando = [c for c in essenciais if not col[c]]

if faltando:
    st.error(f"⚠ O arquivo não possui as colunas essenciais: {', '.join(faltando)}")
    st.stop()

df = preparar_dataframe(df, col)

# ==============================
# FILTROS
# ==============================

anos = sorted(df["ano"].dropna().unique())
ano_sel = st.sidebar.selectbox("Ano", anos)

meses = sorted(df[df["ano"] == ano_sel]["mes"].dropna().unique())
mes_sel = st.sidebar.multiselect("Meses", meses, default=meses)

comparar = st.sidebar.checkbox("Comparar com outro ano")

ano_comp = None
if comparar and len(anos) > 1:
    ano_comp = st.sidebar.selectbox("Ano comparação", [a for a in anos if a != ano_sel])


df_filtrado = df[(df["ano"] == ano_sel) & (df["mes"].isin(mes_sel))]


# ==============================
# KPIs
# ==============================

faturamento = df_filtrado["valor_num"].sum()
clientes_ativos = df_filtrado["cliente_norm"].nunique()
ticket_medio = faturamento / max(clientes_ativos,1)

top5 = (
    df_filtrado.groupby("cliente_norm")["valor_num"].sum()
    .sort_values(ascending=False)
)
conc_top5 = top5.head(5).sum() / faturamento if faturamento else 0

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

kpi1.metric("💰 Faturamento", f"R$ {faturamento:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
kpi2.metric("👥 Clientes Ativos", clientes_ativos)
kpi3.metric("🏷 Ticket Médio", f"R$ {ticket_medio:,.2f}")
kpi4.metric("🏦 Concentração Top 5", f"{conc_top5*100:.1f}%")
kpi5.metric("📆 Meses Selecionados", len(mes_sel))


# ==============================
# EVOLUÇÃO TEMPORAL
# ==============================

st.subheader("📈 Evolução Mensal do Faturamento")

evol = (
    df_filtrado.groupby("mes")["valor_num"].sum()
    .reset_index()
    .sort_values("mes")
)

st.line_chart(evol, x="mes", y="valor_num")

# Botões de exportação
colA, colB = st.columns(2)
with colA:
    st.download_button("⬇ Exportar Excel", exportar_excel(evol),
                       file_name="evolucao_mensal.xlsx")
with colB:
    st.download_button("⬇ Exportar PDF", exportar_pdf(evol, "Evolução Mensal"),
                       file_name="evolucao_mensal.pdf")


# ==============================
# COMPARAÇÃO ENTRE ANOS
# ==============================

if ano_comp:
    st.subheader(f"⚖ Comparação {ano_sel} × {ano_comp}")

    df_comp = df[df["ano"].isin([ano_sel, ano_comp])]
    comp = (
        df_comp.groupby(["ano","mes"])["valor_num"].sum()
        .reset_index()
        .sort_values(["ano","mes"])
    )

    st.area_chart(comp, x="mes", y="valor_num", color="ano")


# ==============================
# TOP 10 CLIENTES
# ==============================

st.subheader("🏆 Top 10 Clientes")

top10 = (
    df_filtrado.groupby("cliente_norm")["valor_num"].sum()
    .reset_index()
    .sort_values("valor_num", ascending=False)
    .head(10)
)

st.bar_chart(top10, x="cliente_norm", y="valor_num")

colA, colB = st.columns(2)
with colA:
    st.download_button("⬇ Exportar Excel", exportar_excel(top10),
                       file_name="top10_clientes.xlsx")
with colB:
    st.download_button("⬇ Exportar PDF", exportar_pdf(top10, "Top 10 Clientes"),
                       file_name="top10_clientes.pdf")


# ==============================
# CURVA ABC CLIENTES
# ==============================

st.subheader("📊 Curva ABC — Clientes")

abc_clientes = curva_abc(df_filtrado, "cliente_norm")
st.dataframe(abc_clientes)

colA, colB = st.columns(2)
with colA:
    st.download_button("⬇ Excel ABC", exportar_excel(abc_clientes),
                       file_name="curva_abc_clientes.xlsx")
with colB:
    st.download_button("⬇ PDF ABC", exportar_pdf(abc_clientes, "Curva ABC Clientes"),
                       file_name="curva_abc_clientes.pdf")


# ==============================
# CURVA ABC PRODUTOS (SE EXISTIR)
# ==============================

if col["produto"]:
    st.subheader("📦 Curva ABC — Produtos")
    abc_prod = curva_abc(df_filtrado, col["produto"])
    st.dataframe(abc_prod)

    colA, colB = st.columns(2)
    with colA:
        st.download_button("⬇ Excel", exportar_excel(abc_prod),
                           file_name="curva_abc_produtos.xlsx")
    with colB:
        st.download_button("⬇ PDF", exportar_pdf(abc_prod, "Curva ABC Produtos"),
                           file_name="curva_abc_produtos.pdf")


# ==============================
# MATRIZ CLIENTE (VALOR x FREQUÊNCIA)
# ==============================

st.subheader("🧩 Matriz Cliente (Valor × Frequência)")

matriz = (
    df_filtrado.groupby("cliente_norm")
    .agg(
        faturamento=("valor_num","sum"),
        frequencia=("documento","count") if col["documento"] else ("valor_num","count")
    )
    .reset_index()
)

st.scatter_chart(matriz, x="frequencia", y="faturamento")

st.download_button("⬇ Exportar Excel", exportar_excel(matriz),
                   file_name="matriz_cliente.xlsx")
