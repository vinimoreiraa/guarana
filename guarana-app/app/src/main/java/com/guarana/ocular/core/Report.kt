package com.guarana.ocular.core

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import androidx.core.content.FileProvider
import net.lingala.zip4j.ZipFile
import net.lingala.zip4j.model.ZipParameters
import net.lingala.zip4j.model.enums.AesKeyStrength
import net.lingala.zip4j.model.enums.EncryptionMethod
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Relatorio instantaneo em PDF (A4) e exportacao protegida por senha (ZIP AES-256), como nos retinografos comerciais. */
object Report {
    private val fmt = SimpleDateFormat("dd/MM/yyyy HH:mm", Locale("pt", "BR"))

    fun pdf(context: Context, a: Analysis, patient: Patient?, cnes: String, appVersion: String): File {
        val doc = PdfDocument()
        val page = doc.startPage(PdfDocument.PageInfo.Builder(595, 842, 1).create())
        val c = page.canvas
        val ink = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(0x2B, 0x23, 0x20) }
        val muted = Paint(ink).apply { color = Color.rgb(0x6E, 0x62, 0x5C) }
        val bold = Paint(ink).apply { typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD) }
        var y = 56f
        val left = 48f
        val right = 547f

        bold.textSize = 20f; c.drawText("Guaraná · relatório de triagem ocular", left, y, bold); y += 18f
        muted.textSize = 10f
        c.drawText("Emitido em ${fmt.format(Date())} · análise de ${fmt.format(Date(a.createdAt))} · app $appVersion · modelo ${a.modelVersion}" + if (cnes.isNotBlank()) " · CNES $cnes" else "", left, y, muted); y += 20f
        c.drawLine(left, y, right, y, Paint().apply { color = Color.rgb(0xD9, 0xD1, 0xC7) }); y += 18f

        ink.textSize = 11f
        val who = if (patient == null) "Paciente não identificado" else "Paciente ${patient.code}" + (if (patient.name.isNotBlank()) " · ${patient.name}" else "") +
            (patient.birthYear?.let { " · nasc. $it" } ?: "") + (if (patient.cns.isNotBlank()) " · CNS ${patient.cns}" else "")
        c.drawText(who, left, y, ink); y += 16f
        if (a.child) { c.drawText("Marcado como criança", left, y, muted); y += 14f }
        if (a.gaze.isNotBlank()) { c.drawText("Olhar: ${a.gaze}", left, y, muted); y += 14f }

        // foto principal
        val bmp: Bitmap? = Store.thumbnail(a.imagePath, 700)
        val imgH = 220f
        if (bmp != null) {
            val ratio = bmp.width.toFloat() / bmp.height
            val w = minOf(right - left, imgH * ratio)
            c.drawBitmap(bmp, null, RectF(left, y + 6f, left + w, y + 6f + w / ratio), Paint(Paint.FILTER_BITMAP_FLAG))
            // quadros da rotina, pequenos, a direita
            var fx = left + w + 10f; var fy = y + 6f
            a.frames.take(6).forEach { f ->
                Store.thumbnail(f.path, 160)?.let { t ->
                    val tw = 56f; val th = tw * t.height / t.width
                    if (fx + tw > right) { fx = left + w + 10f; fy += th + 14f }
                    c.drawBitmap(t, null, RectF(fx, fy, fx + tw, fy + th), Paint(Paint.FILTER_BITMAP_FLAG))
                    muted.textSize = 7f; c.drawText(f.label.take(14), fx, fy + th + 8f, muted)
                    fx += tw + 6f
                }
            }
            y += 6f + w / ratio + 18f
        }

        // triagem
        val ts = com.guarana.ocular.ui.triageStyle(a.triage, a.child)
        bold.textSize = 15f; c.drawText("Triagem: ${ts.title}", left, y, bold); y += 16f
        ink.textSize = 10f; y = wrap(c, ts.text, left, y, right - left, ink); y += 8f

        // sinais
        bold.textSize = 12f; c.drawText("Sinais avaliados", left, y, bold); y += 14f
        ink.textSize = 10f
        a.signs.sortedByDescending { it.confidence }.forEach { s ->
            val st = when (s.state) { SignState.present -> "PRESENTE"; SignState.candidate -> "sinal fraco"; SignState.absent -> "ausente" }
            c.drawText("${Signs.name(s.id)}", left, y, ink)
            c.drawText("$st · p=${"%.2f".format(s.confidence)}", 330f, y, muted)
            y += 13f
        }
        y += 6f

        // indices
        if (a.indices.isNotEmpty()) {
            bold.textSize = 12f; c.drawText("Reflectância multiespectral (sem calibração clínica)", left, y, bold); y += 14f
            fun num(k: String) = (a.indices[k] as? Number)?.toDouble()
            listOf("Icterícia · ln(R vermelho / B azul)" to num("ictericia_log_rb"), "Palidez · ln(R / G) no branco" to num("palidez_log_rg"), "Hiperemia · R / (R+G+B) no branco" to num("hiperemia_r_frac")).forEach { (n, v) ->
                c.drawText(n, left, y, ink); c.drawText(if (v == null) "—" else "%.3f".format(v), 330f, y, muted); y += 13f
            }
            y += 6f
        }
        if (a.notes.isNotBlank()) {
            bold.textSize = 12f; c.drawText("Notas do caso", left, y, bold); y += 14f
            ink.textSize = 10f; y = wrap(c, a.notes, left, y, right - left, ink); y += 6f
        }
        if (!a.quality.ok) { muted.textSize = 10f; c.drawText("Qualidade da captura: " + a.quality.issues.joinToString(", "), left, y, muted); y += 14f }

        muted.textSize = 9f
        wrap(c, "Demonstração experimental. Os sinais são pistas de triagem obtidas de foto comum e não constituem diagnóstico. A decisão de encaminhar é do profissional de saúde responsável. Origem: ${a.engine} · ${a.status}.", left, 800f, right - left, muted)
        doc.finishPage(page)

        val out = File(context.cacheDir, "relatorios").apply { mkdirs() }
        val f = File(out, "guarana_${a.createdAt}.pdf")
        f.outputStream().use { doc.writeTo(it) }
        doc.close()
        return f
    }

    private fun wrap(c: Canvas, text: String, x: Float, y0: Float, width: Float, p: Paint): Float {
        var y = y0; val line = StringBuilder()
        text.split(" ").forEach { w ->
            val t = if (line.isEmpty()) w else "$line $w"
            if (p.measureText(t) > width) { c.drawText(line.toString(), x, y, p); y += p.textSize + 3f; line.clear(); line.append(w) } else { line.clear(); line.append(t) }
        }
        if (line.isNotEmpty()) { c.drawText(line.toString(), x, y, p); y += p.textSize + 3f }
        return y
    }

    /** ZIP com AES-256: PDF + JSON da analise + fotos. */
    fun protectedZip(context: Context, files: List<File>, password: String, name: String): File {
        val out = File(context.cacheDir, "relatorios").apply { mkdirs() }
        val target = File(out, "$name.zip").also { it.delete() }
        val zip = ZipFile(target, password.toCharArray())
        val params = ZipParameters().apply { isEncryptFiles = true; encryptionMethod = EncryptionMethod.AES; aesKeyStrength = AesKeyStrength.KEY_STRENGTH_256 }
        zip.addFiles(files.filter { it.exists() }, params)
        return target
    }

    fun share(context: Context, file: File, mime: String, title: String) {
        val uri = FileProvider.getUriForFile(context, context.packageName + ".files", file)
        val send = Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM, uri).putExtra(Intent.EXTRA_SUBJECT, title)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        context.startActivity(Intent.createChooser(send, title).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
