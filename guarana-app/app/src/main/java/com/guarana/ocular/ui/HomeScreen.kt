package com.guarana.ocular.ui

import android.graphics.Bitmap
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.Map
import androidx.compose.material.icons.outlined.OpenInFull
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import com.guarana.ocular.core.Analysis
import com.guarana.ocular.core.Household
import com.guarana.ocular.core.OcularPriority
import com.guarana.ocular.core.Patient
import com.guarana.ocular.core.SignState
import com.guarana.ocular.core.Signs
import com.guarana.ocular.core.Store
import com.guarana.ocular.core.Visit
import com.guarana.ocular.core.VisitState
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Painel inicial inspirado em dashboards de viagem: barra com pílulas, contexto, mapa com trajeto e cartões brancos. */
@Composable
fun HomeScreen(
    items: List<Analysis>,
    patient: Patient?,
    visits: List<Visit>,
    households: Map<String, Household>,
    patients: Map<String, Patient>,
    unidade: String,
    date: String,
    onNew: () -> Unit,
    onGallery: () -> Unit,
    onOpen: (Analysis) -> Unit,
    onSettings: () -> Unit,
    onPatients: () -> Unit,
    onAgenda: () -> Unit,
    onMap: () -> Unit,
    onTerritory: () -> Unit,
    onStartVisit: (Visit) -> Unit,
) {
    val day = visits.filter { it.date == date }
    val pending = OcularPriority.sortVisits(day.filter { it.state == VisitState.planejada }, households, patients)   // prioridade ocular, depois tempo sem visita
    val hoje = LocalDate.now()
    val encaminhar = items.count { a -> a.triage.startsWith("encaminhar") && Instant.ofEpochMilli(a.createdAt).atZone(ZoneId.systemDefault()).toLocalDate() == hoje }

    Scaffold(containerColor = G.Cream) { pad ->
        BoxWithConstraints(Modifier.fillMaxSize().padding(pad)) {
            val wide = maxWidth >= 840.dp
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(horizontal = if (wide) 28.dp else 18.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                item { TopBar(onSettings, onAgenda, onPatients, onTerritory, patient, wide) }
                item { ContextRow(patient, onPatients) }
                if (wide) {
                    item {
                        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                            MapCard(Modifier.weight(1.15f).height(640.dp), date, visits, households, patients, onMap, onStartVisit)
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                                AgendaCard(pending, households, patients, onAgenda, onStartVisit, max = 5)
                                Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                                    StatsCard(Modifier.weight(1f), day.size, pending.size, encaminhar)
                                    WeekCard(Modifier.weight(1f), items)
                                }
                                RecentCard(items, onOpen, onNew, onGallery, max = 4)
                            }
                        }
                    }
                } else {
                    item { PrimaryPill("Nova análise", Modifier.fillMaxWidth(), onClick = onNew, icon = { Icon(Icons.Outlined.CameraAlt, null, Modifier.size(20.dp)) }) }
                    item { StatsCard(Modifier.fillMaxWidth(), day.size, pending.size, encaminhar) }
                    item { AgendaCard(pending, households, patients, onAgenda, onStartVisit, max = 4) }
                    if (day.isNotEmpty()) item { MapCard(Modifier.fillMaxWidth().height(320.dp), date, visits, households, patients, onMap, onStartVisit) }
                    item { WeekCard(Modifier.fillMaxWidth(), items) }
                    item { RecentCard(items, onOpen, onNew, onGallery, max = 4) }
                }
                item { Text("Análise experimental em foto comum. Não substitui exame nem diagnóstico.", style = MaterialTheme.typography.bodySmall, color = G.Ink3, modifier = Modifier.padding(top = 8.dp)) }
            }
        }
    }
}

// ---------------- barra superior ----------------
@Composable
private fun TopBar(onSettings: () -> Unit, onAgenda: () -> Unit, onPatients: () -> Unit, onTerritory: () -> Unit, patient: Patient?, wide: Boolean) {
    val pills = @Composable {
        NavPill("Início", true) {}
        NavPill("Agenda", false, onAgenda)
        NavPill("Território", false, onTerritory)
        NavPill("Pacientes", false, onPatients)
    }
    Column {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            GuaranaLogo(30.dp); Spacer(Modifier.width(8.dp))
            Text("Guaraná", style = MaterialTheme.typography.headlineSmall)
            Spacer(Modifier.weight(1f))
            if (wide) { Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) { pills() }; Spacer(Modifier.weight(1f)) }
            RoundIcon(Icons.Outlined.Settings, "Ajustes", onSettings)
            Spacer(Modifier.width(8.dp))
            Box(Modifier.size(40.dp).clip(CircleShape).background(G.PinkSoft), contentAlignment = Alignment.Center) {
                Text((patient?.name?.firstOrNull()?.uppercaseChar() ?: 'G').toString(), style = MaterialTheme.typography.titleSmall, color = G.RedDark)
            }
        }
        // em telefone as pilulas descem para uma segunda linha rolavel, como nos apps de viagem em tela estreita
        if (!wide) Row(Modifier.fillMaxWidth().padding(top = 10.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) { pills() }
    }
}

@Composable
private fun NavPill(text: String, active: Boolean, onClick: () -> Unit) {
    Text(
        text, style = MaterialTheme.typography.labelLarge, color = if (active) G.Cream else G.Seed,
        modifier = Modifier.clip(RoundedCornerShape(10.dp)).background(if (active) G.Seed else G.Sand).clickable(onClick = onClick).padding(horizontal = 14.dp, vertical = 9.dp),
    )
}

@Composable
private fun RoundIcon(icon: androidx.compose.ui.graphics.vector.ImageVector, desc: String, onClick: () -> Unit) {
    Surface(shape = CircleShape, color = Color.White, border = BorderStroke(1.dp, G.Line), modifier = Modifier.size(40.dp)) {
        IconButton(onClick = onClick) { Icon(icon, desc, tint = G.Seed, modifier = Modifier.size(20.dp)) }
    }
}

// ---------------- linha de contexto ----------------
/** So a busca de paciente: unidade e pendentes ja aparecem no Resumo e na agenda. */
@Composable
private fun ContextRow(patient: Patient?, onPatients: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(G.Sand).clickable(onClick = onPatients).padding(horizontal = 14.dp, vertical = 13.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Outlined.Search, null, tint = G.Ink3, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(8.dp))
        Text(patient?.let { "Paciente: " + it.name.ifBlank { it.code } } ?: "Buscar ou escolher paciente", style = MaterialTheme.typography.bodyMedium, color = if (patient == null) G.Ink3 else G.Seed)
    }
}

// ---------------- cartoes ----------------
@Composable
private fun Card(title: String, modifier: Modifier = Modifier, onExpand: (() -> Unit)? = null, content: @Composable () -> Unit) {
    Surface(modifier, shape = RoundedCornerShape(20.dp), color = Color.White, border = BorderStroke(1.dp, G.Hairline)) {
        Column(Modifier.padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                if (onExpand != null) RoundIcon(Icons.Outlined.OpenInFull, "Abrir", onExpand)
            }
            Spacer(Modifier.height(12.dp))
            content()
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MapCard(modifier: Modifier, date: String, visits: List<Visit>, households: Map<String, Household>, patients: Map<String, Patient>, onMap: () -> Unit, onStart: (Visit) -> Unit) {
    val handle = remember { MapHandle() }
    var selected by remember { mutableStateOf<Visit?>(null) }
    Surface(modifier, shape = RoundedCornerShape(20.dp), color = G.Sand, border = BorderStroke(1.dp, G.Hairline)) {
        if (visits.none { it.date == date }) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Sem visitas no mapa. Importe o território em Ajustes.", style = MaterialTheme.typography.bodyMedium, color = G.Ink2) }
        } else HouseholdMap(Modifier.fillMaxSize().clip(RoundedCornerShape(20.dp)), date, visits, households, patients, handle, onSelect = { selected = it }) {
            // barra flutuante como no painel de referencia
            Row(Modifier.align(Alignment.BottomCenter).padding(14.dp).clip(RoundedCornerShape(16.dp)).background(Color.White).padding(6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                FloatChip("Hoje · ${visits.count { it.date == date }}", true) {}
                FloatChip("Trajeto", false) {}
                FloatChip("Abrir mapa", false, onMap)
            }
            selected?.let { v ->
                val p = patients[v.patientId]; val h = households[v.householdId]
                Surface(Modifier.align(Alignment.TopStart).padding(14.dp).width(260.dp), shape = RoundedCornerShape(14.dp), color = Color.White.copy(alpha = 0.94f)) {
                    Column(Modifier.padding(12.dp)) {
                        Text(p?.name ?: "Pessoa", style = MaterialTheme.typography.titleSmall)
                        Text((h?.endereco ?: "") + (h?.bairro?.let { " · $it" } ?: ""), style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                        Text(listOfNotNull(v.turno, v.motivo).joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = G.Ink3)
                        FlowRow(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { HouseholdChips(h, listOfNotNull(p)) }
                        Spacer(Modifier.height(8.dp))
                        PrimaryPill("Iniciar análise", Modifier.fillMaxWidth(), onClick = { onStart(v) })
                    }
                }
            }
        }
    }
}

@Composable
private fun FloatChip(text: String, active: Boolean, onClick: () -> Unit) {
    Text(text, style = MaterialTheme.typography.labelMedium, color = if (active) G.Seed else G.Ink2,
        modifier = Modifier.clip(RoundedCornerShape(10.dp)).background(if (active) G.PinkSoft else Color.Transparent).clickable(onClick = onClick).padding(horizontal = 12.dp, vertical = 9.dp))
}

private val diaSemana = DateTimeFormatter.ofPattern("EEE", Locale("pt", "BR"))

@Composable
private fun AgendaCard(pending: List<Visit>, households: Map<String, Household>, patients: Map<String, Patient>, onAgenda: () -> Unit, onStart: (Visit) -> Unit, max: Int) {
    Card("Visitas de hoje", onExpand = onAgenda) {
        if (pending.isEmpty()) Text("Nenhuma visita pendente hoje.", style = MaterialTheme.typography.bodyMedium, color = G.Ink2)
        pending.take(max).forEachIndexed { i, v ->
            if (i > 0) Spacer(Modifier.height(6.dp))
            val p = patients[v.patientId]; val h = households[v.householdId]
            val d = runCatching { LocalDate.parse(v.date) }.getOrNull()
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(G.Cream).clickable { onStart(v) }.padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.width(38.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(d?.format(diaSemana)?.replace(".", "") ?: "", style = MaterialTheme.typography.labelSmall, color = G.Ink3)
                    Text(d?.dayOfMonth?.toString() ?: "", style = MaterialTheme.typography.headlineSmall, color = if (v.turno == "manhã") G.Seed else G.RedDark)
                }
                Spacer(Modifier.width(10.dp))
                Box(Modifier.size(36.dp).clip(CircleShape).background(G.Sand), contentAlignment = Alignment.Center) {
                    Text(initials(p?.name), style = MaterialTheme.typography.labelMedium, color = G.Ink2)
                }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(p?.name ?: "Pessoa não identificada", style = MaterialTheme.typography.titleSmall, maxLines = 1)
                    Text(listOfNotNull(h?.endereco, v.motivo.takeIf { it.isNotBlank() }, h?.diasDesdeVisita()?.let { "há $it dias" }).joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = G.Ink3, maxLines = 1)
                }
                Spacer(Modifier.width(8.dp))
                p?.let { PriorityPill(OcularPriority.score(it), compact = true); Spacer(Modifier.width(6.dp)) }
                val (bg, fg) = visitStateStyle(v.state); Pill(if (v.turno.isNotBlank()) v.turno.replaceFirstChar { it.uppercase() } else visitStateLabel(v.state), bg, fg)
                Spacer(Modifier.width(6.dp))
                Icon(Icons.Outlined.CameraAlt, "Iniciar", tint = G.Ink3, modifier = Modifier.size(18.dp))
            }
        }
        if (pending.size > max) Text("+ ${pending.size - max} na agenda", style = MaterialTheme.typography.labelMedium, color = G.RedDark, modifier = Modifier.padding(top = 10.dp).clickable(onClick = onAgenda))
    }
}

private fun initials(name: String?): String = name?.split(" ")?.filter { it.isNotBlank() }?.take(2)?.joinToString("") { it.first().uppercaseChar().toString() } ?: "?"

@Composable
private fun StatsCard(modifier: Modifier, total: Int, pending: Int, encaminhar: Int) {
    Card("Resumo", modifier) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Stat("Hoje", total.toString(), modifier = Modifier.weight(1f))
            Stat("Pendentes", pending.toString(), modifier = Modifier.weight(1f))
            Stat("Encaminhar", encaminhar.toString(), if (encaminhar > 0) G.RedDark else G.Seed, Modifier.weight(1f))
        }
    }
}

@Composable
private fun Stat(label: String, value: String, color: Color = G.Seed, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = G.Ink3, maxLines = 1)
        Text(value, style = MaterialTheme.typography.headlineMedium, color = color)
    }
}

@Composable
private fun WeekCard(modifier: Modifier, items: List<Analysis>) {
    val zone = ZoneId.systemDefault(); val hoje = LocalDate.now()
    val days = (13 downTo 0).map { hoje.minusDays(it.toLong()) }
    val counts = days.map { d -> items.count { Instant.ofEpochMilli(it.createdAt).atZone(zone).toLocalDate() == d } }
    Card("Análises · 14 dias", modifier) {
        Text("${counts.sum()}", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Canvas(Modifier.fillMaxWidth().height(56.dp)) {
            val n = counts.size; val gap = 4.dp.toPx(); val bw = (size.width - gap * (n - 1)) / n
            val mx = (counts.maxOrNull() ?: 0).coerceAtLeast(1)
            counts.forEachIndexed { i, c ->
                val h = if (c == 0) 3.dp.toPx() else (size.height * c / mx).coerceAtLeast(6.dp.toPx())
                drawRoundRect(if (i == n - 1) G.Red else G.Sand, topLeft = Offset(i * (bw + gap), size.height - h), size = Size(bw, h), cornerRadius = CornerRadius(3.dp.toPx()))
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(days.first().format(DateTimeFormatter.ofPattern("d/MM")), style = MaterialTheme.typography.labelSmall, color = G.Ink3)
            Text("hoje", style = MaterialTheme.typography.labelSmall, color = G.RedDark)
        }
    }
}

private val hora = java.text.SimpleDateFormat("dd/MM · HH:mm", Locale("pt", "BR"))

@Composable
private fun RecentCard(items: List<Analysis>, onOpen: (Analysis) -> Unit, onNew: () -> Unit, onGallery: () -> Unit, max: Int) {
    Card("Análises recentes") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(bottom = 12.dp)) {
            PrimaryPill("Nova análise", Modifier.weight(1f), onClick = onNew, icon = { Icon(Icons.Outlined.CameraAlt, null, Modifier.size(18.dp)) })
            SecondaryPill("Galeria", Modifier.weight(0.7f), onClick = onGallery, icon = { Icon(Icons.Outlined.Image, null, Modifier.size(18.dp)) })
        }
        if (items.isEmpty()) Text("Nenhuma análise ainda.", style = MaterialTheme.typography.bodyMedium, color = G.Ink2)
        items.take(max).forEachIndexed { i, a ->
            if (i > 0) Hairline()
            val thumb: Bitmap? = remember(a.imagePath) { Store.thumbnail(a.imagePath, 160) }
            val present = a.signs.filter { it.state == SignState.present }.map { Signs.name(it.id) }
            Row(Modifier.fillMaxWidth().clickable { onOpen(a) }.padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(40.dp).clip(RoundedCornerShape(10.dp)).background(G.Sand)) { if (thumb != null) Image(thumb.asImageBitmap(), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(if (present.isEmpty()) "Sem sinais acima do limiar" else present.joinToString(", "), style = MaterialTheme.typography.titleSmall, maxLines = 1)
                    Text(hora.format(java.util.Date(a.createdAt)) + (if (a.frames.isNotEmpty()) " · ${a.frames.size} quadros" else ""), style = MaterialTheme.typography.bodySmall, color = G.Ink3)
                }
                Spacer(Modifier.width(8.dp)); TriageChip(a.triage)
            }
        }
    }
}
