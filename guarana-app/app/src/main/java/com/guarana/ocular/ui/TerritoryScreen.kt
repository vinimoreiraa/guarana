package com.guarana.ocular.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.fillMaxHeight
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
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Map
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Place
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.guarana.ocular.core.Household
import com.guarana.ocular.core.OcularPriority
import com.guarana.ocular.core.Patient
import com.guarana.ocular.core.Visit
import java.time.LocalDate

// ---------------- chips reutilizados (agenda, painel, mapa) ----------------

/** "Visitado há N dias", "N condições a acompanhar" e prioridade ocular, como o agente ve no e-SUS Territorio. */
@Composable
fun HouseholdChips(h: Household?, people: List<Patient>, hoje: LocalDate = LocalDate.now()) {
    val dias = h?.diasDesdeVisita(hoje)
    val late = dias != null && dias > 30
    Pill(
        when { dias == null -> "Sem visita registrada"; dias == 0 -> "Visitado hoje"; dias == 1 -> "Visitado ontem"; else -> "Visitado há $dias dias" },
        if (late) G.AmberSoft else G.Sand, if (late) G.AmberDark else G.Ink2,
    )
    val conds = people.sumOf { it.allConditions.size }
    if (conds > 0) Pill("$conds " + (if (conds == 1) "condição" else "condições") + " a acompanhar", G.Sand, G.Ink2)
    PriorityPill(people.maxOfOrNull { OcularPriority.score(it, hoje) } ?: 0)
}

@Composable
fun PriorityPill(score: Int, compact: Boolean = false) {
    when (OcularPriority.level(score)) {
        "alta" -> Pill(if (compact) "Olho: alta" else "Prioridade ocular alta", G.PinkSoft, G.RedDark)
        "média" -> Pill(if (compact) "Olho: média" else "Prioridade ocular média", G.AmberSoft, G.AmberDark)
        else -> {}
    }
}

// ---------------- tela ----------------

/**
 * Navegacao do territorio na hierarquia do e-SUS Territorio: bairro -> logradouro -> imovel -> familia -> cidadao.
 * O agente pensa por rua e numero; a busca por nome fica em Pacientes.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun TerritoryScreen(
    households: Map<String, Household>,
    patients: Map<String, Patient>,
    visits: List<Visit>,
    municipio: String,
    onAnalyze: (Patient) -> Unit,
    onVisit: (Household, Patient) -> Unit,
    onMap: () -> Unit,
    onImport: () -> Unit,
    onBack: () -> Unit,
) {
    var bairro by remember { mutableStateOf<String?>(null) }
    var logradouro by remember { mutableStateOf<String?>(null) }
    var houseId by remember { mutableStateOf<String?>(null) }
    var query by remember { mutableStateOf("") }
    val peopleByHouse = remember(patients) { patients.values.groupBy { it.householdId } }
    val all = remember(households) {
        households.values.sortedWith(compareBy({ it.bairro }, { it.logradouroCompleto }, { it.numero.toIntOrNull() ?: Int.MAX_VALUE }, { it.numero }))
    }
    fun pop() { when { houseId != null -> houseId = null; logradouro != null -> logradouro = null; bairro != null -> bairro = null; else -> onBack() } }
    BackHandler { pop() }

    val house = houseId?.let { households[it] }
    val title = when { house != null -> "Informações do domicílio"; logradouro != null -> "Lista de imóveis"; bairro != null -> "Lista de logradouros"; else -> "Território" }
    Scaffold(
        containerColor = G.Cream,
        topBar = {
            TopAppBar(
                title = { Text(title, style = MaterialTheme.typography.headlineSmall) },
                navigationIcon = { IconButton(onClick = { pop() }) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Voltar", tint = G.Seed) } },
                actions = { IconButton(onClick = onMap) { Icon(Icons.Outlined.Map, "Mapa", tint = G.Seed) } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = G.Cream),
            )
        },
    ) { pad ->
        val m = Modifier.fillMaxSize().padding(pad)
        when {
            house != null -> HouseholdDetail(house, peopleByHouse[house.uuid].orEmpty(), visits.filter { it.householdId == house.uuid }, municipio, onAnalyze, onVisit, m)
            all.isEmpty() -> Column(m.padding(22.dp)) {
                Text("Nenhum território importado. Importe a exportação do e-SUS ou carregue os dados de demonstração em Ajustes.", style = MaterialTheme.typography.bodyMedium, color = G.Ink2)
                Spacer(Modifier.height(12.dp)); SecondaryPill("Importar território", Modifier.fillMaxWidth(), onClick = onImport)
            }
            else -> Column(m) {
                OutlinedTextField(
                    value = query, onValueChange = { query = it }, singleLine = true, shape = MaterialTheme.shapes.medium,
                    placeholder = { Text("Buscar rua, número, bairro ou pessoa") }, modifier = Modifier.fillMaxWidth().padding(horizontal = 22.dp, vertical = 8.dp),
                )
                val q = query.trim().lowercase()
                val hits = if (q.isBlank()) emptyList() else all.filter { h ->
                    h.endereco.lowercase().contains(q) || h.bairro.lowercase().contains(q) || peopleByHouse[h.uuid].orEmpty().any { it.name.lowercase().contains(q) }
                }
                when {
                    q.isNotBlank() -> HouseGrid(hits, peopleByHouse, header = "${hits.size} imóveis encontrados") { houseId = it.uuid }
                    logradouro != null -> HouseGrid(all.filter { it.bairro == bairro && it.logradouroCompleto == logradouro }, peopleByHouse, header = "${logradouro}\n$bairro") { houseId = it.uuid }
                    bairro != null -> StreetList(all.filter { it.bairro == bairro }, bairro!!) { logradouro = it }
                    else -> NeighborhoodList(all, peopleByHouse) { bairro = it }
                }
            }
        }
    }
}

@Composable
private fun NeighborhoodList(all: List<Household>, peopleByHouse: Map<String, List<Patient>>, onPick: (String) -> Unit) {
    val groups = all.groupBy { it.bairro }.toSortedMap()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 22.dp, end = 22.dp, bottom = 32.dp)) {
        item { SectionLabel("${groups.size} bairros · ${all.size} imóveis") }
        itemsIndexed(groups.entries.toList(), key = { _, e -> e.key }) { i, (name, hs) ->
            if (i > 0) Hairline()
            Row(Modifier.fillMaxWidth().clickable { onPick(name) }.padding(vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Place, null, tint = G.LeafDark, modifier = Modifier.size(22.dp)); Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(name.uppercase(), style = MaterialTheme.typography.titleMedium)
                    val nLog = hs.map { it.logradouroCompleto }.toSet().size
                    Text("$nLog logradouros · ${hs.size} imóveis", style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                }
                val alta = hs.count { h -> peopleByHouse[h.uuid].orEmpty().any { OcularPriority.level(it) == "alta" } }
                if (alta > 0) Pill("$alta " + (if (alta == 1) "imóvel prioritário" else "imóveis prioritários"), G.PinkSoft, G.RedDark)
            }
        }
    }
}

@Composable
private fun StreetList(hs: List<Household>, bairro: String, onPick: (String) -> Unit) {
    val groups = hs.groupBy { it.logradouroCompleto }.toSortedMap()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 22.dp, end = 22.dp, bottom = 32.dp)) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
                Icon(Icons.Outlined.Place, null, tint = G.LeafDark, modifier = Modifier.size(20.dp)); Spacer(Modifier.width(8.dp))
                Text(bairro.uppercase(), style = MaterialTheme.typography.titleMedium)
            }
            SectionLabel("${groups.size} logradouros")
        }
        itemsIndexed(groups.entries.toList(), key = { _, e -> e.key }) { i, (name, list) ->
            if (i > 0) Hairline()
            val tipo = list.firstOrNull()?.tipoLogradouro?.ifBlank { null } ?: "Logradouro"
            Column(Modifier.fillMaxWidth().clickable { onPick(name) }.padding(vertical = 14.dp)) {
                Text("${tipo.uppercase()} · ${list.size} " + (if (list.size == 1) "IMÓVEL" else "IMÓVEIS"), style = MaterialTheme.typography.labelSmall, color = G.Ink3)
                Text(list.firstOrNull()?.logradouro?.ifBlank { null } ?: name, style = MaterialTheme.typography.titleMedium)
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun HouseGrid(hs: List<Household>, peopleByHouse: Map<String, List<Patient>>, header: String, onPick: (Household) -> Unit) {
    LazyVerticalGrid(
        columns = GridCells.Adaptive(300.dp), modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 22.dp, end = 22.dp, bottom = 32.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item(span = { androidx.compose.foundation.lazy.grid.GridItemSpan(maxLineSpan) }) {
            Column {
                header.lines().forEachIndexed { i, l -> Text(l, style = if (i == 0) MaterialTheme.typography.titleLarge else MaterialTheme.typography.bodySmall, color = if (i == 0) G.Seed else G.Ink2) }
                Spacer(Modifier.height(4.dp))
            }
        }
        items(hs, key = { it.uuid }) { h -> HouseCard(h, peopleByHouse[h.uuid].orEmpty()) { onPick(h) } }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun HouseCard(h: Household, people: List<Patient>, onClick: () -> Unit) {
    Surface(Modifier.fillMaxWidth().clickable(onClick = onClick), shape = RoundedCornerShape(16.dp), color = Color.White, border = BorderStroke(1.dp, G.Hairline)) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Home, null, tint = G.LeafDark, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(8.dp))
                Text("Nº ${h.numero} · ${h.complemento.ifBlank { "s/ complemento" }.uppercase()}", style = MaterialTheme.typography.labelMedium, color = G.Ink2)
            }
            Hairline(Modifier.padding(vertical = 8.dp))
            val fams = h.familias.map { it.numero }.ifEmpty { people.map { it.familyNumber }.filter { it.isNotBlank() }.distinct() }
            Text(if (fams.size <= 1) "Família ${fams.firstOrNull() ?: "–"}" else "Famílias ${fams.joinToString(", ")}", style = MaterialTheme.typography.titleMedium)
            val resp = people.filter { it.responsible }.ifEmpty { people.take(1) }
            if (resp.isNotEmpty()) Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 4.dp)) {
                Icon(Icons.Outlined.Person, null, tint = G.Ink3, modifier = Modifier.size(16.dp)); Spacer(Modifier.width(6.dp))
                Text(resp.joinToString(", ") { it.name }, style = MaterialTheme.typography.bodyMedium, maxLines = 1)
            }
            FlowRow(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { HouseholdChips(h, people) }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun HouseholdDetail(h: Household, people: List<Patient>, visits: List<Visit>, municipio: String, onAnalyze: (Patient) -> Unit, onVisit: (Household, Patient) -> Unit, modifier: Modifier) {
    // responsavel primeiro, como no e-SUS; depois os demais por idade decrescente
    val families = people.groupBy { it.familyNumber }.toSortedMap().mapValues { (_, m) -> m.sortedWith(compareByDescending<Patient> { it.responsible }.thenByDescending { it.ageYears ?: 0 }) }
    LazyColumn(modifier, contentPadding = PaddingValues(start = 22.dp, end = 22.dp, bottom = 32.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp), color = Color.White, border = BorderStroke(1.dp, G.Hairline)) {
                Column(Modifier.padding(18.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(52.dp).clip(CircleShape).background(G.Sand), contentAlignment = Alignment.Center) { Icon(Icons.Outlined.Home, null, tint = G.LeafDark, modifier = Modifier.size(26.dp)) }
                        Spacer(Modifier.width(14.dp))
                        Column {
                            Text(h.tipoLogradouro.ifBlank { "Logradouro" }.uppercase(), style = MaterialTheme.typography.labelSmall, color = G.Ink3)
                            Text("${h.logradouro.ifBlank { h.logradouroCompleto }}, ${h.numero}", style = MaterialTheme.typography.headlineSmall)
                            Text(listOfNotNull(h.microarea.takeIf { it.isNotBlank() }?.let { "Microárea $it" }, h.bairro.takeIf { it.isNotBlank() }).joinToString(", ") + (if (municipio.isNotBlank()) " - $municipio" else ""), style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                        }
                    }
                    FlowRow(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { HouseholdChips(h, people) }
                    Hairline(Modifier.padding(vertical = 12.dp))
                    DetailLine(Icons.Outlined.Place, h.complemento.ifBlank { "Complemento não informado" })
                    if (h.pontoReferencia.isNotBlank()) DetailLine(Icons.Outlined.Place, h.pontoReferencia)
                    Row(Modifier.padding(top = 6.dp)) {
                        PhoneCol("Residencial", h.telefone); Spacer(Modifier.width(24.dp)); PhoneCol("Contato", h.telefoneContato)
                    }
                    if (h.cep.isNotBlank()) Text("CEP ${h.cep}", style = MaterialTheme.typography.bodySmall, color = G.Ink3, modifier = Modifier.padding(top = 8.dp))
                }
            }
        }
        if (people.isEmpty()) item { Text("Nenhum cidadão cadastrado neste imóvel.", style = MaterialTheme.typography.bodyMedium, color = G.Ink2) }
        families.forEach { (fam, members) ->
            val resp = members.firstOrNull { it.responsible } ?: members.first()
            item(key = "fam-$fam") {
                Row(Modifier.fillMaxWidth().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Família de ${resp.name.split(" ").first()}", style = MaterialTheme.typography.titleLarge)
                        if (fam.isNotBlank()) Text("Nº $fam", style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                    }
                    SecondaryPill("Visitar família", onClick = { onVisit(h, resp) })
                }
            }
            items(members.size, key = { "p-" + members[it].id }) { i -> PersonCard(members[i], h, onAnalyze, onVisit) }
        }
        if (visits.isNotEmpty()) {
            item { SectionLabel("Visitas") }
            items(visits.sortedByDescending { it.date }.take(6).size) { i ->
                val v = visits.sortedByDescending { it.date }[i]
                Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(listOfNotNull(dayLabel(v.date), v.motivo.takeIf { it.isNotBlank() }).joinToString(" · "), style = MaterialTheme.typography.bodyMedium)
                        if (v.desfecho.isNotBlank() || v.profissional.isNotBlank()) Text(listOfNotNull(v.desfecho.takeIf { it.isNotBlank() }, v.profissional.takeIf { it.isNotBlank() }).joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = G.Ink3)
                    }
                    val (bg, fg) = visitStateStyle(v.state); Pill(visitStateLabel(v.state), bg, fg)
                }
            }
        }
    }
}

@Composable
private fun DetailLine(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Row(Modifier.padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = G.Ink3, modifier = Modifier.size(16.dp)); Spacer(Modifier.width(8.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium, color = G.Ink2)
    }
}

@Composable
private fun PhoneCol(label: String, value: String) {
    Column {
        Text(label.uppercase(), style = MaterialTheme.typography.labelSmall, color = G.Ink3)
        Text(value.ifBlank { "Não informado" }, style = MaterialTheme.typography.bodyMedium, color = if (value.isBlank()) G.Ink3 else G.Seed)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PersonCard(p: Patient, h: Household, onAnalyze: (Patient) -> Unit, onVisit: (Household, Patient) -> Unit) {
    val factors = OcularPriority.factors(p)
    val level = OcularPriority.level(factors.sumOf { it.weight })
    Surface(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp), color = Color.White, border = BorderStroke(1.dp, G.Hairline)) {
        Row(Modifier.height(IntrinsicSize.Min)) {
            Box(Modifier.width(5.dp).fillMaxHeight().background(if (p.responsible) G.Leaf else Color.Transparent))
            Column(Modifier.padding(14.dp).weight(1f)) {
                if (p.responsible) Text("RESPONSÁVEL", style = MaterialTheme.typography.labelSmall, color = G.LeafDark)
                Text(p.name, style = MaterialTheme.typography.titleMedium)
                Text(listOfNotNull(p.sexLabel.takeIf { it.isNotBlank() }, p.ageText.takeIf { it.isNotBlank() }).joinToString(" | "), style = MaterialTheme.typography.bodySmall, color = G.Ink2)
                if (p.allConditions.isNotEmpty()) FlowRow(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    p.conditions.forEach { Pill(it, G.Sand, G.Seed) }
                    p.extraConditions.forEach { Pill(it, G.Cream, G.Ink2) }
                }
                if (factors.isNotEmpty()) Text(
                    "Prioridade ocular ${level.ifBlank { "baixa" }}: " + factors.joinToString(", ") { it.label },
                    style = MaterialTheme.typography.bodySmall, color = when (level) { "alta" -> G.RedDark; "média" -> G.AmberDark; else -> G.Ink3 }, modifier = Modifier.padding(top = 8.dp),
                )
                Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PrimaryPill("Analisar olho", Modifier.weight(1f), onClick = { onAnalyze(p) })
                    SecondaryPill("Visitar", Modifier.weight(0.7f), onClick = { onVisit(h, p) })
                }
            }
        }
    }
}
