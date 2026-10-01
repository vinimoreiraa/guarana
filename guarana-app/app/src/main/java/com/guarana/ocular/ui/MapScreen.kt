package com.guarana.ocular.ui

import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.guarana.ocular.core.Household
import com.guarana.ocular.core.Patient
import com.guarana.ocular.core.Visit

@Composable
fun MapScreen(
    date: String,
    visits: List<Visit>,
    households: Map<String, Household>,
    patients: Map<String, Patient>,
    onStart: (Visit) -> Unit,
    onBack: () -> Unit,
) {
    val ctx = LocalContext.current
    var selected by remember { mutableStateOf<Visit?>(null) }
    var status by remember { mutableStateOf("") }
    val handle = remember { MapHandle().also { it.onStatus = { s -> status = s } } }
    val day = visits.filter { it.date == date }

    HouseholdMap(Modifier.fillMaxSize().background(G.Cream), date, visits, households, patients, handle, onSelect = { selected = it }) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(shape = CircleShape, color = G.Cream) { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Voltar", tint = G.Seed) } }
            Spacer(Modifier.width(8.dp))
            Text("${day.size} domicílios · ${dayLabel(date)}", style = MaterialTheme.typography.labelLarge, color = G.Seed,
                modifier = Modifier.clip(CircleShape).background(G.Cream).padding(horizontal = 12.dp, vertical = 8.dp))
            Spacer(Modifier.weight(1f))
            Text("Baixar mapa desta área", style = MaterialTheme.typography.labelMedium, color = G.RedDark,
                modifier = Modifier.clip(CircleShape).background(G.Cream).clickable { handle.downloadVisibleArea(ctx, "area-$date") }.padding(horizontal = 12.dp, vertical = 8.dp))
        }
        if (status.isNotBlank()) {
            Text(status, style = MaterialTheme.typography.bodySmall, color = G.Seed,
                modifier = Modifier.align(Alignment.TopCenter).statusBarsPadding().padding(top = 60.dp).clip(CircleShape).background(G.Cream).padding(horizontal = 12.dp, vertical = 6.dp))
        }
        selected?.let { v ->
            val h = households[v.householdId]; val p = patients[v.patientId]
            Surface(Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(16.dp).fillMaxWidth(), shape = MaterialTheme.shapes.large, color = Color.White) {
                Column(Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(p?.name ?: "Pessoa não identificada", style = MaterialTheme.typography.titleSmall)
                            Text((h?.endereco ?: "") + (h?.bairro?.let { " · $it" } ?: ""), style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                            Text(listOfNotNull(v.turno, v.motivo, p?.conditions?.joinToString(", ")?.takeIf { it.isNotBlank() }).joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = G.Ink3)
                        }
                        val (bg, fg) = visitStateStyle(v.state); Pill(visitStateLabel(v.state), bg, fg)
                    }
                    Spacer(Modifier.height(10.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PrimaryPill("Iniciar análise", Modifier.weight(1f), onClick = { onStart(v) })
                        SecondaryPill("Fechar", Modifier.weight(0.6f), onClick = { selected = null })
                    }
                }
            }
        }
    }
}
