# Ocular.IA

Triagem de sinais no olho externo (córnea, esclera, conjuntiva, cristalino) a partir de foto comum de celular ou tablet, sem lente macro nem lâmpada de fenda. Cada sinal é uma pista de encaminhamento, nunca um diagnóstico.

Referência dos sinais: `Ocular_IA_Sinais_Oculares_de_Forma.pdf` (3 páginas, 10 sinais de forma, mais os 3 de cor da fase 1).

## Estrutura

```
contrato/resultado.schema.json   contrato JSON único: app, motor local e API produzem exatamente isso
dados/                           labels*.csv + imagens (NÃO versionar imagens de pessoas)
dados/labels.exemplo.csv         formato esperado pelo notebook
treino/ocular_treino.ipynb       notebook Colab: treino multirrótulo + limiares + export ONNX + model card
treino/build_notebook.py         gera o .ipynb (edite aqui, não no JSON)
treino/rotular_com_claude.py     rotula fotos novas com o Claude (visão + saída estruturada) para labels_claude.csv
guarana-app/                     app Android (Kotlin/Compose, ONNX Runtime, CameraX, anel de luz por BLE/Wi-Fi)
firmware/guarana_luz/            firmware ESP32 do anel de LEDs + simulador HTTP em firmware/mock/
saida/                           ocular_v1.onnx, ocular_v1_int8.onnx, model_card.json, ocular_v1.pt
```

## Arquitetura de análise (decisão de 29/09/2026)

Três camadas, mesma saída JSON (`contrato/resultado.schema.json`):

1. **Sempre local:** gate de qualidade e localização do olho.
2. **Local, provisório:** regras por região (cor) e/ou este modelo pequeno em ONNX Runtime. Saída com `engine = local-*`, `status = provisional`, `needs_cloud_review = true`.
3. **Nuvem, quando houver rede:** modelo de visão confirma ou descarta. Resultado substitui o local; divergências viram dados de calibração.

Regras fixas de segurança, em qualquer camada: `catarata_leucocoria` em criança e `lesao_pigmentada` sempre saem como `encaminhar` no mínimo.

## Pipeline (o que já foi rodado em 29/09/2026)

```
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r treino/requirements.txt "opencv-python-headless<5"
.venv/bin/python treino/baixar_datasets.py            # dados/raw/<fonte>/ (retomável; ~8 GB)
.venv/bin/python treino/preparar_dados.py             # dados/crops/<fonte>/ + dados/labels_<fonte>.csv
.venv/bin/python treino/treinar.py                    # saida/ocular_v1*.onnx + model_card.json (Mac: MPS)
OCULAR_SMOKE=1 .venv/bin/python treino/treinar.py     # teste do pipeline em 400 imagens, 1 época
.venv/bin/python treino/calibrar_palidez.py           # tenta a regra de cor para palidez (ver resultado abaixo)
```

`treino/treinar.py` é gerado a partir das células do notebook por `treino/build_notebook.py`; edite o builder, não o script. No Colab, use `treino/ocular_treino.ipynb` com os mesmos `dados/` no Drive em `MyDrive/guarana/`.

### O que os dados públicos renderam de fato

| Fonte | Recortes | Rótulos positivos | Domínio | Nota |
|---|---|---|---|---|
| CFD periorbital (Zenodo) | 1.654 | nenhum (negativos) | foto de rosto, recorte por olho via COCO | resolução baixa (~230 px) |
| Eye Conjunctiva Segmentation (Mendeley) | 547 | nenhum (negativos) | **celular, pálpebra puxada** | melhor domínio para o app; recorte pela máscara |
| HF Jaundice | 278 | ictericia 118 | web | faixa dos olhos por Haar; CC BY-NC |
| Mendeley Eye Diseases | ~720 | hiperemia ~410, catarata ~300 | web | pasta "Normal" são miniaturas de 41 a 74 px, descartadas; SMOTE excluído |
| Faridpur | 17 | pterigio 17 | câmera externa | só 17 originais de pterígio |
| SLID | 1.861 | pterigio/pinguécula 445, opacidade 569, lesão pigmentada 395, hiperemia 268, catarata 204, hemorragia 170 | **lâmpada de fenda** | única fonte de hemorragia e nevo; tumor/cisto/LIO excluídos |
| CP-AnemiC | 710 | Hb medida | recorte de conjuntiva em fundo branco | fora do CNN; usado só na calibração abaixo |
| Ghana IDA | 0 | | | a listagem da API não devolveu arquivos; redundante com CP-AnemiC |
| BR-Pterygium (Roboflow) | 0 | | | exige login para exportar: baixar manualmente em formato "folder" e rodar `rows_from_folders` |

Total no treino v1: cerca de 5.000 recortes, divididos por pessoa em 3.614 treino / 664 validação / 783 teste.

### Ramo A: reflectância multiespectral (documento "Embasamento científico")

Com o anel ligado, o **disparador** executa a sequência do documento: branco, azul, vermelho e ambiente (LEDs apagados), uma foto por passo. Depois do primeiro passo o app **trava exposição e balanço de branco** (Camera2 interop), então os quatro quadros têm a mesma exposição e o quadro ambiente pode ser subtraído. A foto salva é recortada igual ao preview (ViewPort), então a moldura oval da tela vale na imagem.

`core/color/Reflectance.kt` monta uma máscara de esclera no quadro branco (elipse central, pixels claros e pouco saturados, excluindo pele e íris), aplica a mesma máscara aos outros quadros e calcula, com o ambiente subtraído:

| Índice | Fórmula | Sentido |
|---|---|---|
| Icterícia | ln(R no quadro vermelho / B no quadro azul) | sobe com bilirrubina (absorção em ~460 nm) |
| Palidez | ln(R / G) no quadro branco | cai com menos hemoglobina |
| Hiperemia | R / (R+G+B) no quadro branco | sobe com vermelhidão |

Os valores aparecem no resultado com a máscara medida ("ROI esclera") e ficam no JSON da análise (`indices`). São **relativos ao anel e sem calibração**: só viram número clínico depois de uma curva contra hemograma e bilirrubina sérica, que é a coleta a fazer. A triagem continua vindo do modelo (Ramo B); o Ramo A é medição e evidência. O botão pequeno de câmera na captura tira uma foto única sem a sequência.

### Painel inicial (29/09/2026, noite)

Inspirado num dashboard de viagem (shot da Taqwah Agency no Dribbble), com a paleta do Guaraná: barra superior com logo, navegação em pílulas (ativa na cor da semente) e botões redondos; linha de busca de paciente e pílulas de contexto (unidade, visitas pendentes); em telas largas (tablet em paisagem, ≥ 840 dp) duas colunas: mapa do dia com o trajeto sugerido tracejado e barra flutuante, e à direita "Visitas de hoje" (coluna dia/data, iniciais, endereço, turno), "Resumo", "Análises · 14 dias" (barras, hoje em vermelho) e "Análises recentes". Em retrato, tudo empilha. Tipografia: Inter Tight nos títulos e números (identificação visual do shot, não declarada), Inter no corpo. `ui/HouseholdMap.kt` é o mapa reutilizado no painel e na tela cheia, com trajeto por vizinho mais próximo e download da área.

### Agenda, território e mapa offline (29/09/2026, noite)

- **Mock do SUS** em `dados/mock-sus/`: `gerar_mock_sus.py` produz `territorio.json` (o que o app importa) e `domicilios.csv`, `pessoas.csv`, `visitas.csv` no espírito de uma exportação do PEC: 24 domicílios com latitude/longitude em bairros de São José dos Campos, 70 pessoas com CNS (dígito verificador válido) e CPF válidos, condições autorreferidas, 24 visitas (ontem feitas, hoje e próximos dias planejadas). Tudo fictício. O JSON também vai nos assets do app como "Dados de demonstração".
- **Importação** (`core/Territory.kt`): Ajustes → Território → "Importar JSON" (arquivo) ou "Dados de demonstração". Pessoas viram pacientes com id derivado do CNS (reimportar não duplica); domicílios e visitas ficam em `files/territorio/`.
- **Agenda** (`ui/AgendaScreen.kt`): dias com contagem de pendentes, visitas com pessoa, endereço, turno, motivo e condições; ações Iniciar análise (seleciona o paciente e abre a captura), Feita, Adiar, Ausente, Recusada.
- **Mapa** (`ui/MapScreen.kt`, MapLibre): pinos dos domicílios do dia coloridos por estado, nome da pessoa, toque abre o cartão com "Iniciar análise", posição atual, e **"Baixar mapa desta área"** grava os tiles (zoom 10 a 16) para uso sem internet. Estilo aberto OpenFreeMap (dados OpenStreetMap), sem chave. Testado no tablet: download da área de SJC deu 18 MB.
- Ordem de rota por vizinho mais próximo está em `TerritoryStore.route`, ainda sem botão na tela.


### e-SUS Território como referência (29/09/2026, noite)

Telas reais do e-SUS Território (app oficial do ACS, dados sincronizados com o PEC) mostraram o modelo mental do agente: **bairro → logradouro (tipo + nome, contagem de imóveis) → imóvel (nº, complemento) → família (número, responsável) → cidadão**, com dois indicadores por imóvel ("Visitado há N dias" e "N condições a acompanhar"), idade em anos e meses, chips de condição vindos da Ficha de Cadastro Individual (FCI) e "condições extras" em texto livre (remédios, peso, altura, com erros de digitação). O cadastro é um wizard de 7 etapas que já existe no PEC: **não pedimos para o agente digitar de novo**, importamos.

O que mudou no Guaraná por causa disso:

- **Mock** (`dados/mock-sus/gerar_mock_sus.py`): `tipo_logradouro`, `ponto_referencia`, `telefone_contato`, `ultima_visita` e `familias[]` por domicílio; `familia_numero`, `responsavel_familiar`, `condicoes` no vocabulário da FCI ("Hipertensão arterial", "Diabetes", "AVC/derrame", "Acamado(a)", "Deficiência visual", "Hanseníase"…), `condicoes_extra` (texto livre com ruído real) e `ultimo_exame_fundo_olho` (campo de DW municipal, não da FCI; vazio = sem registro) por pessoa; motivos e desfechos de visita com o vocabulário da Ficha de Visita Domiciliar e Territorial ("Busca ativa: exame", "Acompanhamento: pessoa com diabetes", "Visita realizada", "Ausente"…). "Dados de demonstração" agora substitui o território anterior (UUIDs novos duplicariam imóveis).
- **Tela Território** (`ui/TerritoryScreen.kt`): navegação na hierarquia do e-SUS, busca por rua/número/bairro/pessoa, cartões de imóvel em grade com família, responsável e chips, ficha do domicílio (microárea, referência, telefones residencial/contato, CEP), famílias com responsável primeiro, idade em anos e meses, chips de condição, "Analisar olho" e "Visitar" (reaproveita a visita planejada de hoje ou cria uma "Busca ativa: exame") e histórico de visitas do imóvel. Pílula "Território" na barra do painel; em telefone as pílulas descem para uma linha rolável.
- **Prioridade ocular** (`core/OcularPriority.kt`): pontuação por pessoa a partir das condições da FCI e da idade (diabetes sem fundo de olho há >12 meses, deficiência visual, hanseníase, acamado/domiciliado, hipertensão, AVC, internação recente, histórico ocular nas condições extras, ≥60 anos, <6 anos). Ordena a agenda (prioridade, depois tempo sem visita) e aparece como chip no painel, na agenda, no mapa e no território. Regras provisórias, a validar com oftalmologista.
- **Triagem pela ficha** (`Triage.withHistory`, aplicada no `Pipeline` sobre o resultado local e o da nuvem): diabetes sem fundo de olho registrado nos últimos 12 meses → pelo menos "encaminhar" mesmo sem sinal na foto; deficiência visual ou hanseníase + qualquer sinal → encaminhar; hipertensão + hemorragia subconjuntival → observar com orientação de aferir a pressão. Os motivos vão em `triage_reasons` (contrato atualizado, opcional) e aparecem no resultado no cartão "Pela ficha do cidadão". Verificado de ponta a ponta no emulador: paciente diabética sem fundo de olho → "Encaminhar" com o motivo.
- **Build**: `armeabi-v7a` de volta nos `abiFilters` (tablets de entrada de 32 bits, que é onde o e-SUS Território roda; APK ~112 MB); câmera de foco fixo (`LENS_INFO_MINIMUM_FOCUS_DISTANCE` = 0) esconde o controle de foco manual e mostra "Foco fixo nesta câmera".

**Integração, decidido**: o PEC e o e-SUS Território não têm código-fonte publicado pelo Ministério (só projetos da comunidade e o Painel e-SUS APS da Fiocruz), então não dá para embutir uma "janela" dentro do app oficial. O caminho oficial é o **LEDI** (Layout e-SUS APS de Dados e Interface): fichas em Thrift enviadas ao PEC pelo endpoint REST `/api/v1/recebimento/ficha` (arquivo `.esus`), documentação em integracao.esusaps.bridge.ufsc.tech. Ou seja: app próprio, dados importados do PEC, resultado devolvido como ficha pelo LEDI e como registro FHIR na RNDS. No tablet, o que se aproxima de "embed" é tela dividida (Android multi-window) com o e-SUS Território de um lado, mais link profundo `guarana://cidadao/{cns}` para abrir a captura com a pessoa selecionada (ainda não implementado).


### Simulador do e-SUS Território (30/09/2026)

`esus-mock-app/` é um segundo app Android, **e-SUS Território (simulador)**, que reproduz as telas do app oficial do ACS com os mesmos dados fictícios do Guaraná (`mock_territorio.json` nos assets): login por CPF e senha (qualquer senha entra), menu lateral (Sincronizar, Inconsistências, Mapa, Cidadãos, Relatórios do território, Unificar/Editar logradouro, Ajuda, Sobre, Sair), lista de logradouros agrupada por bairro, lista de imóveis em grade com "Família N", responsável e chips "Visitado há N dias" / "N condições a acompanhar", informações do domicílio (microárea, referência, telefones residencial e contato, condições de moradia, famílias com responsável, VISITAR / VISITAR FAMÍLIA, ADICIONAR CIDADÃO), cadastro do cidadão em 7 etapas com os cartões Sim/Não/Limpar e as três "condições extras" em texto livre, e o formulário da visita com os grupos de motivo da Ficha de Visita Domiciliar e Territorial (Busca ativa, Acompanhamento, Controle ambiental…), antropometria e desfecho.

Serve para testar a integração pelo front: tudo o que o simulador grava (visitas, cadastros) vai para arquivos do app e para o logcat com a tag `ESUSMOCK` (`adb logcat -s ESUSMOCK`), então dá para conferir o que o Guaraná injetou. Os textos dos campos são os do app oficial, para que um assistente de preenchimento por acessibilidade testado aqui funcione lá com o mínimo de ajuste. Build: `cd esus-mock-app && ./gradlew assembleRelease`; APK em `~/Desktop/eSUS-simulador.apk`. Não é o aplicativo oficial e diz isso na tela de login e em Sobre.

**Injeção no e-SUS, caminho escolhido**: o Guaraná não lê a tela do e-SUS; ele escreve nela. No Android isso é um serviço de acessibilidade que, com o formulário de visita aberto, marca "Busca ativa: Exame" (e o acompanhamento correspondente, como "Pessoa com diabetes"), preenche o desfecho e, no cadastro, adiciona uma "condição extra" com o resumo da triagem. Alternativa sem permissão especial: botão "Copiar para o e-SUS" que põe o resumo na área de transferência para colar na condição extra. Os dois ainda não estão implementados no Guaraná; o simulador é o alvo de teste.


### Companheiro do e-SUS: pílula flutuante (30/09/2026)

`esus/EsusCompanionService.kt` é um serviço de acessibilidade do Guaraná. Quando o e-SUS Território (oficial `br.gov.saude.acs` ou o simulador `com.guarana.esusmock`) vem para a frente, ele desenha uma pílula vertical e discreta por cima do e-SUS, encostada na borda direita, com a fruta em cima e um botão redondo com um olho embaixo (cápsula creme translúcida de 40 dp de largura, como a do Granola), arrastável na vertical. O olho abre direto a análise; a fruta abre o Guaraná na tela inicial. Some quando o e-SUS sai da frente. Tocar abre o Guaraná direto na captura com o paciente atual; a tela de resultado ganha "Copiar resumo para o e-SUS" (texto curto para a condição extra do cadastro, com o motivo de visita correspondente) e "Voltar ao e-SUS", que traz o e-SUS de volta no estado em que estava.

- Sem permissão "exibir sobre outros apps": a janela é `TYPE_ACCESSIBILITY_OVERLAY`, que o próprio serviço pode criar. O manifesto declara `<queries>` para os dois pacotes do e-SUS, exigido pelo Android 11+ para abrir o app de volta.
- Privacidade: para decidir mostrar ou esconder, o serviço consulta só o pacote da janela de aplicativo ativa; teclado e janelas de sistema não mudam o estado (evita piscar). Nenhum conteúdo da tela do e-SUS é lido. Documentar no dossiê como "função de acessibilidade do fluxo de trabalho".
- Ativação: Ajustes → "Companheiro do e-SUS" → "Ativar na Acessibilidade" (Android → Acessibilidade → Guaraná · companheiro do e-SUS). Por adb: `settings put secure enabled_accessibility_services com.guarana.ocular/com.guarana.ocular.esus.EsusCompanionService` e `settings put secure accessibility_enabled 1`. Um `am force-stop` do Guaraná derruba o serviço; religue pelo Android ou repetindo o `settings put`.
- Verificado no emulador contra o simulador: pílula sobre a lista de logradouros e a ficha do domicílio → captura → rotina de luz (mock) → resultado → "Voltar ao e-SUS" traz o simulador de volta. Ativado também no tablet.
- Próximo passo: o mesmo serviço preenche o formulário de visita do e-SUS (marca "Busca ativa: Exame" e o acompanhamento, define o desfecho) e a condição extra, como ação explícita do agente. O simulador tem os mesmos textos de campo do app oficial para esse teste.


### Logo minimalista (30/09/2026)

A fruta virou três círculos concêntricos (cápsula vermelha, arilo claro, semente escura) e uma única folha, sem gradiente, brilho ou caule, nas proporções do logotipo da Apple: corpo grande centrado, folha pequena inclinada em cima, à direita do centro, conjunto mais alto que largo. Mesma geometria em `ui/Logo.kt` (Canvas, preenche a altura), `res/drawable/ic_launcher_foreground.xml` e `ic_launcher_mono.xml` (viewport 108, corpo em 54,61 com raios 22/12/7, folha de 56,38 a 69,24; tudo dentro da zona segura do ícone adaptativo, raio 33, senão o launcher corta). PNGs regenerados em `~/Desktop/guarana-logo*.png` e `guarana-icone-1024.png`. A pílula do e-SUS usa o mesmo vetor.


### Modelo v2, enquadramento, observabilidade e validação automática (30/09/2026, madrugada)

**Modelo `ocular_v2`** (`treino/treinar.py`, `saida/`): 15 rótulos em vez de 7. Novos: `pterigio` e `pinguecula` separados, `tumor_superficie_ocular`, `ceratite`, `cisto_conjuntival`, `lente_intraocular`, `conjuntivite`, `uveite`, `alteracao_palpebral`. Vieram das lesões do SLID que estavam excluídas (tumor 537, cisto 134, LIO 119, ceratite 270) e das pastas do `eye_diseases` (Conjunctivitis 714, Uveitis 446, Eyelid 1050). Treino 4373 · val 782 · teste 927 imagens, separadas por sujeito. Teste (mesma ressalva de sempre: domínios lâmpada de fenda e web, quase nada de foto de celular):

| sinal | n pos | AUROC | limiar | sens | esp |
|---|---:|---:|---:|---:|---:|
| hiperemia | 109 | 0.991 | 0.75 | 0.87 | 1.00 |
| ictericia | 12 | 0.998 | 0.02 | 1.00 | 0.97 |
| pterigio | 21 | 0.979 | 0.40 | 0.81 | 0.99 |
| pinguecula | 67 | 0.955 | 0.34 | 0.81 | 0.93 |
| catarata_leucocoria | 87 | 0.992 | 0.80 | 0.84 | 0.99 |
| hemorragia_subconjuntival | 19 | 0.949 | 0.13 | 0.84 | 0.97 |
| lesao_pigmentada | 61 | 0.986 | 0.82 | 0.84 | 0.95 |
| opacidade_corneana | 95 | 0.999 | 0.95 | 0.91 | 1.00 |
| tumor_superficie_ocular | 75 | 0.992 | 0.32 | 0.91 | 0.97 |
| ceratite | 35 | 1.000 | 0.87 | 1.00 | 1.00 |
| cisto_conjuntival | 13 | 0.978 | 0.97 | 0.54 | 1.00 |
| lente_intraocular | 26 | 0.995 | 0.48 | 0.96 | 1.00 |
| conjuntivite | 34 | 0.999 | 0.58 | 0.85 | 1.00 |
| uveite | 25 | 0.995 | 0.98 | 0.80 | 0.99 |
| alteracao_palpebral | 39 | 0.999 | 0.39 | 0.95 | 1.00 |

Triagem: `ceratite` e `uveite` → encaminhar urgente; `pterigio`, `tumor_superficie_ocular` → encaminhar; `pinguecula`, `conjuntivite`, `cisto_conjuntival`, `alteracao_palpebral` → observar; `lente_intraocular` é só contexto. A `ictericia` ficou com limiar 0,02 (12 positivos na validação): sensível, mas com falsos positivos; precisa de mais fotos de icterícia em celular.

**Observabilidade (o que fez o modelo dar aquela confiança).** O ONNX v2 tem uma segunda saída `cam` [1, 15, 10, 10]: a cabeça do classificador (conv 1×1 + hardswish + linear) aplicada a cada célula do mapa de características, como se aquela célula fosse o vetor agregado. É o logit local por rótulo, custo zero, sem gradiente. No resultado: mapa de ativação sobre a foto (vermelho onde o sinal foi visto; a moldura branca é o recorte central que o modelo viu), trocável tocando no sinal; barra de probabilidade com o traço do limiar em cada sinal; cartão "Observabilidade" com modelo, tempo de inferência, nitidez, luminância, enquadramento e confiança do detector, e o pré-processamento por extenso. Tudo fica no JSON da análise (`explain`, `explain_shape`, `inference_ms`, `framing`, `quality.metrics`).

**Enquadramento (um olho, perto, centralizado).** Um blob escuro como heurística não passou de 40% de acerto (`treino/avaliar_enquadramento.py` mede isso). Entrou um detector treinado por síntese (`treino/treinar_enquadramento.py`): do círculo da íris anotado no SLID (1.388 fotos) e das caixas de íris das faixas do CFD (827) geramos janelas nas seis classes OK, TOO_FAR, TOO_CLOSE, TWO_EYES, OFF_CENTER, NOT_FOUND. MobileNetV3-small, 160 px, escala de cinza (o app usa o canal Y do preview), 6 MB. Validação sintética por sujeito: acurácia 0.88; em recortes reais, CFD 100% OK, conjuntiva 94% OK, SLID cai em TOO_CLOSE (é close-up extremo) e 26% NOT_FOUND, que é o ponto fraco. Por isso a política: **recusa a foto** só em TOO_FAR, TWO_EYES e NOT_FOUND ("Aproxime-se do olho", "Fotografe um olho de cada vez", "Não encontrei o olho"); descentralizado e perto demais só avisam. Na captura a dica aparece ao vivo (anel verde/âmbar/vermelho) e, ao disparar, a foto recusada volta para a câmera com o motivo. Ajustes → "Enquadramento do olho" desliga a recusa para testes.

**Validação sem tirar foto.**
- `treino/avaliar.py`: roda o ONNX exportado (não o torch) sobre o split de teste com o mesmo pré-processamento do app, confere paridade torch/onnx (1,7e-5), métricas por sinal e por domínio, concordância da triagem com a esperada pelos rótulos (88%) e a distribuição do enquadramento. Sai `saida/avaliacao_ocular_v2.md/.json`.
- `treino/gerar_conjunto_validacao.py`: monta `validacao/conjunto/` com imagens do teste mais faixas de dois olhos e um `manifest.csv` (file;labels;triage;framing).
- **No aparelho**, Ajustes → "Validação automática": escolhe a pasta (SAF, permissão persistida), roda o caminho real (qualidade, enquadramento, modelo, triagem) sobre todas as imagens e grava `Downloads/guarana-validacao/validacao_<data>.md/.json` (`adb pull`) e um relatório compartilhável. Nada entra no histórico. Primeira rodada no emulador: 70 imagens, 26 ms por imagem.

**Status do auto-preenchimento do e-SUS**: implementado no `EsusCompanionService` (abre VISITAR da pessoa, marca "Busca ativa: Exame" e o acompanhamento, define o desfecho, deixa FINALIZAR para o agente), mas a busca por texto `findAccessibilityNodeInfosByText` não é implementada por apps Compose, então falha contra o simulador; falta trocar por percurso da árvore de nós. Interrompido a pedido para priorizar o modelo.

**Anotações verbosas com Claude** (`treino/rotular_com_claude.py`): ideia acolhida para rótulos mais finos e explicação por casos semelhantes; precisa de `ANTHROPIC_API_KEY` no ambiente, que não está.


### Pterígio errado → modelo v2.1, vistas múltiplas e explicação para o agente (30/09/2026, madrugada)

Uma foto óbvia de pterígio (`validacao/casos/pterigio_usuario_01.jpg`, 271×169 px) deu pterígio 0,04 na v2. Diagnóstico reproduzido no Mac com o mesmo ONNX: (1) o recorte central do pré-processamento jogava fora 22% de cada lado da foto, justamente a asa do pterígio; um recorte pela direita já dava 0,38; (2) o rótulo tinha 17 fotos comuns de treino contra 164 de lâmpada de fenda. O erro não era um caso isolado: era o domínio.

O que mudou:
- **Dados**: `mostafasmart/pterygium2class` do Hugging Face, 622 fotos de pterígio e 598 sem, todas em foto comum (celular/web), agora fonte `hf_pterygium` em `treino/preparar_dados.py`. Pterígio passou de 17 para 425 positivos de treino em foto comum.
- **Vistas múltiplas** (app e avaliação): em vez de um recorte central, o app roda o modelo em até seis vistas no zoom do treino (centro, laterais ou topo/base, cada uma espelhada) e usa o máximo por rótulo; o mapa de ativação e a caixa vêm da vista vencedora (`explain_boxes`). Os limiares são escolhidos na validação com as mesmas vistas, senão os falsos positivos disparam (medido: triagem caiu de 88% para 85% com vistas e limiares antigos).
- **Limiares** com piso 0,08 e teto 0,90: com poucos positivos o limiar para sensibilidade 0,90 ia a 0,02 (icterícia) e, com separação muito boa, a 0,98 (pterígio), frágil em caso real menos óbvio.
- **Aumento** de recorte mais forte no treino (escala 0,45 a 1, proporção 0,8 a 1,25) para lesão de borda aparecer em mais posições.
- **Confiabilidade por domínio** (`treino/marcar_confiabilidade.py`): o cartão do modelo passou a registrar, por rótulo, quantos positivos de treino vieram de foto comum e quantos de lâmpada de fenda. Rótulos com menos de 40 positivos em foto comum entram em `unreliable_labels` e o app escreve "ainda pouco testado em foto de celular" ao lado deles. Hoje são oito: ceratite, cisto_conjuntival, hemorragia_subconjuntival, lente_intraocular, lesao_pigmentada, opacidade_corneana, pinguecula, tumor_superficie_ocular. É a resposta honesta ao "um tanto dando errado": o desempenho medido desses vale para consultório, não para a câmera do tablet, até termos fotos reais.
- **Caso real como regressão**: `validacao/casos/` com `manifest.csv`; `treino/avaliar.py` imprime por caso a probabilidade do rótulo esperado, o limiar e se passou. A foto do usuário: pterígio 1,00 com limiar 0,90, nenhum outro rótulo acima do limiar.
- **Publicação num comando**: `treino/publicar_modelo.sh ocular_v21` marca confiabilidade, avalia (vistas + casos), regenera `validacao/conjunto/`, troca os assets e compila.

Teste v2.1 com vistas (1.095 imagens, separadas por sujeito; a última coluna diz se há base em foto comum):

| sinal | n pos | AUROC | limiar | sens | esp | foto comum? |
|---|---:|---:|---:|---:|---:|---|
| hiperemia | 110 | 0.993 | 0.90 | 0.94 | 0.98 | sim |
| ictericia | 16 | 0.999 | 0.69 | 0.94 | 0.99 | sim |
| pterigio | 110 | 0.993 | 0.90 | 0.95 | 0.98 | sim |
| pinguecula | 71 | 0.977 | 0.76 | 0.90 | 0.94 | não |
| catarata_leucocoria | 84 | 0.992 | 0.80 | 0.89 | 0.98 | sim |
| hemorragia_subconjuntival | 29 | 0.993 | 0.90 | 0.97 | 0.99 | não |
| lesao_pigmentada | 53 | 0.987 | 0.77 | 0.87 | 0.96 | não |
| opacidade_corneana | 89 | 0.998 | 0.90 | 0.98 | 0.99 | não |
| tumor_superficie_ocular | 69 | 0.995 | 0.90 | 0.93 | 0.98 | não |
| ceratite | 35 | 0.997 | 0.90 | 0.94 | 0.99 | não |
| cisto_conjuntival | 10 | 0.998 | 0.90 | 0.90 | 0.99 | não |
| lente_intraocular | 23 | 0.949 | 0.90 | 0.87 | 1.00 | não |
| conjuntivite | 39 | 0.982 | 0.69 | 0.90 | 1.00 | sim |
| uveite | 22 | 0.998 | 0.90 | 0.95 | 0.99 | sim |
| alteracao_palpebral | 41 | 0.999 | 0.90 | 0.93 | 1.00 | sim |

Triagem: 87% de concordância com a esperada pelos rótulos. Positivos de treino em foto comum por rótulo: hiperemia 298, ictericia 90, pterigio 425, pinguecula 0, catarata_leucocoria 220, hemorragia_subconjuntival 0, lesao_pigmentada 0, opacidade_corneana 0, tumor_superficie_ocular 0, ceratite 0, cisto_conjuntival 0, lente_intraocular 0, conjuntivite 181, uveite 117, alteracao_palpebral 210.

**Explicação para o agente.** O cartão "Observabilidade" com variância do laplaciano foi trocado por três blocos em linguagem comum: "Por que o aplicativo disse isso" (uma frase por sinal: o que viu, em que parte do olho, onde na foto, com que confiança), "A foto estava boa?" (nítida, luz, enquadramento, com o que fazer na próxima) e "Como funciona" em três linhas. Os números (modelo, tempo, nitidez, luminância, confiança do detector, pré-processamento, evidência por rótulo) ficaram atrás do ícone "Detalhes técnicos", fechado por padrão, para a equipe e o dossiê.

Fontes abertas verificadas e descartadas para foto de celular: os demais conjuntos "eye disease" do Hugging Face (`kazuhasasd/eye_disease`, `smrndmdude/eye-diseases-dataset`, `rksys/EYE_DISEASE_CLASSIFICATION`) são de fundo de olho. O caminho para os oito rótulos sem base em foto comum é coletar fotos reais e rotular, com Claude (`treino/rotular_com_claude.py`, precisa de chave) ou com oftalmologista.


### Pesquisa em massa de dados e primeira validação do ramo de cor (30/09/2026, madrugada)

- **Catálogo** em `dados/CATALOGO_FONTES.md` (o que existe, para que serve, como se acessa) e **visão por doença** em `dados/DOENCAS_E_DADOS.md` (epidemiologia brasileira com fontes, se o sinal aparece na foto de olho externo, rótulo no app, positivos por domínio, fonte para crescer, lacunas).
- **NeoJaundice** (HF `Gamma-Fest-2026/jaundice-neojaundice`): 2.235 fotos de pele de 745 recém-nascidos por smartphone, cada uma com bilirrubina sérica e um cartão de cor na cena. `treino/calibrar_ictericia.py` mede o índice do PDF contra o padrão-ouro, com validação cruzada por paciente:

| índice | calibração pelo branco do cartão | Spearman | AUROC bilirrubina ≥ 12 mg/dL | MAE (mg/dL) |
|---|---|---:|---:|---:|
| fração de azul B/(R+G+B) | sim | −0,76 | 0,89 | 2,6 |
| ln(R/B) (o do PDF) | sim | 0,73 | 0,88 | 2,8 |
| fração de azul | não | −0,69 | 0,85 | 3,0 |
| ln(R/B) | não | 0,65 | 0,83 | 3,2 |
| ln(R/G) (palidez) | sim | 0,19 | 0,62 | 4,2 |

  Leitura: o princípio físico do ramo A se sustenta com laboratório (é pele de recém-nascido, não esclera, mas o cromóforo é o mesmo), e a **calibração por referência branca vale ~0,09 de correlação e 0,04 de AUROC**. Isso é o argumento para o cartão/branco de referência no anel de LEDs. O índice de palidez não responde a bilirrubina, como esperado (controle negativo).
- **anemia-eyes** (HF `Yahaira/anemia-eyes`, 218 fotos de conjuntiva com pálpebra puxada, dispositivo padronizando a luz; é o Eyes-Defy-Anemia sem a hemoglobina, que fica na versão do IEEE DataPort) e **Anemia-seg** (411 fotos com polígonos da conjuntiva) baixados para o ramo de palidez.
- **PubMed Central** via `FreedomIntelligence/PubMedVision`: busca por termo de legenda no datasets-server (`treino/minerar_pubmed.py`), índice dos 20 zips (1,0 milhão de figuras) e leitura só das figuras candidatas por HTTP Range (`treino/baixar_pubmed.py`), separação de painéis e gate do detector de enquadramento (`treino/preparar_pubmed.py`). As etiquetas da base são imperfeitas (fotos clínicas aparecem como "Endoscopy"); o rendimento real é de dezenas de fotos por sinal, com a legenda do médico como anotação verbosa.
- **Reflexo de flash**: o gate de qualidade mede a fração de pixels estourados; com reflexo forte no quadro com luz e quadro sem luz limpo, a análise usa o sem luz e avisa em linguagem simples. Motivado por uma foto tirada da tela do Mac com o flash da rotina.
- Fontes que dependem de credencial do usuário: Kaggle (catarata em foto comum), Roboflow (pterígio, vermelhidão, conjuntivite, ceratite), IEEE DataPort (Eyes-Defy-Anemia com Hb).


### Teste "fonte de fora": o que a lâmpada de fenda ensina NÃO transfere para a foto de celular (30/09/2026)

`OCULAR_EXCLUDE_SOURCES=hf_pterygium .venv/bin/python treino/treinar.py` treina o v2.1 sem a única fonte de pterígio em foto comum (HF, 622 positivos + 598 normais de celular) e depois a usa inteira como teste externo. O modelo que fica tem 138 pterígios de treino, quase todos de lâmpada de fenda, e vai a 0,97 de AUROC no pterígio de lâmpada de fenda do teste interno.

| conjunto | n | AUROC pterígio | sens (limiar 0,90) |
|---|---:|---:|---:|
| teste interno (lâmpada de fenda) | 388 | 0,97 | – |
| **teste externo: fotos de celular nunca vistas (HF)** | 1106 (554 pos) | **0,47** | **0,00** |

AUROC 0,47 é pior que moeda: o modelo ranqueia pterígio em celular abaixo de olho normal em celular. Não é "um pouco de perda de domínio"; é que o sinal aprendido na lâmpada de fenda não existe na foto comum. Isso responde à pergunta de por que o pterígio do usuário deu negativo antes do v2.1 e vale para os oito rótulos que hoje só têm positivos de lâmpada de fenda (`unreliable_labels` do cartão: ceratite, cisto, hemorragia, LIO, lesão pigmentada, opacidade corneana, pinguécula, tumor): **até chegar foto comum deles, o número do teste interno não diz nada sobre o campo**. É por isso que o app já os mostra como "sem validação em foto comum", e é a régua para qualquer fonte nova: entra como teste externo antes de entrar no treino.

Artefatos: `saida/ocular_v21_sem_hf_pterygium.*` (modelo, cartão, split, predições); o `ocular_v21` de produção não foi tocado (mesmo md5 do asset do app). Log em `dados/train_loso_pterigio.log`.

### PubMed como teste externo: o 0,99 interno não mede o campo (30/09/2026)

`treino/minerar_pubmed.py` (busca por legenda no PubMedVision, 49 termos) → 640 figuras / 727 imagens; `treino/baixar_pubmed.py` (Range HTTP paralelo, 5 min) → `treino/preparar_pubmed.py` (separa painéis, gate de enquadramento) → 657 recortes de 399 figuras, rótulo pela legenda, `dados/labels_pubmed.csv`. Limpeza por legenda (animal, fundo de olho, microscopia, cirurgia) e enquadramento OK/descentralizado → `dados/labels_pubmed_limpo.csv`, 277 recortes de 204 figuras. `treino/testar_externo.py` roda o `ocular_v21.onnx` com as vistas do app sobre isso:

| sinal | n pos | AUROC interno (TTA) | AUROC externo | sens externa (limiar do app) |
|---|---:|---:|---:|---:|
| hiperemia | 45 | 0,99 | 0,70 | 0,47 |
| conjuntivite | 23 | 0,98 | 0,61 | 0,30 |
| catarata / leucocoria | 32 | 0,99 | 0,58 | 0,09 |
| ceratite | 40 | 1,00 | 0,64 | 0,07 |
| uveíte | 19 | 1,00 | 0,50 | 0,05 |
| pálpebra | 86 | 1,00 | 0,51 | 0,01 |
| pterígio | 15 | 0,99 | 0,67 | 0,07 |

43% dos recortes com algum sinal na legenda sairiam "sem sinais" no app; icterícia dispara em 13% dos recortes sem icterícia. O rótulo é ruidoso (é da figura inteira: olho contralateral normal e pós-operatório herdam o rótulo; a legenda chama de uveíte o que o modelo, com razão, chama de ceratite), então os números são um piso, não a verdade. Mas a queda é a mesma lição do pterígio: **cada fonte nova é um teste externo antes de ser treino**. Quadro completo por sinal em `dados/QUADRO_POR_SINAL.md`; artefatos em `saida/teste_externo_ocular_v21_labels_pubmed*.{md,json}` e `saida/pred_ocular_v21_externo_*.csv`. Folhas de contato dos recortes mostraram o que o gate deixa passar: olho de cavalo, cachorro e rato, fundo de olho, macro de lâmpada de fenda e campo cirúrgico; o filtro por legenda tira a maior parte, e o gate de enquadramento precisa de uma classe "não é olho humano" na próxima versão.

### Segundo teste externo (Wikimedia Commons) e o que a recalibração de limiar NÃO resolve (30/09/2026, tarde)

`treino/minerar_commons.py` baixa as categorias do Commons por sinal (licença e autor guardados por arquivo) mais 462 close-ups de olho normal; `treino/preparar_commons.py` recorta e passa pelo gate → 686 recortes, 433 normais. É um teste externo mais limpo que o PubMed (tem negativos de verdade). O v2.1 nele:

| sinal | n pos | AUROC | sens (limiar do app) |
|---|---:|---:|---:|
| pterígio | 7 | 0,90 | 0,43 |
| icterícia | 12 | 0,85 | 0,67 |
| hiperemia | 66 | 0,82 | 0,48 |
| ceratite | 16 | 0,82 | 0,12 |
| conjuntivite | 53 | 0,80 | 0,30 |
| catarata | 39 | 0,75 | 0,38 |
| pálpebra | 58 | 0,65 | 0,03 |
| uveíte | 11 | **0,19** | 0,09 |

Ranqueia razoavelmente (0,75–0,90) onde há mais de uma fonte no treino; uveíte (1 fonte) ranqueia ao contrário. Recalibrar os limiares em metade do Commons e testar na outra metade não salva: para chegar a 75% de sensibilidade os limiares caem ao piso (0,10) e 91% dos olhos normais disparam alarme (`saida/limiares_externos_commonsA.json`). Não é limiar, é separação. Os dois CSVs externos agora rodam automaticamente no fim de `treino/treinar.py` (`OCULAR_EXTERNAL_CSVS`) e nunca entram no treino.

### Dados sintéticos no Blender (30/09/2026, tarde)

`sintese/olho.py` (Blender 5.2 headless, EEVEE, ~1–3 s por imagem): olho paramétrico com globo, abertura corneana, córnea transparente com brilho de Fresnel, íris com textura CC0 ou procedural, pupila variável, pálpebras com fenda elíptica, prega e cílios, pele com textura CC0 e tons de Fitzpatrick I–VI, HDRIs CC0 do Poly Haven, flash opcional, câmera com enquadramento de celular (fenda ocupa 50–90% do quadro). Sinais gerados com rótulo automático: hiperemia (vasos radiais + tinta), conjuntivite, icterícia, pterígio (asa carnosa em coordenadas esféricas invadindo a córnea), pinguécula, hemorragia subconjuntival, catarata/leucocoria, opacidade corneana, ceratite (opacidade + injeção ciliar), uveíte (injeção ciliar + miose + hipópio), calázio/ptose, lesão pigmentada. `sintese/render/lote1/` = 1.600 imagens (4 sementes); `treino/preparar_sintese.py` junta em `dados/labels_sintese.csv`; entra no treino só com `OCULAR_USE_SINTESE=1`. Realismo ainda de desenho (vasos, pele lisa); vale como fonte de randomização, e o juiz é o teste externo, não o olho humano. Iterações do mostruário: `blender -b -P sintese/olho.py -- --mostruario --out sintese/render/v1 --seed N`.

Experimentos em fila (todos medidos nos dois testes externos): E2 = aumento forte + amostragem balanceada por fonte (`OCULAR_AUG=forte OCULAR_BALANCE_SOURCE=1`); E1 = E2 + síntese; E3 = codificador congelado (DINOv2/SigLIP) com sonda linear.

### Síntese v3: cabeça MPFB + globo com sinais (30/09/2026, fim da tarde)

O agente de pesquisa instalou o MPFB 2 (MakeHuman Plugin for Blender, malha e assets CC0) e provou o pipeline headless (`sintese/scripts/mpfb_closeup.py`, `sintese/PESQUISA.md`). `sintese/olho_mpfb.py` junta as duas partes: cabeça MPFB com macros sorteados (idade, sexo, ancestralidade, pele CC0 com SSS, cílios, sobrancelhas) e, no olho direito, o globo paramétrico de `sintese/olho.py` (`build_eye`) com os sinais, ajustado ao globo do MPFB por ajuste de esfera (mínimos quadrados com refino; o olho do MPFB tem raio 15,3 mm). Câmera física de celular (sensor 7 mm, lente 7–11 mm, f/1,7–2,4, 3,5–7,5 cm, foco na córnea), HDRI Poly Haven, flash coaxial opcional, balanço de branco sorteado, Cycles em Metal (~6–13 s por imagem, humano novo a cada 6 imagens). Mostruário: `sintese/render/mpfb_v1/`. Lote em curso: `sintese/render/mpfb1/` (2 × 500). O lote da v2 (olho em plano) foi interrompido com 669 imagens, rotuladas pelo nome do arquivo em `dados/labels_sintese_v2.csv`.

Limites conhecidos da v3: calázio e ptose ainda não são modelados na pálpebra do MPFB (o rótulo `alteracao_palpebral` fica fora da síntese por enquanto); vasos ainda esparsos; o olho esquerdo é o do MPFB (sem sinal). A literatura reunida em `sintese/assets/refs/LITERATURA_sim2real.md` diz: misturar ~1:1 com real, variar textura mais que fotorrealismo, não passar de 2:1 sintético:real.

### Fontes novas do grupo A (30/09/2026) e como entram

`dados/pesquisa/fontes_grupo_A.md` tem a tabela completa. O que baixou sem credencial: `mendeley_conj_lesoes` (pterígio 75, nevo 86, melanoma 139, melanose 10, normal 96; CC BY-NC), `mendeley_blefarite` (64 + 64 normais; CC BY), `zenodo_eyearea_tr` (1.980 fotos de celular de olho normal, 96 pessoas, 3–64 anos; CC BY), `hf_pinkeye` (conjuntivite viral/bacteriana 5.810, alérgica 1.633, normal 2.826; licença não declarada e ~15% é `eye_diseases` reaumentado), `mendeley_tiroide` (29 proptoses), `hf_eyes_det_roboflow` (3.104 rostos com caixa de olho, CC BY), espelho parcial do Eyes-Defy sem Hb. Icterícia adulta NÃO ganhou fonte (o "novo" era cópia byte a byte). Bloqueado por credencial/rede: tracoma do Figshare (1.546 pálpebras evertidas), 300 RN com bilirrubina no Mendeley, pálpebras do Synapse (ptose/entrópio/triquíase), Kaggle, Roboflow, IEEE.

Regra aplicada: tudo isso entra primeiro como **teste externo** em `dados/externos/labels_*.csv` (`treino/preparar_novas_fontes.py`: gate de enquadramento, desduplicação do pinkeye contra `eye_diseases` por md5 e dHash ≤ 6, amostra de 500 normais do Zenodo). O treino só lê `dados/labels*.csv`, então nada disso vaza para o treino até ser promovido de propósito.

### Meta declarada e protocolo de medição (30/09/2026, tarde)

Meta do projeto a partir de agora: **foto aleatória de doença ocular tirada da internet → ≥ 90% de acerto**. A régua já existe: os testes externos são exatamente fotos aleatórias da internet. Para não contaminar a régua ao usar essas fontes como matéria-prima, toda fonte externa ganhou a coluna `metade` (hash do sujeito): **A** pode virar treino (direto, embrulho ou colagem), **B** é teste para sempre. `treino/treinar.py` e `treino/testar_externo.py` só medem na B; `sintese/preparar_embrulho.py` e `treino/colar_lesoes.py` só consomem a A.

### Ferramentas de "embrulhar foto real" (30/09/2026, tarde)

1. **Segmentador de fenda e íris** (`treino/preparar_periorbital.py` + `treino/treinar_segmentador.py` → `saida/fenda_v1.onnx`): MobileNetV3-small + decodificador leve, 256 px, 2 canais. Dados reais: periorbital CFD (1.654 olhos com polígonos de esclera/íris/pupila) e CelebA (2.015 faixas com mapas de rótulo, entram na v2), mais as máscaras sintéticas do MPFB. IoU na validação: fenda 0,915, íris 0,938. Em close-up real funciona (Zenodo, Commons, pinkeye); falha em macro extremo (íris ocupando o quadro) e em imagens que não são olho, por isso os consumidores filtram por plausibilidade (raio da íris entre 6% e 40% do lado, fenda entre 1,5× e 8× a íris, íris dentro da fenda).
2. **Embrulho** (`sintese/embrulhar.py`): projeta a foto real ao longo do eixo óptico no globo (r 12 mm, córnea transparente com brilho de Fresnel) e num retalho de pele com perfil de órbita rasa, recorta a fenda pela máscara da própria foto (escala 2r px = 12 mm), estende o retalho além da foto com a cor média da borda, e refotografa: ângulo até ±28°, rolagem ±15°, lente escolhida para o quadro cobrir 60–95% da largura da foto, HDRI misturado a luz uniforme, flash coaxial em 40%. `sintese/preparar_embrulho.py` gera os trabalhos (segmentação + plausibilidade, metade A) e `sintese/embrulhar_lote.sh` renderiza 6 vistas por foto. Primeiro lote: 156 fotos.
3. **Colagem de lesão real** (`treino/colar_lesoes.py`): segmenta fonte e alvo, isola a lesão por regra de cor dentro da esclera (hemorragia: vermelho saturado; pterígio: tecido rosado até 3 raios do centro, pode invadir a borda da íris; lesão pigmentada: escura; pinguécula: amarela), transporta alinhando pelas íris (escala, translação, espelho em 50%), ajusta a cor pela esclera do alvo e funde com borda suave; icterícia e conjuntivite são transferência de cor da esclera. Alvos: os 1.980 olhos normais de celular do Zenodo (metade A). Saída `dados/labels_colagem.csv`.
4. **MPFB com máscaras** (`sintese/olho_mpfb.py`): cada render sai com `_mask.png` (R esclera, G íris/córnea, B asa de pterígio) por material de sobreposição indexado por objeto, e o `labels.csv` é incremental.

Lição de máquina: Cycles (Metal) e treino em MPS ao mesmo tempo travam o treino; a GPU tem uma fila (`dados/fila_gpu.sh`): E2 → embrulho → E3 (DINOv2) → E1 (treino com fontes geradas) → lote MPFB.

### Resultados E2 e E3 (30/09/2026, tarde)

| experimento | PubMed limpo AUROC médio | Commons AUROC médio | positivos perdidos (PubMed / Commons) |
|---|---:|---:|---|
| v2.1 (referência) | 0,62 | 0,71 | 43% / 43% |
| E2: aumento forte + balanceamento por fonte | 0,65 | 0,73 | 39% / 35% (mas 41–43% dos normais alarmam) |
| E3: DINOv2 ViT-S/14 congelado + regressão logística | 0,64 | 0,66 | – |

E2 ajuda pouco e troca especificidade por sensibilidade; E3 (codificador congelado) fica abaixo do ajuste fino. Nenhum dos dois é a alavanca: confirma que o gargalo é fonte, não treino. Números por sinal em `saida/externo_ocular_v21_e2_augbal.json` e `saida/sonda_vit_small_patch14_dinov2_lvd142m.md`.

### Estado do embrulho e da colagem (30/09/2026, fim da tarde)

- **Segmentador v2** (CFD + CelebA + MPFB, zoom até íris em 80% do quadro): passou a segmentar as fotos macro de pterígio do Mendeley, que a v1 não pegava. IoU de validação 0,86/0,87 (validação mais difícil que a v1).
- **Embrulho**: dois bugs graves corrigidos (o tamanho do retalho de pele estava em mm tratados como metros, e o reflexo da córnea vinha do mundo inteiro; agora só do flash, via Light Path). Com máscara boa (olho vermelho, close-up comum) as vistas ficam plausíveis; com máscara ruim fica um recorte com costura. Por isso 40 dos 137 trabalhos são olhos **normais** do Zenodo: a costura aparece também em negativos e não vira pista de doença. Bug de processo: um driver do lote antigo continuou rodando e contaminou um E1 com 312 imagens ruins; o E1 foi descartado e refeito na fila 6.
- **Colagem**: a regra de cor não acha pterígio nem lesão pigmentada em fotos pequenas; pterígio virou transplante de **setor geométrico nasal** (do limbo ao canto, ±40°), hemorragia por cor funciona parcialmente, icterícia e conjuntivite por transferência de cor ficam convincentes. 30% das colagens são negativas (esclera normal sobre olho normal) pelo mesmo motivo da costura. Alvos agora recortados em close-up como o app exige.

### Fontes do grupo B como teste externo e a fila de experimentos (30/09/2026, noite)

`treino/preparar_fontes_B.py` + desduplicação contra `eye_diseases` (md5 e dHash ≤ 6): `cekmate_leucocoria` (349 fotos de criança com flash, 119 leucocorias), `gh_eyedis5` (92 fotos web: catarata, uveíte; 16 cópias do `eye_diseases` removidas), `commons_olho` (135 fotos do Commons por 62 termos). `hf_retinoblastoma` (224 px) não passa no gate de enquadramento (10 de 287) e foi deixado de lado. Baseline do v2.1 na metade B: leucocoria AUROC 0,84 (sens 0,49); catarata/uveíte web 0,89/0,90; Commons por termo 0,26–0,69.

Experimentos enfileirados na GPU (`dados/fila6..8_gpu.sh`): **E1** = real + colagem (286) + MPFB (111) + síntese v2 (669) + embrulho (42); **E4a** = real + metade A de todas as fontes externas (`treino/promover_metade_A.py` → `dados/labels_promovidas_A.csv`); **E4b** = E4a + fontes geradas. Depois `treino/comparar_externos.py` compara v2.1, E2, E1, E4a e E4b em nove fontes externas (metade B) → `saida/comparacao_externos.md`. A aposta declarada: E4a (fontes reais novas) é a maior alavanca; as geradas ajudam na margem.

### Comparação das versões nas fontes externas, metade B (30/09/2026, noite) — a resposta

`saida/comparacao_externos.md` (gerado por `treino/comparar_externos.py`). AUROC médio por fonte (sinais com n ≥ 5) e, entre parênteses, positivos que sairiam "sem sinais":

| fonte (metade B) | v2.1 | E2 aumento | E1 geradas | **E4a real A** | E4b real A + geradas |
|---|---:|---:|---:|---:|---:|
| PubMed limpo | 0,62 (48%) | 0,67 (38%) | 0,65 (12%) | **0,73 (2%)** | 0,70 (8%) |
| Commons | 0,67 (43%) | 0,72 (34%) | 0,74 (7%) | **0,89 (5%)** | 0,88 (10%) |
| Mendeley conj. (pterígio, nevo, melanoma) | 0,64 (29%) | 0,69 (12%) | 0,66 (2%) | **0,92 (2%)** | 0,89 (0%) |
| pinkeye (conjuntivite) | 0,83 (42%) | 0,84 (36%) | 0,85 (14%) | **0,91 (2%)** | 0,91 (4%) |
| Mendeley blefarite | 0,83 (50%) | 0,87 (29%) | 0,85 (7%) | **0,98 (0%)** | 0,97 (0%) |
| cekmate leucocoria (criança, flash) | 0,84 (30%) | 0,80 (52%) | 0,72 (43%) | **0,97 (0%)** | 0,98 (7%) |
| gh_eyedis5 (catarata, uveíte web) | 0,92 (35%) | 0,93 (13%) | 0,96 (6%) | **0,99 (2%)** | 0,99 (2%) |
| Commons por termo (ceratite, uveíte…) | 0,64 (23%) | 0,66 (27%) | 0,63 (7%) | **0,74 (0%)** | 0,68 (7%) |

Leitura: **fontes reais novas (E4a) são a alavanca**, em toda fonte e todo sinal; as fontes geradas (colagem, MPFB, embrulho) sozinhas dão pouco (E1) e em cima do real não somam (E4b ≤ E4a). Ressalva explícita: as metades B são imagens novas mas das mesmas fontes que entraram no treino; o número honesto entre fontes vem do E4c (sem promover Commons) e E4d (sem promover PubMed), na fila 9. Por sinal, os ganhos maiores: tumor de superfície 0,30 → 0,90 (Mendeley), uveíte no Commons 0,07 → 0,72, pálpebra 0,53 → 0,76 (PubMed) e 0,72 → 0,94 (Commons), leucocoria 0,84 → 0,97.

### Número honesto entre fontes e ponto de operação (30/09/2026, noite)

- **E4c** (treina com a metade A de todas as fontes MENOS Commons e Commons-por-termo; testa no Commons B): AUROC médio **0,83** (v2.1: 0,67; E4a com o Commons dentro: 0,89). Ou seja, dois terços do ganho vêm de outras fontes, não de ter visto a mesma fonte. PubMed nesse modelo: 0,74.
- **E4d** (idem sem PubMed; testa no PubMed B): **0,71** (v2.1: 0,62; E4a com PubMed dentro: 0,73). Mesmo padrão: quase todo o ganho vem das outras fontes. Tabela final com E4c/E4d em `saida/comparacao_externos.md`.
- **Limiares**: os do treino (sensibilidade 0,90 na validação interna) fazem o E4a alarmar em 62% dos olhos normais de celular (Zenodo B). Recalibrei em normais reais (Zenodo + Commons, metade B1; a B2 mede): a 92% de especificidade por sinal a união dos 15 sinais ainda alarma 41% dos normais; a 98,5% alarma 15% e perde 16% dos positivos (835 positivos externos). Decisão: o cartão leva **dois conjuntos**, `thresholds` (98,5%: o app mostra como "presente") e `thresholds_candidato` (92%: "candidato", em tom mais fraco), que é o que a interface já distingue. `treino/recalibrar_limiares.py --versao X --espec 0.985 --candidato-espec 0.92`.

### v2.2 publicada no app (30/09/2026, 14:08)

`treino/publicar_modelo.sh ocular_v22`: E4a renomeado, cartão com `thresholds` (presente, 98,5% de especificidade em normais reais) e `thresholds_candidato` (92%), que o app agora lê (`ModelCard.candidateThresholds`, `LocalAnalyzer`). Assets trocados, APK de 117 MB gerado. Caso real de regressão: o pterígio do usuário passa com 0,98 (limiar 0,94). Teste interno com os limiares rígidos: hiperemia sens 0,68 / esp 0,99, pterígio 0,82 / 0,99, catarata 0,83 / 0,97, hemorragia 0,89 / 0,98 (o candidato recupera parte da sensibilidade). Continuam marcados como "sem validação em foto comum": ceratite, cisto, hemorragia, LIO, opacidade, pinguécula, tumor (menos de 40 positivos de foto comum no treino mesmo com as fontes novas).

O que a v2.2 NÃO resolve: opacidade corneana e pinguécula não ganharam fonte; uveíte em foto de consultório continua fraca (0,5–0,7); o alarme em olhos normais está em 15% no limiar rígido. Próximo salto exige mais fontes reais por sinal (as bloqueadas por credencial: Kaggle, Roboflow, IEEE, Figshare tracoma, Synapse pálpebras) e rotulagem por recorte com Claude.

### Ramo A com dados da internet: os índices físicos separam (30/09/2026, fim do dia)

`treino/avaliar_indices.py`: ROI da esclera pelo segmentador (fenda menos íris dilatada, sem pixels estourados), índices do PDF calculados em fotos aleatórias da internet, **sem nenhum controle de luz**:

| tarefa | índice | AUROC | normalizado pela pele periocular |
|---|---|---:|---:|
| icterícia vs normal (86 vs 299) | ln(R/B) da esclera | **0,90** | 0,88 |
| hiperemia vs normal (198 vs 299) | R/(R+G+B) da esclera | **0,88** | 0,77 |
| icterícia vs normal | ln(R/G) | 0,74 | 0,66 |

Ou seja: o princípio de absorbância (bilirrubina absorve azul, hemoglobina absorve verde) já discrimina em foto comum sem flash controlado; normalizar pela pele não ajuda (a pele também muda e varia entre pessoas). `saida/indices_referencia.json` guarda os percentis dos índices em olhos normais para o app poder dizer "esclera mais amarela que 95% dos olhos normais". O app agora usa o segmentador como ROI do ramo A (`EyeSegmenter.kt`, `Reflectance.scleraFromSegmenter`; APK recompilado 14:46, 124 MB).

O que continua faltando para virar **número clínico** (bilirrubina em mg/dL, Hb em g/dL): pares foto + laboratório. Abertos só existem NeoJaundice (pele de RN, calibrado: Spearman 0,73) e CP-AnemiC (conjuntiva, rede: AUROC 0,82 dentro da fonte). Os que destravam sem hardware: Mendeley yfsz6c36vc (300 RN com bilirrubina; baixa só pelo navegador) e Eyes-Defy-Anemia com Hb (IEEE DataPort, conta). Com o anel ou o flash do tablet + cartão branco impresso, a mesma medição vira absorbância de verdade (−log da reflectância relativa ao branco), e aí a coleta em campo com hemograma/bilirrubina calibra.

### Modo de falha "foto de tela" (30/09/2026, 17h)

O usuário testa apontando o tablet para fotos do Google na tela do Mac, e um pterígio saiu com 0 e "uveíte". Reproduzido em simulação (`treino/testar_tela.py`: grade de subpixels, moiré, brilho especular, tela azulada, borrão) em 27 pterígios reais do Mendeley: v2.1 e v2.2 detectam 56–67% no original e **0% na "foto de tela"** (p médio 0,00–0,13). Pré-processar na inferência não resolve (borrão 2,5: 11%). Correção em treino: `TelaPIL` em `treino/treinar.py` (`OCULAR_TELA_P=0.3` aplica a simulação a 30% das imagens) → experimento E5 sobre os dados da v2.2. Se passar no teste de tela sem perder nas metades B, vira v2.3. O tablet tinha a build das 04:36 (v2.1) até as 16:54; agora está com a de 14:46 (v2.2 + segmentador).

### Qualidade dos rótulos, medida (30/09/2026, noite)

1. **Rótulo ausente virava "negativo"**: cada fonte anota poucos sinais e o resto entrava como 0. Ex.: 613 pterígios no treino, só 25 com hiperemia marcada; uveíte com 106 de 136 exemplos de uma só raspagem web. Corrigido com `OCULAR_LABEL_MASK=1` (a perda só usa os rótulos que a fonte anota). E6 = v2.2 + máscara + simulação de tela: Commons B 0,90, PubMed B 0,73.
2. **Rótulo por texto relido com LAYA** (`treino/rotular_laya.py`, modelo de decisões tipadas só de texto, Apache 2.0): o LAYA concorda com o rótulo por palavra-chave em 64% no PubMed, 77% no Commons e 16% no Commons-por-termo. No PubMed, 46% das figuras são pós-operatório e 183 são campo cirúrgico. Teste limpo (foto externa ou lâmpada de fenda, não pós-operatório, LAYA concorda): `dados/labels_*_limpo_laya.csv`. No Commons limpo, E6 dá hiperemia 0,97 (sens 0,79), conjuntivite 0,98 (0,93), catarata 0,96, hemorragia 0,98 (1,00), icterícia 0,93. Parte do "número baixo" era rótulo ruim, não modelo.
3. LAYA e JEV são modelos de texto: não veem imagem, servem para rótulo e triagem de legendas, não para o reconhecedor.

### Experimento 300/200 com acurácia simples (30/09/2026, noite)

`treino/experimento_300_200.py`: 4 classes com pelo menos 500 fotos comuns (normal, conjuntivite, pterígio, catarata), 300 por classe no treino, 200 por classe separadas por paciente, classificador único (softmax, MobileNetV3 do app). **Acurácia no teste separado: 89,1%** (800 fotos; acaso 25%). Por classe: normal 80,5%, conjuntivite 87,5%, pterígio 95,0%, catarata 93,5%. Erro mais comum: normal chamado de pterígio (21). Foto do usuário (pterígio vascular) sai pterígio com 0,39, não 0,01. Limite: as 200 de teste vêm das mesmas bases das 300 de treino; os outros sinais não têm 500 fotos comuns.

### Palidez / anemia só com dados públicos (30/09/2026, manhã)

`treino/treinar_palidez.py`: regressor de hemoglobina (MobileNetV3-small) no recorte da conjuntiva do CP-AnemiC (710 crianças de Gana com Hb de laboratório), validação cruzada em 5 dobras por criança, comparado com a regra de cor linear e testado em transferência na base Eyes-Defy-Anemia (Índia/Itália, outro dispositivo, só classe), que nunca entra no treino.

| método | MAE (g/dL) | Spearman | AUROC anemia (Hb < 11) | AUROC grave (Hb < 7) |
|---|---:|---:|---:|---:|
| CNN na conjuntiva | 1,62 | 0,46 | **0,82** | 0,64 |
| regra de cor linear (L, a, b, fração de vermelho) | 1,80 | 0,08 | 0,55 | – |
| transferência para Eyes-Defy-Anemia (classe) | – | – | **0,55** | – |

Leitura: dentro da fonte, um modelo aprendido faz o que a literatura de campo reporta (~0,8 de AUROC para anemia); a regra de cor pura não faz nada, como já tínhamos visto. **Entre fontes, não transfere**: 0,55 numa base de outro país e outro dispositivo, com região de interesse por heurística. É o limite do "só internet" para cor sem referência: cada base é um iluminante e um aparelho. O caminho é (1) juntar as duas bases com Hb (a versão do IEEE DataPort do Eyes-Defy tem a hemoglobina) e validar cruzado, (2) ROI de conjuntiva aprendida (Anemia-seg tem os polígonos) em vez de heurística, (3) normalização pela esclera da própria foto como referência branca. O `saida/palidez_v1.onnx` existe, mas não vai para o app até passar num teste entre fontes.

### Funcionalidades para o agente de saúde (29/09/2026, noite)

- **Ficha do paciente** (`core/Patient.kt`, tela Pacientes): código interno, nome, ano de nascimento, sexo, CNS opcional. Cada análise fica ligada ao paciente; o histórico mostra triagem e índices por visita.
- **Comandos por voz e texto** (`core/Commands.kt`, `core/Voice.kt`): a mesma gramática na barra da tela inicial e no microfone da captura: "nova análise", "capturar", "pronto", "criança", "luz baixa/média/alta", "paciente Maria", "novo paciente Maria", "relatório", "galeria", "pacientes", "ajustes", "voltar", "ajuda". Reconhecimento pt-BR do sistema (Google); precisa de RECORD_AUDIO.
- **Relatório PDF** (`core/Report.kt`) com foto, quadros, triagem, sinais, índices e notas; **exportação protegida** em ZIP AES-256 (zip4j) com PDF, JSON, FHIR e fotos; compartilhamento pelo Android (FileProvider).
- **FHIR R4 para o SUS** (`core/fhir/FhirExport.kt`): Bundle com Patient (CNS/CPF nos NamingSystems da RNDS), Organization (CNES, configurável em Ajustes), Encounter, Observation por sinal e por índice, DocumentReference com a foto, ServiceRequest quando há encaminhamento. Códigos dos sinais em sistema próprio; mapeamento SNOMED CT pendente. O envio à RNDS exige credenciamento e certificado do estabelecimento: o app gera, um backend transmite. DICOM fica para depois.
- **Foco manual e zoom** na captura (Camera2 interop: `CONTROL_AF_MODE OFF` + `LENS_FOCUS_DISTANCE`; `setZoomRatio`). O foco manual depende de o aparelho expor a distância mínima de foco.
- **Níveis de luz** (alta, média, baixa) que escalam o brilho dos comandos `S` da rotina; **flash do tablet** como fonte de luz quando não há anel (`TORCH on/off` na rotina); **pausas com instrução** na rotina (`rótulo; comando; ms; foto; Peça para olhar para a esquerda`) para a sequência de olhares, confirmadas por toque ou pela voz ("pronto").
- **Red-free por software**: canal verde do quadro branco salvo como quadro "Red-free".
- **Infravermelho** no firmware serial (`CFG ir=<pino>`, comando `IR ii`); exige LED IR e câmera que enxergue IR.

### Anel de luz pela USB (ESP32-CAM) e rotina de cores

Arquitetura atual: o tablet fotografa com a própria câmera; um ESP32-CAM ligado por cabo USB (adaptador OTG) controla os LEDs RGB. Firmware sem nada fixo em `firmware/guarana_luz_serial/`: o app envia, ao conectar, a linha `CFG` com pino, quantidade e tipo de LED e o pino do flash, e o ESP grava isso na flash. A rotina de cores é um texto editável em Ajustes (`rótulo; comando; espera ms; foto`, `*` marca o quadro analisado), então cores, tempos e ordem também ficam no app. Ao plugar o ESP, o Android oferece abrir o Guaraná e concede a permissão USB. Bluetooth e Wi-Fi continuam como transportes alternativos (`firmware/guarana_luz/`). O caminho USB ainda não foi testado com hardware; o HTTP foi testado no emulador com o simulador.

#### Versão anterior (Bluetooth/Wi-Fi)

O app controla um anel de LEDs WS2812B ligado a um ESP32 (firmware em `firmware/guarana_luz/`). Em Ajustes → "Anel de luz": ligar, escolher Bluetooth (padrão, procura o nome `Guarana-Luz`) ou Wi-Fi do ESP (rede `Guarana-Luz`, endereço 192.168.4.1) e "Testar luz". Na captura aparece um botão de luz que executa a rotina: branco 30%, 60%, 100%, vermelho, verde, azul e ambiente, com uma foto por passo (~10 s). O quadro "Branco 60%" é analisado; os sete ficam guardados na análise e aparecem no resultado. Protocolo e montagem: `firmware/guarana_luz/README.md`. Para testar sem hardware: `python3 firmware/mock/mock_esp.py 8080` e, no emulador, endereço `10.0.2.2:8080`.

Lição do teste: o transporte HTTP do anel ignora proxy do sistema (`Proxy.NO_PROXY`); o emulador desta máquina tinha um proxy global configurado e a primeira tentativa foi para ele.

### Resultado do treino v1 (29/09/2026, Mac M5 Pro, 18 épocas, ~12 min)

Teste: 783 recortes de pessoas não vistas no treino. Limiar por sinal escolhido na validação para sensibilidade 0,90.

| Sinal | Positivos no teste | AUROC | Sensibilidade | Especificidade |
|---|---|---|---|---|
| hiperemia | 95 | 0,999 | 0,92 | 1,00 |
| ictericia | 22 | 1,000 | 0,95 | 0,99 |
| pterigio_pinguecula | 80 | 0,986 | 0,84 | 0,95 |
| catarata_leucocoria | 81 | 0,995 | 0,75 | 1,00 |
| hemorragia_subconjuntival | 21 | 0,996 | 0,86 | 1,00 |
| lesao_pigmentada | 42 | 0,985 | 0,86 | 0,96 |
| opacidade_corneana | 83 | 0,998 | 0,92 | 1,00 |

Por domínio: lâmpada de fenda (n = 249) AUROC 0,94 a 1,00; web (n = 149) hiperemia 1,00, icterícia 1,00, catarata 0,98. **Não há positivo nenhum no domínio de celular** (conj_seg só tem negativos), então o desempenho na foto do tablet é desconhecido até haver fotos próprias. Parte desses números vem do modelo reconhecer o "estilo" de cada fonte (lâmpada de fenda versus web); trate como prova de pipeline, não como acurácia.

Arquivos em `saida/`: `ocular_v1.onnx` (fp32, 16,8 MB, **recomendado**), `ocular_v1_int8.onnx` (4,4 MB, desvio de probabilidade até 0,10, não use), `ocular_v1.pt`, `model_card.json`. Inferência no Mac: ~5 ms por imagem em CPU.

### Palidez conjuntival: sem regra de cor

`calibrar_palidez.py` mede a cor média (CIELab) dos 710 recortes do CP-AnemiC e tenta separar anêmicos (Hb < 11) de não anêmicos. Resultado: AUROC 0,51, cor média idêntica em todas as faixas de Hb, inclusive Hb < 7. A cor média da conjuntiva nesse dataset não carrega o sinal, provavelmente por variação de iluminação entre hospitais. Conclusão: **palidez não entra no motor local v1**. Fica na nuvem, e só volta ao local com fotos próprias sob protocolo de luz controlada.

## App Android: Guaraná (`guarana-app/`)

Kotlin + Jetpack Compose, ONNX Runtime em CPU, CameraX. Roda o `ocular_v1.onnx` inteiramente no aparelho; a nuvem é opcional (Ajustes). Ícone e logo: a fruta de guaraná aberta, que parece um olho, em tons pastel.

```
cd guarana-app
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home ANDROID_HOME=~/Library/Android/sdk
./gradlew assembleRelease            # app/build/outputs/apk/release/app-release.apk (assinado com a chave de debug)
adb install -r Guarana-v0.1.apk      # ou copie o APK para o tablet e instale por "fontes desconhecidas"
```

Telas: início (nova análise, galeria, recentes), captura (moldura oval, sem flash, chip "Criança"), análise, resultado (faixa de triagem, sinais com probabilidade e limiar, origem da análise) e ajustes (servidor da nuvem, limiares do modelo). Cada análise fica em `files/analises/` como JPEG + JSON no contrato.

Como o app decide: `core/Triage.kt`. Leucocoria em criança → urgente; lesão pigmentada, catarata, icterícia, opacidade, pterígio → encaminhar; hiperemia ou hemorragia isoladas → observar. Limiares e pré-processamento vêm do `model_card.json` nos assets: para trocar de modelo, substitua os dois arquivos em `app/src/main/assets/`.

Versões: `versionCode` é derivado do horário da compilação, então todo APK novo instala por cima do anterior (`adb install -r`) mantendo ícone, atalhos e histórico. Isso só vale enquanto a assinatura for a mesma: a chave de debug deste Mac (`~/.android/debug.keystore`). Compilar em outra máquina exige desinstalar antes. Em Ajustes há "Fixar na tela inicial", que cria um atalho persistente; no launcher da Samsung, apps instalados por cabo vão só para a gaveta.

Limitações conhecidas desta versão: não há detector de olho, então uma foto sem olho produz sinais sem sentido (o gate de qualidade só vê desfoque e exposição); a fila de sincronização com a nuvem ainda não existe (a nuvem é consultada só na hora da análise, se houver rede); APK só para arm64 e x86_64.

## Integrar no app Android (ONNX Runtime)

Dependência: `com.microsoft.onnxruntime:onnxruntime-android` (versão estável mais recente). Copie para `app/src/main/assets/` o arquivo indicado em `model_card.json` → `files.recommended` e o próprio `model_card.json`. O app lê do card: tamanho de entrada, `mean`/`std`, ordem dos rótulos e `thresholds`. Nada disso pode virar constante duplicada no Kotlin.

Pré-processamento idêntico ao treino, na ordem: EXIF → RGB → redimensionar o lado menor para 352 → recorte central 320×320 → float 0..1 → (x − mean) / std por canal → tensor NCHW `[1,3,320,320]`. Saída `logits[1,7]` → sigmoid → comparar com o limiar de cada rótulo. Resultado vira o contrato `contrato/resultado.schema.json` com `engine = "local-model"`, `status = "provisional"`, `needs_cloud_review = true`, e `evidence` = probabilidade e limiar.

Se a foto vier de rosto inteiro, recorte a faixa dos olhos antes (o app já tem a guia de enquadramento; a regra do treino foi Haar do OpenCV com margem de 1,3× na largura e 1,4× na altura).

## Como rotular fotos novas com o Claude

```
export ANTHROPIC_API_KEY=...        # ou: ant auth login
python treino/rotular_com_claude.py --imagens dados/brutas --saida dados/labels_claude.csv --idade 40
```

O CSV é retomável. Rótulos "incerto" viram 0 e ficam listados na coluna `revisar`: confira esses manualmente antes de treinar. Custo aproximado por foto: US$ 0,02 no Opus 5.5. O script já usa o fallback server-side para recusas (`fallbacks = "default"`), para uma foto recusada não travar o lote.

## Rótulos

Treináveis na v1 (precisam de pelo menos 15 positivos no treino cada, idealmente 50+):

| Rótulo | Sinal do PDF |
|---|---|
| hiperemia | inflamação (fase 1) |
| ictericia | icterícia (fase 1) |
| opacidade_corneana | opacidade / turvação da córnea (inclui ceratite, distrofia e cicatriz no SLID) |
| pterigio_pinguecula | pinguécula / pterígio |
| catarata_leucocoria | catarata / leucocoria |
| hemorragia_subconjuntival | hemorragia subconjuntival |
| lesao_pigmentada | nevo / PAM / melanoma, sem separar |

Coletados no CSV mas fora do modelo até haver dados: palidez_conjuntival (ver acima), arco_corneano, esclera_azul, manchas_bitot, ocronose, telangiectasia. Enquanto isso, ficam com as regras de cor (camada 2) e com a nuvem (camada 3).

## Regras que não se negocia

- Divisão treino/validação/teste **por pessoa**, nunca por foto.
- Sem jitter de matiz ou saturação: cor é o sinal.
- Limiar por sinal escolhido para sensibilidade alvo de 0,90 na validação. Triagem prefere falso positivo.
- O app lê tamanho de entrada, normalização, rótulos e limiares do `model_card.json`. Nada duplicado em constantes.
- Métricas em conjunto pequeno são preliminares. Na apresentação: "triagem experimental, sem validação clínica".
- Fotos de olho são dado sensível (LGPD). Consentimento na coleta, sem EXIF, sem imagens no repositório.

## Referências de produto (benchmark de 29/09/2026)

| | Guaraná hoje | Phelcom Eyer2 | Volk VistaView | "MS-01" OPTCAM100F (Amazon.br) |
|---|---|---|---|---|
| Alvo | olho externo (esclera, conjuntiva, córnea) | retina 55°×45° + segmento anterior | retina 55° (mais com dinâmico) | retina 42° |
| Pupila mínima | não se aplica | 3 mm, não midriático | não informado (midriático) | 2,5 mm |
| Iluminação | anel de LED RGB externo, rotina branco/azul/vermelho/ambiente | branca, azul-cobalto, infravermelha (meibografia), red-free | LED branco em 3 níveis, filtro red-free | LED branco + infravermelho próximo |
| Foco | manual da câmera do tablet | autofoco, −20 a +20 D | autofoco e manual, −15 a +15 D | não informado |
| Captura | disparo manual + sequência | autofoco, alvos internos de fixação | por voz, tela 8" | tela 3,5" |
| Dados | JSON + JPEG locais | JPEG, PNG, DICOM, nuvem com laudos, IA | DICOM, relatório com notas, busca de pacientes, exportação com senha | microSD |
| Regulatório | investigacional | ANVISA classe II, FDA, ISO 13485 | não informado na página | não informado |

Fontes: página da Volk (VistaView), descrição técnica do Eyer2 (UFMA) e anúncio na Amazon.br.

**Funcionalidades a puxar, por ordem de valor por esforço:**

1. **Ficha e identificação do paciente** (código interno, não CPF): busca e ordenação na tela inicial, histórico por pessoa, comparação entre visitas. Só software.
2. **Relatório instantâneo** com notas do caso, PDF com as fotos, índices e a triagem, exportação protegida por senha. Só software.
3. **Red-free por software**: canal verde do quadro branco realça vasos da conjuntiva; entra como mais um quadro derivado na rotina.
4. **Níveis de iluminação** (alto, médio, baixo) na rotina, para pessoas fotofóbicas e para calibrar exposição; já é uma linha no texto da rotina.
5. **Captura por voz** ("capturar"): mãos livres quando o agente segura a pálpebra.
6. **Canal infravermelho no anel**: pré-visualização sem contrair a pupila e vascularização; o Eyer2 e o MS-01 têm. Exige LED IR e câmera sem filtro IR forte (a do tablet costuma ter; medir).
7. **Alvos de fixação**: um ponto na tela para o olhar, como os 9 alvos do Eyer2; no olho externo, dois ou três bastam (olhar para cima, para os lados) para expor mais esclera.
8. **Adaptador óptico**: lente macro ou ocular acoplada ao tablet para nitidez de córnea e íris; é o que o documento do Ramo B chama de "magnificação" e o que separa sinais de cor de sinais de forma.
9. **DICOM e FHIR** na exportação, para o e-SUS e para licitação.

## Datasets públicos

Verificados por acesso direto em 29/09/2026. "NV" = existe, mas conteúdo ou licença não verificados. Priorize os de download direto com CC BY 4.0.

**Baixar hoje (download direto):**

| Rótulo alvo | Dataset | Imagens | Licença | Observação |
|---|---|---|---|---|
| palidez_conjuntival | CP-AnemiC (Gana), https://data.mendeley.com/datasets/m53vz6b7fx/1 | 710, com Hb g/dL | CC BY 4.0 | Tablet 12 MP, conjuntiva palpebral, crianças. Positivo = Hb abaixo do corte do laudo |
| palidez_conjuntival | Ghana IDA conjunctiva, https://data.mendeley.com/datasets/nt7r8hv2pz/1 | 710 + 4.260 aumentadas | CC BY 4.0 | Mesmo grupo, provável sobreposição com o anterior: use um só, e nunca as aumentadas no teste |
| negativos, segmentação | Eye Conjunctiva Segmentation, https://data.mendeley.com/datasets/yxwjgcndg2/1 | 547 | CC BY 4.0 | Smartphone; máscaras de conjuntiva, sem Hb |
| ictericia | Jaundice_Dataset, https://huggingface.co/datasets/Bleachcarte/Jaundice_Dataset | 256 (115 ictéricos) | CC BY-NC 4.0 | Raspado da web, sem bilirrubina. Só para competição e pesquisa |
| pterigio_pinguecula | BR-Pterygium, https://universe.roboflow.com/mauro-gobira/br-pterygium-dataset | 338 | CC BY 4.0 | Foto externa, autor brasileiro |
| pterigio_pinguecula | Eye Disease Image Dataset (Faridpur), https://data.mendeley.com/datasets/s9bfhswzjb/1 | ~102 de pterígio | CC BY 4.0 | Use SÓ a classe pterígio; as outras 9 classes são fundo de olho |
| hiperemia, catarata_leucocoria, negativos | Eye Diseases (uveíte, conjuntivite, catarata, pálpebra), https://data.mendeley.com/datasets/n9zp473wfw/1 | conjuntivite 357, catarata 544, normal 649 | CC BY 4.0 | Raspado do Google: qualidade e viés heterogêneos. Use as pastas originais, não as balanceadas por SMOTE |
| hemorragia_subconjuntival, lesao_pigmentada, pterigio_pinguecula, hiperemia, catarata | SLID, https://github.com/xumingyu-hub/SLID | 2.617 (hemorragia 181, nevo 416, pinguécula 405, hiperemia 307, catarata 225) | CC BY | LÂMPADA DE FENDA, não celular. Única fonte pública de hemorragia e nevo. Treine com `source = slid` e avalie separadamente em fotos de celular |
| negativos | Periorbital Segmentation Dataset, https://zenodo.org/records/13916845 | 2.842 recortes de olho | CC BY 4.0 (máscaras); imagens-fonte CFD e CelebAMask-HQ têm licença própria | Bons negativos no domínio "foto comum" |

**Pedir hoje, chega quando chegar (formulário por e-mail):** MOBIUS (16.717 fotos de 3 smartphones, máscaras de esclera e íris) e SBVPI (1.858, DSLR macro), em https://sclera.fri.uni-lj.si/datasets.html; UBIRIS.v2 (11.102, luz visível), em https://iris.di.ubi.pt/ubiris2.html.

**Existem mas não verificados (Kaggle renderiza por JS):** nandanp6/cataract-image-dataset (~609, raspado do Bing), puspendrakumar77/jaundiced-and-normal-eyes, guptajanavi/palpebral-conjunctiva-to-detect-anaemia, harshwardhanfartale/eyes-defy-anemia (espelho do Eyes-defy-anemia, 218 imagens com Hb, original no IEEE DataPort com login).

**Sem nenhum dado público de foto externa:** icterícia com bilirrubina medida (os públicos com bilirrubina são de pele neonatal), leucocoria, arco corneano, esclera azul, manchas de Bitot, ocronose, telangiectasia. Esses ficam nas regras de cor e na nuvem, e entram no modelo só com fotos próprias coletadas com consentimento.

**Tamanho realista do treino v1:** entre 2 mil e 3,5 mil imagens. Positivos por rótulo: palidez ~420, icterícia ~115, pterígio/pinguécula ~440 + 405 (SLID), catarata ~540 + 225 (SLID), hiperemia ~360 + 307 (SLID), hemorragia 181 (só SLID), lesão pigmentada 416 (só SLID). Hemorragia e lesão pigmentada não têm nenhum exemplo no domínio de celular: o conjunto de teste precisa ter fotos próprias desses sinais, ou o card marca "não avaliado no domínio".
