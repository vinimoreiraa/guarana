package com.guarana.ocular.core

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID
import kotlin.math.cos
import kotlin.math.sqrt

/** Familia dentro do imovel, como no e-SUS Territorio ("Familia 68", responsavel). */
data class Family(val numero: String, val responsavelCns: String, val pessoas: Int) {
    fun toJson(): JSONObject = JSONObject().put("numero", numero).put("responsavel_cns", responsavelCns).put("pessoas", pessoas)
    companion object { fun fromJson(o: JSONObject) = Family(o.optString("numero"), o.optString("responsavel_cns"), o.optInt("pessoas", 0)) }
}

/** Domicilio como vem do cadastro domiciliar e territorial do e-SUS (UUID da ficha, INE, microarea, coordenadas, familias, ultima visita). */
data class Household(
    val uuid: String, val cnes: String, val ine: String, val microarea: String,
    val logradouro: String, val numero: String, val complemento: String, val bairro: String, val cep: String,
    val lat: Double?, val lon: Double?, val telefone: String,
    val tipoLogradouro: String = "", val pontoReferencia: String = "", val telefoneContato: String = "",
    val ultimaVisita: String = "",          // ISO (yyyy-MM-dd) da ultima visita realizada; vazio = sem registro
    val familias: List<Family> = emptyList(),
) {
    /** "Rua Bahia, 12 (fundos)"; o tipo vem separado no cadastro do e-SUS, nomes antigos ja trazem o tipo no proprio nome. */
    val endereco: String get() = "${(tipoLogradouro + " " + logradouro).trim()}, $numero" + (if (complemento.isNotBlank()) " ($complemento)" else "")
    val logradouroCompleto: String get() = (tipoLogradouro + " " + logradouro).trim()
    /** Dias desde a ultima visita, ou null sem registro. */
    fun diasDesdeVisita(hoje: java.time.LocalDate = java.time.LocalDate.now()): Int? =
        runCatching { java.time.temporal.ChronoUnit.DAYS.between(java.time.LocalDate.parse(ultimaVisita), hoje).toInt() }.getOrNull()
    fun toJson(): JSONObject = JSONObject().put("uuid", uuid).put("cnes", cnes).put("ine", ine).put("microarea", microarea)
        .put("tipo_logradouro", tipoLogradouro).put("logradouro", logradouro).put("numero", numero).put("complemento", complemento).put("bairro", bairro).put("cep", cep)
        .put("latitude", lat ?: JSONObject.NULL).put("longitude", lon ?: JSONObject.NULL).put("telefone", telefone)
        .put("ponto_referencia", pontoReferencia).put("telefone_contato", telefoneContato).put("ultima_visita", ultimaVisita)
        .put("familias", JSONArray(familias.map { it.toJson() }))
    companion object {
        fun fromJson(o: JSONObject) = Household(
            uuid = o.getString("uuid"), cnes = o.optString("cnes"), ine = o.optString("ine"), microarea = o.optString("microarea"),
            logradouro = o.optString("logradouro"), numero = o.optString("numero"), complemento = o.optString("complemento"),
            bairro = o.optString("bairro"), cep = o.optString("cep"),
            lat = if (o.isNull("latitude")) null else o.optDouble("latitude"), lon = if (o.isNull("longitude")) null else o.optDouble("longitude"),
            telefone = o.optString("telefone"),
            tipoLogradouro = o.optString("tipo_logradouro"), pontoReferencia = o.optString("ponto_referencia"), telefoneContato = o.optString("telefone_contato"),
            ultimaVisita = o.optString("ultima_visita"),
            familias = o.optJSONArray("familias")?.let { a -> List(a.length()) { Family.fromJson(a.getJSONObject(it)) } } ?: emptyList(),
        )
    }
}

enum class VisitState { planejada, feita, adiada, recusada, ausente }

/** Visita planejada ou realizada. Vira a ficha de visita domiciliar (LEDI) quando houver exportador. */
data class Visit(
    val uuid: String, val householdId: String, val patientId: String, val date: String, val turno: String,
    val state: VisitState, val motivo: String, val profissional: String, val observacao: String,
    val desfecho: String = "", val updatedAt: Long = System.currentTimeMillis(),
) {
    fun toJson(): JSONObject = JSONObject().put("uuid", uuid).put("domicilio_uuid", householdId).put("paciente_id", patientId).put("data", date)
        .put("turno", turno).put("estado", state.name).put("motivo", motivo).put("profissional", profissional).put("observacao", observacao)
        .put("desfecho", desfecho).put("atualizado_em", updatedAt)
    companion object {
        fun fromJson(o: JSONObject) = Visit(
            uuid = o.getString("uuid"), householdId = o.optString("domicilio_uuid"), patientId = o.optString("paciente_id"), date = o.optString("data"),
            turno = o.optString("turno"), state = runCatching { VisitState.valueOf(o.optString("estado", "planejada")) }.getOrDefault(VisitState.planejada),
            motivo = o.optString("motivo"), profissional = o.optString("profissional"), observacao = o.optString("observacao"),
            desfecho = o.optString("desfecho"), updatedAt = o.optLong("atualizado_em", 0L),
        )
    }
}

data class ImportReport(val unidade: String, val households: Int, val people: Int, val visits: Int)

class TerritoryStore(context: Context) {
    private val dir = File(context.filesDir, "territorio").apply { mkdirs() }
    private val fHouseholds = File(dir, "domicilios.json")
    private val fVisits = File(dir, "visitas.json")
    private val fMeta = File(dir, "unidade.json")

    fun households(): List<Household> = readArray(fHouseholds).map { Household.fromJson(it) }
    fun visits(): List<Visit> = readArray(fVisits).map { Visit.fromJson(it) }.sortedWith(compareBy({ it.date }, { it.turno }))
    fun household(id: String): Household? = households().firstOrNull { it.uuid == id }
    fun unidade(): JSONObject? = fMeta.takeIf { it.exists() }?.let { runCatching { JSONObject(it.readText()) }.getOrNull() }

    fun saveVisits(list: List<Visit>) = fVisits.writeText(JSONArray(list.map { it.toJson() }).toString())
    fun updateVisit(v: Visit) {
        saveVisits(visits().map { if (it.uuid == v.uuid) v else it })
        if (v.state == VisitState.feita) markVisited(v.householdId, v.date)
    }
    /** Registra a data da ultima visita realizada no imovel (o "Visitado ha N dias" do e-SUS Territorio). */
    fun markVisited(householdId: String, date: String) {
        val hs = households(); val h = hs.firstOrNull { it.uuid == householdId } ?: return
        if (h.ultimaVisita.isNotBlank() && h.ultimaVisita >= date) return
        fHouseholds.writeText(JSONArray(hs.map { if (it.uuid == householdId) it.copy(ultimaVisita = date).toJson() else it.toJson() }).toString())
    }
    fun addVisit(v: Visit) { saveVisits(visits() + v) }

    /** Importa a exportacao do territorio (formato de dados/mock-sus/territorio.json). Pessoas viram pacientes, com id derivado do CNS. */
    fun importTerritory(json: JSONObject, patients: PatientStore): ImportReport {
        val unidade = json.optJSONObject("unidade") ?: JSONObject()
        fMeta.writeText(unidade.toString())
        val hs = json.optJSONArray("domicilios") ?: JSONArray()
        val existingH = households().associateBy { it.uuid }.toMutableMap()
        for (i in 0 until hs.length()) { val h = Household.fromJson(hs.getJSONObject(i)); existingH[h.uuid] = h }
        fHouseholds.writeText(JSONArray(existingH.values.map { it.toJson() }).toString())

        val ps = json.optJSONArray("pessoas") ?: JSONArray()
        val byCns = HashMap<String, String>()
        var people = 0
        for (i in 0 until ps.length()) {
            val p = ps.getJSONObject(i)
            val cns = p.optString("cns")
            val id = if (cns.isNotBlank()) UUID.nameUUIDFromBytes("cns:$cns".toByteArray()).toString() else UUID.randomUUID().toString()
            val birth = p.optString("data_nascimento").take(4).toIntOrNull()
            val conds = p.optJSONArray("condicoes")?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList()
            val extras = p.optJSONArray("condicoes_extra")?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList()
            patients.save(Patient(id = id, name = p.optString("nome"), cns = cns, cpf = p.optString("cpf"), birthYear = birth, sex = p.optString("sexo"),
                householdId = p.optString("domicilio_uuid"), conditions = conds, extraConditions = extras,
                birthDate = p.optString("data_nascimento"), familyNumber = p.optString("familia_numero"), responsible = p.optBoolean("responsavel_familiar", false),
                lastFundusExam = p.optString("ultimo_exame_fundo_olho")))
            byCns[cns] = id; people++
        }

        val vs = json.optJSONArray("visitas") ?: JSONArray()
        val existingV = visits().associateBy { it.uuid }.toMutableMap()
        for (i in 0 until vs.length()) {
            val v = vs.getJSONObject(i)
            val visit = Visit(
                uuid = v.getString("uuid"), householdId = v.optString("domicilio_uuid"), patientId = byCns[v.optString("cns_pessoa")] ?: "",
                date = v.optString("data"), turno = v.optString("turno"),
                state = runCatching { VisitState.valueOf(v.optString("estado", "planejada")) }.getOrDefault(VisitState.planejada),
                motivo = v.optString("motivo"), profissional = v.optString("profissional_nome"), observacao = v.optString("observacao"), desfecho = v.optString("desfecho"),
            )
            if (existingV[visit.uuid]?.let { it.updatedAt > visit.updatedAt && it.state != VisitState.planejada } != true) existingV[visit.uuid] = visit
        }
        saveVisits(existingV.values.toList())
        return ImportReport(unidade.optString("nome", "?"), existingH.size, people, existingV.size)
    }

    /** Dados de demonstracao substituem o territorio anterior (o mock muda entre versoes; UUIDs novos duplicariam imoveis). */
    fun loadMock(context: Context, patients: PatientStore): ImportReport {
        clear(patients)
        return importTerritory(JSONObject(context.assets.open("mock_territorio.json").bufferedReader().use { it.readText() }), patients)
    }

    /** Remove domicilios, visitas e unidade; com [patients], remove tambem as pessoas que vieram do cadastro (as criadas a mao ficam). */
    fun clear(patients: PatientStore? = null) {
        fHouseholds.delete(); fVisits.delete(); fMeta.delete()
        patients?.list()?.filter { it.householdId.isNotBlank() }?.forEach { patients.delete(it.id) }
    }

    private fun readArray(f: File): List<JSONObject> = if (!f.exists()) emptyList() else runCatching {
        val a = JSONArray(f.readText()); List(a.length()) { a.getJSONObject(it) }
    }.getOrDefault(emptyList())

    companion object {
        /** Ordem de visita por vizinho mais proximo a partir de um ponto (ou do primeiro domicilio). */
        fun route(visits: List<Visit>, households: Map<String, Household>, fromLat: Double?, fromLon: Double?): List<Visit> {
            val pending = visits.toMutableList(); val out = mutableListOf<Visit>()
            var lat = fromLat; var lon = fromLon
            while (pending.isNotEmpty()) {
                val next = if (lat == null || lon == null) pending.first() else pending.minByOrNull { v ->
                    val h = households[v.householdId]; if (h?.lat == null || h.lon == null) Double.MAX_VALUE else dist(lat!!, lon!!, h.lat, h.lon)
                }!!
                pending.remove(next); out += next
                households[next.householdId]?.let { if (it.lat != null && it.lon != null) { lat = it.lat; lon = it.lon } }
            }
            return out
        }
        fun dist(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
            val kx = 111.32 * cos(Math.toRadians((lat1 + lat2) / 2)); val ky = 110.57
            val dx = (lon1 - lon2) * kx; val dy = (lat1 - lat2) * ky
            return sqrt(dx * dx + dy * dy)   // km
        }
    }
}
