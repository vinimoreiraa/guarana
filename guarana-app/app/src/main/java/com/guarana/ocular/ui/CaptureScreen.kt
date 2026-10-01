package com.guarana.ocular.ui

import androidx.compose.runtime.DisposableEffect
import com.guarana.ocular.core.EyeFraming
import java.util.concurrent.Executors
import androidx.camera.core.ImageProxy
import androidx.camera.core.ImageAnalysis
import android.Manifest
import android.content.pm.PackageManager
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CaptureRequest
import android.util.Log
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.camera2.interop.Camera2CameraControl
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.camera2.interop.CaptureRequestOptions
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.core.UseCaseGroup
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.core.view.doOnLayout
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.guarana.ocular.core.Patient
import com.guarana.ocular.core.Settings
import com.guarana.ocular.core.light.BleLightRig
import com.guarana.ocular.core.light.LightRig
import com.guarana.ocular.core.light.LightRigs
import com.guarana.ocular.core.light.LightRoutines
import com.guarana.ocular.core.light.RoutineStep
import com.guarana.ocular.core.light.TabletFlashRoutine
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.File
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

@OptIn(ExperimentalCamera2Interop::class)
@Composable
fun CaptureScreen(
    capturesDir: File,
    settings: Settings,
    patient: Patient?,
    onCaptured: (File, Boolean) -> Unit,
    onRoutineCaptured: (File, Boolean, List<Pair<String, File>>) -> Unit,
    onGallery: () -> Unit,
    onBack: () -> Unit,
) {
    val ctx = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    var granted by remember { mutableStateOf(ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted = it }
    LaunchedEffect(Unit) { if (!granted) permission.launch(Manifest.permission.CAMERA) }
    val blePermissions = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { }

    val imageCapture = remember {
        ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).setFlashMode(ImageCapture.FLASH_MODE_OFF).build()
    }
    // dica de enquadramento ao vivo: o mesmo gate da captura roda no quadro de luminancia do preview a cada ~250 ms
    var framingHint by remember { mutableStateOf<EyeFraming.Result?>(null) }
    val framingGate = remember { EyeFraming(ctx) }
    val analysisExecutor = remember { Executors.newSingleThreadExecutor() }
    val imageAnalysis = remember {
        ImageAnalysis.Builder().setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build().also { ia ->
            var last = 0L
            ia.setAnalyzer(analysisExecutor) { img ->
                val now = System.currentTimeMillis()
                if (now - last >= 250) { last = now; runCatching { framingFromY(img, framingGate) }.getOrNull()?.let { if (it.available) framingHint = it } }
                img.close()
            }
        }
    }
    DisposableEffect(Unit) { onDispose { analysisExecutor.shutdown() } }
    var child by remember { mutableStateOf(patient?.isChild ?: false) }
    var busy by remember { mutableStateOf(false) }
    var routineStatus by remember { mutableStateOf<String?>(null) }
    // anel ligado nos Ajustes, ou um ESP plugado na USB agora (checado a cada 2 s: plugar no meio da captura vale)
    var lightEnabled by remember { mutableStateOf(settings.lightEnabled || (settings.lightTransport == "usb" && LightRigs.usbAttached(ctx))) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(2000)
            lightEnabled = settings.lightEnabled || (settings.lightTransport == "usb" && LightRigs.usbAttached(ctx))
        }
    }
    val tabletFlash = remember { settings.tabletFlash }
    val usesRoutine = lightEnabled || tabletFlash
    var lightLevel by remember { mutableFloatStateOf(settings.lightLevel) }
    val cameraRef = remember { arrayOfNulls<Camera>(1) }

    // foco manual e zoom
    var manualFocus by remember { mutableStateOf(false) }
    var focusSupported by remember { mutableStateOf(true) }   // camera de foco fixo (tablets de entrada) esconde o controle
    var focus by remember { mutableFloatStateOf(0.5f) }
    var zoom by remember { mutableFloatStateOf(1f) }
    var maxZoom by remember { mutableFloatStateOf(1f) }

    // pausa da rotina (instrucao ao operador)
    var pauseText by remember { mutableStateOf<String?>(null) }
    val pauseGate = remember { arrayOfNulls<CompletableDeferred<Unit>>(1) }

    suspend fun takePhoto(file: File): File = suspendCancellableCoroutine { cont ->
        imageCapture.takePicture(
            ImageCapture.OutputFileOptions.Builder(file).build(), ContextCompat.getMainExecutor(ctx),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) { if (cont.isActive) cont.resume(file) }
                override fun onError(exception: ImageCaptureException) { if (cont.isActive) cont.resumeWithException(exception) }
            },
        )
    }

    fun singleShot() {
        busy = true
        scope.launch {
            try { val f = takePhoto(File(capturesDir, "cap_${System.currentTimeMillis()}.jpg")); busy = false; onCaptured(f, child) }
            catch (e: Exception) { busy = false; Toast.makeText(ctx, "Erro na captura: ${e.message}", Toast.LENGTH_SHORT).show() }
        }
    }

    /** Executa um comando local do tablet (flash) ou manda ao anel, ja com o nivel de luz aplicado. */
    suspend fun applyStep(rig: LightRig?, step: RoutineStep) {
        val cmd = step.command.trim()
        when {
            cmd.uppercase().startsWith("TORCH") -> cameraRef[0]?.cameraControl?.enableTorch(cmd.uppercase().contains("ON"))
            cmd.uppercase() == "NOP" -> {}
            rig != null -> rig.send(LightRoutines.scaleBrightness(cmd, lightLevel))
        }
    }

    /** Rotina de luz: para cada passo acende, espera a exposicao estabilizar e fotografa. */
    fun runRoutine() {
        if (lightEnabled && settings.lightTransport == "ble" && !BleLightRig.hasPermissions(ctx)) { blePermissions.launch(BleLightRig.permissions()); return }
        scope.launch {
            busy = true
            val text = if (lightEnabled) settings.routineText else TabletFlashRoutine.TEXTO
            val steps = LightRoutines.parse(text)
            var rig: LightRig? = null
            if (lightEnabled) {
                routineStatus = "Conectando ao anel de luz…"
                rig = LightRigs.create(ctx, settings)
                if (!rig.connect()) {
                    routineStatus = null; busy = false
                    Toast.makeText(ctx, "Anel de luz não encontrado (${rig.name})", Toast.LENGTH_LONG).show()
                    return@launch
                }
            }
            val frames = mutableListOf<Pair<String, File>>()
            var main: File? = null
            val stamp = System.currentTimeMillis()
            val principal = LightRoutines.principalLabel(steps)
            try {
                if (steps.isEmpty()) throw IllegalStateException("rotina vazia nos Ajustes")
                steps.forEachIndexed { i, step ->
                    if (step.pause.isNotBlank()) {
                        val gate = CompletableDeferred<Unit>(); pauseGate[0] = gate; pauseText = step.pause
                        gate.await(); pauseText = null
                    }
                    routineStatus = "Luz: ${step.label} · ${i + 1}/${steps.size}"
                    applyStep(rig, step)
                    delay(step.settleMs)
                    if (i == 0) { lockExposure(cameraRef[0], true); delay(250) }   // mesma exposicao em todos os quadros
                    if (step.capture) {
                        val f = takePhoto(File(capturesDir, "rot_${stamp}_$i.jpg"))
                        frames += step.label to f
                        if (step.label == principal) main = f
                    }
                }
            } catch (e: Exception) {
                Log.e("Guarana", "rotina de luz", e)
                Toast.makeText(ctx, "Rotina interrompida: ${e.message}", Toast.LENGTH_LONG).show()
            } finally {
                lockExposure(cameraRef[0], false)
                runCatching { cameraRef[0]?.cameraControl?.enableTorch(false) }
                runCatching { rig?.off() }
                rig?.close()
            }
            routineStatus = null; busy = false
            val chosen = main ?: frames.firstOrNull()?.second
            if (chosen != null) onRoutineCaptured(chosen, child, frames)
        }
    }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        if (granted) {
            AndroidView(
                factory = { c ->
                    PreviewView(c).apply {
                        scaleType = PreviewView.ScaleType.FILL_CENTER
                        implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                        doOnLayout {
                            bindCamera(this, lifecycleOwner, imageCapture, imageAnalysis) { cam ->
                                cameraRef[0] = cam
                                maxZoom = cam.cameraInfo.zoomState.value?.maxZoomRatio ?: 1f
                                focusSupported = focusRange(cam) > 0f
                            }
                        }
                    }
                },
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            Column(Modifier.align(Alignment.Center).padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Precisamos da câmera para fotografar o olho.", color = Color.White, style = MaterialTheme.typography.bodyLarge)
                Spacer(Modifier.padding(8.dp))
                Button(onClick = { permission.launch(Manifest.permission.CAMERA) }) { Text("Permitir câmera") }
            }
        }
        EyeGuideOverlay(Modifier.fillMaxSize(), when { framingHint == null -> G.Pink; framingHint!!.ok -> G.Leaf; framingHint!!.rejects -> G.Red; else -> G.Amber })

        // barra superior: voltar, paciente, crianca, microfone
        Row(Modifier.fillMaxWidth().statusBarsPadding().padding(8.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Voltar", tint = Color.White) }
            Text(
                patient?.let { it.name.ifBlank { it.code } } ?: "Sem paciente",
                color = Color.White, style = MaterialTheme.typography.labelLarge, maxLines = 1,
                modifier = Modifier.weight(1f).clip(CircleShape).background(Color.White.copy(alpha = 0.16f)).padding(horizontal = 12.dp, vertical = 6.dp),
            )
            FilterChip(
                selected = child, onClick = { child = !child }, label = { Text("Criança") },
                leadingIcon = if (child) ({ Icon(Icons.Outlined.Check, null, Modifier.size(16.dp)) }) else null,
                colors = FilterChipDefaults.filterChipColors(containerColor = Color.White.copy(alpha = 0.16f), labelColor = Color.White, selectedContainerColor = G.Pink, selectedLabelColor = G.Seed, selectedLeadingIconColor = G.Seed),
                border = null,
            )
        }

        routineStatus?.let { status ->
            Box(Modifier.align(Alignment.TopCenter).statusBarsPadding().padding(top = 64.dp)) {
                Text(status, color = G.Seed, style = MaterialTheme.typography.labelMedium, modifier = Modifier.clip(CircleShape).background(G.Cream).padding(horizontal = 14.dp, vertical = 7.dp))
            }
        }
        if (routineStatus == null && pauseText == null) framingHint?.let { fh ->
            Box(Modifier.align(Alignment.TopCenter).statusBarsPadding().padding(top = 64.dp)) {
                Text(
                    fh.reason.message, color = when { fh.ok -> G.LeafDark; fh.rejects -> G.RedDark; else -> G.AmberDark }, style = MaterialTheme.typography.labelMedium,
                    modifier = Modifier.clip(CircleShape).background(when { fh.ok -> G.LeafSoft; fh.rejects -> G.PinkSoft; else -> G.AmberSoft }).padding(horizontal = 14.dp, vertical = 7.dp),
                )
            }
        }

        // instrucao ao operador (sequencia de olhares)
        pauseText?.let { t ->
            Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.55f)), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(32.dp)) {
                    Text(t, color = Color.White, style = MaterialTheme.typography.headlineMedium)
                    Spacer(Modifier.height(18.dp))
                    PrimaryPill("Pronto", onClick = { pauseGate[0]?.complete(Unit) })
                }
            }
        }

        Column(Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 22.dp, start = 22.dp, end = 22.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            // zoom e foco
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Zoom", color = Color.White, style = MaterialTheme.typography.labelSmall, modifier = Modifier.width(44.dp))
                Slider(
                    value = zoom, onValueChange = { zoom = it; cameraRef[0]?.cameraControl?.setZoomRatio(it) },
                    valueRange = 1f..maxOf(1.01f, maxZoom), modifier = Modifier.weight(1f).height(28.dp),
                    colors = SliderDefaults.colors(thumbColor = Color.White, activeTrackColor = G.Pink, inactiveTrackColor = Color.White.copy(alpha = 0.3f)),
                )
            }
            if (!focusSupported) Text("Foco fixo nesta câmera", color = Color.White.copy(alpha = 0.7f), style = MaterialTheme.typography.labelSmall)
            else Row(verticalAlignment = Alignment.CenterVertically) {
                Text(if (manualFocus) "Foco" else "Foco auto", color = Color.White, style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.width(64.dp).clickable { manualFocus = !manualFocus; setFocus(cameraRef[0], if (manualFocus) focus else null) })
                Slider(
                    value = focus, onValueChange = { focus = it; if (!manualFocus) manualFocus = true; setFocus(cameraRef[0], it) },
                    modifier = Modifier.weight(1f).height(28.dp),
                    colors = SliderDefaults.colors(thumbColor = if (manualFocus) Color.White else Color.White.copy(alpha = 0.4f), activeTrackColor = if (manualFocus) G.Pink else Color.White.copy(alpha = 0.3f), inactiveTrackColor = Color.White.copy(alpha = 0.3f)),
                )
            }
            if (usesRoutine) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.padding(top = 2.dp)) {
                    listOf("Luz alta" to 1.0f, "Média" to 0.6f, "Baixa" to 0.3f).forEach { (l, v) ->
                        FilterChip(
                            selected = lightLevel == v, onClick = { lightLevel = v; settings.lightLevel = v }, label = { Text(l) }, border = null,
                            colors = FilterChipDefaults.filterChipColors(containerColor = Color.White.copy(alpha = 0.16f), labelColor = Color.White, selectedContainerColor = G.Pink, selectedLabelColor = G.Seed),
                        )
                    }
                }
            }
            Text(
                if (lightEnabled) "Branco, azul, vermelho e sem luz" else if (tabletFlash) "Flash do tablet e sem luz" else "Enquadre o olho na moldura, sem flash",
                color = Color.White.copy(alpha = 0.85f), style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 6.dp, bottom = 10.dp),
            )
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(36.dp)) {
                IconButton(onClick = onGallery, modifier = Modifier.size(56.dp)) { Icon(Icons.Outlined.Image, "Galeria", tint = Color.White, modifier = Modifier.size(28.dp)) }
                ShutterButton(enabled = granted && !busy) { if (usesRoutine) runRoutine() else singleShot() }
                if (usesRoutine) {
                    IconButton(onClick = { if (granted && !busy) singleShot() }, modifier = Modifier.size(56.dp)) {
                        Icon(Icons.Outlined.CameraAlt, "Foto única, sem sequência", tint = Color.White.copy(alpha = 0.8f), modifier = Modifier.size(26.dp))
                    }
                } else Spacer(Modifier.size(56.dp))
            }
        }
    }
}

/** Luminancia do preview, subamostrada para ~160 px e girada para a orientacao da tela, no gate de enquadramento. */
private fun framingFromY(img: ImageProxy, gate: EyeFraming): EyeFraming.Result {
    val plane = img.planes[0]; val buf = plane.buffer; val rs = plane.rowStride; val ps = plane.pixelStride
    val step = maxOf(1, img.width / 160)
    val w = img.width / step; val h = img.height / step
    val g = FloatArray(w * h)
    for (y in 0 until h) { val row = y * step * rs; for (x in 0 until w) g[y * w + x] = (buf.get(row + x * step * ps).toInt() and 0xFF).toFloat() }
    return when (img.imageInfo.rotationDegrees) {
        90 -> gate.checkGray(FloatArray(w * h) { i -> val ny = i / h; val nx = i % h; g[(h - 1 - nx) * w + ny] }, h, w)
        270 -> gate.checkGray(FloatArray(w * h) { i -> val ny = i / h; val nx = i % h; g[nx * w + (w - 1 - ny)] }, h, w)
        180 -> gate.checkGray(FloatArray(w * h) { i -> g[w * h - 1 - i] }, w, h)
        else -> gate.checkGray(g, w, h)
    }
}

private fun bindCamera(pv: PreviewView, owner: LifecycleOwner, capture: ImageCapture, analysis: ImageAnalysis, onCamera: (Camera) -> Unit) {
    val ctx = pv.context
    val future = ProcessCameraProvider.getInstance(ctx)
    future.addListener({
        val provider = future.get()
        val preview = Preview.Builder().build().also { it.setSurfaceProvider(pv.surfaceProvider) }
        val selector = if (provider.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA)) CameraSelector.DEFAULT_BACK_CAMERA else CameraSelector.DEFAULT_FRONT_CAMERA
        try {
            provider.unbindAll()
            val group = UseCaseGroup.Builder().addUseCase(preview).addUseCase(capture).addUseCase(analysis).also { b -> pv.viewPort?.let { b.setViewPort(it) } }.build()
            onCamera(provider.bindToLifecycle(owner, selector, group))
        } catch (e: Exception) {
            Log.e("Guarana", "Falha ao abrir a câmera", e)
        }
    }, ContextCompat.getMainExecutor(ctx))
}

@OptIn(ExperimentalCamera2Interop::class)
private fun lockExposure(camera: Camera?, lock: Boolean) {
    camera ?: return
    runCatching {
        Camera2CameraControl.from(camera.cameraControl).addCaptureRequestOptions(
            CaptureRequestOptions.Builder()
                .setCaptureRequestOption(CaptureRequest.CONTROL_AE_LOCK, lock)
                .setCaptureRequestOption(CaptureRequest.CONTROL_AWB_LOCK, lock).build(),
        )
    }.onFailure { Log.w("Guarana", "trava de exposição: $it") }
}

/** Alcance de foco da lente em dioptrias; 0 = foco fixo (sem lente movel), comum em tablets baratos. */
@OptIn(ExperimentalCamera2Interop::class)
private fun focusRange(camera: Camera): Float = runCatching {
    Camera2CameraInfo.from(camera.cameraInfo).getCameraCharacteristic(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE) ?: 0f
}.getOrDefault(0f)

/** Foco manual por distancia de lente (Camera2). fraction 0 = infinito, 1 = mais perto que a lente alcanca; null = automatico. */
@OptIn(ExperimentalCamera2Interop::class)
private fun setFocus(camera: Camera?, fraction: Float?) {
    camera ?: return
    runCatching {
        val b = CaptureRequestOptions.Builder()
        if (fraction == null) {
            b.setCaptureRequestOption(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
        } else {
            val minDist = Camera2CameraInfo.from(camera.cameraInfo).getCameraCharacteristic(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE) ?: 10f
            b.setCaptureRequestOption(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_OFF)
            b.setCaptureRequestOption(CaptureRequest.LENS_FOCUS_DISTANCE, fraction * minDist)
        }
        Camera2CameraControl.from(camera.cameraControl).addCaptureRequestOptions(b.build())
    }.onFailure { Log.w("Guarana", "foco manual: $it") }
}

@Composable
private fun ShutterButton(enabled: Boolean, onClick: () -> Unit) {
    Box(Modifier.size(80.dp).clip(CircleShape).border(4.dp, Color.White, CircleShape).clickable(enabled = enabled, onClick = onClick), contentAlignment = Alignment.Center) {
        Box(Modifier.size(64.dp).clip(CircleShape).background(if (enabled) G.Red else G.Pink))
    }
}

/** Escurece tudo menos uma elipse central, onde o olho deve ficar. */
@Composable
private fun EyeGuideOverlay(modifier: Modifier, ring: Color = G.Pink) {
    Canvas(modifier.graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }) {
        val w = size.width; val h = size.height
        val ow = w * 0.72f; val oh = ow * 0.6f
        val tl = Offset((w - ow) / 2f, (h - oh) / 2f)
        drawRect(Color.Black.copy(alpha = 0.45f))
        drawOval(Color.Transparent, topLeft = tl, size = Size(ow, oh), blendMode = BlendMode.Clear)
        drawOval(ring, topLeft = tl, size = Size(ow, oh), style = Stroke(width = 4f))
    }
}
