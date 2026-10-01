package com.guarana.esusmock

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.toMutableStateList
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.UUID

/** Grupos de motivo da Ficha de Visita Domiciliar e Territorial (FVDT), no vocabulario oficial. */
object Fvdt {
    val grupos: List<Pair<String, List<String>>> = listOf(
        "Motivo da visita" to listOf("Cadastramento/atualização", "Visita periódica"),
        "Busca ativa" to listOf("Consulta", "Exame", "Vacina", "Condicionalidades do Bolsa Família"),
        "Acompanhamento" to listOf(
            "Gestante", "Puérpera", "Recém-nascido", "Criança", "Pessoa com desnutrição", "Pessoa em reabilitação ou com deficiência",
            "Pessoa com hipertensão", "Pessoa com diabetes", "Pessoa com asma", "Pessoa com DPOC/enfisema", "Pessoa com câncer",
            "Pessoa com outras doenças crônicas", "Pessoa com hanseníase", "Pessoa com tuberculose", "Sintomáticos respiratórios", "Tabagista",
            "Domiciliados/acamados", "Condições de vulnerabilidade social", "Condicionalidades do Bolsa Família", "Saúde mental",
            "Usuário de álcool", "Usuário de outras drogas",
        ),
        "Outros motivos" to listOf("Egresso de internação", "Convite para atividades coletivas / campanha de saúde", "Orientação / prevenção", "Outros"),
        "Controle ambiental / vetorial" to listOf("Ação educativa", "Imóvel com foco", "Ação mecânica", "Tratamento focal"),
    )
    val desfechos = listOf("Visita realizada", "Visita recusada", "Ausente")
    val turnos = listOf("Manhã", "Tarde", "Noite")
    val tiposImovel = listOf("Domicílio", "Comércio", "Terreno baldio", "Ponto de estratégia", "Escola", "Creche", "Abrigo", "Instituição de longa permanência para idosos", "Unidade prisional", "Unidade de medida socioeducativa", "Delegacia", "Estabelecimento religioso", "Outros")

    /** Motivo com o grupo na frente, como "Busca ativa: Exame", que e como o Guarana e o mock do PEC escrevem. */
    fun rotulo(grupo: String, item: String) = if (grupo == "Motivo da visita") item else "$grupo: $item"
}

/**
 * Formulario da visita, aberto por VISITAR / VISITAR FAMILIA. E o alvo da injecao do Guarana: os campos usam os
 * mesmos textos do app oficial (turno, motivo por grupo, desfecho, peso e altura). FINALIZAR grava a visita no Repo.
 */
@Composable
fun VisitForm(imovelUuid: String, cns: String, onDone: () -> Unit, onCancel: () -> Unit) {
    val c = remember(cns) { Repo.cidadao(cns) }
    val i = remember(imovelUuid) { Repo.imovel(imovelUuid) }
    var turno by remember { mutableStateOf(if (LocalDateTime.now().hour < 12) "Manhã" else "Tarde") }
    var tipoImovel by remember { mutableStateOf("Domicílio") }
    var compartilhada by remember { mutableStateOf<Boolean?>(false) }
    val marcados = remember { mutableListOf<String>().toMutableStateList() }
    var peso by remember { mutableStateOf("") }
    var altura by remember { mutableStateOf("") }
    var desfecho by remember { mutableStateOf("Visita realizada") }
    var erro by remember { mutableStateOf<String?>(null) }

    Column(Modifier.fillMaxSize().background(E.Bg)) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(bottom = 16.dp)) {
            BodyTitle("Visita domiciliar")
            EsusCard(Modifier.padding(horizontal = 12.dp)) {
                Column(Modifier.padding(14.dp)) {
                    Text(c?.nome ?: "Cidadão", fontSize = 18.sp, color = E.Ink)
                    Text(listOfNotNull(c?.sexoLabel, c?.idade, c?.cns?.let { "CNS $it" }).joinToString(" | "), fontSize = 13.sp, color = E.Ink2)
                    if (i != null) Text("${i.logradouroCompleto}, ${i.numero} · ${i.bairro} · Microárea ${i.microarea}", fontSize = 13.sp, color = E.Ink2)
                }
            }
            Column(Modifier.padding(horizontal = 16.dp).padding(top = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                EsusDropdown("Turno", turno, Fvdt.turnos, { turno = it }, required = true)
                EsusDropdown("Tipo de imóvel", tipoImovel, Fvdt.tiposImovel, { tipoImovel = it }, required = true)
            }
            Column(Modifier.padding(horizontal = 12.dp).padding(top = 10.dp)) {
                YesNoCard("Visita compartilhada com outro profissional?", "Visita compartilhada com outro profissional", "Visita não compartilhada com outro profissional", compartilhada, onChange = { compartilhada = it })
            }
            Fvdt.grupos.forEach { (grupo, itens) ->
                Text(grupo, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = E.Ink, modifier = Modifier.padding(horizontal = 16.dp).padding(top = 18.dp, bottom = 4.dp))
                EsusCard(Modifier.padding(horizontal = 12.dp)) {
                    Column(Modifier.padding(horizontal = 6.dp, vertical = 4.dp)) {
                        itens.forEach { item ->
                            val r = Fvdt.rotulo(grupo, item)
                            CheckRow(item, r in marcados) { on -> if (on) marcados += r else marcados -= r }
                        }
                    }
                }
            }
            Text("Antropometria", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = E.Ink, modifier = Modifier.padding(horizontal = 16.dp).padding(top = 18.dp, bottom = 4.dp))
            Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                EsusField("Peso (kg)", peso, { peso = it }, Modifier.weight(1f))
                EsusField("Altura (cm)", altura, { altura = it }, Modifier.weight(1f))
            }
            Text("Desfecho", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = E.Ink, modifier = Modifier.padding(horizontal = 16.dp).padding(top = 18.dp, bottom = 4.dp))
            Column(Modifier.padding(horizontal = 16.dp)) {
                EsusDropdown("Desfecho", desfecho, Fvdt.desfechos, { desfecho = it }, required = true)
            }
            if (erro != null) Text(erro!!, color = androidx.compose.ui.graphics.Color(0xFFC62828), fontSize = 14.sp, modifier = Modifier.padding(16.dp))
            Spacer(Modifier.height(8.dp))
        }
        StepFooter(first = false, last = true, onPrev = onCancel) {
            if (desfecho == "Visita realizada" && marcados.isEmpty()) { erro = "Informe ao menos um motivo da visita."; return@StepFooter }
            Repo.registrarVisita(Visita(
                uuid = UUID.randomUUID().toString(), imovelUuid = imovelUuid, cns = cns,
                dataHora = LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME).take(19), turno = turno, tipoImovel = tipoImovel,
                compartilhada = compartilhada == true, motivos = marcados.toList(), peso = peso, altura = altura, desfecho = desfecho, origem = "formulário",
            ))
            onDone()
        }
    }
}
