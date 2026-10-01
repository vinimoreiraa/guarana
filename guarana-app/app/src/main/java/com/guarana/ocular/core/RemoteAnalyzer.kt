package com.guarana.ocular.core

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/** Camada de nuvem: POST /analyze com a foto; espera o mesmo contrato JSON. Retorna null se falhar. */
class RemoteAnalyzer(private val baseUrl: String) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(40, TimeUnit.SECONDS)
        .build()

    fun analyze(jpeg: File, child: Boolean): Analysis? {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("image", jpeg.name, jpeg.asRequestBody("image/jpeg".toMediaType()))
            .addFormDataPart("child", child.toString())
            .build()
        val req = Request.Builder().url(baseUrl.trimEnd('/') + "/analyze").post(body).build()
        return runCatching {
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return null
                val txt = resp.body?.string() ?: return null
                Analysis.fromJson(JSONObject(txt))
            }
        }.getOrNull()
    }
}
