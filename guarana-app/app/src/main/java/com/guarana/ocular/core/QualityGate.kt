package com.guarana.ocular.core

import android.graphics.Bitmap
import kotlin.math.max

/** Gate de qualidade local: desfoque (variancia do laplaciano) e exposicao (luminancia media). */
object QualityGate {
    private const val BLUR_MIN_VAR = 30f
    private const val DARK_MAX_MEAN = 45f
    private const val BRIGHT_MIN_MEAN = 215f
    private const val GLARE_MAX = 0.04f   // mais de 4% da imagem estourada

    fun check(bmp: Bitmap): Quality {
        val scale = 256f / max(bmp.width, bmp.height)
        val w = max(3, (bmp.width * scale).toInt())
        val h = max(3, (bmp.height * scale).toInt())
        val small = Bitmap.createScaledBitmap(bmp, w, h, true)
        val px = IntArray(w * h)
        small.getPixels(px, 0, w, 0, 0, w, h)
        val g = FloatArray(w * h) { i ->
            val p = px[i]
            0.299f * ((p shr 16) and 0xFF) + 0.587f * ((p shr 8) and 0xFF) + 0.114f * (p and 0xFF)
        }
        var mean = 0.0
        for (v in g) mean += v
        mean /= g.size
        // reflexo: fracao de pixels quase brancos (flash numa tela ou numa superficie brilhante vira mancha branca)
        var blown = 0; for (v in g) if (v >= 250f) blown++
        val glare = blown.toFloat() / g.size

        var lapSum = 0.0
        var lapSq = 0.0
        var n = 0
        for (y in 1 until h - 1) for (x in 1 until w - 1) {
            val c = y * w + x
            val lap = 4f * g[c] - g[c - 1] - g[c + 1] - g[c - w] - g[c + w]
            lapSum += lap; lapSq += lap * lap; n++
        }
        val lapVar = if (n == 0) 0.0 else (lapSq / n) - (lapSum / n) * (lapSum / n)

        val issues = mutableListOf<String>()
        if (lapVar < BLUR_MIN_VAR) issues += "desfoque"
        if (mean < DARK_MAX_MEAN) issues += "escura"
        if (mean > BRIGHT_MIN_MEAN) issues += "superexposta"
        if (glare > GLARE_MAX) issues += "reflexo"
        return Quality(issues.isEmpty(), issues, mapOf("nitidez_var" to lapVar.toFloat(), "luminancia" to mean.toFloat(), "reflexo" to glare))
    }
}
