package com.guarana.ocular.core

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.exifinterface.media.ExifInterface
import org.json.JSONObject
import java.io.File

/** Persistencia simples: uma pasta com <timestamp>.jpg + <timestamp>.json por analise. */
class Store(private val context: Context) {
    private val dir: File get() = File(context.filesDir, "analises").apply { mkdirs() }
    val capturesDir: File get() = File(context.filesDir, "capturas").apply { mkdirs() }

    fun save(bitmap: Bitmap, analysis: Analysis): Analysis {
        val stamp = analysis.createdAt.toString()
        val jpg = File(dir, "$stamp.jpg")
        jpg.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 92, it) }
        val withPath = analysis.copy(imagePath = jpg.absolutePath)
        update(withPath)
        return withPath
    }

    /** Copia os quadros da rotina para a pasta da analise e devolve a analise com os caminhos definitivos. */
    fun saveFrames(analysis: Analysis, frames: List<Pair<String, File>>): Analysis {
        if (frames.isEmpty()) return analysis
        val base = analysis.frames.size
        val saved = frames.mapIndexed { i, (label, f) ->
            val dest = File(dir, "${analysis.createdAt}_${base + i}_${label.lowercase().replace(Regex("[^a-z0-9]+"), "-")}.jpg")
            f.copyTo(dest, overwrite = true)
            Frame(label, dest.absolutePath)
        }
        val withFrames = analysis.copy(frames = analysis.frames + saved)
        update(withFrames)
        return withFrames
    }

    fun update(analysis: Analysis) {
        File(dir, "${analysis.createdAt}.json").writeText(analysis.toJson().toString(2))
    }

    fun list(): List<Analysis> = (dir.listFiles { f -> f.extension == "json" } ?: emptyArray())
        .mapNotNull { f -> runCatching { Analysis.fromJson(JSONObject(f.readText())) }.getOrNull() }
        .sortedByDescending { it.createdAt }

    fun delete(analysis: Analysis) {
        File(dir, "${analysis.createdAt}.json").delete()
        if (analysis.imagePath.isNotEmpty()) File(analysis.imagePath).delete()
        analysis.frames.forEach { File(it.path).delete() }
    }

    companion object {
        /** Decodifica com orientacao EXIF aplicada e lado maior limitado a maxSide (economiza memoria). */
        fun decodeOriented(file: File, maxSide: Int = 1600): Bitmap? {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeFile(file.path, bounds)
            if (bounds.outWidth <= 0) return null
            var sample = 1
            while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= maxSide) sample *= 2
            val bmp = BitmapFactory.decodeFile(file.path, BitmapFactory.Options().apply { inSampleSize = sample }) ?: return null
            val rot = when (ExifInterface(file.path).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
                ExifInterface.ORIENTATION_ROTATE_90 -> 90f
                ExifInterface.ORIENTATION_ROTATE_180 -> 180f
                ExifInterface.ORIENTATION_ROTATE_270 -> 270f
                else -> 0f
            }
            return if (rot == 0f) bmp else Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, Matrix().apply { postRotate(rot) }, true)
        }

        fun thumbnail(path: String, maxSide: Int = 320): Bitmap? = if (path.isEmpty()) null else decodeOriented(File(path), maxSide)
    }
}
