package com.guarana.ocular

import com.guarana.ocular.core.FramingRejected
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.guarana.ocular.core.Analysis
import com.guarana.ocular.core.Pipeline
import com.guarana.ocular.core.Report
import com.guarana.ocular.core.Household
import com.guarana.ocular.core.Patient
import com.guarana.ocular.core.Visit
import com.guarana.ocular.core.VisitState
import com.guarana.ocular.esus.CompanionBridge
import com.guarana.ocular.esus.EsusCompanionService
import com.guarana.ocular.esus.EsusSummary
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import com.guarana.ocular.ui.AgendaScreen
import com.guarana.ocular.ui.MapScreen
import org.json.JSONObject
import java.time.LocalDate
import com.guarana.ocular.core.fhir.FhirExport
import com.guarana.ocular.ui.CaptureScreen
import com.guarana.ocular.ui.GuaranaTheme
import com.guarana.ocular.ui.HomeScreen
import com.guarana.ocular.ui.PatientsScreen
import com.guarana.ocular.ui.ProcessingScreen
import com.guarana.ocular.ui.ResultScreen
import com.guarana.ocular.ui.SettingsScreen
import com.guarana.ocular.ui.TerritoryScreen
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class MainActivity : ComponentActivity() {
    companion object { const val EXTRA_FROM_ESUS = "from_esus"; const val EXTRA_CAPTURE = "capture" }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val pipeline = Pipeline(this)
        handleCompanion(intent)
        setContent { GuaranaTheme { GuaranaApp(pipeline) } }
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); handleCompanion(intent) }

    /** Aberto pela pilula por cima do e-SUS: guarda de onde veio e pede a captura. */
    private fun handleCompanion(i: Intent?) { i?.getStringExtra(EXTRA_FROM_ESUS)?.let { CompanionBridge.open(it, i.getBooleanExtra(EXTRA_CAPTURE, true)) } }
}

sealed interface Screen {
    data object Home : Screen
    data object Capture : Screen
    data class Processing(val file: File, val child: Boolean, val frames: List<Pair<String, File>> = emptyList()) : Screen
    data class Result(val analysis: Analysis) : Screen
    data object Settings : Screen
    data object Patients : Screen
    data object Agenda : Screen
    data object Map : Screen
    data object Territory : Screen
}

@Composable
fun GuaranaApp(pipeline: Pipeline) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var screen by remember { mutableStateOf<Screen>(Screen.Home) }
    var history by remember { mutableStateOf(pipeline.store.list()) }
    var patients by remember { mutableStateOf(pipeline.patients.list()) }
    var currentPatientId by remember { mutableStateOf(pipeline.settings.currentPatientId) }
    val currentPatient = patients.firstOrNull { it.id == currentPatientId }
    val version = remember { runCatching { ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull() ?: "?" }
    fun toast(t: String) = Toast.makeText(ctx, t, Toast.LENGTH_SHORT).show()
    fun selectPatient(id: String) { currentPatientId = id; pipeline.settings.currentPatientId = id }
    var visits by remember { mutableStateOf(pipeline.territory.visits()) }
    var households by remember { mutableStateOf(pipeline.territory.households().associateBy { it.uuid }) }
    var agendaDate by remember { mutableStateOf(LocalDate.now().toString()) }
    fun refreshTerritory() { visits = pipeline.territory.visits(); households = pipeline.territory.households().associateBy { it.uuid }; patients = pipeline.patients.list() }
    val hoje = LocalDate.now().toString()
    val territoryStatus = pipeline.territory.unidade()?.let { u -> "${u.optString("nome")} · ${households.size} domicílios · ${patients.count { it.householdId.isNotBlank() }} pessoas · ${visits.size} visitas" } ?: "Nenhum território importado"
    val importTerritory = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) runCatching {
            val txt = ctx.contentResolver.openInputStream(uri)!!.bufferedReader().use { it.readText() }
            pipeline.territory.importTerritory(JSONObject(txt), pipeline.patients)
        }.onSuccess { refreshTerritory(); toast("Importado: ${it.unidade} · ${it.households} domicílios · ${it.people} pessoas · ${it.visits} visitas") }
            .onFailure { toast("Importação falhou: ${it.message}") }
    }
    fun startVisit(v: Visit) {
        if (v.patientId.isNotBlank()) selectPatient(v.patientId)
        screen = Screen.Capture
    }
    // validacao automatica (Ajustes): pasta persistida via SAF, execucao fora da UI, relatorio compartilhavel
    var validationStatus by remember { mutableStateOf("") }
    var validationRunning by remember { mutableStateOf(false) }
    var validationReport by remember { mutableStateOf<com.guarana.ocular.core.Validation.Report?>(null) }
    val pickValidationFolder = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            runCatching { ctx.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            pipeline.settings.validationFolder = uri.toString(); validationStatus = "Pasta escolhida. Toque em Rodar."
        }
    }
    fun runValidation() {
        val tree = pipeline.settings.validationFolder.takeIf { it.isNotBlank() }?.let { android.net.Uri.parse(it) } ?: return
        validationRunning = true; validationStatus = "Preparando…"
        scope.launch {
            val r = withContext(Dispatchers.Default) {
                runCatching { com.guarana.ocular.core.Validation(ctx, pipeline).run(tree, pipeline.settings.requireEyeFraming) { done, total -> validationStatus = "Analisando $done de $total…" } }
            }
            validationRunning = false
            r.onSuccess { validationReport = it; validationStatus = "Concluído: " + it.summary + (if (it.downloadsUri != null) " · relatório em Downloads/guarana-validacao" else "") }
                .onFailure { validationStatus = "Falhou: ${it.message}" }
        }
    }
    fun setVisitState(v: Visit, st: VisitState) { pipeline.territory.updateVisit(v.copy(state = st, updatedAt = System.currentTimeMillis())); refreshTerritory() }
    /** "Visitar" a partir do territorio: reaproveita a visita planejada de hoje ou cria uma (busca ativa: exame) e abre a captura. */
    fun scheduleVisit(h: Household, p: Patient) {
        val v = visits.firstOrNull { it.date == hoje && it.patientId == p.id && it.state == VisitState.planejada }
            ?: Visit(uuid = UUID.randomUUID().toString(), householdId = h.uuid, patientId = p.id, date = hoje, turno = "", state = VisitState.planejada,
                motivo = "Busca ativa: exame", profissional = "", observacao = "").also { pipeline.territory.addVisit(it); refreshTerritory() }
        startVisit(v)
    }


    val pickImage = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) {
            val f = File(pipeline.store.capturesDir, "gal_${System.currentTimeMillis()}.jpg")
            ctx.contentResolver.openInputStream(uri)?.use { i -> f.outputStream().use { o -> i.copyTo(o) } }
            screen = Screen.Processing(f, currentPatient?.isChild ?: false)
        }
    }
    val openGallery = { pickImage.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }

    fun exportReport(a: Analysis) = scope.launch {
        runCatching { withContext(Dispatchers.IO) { Report.pdf(ctx, a, pipeline.patients.get(a.patientId), pipeline.settings.cnes, version) } }
            .onSuccess { Report.share(ctx, it, "application/pdf", "Relatório Guaraná") }
            .onFailure { toast("Relatório falhou: ${it.message}") }
    }
    fun exportFhir(a: Analysis) = scope.launch {
        runCatching { withContext(Dispatchers.IO) { FhirExport.toFile(ctx, a, pipeline.patients.get(a.patientId), pipeline.settings.cnes, version) } }
            .onSuccess { Report.share(ctx, it, "application/fhir+json", "Bundle FHIR Guaraná") }
            .onFailure { toast("FHIR falhou: ${it.message}") }
    }
    fun exportProtected(a: Analysis, password: String) = scope.launch {
        runCatching {
            withContext(Dispatchers.IO) {
                val p = pipeline.patients.get(a.patientId)
                val pdf = Report.pdf(ctx, a, p, pipeline.settings.cnes, version)
                val fhir = FhirExport.toFile(ctx, a, p, pipeline.settings.cnes, version)
                val json = File(ctx.cacheDir, "relatorios/analise_${a.createdAt}.json").also { it.writeText(a.toJson().toString(2)) }
                Report.protectedZip(ctx, listOf(pdf, fhir, json, File(a.imagePath)) + a.frames.map { File(it.path) }, password, "guarana_${a.createdAt}")
            }
        }.onSuccess { Report.share(ctx, it, "application/zip", "Exportação protegida Guaraná") }
            .onFailure { toast("Exportação falhou: ${it.message}") }
    }

    /** Aberto pela pilula do e-SUS: voltar da captura, do processamento ou do resultado devolve o agente ao e-SUS. */
    fun back() {
        val fromEsus = CompanionBridge.esusPackage != null && (screen is Screen.Capture || screen is Screen.Processing || screen is Screen.Result)
        if (fromEsus && CompanionBridge.backToEsus(ctx)) CompanionBridge.clear()
        screen = Screen.Home
    }
    BackHandler(enabled = screen != Screen.Home) { back() }
    // toque na pilula do e-SUS: vai direto para a captura
    LaunchedEffect(CompanionBridge.requestId) { if (CompanionBridge.requestId > 0 && CompanionBridge.esusPackage != null) screen = if (CompanionBridge.capture) Screen.Capture else Screen.Home }

    when (val s = screen) {
        Screen.Home -> HomeScreen(
            items = history, patient = currentPatient, visits = visits, households = households, patients = patients.associateBy { it.id },
            unidade = pipeline.territory.unidade()?.optString("nome").orEmpty(), date = hoje,
            onNew = { screen = Screen.Capture }, onGallery = openGallery, onOpen = { screen = Screen.Result(it) },
            onSettings = { screen = Screen.Settings }, onPatients = { screen = Screen.Patients },
            onAgenda = { agendaDate = hoje; screen = Screen.Agenda }, onMap = { agendaDate = hoje; screen = Screen.Map }, onTerritory = { screen = Screen.Territory },
            onStartVisit = { startVisit(it) },
        )
        Screen.Territory -> TerritoryScreen(
            households = households, patients = patients.associateBy { it.id }, visits = visits,
            municipio = pipeline.territory.unidade()?.let { u -> listOfNotNull(u.optString("municipio").takeIf { it.isNotBlank() }, u.optString("uf").takeIf { it.isNotBlank() }).joinToString("/") }.orEmpty(),
            onAnalyze = { p -> selectPatient(p.id); screen = Screen.Capture }, onVisit = { h, p -> scheduleVisit(h, p) },
            onMap = { agendaDate = hoje; screen = Screen.Map }, onImport = { importTerritory.launch(arrayOf("application/json", "text/plain", "*/*")) }, onBack = { screen = Screen.Home },
        )
        Screen.Capture -> CaptureScreen(
            capturesDir = pipeline.store.capturesDir, settings = pipeline.settings, patient = currentPatient,
            onCaptured = { f, child -> screen = Screen.Processing(f, child) },
            onRoutineCaptured = { f, child, frames -> screen = Screen.Processing(f, child, frames) },
            onGallery = openGallery, onBack = { back() },
        )
        is Screen.Processing -> {
            ProcessingScreen()
            LaunchedEffect(s) {
                val r = withContext(Dispatchers.Default) { runCatching { pipeline.run(s.file, s.child, s.frames, currentPatientId) } }
                r.onSuccess { history = pipeline.store.list(); screen = Screen.Result(it) }
                    .onFailure { e ->
                        if (e is FramingRejected) { android.util.Log.w("Guarana", "foto recusada pelo enquadramento: ${e.result.reason} (${"%.2f".format(e.result.confidence)})"); toast("Foto recusada: ${e.message}"); screen = Screen.Capture }
                        else { toast("Não foi possível analisar: ${e.message}"); screen = Screen.Home }
                    }
            }
        }
        is Screen.Result -> ResultScreen(
            a = s.analysis, patient = pipeline.patients.get(s.analysis.patientId),
            unreliable = runCatching { pipeline.local.card.unreliable }.getOrDefault(emptySet()),
            thresholds = runCatching { pipeline.local.card.thresholds }.getOrDefault(emptyMap()),
            onBack = { back() }, onNew = { screen = Screen.Capture },
            onDelete = { pipeline.store.delete(s.analysis); history = pipeline.store.list(); screen = Screen.Home },
            onNotes = { n -> pipeline.store.update(s.analysis.copy(notes = n)); history = pipeline.store.list() },
            onReport = { exportReport(s.analysis) }, onFhir = { exportFhir(s.analysis) }, onProtected = { pw -> exportProtected(s.analysis, pw) },
            onCopyEsus = {
                val cm = ctx.getSystemService(ClipboardManager::class.java)
                cm.setPrimaryClip(ClipData.newPlainText("Guaraná", EsusSummary.text(s.analysis, pipeline.patients.get(s.analysis.patientId))))
                toast("Resumo copiado. No e-SUS, cole em \"Condição extra\" ou marque o motivo da visita.")
            },
            onBackToEsus = CompanionBridge.esusPackage?.let { { if (!CompanionBridge.backToEsus(ctx)) toast("e-SUS não encontrado neste aparelho") } },
            onRegisterEsus = if (CompanionBridge.installedEsus(ctx) == null) null else ({
                val f = EsusSummary.fill(s.analysis, pipeline.patients.get(s.analysis.patientId))
                if (!EsusCompanionService.isEnabled(ctx)) toast("Ative o companheiro do e-SUS em Ajustes para preencher automaticamente")
                if (!CompanionBridge.registerVisit(ctx, f)) toast("e-SUS não encontrado neste aparelho")
            }),
        )
        Screen.Settings -> SettingsScreen(
            settings = pipeline.settings, card = runCatching { pipeline.local.card }.getOrNull(), territoryStatus = territoryStatus,
            onLoadMock = { runCatching { pipeline.territory.loadMock(ctx, pipeline.patients) }.onSuccess { refreshTerritory(); toast("Demonstração: ${it.households} domicílios · ${it.people} pessoas · ${it.visits} visitas") }.onFailure { toast("Falhou: ${it.message}") } },
            onImport = { importTerritory.launch(arrayOf("application/json", "text/plain", "*/*")) },
            onClearTerritory = { pipeline.territory.clear(pipeline.patients); refreshTerritory(); toast("Território removido") },
            onBack = { screen = Screen.Home },
            validationStatus = validationStatus, validationRunning = validationRunning,
            onPickValidationFolder = { pickValidationFolder.launch(null) }, onRunValidation = { runValidation() },
            onShareValidation = validationReport?.let { rep -> { Report.share(ctx, rep.mdFile, "text/markdown", "Relatório de validação Guaraná") } },
        )
        Screen.Agenda -> AgendaScreen(
            visits = visits, households = households, patients = patients.associateBy { it.id }, selectedDate = agendaDate,
            onDate = { agendaDate = it }, onStart = { startVisit(it) }, onState = { v, st -> setVisitState(v, st) },
            onMap = { screen = Screen.Map }, onImport = { importTerritory.launch(arrayOf("application/json", "text/plain", "*/*")) }, onBack = { screen = Screen.Home },
        )
        Screen.Map -> MapScreen(
            date = agendaDate, visits = visits, households = households, patients = patients.associateBy { it.id },
            onStart = { startVisit(it) }, onBack = { screen = Screen.Agenda },
        )
        Screen.Patients -> PatientsScreen(
            patients = patients, analyses = history, currentId = currentPatientId,
            onSelect = { selectPatient(it.id); toast("Paciente selecionado") },
            onCreate = { n, cns, by, sex -> val p = pipeline.patients.create(n, cns, "", by, sex); patients = pipeline.patients.list(); selectPatient(p.id) },
            onOpenAnalysis = { screen = Screen.Result(it) }, onBack = { screen = Screen.Home },
        )
    }
}
