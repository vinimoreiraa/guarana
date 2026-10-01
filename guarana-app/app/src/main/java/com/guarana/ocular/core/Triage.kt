package com.guarana.ocular.core

/**
 * Regra de triagem. Nunca diagnostico: define apenas se a pessoa deve ser encaminhada.
 *  Pela foto:
 *  - leucocoria/catarata em crianca -> encaminhar urgente (retinoblastoma ou catarata congenita)
 *  - lesao pigmentada, catarata, ictericia, opacidade da cornea, pterigio -> encaminhar
 *  - hiperemia ou hemorragia subconjuntival isoladas -> observar (quase sempre benignas)
 *  - so sinais fracos -> observar
 *  Pela ficha do cidadao (condicoes autorreferidas do e-SUS), regras provisorias a validar com oftalmologista:
 *  - diabetes sem fundo de olho registrado nos ultimos 12 meses -> pelo menos encaminhar, mesmo sem sinal na foto
 *  - deficiencia visual ou hanseniase + qualquer sinal (mesmo fraco) -> encaminhar
 *  - hipertensao + hemorragia subconjuntival -> observar, com orientacao de aferir a pressao
 */
object Triage {
    /** ceratite e uveite pedem avaliacao no mesmo dia (dor, risco de sequela); lente intraocular e so contexto */
    private val URGENTE = setOf("ceratite", "uveite", "trauma_ocular")
    private val ENCAMINHAR = setOf("lesao_pigmentada", "catarata_leucocoria", "ictericia", "opacidade_corneana", "pterigio_pinguecula",
        "pterigio", "tumor_superficie_ocular", "esclera_azul", "manchas_bitot", "ocronose", "telangiectasia", "palidez_conjuntival", "arco_corneano")
    private val OBSERVAR = setOf("hiperemia", "hemorragia_subconjuntival", "pinguecula", "conjuntivite", "cisto_conjuntival", "alteracao_palpebral")
    private val ORDER = listOf("sem_sinais", "observar", "encaminhar", "encaminhar_urgente")

    fun decide(signs: List<Sign>, child: Boolean): String {
        val present = signs.filter { it.state == SignState.present }.map { it.id }.toSet()
        return when {
            child && "catarata_leucocoria" in present -> "encaminhar_urgente"
            present.any { it in URGENTE } -> "encaminhar_urgente"
            present.any { it in ENCAMINHAR } -> "encaminhar"
            present.any { it in OBSERVAR } -> "observar"
            signs.any { it.state == SignState.candidate } -> "observar"
            else -> "sem_sinais"
        }
    }

    data class Decision(val triage: String, val reasons: List<String>)

    private fun max(a: String, b: String) = if (ORDER.indexOf(b) > ORDER.indexOf(a)) b else a

    /** Combina a triagem da foto com as condicoes da ficha. [base] e a decisao pela foto. */
    fun withHistory(base: String, signs: List<Sign>, patient: Patient?): Decision {
        patient ?: return Decision(base, emptyList())
        var t = base
        val why = mutableListOf<String>()
        val present = signs.filter { it.state == SignState.present }.map { it.id }.toSet()
        val any = signs.any { it.state != SignState.absent }
        if (OcularPriority.diabetesSemFundoDeOlho(patient)) {
            t = max(t, "encaminhar"); why += "Diabetes sem exame de fundo de olho registrado nos últimos 12 meses: rastreamento anual de retinopatia."
        }
        if (any && OcularPriority.has(patient, "deficiencia visual", "baixa visao")) {
            t = max(t, "encaminhar"); why += "Deficiência visual na ficha e sinal na foto: avaliar antes que piore."
        }
        if (any && OcularPriority.has(patient, "hansen")) {
            t = max(t, "encaminhar"); why += "Hanseníase pode comprometer o olho (lagoftalmo, iridociclite): sinal na foto pede avaliação."
        }
        if ("hemorragia_subconjuntival" in present && OcularPriority.has(patient, "hipertens")) {
            t = max(t, "observar"); why += "Hemorragia subconjuntival em pessoa com hipertensão: aferir a pressão arterial na visita."
        }
        return Decision(t, why)
    }
}
