package com.guarana.ocular.core.fhir

import android.content.Context
import android.util.Base64
import com.guarana.ocular.core.Analysis
import com.guarana.ocular.core.Patient
import com.guarana.ocular.core.SignState
import com.guarana.ocular.core.Signs
import com.guarana.ocular.core.Store
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID

/**
 * Exporta uma analise como Bundle HL7 FHIR R4 nos moldes da RNDS (Rede Nacional de Dados em Saude):
 * identificadores CNS, CPF e CNES nos NamingSystems da RNDS, Patient, Organization, Encounter, Observation por sinal e por
 * indice, DocumentReference com a foto e ServiceRequest quando ha encaminhamento.
 * O envio real a RNDS exige credenciamento do estabelecimento e certificado ICP-Brasil; este arquivo e o que o backend enviara.
 * Codigos SNOMED CT para os sinais ainda nao foram validados: os Observation usam o sistema proprio do Guarana.
 */
object FhirExport {
    private const val NS_CNS = "http://rnds.saude.gov.br/fhir/r4/NamingSystem/cns"
    private const val NS_CPF = "http://rnds.saude.gov.br/fhir/r4/NamingSystem/cpf"
    private const val NS_CNES = "http://rnds.saude.gov.br/fhir/r4/NamingSystem/cnes"
    private const val SYS_SINAIS = "https://guarana.app/fhir/CodeSystem/sinais-oculares"
    private const val SYS_INDICES = "https://guarana.app/fhir/CodeSystem/indices-reflectancia"
    private val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).apply { timeZone = TimeZone.getDefault() }

    fun bundle(a: Analysis, patient: Patient?, cnes: String, deviceVersion: String, embedImage: Boolean = true): JSONObject {
        val pid = "urn:uuid:" + (patient?.id ?: UUID.nameUUIDFromBytes("anon-${a.createdAt}".toByteArray()).toString())
        val oid = "urn:uuid:" + UUID.nameUUIDFromBytes("org-$cnes".toByteArray())
        val eid = "urn:uuid:" + UUID.nameUUIDFromBytes("enc-${a.createdAt}".toByteArray())
        val when_ = iso.format(Date(a.createdAt))
        val entries = JSONArray()
        fun add(fullUrl: String, res: JSONObject) { entries.put(JSONObject().put("fullUrl", fullUrl).put("resource", res)) }

        add(pid, JSONObject().put("resourceType", "Patient").put("id", pid.removePrefix("urn:uuid:")).apply {
            val ids = JSONArray()
            if (!patient?.cns.isNullOrBlank()) ids.put(JSONObject().put("system", NS_CNS).put("value", patient!!.cns))
            if (!patient?.cpf.isNullOrBlank()) ids.put(JSONObject().put("system", NS_CPF).put("value", patient!!.cpf))
            ids.put(JSONObject().put("system", "https://guarana.app/fhir/paciente").put("value", patient?.code ?: "anon"))
            put("identifier", ids)
            if (!patient?.name.isNullOrBlank()) put("name", JSONArray().put(JSONObject().put("text", patient!!.name)))
            patient?.birthYear?.let { put("birthDate", it.toString()) }
            when (patient?.sex) { "F" -> put("gender", "female"); "M" -> put("gender", "male") }
        })
        if (cnes.isNotBlank()) add(oid, JSONObject().put("resourceType", "Organization").put("id", oid.removePrefix("urn:uuid:"))
            .put("identifier", JSONArray().put(JSONObject().put("system", NS_CNES).put("value", cnes))))
        add(eid, JSONObject().put("resourceType", "Encounter").put("id", eid.removePrefix("urn:uuid:")).put("status", "finished")
            .put("class", JSONObject().put("system", "http://terminology.hl7.org/CodeSystem/v3-ActCode").put("code", "AMB"))
            .put("subject", JSONObject().put("reference", pid))
            .put("period", JSONObject().put("start", when_).put("end", when_))
            .apply { if (cnes.isNotBlank()) put("serviceProvider", JSONObject().put("reference", oid)) })

        val obsRefs = JSONArray()
        a.signs.forEach { s ->
            val id = "urn:uuid:" + UUID.nameUUIDFromBytes("obs-${a.createdAt}-${s.id}".toByteArray())
            val interp = when (s.state) { SignState.present -> "POS"; SignState.candidate -> "IND"; SignState.absent -> "NEG" }
            add(id, JSONObject().put("resourceType", "Observation").put("id", id.removePrefix("urn:uuid:")).put("status", "preliminary")
                .put("category", JSONArray().put(JSONObject().put("coding", JSONArray().put(JSONObject().put("system", "http://terminology.hl7.org/CodeSystem/observation-category").put("code", "exam")))))
                .put("code", JSONObject().put("coding", JSONArray().put(JSONObject().put("system", SYS_SINAIS).put("code", s.id).put("display", Signs.name(s.id)))).put("text", Signs.name(s.id)))
                .put("subject", JSONObject().put("reference", pid)).put("encounter", JSONObject().put("reference", eid)).put("effectiveDateTime", when_)
                .put("valueCodeableConcept", JSONObject().put("coding", JSONArray().put(JSONObject().put("system", SYS_SINAIS).put("code", s.state.name))).put("text", s.state.name))
                .put("interpretation", JSONArray().put(JSONObject().put("coding", JSONArray().put(JSONObject().put("system", "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation").put("code", interp)))))
                .put("component", JSONArray().put(JSONObject().put("code", JSONObject().put("text", "probabilidade")).put("valueQuantity", JSONObject().put("value", s.confidence.toDouble()).put("unit", "1"))))
                .put("device", JSONObject().put("display", "Guaraná $deviceVersion · modelo ${a.modelVersion} · ${a.engine}"))
                .put("note", JSONArray().put(JSONObject().put("text", "Triagem experimental por foto comum; não é diagnóstico. Região: ${s.region}. ${s.evidence}"))))
            if (s.state != SignState.absent) obsRefs.put(JSONObject().put("reference", id))
        }
        a.indices.filterValues { it is Number }.forEach { (k, v) ->
            val id = "urn:uuid:" + UUID.nameUUIDFromBytes("idx-${a.createdAt}-$k".toByteArray())
            add(id, JSONObject().put("resourceType", "Observation").put("id", id.removePrefix("urn:uuid:")).put("status", "preliminary")
                .put("code", JSONObject().put("coding", JSONArray().put(JSONObject().put("system", SYS_INDICES).put("code", k))).put("text", k))
                .put("subject", JSONObject().put("reference", pid)).put("encounter", JSONObject().put("reference", eid)).put("effectiveDateTime", when_)
                .put("valueQuantity", JSONObject().put("value", (v as Number).toDouble()).put("unit", "1"))
                .put("note", JSONArray().put(JSONObject().put("text", "Índice de reflectância relativo ao anel de luz, sem calibração clínica"))))
        }
        // foto principal
        val did = "urn:uuid:" + UUID.nameUUIDFromBytes("doc-${a.createdAt}".toByteArray())
        val att = JSONObject().put("contentType", "image/jpeg").put("title", "Foto do olho · quadro principal").put("creation", when_)
        if (embedImage) Store.thumbnail(a.imagePath, 800)?.let { b ->
            val bos = ByteArrayOutputStream(); b.compress(android.graphics.Bitmap.CompressFormat.JPEG, 85, bos)
            att.put("data", Base64.encodeToString(bos.toByteArray(), Base64.NO_WRAP))
        } else att.put("url", "file://${a.imagePath}")
        add(did, JSONObject().put("resourceType", "DocumentReference").put("id", did.removePrefix("urn:uuid:")).put("status", "current")
            .put("type", JSONObject().put("text", "Fotografia do olho externo")).put("subject", JSONObject().put("reference", pid)).put("date", when_)
            .put("content", JSONArray().put(JSONObject().put("attachment", att))))
        // encaminhamento
        if (a.triage == "encaminhar" || a.triage == "encaminhar_urgente") {
            val sid = "urn:uuid:" + UUID.nameUUIDFromBytes("sr-${a.createdAt}".toByteArray())
            add(sid, JSONObject().put("resourceType", "ServiceRequest").put("id", sid.removePrefix("urn:uuid:")).put("status", "active").put("intent", "proposal")
                .put("priority", if (a.triage == "encaminhar_urgente") "urgent" else "routine")
                .put("code", JSONObject().put("text", "Encaminhamento para avaliação oftalmológica (triagem por imagem)"))
                .put("subject", JSONObject().put("reference", pid)).put("encounter", JSONObject().put("reference", eid)).put("authoredOn", when_)
                .put("reasonReference", obsRefs)
                .apply { if (cnes.isNotBlank()) put("requester", JSONObject().put("reference", oid)) })
        }
        return JSONObject().put("resourceType", "Bundle").put("type", "collection").put("timestamp", when_).put("entry", entries)
    }

    fun toFile(context: Context, a: Analysis, patient: Patient?, cnes: String, deviceVersion: String): File {
        val out = File(context.cacheDir, "fhir").apply { mkdirs() }
        return File(out, "guarana_fhir_${a.createdAt}.json").also { it.writeText(bundle(a, patient, cnes, deviceVersion).toString(2)) }
    }
}
