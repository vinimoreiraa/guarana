package com.guarana.ocular.core

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import java.nio.FloatBuffer
import kotlin.math.exp
import kotlin.math.min
import kotlin.math.roundToInt

/** Motor local: ONNX Runtime em CPU, pre-processamento identico ao treino, lido do model card. */
class LocalAnalyzer(context: Context) {
    val card: ModelCard = ModelCard.load(context)
    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private val session: OrtSession = context.assets.open(card.file).use { it.readBytes() }.let { env.createSession(it) }

    /** Uma vista: recorte quadrado (px) da foto, espelhado ou nao. */
    private class View(val x0: Int, val y0: Int, val side: Int, val flip: Boolean)

    /**
     * Vistas no zoom do treino (lado menor × 320/352): centro, mais esquerda e direita (ou topo e base) quando a foto
     * nao e quadrada, cada uma com espelho. Lesao na borda (pterigio no canto nasal) entra inteira em alguma vista.
     */
    private fun views(bmp: Bitmap): List<View> {
        val w = bmp.width; val h = bmp.height
        val side = (min(w, h) * card.inputSize / (card.inputSize * 1.1)).roundToInt().coerceIn(1, min(w, h))
        val boxes = mutableListOf((w - side) / 2 to (h - side) / 2)
        if (w > h) boxes += listOf(0 to (h - side) / 2, (w - side) to (h - side) / 2)
        else if (h > w) boxes += listOf((w - side) / 2 to 0, (w - side) / 2 to (h - side))
        return boxes.flatMap { (x, y) -> listOf(View(x, y, side, false), View(x, y, side, true)) }
    }

    fun analyze(bitmap: Bitmap, quality: Quality, child: Boolean): Analysis {
        if (card.multiclasse) return analyzeMulticlasse(bitmap, quality, child)
        val s = card.inputSize
        val t0 = System.nanoTime()
        val vs = views(bitmap)
        val probs = Array(vs.size) { FloatArray(card.labels.size) }
        val cams = arrayOfNulls<Array<Array<FloatArray>>>(vs.size)
        var eh = 0; var ew = 0
        vs.forEachIndexed { vi, v ->
            val input = preprocessView(bitmap, v, s)
            OnnxTensor.createTensor(env, FloatBuffer.wrap(input), longArrayOf(1, 3, s.toLong(), s.toLong())).use { t ->
                session.run(mapOf(session.inputNames.first() to t)).use { r ->
                    @Suppress("UNCHECKED_CAST")
                    val lg = (r[0].value as Array<FloatArray>)[0]
                    for (k in lg.indices) probs[vi][k] = 1f / (1f + exp(-lg[k]))
                    if (session.outputNames.contains("cam")) runCatching {
                        @Suppress("UNCHECKED_CAST")
                        val cam = (r.get("cam").get().value as Array<Array<Array<FloatArray>>>)[0]
                        eh = cam[0].size; ew = cam[0][0].size; cams[vi] = cam
                    }
                }
            }
        }
        val ms = (System.nanoTime() - t0) / 1_000_000
        val explain = HashMap<String, FloatArray>(); val boxes = HashMap<String, FloatArray>()
        val signs = card.labels.mapIndexed { i, id ->
            // probabilidade = maximo entre as vistas; o mapa e a caixa vem da vista vencedora (desespelhado se preciso)
            var best = 0; for (vi in vs.indices) if (probs[vi][i] > probs[best][i]) best = vi
            val p = probs[best][i]
            cams[best]?.let { cam ->
                val v = vs[best]
                explain[id] = FloatArray(eh * ew) { k -> val row = k / ew; val col = k % ew; cam[i][row][if (v.flip) ew - 1 - col else col] }
                boxes[id] = floatArrayOf(v.x0.toFloat() / bitmap.width, v.y0.toFloat() / bitmap.height, v.side.toFloat() / bitmap.width, v.side.toFloat() / bitmap.height)
            }
            val thr = card.thresholds[id] ?: 0.5f
            val thrC = card.candidateThresholds[id] ?: (thr / 2f)   // v2.2: limiar de candidato calibrado em normais reais (92% de especificidade)
            val state = when {
                p >= thr -> SignState.present
                p >= thrC && p >= 0.05f -> SignState.candidate
                else -> SignState.absent
            }
            Sign(id, state, p, Signs.REGIONS[id] ?: "esclera", "p=%.2f · limiar=%.2f · %d vistas".format(p, thr, vs.size))
        }
        return Analysis(
            engine = "local-model",
            status = "provisional",
            modelVersion = card.name,
            quality = quality,
            signs = signs,
            triage = Triage.decide(signs, child),
            needsCloudReview = true,
            child = child,
            explain = explain, explainW = ew, explainH = eh, explainBoxes = boxes, inferenceMs = ms,
        )
    }

    /**
     * v2.3+: decisao conservadora. P(doente) = 1 - P(normal); acima do corte do cartao a pessoa "precisa de avaliacao" e a doenca
     * mais provavel (fora "normal") vira o sinal presente, que da o nivel da triagem e a explicacao. Abaixo do corte: sem sinais.
     * O mapa de atencao do modelo (24x24) mostra onde ele olhou.
     */
    private fun analyzeMulticlasse(bitmap: Bitmap, quality: Quality, child: Boolean): Analysis {
        val s = card.inputSize; val t0 = System.nanoTime()
        var probs = FloatArray(card.labels.size); var att: Array<FloatArray>? = null
        OnnxTensor.createTensor(env, FloatBuffer.wrap(preprocess(bitmap, s)), longArrayOf(1, 3, s.toLong(), s.toLong())).use { t ->
            session.run(mapOf(session.inputNames.first() to t)).use { r ->
                @Suppress("UNCHECKED_CAST")
                probs = (r[0].value as Array<FloatArray>)[0]
                runCatching { @Suppress("UNCHECKED_CAST") att = (r.get("atencao").get().value as Array<Array<FloatArray>>)[0] }
            }
        }
        val ms = (System.nanoTime() - t0) / 1_000_000
        val iNormal = card.labels.indexOf("normal")
        val pDoente = if (iNormal >= 0) 1f - probs[iNormal] else probs.maxOrNull() ?: 0f
        val precisa = pDoente >= card.corteDoente
        val doencas = card.labels.indices.filter { it != iNormal }.sortedByDescending { probs[it] }
        val top = doencas.firstOrNull()
        val signs = doencas.map { i ->
            val id = card.labels[i]; val p = probs[i]
            val state = when {
                !precisa -> SignState.absent
                i == top -> SignState.present
                p >= 0.15f -> SignState.candidate
                else -> SignState.absent
            }
            Sign(id, state, p, Signs.REGIONS[id] ?: "esclera", "p=%.2f · P(doente)=%.2f · corte=%.2f".format(p, pDoente, card.corteDoente))
        }
        // recorte central usado no preprocess (lado menor), em fracao da foto, para desenhar o mapa no lugar certo
        val side = min(bitmap.width, bitmap.height) / 1.1f
        val box = floatArrayOf((bitmap.width - side) / 2f / bitmap.width, (bitmap.height - side) / 2f / bitmap.height, side / bitmap.width, side / bitmap.height)
        val explain = HashMap<String, FloatArray>(); val boxes = HashMap<String, FloatArray>()
        val a = att
        if (a != null && top != null && precisa) {
            val h = a.size; val w = a[0].size
            explain[card.labels[top]] = FloatArray(h * w) { k -> a[k / w][k % w] }; boxes[card.labels[top]] = box
        }
        val gh = a?.size ?: 0; val gw = a?.getOrNull(0)?.size ?: 0
        return Analysis(
            engine = "local-model", status = "provisional", modelVersion = card.name,
            quality = quality.copy(metrics = quality.metrics + mapOf("p_doente" to pDoente, "corte_doente" to card.corteDoente)),
            signs = signs, triage = if (precisa) Triage.decide(signs, child) else "sem_sinais", needsCloudReview = true, child = child,
            explain = explain, explainW = gw, explainH = gh, explainBoxes = boxes, inferenceMs = ms,
        )
    }

    /** Recorte quadrado da vista reamostrado para SxS, espelhado se a vista pedir, /255, (x-mean)/std, NCHW. */
    private fun preprocessView(bmp: Bitmap, v: View, s: Int): FloatArray {
        val crop = Bitmap.createBitmap(bmp, v.x0.coerceIn(0, bmp.width - v.side), v.y0.coerceIn(0, bmp.height - v.side), v.side, v.side)
        val scaled = Bitmap.createScaledBitmap(crop, s, s, true)
        val px = IntArray(s * s); scaled.getPixels(px, 0, s, 0, 0, s, s)
        val out = FloatArray(3 * s * s); val plane = s * s
        for (i in 0 until plane) {
            val src = if (v.flip) (i / s) * s + (s - 1 - i % s) else i
            val p = px[src]
            out[i] = (((p shr 16) and 0xFF) / 255f - card.mean[0]) / card.std[0]
            out[plane + i] = (((p shr 8) and 0xFF) / 255f - card.mean[1]) / card.std[1]
            out[2 * plane + i] = ((p and 0xFF) / 255f - card.mean[2]) / card.std[2]
        }
        return out
    }

    /** resize do lado menor para 1.1*S, recorte central SxS, /255, (x-mean)/std, NCHW. */
    private fun preprocess(bmp: Bitmap, s: Int): FloatArray {
        val target = (s * 1.1).toInt()
        val scale = target.toFloat() / min(bmp.width, bmp.height)
        val w = (bmp.width * scale).roundToInt().coerceAtLeast(s)
        val h = (bmp.height * scale).roundToInt().coerceAtLeast(s)
        val scaled = Bitmap.createScaledBitmap(bmp, w, h, true)
        val crop = Bitmap.createBitmap(scaled, (w - s) / 2, (h - s) / 2, s, s)
        val px = IntArray(s * s)
        crop.getPixels(px, 0, s, 0, 0, s, s)
        val out = FloatArray(3 * s * s)
        val plane = s * s
        for (i in 0 until plane) {
            val p = px[i]
            out[i] = (((p shr 16) and 0xFF) / 255f - card.mean[0]) / card.std[0]
            out[plane + i] = (((p shr 8) and 0xFF) / 255f - card.mean[1]) / card.std[1]
            out[2 * plane + i] = ((p and 0xFF) / 255f - card.mean[2]) / card.std[2]
        }
        return out
    }
}
