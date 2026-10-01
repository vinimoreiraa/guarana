package com.guarana.ocular.core

import android.content.Context

class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("guarana", Context.MODE_PRIVATE)
    var serverUrl: String
        get() = prefs.getString("server_url", "") ?: ""
        set(v) = prefs.edit().putString("server_url", v.trim()).apply()
    var useCloud: Boolean
        get() = prefs.getBoolean("use_cloud", false)
        set(v) = prefs.edit().putBoolean("use_cloud", v).apply()

    // anel de luz (ESP32)
    /** rejeita a foto quando o gate de enquadramento nao acha um olho perto e centralizado (desligar so para testes) */
    var requireEyeFraming: Boolean
        get() = prefs.getBoolean("require_eye_framing", true)
        set(v) = prefs.edit().putBoolean("require_eye_framing", v).apply()
    var validationFolder: String
        get() = prefs.getString("validation_folder", "") ?: ""
        set(v) = prefs.edit().putString("validation_folder", v).apply()
    var lightEnabled: Boolean
        get() = prefs.getBoolean("light_enabled", false)
        set(v) = prefs.edit().putBoolean("light_enabled", v).apply()
    var lightTransport: String                       // "usb", "ble" ou "wifi"
        get() = prefs.getString("light_transport", "usb") ?: "usb"
        set(v) = prefs.edit().putString("light_transport", v).apply()
    var lightHost: String
        get() = prefs.getString("light_host", "192.168.4.1") ?: "192.168.4.1"
        set(v) = prefs.edit().putString("light_host", v.trim()).apply()
    var lightDeviceName: String
        get() = prefs.getString("light_device", "Guarana-Luz") ?: "Guarana-Luz"
        set(v) = prefs.edit().putString("light_device", v.trim()).apply()
    var usbBaud: Int
        get() = prefs.getInt("usb_baud", 115200)
        set(v) = prefs.edit().putInt("usb_baud", v).apply()
    /** Anel v0: ESP32 DevKit com 9 LEDs comuns, 3 vermelhos (27, 33, 16), 3 brancos (26, 14, 4) e 3 azuis (5, 32, 2). */
    private val CFG_PADRAO = "CFG mode=pwm r=27,33,16 g=-1 b=5,32,2 w=26,14,4 flash=-1 ir=-1"
    private val CFG_ANTIGA = "CFG mode=ws pin=13 n=12 type=GRB flash=4"
    /** Linha CFG enviada ao conectar: pinos, quantidade e tipo de LED, flash. Nada disso fica fixo no firmware. */
    var lightConfigLine: String
        get() = prefs.getString("light_cfg", null)?.takeIf { it != CFG_ANTIGA } ?: CFG_PADRAO
        set(v) = prefs.edit().putString("light_cfg", v.trim()).apply()
    /** Rotina de cores editavel (ver LightRoutines.parse). */
    var routineText: String
        get() = prefs.getString("light_routine", null)?.takeIf { it.trim() != com.guarana.ocular.core.light.LightRoutines.PADRAO_ANTIGO } ?: com.guarana.ocular.core.light.LightRoutines.PADRAO_TEXTO
        set(v) = prefs.edit().putString("light_routine", v).apply()
    /** Escala de brilho aplicada aos comandos S da rotina: 1.0 alto, 0.6 medio, 0.3 baixo. */
    var lightLevel: Float
        get() = prefs.getFloat("light_level", 1.0f)
        set(v) = prefs.edit().putFloat("light_level", v).apply()
    /** Usar o flash do tablet como fonte de luz quando nao ha anel. */
    var tabletFlash: Boolean
        get() = prefs.getBoolean("tablet_flash", false)
        set(v) = prefs.edit().putBoolean("tablet_flash", v).apply()
    var cnes: String
        get() = prefs.getString("cnes", "") ?: ""
        set(v) = prefs.edit().putString("cnes", v.trim()).apply()
    var currentPatientId: String
        get() = prefs.getString("current_patient", "") ?: ""
        set(v) = prefs.edit().putString("current_patient", v).apply()
    /** "tablet" (camera do tablet) ou "espcam" (camera da ESP32-CAM pela serial). */
    var photoSource: String
        get() = prefs.getString("photo_source", "tablet") ?: "tablet"
        set(v) = prefs.edit().putString("photo_source", v).apply()
}
