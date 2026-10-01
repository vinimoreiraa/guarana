package com.guarana.ocular.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Map
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.guarana.ocular.core.Household
import com.guarana.ocular.core.OcularPriority
import com.guarana.ocular.core.Patient
import com.guarana.ocular.core.Visit
import com.guarana.ocular.core.VisitState
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

fun visitStateStyle(s: VisitState): Pair<androidx.compose.ui.graphics.Color, androidx.compose.ui.graphics.Color> = when (s) {
    VisitState.planejada -> G.Sand to G.Ink2
    VisitState.feita -> G.LeafSoft to G.LeafDark
    VisitState.adiada -> G.AmberSoft to G.AmberDark
    VisitState.recusada, VisitState.ausente -> G.PinkSoft to G.RedDark
}

fun visitStateLabel(s: VisitState) = when (s) {
    VisitState.planejada -> "Planejada"; VisitState.feita -> "Feita"; VisitState.adiada -> "Adiada"; VisitState.recusada -> "Recusada"; VisitState.ausente -> "Ausente"
}

fun dayLabel(date: String): String {
    val d = runCatching { LocalDate.parse(date) }.getOrNull() ?: return date
    val hoje = LocalDate.now()
    return when (d) {
        hoje -> "Hoje"; hoje.plusDays(1) -> "Amanhã"; hoje.minusDays(1) -> "Ontem"
        else -> d.format(DateTimeFormatter.ofPattern("EEE d/MM", Locale("pt", "BR")))
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgendaScreen(
    visits: List<Visit>,
    households: Map<String, Household>,
    patients: Map<String, Patient>,
    selectedDate: String,
    onDate: (String) -> Unit,
    onStart: (Visit) -> Unit,
    onState: (Visit, VisitState) -> Unit,
    onMap: () -> Unit,
    onImport: () -> Unit,
    onBack: () -> Unit,
) {
    val dates = (visits.map { it.date }.toSet() + LocalDate.now().toString()).sorted()
    val day = visits.filter { it.date == selectedDate }
    val pending = OcularPriority.sortVisits(day.filter { it.state == VisitState.planejada }, households, patients)   // prioridade ocular, depois tempo sem visita
    val done = day.filter { it.state != VisitState.planejada }
    var expanded by remember { mutableStateOf<String?>(null) }

    Scaffold(
        containerColor = G.Cream,
        topBar = {
            TopAppBar(
                title = { Text("Agenda", style = MaterialTheme.typography.headlineSmall) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Voltar", tint = G.Seed) } },
                actions = { IconButton(onClick = onMap) { Icon(Icons.Outlined.Map, "Mapa", tint = G.Seed) } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = G.Cream),
            )
        },
    ) { pad ->
        LazyColumn(Modifier.fillMaxSize().padding(pad), contentPadding = PaddingValues(start = 22.dp, end = 22.dp, bottom = 32.dp)) {
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(dates) { d ->
                        val n = visits.count { it.date == d && it.state == VisitState.planejada }
                        FilterChip(selected = d == selectedDate, onClick = { onDate(d) }, label = { Text(dayLabel(d) + if (n > 0) " · $n" else "") })
                    }
                }
                Spacer(Modifier.height(8.dp))
                if (visits.isEmpty()) {
                    Text("Nenhuma visita. Importe a exportação do território ou carregue os dados de demonstração.", style = MaterialTheme.typography.bodyMedium, color = G.Ink2, modifier = Modifier.padding(vertical = 8.dp))
                    SecondaryPill("Importar território", Modifier.fillMaxWidth(), onClick = onImport)
                } else {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PrimaryPill("Mapa do dia", Modifier.weight(1f), onClick = onMap, icon = { Icon(Icons.Outlined.Map, null, Modifier.width(18.dp)) })
                        SecondaryPill("Importar", Modifier.weight(1f), onClick = onImport)
                    }
                }
            }
            if (pending.isNotEmpty()) item { SectionLabel("${pending.size} pendentes · por prioridade ocular e tempo sem visita") }
            itemsIndexed(pending, key = { _, v -> v.uuid }) { i, v ->
                if (i > 0) Hairline()
                VisitRow(v, households[v.householdId], patients[v.patientId], expanded == v.uuid, { expanded = if (expanded == v.uuid) null else v.uuid }, onStart, onState)
            }
            if (done.isNotEmpty()) item { SectionLabel("${done.size} concluídas") }
            itemsIndexed(done, key = { _, v -> v.uuid }) { i, v ->
                if (i > 0) Hairline()
                VisitRow(v, households[v.householdId], patients[v.patientId], expanded == v.uuid, { expanded = if (expanded == v.uuid) null else v.uuid }, onStart, onState)
            }
            if (visits.isNotEmpty() && day.isEmpty()) item { Text("Sem visitas neste dia.", style = MaterialTheme.typography.bodyMedium, color = G.Ink2, modifier = Modifier.padding(vertical = 12.dp)) }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun VisitRow(v: Visit, h: Household?, p: Patient?, open: Boolean, onToggle: () -> Unit, onStart: (Visit) -> Unit, onState: (Visit, VisitState) -> Unit) {
    Column(Modifier.fillMaxWidth().clickable(onClick = onToggle).padding(vertical = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(p?.name?.ifBlank { null } ?: "Pessoa não identificada", style = MaterialTheme.typography.titleSmall)
                Text((h?.endereco ?: "endereço desconhecido") + (h?.bairro?.takeIf { it.isNotBlank() }?.let { " · $it" } ?: ""), style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                Text(
                    listOfNotNull(v.turno.takeIf { it.isNotBlank() }, v.motivo.takeIf { it.isNotBlank() }, p?.conditions?.takeIf { it.isNotEmpty() }?.joinToString(", ")).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall, color = G.Ink3,
                )
                FlowRow(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { HouseholdChips(h, listOfNotNull(p)) }
            }
            Spacer(Modifier.width(8.dp))
            val (bg, fg) = visitStateStyle(v.state); Pill(visitStateLabel(v.state), bg, fg)
        }
        if (open) {
            if (v.observacao.isNotBlank()) Text("Obs.: ${v.observacao}", style = MaterialTheme.typography.bodySmall, color = G.Ink2, modifier = Modifier.padding(top = 6.dp))
            if (v.desfecho.isNotBlank()) Text("Desfecho: ${v.desfecho}", style = MaterialTheme.typography.bodySmall, color = G.Ink2)
            if (v.profissional.isNotBlank()) Text("Profissional: ${v.profissional}", style = MaterialTheme.typography.bodySmall, color = G.Ink3)
            p?.let { OcularPriority.factors(it) }?.takeIf { it.isNotEmpty() }?.let { f -> Text("Prioridade ocular: " + f.joinToString(", ") { it.label }, style = MaterialTheme.typography.bodySmall, color = G.RedDark, modifier = Modifier.padding(top = 4.dp)) }
            Spacer(Modifier.height(10.dp))
            PrimaryPill("Iniciar análise" + (p?.let { " · ${it.name.split(" ").first()}" } ?: ""), Modifier.fillMaxWidth(), onClick = { onStart(v) })
            Row(Modifier.fillMaxWidth().padding(top = 2.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                listOf(VisitState.feita to "Feita", VisitState.adiada to "Adiar", VisitState.ausente to "Ausente", VisitState.recusada to "Recusada").forEach { (st, label) ->
                    TextButton(onClick = { onState(v, st) }) { Text(label, color = if (v.state == st) G.RedDark else G.Ink2, style = MaterialTheme.typography.labelLarge) }
                }
            }
        }
    }
}
