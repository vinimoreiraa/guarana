# Pesquisa: planejamento da oferta de oftalmologia no SUS e base para o dashboard de alocação

Data: 01/10/2026. Pesquisa feita com WebSearch e WebFetch, mais download direto (curl) do FTP do DATASUS e das APIs do IBGE.
Convenção: **[V]** = verificado nesta pesquisa, na fonte primária ou num documento oficial lido; **[S]** = visto só em resumo de busca ou na imprensa; **[NV]** = não verificado nesta sessão (conhecimento prévio, conferir antes de citar).

---

## 1. Como o planejamento é feito hoje (passo a passo e quem decide)

### 1.1 Arcabouço normativo
| Norma | O que define | Status |
|---|---|---|
| Portaria GM/MS 957/2008 | Política Nacional de Atenção em Oftalmologia (APS → média complexidade → alta complexidade) | [S] |
| Portaria SAS/MS 288/2008 | Redes estaduais e regionais de oftalmologia. Serviço de média complexidade com **mínimo de 240 consultas/mês**; Centro de Referência com **mínimo de 600 consultas/mês**; 15% das consultas para menores de 15 anos; o serviço de alta complexidade faz no mínimo 24 procedimentos de alta complexidade por ano; quantitativo indicativo de **922 unidades de atenção especializada e 28 centros de referência** no país (base de 184,2 mi hab.) | [V] bvsms |
| Portaria SAS 433/2012 | **Suspendeu os parâmetros populacionais** de habilitação em oftalmologia (e em cardiologia, nefrologia e neurocirurgia) | [V] (citada no Caderno 1 de Parâmetros) |
| Portaria GM/MS 1.631/2015 → PRC nº 1/2017, arts. 102–106 | Critérios e Parâmetros Assistenciais (Caderno 1, 2017). Para oftalmologia: **4 oftalmologistas (40 h) por 100 mil hab.** (1 por 25 mil) e **13.800 consultas oftalmológicas por 100 mil hab.**; também paquimetria 410, US ocular 210, biometria 460, biomicroscopia de fundo 1.450 e campimetria 560 por 100 mil hab. São indicativos e não vinculantes. **Não achei no Caderno 1 um parâmetro explícito de cirurgias de catarata por 10 mil hab.** | [V] PDF gov.br |
| PPI (Portaria GM 1.097/2006) → PGASS (Decreto 7.508/2011) → PRI (Res. CIT 37/2018) | Programação pactuada: quem executa quanto, e para quem | [NV] |
| Política Nacional de Regulação (Portaria GM 1.559/2008) | Complexos reguladores, centrais de regulação e SISREG | [NV] |
| TFD (Portaria SAS 55/1999) | Custeio do deslocamento quando não há oferta no município | [NV] |
| PMAE: Portaria GM/MS 3.492/2024 (ambulatorial); a Portaria GM/MS 3.592/2024 também é citada pelo TCU | Programa Mais Acesso a Especialistas e criação das **OCI** | [V] citado no Acórdão TCU |
| Portaria SAES/MS 1.826, de 11/06/2024 | **OCI de oftalmologia**: Avaliação inicial 0–8 anos (09.05.01.001-9, R$ 200); Estrabismo 0–8 (R$ 200); **Avaliação inicial a partir de 9 anos (09.05.01.003-5, R$ 160)**; Retinopatia diabética (R$ 200); Oncologia oftalmológica (R$ 250); Neuro-oftalmologia (R$ 300). APAC válida por 2 competências. **A cirurgia de catarata não faz parte da OCI**: a OCI cobre diagnóstico e entrega a indicação cirúrgica | [V] bvsms |
| Agora Tem Especialistas (PATE): MPV 1.301/2025 → Lei 15.233/2025; Portaria GM/MS 7.266, de 18/06/2025 | Mantém os componentes do PMAE e soma 6 novos: radioterapia, créditos financeiros, ressarcimento ao SUS, provimento de força de trabalho especializada, SUS Digital e serviços complementares (é aqui que entram as carretas) | [V] TCU |

O TCU fala em **7 OCI de oftalmologia** (34 OCI no total). A sétima não foi identificada; possivelmente veio por portaria SAES posterior (ex.: 2.331/2024). [NV]

### 1.2 Fluxo real (quem decide o quê)
1. **APS/ESF**: o ACS identifica a queixa e o médico/enfermeiro da UBS encaminha. Hoje não existe triagem ocular sistemática pelo ACS, e é essa lacuna que o Guaraná cobre.
2. **Regulação municipal/estadual** (SISREG ou sistema próprio, como o SER do RJ, o CROSS de SP e o Gercon do RS [NV]): o encaminhamento entra na fila de consulta oftalmológica ou de OCI. Quem decide a prioridade é o médico regulador, com base em protocolos (há protocolos publicados pela SES-DF e pela PBH para catarata [S]).
3. **OCI / consulta especializada**: avaliação em até 60 dias [S]. Sai daqui a indicação cirúrgica e o paciente entra na **fila cirúrgica**.
4. **Programação da oferta**: cada estado monta um **Plano de Ação Regional (PAR)** de OCI e uma **programação estadual de cirurgias eletivas**. Os planos passam pela **CIR** (Comissão Intergestores Regional) e pela **CIB**, e o MS aprova. O dinheiro vem do FAEC e é pago por produção. [V] TCU
5. **Execução**: rede própria ou contratada, hospitais filantrópicos, **mutirões estaduais** (Opera+ Amazonas, Opera Paraná), **carretas federais** do PATE e **consórcios intermunicipais** (Lei 11.107/2005 [NV]), que compram serviço em escala para municípios pequenos.
6. **Monitoramento**: o MS consolida filas declaradas pelos estados e dados da RNDS. O TCU registrou que o **SISREG não manda para a RNDS os dados de regulação de cirurgias hospitalares**, e por isso o tamanho das filas é **autodeclarado**, "com grande incerteza". [V]

**Conclusão:** quem decide são os gestores estaduais e regionais (SES, CIB/CIR), com o MS induzindo e financiando. A demanda é medida pela fila (a demanda *expressa*). A **demanda oculta**, de quem nunca chegou à UBS, não aparece em nenhum sistema, e é justamente esse o valor do Guaraná.

### 1.3 Números das iniciativas recentes
- **Acórdão 1.622/2026-TCU-Plenário** (TC 015.703/2025-8, sessão de 24/06/2026, relator Bruno Dantas), auditoria do PATE [V]:
  - Fila declarada de **catarata (facoemulsificação com LIO dobrável)**: **167.509 (2023), 154.187 (2024), 208.294 (2025)**, alta de 24,3%. É a maior fila cirúrgica do SUS nos três anos e responde por ≥10% de toda a fila.
  - Fila de **capsulotomia YAG** (efeito cascata das cirurgias de catarata): 24,5 mil em 2024 e **52 mil em 2025**. Catarata + YAG = 13,6% da fila de 2025; com o laser de retina, 15,4%.
  - O tempo de espera da catarata ficou em "padrão estável" (mediana, desvio-padrão e Q3 com pouca variação). Na RNDS, as medianas de oftalmologia ficaram em 8–13 dias, mas a cobertura da RNDS é limitada.
  - OCI: os PAR previam **9.973.969 OCI em 2025**. Foram feitas **685.826** entre jan e nov (**6,9%**). **56% da produção de OCI é de oftalmologia**. A OCI mais feita foi a "Avaliação inicial em oftalmologia a partir de 9 anos", com 31,1% do programado.
  - Meta da PAS 2025: 6.300 novos especialistas e taxa de expansão de cirurgias eletivas de 1,25.
- **Carretas do PATE** [S, imprensa]: começaram em out/2025. Em 2026 eram ~81–87 carretas, **12 de oftalmologia**, e passavam de 80 mil cirurgias de catarata. Cada unidade tem uma carreta-consultório e uma carreta-centro cirúrgico, com capacidade declarada de **até 150 consultas e 100 cirurgias por dia**. Ficam ~45 dias em cada cidade (Alta Floresta/MT: 35 dias úteis, previsão de 3 mil cirurgias). Resultados: Ponta Grossa/PR, 1.148 cirurgias em ~7 semanas; RN, >3.200 cirurgias; Teresópolis/RJ, ~2.500. A matéria da Agência Gov (set/2026, "1 milhão de procedimentos") está fora do ar por causa da legislação eleitoral.
- **Opera+ Amazonas** [S, SES-AM]: meta de 12 mil cirurgias de catarata até dez/2025, a 180 cirurgias/dia (seg–sáb). A SES-AM afirma ter **zerado a fila de catarata em Manaus** e passou a fazer mutirões no interior. Parintins, a 369 km de Manaus: meta de 140 procedimentos (70 de pterígio e 60 de catarata). A estrutura usa 15 unidades, 2 Caravanas da Saúde e o **Barco Hospital São João XXIII**.
- **Teleoftalmologia (TeleOftalmo, TelessaúdeRS-UFRGS, CIB/RS 032/2017)** [S]: 30.315 pacientes analisados, e **70,5% resolvidos sem encaminhamento presencial**. A estimativa é de redução de 31% no custo (SciELO, *Cad. Saúde Pública* e *Ciênc. Saúde Coletiva* 2020).
- **Curitiba** [S, TCU via busca]: fila de oftalmologia caiu de 47.780 (jan/2025) para 557 (set/2026).

---

## 2. O problema de distribuição

**Fonte principal:** *Demografia Médica no Brasil 2025*, Informe Técnico nº 07 (ago/2025), FMUSP/AMB/MS/OPAS. URL: https://fm.usp.br/fmusp/conteudo/radar_oftalmologistas_demografiamedica.pdf [V]

- **16.784 oftalmologistas** (indivíduos) e 19.054 registros em CRM. Razão de **8,96 por 100 mil hab.** O parâmetro do MS é 4 por 100 mil, então **não falta oftalmologista no agregado. O problema é a distribuição.**
- Por região (por 100 mil): Norte **4,61**, Nordeste 6,55, Sul 9,25, Centro-Oeste 10,80, Sudeste 10,98.
- Extremos por UF: DF **19,18**, SP 11,25, ES 10,97 contra **AM 3,60**, **PA 3,77**, MA 4,22 e AC 4,54. Dezoito UFs ficam abaixo da média.
- Por porte de município: ≥500 mil hab. **18,75/100 mil** (48 cidades concentram **65%** dos oftalmologistas); 50–100 mil, 4,63; 20–50 mil, 2,19; 10–20 mil, **0,59**; ≤5 mil, **0,32**.
- **Municípios com pelo menos 1 oftalmologista:** **1.307 de 5.570 (23,5%)**. **24 regiões de saúde não têm nenhum.** Esses 1.307 municípios concentram 74,6% da população. São 10.534 oftalmologistas no SUS, de 19.974 no CNES de jun/2024 (Gomes, Souto Maior, Silva, *Saúde em Debate*, 2024/25) [V resumo]. O Censo CBO de 2014 dava 848 municípios [S].
- **Cirurgias de catarata em 2024:** SUS **1.181.837** (736 por 100 mil usuários exclusivos do SUS, +20% sobre 2023) e planos 664.861 (1.277 por 100 mil). Total de 868,69 por 100 mil, ou **~87 por 10 mil hab./ano**. Os planos fazem 73,4% mais por habitante que o SUS. Por região: Norte **435**, Sudeste 1.013. Menores taxas por UF: AP 246, TO 256, RO 397, AC 405, DF 413, AM 444, MA 453. **Em média, 96,9 cirurgias por oftalmologista por ano** (PI 180; DF 21,5).
- Referência internacional: EUA 1.172, Canadá 1.103 e Reino Unido 956 cirurgias de catarata por 100 mil por ano (mesmo informe).
- **Prevalência:** a PNS 2019 aponta **34,6% dos ≥60 anos com diagnóstico de catarata**, e 74,2% desses operaram [V, citado no informe]. A cobertura cirúrgica de catarata (CSC) é de **36,3% na Amazônia contra 57,8% em São Paulo** (*Seminars in Ophthalmology*, 2023) [S]. **Pterígio** em ribeirinhos do Solimões/Japurá: **21,2%** na população geral e **41,1% nos >18 anos** (*Rev Bras Oftalmol*, SciELO) [S].
- **Espera:** em 2024 eram mais de 4 meses de espera média até a cirurgia SUS, com 168,4 mil solicitações na fila (informe FMUSP). Em 2025 a fila declarada chegou a 208.294 (TCU, acima).
- **Exemplo verificado por nós, CNES PF do AM (competência 08/2026, CBO 225265)** [V, cálculo próprio]: 173 oftalmologistas distintos (pelo CNS) com 357 vínculos em **apenas 26 dos 62 municípios**. **160 dos 173 têm vínculo em Manaus**, só 13 atuam exclusivamente no interior, e 137 atendem SUS (PROF_SUS=1).
- **Deslocamento:** não achei estudo nacional de distância média para catarata [NV]. Como proxy, na alta complexidade cardiológica só 43% dos procedimentos acontecem no município de residência, e a distância média é de 59 ± 162 km (JAFF) [S]. **Isso dá para calcular direto do SIH/SIA, comparando o município de residência (MUNIC_RES) com o do estabelecimento (MUNIC_MOV)** (ver seção 3).

---

## 3. Dados públicos para a previsão (testados em 01/10/2026)

| Dado | Onde | Formato / acesso | Teste |
|---|---|---|---|
| **CNES Profissionais (PF)**: CBO 225265, CNES, município (CODUFMUN), região de saúde (REGSAUDE), carga horária (HORA_AMB/HOSP/OUTR), PROF_SUS | `ftp://ftp.datasus.gov.br/dissemin/publicos/CNES/200508_/Dados/PF/PF{UF}{AAMM}.dbc` | .dbc (DBF comprimido), mensal, sem login. Lê-se em Python com `datasus-dbc` + `dbfread`, ou com PySUS. No R, `read.dbc`/`microdatasus` | **OK**: PFAM2608.dbc (5,4 MB) baixado e decodificado. Última competência é 2608, publicada em 15/09/2026. O PFSP tem ~78 MB por mês |
| CNES Estabelecimentos (ST), Equipamentos (EQ: facoemulsificador, YAG, retinógrafo), Habilitações (HB) | mesmo FTP, subpastas ST/EQ/HB | .dbc | listagem acessível [V p/ PF; NV p/ EQ/HB] |
| **SIA/SUS** (PA: produção ambulatorial, com catarata ambulatorial e OCI) | `ftp://ftp.datasus.gov.br/dissemin/publicos/SIASUS/200801_/Dados/PA{UF}{AAMM}.dbc` | .dbc. Tem PA_UFMUN (estabelecimento) e PA_MUNPCN (residência) [NV nomes] | **OK**: PAAM2601–2603 listados (30–41 MB cada) |
| **SIH/SUS** (RD: AIH) | `ftp://ftp.datasus.gov.br/dissemin/publicos/SIHSUS/200801_/Dados/RD{UF}{AAMM}.dbc` | .dbc. MUNIC_RES × MUNIC_MOV permite calcular o fluxo e a distância | **OK**: RDAM até 2607 |
| Códigos SIGTAP de catarata | 04.05.05.037-2 facoemulsificação com LIO dobrável; 04.05.05.011-9 faco com LIO rígida; 04.05.05.009-7 facectomia com LIO; 04.05.05.010-0 facectomia sem LIO. **Pterígio**: 04.05.04.xxx [NV, conferir no SIGTAP]. YAG: capsulotomia [NV código] | http://sigtap.datasus.gov.br | [V para os 4 de catarata, via informe FMUSP] |
| **API Dados Abertos MS** (`apidadosabertos.saude.gov.br`, ex. `/cnes/estabelecimentos`) | REST/JSON, sem chave | **FALHOU**: "Network is unreachable / ECONNREFUSED 189.28.130.6:443" tanto via curl quanto via WebFetch. Parece haver bloqueio de rede ou geográfico fora do Brasil. **Retestar de um IP brasileiro** |
| ElastiCNES / OpenDataSUS (CKAN) | elasticnes.saude.gov.br; opendatasus.saude.gov.br | Painel / CSV | não testado [NV] |
| TabNet (CNES, SIA, SIH) | tabnet.datasus.gov.br | HTML/CSV via formulário; serve para validar números agregados | não testado |
| **IBGE população estimada por município** | `https://apisidra.ibge.gov.br/values/t/6579/n6/{cod}/v/all/p/last` | JSON, sem chave | **OK**: São José dos Campos tem 729.153 hab. (2026) |
| IBGE população por idade (Censo 2022) | SIDRA, tabela 9514 (sexo × idade × município) [NV número] | JSON | não testado |
| **Malha municipal GeoJSON** | `https://servicodados.ibge.gov.br/api/v3/malhas/estados/{UF}?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=minima` | GeoJSON | **OK**: SP com 310 KB |
| Regiões de saúde (CIR) | o campo REGSAUDE do CNES; shapefiles no DATASUS/TabWin; tabela de municípios × região no MS [NV URL] | | parcial |
| Distâncias e tempos entre municípios | IBGE *Ligações Rodoviárias e Hidroviárias 2016* (frequência, **tempo de viagem**, custo de passagem, ~65 mil ligações) e módulo da Plataforma Geográfica Interativa; REGIC 2018 (deslocamento para saúde de baixa/média e de alta complexidade) | XLS/ODS | [S] |
| Fila de catarata por UF | só nos anexos do TCU (filas declaradas) e em painéis estaduais; **não há API nacional** | PDF | [V] |

**Implicação para o app:** o pipeline realista para o MVP é FTP DATASUS + IBGE APIs, processado offline em lote mensal e salvo como Parquet/JSON no servidor do dashboard. A API REST do MS fica como opcional.

---

## 4. Métodos de previsão e alocação (literatura)

### 4.1 Demanda (camada epidemiológica + funil de triagem)
`Demanda_cirúrgica(m, t) = Σ_faixa Pop(m, faixa) × Prev(faixa, região) × (1 − CSC_atual) × p(aceita) × p(apto)`, que deve ser **calibrada com o funil observado pelo Guaraná**:
`Cirurgias_esperadas(m) = Triagens_positivas(m) × VPP_triagem × taxa_comparecimento_OCI × taxa_indicação × taxa_aceite`.
- Prevalência: PNS 2019 (34,6% dos ≥60 com catarata diagnosticada); CSC regional (36% na Amazônia); pterígio de 21–41% em ribeirinhos.
- Indicadores OMS: **CSR** (cirurgias por milhão por ano) e **eCSC** (cobertura cirúrgica efetiva). A meta da Assembleia Mundial da Saúde é **+30 pontos percentuais de eCSC até 2030**, medida por inquéritos RAAB (Lancet Glob Health 2022; IAPB Vision Atlas) [S].
- Estimador bayesiano em pequenas áreas: shrinkage da prevalência por microárea em direção à da UBS e do município, porque a amostra por microárea é pequena. Previsão temporal da fila com modelo de estoque e fluxo (entradas = positivos × conversão; saídas = capacidade).

### 4.2 Localização-alocação (onde pôr capacidade fixa)
- **p-mediana**: minimiza a soma de demanda × distância. **MCLP (máxima cobertura)**: maximiza a demanda coberta dentro de um tempo-limite, por exemplo 2 h de estrada ou 1 dia de barco. **LSCP (cobertura de conjuntos)**: número mínimo de pontos para cobrir 100%. Existem versões capacitadas e hierárquicas (MCLP/p-mediana hierárquico aplicado a maternidades na França, *J. Business Research* 2012). Há revisão de 2026 sobre otimização da acessibilidade geográfica em países em desenvolvimento (arXiv 2603.22113) [S].
- **Acessibilidade 2SFCA / E2SFCA** (two-step floating catchment area), para medir a oferta de oftalmologistas por habitante ponderada pela distância [NV ref. específica].

### 4.3 Unidades móveis e mutirões (onde e quando passar)
- **Periodic Location-Routing Problem** para serviços móveis rurais (*OR Spectrum* 2022, Springer). **Multi-depot time-constrained periodic VRP** para clínicas móveis (Witzenberg, África do Sul, PMC11706454: modelo em 3 estágios com roteamento, mochila para justiça entre clínicas e calendário mensal). Roteamento com ressuprimento sincronizado (arXiv 2412.17299). Tour multicritério de unidades móveis em país em desenvolvimento (*ResearchGate* 222662606) [S].
- Adaptação ao Guaraná: os nós são municípios ou polos de região de saúde. A **demanda é o backlog previsto de cirurgias**. Restrições: capacidade da carreta (~100 cirurgias/dia), permanência mínima de ~30–45 dias, sazonalidade dos rios (cheia e vazante) no AM/PA e janela de pós-operatório de 30 dias.
- **Filas**: modelo M/M/c ou fluido para estimar em quantas semanas a fila de cada região zera com c cirurgiões × produtividade. Referência de produtividade: 96,9 cirurgias por oftalmologista por ano (média do SUS + planos) e até 100 por dia por carreta.

---

## 5. Proposta para o dashboard do gestor

### 5.1 Decisões que o gestor precisa tomar
1. **Onde** pôr o próximo mutirão, a carreta ou o barco (município ou polo).
2. **Quando** fazê-lo (janela sazonal e capacidade da regulação de confirmar os pacientes).
3. **Quantos** oftalmologistas e dias de mutirão são necessários.
4. **Que tipo** de cirurgia ofertar: catarata (faco), pterígio, YAG, ou só OCI diagnóstica primeiro.
5. Quanto **ganha em espera e deslocamento** cada alternativa, comparada a mandar pacientes por TFD para o polo.

### 5.2 Métricas (por microárea, UBS, município e região de saúde)
| Métrica | Definição |
|---|---|
| Cobertura de triagem | pessoas triadas ≥50 anos / população ≥50 anos (IBGE) |
| Positividade por condição | % suspeita de catarata, pterígio ou outro |
| **Demanda cirúrgica estimada** | positivos × conversão do funil (§4.1), com IC 80% |
| Backlog estimado | demanda acumulada − cirurgias realizadas (SIA/SIH, por município de residência) |
| Oftalmologistas SUS por 100 mil | CNES PF, CBO 225265, PROF_SUS=1, em FTE (horas/40) |
| CSR local | cirurgias de catarata por 1 milhão por ano (SIA+SIH por residência) contra 8.687 nacional e 4.350 no Norte |
| Tempo ou distância ao serviço mais próximo | IBGE ligações rodo/hidroviárias e fluxos do SIH |
| % operados fora do município | SIH/SIA: MUNIC_RES ≠ MUNIC_MOV |
| **Dias de mutirão necessários** | backlog / (cirurgiões × cirurgias por dia) |
| **Oftalmologistas necessários** | demanda anual / ~97 cirurgias por oftalmologista por ano; para consultas, 4 FTE por 100 mil (Caderno 1) |
| Funil OCI | triado → regulado → OCI concluída em ≤60 d → cirurgia; perda em cada etapa |
| Tempo até a cirurgia | mediana e **P75** (o TCU alerta que a mediana esconde a cauda) |

### 5.3 Visualizações
- **Mapa coroplético** por município ou região de saúde (GeoJSON do IBGE) de demanda estimada, oferta e lacuna, com camada de pontos para as UBS e serviços habilitados. Em zoom, troca para **hexbin por microárea**.
- **Mapa de rotas candidatas** do mutirão (otimizador p-mediana/MCLP), com cobertura em isócronas, para o gestor comparar 2–3 cenários lado a lado.
- **Barra de lacuna** por região: demanda contra capacidade, ordenada.
- **Funil** triagem → OCI → cirurgia por município.
- **Projeção da fila** (linha com faixa de incerteza) para os cenários "sem ação", "1 carreta 45 d" e "2 oftalmologistas fixos".
- **Calendário/Gantt** de mutirões, com a sazonalidade dos rios e o pós-operatório.
- **Tabela de priorização** (ranking) com score = lacuna × vulnerabilidade × distância, exportável para CIR/CIB.
- Selo de **qualidade do dado** em cada número: triagem própria, CNES, SIA/SIH, fila declarada.

### 5.4 Ressalvas
- O CNES conta vínculos, não presença real: o mesmo oftalmologista aparece em vários municípios. Deduplicar por CNS e ponderar por horas.
- Mutirões podem não ser registrados no DATASUS (o próprio informe FMUSP faz essa ressalva). Use o SIA/SIH como piso da oferta.
- A triagem pelo ACS não é diagnóstico. A conversão de triagem positiva em cirurgia precisa ser **medida na validação** antes de ser usada na previsão.
- Dados do e-SUS identificados: agregar por microárea, com k-anonimato mínimo, antes de mostrar.

---

## Fontes principais
- FMUSP/AMB, Demografia Médica 2025, Informe nº 07 (ago/2025): https://fm.usp.br/fmusp/conteudo/radar_oftalmologistas_demografiamedica.pdf
- TCU, Acórdão 1.622/2026-Plenário (TC 015.703/2025-8): https://portal.tcu.gov.br/uploads/noticias/pdf/2026/06/24/documentos_-_2026-06-24T123648.987.pdf
- Portaria SAS 288/2008: https://bvsms.saude.gov.br/bvs/saudelegis/sas/2008/prt0288_19_05_2008.html
- Critérios e Parâmetros Assistenciais, Caderno 1 (2017): https://www.gov.br/saude/pt-br/acesso-a-informacao/gestao-do-sus/programacao-regulacao-controle-e-financiamento-da-mac/programacao-assistencial/arquivos/caderno-1-criterios-e-parametros-assistenciais-1-revisao.pdf
- Portaria SAES 1.826/2024 (OCI de oftalmologia): https://bvsms.saude.gov.br/bvs/saudelegis/Saes/2024/prt1826_12_06_2024.html
- Gomes et al., Saúde em Debate: https://revista.saudeemdebate.org.br/sed/article/view/10706
- Pterígio no Solimões/Japurá: https://www.scielo.br/j/rbof/a/V6Fxm6RTTBFtJfhyxJmqCZC/abstract/?lang=en
- TeleOftalmo: http://www.scielo.br/j/csp/a/DNvgnW6zGSLvHS5V5YqphJy/?lang=pt
- Opera+ Amazonas (SES-AM): https://www.saude.am.gov.br/governador-wilson-lima-da-inicio-ao-maior-mutirao-de-cirurgias-de-catarata-da-historia-do-amazonas-em-homenagem-aos-356-anos-de-manaus/
- Clínicas móveis (Witzenberg): https://pmc.ncbi.nlm.nih.gov/articles/PMC11706454/ ; PLRP: https://link.springer.com/article/10.1007/s00291-022-00670-3
- eCSC: https://pmc.ncbi.nlm.nih.gov/articles/PMC7618287/
- IBGE Ligações Rodoviárias e Hidroviárias: https://www.ibge.gov.br/geociencias/organizacao-do-territorio/redes-e-fluxos-geograficos/15794-rodoviarias-e-hidroviarias.html
