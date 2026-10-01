package com.guarana.ocular.core.color

import android.graphics.Bitmap
import android.graphics.Color
import com.guarana.ocular.core.EyeSegmenter
import com.guarana.ocular.core.Store
import java.io.File
import kotlin.math.ln
import kotlin.math.max

/**
 * Ramo A do Guaraná: medicao de cor por reflectancia multiespectral.
 *
 * Entrada: os quadros da rotina de luz (branco, azul, vermelho e ambiente sem LED), fotografados com exposicao
 * e balanco de branco travados. Saida: indices relativos, SEM calibracao clinica:
 *   ictericia  = ln(R_vermelho / R_azul)   queda da reflectancia no azul (bilirrubina absorve ~460 nm) relativa ao vermelho
 *   palidez    = ln(R / G) no quadro branco  menos hemoglobina -> menos absorcao no verde -> indice cai
 *   hiperemia  = R / (R + G + B) no quadro branco
 * Cada canal e a media na mascara de esclera, com o quadro ambiente subtraido (mesma exposicao).
 * Os valores dependem da potencia dos LEDs do anel: so viram numero clinico depois de calibrar contra hemograma e bilirrubina.
 */
data class Reflectance(
    val ictericiaLogRB: Double?,
    val palidezLogRG: Double?,
    val hiperemiaRFrac: Double?,
    val whiteRGB: DoubleArray?,
    val blueB: Double?,
    val redR: Double?,
    val roiPixels: Int,
    val roiFraction: Double,
    val ambientSubtracted: Boolean,
    val notes: List<String>,
) {
    fun toMap(): Map<String, Any?> = mapOf(
        "ictericia_log_rb" to ictericiaLogRB, "palidez_log_rg" to palidezLogRG, "hiperemia_r_frac" to hiperemiaRFrac,
        "branco_r" to whiteRGB?.get(0), "branco_g" to whiteRGB?.get(1), "branco_b" to whiteRGB?.get(2),
        "azul_b" to blueB, "vermelho_r" to redR, "roi_px" to roiPixels, "roi_frac" to roiFraction,
        "ambiente_subtraido" to ambientSubtracted, "calibrado" to false, "notas" to notes.joinToString(" | "),
    )
}

object ReflectanceIndices {
    private const val SIDE = 480

    /** Escolhe os quadros pelo rotulo (a rotina e editavel): branco / azul / vermelho / ambiente. */
    fun pick(frames: List<Pair<String, File>>, vararg keys: String): File? =
        frames.firstOrNull { (label, _) -> keys.any { label.lowercase().contains(it) } }?.second

    fun compute(frames: List<Pair<String, File>>, segmenter: EyeSegmenter? = null): Pair<Reflectance, Bitmap?>? {
        val whiteF = pick(frames, "branco", "white") ?: return null
        val white = Store.decodeOriented(whiteF, SIDE) ?: return null
        val w = white.width; val h = white.height
        val blue = pick(frames, "azul", "blue")?.let { Store.decodeOriented(it, SIDE) }?.takeIf { it.width == w && it.height == h }
        val red = pick(frames, "vermelh", "red")?.let { Store.decodeOriented(it, SIDE) }?.takeIf { it.width == w && it.height == h }
        val amb = pick(frames, "ambient", "sem led", "escuro")?.let { Store.decodeOriented(it, SIDE) }?.takeIf { it.width == w && it.height == h }
        val notes = mutableListOf<String>()
        if (blue == null) notes += "sem quadro azul"
        if (red == null) notes += "sem quadro vermelho"
        if (amb == null) notes += "sem quadro ambiente: indices sem subtracao"

        // ROI: esclera pelo segmentador (fenda menos a iris dilatada, sem brilho estourado); heuristica se nao houver modelo
        var mask = segmenter?.let { scleraFromSegmenter(white, it) }
        if (mask == null || mask.count { it } < 200) { mask = scleraMask(white); notes += "roi heuristica" } else notes += "roi segmentador"
        val roi = mask.count { it }
        val ellipseArea = mask.size
        if (roi < 200) {
            return Reflectance(null, null, null, null, null, null, roi, roi.toDouble() / ellipseArea, amb != null, notes + "esclera nao encontrada na moldura") to overlay(white, mask)
        }
        val wp = pixels(white); val ap = amb?.let { pixels(it) }
        val wMean = meanRGB(wp, ap, mask)
        val bMean = blue?.let { meanRGB(pixels(it), ap, mask) }
        val rMean = red?.let { meanRGB(pixels(it), ap, mask) }

        val ict = if (bMean != null && rMean != null) ln(max(1.0, rMean[0]) / max(1.0, bMean[2])) else null
        val pal = ln(max(1.0, wMean[0]) / max(1.0, wMean[1]))
        val hip = wMean[0] / max(1.0, wMean[0] + wMean[1] + wMean[2])
        return Reflectance(ict, pal, hip, wMean, bMean?.get(2), rMean?.get(0), roi, roi.toDouble() / ellipseArea, amb != null, notes) to overlay(white, mask)
    }

    /** esclera = fenda & !iris dilatada (raio ~4% do lado) & pixels nem estourados nem escuros */
    private fun scleraFromSegmenter(b: Bitmap, seg: EyeSegmenter): BooleanArray? {
        val m = seg.segment(b) ?: return null
        if (m.irisPixels < 50 || m.fissurePixels < 200) return null
        val w = b.width; val h = b.height; val k = max(2, (max(w, h) * 0.04).toInt())
        val irisD = BooleanArray(w * h)
        for (y in 0 until h) for (x in 0 until w) if (m.iris[y * w + x]) {
            for (dy in -k..k) { val yy = y + dy; if (yy !in 0 until h) continue
                for (dx in -k..k) { val xx = x + dx; if (xx in 0 until w && dx * dx + dy * dy <= k * k) irisD[yy * w + xx] = true } }
        }
        val px = pixels(b); val out = BooleanArray(w * h)
        for (i in out.indices) {
            if (!m.fissure[i] || irisD[i]) continue
            val p = px[i]; val r = (p shr 16) and 0xFF; val g = (p shr 8) and 0xFF; val bl = p and 0xFF
            val mx = maxOf(r, g, bl); val mn = minOf(r, g, bl)
            out[i] = mx < 245 && mn > 15
        }
        return out
    }

    private fun pixels(b: Bitmap): IntArray = IntArray(b.width * b.height).also { b.getPixels(it, 0, b.width, 0, 0, b.width, b.height) }

    /**
     * Mascara de esclera dentro da elipse central (mesma moldura da tela de captura): pixels claros e pouco saturados,
     * excluindo pele (matiz laranja com saturacao) e iris/pupila (escuros ou saturados).
     */
    private fun scleraMask(b: Bitmap): BooleanArray {
        val w = b.width; val h = b.height
        val px = pixels(b)
        val cx = w / 2.0; val cy = h / 2.0; val rx = w * 0.36; val ry = h * 0.30
        val hsv = FloatArray(3)
        val inside = BooleanArray(w * h)
        val vs = ArrayList<Float>(w * h / 4)
        for (y in 0 until h) for (x in 0 until w) {
            val dx = (x - cx) / rx; val dy = (y - cy) / ry
            if (dx * dx + dy * dy <= 1.0) {
                inside[y * w + x] = true
                Color.colorToHSV(px[y * w + x], hsv); vs += hsv[2]
            }
        }
        if (vs.isEmpty()) return BooleanArray(w * h)
        vs.sort()
        val vCut = vs[(vs.size * 0.62).toInt().coerceIn(0, vs.size - 1)]
        val mask = BooleanArray(w * h)
        for (i in mask.indices) {
            if (!inside[i]) continue
            Color.colorToHSV(px[i], hsv)
            val hue = hsv[0]; val s = hsv[1]; val v = hsv[2]
            val skin = hue in 5f..45f && s > 0.22f
            val bright = v >= vCut && v > 0.35f
            val lowSat = s < 0.32f
            mask[i] = bright && lowSat && !skin
        }
        return mask
    }

    private fun meanRGB(px: IntArray, amb: IntArray?, mask: BooleanArray): DoubleArray {
        var r = 0.0; var g = 0.0; var bl = 0.0; var n = 0
        for (i in mask.indices) {
            if (!mask[i]) continue
            val p = px[i]
            var pr = ((p shr 16) and 0xFF).toDouble(); var pg = ((p shr 8) and 0xFF).toDouble(); var pb = (p and 0xFF).toDouble()
            if (amb != null) {
                val a = amb[i]
                pr = max(0.0, pr - ((a shr 16) and 0xFF)); pg = max(0.0, pg - ((a shr 8) and 0xFF)); pb = max(0.0, pb - (a and 0xFF))
            }
            r += pr; g += pg; bl += pb; n++
        }
        return if (n == 0) doubleArrayOf(0.0, 0.0, 0.0) else doubleArrayOf(r / n, g / n, bl / n)
    }

    /** Quadro branco com a mascara pintada de verde translucido, para a pessoa ver o que foi medido. */
    private fun overlay(b: Bitmap, mask: BooleanArray): Bitmap {
        val out = b.copy(Bitmap.Config.ARGB_8888, true)
        val px = pixels(out)
        for (i in px.indices) if (mask[i]) {
            val p = px[i]
            val r = ((p shr 16) and 0xFF) / 2; val g = (((p shr 8) and 0xFF) + 255) / 2; val bl = (p and 0xFF) / 2
            px[i] = (0xFF shl 24) or (r shl 16) or (g shl 8) or bl
        }
        out.setPixels(px, 0, out.width, 0, 0, out.width, out.height)
        return out
    }
}
