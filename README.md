# csmRadar — Observatório dos Movimentos Judiciais em Portugal (2004–2026)

**Dashboard interativo:** https://sergioamsilva.github.io/csmradar/

## Resumo

O csmRadar sistematiza e analisa **12 747 colocações de juízes** decididas nos
Movimentos Judiciais Ordinários (MJO) portugueses entre 2004 e 2026, extraídas
das versões finais publicadas pelo Conselho Superior da Magistratura (CSM) e,
para 2009–2010, do Diário da República (2.ª série). O conjunto de dados cobre
23 movimentos anuais e permite estudar a mobilidade da magistratura judicial em
cinco dimensões: geográfica (fluxos e saldos entre comarcas, distâncias,
assimetria interior/litoral), de carreira (permanência, promoções, regressos),
de preferências (grau de satisfação das escolhas dos juízes, atratividade
relativa das comarcas), de género (participação feminina nos movimentos e nas
três instâncias ao longo de duas décadas) e demográfica (entradas e saídas do
sistema, balanço com o pipeline de formação e projeção de cessações).

## Fontes

Todos os dados provêm de documentos oficiais de acesso público:

- **Movimentos Judiciais Ordinários** — versões finais/consolidadas publicadas
  pelo CSM (csm.org.pt) para 2004–2008 e 2011–2026; publicação no Diário da
  República, 2.ª série, para 2009–2010. Os URL de todos os documentos constam
  de [`fontes/movimentos_fontes.tsv`](fontes/movimentos_fontes.tsv).
- **Quadros anuais de juízes** (STJ, Tribunais da Relação, 1.ª instância,
  quadros complementares), 2014–2026 —
  [`fontes/quadros_fontes.tsv`](fontes/quadros_fontes.tsv).
- **Validação externa** — série oficial de cessações do Relatório Anual do
  CSM (2023) e Estudo sobre as necessidades de recrutamento de juízes (CSM,
  2023) — [`fontes/cej_e_validacao_fontes.tsv`](fontes/cej_e_validacao_fontes.tsv).
- **Pipeline de formação (CEJ)** — vagas para a magistratura judicial nos
  avisos de abertura dos concursos de ingresso no Centro de Estudos
  Judiciários: Aviso n.º 225/2023 (40.º curso, 52), Aviso n.º 25126/2023
  (41.º, 52), Aviso n.º 7191-B/2025 (42.º, 75) e Aviso n.º 1435-A/2026
  (43.º, 79). O desfasamento aviso→colocação (~3 anos) foi calibrado com os
  cursos 34.º (48 vagas em 2018 → 42 colocações no MJO 2021) e 40.º (52 vagas
  em 2023 → 56 colocações no MJO 2026) —
  [`fontes/cej_e_validacao_fontes.tsv`](fontes/cej_e_validacao_fontes.tsv).
- **Lista de antiguidade dos magistrados judiciais** — reportada a 31-12-2025,
  homologada pelo CSM em 26-03-2026: tempo de serviço na categoria e na
  magistratura dos 1941 magistrados judiciais no ativo (60 juízes
  conselheiros, 470 desembargadores, 1411 juízes de direito). Não contém
  datas de nascimento.
- **Acesso ao STJ** — Divulgações do CSM n.º 61/2026 (graduação do
  18.º Concurso Curricular de Acesso ao STJ) e n.º 109/2026 (graduação final
  após reclamações: 126 desembargadores, 12 procuradores-gerais adjuntos e
  3 juristas de mérito, para as vagas de 12-03-2026 a 01-08-2028), e notícia
  oficial da posse de 17 juízes conselheiros em 09-07-2026.
- **Perfil etário de ingresso** — estudos sociográficos do CEJ sobre os
  auditores de justiça (idade média de entrada no curso de formação).

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
   primeira e última aparição de cada juiz na união dos quadros anuais das
   Relações e da 1.ª instância, com nomes normalizados (STJ excluído por
   lacunas nos quadros publicados); os anos de fronteira da série são
   excluídos. A estimativa foi **validada externamente** contra a série de
   cessações do Relatório Anual do CSM de 2023 (34, 25, 64, 77 e 55 saídas em
   2019–2023, anos civis): acompanha o padrão, com um excesso de ~20%
   atribuível a variações de grafia e a saídas temporárias longas.
5. **Validação.** Totais confrontados com os declarados nos próprios documentos
   quando existentes; distribuições anuais inspecionadas para deteção de
   anomalias; espelho independente de todas as estatísticas apresentadas.
6. **Proteção de dados.** O dashboard publicado não contém nomes de
   magistrados: os registos são pseudonimizados na compilação e apenas
   agregados são apresentados, em conformidade com o RGPD.

### Demografia do sistema

Sobre a base de entradas/saídas foram construídos indicadores demográficos:
balanço anual do sistema, composição por género de quem entra e de quem sai,
anos de carreira observáveis à saída e até à promoção (valores mínimos, por
censura à esquerda em 2004), taxa de saída por comarca, correlação entre as
saídas e as colocações de primeiro acesso do movimento seguinte, e projeção de
saídas até 2030 ao ritmo médio dos últimos cinco anos, confrontada com as
entradas já garantidas pelo pipeline de formação do CEJ. Todos os cartões
declaram as limitações do método.

### Idades estimadas

A lista de antiguidade não contém datas de nascimento. A idade de cada
magistrado é **estimada** somando ao tempo de serviço na magistratura a idade
típica de nomeação da respetiva época de ingresso, com interpolação linear
entre âncoras decenais: ~26 anos no início dos anos 80 — valor autocalibrado
pela consistência com o limite de idade de 70 anos (os magistrados com maior
tempo de serviço, ~44 anos, têm de se encontrar abaixo do limite) — até ~34
anos na atualidade (os estudos sociográficos do CEJ situam a entrada dos
auditores da via judicial nos ~31 anos, a que acrescem cerca de dois anos de
formação). A incerteza individual é de ±3–4 anos; apenas distribuições
agregadas são apresentadas (pirâmide etária por género, medianas por
categoria, contagem anual de quem atinge os 66 e os 70 anos). Os 15 juízes
conselheiros de entrada lateral (Ministério Público e juristas de mérito),
sem carreira judicial contável, são excluídos da estimativa.

### Cenários de vagas no STJ («o gargalo»)

O acesso ao STJ faz-se por concurso curricular, fora dos MJO, pelo que não é
observável na base de colocações. O cartão dedicado usa um **modelo de
cadeiras declaradamente ilustrativo**: 70 lugares (quadro de 2023); coorte
instalada no início de 2026 com idades uniformes 61–70 — consistente com a
lista de antiguidade, que estima os conselheiros de carreira então em
funções em 66+ anos —; novos conselheiros a entrar aos ~58 (a maioria dos
empossados de julho de 2026 tinha menos de 60 anos); saída aos 67 até 2028 em
ambos os cenários e, daí em diante, aos 67 (cenário A) ou por retenção até ao
limite de 70 (cenário B). O modelo é calibrado pelo observado — 17 posses em
julho de 2026 (28 no ano simulado, incluindo as anunciadas para o outono) e
~42 promoções até agosto de 2028, compatível com a expectativa do concurso —
e não constitui uma previsão.

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
- As idades são estimativas derivadas do tempo de serviço (±3–4 anos por
  pessoa); não devem ser lidas ao ano, apenas em agregado.
- O cartão «O gargalo do STJ» apresenta cenários, não previsões: o
  comportamento de saída (aposentação vs. permanência até aos 70) é a própria
  incógnita que os cenários delimitam.

## Reprodução

O sítio é um único ficheiro estático (`index.html`) com os dados agregados
embebidos. O processo completo — descarregamento dos documentos (URL nos
ficheiros de fontes), extração, construção da base de dados SQLite e geração
do dashboard — está descrito e implementado nos scripts:

```
parse_mjo*.py         extração dos movimentos (por família de formato)
parse_quadros.py      extração dos quadros anuais de juízes
parse_antiguidade.py  extração da lista de antiguidade dos magistrados
genero.py             inferência de género a partir do nome próprio
build_db.py           construção da base de dados SQLite
build_mapa.py         projeção cartográfica (distritos e sedes de comarca)
build_dashboard.py    agregação e geração do dashboard (template.html)
```

## Atualização

Última extração de dados: julho de 2026 (inclui a versão consolidada do MJO
de 2026, o 43.º concurso de ingresso no CEJ, a lista de antiguidade reportada
a 31-12-2025 e o 18.º Concurso Curricular de Acesso ao STJ). O conjunto
atualiza-se a cada Movimento Judicial Ordinário.

## Citação sugerida

> csmRadar — Observatório dos Movimentos Judiciais em Portugal, 2004–2026.
> Compilação a partir das divulgações do Conselho Superior da Magistratura e
> do Diário da República. Disponível em
> https://sergioamsilva.github.io/csmradar/ (consultado em [data]).

## Licença

Código sob licença MIT. Os documentos-fonte são publicações oficiais de acesso
público; os dados agregados derivados são disponibilizados para fins de
investigação e informação pública, com indicação da fonte.
