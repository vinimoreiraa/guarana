package com.guarana.ocular.esus

import android.content.Context
import android.content.Intent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.guarana.ocular.core.Analysis
import com.guarana.ocular.core.OcularPriority
import com.guarana.ocular.core.Patient
import com.guarana.ocular.core.SignState
import com.guarana.ocular.core.Signs
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** O que preencher na Ficha de Visita do e-SUS: pessoa, itens de motivo (rotulos como aparecem no formulario), desfecho e resumo. */
data class EsusFill(val patientName: String, val itens: List<String>, val desfecho: String, val resumo: String)

/** Ponte entre a pilula (servico) e a UI: qual e-SUS chamou o Guarana e um contador para a UI reagir a cada toque. */
object CompanionBridge {
    /** Preenchimento pendente: o servico executa quando o e-SUS voltar para a frente. */
    @Volatile var pendingFill: EsusFill? = null

    var esusPackage by mutableStateOf<String?>(null)
        private set
    var requestId by mutableIntStateOf(0)
        private set

    var capture: Boolean = true
        private set

    /** Pessoa aberta no e-SUS quando a pilula foi tocada: "nome|cns|sexo|idade". */
    var pessoa: String? = null
        private set

    fun open(pkg: String?, capture: Boolean = true, pessoa: String? = null) { esusPackage = pkg; this.capture = capture; this.pessoa = pessoa; requestId++ }

    /** Sessao vinda do e-SUS terminou (voltou para la): o proximo uso do Guarana pelo launcher se comporta normalmente. */
    fun clear() { esusPackage = null }

    /** Traz o e-SUS de volta para a frente, no estado em que estava (a task dele continua viva). */
    fun backToEsus(ctx: Context): Boolean {
        val pkg = esusPackage ?: installedEsus(ctx) ?: return false
        val i = ctx.packageManager.getLaunchIntentForPackage(pkg) ?: return false
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(i)
        return true
    }

    fun installedEsus(ctx: Context): String? = EsusCompanionService.ESUS_PACKAGES.firstOrNull { ctx.packageManager.getLaunchIntentForPackage(it) != null }

    /** Agenda o preenchimento da visita e volta para o e-SUS; o servico de acessibilidade faz o resto. */
    fun registerVisit(ctx: Context, fill: EsusFill): Boolean {
        pendingFill = fill
        val ok = backToEsus(ctx)
        if (!ok) pendingFill = null
        return ok
    }
}

/** Resumo curto da triagem para colar no e-SUS (condicao extra do cadastro ou observacao), ou para a injecao automatica. */
object EsusSummary {
    private val fmt = SimpleDateFormat("dd/MM/yyyy", Locale("pt", "BR"))

    fun triagem(t: String) = when (t) { "encaminhar_urgente" -> "encaminhar com urgência"; "encaminhar" -> "encaminhar"; "observar" -> "observar"; else -> "sem sinais" }

    /** Motivo da Ficha de Visita Domiciliar que corresponde ao resultado. */
    fun motivoVisita(a: Analysis): String = if (a.triage.startsWith("encaminhar")) "Busca ativa: Exame" else "Orientação / prevenção"

    /** Itens da Ficha de Visita a marcar: busca ativa de exame (ou orientacao) mais os acompanhamentos que a ficha do cidadao pede. */
    fun fill(a: Analysis, p: Patient?): EsusFill {
        val itens = mutableListOf(if (a.triage.startsWith("encaminhar")) "Exame" else "Orientação / prevenção")
        if (p != null) {
            if (OcularPriority.has(p, "diabet")) itens += "Pessoa com diabetes"
            if (OcularPriority.has(p, "hipertens")) itens += "Pessoa com hipertensão"
            if (OcularPriority.has(p, "acamad", "domiciliad")) itens += "Domiciliados/acamados"
            if (OcularPriority.has(p, "hansen")) itens += "Pessoa com hanseníase"
            if (OcularPriority.has(p, "deficiencia")) itens += "Pessoa em reabilitação ou com deficiência"
        }
        return EsusFill(p?.name.orEmpty(), itens, "Visita realizada", text(a, p))
    }

    fun text(a: Analysis, patient: Patient?): String {
        val sinais = a.signs.filter { it.state == SignState.present }.map { Signs.name(it.id) }
        val partes = mutableListOf("Triagem ocular Guaraná ${fmt.format(Date(a.createdAt))}: ${triagem(a.triage)}")
        if (sinais.isNotEmpty()) partes += "sinais: " + sinais.joinToString(", ")
        if (a.triageReasons.isNotEmpty()) partes += a.triageReasons.first().substringBefore(":")
        partes += "visita: ${motivoVisita(a)}"
        return partes.joinToString(" · ")
    }
}
