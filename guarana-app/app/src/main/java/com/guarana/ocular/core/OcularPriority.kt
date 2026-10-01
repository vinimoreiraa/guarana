package com.guarana.ocular.core

import java.text.Normalizer
import java.time.LocalDate
import java.time.temporal.ChronoUnit

/**
 * Prioridade ocular a partir das condicoes autorreferidas da Ficha de Cadastro Individual e da idade.
 * Serve para ordenar a agenda e destacar quem deve ser fotografado primeiro. Regras provisorias, a validar com oftalmologista.
 * Nao e diagnostico e nao entra no laudo: e organizacao do trabalho do agente.
 */
object OcularPriority {
    data class Factor(val label: String, val weight: Int)

    private fun norm(s: String) = Normalizer.normalize(s.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{M}"), "")

    fun has(p: Patient, vararg keys: String): Boolean {
        val all = p.allConditions.map { norm(it) }
        return all.any { c -> keys.any { k -> c.contains(norm(k)) } }
    }

    /** Diabetico sem fundoscopia registrada nos ultimos 12 meses (Ministerio da Saude: exame de fundo de olho anual). */
    fun diabetesSemFundoDeOlho(p: Patient, hoje: LocalDate = LocalDate.now()): Boolean {
        if (!has(p, "diabet")) return false
        val last = runCatching { LocalDate.parse(p.lastFundusExam) }.getOrNull() ?: return true
        return ChronoUnit.DAYS.between(last, hoje) > 365
    }

    fun factors(p: Patient, hoje: LocalDate = LocalDate.now()): List<Factor> {
        val f = mutableListOf<Factor>()
        val age = p.ageYears
        if (has(p, "diabet")) f += if (diabetesSemFundoDeOlho(p, hoje)) Factor("diabetes sem fundo de olho há mais de 12 meses", 4) else Factor("diabetes", 2)
        if (has(p, "deficiencia visual", "visual", "baixa visao", "cego")) f += Factor("deficiência visual", 3)
        if (has(p, "hansen")) f += Factor("hanseníase (risco ocular)", 2)
        if (has(p, "acamad", "domiciliad")) f += Factor("acamado ou domiciliado", 2)
        if (has(p, "hipertens")) f += Factor("hipertensão", 1)
        if (has(p, "avc", "derrame")) f += Factor("AVC prévio", 1)
        if (has(p, "internac")) f += Factor("internação recente", 1)
        if (has(p, "catarata", "glaucoma", "oftalmo", "vista embacada", "colirio")) f += Factor("histórico ocular na ficha", 2)
        if (age != null && age >= 60) f += Factor("60 anos ou mais", 2)
        if (age != null && age < 6) f += Factor("menor de 6 anos (leucocoria)", 2)
        return f
    }

    fun score(p: Patient, hoje: LocalDate = LocalDate.now()): Int = factors(p, hoje).sumOf { it.weight }

    /** "alta" (>=4), "media" (2..3) ou "" (sem fatores relevantes). */
    fun level(score: Int): String = when { score >= 4 -> "alta"; score >= 2 -> "média"; else -> "" }
    fun level(p: Patient, hoje: LocalDate = LocalDate.now()): String = level(score(p, hoje))

    /** Ordena visitas: prioridade ocular, depois tempo sem visita, depois turno. */
    fun sortVisits(visits: List<Visit>, households: Map<String, Household>, patients: Map<String, Patient>, hoje: LocalDate = LocalDate.now()): List<Visit> =
        visits.sortedWith(
            compareByDescending<Visit> { v -> patients[v.patientId]?.let { score(it, hoje) } ?: 0 }
                .thenByDescending { v -> households[v.householdId]?.diasDesdeVisita(hoje) ?: 0 }
                .thenBy { it.turno }
        )
}
