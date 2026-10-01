package com.guarana.ocular.ui

import androidx.compose.material.icons.outlined.ExpandMore
import androidx.compose.material.icons.outlined.ExpandLess
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.clickable
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.geometry.Offset
import androidx.compose.foundation.Canvas
import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.text.input.PasswordVisualTransformation
import com.guarana.ocular.core.Patient
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import com.guarana.ocular.core.Analysis
import com.guarana.ocular.core.Sign
import com.guarana.ocular.core.SignState
import com.guarana.ocular.core.Signs
import com.guarana.ocular.core.Store

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResultScreen(
    a: Analysis, patient: Patient?, unreliable: Set<String>,
    onBack: () -> Unit, onNew: () -> Unit, onDelete: () -> Unit,
    onNotes: (String) -> Unit, onReport: () -> Unit, onFhir: () -> Unit, onProtected: (String) -> Unit,
    onCopyEsus: () -> Unit = {}, onBackToEsus: (() -> Unit)? = null, onRegisterEsus: (() -> Unit)? = null,
    thresholds: Map<String, Float> = emptyMap(),
) {
    var notes by remember { mutableStateOf(a.notes) }
    // sinal cujo mapa de ativacao esta sobre a foto (toque num sinal para trocar)
    var explainId by remember { mutableStateOf(a.signs.firstOrNull { it.state == SignState.present && a.explain.containsKey(it.id) }?.id ?: a.signs.firstOrNull { a.explain.containsKey(it.id) }?.id) }
    var askPassword by remember { mutableStateOf(false) }
    var password by remember { mutableStateOf("") }
    if (askPassword) {
        AlertDialog(
            onDismissRequest = { askPassword = false },
            title = { Text("Exportar protegido") },
            text = {
                Column {
                    Text("PDF, JSON e fotos num ZIP com AES-256. Quem receber precisa da senha.", style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(value = password, onValueChange = { password = it }, label = { Text("Senha") }, singleLine = true, visualTransformation = PasswordVisualTransformation())
                }
            },
            confirmButton = { TextButton(onClick = { if (password.length >= 4) { onProtected(password); askPassword = false; password = "" } }) { Text("Exportar") } },
            dismissButton = { TextButton(onClick = { askPassword = false }) { Text("Cancelar") } },
        )
    }
    Scaffold(
        containerColor = G.Cream,
        topBar = {
            TopAppBar(
                title = { Text("Resultado", style = MaterialTheme.typography.headlineSmall) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Voltar", tint = G.Seed) } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = G.Cream),
            )
        },
    ) { pad ->
        LazyColumn(Modifier.fillMaxSize().padding(pad), contentPadding = PaddingValues(start = 22.dp, end = 22.dp, bottom = 32.dp)) {
            item {
                val bmp: Bitmap? = remember(a.imagePath) { Store.thumbnail(a.imagePath, 1000) }
                if (bmp != null) {
                    Box(Modifier.fillMaxWidth().aspectRatio(bmp.width.toFloat() / bmp.height.toFloat()).clip(MaterialTheme.shapes.medium)) {
                        Image(bmp.asImageBitmap(), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                        val grid = explainId?.let { a.explain[it] }
                        if (grid != null && a.explainW > 0 && a.explainH > 0) HeatOverlay(grid, a.explainW, a.explainH, explainId?.let { a.explainBoxes[it] }, Modifier.matchParentSize())
                    }
                    explainId?.let {
                        Text("Em azul: onde o aplicativo olhou para dizer \"${Signs.name(it)}\". Toque em outro sinal da lista para ver onde ele apareceu.",
                            style = MaterialTheme.typography.labelSmall, color = G.Ink3, modifier = Modifier.padding(top = 6.dp))
                    }
                }
                Spacer(Modifier.height(14.dp))
            }
            if (a.frames.isNotEmpty()) {
                item {
                    SectionLabel("Rotina de luz · ${a.frames.size} quadros", Modifier.padding(top = 0.dp))
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        items(a.frames) { f ->
                            val t: Bitmap? = remember(f.path) { Store.thumbnail(f.path, 260) }
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Box(Modifier.size(96.dp).clip(MaterialTheme.shapes.small).background(G.Sand)) {
                                    if (t != null) Image(t.asImageBitmap(), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                                }
                                Text(f.label, style = MaterialTheme.typography.labelSmall, color = G.Ink3, modifier = Modifier.padding(top = 4.dp))
                            }
                        }
                    }
                    Spacer(Modifier.height(14.dp))
                }
            }
            item {
                Text(
                    (patient?.let { "Paciente " + it.name.ifBlank { it.code } + " · " + it.code } ?: "Sem paciente") + (if (a.child) " · criança" else "") + (if (a.gaze.isNotBlank()) " · olhar ${a.gaze}" else ""),
                    style = MaterialTheme.typography.bodySmall, color = G.Ink2, modifier = Modifier.padding(bottom = 10.dp),
                )
            }
            item {
                // se a ficha elevou a triagem, diz isso na faixa em vez de atribuir o encaminhamento a um sinal da foto
                val photoOnly = com.guarana.ocular.core.Triage.decide(a.signs, a.child)
                val fromRecord = a.triageReasons.isNotEmpty() && photoOnly != a.triage
                TriageBanner(a.triage, a.child, if (fromRecord) "A foto sozinha daria \"${triageShort(photoOnly)}\". A ficha do cidadão eleva a triagem; veja o motivo abaixo." else null)
            }
            if (a.triageReasons.isNotEmpty()) item {
                SoftCard(color = G.AmberSoft) {
                    Text("Pela ficha do cidadão", style = MaterialTheme.typography.titleSmall, color = G.AmberDark)
                    a.triageReasons.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall, color = G.AmberDark) }
                    Text("Regra provisória, a validar com oftalmologista. Não altera o que a foto mostra.", style = MaterialTheme.typography.labelSmall, color = G.AmberDark)
                }
            }
            if (a.indices.isNotEmpty()) {
                item {
                    Spacer(Modifier.height(10.dp))
                    SoftCard {
                        Text("Reflectância multiespectral", style = MaterialTheme.typography.titleSmall)
                        Text("Média na esclera com o quadro sem luz subtraído. Relativo ao anel, sem calibração clínica.", style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                        Spacer(Modifier.height(8.dp))
                        fun num(k: String) = (a.indices[k] as? Number)?.toDouble()
                        listOf(
                            Triple("Icterícia · ln(R vermelho / B azul)", num("ictericia_log_rb"), "sobe com bilirrubina"),
                            Triple("Palidez · ln(R / G) no branco", num("palidez_log_rg"), "cai com menos hemoglobina"),
                            Triple("Hiperemia · R / (R+G+B) no branco", num("hiperemia_r_frac"), "sobe com vermelhidão"),
                        ).forEachIndexed { i, (nome, v, dica) ->
                            if (i > 0) Hairline()
                            Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Text(nome, style = MaterialTheme.typography.bodyMedium)
                                    Text(dica, style = MaterialTheme.typography.bodySmall, color = G.Ink3)
                                }
                                Text(if (v == null) "—" else "%.3f".format(v), style = MaterialTheme.typography.titleMedium)
                            }
                        }
                        val roi = (a.indices["roi_px"] as? Number)?.toInt() ?: 0
                        val frac = (a.indices["roi_frac"] as? Number)?.toDouble() ?: 0.0
                        val notas = a.indices["notas"]?.toString().orEmpty()
                        Text(
                            "Região medida: $roi px (${"%.0f".format(frac * 100)}% da moldura)" + if (notas.isNotBlank()) " · $notas" else "",
                            style = MaterialTheme.typography.bodySmall, color = G.Ink3,
                        )
                    }
                }
            }
            if (!a.quality.ok) {
                item {
                    Spacer(Modifier.height(10.dp))
                    WarningCard("Captura com problemas: " + a.quality.issues.joinToString(", "), "O resultado vale pouco. Repita com o olho bem aberto, mais luz e o aparelho firme.")
                }
            }
            item { SectionLabel("Sinais avaliados") }
            val sorted = a.signs.sortedWith(compareByDescending<Sign> { it.state.ordinal == 0 }.thenByDescending { it.confidence })
            itemsIndexed(sorted) { i, s ->
                if (i > 0) Hairline()
                Column(Modifier.fillMaxWidth().then(if (a.explain.containsKey(s.id)) Modifier.clickable { explainId = s.id } else Modifier)
                    .then(if (explainId == s.id) Modifier.background(G.PinkSoft.copy(alpha = 0.5f)) else Modifier)) {
                    SignRow(s, s.id in unreliable)
                    ConfidenceBar(s.confidence, thresholds[s.id])
                }
            }
            item {
                SectionLabel("Por que o aplicativo disse isso")
                PlainExplanation(a, thresholds, unreliable)
            }
            item {
                SectionLabel("A foto estava boa?")
                PhotoQualityPlain(a)
            }
            item { TechnicalDetails(a, thresholds) }
            item {
                SectionLabel("Notas do caso")
                OutlinedTextField(
                    value = notes, onValueChange = { notes = it; onNotes(it) }, placeholder = { Text("Contexto, queixa, conduta…") },
                    minLines = 2, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium,
                )
                SectionLabel("Exportar")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SecondaryPill("Relatório PDF", Modifier.weight(1f), onClick = onReport)
                    SecondaryPill("FHIR (SUS)", Modifier.weight(1f), onClick = onFhir)
                }
                Spacer(Modifier.height(8.dp))
                SecondaryPill("Exportar protegido por senha", Modifier.fillMaxWidth(), onClick = { askPassword = true })
                SectionLabel("e-SUS")
                Text(
                    if (onRegisterEsus != null) "Registrar abre a visita da pessoa no e-SUS e marca os motivos e o desfecho. Você confere e toca em FINALIZAR lá."
                    else "Cole o resumo na \"condição extra\" do cadastro ou registre a visita com o motivo indicado.",
                    style = MaterialTheme.typography.bodySmall, color = G.Ink2, modifier = Modifier.padding(bottom = 8.dp),
                )
                if (onRegisterEsus != null) { PrimaryPill("Registrar visita no e-SUS", Modifier.fillMaxWidth(), onClick = onRegisterEsus); Spacer(Modifier.height(8.dp)) }
                SecondaryPill("Copiar resumo para o e-SUS", Modifier.fillMaxWidth(), onClick = onCopyEsus)
                if (onBackToEsus != null) TextButton(onClick = onBackToEsus, modifier = Modifier.fillMaxWidth().padding(top = 2.dp)) { Text("Voltar ao e-SUS sem registrar", color = G.Ink2, style = MaterialTheme.typography.labelLarge) }
            }
            item {
                SectionLabel("Origem")
                val engine = when (a.engine) { "local-model" -> "Modelo local"; "local-rules" -> "Regras locais"; else -> "Nuvem" }
                val status = when (a.status) { "confirmed" -> "confirmado"; "divergent" -> "divergente da análise local"; else -> "provisório" }
                Text("$engine · $status · ${a.modelVersion}", style = MaterialTheme.typography.bodyMedium)
                Text(
                    if (a.needsCloudReview) "Análise feita no aparelho, sem internet. Será confirmada na nuvem quando houver conexão." else "Análise confirmada pela nuvem.",
                    style = MaterialTheme.typography.bodySmall, color = G.Ink2, modifier = Modifier.padding(top = 4.dp),
                )
                Text("Demonstração experimental em foto comum. Sinais são pistas de triagem e nunca diagnóstico.", style = MaterialTheme.typography.bodySmall, color = G.Ink3, modifier = Modifier.padding(top = 8.dp))
            }
            item {
                Spacer(Modifier.height(22.dp))
                PrimaryPill("Nova análise", Modifier.fillMaxWidth(), onClick = onNew, icon = { Icon(Icons.Outlined.CameraAlt, null, Modifier.size(20.dp)) })
                TextButton(onClick = onDelete, modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
                    Text("Excluir esta análise", color = G.Ink2, style = MaterialTheme.typography.labelLarge)
                }
            }
        }
    }
}

@Composable
private fun SignRow(s: Sign, unreliable: Boolean) {
    Column(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(Signs.name(s.id), style = MaterialTheme.typography.titleSmall)
                Text(
                    Signs.regionPlain(s.id).replaceFirstChar { it.uppercase() } + (if (unreliable) " · ainda pouco testado em foto de celular" else ""),
                    style = MaterialTheme.typography.bodySmall, color = G.Ink3,
                )
            }
            Spacer(Modifier.width(12.dp))
            StateChip(s.state)
        }
    }
}


private fun framingLabel(f: String) = when (f) {
    "OK" -> "olho enquadrado"; "NOT_FOUND" -> "olho não encontrado"; "TOO_FAR" -> "muito longe"; "TOO_CLOSE" -> "muito perto"
    "TWO_EYES" -> "dois olhos"; "OFF_CENTER" -> "descentralizado"; else -> "não avaliado"
}

/** Barra de probabilidade com o traco do limiar: da para ver de relance o quanto faltou ou sobrou para o sinal. */
@Composable
private fun ConfidenceBar(p: Float, thr: Float?) {
    Row(Modifier.fillMaxWidth().padding(bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Canvas(Modifier.weight(1f).height(6.dp)) {
            val w = size.width; val h = size.height; val r = androidx.compose.ui.geometry.CornerRadius(h / 2)
            drawRoundRect(G.Sand, size = Size(w, h), cornerRadius = r)
            drawRoundRect(if (thr != null && p >= thr) G.Red else G.Pink, size = Size(w * p.coerceIn(0f, 1f), h), cornerRadius = r)
            if (thr != null) drawRect(G.Seed, topLeft = Offset(w * thr.coerceIn(0f, 1f) - 1f, -2f), size = Size(2f, h + 4f))
        }
        Spacer(Modifier.width(10.dp))
        Text("%.0f%%".format(p * 100), style = MaterialTheme.typography.labelSmall, color = G.Ink3)
    }
}

/**
 * Mapa de ativacao sobre a foto: a grade cobre o recorte central que o modelo viu (lado menor × 320/352),
 * cada celula pintada de vermelho com alfa proporcional ao logit local normalizado entre o minimo e o maximo da grade.
 */
@Composable
private fun HeatOverlay(grid: FloatArray, gw: Int, gh: Int, box: FloatArray?, modifier: Modifier) {
    // suaviza (media 3x3) e comprime picos (raiz): mapas de atencao sao muito concentrados
    val g = FloatArray(grid.size) { k -> val i = k % gw; val j = k / gw; var s = 0f; var n = 0
        for (dj in -1..1) for (di in -1..1) { val ii = i + di; val jj = j + dj; if (ii in 0 until gw && jj in 0 until gh) { s += grid[jj * gw + ii]; n++ } }
        kotlin.math.sqrt(maxOf(s / n, 0f)) }
    val mn = g.minOrNull() ?: 0f; val mx = g.maxOrNull() ?: 1f; val span = (mx - mn).takeIf { it > 1e-6f } ?: 1f
    Canvas(modifier) {
        // caixa da vista que deu a probabilidade (fracoes da foto); sem caixa, o recorte central do treino
        val side = if (box != null) box[2] * size.width else minOf(size.width, size.height) * (320f / 352f)
        val x0 = if (box != null) box[0] * size.width else (size.width - side) / 2f
        val y0 = if (box != null) box[1] * size.height else (size.height - side) / 2f
        val cw = side / gw; val ch = side / gh
        for (j in 0 until gh) for (i in 0 until gw) {
            val t = (g[j * gw + i] - mn) / span
            if (t > 0.35f) drawRect(Color(0xFF2E7DD1).copy(alpha = ((t - 0.35f) / 0.65f) * 0.65f), topLeft = Offset(x0 + i * cw, y0 + j * ch), size = Size(cw + 0.5f, ch + 0.5f))
        }
        drawRect(Color.White.copy(alpha = 0.5f), topLeft = Offset(x0, y0), size = Size(side, side), style = androidx.compose.ui.graphics.drawscope.Stroke(2f))
    }
}


// ---------------- explicacao para o agente ----------------

/** Onde na foto ficou o pico do mapa de ativacao, em palavras: "à direita, no meio da foto". */
private fun wherePlain(grid: FloatArray?, gw: Int, gh: Int, box: FloatArray?): String? {
    if (grid == null || gw == 0 || gh == 0) return null
    var best = 0; for (k in grid.indices) if (grid[k] > grid[best]) best = k
    var cx = (best % gw + 0.5f) / gw; var cy = (best / gw + 0.5f) / gh
    if (box != null) { cx = box[0] + cx * box[2]; cy = box[1] + cy * box[3] }
    val h = when { cx < 0.38f -> "à esquerda"; cx > 0.62f -> "à direita"; else -> "no centro" }
    val v = when { cy < 0.38f -> "na parte de cima"; cy > 0.62f -> "na parte de baixo"; else -> "no meio" }
    return "$h, $v da foto"
}

private fun confidencePlain(p: Float, thr: Float?): String = when {
    p >= 0.9f && (thr == null || p >= thr) -> "muito provável"
    thr != null && p >= thr -> "provável"
    else -> "possível, sinal fraco"
}

@Composable
private fun PlainExplanation(a: Analysis, thresholds: Map<String, Float>, unreliable: Set<String>) {
    val present = a.signs.filter { it.state == SignState.present }.sortedByDescending { it.confidence }
    val candidate = a.signs.filter { it.state == SignState.candidate }.sortedByDescending { it.confidence }
    val pDoente = a.quality.metrics["p_doente"]
    if (pDoente != null) {   // v2.3+: decisao conservadora e frase fixa a partir da evidencia
        SoftCard {
            val corte = a.quality.metrics["corte_doente"] ?: 0.5f
            val top = present.firstOrNull()
            if (top == null) {
                Text("Sem sinais que indiquem avaliação nesta foto.", style = MaterialTheme.typography.titleSmall)
                Text("O aplicativo usa um corte conservador: na dúvida, ele prefere pedir avaliação. Aqui a chance de alteração ficou abaixo desse corte.",
                    style = MaterialTheme.typography.bodySmall, color = G.Ink2, modifier = Modifier.padding(top = 4.dp))
            } else {
                val where = a.explainWhere.ifBlank { null } ?: wherePlain(a.explain[top.id], a.explainW, a.explainH, a.explainBoxes[top.id])
                Text("Precisa de avaliação.", style = MaterialTheme.typography.titleSmall)
                Text("Sinais compatíveis com ${Signs.name(top.id).lowercase()} (${Signs.LEIGO[top.id] ?: Signs.regionPlain(top.id)}), ${"%.0f".format(top.confidence * 100)}% de probabilidade." +
                    (where?.let { " O aplicativo concentrou a atenção $it." } ?: "") +
                    (Signs.TIPICO[top.id]?.let { " O sinal típico é $it." } ?: ""),
                    style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 4.dp))
                if (candidate.isNotEmpty()) Text("Outras possibilidades: " + candidate.joinToString(", ") { "${Signs.name(it.id).lowercase()} (${"%.0f".format(it.confidence * 100)}%)" } + ".",
                    style = MaterialTheme.typography.bodySmall, color = G.Ink2, modifier = Modifier.padding(top = 6.dp))
            }
            if (a.triageReasons.isNotEmpty()) Text("A indicação também considera a ficha da pessoa (veja acima).", style = MaterialTheme.typography.bodySmall, color = G.Ink2, modifier = Modifier.padding(top = 4.dp))
            Text("Como funciona: primeiro o aplicativo decide se a foto mostra algo que precisa de avaliação; o nome da condição é a explicação mais provável, não um diagnóstico. A mancha na foto mostra onde ele olhou.",
                style = MaterialTheme.typography.bodySmall, color = G.Ink3, modifier = Modifier.padding(top = 10.dp))
        }
        return
    }
    SoftCard {
        if (present.isEmpty() && candidate.isEmpty()) {
            Text("Nesta foto o aplicativo não encontrou nenhum dos sinais que ele conhece.", style = MaterialTheme.typography.bodyMedium)
        }
        present.forEach { s ->
            val where = wherePlain(a.explain[s.id], a.explainW, a.explainH, a.explainBoxes[s.id])
            Text("• Viu ${Signs.name(s.id).lowercase()} ${Signs.regionPlain(s.id)}" + (where?.let { ", $it" } ?: "") + ". ${confidencePlain(s.confidence, thresholds[s.id]).replaceFirstChar { it.uppercase() }} (${"%.0f".format(s.confidence * 100)}%).",
                style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(bottom = 6.dp))
        }
        candidate.forEach { s ->
            Text("• Talvez ${Signs.name(s.id).lowercase()} ${Signs.regionPlain(s.id)}: sinal fraco (${"%.0f".format(s.confidence * 100)}%). Vale repetir a foto com mais luz.",
                style = MaterialTheme.typography.bodyMedium, color = G.Ink2, modifier = Modifier.padding(bottom = 6.dp))
        }
        if ((present + candidate).any { it.id in unreliable }) Text("Os sinais marcados como \"pouco testados em foto de celular\" foram aprendidos em fotos de consultório; trate como pista, não como certeza.",
            style = MaterialTheme.typography.bodySmall, color = G.AmberDark, modifier = Modifier.padding(top = 4.dp))
        if (a.triageReasons.isNotEmpty()) Text("A indicação de encaminhar também considera a ficha da pessoa (veja acima).", style = MaterialTheme.typography.bodySmall, color = G.Ink2, modifier = Modifier.padding(top = 4.dp))
        Text("Como funciona: o aplicativo compara a foto com milhares de fotos de olhos com e sem cada sinal. Ele não dá diagnóstico; aponta o que merece avaliação. A mancha vermelha na foto mostra onde ele olhou, e a barra de cada sinal mostra a confiança (o tracinho é o mínimo para contar como presente).",
            style = MaterialTheme.typography.bodySmall, color = G.Ink3, modifier = Modifier.padding(top = 10.dp))
    }
}

@Composable
private fun PhotoQualityPlain(a: Analysis) {
    val m = a.quality.metrics
    val lines = mutableListOf<Pair<Boolean, String>>()
    m["nitidez_var"]?.let { lines += (it >= 30f) to (if (it >= 30f) "Foto nítida." else "Foto tremida ou fora de foco: segure firme e espere o foco.") }
    m["luminancia"]?.let { lines += (it in 45f..215f) to when { it < 45f -> "Foto escura: chegue mais perto da luz ou use o flash."; it > 215f -> "Foto muito clara: afaste do sol direto."; else -> "Luz boa." } }
    m["reflexo"]?.let { if (it > 0.04f) lines += false to "Reflexo forte de luz na foto (flash numa tela ou superfície brilhante). Fotografe o olho da pessoa, não uma tela, ou desligue a luz." }
    if ("usou_quadro_sem_luz" in a.quality.issues) lines += true to "O quadro com luz estava estourado; a análise usou o quadro sem luz."
    when (a.framing) {
        "OK" -> lines += true to "Olho bem enquadrado."
        "TOO_CLOSE" -> lines += false to "Muito perto: a íris ficou grande demais, mas deu para analisar."
        "OFF_CENTER" -> lines += false to "Olho fora do centro: na próxima, deixe o olho no meio da moldura."
        "TOO_FAR" -> lines += false to "Muito longe do olho."
        "TWO_EYES" -> lines += false to "Apareceram os dois olhos: fotografe um de cada vez."
        "NOT_FOUND" -> lines += false to "O aplicativo não achou o olho na foto."
        else -> {}
    }
    SoftCard {
        if (lines.isEmpty()) Text("Sem medidas de qualidade para esta foto.", style = MaterialTheme.typography.bodyMedium, color = G.Ink2)
        lines.forEach { (ok, t) -> Text((if (ok) "✓ " else "! ") + t, style = MaterialTheme.typography.bodyMedium, color = if (ok) G.LeafDark else G.AmberDark, modifier = Modifier.padding(bottom = 4.dp)) }
        if (lines.any { !it.first }) Text("Uma foto melhor deixa o resultado mais confiável.", style = MaterialTheme.typography.bodySmall, color = G.Ink3, modifier = Modifier.padding(top = 4.dp))
    }
}

/** Numeros para a equipe tecnica e para o dossie; fechado por padrao. */
@Composable
private fun TechnicalDetails(a: Analysis, thresholds: Map<String, Float>) {
    var open by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().padding(top = 18.dp)) {
        Row(Modifier.clip(MaterialTheme.shapes.small).clickable { open = !open }.padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(if (open) Icons.Outlined.ExpandLess else Icons.Outlined.ExpandMore, if (open) "Recolher" else "Expandir", tint = G.Ink3, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(6.dp))
            Text("Detalhes técnicos", style = MaterialTheme.typography.labelMedium, color = G.Ink3)
        }
        if (open) SoftCard(modifier = Modifier.padding(top = 8.dp)) {
            Text("Modelo ${a.modelVersion} · inferência ${a.inferenceMs} ms" + (if (a.explain.isEmpty()) " · sem mapa de ativação" else " · mapa de ativação ${a.explainW}×${a.explainH} por rótulo, vista vencedora"), style = MaterialTheme.typography.bodySmall)
            a.quality.metrics["nitidez_var"]?.let { Text("Nitidez (variância do laplaciano): %.0f · mínimo 30".format(it), style = MaterialTheme.typography.bodySmall, color = G.Ink2) }
            a.quality.metrics["luminancia"]?.let { Text("Luminância média: %.0f · faixa aceita 45 a 215".format(it), style = MaterialTheme.typography.bodySmall, color = G.Ink2) }
            a.quality.metrics["enq_confianca"]?.let { Text("Enquadramento: ${framingLabel(a.framing)} · confiança do detector %.0f%%".format(it * 100), style = MaterialTheme.typography.bodySmall, color = G.Ink2) }
            Text("Pré-processamento: vistas quadradas no zoom do treino (lado menor × 320/352), centro e laterais, com espelho; probabilidade = máximo entre as vistas; normalização ImageNet. Limiar por sinal escolhido para sensibilidade 0,90 na validação, com as mesmas vistas.",
                style = MaterialTheme.typography.labelSmall, color = G.Ink3, modifier = Modifier.padding(top = 6.dp))
            a.signs.sortedByDescending { it.confidence }.forEach { s ->
                Text("${s.id}: ${s.evidence}" + (thresholds[s.id]?.let { "" } ?: ""), style = MaterialTheme.typography.labelSmall, color = G.Ink3)
            }
        }
    }
}
