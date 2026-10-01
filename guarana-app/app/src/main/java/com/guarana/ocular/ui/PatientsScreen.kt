package com.guarana.ocular.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
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
import com.guarana.ocular.core.Analysis
import com.guarana.ocular.core.Patient
import com.guarana.ocular.core.SignState
import com.guarana.ocular.core.Signs
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val fmt = SimpleDateFormat("dd/MM/yy HH:mm", Locale("pt", "BR"))

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PatientsScreen(
    patients: List<Patient>,
    analyses: List<Analysis>,
    currentId: String,
    onSelect: (Patient) -> Unit,
    onCreate: (name: String, cns: String, birthYear: Int?, sex: String) -> Unit,
    onOpenAnalysis: (Analysis) -> Unit,
    onBack: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var creating by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    var cns by remember { mutableStateOf("") }
    var birth by remember { mutableStateOf("") }
    var sex by remember { mutableStateOf("") }
    var open by remember { mutableStateOf<String?>(null) }
    val shown = patients.filter { query.isBlank() || it.name.contains(query, true) || it.code.contains(query, true) || it.cns.contains(query) }

    Scaffold(
        containerColor = G.Cream,
        topBar = {
            TopAppBar(
                title = { Text("Pacientes", style = MaterialTheme.typography.headlineSmall) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Voltar", tint = G.Seed) } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = G.Cream),
            )
        },
    ) { pad ->
        LazyColumn(Modifier.fillMaxSize().padding(pad), contentPadding = PaddingValues(start = 22.dp, end = 22.dp, bottom = 32.dp)) {
            item {
                OutlinedTextField(value = query, onValueChange = { query = it }, placeholder = { Text("Buscar por nome, código ou CNS") }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium)
                Spacer(Modifier.height(10.dp))
                if (!creating) SecondaryPill("Novo paciente", Modifier.fillMaxWidth(), onClick = { creating = true })
                else SoftCard {
                    Text("Novo paciente", style = MaterialTheme.typography.titleSmall)
                    Text("Identificação mínima. CNS e CPF são opcionais e ficam só neste aparelho.", style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Nome ou apelido") }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.small)
                    Spacer(Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(value = birth, onValueChange = { birth = it.filter { c -> c.isDigit() }.take(4) }, label = { Text("Ano nasc.") }, singleLine = true, modifier = Modifier.weight(1f), shape = MaterialTheme.shapes.small)
                        OutlinedTextField(value = cns, onValueChange = { cns = it.filter { c -> c.isDigit() }.take(15) }, label = { Text("CNS") }, singleLine = true, modifier = Modifier.weight(2f), shape = MaterialTheme.shapes.small)
                    }
                    Spacer(Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(selected = sex == "F", onClick = { sex = if (sex == "F") "" else "F" }, label = { Text("Feminino") })
                        FilterChip(selected = sex == "M", onClick = { sex = if (sex == "M") "" else "M" }, label = { Text("Masculino") })
                    }
                    Spacer(Modifier.height(10.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PrimaryPill("Salvar", Modifier.weight(1f), enabled = name.isNotBlank(), onClick = {
                            onCreate(name, cns, birth.toIntOrNull(), sex); creating = false; name = ""; cns = ""; birth = ""; sex = ""
                        })
                        SecondaryPill("Cancelar", Modifier.weight(1f), onClick = { creating = false })
                    }
                }
                SectionLabel("${shown.size} pacientes")
            }
            itemsIndexed(shown, key = { _, p -> p.id }) { i, p ->
                if (i > 0) Hairline()
                val theirs = analyses.filter { it.patientId == p.id }
                Column(Modifier.fillMaxWidth().clickable { open = if (open == p.id) null else p.id }.padding(vertical = 12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(p.name.ifBlank { "Sem nome" }, style = MaterialTheme.typography.titleSmall)
                            Text(
                                listOfNotNull(p.code, p.birthYear?.let { "nasc. $it" }, p.cns.takeIf { it.isNotBlank() }?.let { "CNS $it" }, "${theirs.size} análises").joinToString(" · "),
                                style = MaterialTheme.typography.bodySmall, color = G.Ink3,
                            )
                        }
                        if (p.id == currentId) Pill("Selecionado", G.PinkSoft, G.RedDark)
                        else theirs.firstOrNull()?.let { TriageChip(it.triage) }
                    }
                    if (open == p.id) {
                        Spacer(Modifier.height(10.dp))
                        PrimaryPill(if (p.id == currentId) "Selecionado para a próxima análise" else "Usar na próxima análise", Modifier.fillMaxWidth(), onClick = { onSelect(p) })
                        if (theirs.isNotEmpty()) {
                            SectionLabel("Histórico")
                            theirs.forEach { a ->
                                val present = a.signs.filter { it.state == SignState.present }.map { Signs.name(it.id) }
                                Row(Modifier.fillMaxWidth().clickable { onOpenAnalysis(a) }.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Column(Modifier.weight(1f)) {
                                        Text(if (present.isEmpty()) "Sem sinais acima do limiar" else present.joinToString(", "), style = MaterialTheme.typography.bodyMedium, maxLines = 2)
                                        val ict = (a.indices["ictericia_log_rb"] as? Number)?.toDouble(); val pal = (a.indices["palidez_log_rg"] as? Number)?.toDouble()
                                        Text(fmt.format(Date(a.createdAt)) + (if (ict != null) " · ict %.2f".format(ict) else "") + (if (pal != null) " · pal %.2f".format(pal) else ""), style = MaterialTheme.typography.bodySmall, color = G.Ink3)
                                    }
                                    Spacer(Modifier.width(8.dp)); TriageChip(a.triage)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
