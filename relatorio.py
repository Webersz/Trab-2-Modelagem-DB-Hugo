"""Gera erd_modelo_estrela.png e Relatorio_Trabalho_II.pdf a partir do pipeline."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak, Preformatted

import pipeline as P

REPO = "https://github.com/Webersz/Trab-2-Modelagem-DB-Hugo"


def erd(path):
    fig, ax = plt.subplots(figsize=(9, 6)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 8.4)
    def box(x, y, title, rows, color):
        h = 0.45 * (len(rows) + 1)
        ax.add_patch(plt.Rectangle((x, y), 3, h, fc="#fff", ec=color, lw=2))
        ax.add_patch(plt.Rectangle((x, y + h - 0.45), 3, 0.45, fc=color, ec=color))
        ax.text(x + 1.5, y + h - 0.23, title, ha="center", va="center", color="w", weight="bold", fontsize=9)
        for i, r in enumerate(rows):
            ax.text(x + 0.1, y + h - 0.45 - 0.4 * (i + 0.6), r, fontsize=7.5, va="center")
        return (x + 1.5, y + h / 2)
    f = box(3.5, 1.5, "fato_vendas", ["sk_tempo (FK)", "sk_cliente (FK)", "sk_produto (FK)", "sk_vendedor (FK)",
            "sk_pagamento (FK)", "quantidade", "receita", "custo_total", "lucro_bruto", "margem_lucro_pct"], "#c0392b")
    d = {"dim_tempo": box(3.5, 7.0, "dim_tempo", ["sk_tempo (PK)", "data, ano, mes, trimestre"], "#1f4e79"),
         "dim_cliente": box(0.1, 5.2, "dim_cliente", ["sk_cliente (PK)", "nk_cliente", "nome, cidade, estado"], "#1f4e79"),
         "dim_produto": box(6.9, 5.2, "dim_produto", ["sk_produto (PK)", "nk_produto", "nome, categoria,", "preco, custo"], "#1f4e79"),
         "dim_vendedor": box(0.1, 0.4, "dim_vendedor", ["sk_vendedor (PK)", "nk_vendedor", "nome_vendedor, regiao"], "#1f4e79"),
         "dim_pagamento": box(6.9, 0.4, "dim_pagamento", ["sk_pagamento (PK)", "forma_pagamento"], "#1f4e79")}
    for p in d.values():
        ax.plot([f[0], p[0]], [f[1], p[1]], color="#555", lw=1, zorder=0)
    ax.set_title("Modelo Estrela - Tech LTDA", weight="bold")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def tbl(df, fs=8):
    data = [list(df.columns)] + [[(v.strftime("%d/%m/%Y") if hasattr(v, "strftime") else f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if (isinstance(v, float) or hasattr(v, "strftime")) else str(v))
                                  for v in r] for r in df.itertuples(index=False)]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), fs), ("GRID", (0, 0), (-1, -1), .4, colors.grey)]))
    return t


def main():
    con, q = P.main()
    erd("erd_modelo_estrela.png")
    ss = getSampleStyleSheet(); H, B = ss["Heading2"], ss["BodyText"]; B.alignment = 4
    code = ss["Code"]; code.fontSize = 6.5
    S = [Paragraph("Modelagem Dimensional e Engenharia de Dados com DuckDB", ss["Title"]),
         Paragraph("Trabalho II - Engenharia de Dados e MLOps - UniSENAI - Tech LTDA", ss["Heading4"]),
         Paragraph(f'Repositório Git: <link href="{REPO}" color="blue">{REPO}</link>', B), Spacer(1, 6),
         Paragraph("1. Evolução do OLTP (3FN)", H),
         Paragraph("Foi criada a tabela <b>oltp_vendedores</b> (3 vendedores: Sul e Sudeste). Em <b>oltp_pedidos</b> foram adicionadas as colunas "
                   "<b>vendedor_id</b> e <b>forma_pagamento</b> (PIX, Cartão de Crédito, Boleto), com todos os pedidos atualizados. "
                   "Em <b>oltp_produtos</b> foi adicionada <b>custo_unitario</b> (60% do preço, sempre inferior a ele). "
                   "O DuckDB não aceita FK em ALTER TABLE ADD COLUMN; por isso a integridade referencial de vendedor_id é validada por "
                   "uma verificação de órfãos no script.", B),
         Paragraph("oltp_vendedores", ss["Heading4"]), tbl(con.execute("SELECT * FROM oltp_vendedores").df()),
         Paragraph("oltp_pedidos (com vendedor_id e forma_pagamento)", ss["Heading4"]),
         tbl(con.execute("SELECT * FROM oltp_pedidos").df()),
         Paragraph("oltp_produtos (com custo_unitario)", ss["Heading4"]),
         tbl(con.execute("SELECT * FROM oltp_produtos").df()),
         Paragraph("2. ETL e Star Schema", H),
         Paragraph("O DW tem 5 dimensões (cliente, produto, vendedor, pagamento, tempo) com <i>surrogate keys</i> (sk_) geradas por ROW_NUMBER e "
                   "<i>natural keys</i> (nk_) preservadas. A <b>fato_vendas</b> (grão: item de pedido) guarda as SKs e as métricas "
                   "quantidade, receita (valor_pago), custo_total (quantidade × custo_unitario), lucro_bruto (receita − custo_total) e, como extra, "
                   "margem_lucro_pct. Uma verificação confirma que a receita total do DW é igual à do OLTP.", B),
         Image("erd_modelo_estrela.png", 13 * cm, 8.7 * cm), PageBreak(),
         Paragraph("Tabelas do Data Warehouse", H)] + sum(
        [[Paragraph(n, ss["Heading4"]), tbl(con.execute(f"SELECT * FROM {n}").df(), 6.5)]
         for n in ["dim_vendedor", "dim_pagamento", "dim_cliente", "dim_produto", "dim_tempo"]], []) + [PageBreak(), Paragraph("fato_vendas", ss["Heading4"]), tbl(con.execute("SELECT * FROM fato_vendas").df(), 6.5)] + [PageBreak(),
         Paragraph("3. Consultas analíticas", H)]
    r = [("3.1 Lucratividade por categoria", P.Q1, q["Q1"], f"A categoria <b>{q['Q1'].iloc[0,0]}</b> teve a maior receita e também o maior lucro bruto."),
         ("3.2 Desempenho por vendedor e região", P.Q2, q["Q2"], f"<b>{q['Q2'].iloc[0,0]}</b>, da região <b>{q['Q2'].iloc[0,1]}</b>, gerou mais receita."),
         ("3.3 Meio de pagamento (ticket médio = receita / total de itens)", P.Q3, q["Q3"],
          f"<b>{q['Q3'].iloc[0,0]}</b> lidera em receita; o maior ticket médio é de <b>{q['Q3'].sort_values('ticket_medio').iloc[-1,0]}</b>.")]
    for t, sql, df, txt in r:
        S += [Paragraph(t, ss["Heading3"]), Preformatted(sql, code), Spacer(1, 4), tbl(df), Spacer(1, 4), Paragraph(txt, B)]
    S += [Paragraph("4. Exportação", H),
          Paragraph("O script gera <b>data_warehouse_v2.xlsx</b> com as abas fato_vendas, dim_cliente, dim_produto, dim_vendedor, dim_pagamento, "
                    "dim_tempo e relatorio_analitico (resultado da consulta 3.3). Os dados são fictícios, criados para o exercício.", B)]
    SimpleDocTemplate("Relatorio_Trabalho_II.pdf", pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                      topMargin=1.5 * cm, bottomMargin=1.5 * cm, title="Trabalho II").build(S)


if __name__ == "__main__":
    main()
