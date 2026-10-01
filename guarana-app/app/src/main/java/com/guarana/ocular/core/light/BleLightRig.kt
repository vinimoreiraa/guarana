package com.guarana.ocular.core.light

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import java.util.UUID
import kotlin.coroutines.resume

/**
 * ESP32 anunciando o servico "UART" da Nordic. O app escreve comandos na caracteristica RX.
 * Bluetooth e o transporte preferido em campo: nao tira o tablet da internet nem exige configurar rede.
 */
class BleLightRig(private val context: Context, private val deviceName: String) : LightRig {
    override val name: String get() = "Bluetooth · $deviceName"
    private val adapter get() = (context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
    private var gatt: BluetoothGatt? = null
    private var rx: BluetoothGattCharacteristic? = null
    private var ready = CompletableDeferred<Boolean>()

    companion object {
        val SERVICE: UUID = UUID.fromString("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
        val RX: UUID = UUID.fromString("6e400002-b5a3-f393-e0a9-e50e24dcca9e")

        fun permissions(): Array<String> =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
            else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)

        fun hasPermissions(context: Context): Boolean =
            permissions().all { ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED }
    }

    private val callback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                @SuppressLint("MissingPermission") val r = g.discoverServices()
                if (!r && !ready.isCompleted) ready.complete(false)
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                rx = null
                if (!ready.isCompleted) ready.complete(false)
            }
        }
        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            rx = g.getService(SERVICE)?.getCharacteristic(RX)
            if (!ready.isCompleted) ready.complete(rx != null)
        }
    }

    @SuppressLint("MissingPermission")
    override suspend fun connect(): Boolean {
        if (!hasPermissions(context) || adapter?.isEnabled != true) return false
        if (gatt != null && rx != null) return true
        close()
        val device = scan() ?: return false
        ready = CompletableDeferred()
        gatt = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE)
        val ok = withTimeoutOrNull(10_000) { ready.await() } ?: false
        if (!ok) close()
        return ok
    }

    @SuppressLint("MissingPermission")
    private suspend fun scan(): BluetoothDevice? = withTimeoutOrNull(8_000) {
        suspendCancellableCoroutine { cont ->
            val scanner = adapter?.bluetoothLeScanner
            if (scanner == null) { cont.resume(null); return@suspendCancellableCoroutine }
            val cb = object : ScanCallback() {
                override fun onScanResult(callbackType: Int, result: ScanResult) {
                    val n = result.device.name ?: result.scanRecord?.deviceName ?: return
                    if (n.startsWith(deviceName, ignoreCase = true)) {
                        runCatching { scanner.stopScan(this) }
                        if (cont.isActive) cont.resume(result.device)
                    }
                }
                override fun onScanFailed(errorCode: Int) { if (cont.isActive) cont.resume(null) }
            }
            scanner.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), cb)
            cont.invokeOnCancellation { runCatching { scanner.stopScan(cb) } }
        }
    }

    @SuppressLint("MissingPermission")
    @Suppress("DEPRECATION")
    private suspend fun write(cmd: String): Boolean {
        val g = gatt ?: return false
        val c = rx ?: return false
        val bytes = (cmd + "\n").toByteArray()
        val ok = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            g.writeCharacteristic(c, bytes, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE) == BluetoothStatusCodes.SUCCESS
        } else {
            c.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
            c.value = bytes
            g.writeCharacteristic(c)
        }
        delay(80)   // folga entre escritas sem resposta
        return ok
    }

    /** BLE aqui e so escrita (sem esperar notify): a resposta e sintetica. */
    override suspend fun send(cmd: String): String? = if (write(cmd)) "{\"ok\":true,\"via\":\"ble\"}" else null

    @SuppressLint("MissingPermission")
    override fun close() {
        runCatching { gatt?.disconnect(); gatt?.close() }
        gatt = null; rx = null
    }
}
