package com.guarana.ocular.core

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import org.json.JSONObject
import java.nio.FloatBuffer
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min

/**
 * Enquadramento do olho: um classificador pequeno (MobileNetV3-small, 160 px, escala de cinza) treinado por sintese a
 * partir de iris anotadas (treino/treinar_enquadramento.py). Decide se ha UM olho, perto o bastante e centralizado,
 * ou por que nao: longe, perto demais, dois olhos, descentralizado, sem olho. Roda em poucos milissegundos, entao
 * serve para a dica ao vivo na captura e para recusar a foto antes da analise.
 *
 * Contrato em assets/enquadramento_card.json: classes na ordem da saida, tamanho, normalizacao. Sem o modelo nos
 * assets, tudo passa como OK (o gate fica desligado), e o resultado registra isso.
 */
class EyeFraming(context: Context) {
    enum class Reason(val message: String) {
        OK("Olho enquadrado"),
        TOO_FAR("Aproxime-se do olho até a íris preencher a moldura."),
        TOO_CLOSE("Afaste um pouco: a íris está grande demais."),
        TWO_EYES("Fotografe um olho de cada vez."),
        OFF_CENTER("Centralize o olho na moldura."),
        NOT_FOUND("Não encontrei o olho. Centralize um olho na moldura."),
    }

    data class Result(val reason: Reason, val confidence: Float, val probs: Map<String, Float>, val available: Boolean = true) {
        val ok: Boolean get() = reason == Reason.OK
        /** So estes motivos recusam a foto; descentralizado e perto demais viram aviso (o olho esta la, o modelo ainda ve). */
        val rejects: Boolean get() = reason == Reason.TOO_FAR || reason == Reason.TWO_EYES || reason == Reason.NOT_FOUND
        val issue: String? get() = when (reason) {
            Reason.OK -> null; Reason.NOT_FOUND -> "olho_nao_encontrado"; Reason.TOO_FAR -> "muito_longe"
            Reason.TOO_CLOSE -> "muito_perto"; Reason.TWO_EYES -> "dois_olhos"; Reason.OFF_CENTER -> "descentralizado"
        }
    }

    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private var session: OrtSession? = null
    private var classes: List<String> = emptyList()
    private var size = 160
    private var mean = 0.45f
    private var std = 0.25f
    val available: Boolean get() = session != null
    var version: String = "indisponível"; private set

    init {
        runCatching {
            val card = JSONObject(context.assets.open("enquadramento_card.json").bufferedReader().use { it.readText() })
            val input = card.getJSONObject("input")
            size = input.optInt("size", 160); mean = input.optDouble("mean", 0.45).toFloat(); std = input.optDouble("std", 0.25).toFloat()
            val cl = card.getJSONArray("classes"); classes = List(cl.length()) { cl.getString(it) }
            version = card.optString("name", "enquadramento")
            session = context.assets.open(card.getString("file")).use { it.readBytes() }.let { env.createSession(it) }
        }
    }

    /**
     * Foto capturada (colorida) em escala de cinza. Foto de camera (4:3) usa o recorte central quadrado, como o preview;
     * imagem muito larga ou alta (faixa dos dois olhos, por exemplo) e encaixada inteira num quadrado com borda cinza,
     * senao o recorte jogaria fora justamente os olhos.
     */
    fun check(bmp: Bitmap): Result {
        val ratio = max(bmp.width, bmp.height).toFloat() / min(bmp.width, bmp.height)
        val sq: Bitmap = if (ratio <= 1.4f) {
            val s = min(bmp.width, bmp.height)
            Bitmap.createBitmap(bmp, (bmp.width - s) / 2, (bmp.height - s) / 2, s, s)
        } else {
            val s = max(bmp.width, bmp.height)
            Bitmap.createBitmap(s, s, Bitmap.Config.ARGB_8888).also { c ->
                val cv = android.graphics.Canvas(c); cv.drawColor(0xFF808080.toInt())
                cv.drawBitmap(bmp, ((s - bmp.width) / 2).toFloat(), ((s - bmp.height) / 2).toFloat(), null)
            }
        }
        val small = Bitmap.createScaledBitmap(sq, size, size, true)
        val px = IntArray(size * size); small.getPixels(px, 0, size, 0, 0, size, size)
        val g = FloatArray(size * size) { i -> val p = px[i]; 0.299f * ((p shr 16) and 0xFF) + 0.587f * ((p shr 8) and 0xFF) + 0.114f * (p and 0xFF) }
        return run(g)
    }

    /** Quadro de luminancia [g] com [w]x[h] valores 0..255 (preview): recorte central quadrado e reamostragem para o modelo. */
    fun checkGray(g: FloatArray, w: Int, h: Int): Result {
        val s = min(w, h); val x0 = (w - s) / 2; val y0 = (h - s) / 2
        val out = FloatArray(size * size)
        for (y in 0 until size) { val sy = y0 + (y * s) / size; for (x in 0 until size) out[y * size + x] = g[sy * w + x0 + (x * s) / size] }
        return run(out)
    }

    private fun run(gray: FloatArray): Result {
        val sess = session ?: return Result(Reason.OK, 1f, emptyMap(), available = false)
        val plane = size * size
        val input = FloatArray(3 * plane)
        for (i in 0 until plane) { val v = (gray[i] / 255f - mean) / std; input[i] = v; input[plane + i] = v; input[2 * plane + i] = v }
        val logits = OnnxTensor.createTensor(env, FloatBuffer.wrap(input), longArrayOf(1, 3, size.toLong(), size.toLong())).use { t ->
            sess.run(mapOf(sess.inputNames.first() to t)).use { r -> @Suppress("UNCHECKED_CAST") (r[0].value as Array<FloatArray>)[0] }
        }
        val mx = logits.max(); val ex = logits.map { exp(it - mx) }; val sum = ex.sum()
        val probs = classes.indices.associate { classes[it] to (ex[it] / sum).toFloat() }
        val best = probs.maxByOrNull { it.value } ?: return Result(Reason.NOT_FOUND, 0f, probs)
        val reason = runCatching { Reason.valueOf(best.key) }.getOrDefault(Reason.NOT_FOUND)
        return Result(reason, best.value, probs)
    }
}
