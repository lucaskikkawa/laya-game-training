# Treino

Placeholder para v0.2. A v0.1 usa somente inferência; não modifica pesos.

`selecao.selecionar_sessoes(pasta)` retorna apenas sessões concluídas com
`valida_para_treino=true` e `motivo=null`. Qualquer derrota do algoritmo
invalida a sessão inteira (`algoritmo_perdeu`), mesmo com outras runs vencedoras.
Sessões antigas sem marcação explícita não são selecionadas.
