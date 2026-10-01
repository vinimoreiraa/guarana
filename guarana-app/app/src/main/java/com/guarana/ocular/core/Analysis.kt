package com.guarana.ocular.core

import org.json.JSONArray
import org.json.JSONObject

/** Contrato unico (contrato/resultado.schema.json): app, motor local e nuvem produzem exatamente isto. */
enum class SignState { present, candidate, absent }

data class Sign(val id: String, val state: SignState, val confidence: Float, val region: String, val evidence: String)

data class Quality(val ok: Boolean, val issues: List<String>, val metrics: Map<String, Float> = emptyMap())

/** Um quadro da rotina de luz: rotulo do passo ("Branco 60%") e caminho do JPEG. */
data class Frame(val label: String, val path: String)

data class Analysis(
    val engine: String,
    val status: String,
    val modelVersion: String,
    val quality: Quality,
    val signs: List<Sign>,
    val triage: String,
    val needsCloudReview: Boolean,
    val createdAt: Long = System.currentTimeMillis(),
    val imagePath: String = "",
    val child: Boolean = false,
    val frames: List<Frame> = emptyList(),
    val indices: Map<String, Any?> = emptyMap(),
    val patientId: String = "",
    val notes: String = "",
    val gaze: String = "",              // "centro", "esquerda", "direita", "cima" quando a foto veio de uma sequencia de olhares
    val triageReasons: List<String> = emptyList(),   // motivos vindos da ficha do cidadao (Triage.withHistory); vazio = so a foto
    // observabilidade: mapa de ativacao por rotulo (grade explainH x explainW, row-major, logit local), tempo de inferencia, enquadramento
    val explain: Map<String, FloatArray> = emptyMap(),
    val explainW: Int = 0,
    val explainH: Int = 0,
    val explainBoxes: Map<String, FloatArray> = emptyMap(),   // por rotulo: [x0, y0, w, h] em fracoes da foto, a vista que deu a probabilidade
    val inferenceMs: Long = 0,
    val framing: String = "",
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("engine", engine)
        put("status", status)
        put("model_version", modelVersion)
        put("quality", JSONObject().put("ok", quality.ok).put("issues", JSONArray(quality.issues))
            .put("metrics", JSONObject().also { m -> quality.metrics.forEach { (k, v) -> m.put(k, v.toDouble()) } }))
        put("signs", JSONArray().also { arr ->
            signs.forEach { s ->
                arr.put(JSONObject().put("id", s.id).put("state", s.state.name).put("confidence", s.confidence.toDouble())
                    .put("region", s.region).put("evidence", s.evidence))
            }
        })
        put("triage", triage)
        put("needs_cloud_review", needsCloudReview)
        put("created_at", createdAt)
        put("image_path", imagePath)
        put("child", child)
        put("frames", JSONArray().also { arr -> frames.forEach { f -> arr.put(JSONObject().put("label", f.label).put("path", f.path)) } })
        put("indices", JSONObject().also { o -> indices.forEach { (k, v) -> o.put(k, v ?: JSONObject.NULL) } })
        put("patient_id", patientId)
        put("notes", notes)
        put("gaze", gaze)
        put("triage_reasons", JSONArray(triageReasons))
        put("explain", JSONObject().also { o -> explain.forEach { (k, v) -> o.put(k, JSONArray().also { a -> v.forEach { f -> a.put(f.toDouble()) } }) } })
        put("explain_shape", JSONArray().put(explainH).put(explainW))
        put("explain_boxes", JSONObject().also { o -> explainBoxes.forEach { (k, v) -> o.put(k, JSONArray().also { a -> v.forEach { f -> a.put(f.toDouble()) } }) } })
        put("inference_ms", inferenceMs)
        put("framing", framing)
    }

    companion object {
        fun fromJson(o: JSONObject): Analysis {
            val q = o.optJSONObject("quality") ?: JSONObject().put("ok", true).put("issues", JSONArray())
            val issues = q.optJSONArray("issues") ?: JSONArray()
            val signsArr = o.optJSONArray("signs") ?: JSONArray()
            return Analysis(
                engine = o.optString("engine", "cloud-vlm"),
                status = o.optString("status", "provisional"),
                modelVersion = o.optString("model_version", "?"),
                quality = Quality(q.optBoolean("ok", true), List(issues.length()) { issues.getString(it) },
                    (q.optJSONObject("metrics") ?: JSONObject()).let { m -> m.keys().asSequence().associateWith { k -> m.optDouble(k).toFloat() } }),
                signs = List(signsArr.length()) { i ->
                    val s = signsArr.getJSONObject(i)
                    Sign(
                        id = s.getString("id"),
                        state = runCatching { SignState.valueOf(s.optString("state", "absent")) }.getOrDefault(SignState.absent),
                        confidence = s.optDouble("confidence", 0.0).toFloat(),
                        region = s.optString("region", ""),
                        evidence = s.optString("evidence", ""),
                    )
                },
                triage = o.optString("triage", "sem_sinais"),
                needsCloudReview = o.optBoolean("needs_cloud_review", true),
                createdAt = o.optLong("created_at", System.currentTimeMillis()),
                imagePath = o.optString("image_path", ""),
                child = o.optBoolean("child", false),
                frames = (o.optJSONArray("frames") ?: JSONArray()).let { arr ->
                    List(arr.length()) { i -> arr.getJSONObject(i).let { Frame(it.optString("label"), it.optString("path")) } }
                },
                indices = (o.optJSONObject("indices") ?: JSONObject()).let { io -> io.keys().asSequence().associateWith { k -> io.opt(k).takeIf { it != JSONObject.NULL } } },
                patientId = o.optString("patient_id", ""),
                notes = o.optString("notes", ""),
                gaze = o.optString("gaze", ""),
                triageReasons = o.optJSONArray("triage_reasons")?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList(),
                explain = (o.optJSONObject("explain") ?: JSONObject()).let { e -> e.keys().asSequence().associateWith { k -> val a = e.getJSONArray(k); FloatArray(a.length()) { a.getDouble(it).toFloat() } } },
                explainBoxes = (o.optJSONObject("explain_boxes") ?: JSONObject()).let { e -> e.keys().asSequence().associateWith { k -> val a = e.getJSONArray(k); FloatArray(a.length()) { a.getDouble(it).toFloat() } } },
                explainH = o.optJSONArray("explain_shape")?.optInt(0) ?: 0,
                explainW = o.optJSONArray("explain_shape")?.optInt(1) ?: 0,
                inferenceMs = o.optLong("inference_ms", 0),
                framing = o.optString("framing", ""),
            )
        }
    }
}

object Signs {
    val NAMES = mapOf(
        "hiperemia" to "Vermelhidão (hiperemia)",
        "ictericia" to "Icterícia (esclera amarela)",
        "pterigio_pinguecula" to "Pterígio / pinguécula",
        "catarata_leucocoria" to "Catarata / leucocoria",
        "hemorragia_subconjuntival" to "Hemorragia subconjuntival",
        "lesao_pigmentada" to "Lesão pigmentada",
        "opacidade_corneana" to "Opacidade da córnea",
        "pterigio" to "Pterígio",
        "pinguecula" to "Pinguécula",
        "tumor_superficie_ocular" to "Tumor da superfície ocular",
        "ceratite" to "Ceratite",
        "cisto_conjuntival" to "Cisto conjuntival",
        "lente_intraocular" to "Lente intraocular (operado de catarata)",
        "conjuntivite" to "Conjuntivite",
        "uveite" to "Uveíte",
        "alteracao_palpebral" to "Alteração palpebral",
        "palidez_conjuntival" to "Palidez conjuntival",
        "arco_corneano" to "Arco corneano",
        "esclera_azul" to "Esclera azul",
        "manchas_bitot" to "Manchas de Bitot",
        "ocronose" to "Ocronose",
        "telangiectasia" to "Telangiectasias",
    )
    val REGIONS = mapOf(
        "hiperemia" to "conjuntiva", "ictericia" to "esclera", "pterigio_pinguecula" to "conjuntiva",
        "catarata_leucocoria" to "pupila", "hemorragia_subconjuntival" to "esclera", "lesao_pigmentada" to "conjuntiva",
        "opacidade_corneana" to "cornea", "palidez_conjuntival" to "conjuntiva", "arco_corneano" to "limbo",
        "pterigio" to "conjuntiva", "pinguecula" to "conjuntiva", "tumor_superficie_ocular" to "conjuntiva", "ceratite" to "cornea",
        "cisto_conjuntival" to "conjuntiva", "lente_intraocular" to "pupila", "conjuntivite" to "conjuntiva", "uveite" to "limbo", "alteracao_palpebral" to "palpebra",
        "esclera_azul" to "esclera", "manchas_bitot" to "conjuntiva", "ocronose" to "esclera", "telangiectasia" to "conjuntiva",
    )
    fun name(id: String) = NAMES[id] ?: id.replace('_', ' ')
    /** Regiao em palavras do dia a dia, para o agente. */
    fun regionPlain(id: String): String = when (REGIONS[id]) {
        "conjuntiva", "esclera" -> "na parte branca do olho"
        "pupila" -> "na pupila"
        "cornea" -> "na parte transparente do olho"
        "limbo" -> "na borda da íris"
        "palpebra" -> "na pálpebra"
        else -> "no olho"
    }
}
