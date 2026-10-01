package com.guarana.ocular.core.light

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.util.Log
import androidx.core.content.ContextCompat
import com.hoho.android.usbserial.driver.CdcAcmSerialDriver
import com.hoho.android.usbserial.driver.ProbeTable
import com.hoho.android.usbserial.driver.UsbSerialPort
import com.hoho.android.usbserial.driver.UsbSerialProber
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.io.ByteArrayOutputStream
import java.io.File

/**
 * ESP32 / ESP32-CAM pela USB (cabo + adaptador OTG). Conversores CH340, CP210x, FTDI e USB nativo da Espressif.
 * Linha de comando -> linha JSON de resposta. "F" devolve "FRAME <n>\n" + JPEG cru.
 */
class UsbSerialLightRig(private val context: Context, private val baud: Int, private val configLine: String) : LightRig {
    override val name: String get() = "USB · " + (port?.driver?.device?.productName ?: "serial")
    override val canGrabFrame: Boolean get() = camReady
    private var port: UsbSerialPort? = null
    private var camReady = false
    private val inbuf = ByteArrayOutputStream()
    private val chunk = ByteArray(4096)

    companion object {
        private const val ACTION_PERMISSION = "com.guarana.ocular.USB_PERMISSION"
        private val prober: UsbSerialProber by lazy {
            val table = ProbeTable()
            table.addProduct(0x303A, 0x1001, CdcAcmSerialDriver::class.java)   // Espressif USB nativo (ESP32-S3/C3)
            table.addProduct(0x303A, 0x0002, CdcAcmSerialDriver::class.java)
            UsbSerialProber(table)
        }
    }

    override suspend fun connect(): Boolean = withContext(Dispatchers.IO) {
        if (port != null) return@withContext true
        val manager = context.getSystemService(Context.USB_SERVICE) as UsbManager
        val drivers = UsbSerialProber.getDefaultProber().findAllDrivers(manager) + prober.findAllDrivers(manager)
        val driver = drivers.firstOrNull() ?: run { Log.w("Guarana", "usb: nenhum conversor serial"); return@withContext false }
        val device = driver.device
        if (!ensurePermission(manager, device)) { Log.w("Guarana", "usb: sem permissão"); return@withContext false }
        val conn = manager.openDevice(device) ?: return@withContext false
        val p = driver.ports.firstOrNull() ?: return@withContext false
        try {
            p.open(conn)
            p.setParameters(baud, 8, UsbSerialPort.STOPBITS_1, UsbSerialPort.PARITY_NONE)
            runCatching { p.dtr = true; p.rts = true }
        } catch (e: Exception) {
            Log.w("Guarana", "usb: abrir porta falhou: $e"); runCatching { p.close() }; return@withContext false
        }
        port = p
        delay(1500)               // se a placa reiniciou ao abrir a porta, espera o boot
        drain()
        var status: String? = null
        repeat(3) { if (status == null) status = sendLine("P") }
        if (status == null) { close(); return@withContext false }
        camReady = status!!.contains("\"cam\":true")
        if (configLine.isNotBlank()) sendLine(configLine.trim())   // nada fixo no firmware: o app configura ao conectar
        true
    }

    private suspend fun ensurePermission(manager: UsbManager, device: UsbDevice): Boolean {
        if (manager.hasPermission(device)) return true
        val granted = CompletableDeferred<Boolean>()
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(c: Context, i: Intent) {
                if (i.action == ACTION_PERMISSION) {
                    granted.complete(i.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false))
                    runCatching { context.unregisterReceiver(this) }
                }
            }
        }
        ContextCompat.registerReceiver(context, receiver, IntentFilter(ACTION_PERMISSION), ContextCompat.RECEIVER_NOT_EXPORTED)
        val pi = PendingIntent.getBroadcast(context, 0, Intent(ACTION_PERMISSION).setPackage(context.packageName), PendingIntent.FLAG_MUTABLE)
        manager.requestPermission(device, pi)
        return withTimeoutOrNull(60_000) { granted.await() } ?: false
    }

    // ---- leitura com buffer proprio: a linha de resposta e os bytes do JPEG chegam no mesmo fluxo ----
    private fun fill(timeoutMs: Int): Int {
        val p = port ?: return -1
        val n = runCatching { p.read(chunk, timeoutMs) }.getOrDefault(-1)
        if (n > 0) inbuf.write(chunk, 0, n)
        return n
    }

    private fun takeLine(): String? {
        val bytes = inbuf.toByteArray()
        val i = bytes.indexOf('\n'.code.toByte())
        if (i < 0) return null
        val line = String(bytes, 0, i).trim()
        inbuf.reset(); inbuf.write(bytes, i + 1, bytes.size - i - 1)
        return line
    }

    private fun readLine(timeoutMs: Long): String? {
        val t0 = System.currentTimeMillis()
        while (System.currentTimeMillis() - t0 < timeoutMs) {
            takeLine()?.let { if (it.isNotEmpty()) return it }
            if (fill(150) < 0) return null
        }
        return null
    }

    private fun drain() { val t0 = System.currentTimeMillis(); while (System.currentTimeMillis() - t0 < 400) fill(100); inbuf.reset() }

    private fun sendLine(cmd: String): String? {
        val p = port ?: return null
        return runCatching {
            p.write((cmd + "\n").toByteArray(), 1000)
            readLine(2000)
        }.onFailure { Log.w("Guarana", "usb: $cmd falhou: $it") }.getOrNull()
    }

    override suspend fun send(cmd: String): String? = withContext(Dispatchers.IO) { sendLine(cmd) }

    override suspend fun grabFrame(dest: File): Boolean = withContext(Dispatchers.IO) {
        val p = port ?: return@withContext false
        runCatching {
            drain()
            p.write("F\n".toByteArray(), 1000)
            var header = readLine(8000) ?: return@withContext false
            var guard = 5
            while (!header.startsWith("FRAME ") && guard-- > 0) header = readLine(3000) ?: return@withContext false   // ignora linhas de log
            val n = header.removePrefix("FRAME ").trim().toIntOrNull() ?: return@withContext false
            val t0 = System.currentTimeMillis()
            while (inbuf.size() < n && System.currentTimeMillis() - t0 < 30_000) { if (fill(500) < 0) break }
            if (inbuf.size() < n) return@withContext false
            val all = inbuf.toByteArray()
            dest.writeBytes(all.copyOfRange(0, n))
            inbuf.reset(); inbuf.write(all, n, all.size - n)
            true
        }.onFailure { Log.w("Guarana", "usb: quadro falhou: $it") }.getOrDefault(false)
    }

    override fun close() {
        runCatching { port?.close() }
        port = null; camReady = false; inbuf.reset()
    }
}
