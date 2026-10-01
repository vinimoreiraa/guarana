package com.guarana.ocular.core

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import org.json.JSONObject
import java.nio.FloatBuffer
import kotlin.math.exp

/**
 * Segmentador da fenda ocular (esclera + iris) e da iris, treinado em treino/treinar_segmentador.py (CFD + CelebA reais e
 * mascaras sinteticas do MPFB). Entrada 256x256 normalizada; saida 2 canais de logits. Serve para a ROI de esclera do ramo A
 * (esclera = fenda menos a iris dilatada) e para saber onde esta a iris. Sem o modelo nos assets, fica indisponivel e o
 * ramo A volta para a mascara heuristica.
 */
class EyeSegmenter(context: Context) {
    class Masks(val width: Int, val height: Int, val fissure: BooleanArray, val iris: BooleanArray) {
        val fissurePixels: Int get() = fissure.count { it }
        val irisPixels: Int get() = iris.count { it }
    }

    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private var session: OrtSession? = null
    private var size = 256
    private var mean = floatArrayOf(0.485f, 0.456f, 0.406f)
    private var std = floatArrayOf(0.229f, 0.224f, 0.225f)
    val available: Boolean get() = session != null
    var version: String = "indisponível"; private set

    init {
        runCatching {
            val card = JSONObject(context.assets.open("fenda_card.json").bufferedReader().use { it.readText() })
            val input = card.getJSONObject("input"); size = input.optInt("size", 256)
            input.optJSONArray("mean")?.let { a -> mean = FloatArray(3) { a.getDouble(it).toFloat() } }
            input.optJSONArray("std")?.let { a -> std = FloatArray(3) { a.getDouble(it).toFloat() } }
            version = card.optString("name", "fenda")
            session = context.assets.open(card.getString("file")).use { it.readBytes() }.let { env.createSession(it) }
        }
    }

    /** Mascaras na resolucao do bitmap (reamostragem por vizinho mais proximo a partir de 256x256). */
    fun segment(bmp: Bitmap): Masks? {
        val sess = session ?: return null
        val small = Bitmap.createScaledBitmap(bmp, size, size, true)
        val px = IntArray(size * size); small.getPixels(px, 0, size, 0, 0, size, size)
        val plane = size * size; val input = FloatArray(3 * plane)
        for (i in 0 until plane) {
            val p = px[i]
            input[i] = (((p shr 16) and 0xFF) / 255f - mean[0]) / std[0]
            input[plane + i] = (((p shr 8) and 0xFF) / 255f - mean[1]) / std[1]
            input[2 * plane + i] = ((p and 0xFF) / 255f - mean[2]) / std[2]
        }
        val logits = OnnxTensor.createTensor(env, FloatBuffer.wrap(input), longArrayOf(1, 3, size.toLong(), size.toLong())).use { t ->
            sess.run(mapOf(sess.inputNames.first() to t)).use { r -> @Suppress("UNCHECKED_CAST") (r[0].value as Array<Array<Array<FloatArray>>>)[0] }
        }
        val w = bmp.width; val h = bmp.height
        val fissure = BooleanArray(w * h); val iris = BooleanArray(w * h)
        for (y in 0 until h) {
            val sy = (y * size) / h
            for (x in 0 until w) {
                val sx = (x * size) / w
                val f = 1f / (1f + exp(-logits[0][sy][sx])); val i = 1f / (1f + exp(-logits[1][sy][sx]))
                fissure[y * w + x] = f > 0.5f; iris[y * w + x] = i > 0.5f
            }
        }
        return Masks(w, h, fissure, iris)
    }
}
