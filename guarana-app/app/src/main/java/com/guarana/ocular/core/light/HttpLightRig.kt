package com.guarana.ocular.core.light

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.Proxy
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

/** ESP32 em modo ponto de acesso (Wi-Fi "Guarana-Luz"): GET http://192.168.4.1/cmd?c=<comando>. */
class HttpLightRig(private val host: String) : LightRig {
    override val name: String get() = "Wi-Fi · $host"
    // o ESP esta na rede local: nunca passar por proxy configurado no aparelho
    private val client = OkHttpClient.Builder().proxy(Proxy.NO_PROXY).connectTimeout(2, TimeUnit.SECONDS).readTimeout(2, TimeUnit.SECONDS).build()
    private fun base() = (if (host.startsWith("http")) host else "http://$host").trimEnd('/')

    override suspend fun send(cmd: String): String? = withContext(Dispatchers.IO) {
        runCatching {
            client.newCall(Request.Builder().url(base() + "/cmd?c=" + URLEncoder.encode(cmd, "UTF-8")).build()).execute()
                .use { if (it.isSuccessful) it.body?.string() else { Log.w("Guarana", "luz http ${it.code}"); null } }
        }.onFailure { Log.w("Guarana", "luz http falhou: $it") }.getOrNull()
    }

    override suspend fun connect(): Boolean = ping() != null
    override fun close() {}
}
