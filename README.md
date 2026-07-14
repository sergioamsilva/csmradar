# csmRadar — Observatório dos Movimentos Judiciais em Portugal (2004–2026)

**Dashboard interativo:** https://sergioamsilva.github.io/csmradar/

## Resumo

O csmRadar sistematiza e analisa **12 747 colocações de juízes** decididas nos
Movimentos Judiciais Ordinários (MJO) portugueses entre 2004 e 2026, extraídas
das versões finais publicadas pelo Conselho Superior da Magistratura (CSM) e,
para 2009–2010, do Diário da República (2.ª série). O conjunto de dados cobre
23 movimentos anuais e permite estudar a mobilidade da magistratura judicial em
quatro dimensões: geográfica (fluxos e saldos entre comarcas, distâncias,
assimetria interior/litoral), de carreira (permanência, promoções, regressos),
de preferências (grau de satisfação das escolhas dos juízes, atratividade
relativa das comarcas) e de género (participação feminina nos movimentos e nas
três instâncias ao longo de duas décadas).

## Fontes

Todos os dados provêm de documentos oficiais de acesso público:

- **Movimentos Judiciais Ordinários** — versões finais/consolidadas publicadas
  pelo CSM (csm.org.pt) para 2004–2008 e 2011–2026; publicação no Diário da
  República, 2.ª série, para 2009–2010. Os URL de todos os documentos constam
  de [`fontes/movimentos_fontes.tsv`](fontes/movimentos_fontes.tsv).
- **Quadros anuais de juízes** (STJ, Tribunais da Relação, 1.ª instância,
  quadros complementares), 2014–2026 —
  [`fontes/quadros_fontes.tsv`](fontes/quadros_fontes.tsv).

## Metodologia

1. **Extração.** Os documentos-fonte apresentam seis formatos distintos ao
   longo do período. Foi escrito um analisador sintático dedicado para cada
   família: tabelas numeradas (2004–2008), prosa do Diário da República
   (2009–2010), formato proto-tabular do CSM (2011), documentos Word tabulados
   (2012–2013), formato de três colunas «iudex» (2014–2025) e o formato de 2026
   com marcadores semânticos. O código encontra-se em [`scripts/`](scripts/).
2. **Normalização.** Comarcas reduzidas à nomenclatura canónica das 23 comarcas
   pós-2014; motivos de movimento reconciliados num vocabulário comum;
   distâncias calculadas em linha reta (haversine) entre as sedes de comarca.
3. **Género.** Obtido do tratamento honorífico constante dos próprios
   documentos («Dr.»/«Dr.ª/Dra.») até 2010 e, nos restantes anos, inferido do
   primeiro nome próprio com listas de exceções; taxa de classificação de 100%
   dos registos, validada ano a ano.
4. **Renovação do sistema.** As entradas e saídas do sistema judicial
   (jubilações e outras cessações, ausentes dos movimentos) são estimadas pela
   primeira e última aparição de cada juiz na união dos quadros anuais das três
   instâncias, com nomes normalizados; os anos de fronteira da série são
   excluídos por serem estruturalmente enviesados.
5. **Validação.** Totais confrontados com os declarados nos próprios documentos
   quando existentes; distribuições anuais inspecionadas para deteção de
   anomalias; espelho independente de todas as estatísticas apresentadas.
6. **Proteção de dados.** O dashboard publicado não contém nomes de
   magistrados: os registos são pseudonimizados na compilação e apenas
   agregados são apresentados, em conformidade com o RGPD.

## Limitações

- Antes de 2014 vigora o mapa judicial anterior à reorganização (Lei
  n.º 62/2013); não existe equivalência direta de comarcas, pelo que as
  métricas geográficas finas se restringem a 2014–2026.
- A publicação de 2009–2010 (Diário da República) não inclui preferências nem
  classificações de mérito.
- Em 2020 o movimento foi restringido pela pandemia e não abrangeu os
  Tribunais da Relação.
- O quadro do STJ de 2022 não foi publicado; os de 2024–2025 têm extração
  parcial.
- Cerca de 1,6% dos registos de 2014–2017 carecem de motivo ou antiguidade por
  variações de leiaute dos originais.

## Reprodução

O sítio é um único ficheiro estático (`index.html`) com os dados agregados
embebidos. O processo completo — descarregamento dos documentos (URL nos
ficheiros de fontes), extração, construção da base de dados SQLite e geração
do dashboard — está descrito e implementado nos scripts:

```
parse_mjo*.py      extração dos movimentos (por família de formato)
parse_quadros.py   extração dos quadros anuais de juízes
genero.py          inferência de género a partir do nome próprio
build_db.py        construção da base de dados SQLite
build_mapa.py      projeção cartográfica (distritos e sedes de comarca)
build_dashboard.py agregação e geração do dashboard (template.html)
```

## Citação sugerida

> csmRadar — Observatório dos Movimentos Judiciais em Portugal, 2004–2026.
> Compilação a partir das divulgações do Conselho Superior da Magistratura e
> do Diário da República. Disponível em
> https://sergioamsilva.github.io/csmradar/ (consultado em [data]).

## Licença

Código sob licença MIT. Os documentos-fonte são publicações oficiais de acesso
público; os dados agregados derivados são disponibilizados para fins de
investigação e informação pública, com indicação da fonte.
