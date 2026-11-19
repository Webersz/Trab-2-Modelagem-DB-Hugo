# Trabalho II – Modelagem Dimensional com DuckDB (Tech LTDA)

Pipeline completo: OLTP (3FN) → evolução (vendedores, forma de pagamento, custo) → Star Schema Kimball → 3 consultas OLAP → Excel.

```bash
pip install -r requirements.txt
python pipeline.py     # gera data_warehouse_v2.xlsx
python relatorio.py    # gera erd_modelo_estrela.png e Relatorio_Trabalho_II.pdf
```

- `pipeline.py` – script comentado com todas as etapas
- `data_warehouse_v2.xlsx` – abas fato_vendas, dim_cliente, dim_produto, dim_vendedor, dim_pagamento, dim_tempo, relatorio_analitico
- `erd_modelo_estrela.png` – diagrama do modelo estrela (bônus)
- `Relatorio_Trabalho_II.pdf` – relatório de entrega

Os dados do OLTP base (clientes, produtos, pedidos, itens) são fictícios, recriados no script.
