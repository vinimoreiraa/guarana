package com.guarana.ocular.core

import android.content.Context
import android.graphics.Bitmap
import com.guarana.ocular.core.color.ReflectanceIndices
import java.io.File

/** Captura -> qualidade -> modelo local (sempre) -> nuvem (se configurada e disponivel) -> persistencia. */
private fun redFree(src: Bitmap): Bitmap {
    val w = src.width; val h = src.height
    val px = IntArray(w * h); src.getPixels(px, 0, w, 0, 0, w, h)
    for (i in px.indices) { val g = (px[i] shr 8) and 0xFF; px[i] = (0xFF shl 24) or (g shl 16) or (g shl 8) or g }
    return Bitmap.createBitmap(px, w, h, Bitmap.Config.ARGB_8888)
}

/** Aplica as regras da ficha do cidadao (diabetes sem fundo de olho etc.) por cima da triagem da foto. */
private fun Analysis.withHistory(patient: Patient?): Analysis {
    val d = Triage.withHistory(triage, signs, patient)
    return copy(triage = d.triage, triageReasons = d.reasons)
}

/** Foto recusada pelo gate de enquadramento: a mensagem e a instrucao para o agente. */
class FramingRejected(val result: EyeFraming.Result) : Exception(result.reason.message)

class Pipeline(context: Context) {
    private val app = context.applicationContext
    val store = Store(app)
    val settings = Settings(app)
    val local: LocalAnalyzer by lazy { LocalAnalyzer(app) }
    val patients = PatientStore(app)
    val territory = TerritoryStore(app)
    val framingGate: EyeFraming by lazy { EyeFraming(app) }
    /** segmentador de fenda/iris (ROI de esclera do ramo A) */
    val segmenter: EyeSegmenter by lazy { EyeSegmenter(app) }

    /** [frames]: quadros da rotina de luz (rotulo, arquivo); [file] e o quadro principal analisado. */
    fun run(file: File, child: Boolean, frames: List<Pair<String, File>> = emptyList(), patientId: String = ""): Analysis {
        var chosen = file
        var bitmap: Bitmap = Store.decodeOriented(file) ?: throw IllegalArgumentException("Não foi possível ler a imagem")
        var q0 = QualityGate.check(bitmap)
        // flash/LED batendo numa tela ou superficie brilhante: se o quadro com luz esta estourado e o quadro sem luz esta limpo, usa o sem luz
        if ((q0.metrics["reflexo"] ?: 0f) > 0.04f) {
            val amb = frames.firstOrNull { (l, _) -> l.contains("ambiente", true) || l.contains("sem luz", true) }?.second
            val ambBmp = amb?.let { Store.decodeOriented(it) }
            if (ambBmp != null) {
                val qa = QualityGate.check(ambBmp)
                if ((qa.metrics["reflexo"] ?: 1f) < (q0.metrics["reflexo"] ?: 0f) / 2f && "escura" !in qa.issues) { chosen = amb; bitmap = ambBmp; q0 = qa.copy(issues = qa.issues + "usou_quadro_sem_luz") }
            }
        }
        val framing = framingGate.check(bitmap)
        if (framing.rejects && settings.requireEyeFraming) throw FramingRejected(framing)
        val quality = Quality(
            ok = q0.ok && framing.ok,
            issues = q0.issues + listOfNotNull(framing.issue),
            metrics = q0.metrics + (if (framing.available) mapOf("enq_confianca" to framing.confidence) + framing.probs.mapKeys { "enq_p_" + it.key.lowercase() } else emptyMap()),
        )
        val patient = patients.get(patientId)
        var result = store.save(bitmap, local.analyze(bitmap, quality, child).copy(patientId = patientId, framing = if (framing.available) framing.reason.name else "").withHistory(patient))
        result = store.saveFrames(result, frames)
        // red-free por software: canal verde do quadro branco realca os vasos (como o filtro dos retinografos)
        ReflectanceIndices.pick(frames, "branco", "white")?.let { wf ->
            Store.decodeOriented(wf, 1200)?.let { wb ->
                val rf = redFree(wb)
                val f = File(store.capturesDir, "redfree_${result.createdAt}.jpg")
                f.outputStream().use { rf.compress(Bitmap.CompressFormat.JPEG, 90, it) }
                result = store.saveFrames(result, listOf("Red-free" to f))
            }
        }
        if (frames.isNotEmpty()) {                       // Ramo A: indices de reflectancia nos quadros da rotina
            ReflectanceIndices.compute(frames, segmenter)?.let { (refl, overlay) ->
                var withIdx = result.copy(indices = refl.toMap())
                if (overlay != null) {
                    val f = File(store.capturesDir, "roi_${result.createdAt}.jpg")
                    f.outputStream().use { overlay.compress(Bitmap.CompressFormat.JPEG, 90, it) }
                    withIdx = store.saveFrames(withIdx, listOf("ROI esclera" to f)).let { it.copy(frames = result.frames + it.frames.takeLast(1)) }
                }
                store.update(withIdx)
                result = withIdx
            }
        }
        val url = settings.serverUrl
        if (settings.useCloud && url.isNotEmpty()) {
            val remote = RemoteAnalyzer(url).analyze(File(result.imagePath), child)
            if (remote != null) {
                result = remote.copy(
                    status = if (remote.triage == result.triage) "confirmed" else "divergent",
                    needsCloudReview = false,
                    createdAt = result.createdAt,
                    imagePath = result.imagePath,
                    child = child,
                    frames = result.frames,
                ).withHistory(patient)
                store.update(result)
            }
        }
        return result
    }
}
