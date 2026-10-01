package com.guarana.ocular.core.light

import android.content.Context
import com.guarana.ocular.core.Settings
import java.io.File

/**
 * Protocolo de texto compartilhado por USB, Bluetooth e Wi-Fi (o firmware tem um unico parser):
 *   "S" + RR GG BB WW II em hex -> cor (r,g,b), canal branco (w) e brilho geral (i), ex.: SFFFFFFFF99
 *   "O" apaga · "P" ping · "FL ii" flash da placa · "L i RRGGBB" + "X" LED a LED · "CFG ..." configura · "F" quadro da camera
 */
data class LightState(val r: Int, val g: Int, val b: Int, val w: Int = 0, val bri: Int = 255) {
    fun command(): String = "S%02X%02X%02X%02X%02X".format(r.coerceIn(0, 255), g.coerceIn(0, 255), b.coerceIn(0, 255), w.coerceIn(0, 255), bri.coerceIn(0, 255))
    companion object {
        val OFF = LightState(0, 0, 0, 0, 0)
        fun white(bri: Int) = LightState(255, 255, 255, 255, bri)
    }
}

interface LightRig {
    val name: String
    suspend fun connect(): Boolean
    /** Envia um comando cru do protocolo e devolve a resposta (ou null se falhou). */
    suspend fun send(cmd: String): String?
    suspend fun set(state: LightState): Boolean = send(state.command()) != null
    suspend fun off(): Boolean = send("O") != null
    suspend fun ping(): String? = send("P")
    /** Quadro JPEG da camera do proprio ESP (ESP32-CAM). So o transporte serial implementa. */
    suspend fun grabFrame(dest: File): Boolean = false
    val canGrabFrame: Boolean get() = false
    fun close()
}

/** Um passo da rotina: manda o comando, espera a exposicao estabilizar e fotografa. */
data class RoutineStep(
    val label: String, val command: String, val settleMs: Long = 400, val capture: Boolean = true, val principal: Boolean = false,
    /** Texto mostrado ao operador antes da foto (ex.: "Peca para olhar para a esquerda"); a rotina espera a confirmacao. */
    val pause: String = "",
) {
    /** Comandos que o proprio tablet executa em vez de mandar ao ESP: TORCH on/off (flash da camera), NOP. */
    val isLocal: Boolean get() = command.uppercase().startsWith("TORCH") || command.uppercase() == "NOP"
}

object LightRoutines {
    /** Formato editavel nos Ajustes: `rotulo; comando; espera_ms; foto; pausa-texto`. Linha com `*` no inicio e o quadro analisado.
     *  Comandos locais: `TORCH on` / `TORCH off` (flash do tablet) e `NOP` (nao muda a luz). */
    val PADRAO_TEXTO = """
        *Branco; SFFFFFFFF99; 600; foto
        Azul; S0000FF00FF; 500; foto
        Vermelho; SFF000000FF; 500; foto
        Ambiente; O; 500; foto
    """.trimIndent()
    val PADRAO_ANTIGO = """
        Branco 30%; SFFFFFFFF4D; 400; foto
        *Branco 60%; SFFFFFFFF99; 400; foto
        Branco 100%; SFFFFFFFFFF; 400; foto
        Vermelho; SFF000000FF; 400; foto
        Verde; S00FF0000FF; 400; foto
        Azul; S0000FF00FF; 400; foto
        Ambiente; O; 300; foto
    """.trimIndent()

    fun parse(text: String): List<RoutineStep> = text.lines().mapNotNull { raw ->
        val line = raw.trim()
        if (line.isEmpty() || line.startsWith("#")) return@mapNotNull null
        val parts = line.split(";").map { it.trim() }
        if (parts.size < 2) return@mapNotNull null
        val principal = parts[0].startsWith("*")
        RoutineStep(
            label = parts[0].removePrefix("*").trim().ifEmpty { "Passo" },
            command = parts[1],
            settleMs = parts.getOrNull(2)?.toLongOrNull() ?: 400L,
            capture = parts.getOrNull(3)?.let { it.lowercase().startsWith("s") || it.lowercase().startsWith("f") || it == "1" } ?: true,
            principal = principal,
            pause = parts.getOrNull(4).orEmpty(),
        )
    }

    /** Aplica o nivel de luz (1.0 alto, 0.6 medio, 0.3 baixo) ao brilho de um comando S; outros comandos passam intactos. */
    fun scaleBrightness(cmd: String, level: Float): String {
        val c = cmd.trim().replace(" ", "")
        if (!c.uppercase().startsWith("S") || c.length < 11) return cmd
        val bri = c.substring(9, 11).toIntOrNull(16) ?: return cmd
        return c.substring(0, 9) + "%02X".format((bri * level).toInt().coerceIn(0, 255))
    }

    fun principalLabel(steps: List<RoutineStep>): String? = (steps.firstOrNull { it.principal } ?: steps.firstOrNull { it.capture })?.label
}

/** Rotina so com o flash do tablet, para quem nao tem o anel. */
object TabletFlashRoutine {
    val TEXTO = """
        *Flash do tablet; TORCH on; 700; foto
        Ambiente; TORCH off; 500; foto
    """.trimIndent()
}

object LightRigs {
    fun create(context: Context, settings: Settings): LightRig = when (settings.lightTransport) {
        "wifi" -> HttpLightRig(settings.lightHost)
        "ble" -> BleLightRig(context, settings.lightDeviceName)
        else -> UsbSerialLightRig(context, settings.usbBaud, settings.lightConfigLine)
    }
}
