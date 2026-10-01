package com.guarana.ocular.ui

import android.content.Intent
import androidx.lifecycle.compose.LifecycleResumeEffect
import com.guarana.ocular.esus.EsusCompanionService
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.pm.ShortcutInfoCompat
import androidx.core.content.pm.ShortcutManagerCompat
import androidx.core.graphics.drawable.IconCompat
import com.guarana.ocular.MainActivity
import com.guarana.ocular.R
import com.guarana.ocular.core.ModelCard
import com.guarana.ocular.core.Settings
import com.guarana.ocular.core.Signs
import com.guarana.ocular.core.light.BleLightRig
import com.guarana.ocular.core.light.LightRigs
import com.guarana.ocular.core.light.LightRoutines
import com.guarana.ocular.core.light.LightState
import androidx.compose.material3.TextButton
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    settings: Settings, card: ModelCard?, territoryStatus: String, onLoadMock: () -> Unit, onImport: () -> Unit, onClearTerritory: () -> Unit, onBack: () -> Unit,
    validationStatus: String = "", validationRunning: Boolean = false, onPickValidationFolder: () -> Unit = {}, onRunValidation: () -> Unit = {}, onShareValidation: (() -> Unit)? = null,
) {
    val ctx = LocalContext.current
    var url by remember { mutableStateOf(settings.serverUrl) }
    var useCloud by remember { mutableStateOf(settings.useCloud) }
    val version = remember { runCatching { ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull() ?: "?" }
    val scope = rememberCoroutineScope()
    var lightEnabled by remember { mutableStateOf(settings.lightEnabled) }
    var transport by remember { mutableStateOf(settings.lightTransport) }
    var lightHost by remember { mutableStateOf(settings.lightHost) }
    var lightDevice by remember { mutableStateOf(settings.lightDeviceName) }
    var lightStatus by remember { mutableStateOf("") }
    var tabletFlash by remember { mutableStateOf(settings.tabletFlash) }
    var requireFraming by remember { mutableStateOf(settings.requireEyeFraming) }
    var cnes by remember { mutableStateOf(settings.cnes) }
    var baud by remember { mutableStateOf(settings.usbBaud.toString()) }
    var cfgLine by remember { mutableStateOf(settings.lightConfigLine) }
    var routine by remember { mutableStateOf(settings.routineText) }
    var testing by remember { mutableStateOf(false) }
    val blePermissions = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { }
    fun testLight() {
        if (transport == "ble" && !BleLightRig.hasPermissions(ctx)) { blePermissions.launch(BleLightRig.permissions()); return }
        scope.launch {
            testing = true; lightStatus = if (transport == "usb") "Abrindo a porta USB… (aceite a permissão se aparecer)" else "Procurando…"
            val rig = LightRigs.create(ctx, settings)
            try {
                if (!rig.connect()) { lightStatus = "Não encontrado (${rig.name})"; return@launch }
                lightStatus = "Conectado · ${rig.name}"
                for (st in listOf(LightState.white(153), LightState(255, 0, 0), LightState(0, 255, 0), LightState(0, 0, 255))) {
                    rig.set(st); delay(450)
                }
                rig.off()
                lightStatus = "Funcionando · ${rig.ping() ?: rig.name}"
            } finally { rig.close(); testing = false }
        }
    }
    Scaffold(
        containerColor = G.Cream,
        topBar = {
            TopAppBar(
                title = { Text("Ajustes", style = MaterialTheme.typography.headlineSmall) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Voltar", tint = G.Seed) } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = G.Cream),
            )
        },
    ) { pad ->
        LazyColumn(
            Modifier.fillMaxSize().padding(pad),
            contentPadding = PaddingValues(start = 22.dp, end = 22.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                SoftCard {
                    Text("Nuvem", style = MaterialTheme.typography.titleSmall)
                    Text(
                        "Opcional. A análise no aparelho funciona sem internet. Com um servidor configurado, cada foto também é confirmada na nuvem quando houver conexão.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = url, onValueChange = { url = it; settings.serverUrl = it },
                        label = { Text("Endereço do servidor") }, placeholder = { Text("https://…/api") },
                        singleLine = true, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.small,
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Usar a nuvem quando disponível", modifier = Modifier.weight(1f))
                        Switch(checked = useCloud, onCheckedChange = { useCloud = it; settings.useCloud = it }, colors = SwitchDefaults.colors(checkedTrackColor = G.Red, checkedThumbColor = G.Cream))
                    }
                }
            }
            item {
                SoftCard {
                    Text("Território (e-SUS)", style = MaterialTheme.typography.titleSmall)
                    Text("Domicílios, pessoas e visitas vindos da exportação do PEC. O Guaraná não é a fonte da verdade do cadastro: importa e devolve.", style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                    Spacer(Modifier.height(6.dp))
                    Text(territoryStatus, style = MaterialTheme.typography.bodySmall, color = G.Ink3)
                    Spacer(Modifier.height(10.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        SecondaryPill("Importar JSON", Modifier.weight(1f), onClick = onImport)
                        SecondaryPill("Dados de demonstração", Modifier.weight(1f), onClick = onLoadMock)
                    }
                    TextButton(onClick = onClearTerritory) { Text("Limpar território", color = G.Ink2) }
                }
            }
            item {
                SoftCard {
                    Text("Agente de saúde", style = MaterialTheme.typography.titleSmall)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Usar o flash do tablet como luz")
                            Text("Sem anel: o disparador tira uma foto com o flash e outra sem, para subtrair o ambiente", style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                        }
                        Switch(checked = tabletFlash, onCheckedChange = { tabletFlash = it; settings.tabletFlash = it }, colors = SwitchDefaults.colors(checkedTrackColor = G.Red, checkedThumbColor = G.Cream))
                    }
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = cnes, onValueChange = { cnes = it.filter { c -> c.isDigit() }.take(7); settings.cnes = cnes },
                        label = { Text("CNES da unidade (para o FHIR)") }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.small,
                    )
                }
            }
            item {
                SoftCard {
                    Text("Anel de luz (ESP32)", style = MaterialTheme.typography.titleSmall)
                    Text(
                        "Iluminação padronizada: na captura, o botão de luz executa a sequência de cores e fotografa em cada passo.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Usar anel de luz", modifier = Modifier.weight(1f))
                        Switch(checked = lightEnabled, onCheckedChange = { lightEnabled = it; settings.lightEnabled = it }, colors = SwitchDefaults.colors(checkedTrackColor = G.Red, checkedThumbColor = G.Cream))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(selected = transport == "usb", onClick = { transport = "usb"; settings.lightTransport = "usb" }, label = { Text("USB") })
                        FilterChip(selected = transport == "ble", onClick = { transport = "ble"; settings.lightTransport = "ble" }, label = { Text("Bluetooth") })
                        FilterChip(selected = transport == "wifi", onClick = { transport = "wifi"; settings.lightTransport = "wifi" }, label = { Text("Wi-Fi") })
                    }
                    Spacer(Modifier.height(8.dp))
                    if (transport == "usb") {
                        OutlinedTextField(
                            value = baud, onValueChange = { baud = it; it.toIntOrNull()?.let { b -> settings.usbBaud = b } },
                            label = { Text("Velocidade serial (baud)") }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.small,
                        )
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(
                            value = cfgLine, onValueChange = { cfgLine = it; settings.lightConfigLine = it },
                            label = { Text("Configuração enviada ao conectar") }, placeholder = { Text("CFG mode=pwm r=27,33,16 g=-1 b=5,32,2 w=26,14,4 flash=-1") },
                            singleLine = true, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.small,
                        )
                        Text(
                            "Pino, quantidade e tipo dos LEDs e o pino do flash ficam aqui, gravados no ESP ao conectar. mode=pwm r= g= b= w= para LEDs comuns.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else if (transport == "wifi") {
                        OutlinedTextField(
                            value = lightHost, onValueChange = { lightHost = it; settings.lightHost = it },
                            label = { Text("Endereço do ESP") }, placeholder = { Text("192.168.4.1") },
                            singleLine = true, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.small,
                        )
                    } else {
                        OutlinedTextField(
                            value = lightDevice, onValueChange = { lightDevice = it; settings.lightDeviceName = it },
                            label = { Text("Nome Bluetooth do ESP") }, placeholder = { Text("Guarana-Luz") },
                            singleLine = true, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.small,
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                    val steps = LightRoutines.parse(routine)
                    Text("Rotina de cores · ${steps.size} passos · analisa \"${LightRoutines.principalLabel(steps) ?: "?"}\"", style = MaterialTheme.typography.labelLarge)
                    OutlinedTextField(
                        value = routine, onValueChange = { routine = it; settings.routineText = it },
                        label = { Text("rótulo; comando; espera ms; foto; pausa  (* = analisado; TORCH on/off = flash)") },
                        minLines = 4, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.small,
                        textStyle = MaterialTheme.typography.bodySmall,
                    )
                    TextButton(onClick = { routine = LightRoutines.PADRAO_TEXTO; settings.routineText = LightRoutines.PADRAO_TEXTO }) { Text("Restaurar rotina padrão") }
                    Spacer(Modifier.height(4.dp))
                    SecondaryPill(if (testing) "Testando…" else "Testar luz", Modifier.fillMaxWidth(), onClick = { if (!testing) testLight() })
                    if (lightStatus.isNotEmpty()) {
                        Spacer(Modifier.height(6.dp))
                        Text(lightStatus, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            item {
                SoftCard {
                    Text("Validação automática", style = MaterialTheme.typography.titleSmall)
                    Text("Roda o mesmo caminho da análise (qualidade, enquadramento, modelo, triagem) sobre uma pasta de imagens, sem fotografar. Com um manifest.csv (file;labels;triage;framing) mede sensibilidade, especificidade e concordância. O relatório vai para Downloads/guarana-validacao e pode ser compartilhado. Nada entra no histórico.",
                        style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                    Text(if (settings.validationFolder.isBlank()) "Nenhuma pasta escolhida." else "Pasta: " + java.net.URLDecoder.decode(settings.validationFolder.substringAfterLast("/"), "UTF-8"), style = MaterialTheme.typography.bodySmall, color = G.Ink3, modifier = Modifier.padding(top = 6.dp))
                    if (validationStatus.isNotBlank()) Text(validationStatus, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 6.dp))
                    Spacer(Modifier.height(10.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        SecondaryPill("Escolher pasta", Modifier.weight(1f), onClick = onPickValidationFolder)
                        PrimaryPill(if (validationRunning) "Rodando…" else "Rodar", Modifier.weight(1f), enabled = !validationRunning && settings.validationFolder.isNotBlank(), onClick = onRunValidation)
                    }
                    if (onShareValidation != null) { Spacer(Modifier.height(8.dp)); SecondaryPill("Compartilhar relatório", Modifier.fillMaxWidth(), onClick = onShareValidation) }
                }
            }
            item {
                SoftCard {
                    Text("Enquadramento do olho", style = MaterialTheme.typography.titleSmall)
                    Text("A captura só aceita a foto quando encontra um olho perto, centralizado e sozinho na moldura; senão recusa e diz o que ajustar. Desligue apenas para testar com imagens que não são de olho.",
                        style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                    Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(if (requireFraming) "Exigir enquadramento (recomendado)" else "Enquadramento só avisa, não recusa", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                        Switch(checked = requireFraming, onCheckedChange = { requireFraming = it; settings.requireEyeFraming = it }, colors = SwitchDefaults.colors(checkedTrackColor = G.Red, checkedThumbColor = G.Cream))
                    }
                }
            }
            item {
                SoftCard {
                    Text("Companheiro do e-SUS", style = MaterialTheme.typography.titleSmall)
                    var companion by remember { mutableStateOf(EsusCompanionService.isEnabled(ctx)) }
                    LifecycleResumeEffect(Unit) { companion = EsusCompanionService.isEnabled(ctx); onPauseOrDispose {} }
                    Text(
                        if (companion) "Ativo. Quando o e-SUS Território abrir, a pílula \"Analisar olho\" aparece por cima dele; o resultado tem \"Voltar ao e-SUS\"."
                        else "Desativado. Ative o serviço \"Guaraná · companheiro do e-SUS\" em Acessibilidade para a pílula aparecer sobre o e-SUS Território.",
                        style = MaterialTheme.typography.bodySmall, color = G.Ink2,
                    )
                    Text("O serviço só consulta qual app está em primeiro plano. Não lê o conteúdo da tela do e-SUS.", style = MaterialTheme.typography.bodySmall, color = G.Ink3, modifier = Modifier.padding(top = 4.dp))
                    Spacer(Modifier.height(10.dp))
                    SecondaryPill(if (companion) "Abrir Acessibilidade" else "Ativar na Acessibilidade", Modifier.fillMaxWidth(), onClick = {
                        ctx.startActivity(Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    })
                }
            }
            item {
                SoftCard {
                    Text("Modelo local", style = MaterialTheme.typography.titleSmall)
                    if (card == null) {
                        Text("Não carregado.", style = MaterialTheme.typography.bodySmall)
                    } else {
                        Text("${card.name} · entrada ${card.inputSize}×${card.inputSize} · ${card.file}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(10.dp))
                        card.labels.forEach { id ->
                            Row(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
                                Text(Signs.name(id), modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                                Text("limiar %.2f".format(card.thresholds[id] ?: 0.5f), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
            item {
                SoftCard {
                    Text("Tela inicial", style = MaterialTheme.typography.titleSmall)
                    Text(
                        "Cria um atalho do Guaraná na tela inicial. Ele continua lá quando uma versão nova é instalada por cima.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(12.dp))
                    SecondaryPill("Fixar na tela inicial", Modifier.fillMaxWidth(), onClick = {
                            if (ShortcutManagerCompat.isRequestPinShortcutSupported(ctx)) {
                                val intent = Intent(ctx, MainActivity::class.java).setAction(Intent.ACTION_MAIN)
                                val info = ShortcutInfoCompat.Builder(ctx, "guarana-inicio")
                                    .setShortLabel("Guaraná")
                                    .setLongLabel("Guaraná · triagem ocular")
                                    .setIcon(IconCompat.createWithResource(ctx, R.mipmap.ic_launcher))
                                    .setIntent(intent)
                                    .build()
                                ShortcutManagerCompat.requestPinShortcut(ctx, info, null)
                            }
                        })
                }
            }
            item {
                SoftCard {
                    Text("Sobre · versão $version", style = MaterialTheme.typography.titleSmall)
                    Text(
                        "Guaraná é uma demonstração experimental de triagem de sinais no olho externo a partir de foto comum. " +
                            "Os limiares favorecem sensibilidade: prefere-se um alarme falso a um sinal perdido. " +
                            "Nada aqui substitui exame oftalmológico.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
