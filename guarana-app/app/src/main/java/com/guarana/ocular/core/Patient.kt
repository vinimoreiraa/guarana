package com.guarana.ocular.core

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.LocalDate
import java.time.Period
import java.util.UUID

/** Ficha minima do paciente. Identificacao por codigo interno; CNS e CPF sao opcionais e ficam so no aparelho. */
data class Patient(
    val id: String,
    val name: String,
    val cns: String = "",
    val cpf: String = "",
    val birthYear: Int? = null,
    val sex: String = "",          // "F", "M" ou ""
    val createdAt: Long = System.currentTimeMillis(),
    val householdId: String = "",  // UUID do cadastro domiciliar do e-SUS
    val conditions: List<String> = emptyList(),      // condicoes autorreferidas da Ficha de Cadastro Individual
    val extraConditions: List<String> = emptyList(), // "condicao extra" em texto livre (remedios, peso, observacoes)
    val birthDate: String = "",                      // ISO yyyy-MM-dd quando veio do cadastro; birthYear e o minimo
    val familyNumber: String = "",                   // "Familia 68" do e-SUS Territorio
    val responsible: Boolean = false,                // responsavel familiar
    val lastFundusExam: String = "",                 // ISO da ultima fundoscopia registrada (DW municipal); vazio = sem registro
) {
    val isChild: Boolean get() = birthYear?.let { java.util.Calendar.getInstance().get(java.util.Calendar.YEAR) - it < 12 } ?: false
    val code: String get() = id.take(8).uppercase()
    val sexLabel: String get() = when (sex) { "F" -> "Feminino"; "M" -> "Masculino"; else -> "" }
    val ageYears: Int? get() = runCatching { Period.between(LocalDate.parse(birthDate), LocalDate.now()).years }.getOrNull()
        ?: birthYear?.let { LocalDate.now().year - it }
    /** "52 anos e 4 meses", "8 meses", ou "nasc. 1974" quando so ha o ano. */
    val ageText: String get() {
        val d = runCatching { LocalDate.parse(birthDate) }.getOrNull()
        if (d != null) {
            val p = Period.between(d, LocalDate.now())
            return when {
                p.years == 0 && p.months == 0 -> "${p.days} dias"
                p.years == 0 -> "${p.months} meses"
                p.months == 0 -> "${p.years} anos"
                else -> "${p.years} anos e ${p.months} " + if (p.months == 1) "mês" else "meses"
            }
        }
        return birthYear?.let { "nasc. $it" } ?: ""
    }
    val allConditions: List<String> get() = conditions + extraConditions
    fun toJson(): JSONObject = JSONObject().put("id", id).put("name", name).put("cns", cns).put("cpf", cpf)
        .put("birth_year", birthYear ?: JSONObject.NULL).put("sex", sex).put("created_at", createdAt)
        .put("household_id", householdId).put("conditions", JSONArray(conditions)).put("extra_conditions", JSONArray(extraConditions))
        .put("birth_date", birthDate).put("family_number", familyNumber).put("responsible", responsible).put("last_fundus_exam", lastFundusExam)

    companion object {
        fun fromJson(o: JSONObject) = Patient(
            id = o.getString("id"), name = o.optString("name"), cns = o.optString("cns"), cpf = o.optString("cpf"),
            birthYear = if (o.isNull("birth_year")) null else o.optInt("birth_year"), sex = o.optString("sex"),
            createdAt = o.optLong("created_at", System.currentTimeMillis()),
            householdId = o.optString("household_id"),
            conditions = o.optJSONArray("conditions")?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList(),
            extraConditions = o.optJSONArray("extra_conditions")?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList(),
            birthDate = o.optString("birth_date"), familyNumber = o.optString("family_number"), responsible = o.optBoolean("responsible", false),
            lastFundusExam = o.optString("last_fundus_exam"),
        )
    }
}

class PatientStore(context: Context) {
    private val dir = File(context.filesDir, "pacientes").apply { mkdirs() }

    fun list(): List<Patient> = (dir.listFiles { f -> f.extension == "json" } ?: emptyArray())
        .mapNotNull { runCatching { Patient.fromJson(JSONObject(it.readText())) }.getOrNull() }
        .sortedBy { it.name.lowercase() }

    fun get(id: String?): Patient? = id?.let { File(dir, "$it.json") }?.takeIf { it.exists() }?.let { runCatching { Patient.fromJson(JSONObject(it.readText())) }.getOrNull() }

    fun save(p: Patient): Patient { File(dir, "${p.id}.json").writeText(p.toJson().toString(2)); return p }
    fun delete(id: String) { File(dir, "$id.json").delete() }

    fun create(name: String, cns: String = "", cpf: String = "", birthYear: Int? = null, sex: String = ""): Patient =
        save(Patient(UUID.randomUUID().toString(), name.trim(), cns.trim(), cpf.trim(), birthYear, sex))

    /** Busca por nome, codigo ou CNS. */
    fun find(query: String): Patient? {
        val q = query.trim().lowercase()
        if (q.isEmpty()) return null
        val all = list()
        return all.firstOrNull { it.code.lowercase() == q || it.cns == q }
            ?: all.firstOrNull { it.name.lowercase() == q }
            ?: all.firstOrNull { it.name.lowercase().startsWith(q) }
            ?: all.firstOrNull { it.name.lowercase().contains(q) }
    }
}
