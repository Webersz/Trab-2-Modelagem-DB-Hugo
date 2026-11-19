"""Trabalho II - Modelagem Dimensional com DuckDB (Tech LTDA).

Pipeline: Criacao OLTP (3FN) -> evolucao do OLTP -> ETL Star Schema
          -> 3 consultas SQL OLAP -> exportacao Excel (data_warehouse_v2.xlsx).

Execucao:  python pipeline.py
"""
import duckdb
import pandas as pd

XLSX = "data_warehouse_v2.xlsx"


# --------------------------------------------------------------------------
# Etapa 0 - OLTP original (prototipo de sala de aula, recriado aqui)
# --------------------------------------------------------------------------
def criar_oltp_base(con):
    con.execute("""
        CREATE TABLE oltp_clientes (
            cliente_id INTEGER PRIMARY KEY, nome_cliente VARCHAR NOT NULL,
            cidade VARCHAR, estado VARCHAR);
        CREATE TABLE oltp_produtos (
            produto_id INTEGER PRIMARY KEY, nome_produto VARCHAR NOT NULL,
            categoria VARCHAR NOT NULL, preco_unitario DECIMAL(10,2) NOT NULL);
        CREATE TABLE oltp_pedidos (
            pedido_id INTEGER PRIMARY KEY,
            cliente_id INTEGER NOT NULL REFERENCES oltp_clientes(cliente_id),
            data_pedido DATE NOT NULL);
        CREATE TABLE oltp_itens_pedido (
            item_id INTEGER PRIMARY KEY,
            pedido_id INTEGER NOT NULL REFERENCES oltp_pedidos(pedido_id),
            produto_id INTEGER NOT NULL REFERENCES oltp_produtos(produto_id),
            quantidade INTEGER NOT NULL, valor_pago DECIMAL(10,2) NOT NULL);
    """)
    con.execute("""
        INSERT INTO oltp_clientes VALUES
          (1,'Ana Souza','Porto Alegre','RS'), (2,'Bruno Lima','Sao Paulo','SP'),
          (3,'Carla Dias','Curitiba','PR'),    (4,'Diego Alves','Rio de Janeiro','RJ'),
          (5,'Elisa Rocha','Florianopolis','SC');
        INSERT INTO oltp_produtos VALUES
          (1,'Notebook Pro','Eletronicos',5000.00), (2,'Smartphone X','Eletronicos',3000.00),
          (3,'Fone Bluetooth','Acessorios',300.00), (4,'Mouse Gamer','Acessorios',150.00),
          (5,'Cadeira Ergonomica','Moveis',1200.00),(6,'Mesa Home Office','Moveis',900.00);
        INSERT INTO oltp_pedidos VALUES
          (1,1,'2024-01-10'),(2,2,'2024-01-15'),(3,3,'2024-02-05'),(4,4,'2024-02-20'),
          (5,5,'2024-03-03'),(6,1,'2024-03-18'),(7,2,'2024-04-07'),(8,3,'2024-04-25');
        INSERT INTO oltp_itens_pedido VALUES
          (1,1,1,1,5000.00),(2,1,4,2,300.00),(3,2,2,1,3000.00),(4,3,5,2,2400.00),
          (5,4,3,3,900.00),(6,5,6,1,900.00),(7,5,4,1,150.00),(8,6,2,2,6000.00),
          (9,7,5,1,1200.00),(10,7,3,2,600.00),(11,8,1,1,4800.00),(12,8,6,2,1800.00);
    """)


# --------------------------------------------------------------------------
# Etapa 1 - Evolucao do OLTP (3FN)
# --------------------------------------------------------------------------
def evoluir_oltp(con):
    # 1) nova tabela de vendedores (>= 2 registros)
    con.execute("""
        CREATE TABLE oltp_vendedores (
            vendedor_id INTEGER PRIMARY KEY, nome_vendedor VARCHAR NOT NULL, regiao VARCHAR NOT NULL);
        INSERT INTO oltp_vendedores VALUES
          (1,'Marcos Pereira','Sul'), (2,'Juliana Castro','Sudeste'), (3,'Rafael Gomes','Sul');
    """)
    # 2) pedidos: vendedor_id (FK logica) e forma_pagamento
    #    DuckDB nao permite ADD COLUMN ... REFERENCES; a FK e validada abaixo.
    con.execute("ALTER TABLE oltp_pedidos ADD COLUMN vendedor_id INTEGER")
    con.execute("ALTER TABLE oltp_pedidos ADD COLUMN forma_pagamento VARCHAR")
    con.execute("""
        UPDATE oltp_pedidos SET
          vendedor_id = CASE pedido_id WHEN 1 THEN 1 WHEN 2 THEN 2 WHEN 3 THEN 1 WHEN 4 THEN 2
                                       WHEN 5 THEN 3 WHEN 6 THEN 1 WHEN 7 THEN 2 ELSE 3 END,
          forma_pagamento = CASE pedido_id WHEN 1 THEN 'PIX' WHEN 2 THEN 'Cartão de Crédito'
                                       WHEN 3 THEN 'Boleto' WHEN 4 THEN 'PIX' WHEN 5 THEN 'Cartão de Crédito'
                                       WHEN 6 THEN 'PIX' WHEN 7 THEN 'Boleto' ELSE 'Cartão de Crédito' END""")
    orfaos = con.execute("""SELECT COUNT(*) FROM oltp_pedidos p
        LEFT JOIN oltp_vendedores v USING (vendedor_id) WHERE v.vendedor_id IS NULL""").fetchone()[0]
    assert orfaos == 0, "vendedor_id sem correspondente em oltp_vendedores"
    # 3) produtos: custo_unitario < preco_unitario
    con.execute("ALTER TABLE oltp_produtos ADD COLUMN custo_unitario DECIMAL(10,2)")
    con.execute("UPDATE oltp_produtos SET custo_unitario = ROUND(preco_unitario * 0.60, 2)")
    assert con.execute("SELECT COUNT(*) FROM oltp_produtos WHERE custo_unitario >= preco_unitario").fetchone()[0] == 0


# --------------------------------------------------------------------------
# Etapa 2 - ETL / Star Schema (Kimball): SK = surrogate key, NK = natural key
# --------------------------------------------------------------------------
def construir_dw(con):
    con.execute("""
        CREATE TABLE dim_cliente AS
        SELECT ROW_NUMBER() OVER (ORDER BY cliente_id) AS sk_cliente,
               cliente_id AS nk_cliente, nome_cliente, cidade, estado
        FROM oltp_clientes;

        CREATE TABLE dim_produto AS
        SELECT ROW_NUMBER() OVER (ORDER BY produto_id) AS sk_produto,
               produto_id AS nk_produto, nome_produto, categoria, preco_unitario, custo_unitario
        FROM oltp_produtos;

        CREATE TABLE dim_vendedor AS
        SELECT ROW_NUMBER() OVER (ORDER BY vendedor_id) AS sk_vendedor,
               vendedor_id AS nk_vendedor, nome_vendedor, regiao
        FROM oltp_vendedores;

        CREATE TABLE dim_pagamento AS
        SELECT ROW_NUMBER() OVER (ORDER BY forma_pagamento) AS sk_pagamento, forma_pagamento
        FROM (SELECT DISTINCT forma_pagamento FROM oltp_pedidos);

        CREATE TABLE dim_tempo AS
        SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER) AS sk_tempo, d AS data,
               year(d) AS ano, month(d) AS mes, monthname(d) AS nome_mes,
               quarter(d) AS trimestre, dayofweek(d) AS dia_semana
        FROM (SELECT DISTINCT data_pedido AS d FROM oltp_pedidos);

        CREATE TABLE fato_vendas AS
        SELECT i.item_id AS nk_item, i.pedido_id AS nk_pedido,
               t.sk_tempo, c.sk_cliente, pr.sk_produto, v.sk_vendedor, pg.sk_pagamento,
               i.quantidade,
               i.valor_pago                                         AS receita,
               i.quantidade * p.custo_unitario                      AS custo_total,
               i.valor_pago - i.quantidade * p.custo_unitario       AS lucro_bruto,
               ROUND((i.valor_pago - i.quantidade * p.custo_unitario) / i.valor_pago * 100, 2) AS margem_lucro_pct
        FROM oltp_itens_pedido i
        JOIN oltp_pedidos  o ON o.pedido_id  = i.pedido_id
        JOIN oltp_produtos p ON p.produto_id = i.produto_id
        JOIN dim_tempo     t  ON t.data = o.data_pedido
        JOIN dim_cliente   c  ON c.nk_cliente  = o.cliente_id
        JOIN dim_produto   pr ON pr.nk_produto = i.produto_id
        JOIN dim_vendedor  v  ON v.nk_vendedor = o.vendedor_id
        JOIN dim_pagamento pg ON pg.forma_pagamento = o.forma_pagamento;
    """)
    # reconciliacao: o DW deve preservar a receita do OLTP
    r_oltp = con.execute("SELECT SUM(valor_pago) FROM oltp_itens_pedido").fetchone()[0]
    r_dw = con.execute("SELECT SUM(receita) FROM fato_vendas").fetchone()[0]
    assert r_oltp == r_dw, f"receita divergente: {r_oltp} vs {r_dw}"


# --------------------------------------------------------------------------
# Etapa 3 - Consultas OLAP
# --------------------------------------------------------------------------
Q1 = """-- Lucratividade por categoria
SELECT p.categoria, SUM(f.receita) AS receita_total, SUM(f.lucro_bruto) AS lucro_bruto_total
FROM fato_vendas f JOIN dim_produto p USING (sk_produto)
GROUP BY p.categoria ORDER BY receita_total DESC"""

Q2 = """-- Desempenho por vendedor e regiao
SELECT v.nome_vendedor, v.regiao, SUM(f.receita) AS receita_total
FROM fato_vendas f JOIN dim_vendedor v USING (sk_vendedor)
GROUP BY v.nome_vendedor, v.regiao ORDER BY receita_total DESC"""

Q3 = """-- Meio de pagamento: receita total e ticket medio (receita / total de itens)
SELECT pg.forma_pagamento, SUM(f.receita) AS receita_total, SUM(f.quantidade) AS total_itens,
       ROUND(SUM(f.receita) / SUM(f.quantidade), 2) AS ticket_medio
FROM fato_vendas f JOIN dim_pagamento pg USING (sk_pagamento)
GROUP BY pg.forma_pagamento ORDER BY receita_total DESC"""


# --------------------------------------------------------------------------
# Etapa 4 - Exportacao
# --------------------------------------------------------------------------
def exportar(con, consultas):
    with pd.ExcelWriter(XLSX, engine="openpyxl") as xw:
        for tab in ["fato_vendas", "dim_cliente", "dim_produto", "dim_vendedor", "dim_pagamento", "dim_tempo"]:
            df = con.execute(f"SELECT * FROM {tab}").df()
            if tab == "dim_tempo":
                df["data"] = pd.to_datetime(df["data"]).dt.date
            df.to_excel(xw, sheet_name=tab, index=False)
        consultas["Q3"].to_excel(xw, sheet_name="relatorio_analitico", index=False)
        for ws in xw.book.worksheets:           # largura de colunas
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(len(str(c.value or "")) for c in col) + 3


def main():
    con = duckdb.connect(":memory:")
    criar_oltp_base(con)
    evoluir_oltp(con)
    construir_dw(con)
    consultas = {k: con.execute(q).df() for k, q in {"Q1": Q1, "Q2": Q2, "Q3": Q3}.items()}
    exportar(con, consultas)
    for k, df in consultas.items():
        print(f"\n{k}\n{df.to_string(index=False)}")
    return con, consultas


if __name__ == "__main__":
    main()
