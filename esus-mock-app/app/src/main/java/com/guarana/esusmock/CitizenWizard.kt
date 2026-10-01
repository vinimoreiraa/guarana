package com.guarana.esusmock

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Pergunta sim/nao do cadastro individual: id, texto quando Sim, texto quando Nao, pergunta quando vazio. */
data class Pergunta(val id: String, val sim: String, val nao: String, val pergunta: String = "$sim?")

/** Etapas 4, 5 e 6 do cadastro individual, com o texto dos cartoes como aparece no e-SUS Territorio. */
object Perguntas {
    val sociodemografico = listOf(
        Pergunta("orientacao_sexual", "Deseja informar orientação sexual", "Não deseja informar orientação sexual"),
        Pergunta("identidade_genero", "Deseja informar identidade de gênero", "Não deseja informar identidade de gênero"),
        Pergunta("deficiencia", "Possui deficiência", "Não possui deficiência"),
        Pergunta("cuidador_tradicional", "Frequenta cuidador tradicional", "Não frequenta cuidador tradicional"),
        Pergunta("grupo_comunitario", "Participa de grupo comunitário", "Não participa de grupo comunitário"),
        Pergunta("plano_saude", "Possui plano de saúde privado", "Não possui plano de saúde privado"),
        Pergunta("povo_tradicional", "É membro de Povo ou Comunidade Tradicional ou Campo, Floresta e Águas", "Não é membro de Povo ou Comunidade Tradicional ou Campo, Floresta e Águas"),
    )
    val saude1 = listOf(
        Pergunta("peso_adequado", "Se considera com o peso adequado", "Não se considera com o peso adequado"),
        Pergunta("doenca_respiratoria", "Possui doença respiratória", "Não possui doença respiratória"),
        Pergunta("doenca_cardiaca", "Possui doença cardíaca", "Não possui doença cardíaca"),
        Pergunta("rins", "Possui problemas nos rins", "Não possui problemas nos rins"),
        Pergunta("internacao", "Teve internação nos últimos 12 meses", "Não teve internação nos últimos 12 meses"),
        Pergunta("plantas", "Usa plantas medicinais", "Não usa plantas medicinais"),
        Pergunta("alcool", "Faz uso de álcool", "Não faz uso de álcool"),
        Pergunta("drogas", "Faz uso de outras drogas", "Não faz uso de outras drogas"),
        Pergunta("acamado", "Está acamado", "Não está acamado"),
        Pergunta("ave", "Teve AVE", "Não teve AVE"),
        Pergunta("cancer", "Tem/teve câncer", "Não tem/teve câncer"),
        Pergunta("diabetes", "Tem diabetes", "Não tem diabetes"),
    )
    val saude2 = listOf(
        Pergunta("hipertensao", "Tem hipertensão arterial", "Não tem hipertensão arterial"),
        Pergunta("hanseniase", "Tem hanseníase", "Não tem hanseníase"),
        Pergunta("fumante", "É fumante", "Não é fumante"),
        Pergunta("gestante", "Está gestante", "Não está gestante"),
        Pergunta("psiquiatrico", "Está em tratamento psiquiátrico ou com profissional de saúde", "Não está em tratamento psiquiátrico ou com profissional de saúde"),
        Pergunta("tuberculose", "Tem tuberculose", "Não tem tuberculose"),
    )
    val socioeconomico = listOf(
        Pergunta("alimentos_acabaram", "Nos últimos 3 meses, os alimentos acabaram antes que tivesse dinheiro para comprar mais comida", "Nos últimos 3 meses, os alimentos não acabaram antes que tivesse dinheiro para comprar mais comida", "Nos últimos 3 meses, os alimentos acabaram antes que tivesse dinheiro para comprar mais comida?"),
        Pergunta("comeu_poucos", "Nos últimos 3 meses, comeu apenas alguns alimentos que ainda tinha, porque o dinheiro acabou", "Nos últimos 3 meses, não comeu apenas alguns alimentos que ainda tinha, porque o dinheiro acabou", "Nos últimos 3 meses, comeu apenas alguns alimentos que ainda tinha, porque o dinheiro acabou?"),
    )

    /** rotulo da condicao na ficha (como o Guarana importa) <-> id da pergunta */
    val condicaoPorId = mapOf(
        "diabetes" to "Diabetes", "hipertensao" to "Hipertensão arterial", "ave" to "AVC/derrame", "acamado" to "Acamado(a)",
        "internacao" to "Internação nos últimos 12 meses", "gestante" to "Gestante", "fumante" to "Fumante", "alcool" to "Uso de álcool",
        "doenca_respiratoria" to "Doença respiratória", "doenca_cardiaca" to "Doença cardíaca", "rins" to "Problemas nos rins", "cancer" to "Câncer",
        "tuberculose" to "Tuberculose", "hanseniase" to "Hanseníase", "psiquiatrico" to "Tratamento psiquiátrico", "plantas" to "Usa plantas medicinais",
    )
    fun respostasIniciais(c: Cidadao): Map<String, Boolean?> {
        if (c.respostas.isNotEmpty()) return c.respostas
        val m = HashMap<String, Boolean?>()
        (sociodemografico + saude1 + saude2 + socioeconomico).forEach { m[it.id] = false }   // o agente costuma marcar tudo como "Nao"
        condicaoPorId.forEach { (id, label) -> if (c.condicoes.any { it.equals(label, true) }) m[id] = true }
        if (c.condicoes.any { it.startsWith("Deficiência") }) m["deficiencia"] = true
        if (c.condicoes.any { it.startsWith("Domiciliado") }) m["acamado"] = true
        if (c.sexo != "F") m["gestante"] = false
        return m
    }
}

private val GRAUS = listOf("Não sabe ler/escrever", "Alfabetizado", "Ensino fundamental, 1º ciclo", "Ensino fundamental, 2º ciclo", "Ensino médio, médio 2º ciclo (científico, técnico etc.)", "Superior, aperfeiçoamento, especialização, mestrado, doutorado")
private val TRABALHO = listOf("Empregador", "Assalariado com carteira de trabalho", "Assalariado sem carteira de trabalho", "Autônomo com previdência social", "Autônomo sem previdência social", "Aposentado/pensionista", "Desempregado", "Não trabalha", "Servidor público/Militar", "Outro")
private val OCUPACOES = listOf("", "Agricultor", "Auxiliar de serviços gerais", "Comerciante", "Costureira", "Dona de casa", "Estudante", "Motorista", "Pedreiro", "Professor", "Vendedor")
private val UFS = listOf("AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO")

/**
 * Cadastro individual em 7 etapas, como o e-SUS Territorio: Identificacao (1 e 2), Sociodemografico (3 e 4),
 * Condicoes de saude (5 e 6, com "condicao extra" em texto livre) e Socioeconomico (7). FINALIZAR grava no Repo.
 */
@Composable
fun CitizenWizard(cns: String?, imovelUuid: String, familia: String, onDone: (Cidadao) -> Unit, onCancel: () -> Unit) {
    val existing = remember(cns) { cns?.let { Repo.cidadao(it) } }
    var step by remember { mutableStateOf(if (existing == null) 1 else 2) }
    var nome by remember { mutableStateOf(existing?.nome ?: "") }
    var cpf by remember { mutableStateOf(existing?.cpf ?: "") }
    var nasc by remember { mutableStateOf(existing?.dataNascimento ?: "") }
    var sexo by remember { mutableStateOf(existing?.sexo ?: "") }
    var raca by remember { mutableStateOf(existing?.racaCor ?: "") }
    var nacionalidade by remember { mutableStateOf(existing?.nacionalidade ?: "Brasileira") }
    var ufNasc by remember { mutableStateOf(existing?.ufNascimento ?: "SP") }
    var munNasc by remember { mutableStateOf(existing?.municipioNascimento ?: "") }
    var celular by remember { mutableStateOf(existing?.telefone ?: "") }
    var email by remember { mutableStateOf(existing?.email ?: "") }
    var mae by remember { mutableStateOf(existing?.nomeMae ?: "") }
    var maeDesc by remember { mutableStateOf(false) }
    var pai by remember { mutableStateOf(existing?.nomePai ?: "") }
    var paiDesc by remember { mutableStateOf(false) }
    var nis by remember { mutableStateOf(existing?.nis ?: "") }
    var escola by remember { mutableStateOf(existing?.frequentaEscola) }
    var grau by remember { mutableStateOf(existing?.grauInstrucao ?: "") }
    var trabalho by remember { mutableStateOf(existing?.situacaoTrabalho ?: "") }
    var ocupacao by remember { mutableStateOf(existing?.ocupacao ?: "") }
    val respostas = remember { mutableStateMapOf<String, Boolean?>().also { m -> if (existing != null) m.putAll(Perguntas.respostasIniciais(existing)) } }
    val extras = remember { mutableStateMapOf<Int, String>().also { m -> existing?.condicoesExtra?.forEachIndexed { i, s -> if (i < 3) m[i] = s } } }
    val extraOn = remember { mutableStateMapOf<Int, Boolean?>().also { m -> (0..2).forEach { i -> m[i] = if (extras.containsKey(i)) true else null } } }

    val titulo = when (step) { 1, 2 -> "Identificação"; 3, 4 -> "Sociodemográfico"; 5, 6 -> "Condições de saúde"; else -> "Socioeconômico" }
    fun finalizar() {
        val conds = Perguntas.condicaoPorId.filter { (id, _) -> respostas[id] == true }.values.toMutableList()
        if (respostas["deficiencia"] == true) {
            val prev = existing?.condicoes?.filter { it.startsWith("Deficiência") }.orEmpty()
            conds += if (prev.isEmpty()) listOf("Deficiência") else prev
        }
        val ex = (0..2).mapNotNull { i -> if (extraOn[i] == true) extras[i]?.takeIf { it.isNotBlank() } else null }
        val c = Cidadao(
            cns = existing?.cns ?: Repo.novoCns(), cpf = cpf, nome = nome.trim(), sexo = sexo, dataNascimento = nasc, racaCor = raca,
            imovelUuid = imovelUuid, familiaNumero = familia, responsavel = existing?.responsavel ?: false,
            condicoes = conds.distinct().sorted(), condicoesExtra = ex, telefone = celular, nomeMae = if (maeDesc) "" else mae, nomePai = if (paiDesc) "" else pai,
            email = email, nis = nis, nacionalidade = nacionalidade, ufNascimento = ufNasc, municipioNascimento = munNasc,
            frequentaEscola = escola, grauInstrucao = grau, situacaoTrabalho = trabalho, ocupacao = ocupacao, respostas = respostas.toMap(),
        )
        Repo.salvarCidadao(c); onDone(c)
    }

    Column(Modifier.fillMaxSize().background(E.Bg)) {
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(bottom = 16.dp)) {
            BodyTitle(titulo, "Etapa $step de 7")
            when (step) {
                1 -> Column(Modifier.padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    EsusField("Nome completo", nome, { nome = it }, required = true)
                    EsusField("CPF", cpf, { cpf = it.filter { c -> c.isDigit() }.take(11) })
                    EsusField("Data de nascimento (AAAA-MM-DD)", nasc, { nasc = it }, required = true)
                    Kicker("Sexo")
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        RadioRow("Feminino", sexo == "F") { sexo = "F" }; Spacer(Modifier.width(24.dp)); RadioRow("Masculino", sexo == "M") { sexo = "M" }
                    }
                    EsusDropdown("Raça/cor", raca, listOf("branca", "preta", "parda", "amarela", "indígena"), { raca = it }, required = true)
                }
                2 -> Column(Modifier.padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    EsusDropdown("Nacionalidade", nacionalidade, listOf("Brasileira", "Naturalizada", "Estrangeira"), { nacionalidade = it }, required = true)
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        EsusDropdown("Estado de nascimento", ufNasc, UFS, { ufNasc = it }, Modifier.weight(0.6f), required = true)
                        EsusField("Município de nascimento", munNasc, { munNasc = it }, Modifier.weight(1.4f), required = true)
                    }
                    EsusField("Telefone celular", celular, { celular = it }, required = true)
                    EsusField("E-mail", email, { email = it })
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        EsusField("Nome completo da mãe", mae, { mae = it }, Modifier.weight(1f), required = true, enabled = !maeDesc)
                        CheckRow("Desconhece", maeDesc) { maeDesc = it }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        EsusField("Nome completo do pai", pai, { pai = it }, Modifier.weight(1f), required = true, enabled = !paiDesc)
                        CheckRow("Desconhece", paiDesc) { paiDesc = it }
                    }
                    EsusField("Nº NIS (PIS/PASEP)", nis, { nis = it.filter { c -> c.isDigit() }.take(11) })
                }
                3 -> Column(Modifier.padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Frequenta escola?", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = E.Ink)
                    Column { RadioRow("Sim", escola == true) { escola = true }; RadioRow("Não", escola == false) { escola = false } }
                    EsusDropdown("Grau de instrução", grau, GRAUS, { grau = it })
                    EsusDropdown("Situação no mercado de trabalho", trabalho, TRABALHO, { trabalho = it })
                    EsusDropdown("Ocupação", ocupacao, OCUPACOES, { ocupacao = it })
                }
                4 -> PerguntasList(Perguntas.sociodemografico, respostas)
                5 -> Column {
                    InfoBanner("As respostas às perguntas são autorreferidas, ou seja, fornecidas pela pessoa sobre si mesma")
                    PerguntasList(Perguntas.saude1, respostas)
                }
                6 -> Column {
                    PerguntasList(Perguntas.saude2.filter { it.id != "gestante" || sexo == "F" }, respostas)
                    Column(Modifier.padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        (0..2).forEach { i ->
                            if (i == 0 || extraOn[i - 1] == true) YesNoCard(
                                "Deseja adicionar condição extra?", "Deseja adicionar condição extra", "Não deseja adicionar condição extra",
                                extraOn[i], { extraOn[i] = it; if (it != true) extras.remove(i) },
                            ) { EsusField("Condição extra", extras[i] ?: "", { extras[i] = it }, required = true) }
                        }
                    }
                }
                else -> PerguntasList(Perguntas.socioeconomico, respostas)
            }
        }
        StepFooter(first = step == (if (existing == null) 1 else 2), last = step == 7,
            onPrev = { if (step > 1) step-- else onCancel() },
            onNext = { if (step < 7) step++ else finalizar() })
    }
}

@Composable
private fun PerguntasList(list: List<Pergunta>, respostas: MutableMap<String, Boolean?>) {
    Column(Modifier.padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        list.forEach { p -> YesNoCard(p.pergunta, p.sim, p.nao, respostas[p.id], onChange = { respostas[p.id] = it }) }
        Spacer(Modifier.height(4.dp))
    }
}

@Composable
private fun InfoBanner(text: String) {
    EsusCard(Modifier.padding(horizontal = 12.dp).padding(bottom = 10.dp)) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.Info, null, tint = E.Ink2, modifier = Modifier.padding(end = 8.dp)); Text(text, fontSize = 12.sp, color = E.Ink2)
        }
    }
}

@Composable
private fun RadioRow(text: String, selected: Boolean, onClick: () -> Unit) {
    Row(Modifier.clickable(onClick = onClick), verticalAlignment = Alignment.CenterVertically) {
        RadioButton(selected = selected, onClick = onClick, colors = RadioButtonDefaults.colors(selectedColor = E.Green)); Text(text, fontSize = 16.sp, color = E.Ink)
    }
}

@Composable
fun CheckRow(text: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.clickable { onChange(!checked) }, verticalAlignment = Alignment.CenterVertically) {
        Checkbox(checked = checked, onCheckedChange = onChange, colors = CheckboxDefaults.colors(checkedColor = E.Green)); Text(text, fontSize = 16.sp, color = E.Ink)
    }
}
