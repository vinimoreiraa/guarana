package com.guarana.ocular.core

import android.content.ContentValues
import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Environment
import android.provider.DocumentsContract
import android.provider.MediaStore
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Validacao automatica no aparelho: roda o MESMO caminho da analise (gate de qualidade, gate de enquadramento,
 * modelo local, triagem) sobre uma pasta de imagens escolhida pelo agente ou pelo desenvolvedor, sem fotografar nada,
 * e compara com um manifesto opcional (`manifest.csv`: file;labels;triage;framing). Sai um relatorio JSON e Markdown
 * na pasta Downloads (legivel por `adb pull /sdcard/Download/`) e no cache do app para compartilhar.
 *
 * O historico de analises do app NAO e alterado: nada e salvo no Store.
 */
class Validation(private val context: Context, private val pipeline: Pipeline) {
    data class Expect(val labels: Set<String>, val triage: String, val framing: String)
    data class Row(
        val file: String, val ms: Long, val framing: String, val framingOk: Boolean, val quality: List<String>,
        val present: Set<String>, val candidate: Set<String>, val probs: Map<String, Float>, val triage: String, val expect: Expect?,
    )
    data class Report(val n: Int, val jsonFile: File, val mdFile: File, val summary: String, val downloadsUri: Uri?)

    /** Le o manifesto (separador ; ou ,). Colunas: file, labels (rotulos separados por | ou espaco), triage, framing. */
    private fun readManifest(children: List<Pair<String, Uri>>): Map<String, Expect> {
        val m = children.firstOrNull { it.first.equals("manifest.csv", true) } ?: return emptyMap()
        val text = context.contentResolver.openInputStream(m.second)?.bufferedReader()?.use { it.readText() } ?: return emptyMap()
        val lines = text.lines().filter { it.isNotBlank() }
        if (lines.size < 2) return emptyMap()
        val sep = if (lines[0].count { it == ';' } >= lines[0].count { it == ',' }) ';' else ','
        val head = lines[0].split(sep).map { it.trim().lowercase() }
        fun col(r: List<String>, name: String) = head.indexOf(name).takeIf { it >= 0 }?.let { r.getOrNull(it)?.trim() } ?: ""
        return lines.drop(1).map { it.split(sep) }.associate { r ->
            col(r, "file") to Expect(
                labels = col(r, "labels").split('|', ' ', ',').map { it.trim() }.filter { it.isNotBlank() }.toSet(),
                triage = col(r, "triage"), framing = col(r, "framing"),
            )
        }
    }

    private fun listChildren(tree: Uri): List<Pair<String, Uri>> {
        val childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree))
        val out = mutableListOf<Pair<String, Uri>>()
        context.contentResolver.query(childrenUri, arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE), null, null, null)?.use { c ->
            while (c.moveToNext()) {
                val id = c.getString(0); val name = c.getString(1); val mime = c.getString(2) ?: ""
                if (mime.startsWith("image/") || name.endsWith(".csv", true)) out += name to DocumentsContract.buildDocumentUriUsingTree(tree, id)
            }
        }
        return out.sortedBy { it.first }
    }

    /** Executa sobre a pasta; [onProgress] recebe (feitas, total). */
    fun run(tree: Uri, requireFraming: Boolean, onProgress: (Int, Int) -> Unit = { _, _ -> }): Report {
        val children = listChildren(tree)
        val expect = readManifest(children)
        val images = children.filter { !it.first.endsWith(".csv", true) }
        val rows = mutableListOf<Row>()
        images.forEachIndexed { i, (name, uri) ->
            onProgress(i, images.size)
            val bmp = context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) } ?: return@forEachIndexed
            val t0 = System.nanoTime()
            val q = QualityGate.check(bmp)
            val fr = pipeline.framingGate.check(bmp)
            val a = if (!fr.rejects || !requireFraming) pipeline.local.analyze(bmp, q, child = false) else null
            val ms = (System.nanoTime() - t0) / 1_000_000
            rows += Row(
                file = name, ms = ms, framing = if (fr.available) fr.reason.name else "indisponivel", framingOk = fr.ok, quality = q.issues + listOfNotNull(fr.issue),
                present = a?.signs?.filter { it.state == SignState.present }?.map { it.id }?.toSet() ?: emptySet(),
                candidate = a?.signs?.filter { it.state == SignState.candidate }?.map { it.id }?.toSet() ?: emptySet(),
                probs = a?.signs?.associate { it.id to it.confidence } ?: emptyMap(),
                triage = a?.triage ?: "recusada_enquadramento", expect = expect[name],
            )
            bmp.recycle()
        }
        onProgress(images.size, images.size)
        return write(rows, requireFraming)
    }

    private fun write(rows: List<Row>, requireFraming: Boolean): Report {
        val labels = pipeline.local.card.labels
        val stamp = SimpleDateFormat("yyyyMMdd-HHmm", Locale.US).format(Date())
        val withExp = rows.filter { it.expect != null }
        // metricas por rotulo (so com manifesto)
        val perLabel = labels.map { l ->
            var tp = 0; var fn = 0; var tn = 0; var fp = 0
            withExp.forEach { r -> val e = l in r.expect!!.labels; val p = l in r.present; if (e && p) tp++ else if (e) fn++ else if (p) fp++ else tn++ }
            JSONObject().put("label", l).put("n_pos", tp + fn).put("sensibilidade", if (tp + fn > 0) tp.toDouble() / (tp + fn) else JSONObject.NULL)
                .put("especificidade", if (tn + fp > 0) tn.toDouble() / (tn + fp) else JSONObject.NULL).put("fp", fp).put("fn", fn)
        }
        val triageAgree = withExp.count { it.expect!!.triage.isNotBlank() && it.expect.triage == it.triage }
        val triageN = withExp.count { it.expect!!.triage.isNotBlank() }
        val framingAgree = withExp.count { it.expect!!.framing.isNotBlank() && it.expect.framing == it.framing }
        val framingN = withExp.count { it.expect!!.framing.isNotBlank() }
        val framingDist = rows.groupingBy { it.framing }.eachCount()
        val avgMs = if (rows.isNotEmpty()) rows.map { it.ms }.average() else 0.0
        val json = JSONObject().put("gerado_em", stamp).put("modelo", pipeline.local.card.name).put("enquadramento", pipeline.framingGate.version)
            .put("exigir_enquadramento", requireFraming).put("n", rows.size).put("com_manifesto", withExp.size).put("ms_medio", avgMs)
            .put("enquadramento_distribuicao", JSONObject(framingDist.mapValues { it.value as Any }))
            .put("triagem_concordancia", if (triageN > 0) triageAgree.toDouble() / triageN else JSONObject.NULL)
            .put("enquadramento_concordancia", if (framingN > 0) framingAgree.toDouble() / framingN else JSONObject.NULL)
            .put("por_rotulo", JSONArray(perLabel))
            .put("imagens", JSONArray(rows.map { r ->
                JSONObject().put("file", r.file).put("ms", r.ms).put("framing", r.framing).put("quality", JSONArray(r.quality))
                    .put("present", JSONArray(r.present.toList())).put("candidate", JSONArray(r.candidate.toList())).put("triage", r.triage)
                    .put("probs", JSONObject().also { o -> r.probs.forEach { (k, v) -> o.put(k, v.toDouble()) } })
                    .put("expect", r.expect?.let { e -> JSONObject().put("labels", JSONArray(e.labels.toList())).put("triage", e.triage).put("framing", e.framing) } ?: JSONObject.NULL)
            }))
        val md = StringBuilder("# Validação no aparelho · ${pipeline.local.card.name} · $stamp\n\n")
        md.append("Imagens: ${rows.size} · com manifesto: ${withExp.size} · tempo médio por imagem: ${"%.0f".format(avgMs)} ms · enquadramento: ${pipeline.framingGate.version}" + (if (requireFraming) " (exigido)" else " (só avisa)") + "\n\n")
        md.append("Enquadramento: " + framingDist.entries.joinToString(", ") { "${it.key} ${it.value}" } + "\n\n")
        if (triageN > 0) md.append("Triagem concorda com o esperado em ${"%.0f".format(100.0 * triageAgree / triageN)}% de $triageN imagens.\n\n")
        if (framingN > 0) md.append("Enquadramento concorda com o esperado em ${"%.0f".format(100.0 * framingAgree / framingN)}% de $framingN imagens.\n\n")
        if (withExp.isNotEmpty()) {
            md.append("| sinal | n pos | sens | esp | FP | FN |\n|---|---:|---:|---:|---:|---:|\n")
            perLabel.forEach { o -> md.append("| ${o.getString("label")} | ${o.getInt("n_pos")} | ${fmt(o.opt("sensibilidade"))} | ${fmt(o.opt("especificidade"))} | ${o.getInt("fp")} | ${o.getInt("fn")} |\n") }
            md.append("\n")
        }
        md.append("| imagem | enquadramento | triagem | presentes | ms |\n|---|---|---|---|---:|\n")
        rows.forEach { r -> md.append("| ${r.file} | ${r.framing} | ${r.triage} | ${r.present.joinToString(" ")} | ${r.ms} |\n") }
        val dir = File(context.cacheDir, "relatorios").apply { mkdirs() }
        val jf = File(dir, "validacao_$stamp.json").also { it.writeText(json.toString(2)) }
        val mf = File(dir, "validacao_$stamp.md").also { it.writeText(md.toString()) }
        val uri = runCatching { saveToDownloads("validacao_$stamp.md", md.toString(), "text/markdown"); saveToDownloads("validacao_$stamp.json", json.toString(2), "application/json") }.getOrNull()
        val summary = "${rows.size} imagens · ${"%.0f".format(avgMs)} ms/imagem · " + framingDist.entries.joinToString(", ") { "${it.key} ${it.value}" } +
            (if (triageN > 0) " · triagem ${"%.0f".format(100.0 * triageAgree / triageN)}%" else "")
        return Report(rows.size, jf, mf, summary, uri)
    }

    private fun fmt(v: Any?): String = (v as? Double)?.let { "%.2f".format(it) } ?: "–"

    /** Downloads/guarana-validacao/<nome>, via MediaStore (sem permissao de armazenamento). */
    private fun saveToDownloads(name: String, text: String, mime: String): Uri? {
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, name); put(MediaStore.MediaColumns.MIME_TYPE, mime)
            put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/guarana-validacao")
        }
        val uri = context.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values) ?: return null
        context.contentResolver.openOutputStream(uri)?.use { it.write(text.toByteArray()) }
        return uri
    }
}
