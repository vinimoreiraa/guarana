package com.guarana.esusmock

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material.icons.outlined.AccountBox
import androidx.compose.material.icons.outlined.HelpOutline
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// ---------------- login ----------------
@Composable
fun LoginScreen(onLogin: () -> Unit) {
    var cpf by remember { mutableStateOf(Repo.cpfFormatado(Repo.agente.cpf)) }
    var senha by remember { mutableStateOf("") }
    var show by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().background(E.Bg), horizontalAlignment = Alignment.CenterHorizontally) {
        Column(Modifier.fillMaxWidth().background(Color(0xFFF7F7F7)).padding(top = 72.dp, bottom = 28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            EsusLogo()
            Spacer(Modifier.height(10.dp))
            Text("e-SUS", fontSize = 44.sp, fontWeight = FontWeight.Bold, color = Color(0xFF37474F), letterSpacing = 2.sp)
            Text("TERRITÓRIO", fontSize = 22.sp, color = Color(0xFF37474F), letterSpacing = 6.sp)
        }
        Column(Modifier.fillMaxWidth().padding(horizontal = 40.dp).padding(top = 28.dp)) {
            OutlinedTextField(value = cpf, onValueChange = { cpf = it }, label = { Text("CPF") }, singleLine = true, modifier = Modifier.fillMaxWidth(), textStyle = androidx.compose.ui.text.TextStyle(fontSize = 24.sp),
                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = E.Green, focusedLabelColor = E.GreenDark))
            Spacer(Modifier.height(14.dp))
            OutlinedTextField(value = senha, onValueChange = { senha = it }, label = { Text("Senha") }, singleLine = true, modifier = Modifier.fillMaxWidth(), textStyle = androidx.compose.ui.text.TextStyle(fontSize = 24.sp),
                visualTransformation = if (show) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = { IconButton(onClick = { show = !show }) { Icon(if (show) Icons.Filled.VisibilityOff else Icons.Filled.Visibility, null, tint = E.Ink2) } },
                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = E.Green, focusedLabelColor = E.GreenDark))
            Spacer(Modifier.height(24.dp))
            EsusButton("Iniciar sessão", Modifier.fillMaxWidth(), enabled = senha.isNotBlank(), onClick = onLogin)
            Spacer(Modifier.height(10.dp))
            Text("Qualquer senha entra. Este é um simulador para testes de integração do Guaraná, não o aplicativo oficial.", color = E.Ink3, fontSize = 12.sp)
        }
    }
}

/** Logo do simulador: dois blobs verdes e uma casinha, no espirito do original sem ser copia. */
@Composable
private fun EsusLogo(size: androidx.compose.ui.unit.Dp = 150.dp) {
    Canvas(Modifier.size(size)) {
        val w = this.size.width; val h = this.size.height
        fun blob(cx: Float, cy: Float, r: Float, c: Color) {
            val p = Path().apply {
                moveTo(cx - r, cy)
                cubicTo(cx - r, cy - r * 1.1f, cx + r * 0.2f, cy - r * 1.2f, cx + r * 0.9f, cy - r * 0.5f)
                cubicTo(cx + r * 1.3f, cy + r * 0.1f, cx + r * 0.6f, cy + r * 1.2f, cx - r * 0.2f, cy + r * 0.9f)
                cubicTo(cx - r * 0.9f, cy + r * 0.7f, cx - r, cy + r * 0.3f, cx - r, cy); close()
            }
            drawPath(p, c)
        }
        blob(w * 0.42f, h * 0.5f, w * 0.34f, Color(0xFF8BC34A).copy(alpha = 0.55f))
        blob(w * 0.56f, h * 0.5f, w * 0.36f, Color(0xFF1B7A2F))
        val house = Path().apply {
            moveTo(w * 0.60f, h * 0.30f); lineTo(w * 0.40f, h * 0.48f); lineTo(w * 0.45f, h * 0.48f); lineTo(w * 0.45f, h * 0.66f)
            lineTo(w * 0.55f, h * 0.66f); lineTo(w * 0.55f, h * 0.56f); lineTo(w * 0.65f, h * 0.56f); lineTo(w * 0.65f, h * 0.66f)
            lineTo(w * 0.75f, h * 0.66f); lineTo(w * 0.75f, h * 0.48f); lineTo(w * 0.80f, h * 0.48f); close()
        }
        drawPath(house, Color.White)
        drawCircle(Color.White, radius = w * 0.012f, center = Offset(w * 0.42f, h * 0.5f))
    }
}

// ---------------- lista de logradouros ----------------
@Composable
fun StreetsScreen(onStreet: (bairro: String, chaveRua: String) -> Unit) {
    val bairros = remember { Repo.imoveis.groupBy { it.bairro }.toSortedMap() }
    var open by remember { mutableStateOf(bairros.keys.toSet()) }
    LazyColumn(Modifier.fillMaxSize().background(E.Bg), contentPadding = PaddingValues(bottom = 24.dp)) {
        item { BodyTitle("Lista de logradouros") }
        bairros.forEach { (bairro, imoveis) ->
            val ruas = imoveis.groupBy { it.chaveRua }.toSortedMap()
            item(key = "b-$bairro") {
                EsusCard(Modifier.padding(horizontal = 8.dp, vertical = 4.dp), onClick = { open = if (bairro in open) open - bairro else open + bairro }) {
                    Row(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.LocationOn, null, tint = E.GreenDark, modifier = Modifier.size(22.dp)); Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text(bairro.uppercase(), fontSize = 17.sp, fontWeight = FontWeight.Medium, color = E.Ink)
                            Text("${ruas.size} " + if (ruas.size == 1) "logradouro" else "logradouros", fontSize = 14.sp, color = E.Ink2)
                        }
                        Icon(if (bairro in open) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore, null, tint = E.Ink2)
                    }
                }
            }
            if (bairro in open) ruas.forEach { (chave, list) ->
                item(key = "r-$chave") {
                    val first = list.first()
                    EsusCard(Modifier.padding(horizontal = 8.dp, vertical = 3.dp), onClick = { onStreet(bairro, chave) }) {
                        Column(Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
                            Kicker("${first.tipoLogradouro} · ${list.size} " + if (list.size == 1) "imóvel" else "imóveis")
                            Text(first.logradouro, fontSize = 18.sp, color = E.Ink)
                        }
                    }
                }
            }
            item { Spacer(Modifier.height(10.dp)) }
        }
    }
}

// ---------------- lista de imoveis ----------------
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun PropertiesScreen(bairro: String, chaveRua: String, onHouse: (String) -> Unit) {
    val imoveis = remember(chaveRua) { Repo.imoveis.filter { it.chaveRua == chaveRua } }
    val first = imoveis.firstOrNull()
    LazyVerticalGrid(GridCells.Fixed(2), Modifier.fillMaxSize().background(E.Bg), contentPadding = PaddingValues(6.dp, 0.dp, 6.dp, 24.dp)) {
        item(span = { GridItemSpan(2) }) {
            Column(Modifier.padding(horizontal = 10.dp, vertical = 12.dp)) {
                Kicker(first?.tipoLogradouro ?: "")
                Text(first?.logradouro ?: "", fontSize = 22.sp, fontWeight = FontWeight.Medium, color = E.Ink)
                Text(bairro, fontSize = 14.sp, color = E.Ink2)
            }
        }
        items(imoveis, key = { it.uuid }) { i ->
            val people = Repo.cidadaosDo(i.uuid)
            EsusCard(Modifier.padding(4.dp), onClick = { onHouse(i.uuid) }) {
                Row(Modifier.padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Home, null, tint = E.GreenDark, modifier = Modifier.size(20.dp)); Spacer(Modifier.width(8.dp))
                    Text("N° ${i.numero} · ${i.complemento.ifBlank { "S/ complemento" }.uppercase()}", fontSize = 13.sp, color = E.Ink, letterSpacing = 0.5.sp, maxLines = 1)
                }
                Divider()
                Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
                    val fams = i.familias.map { it.numero }
                    Text(if (fams.size <= 1) "Família ${fams.firstOrNull() ?: "–"}" else "Famílias ${fams.joinToString(", ")}", fontSize = 19.sp, fontWeight = FontWeight.Medium, color = E.Ink)
                    val resp = people.filter { it.responsavel }.ifEmpty { people.take(1) }
                    Row(Modifier.padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.AccountBox, null, tint = E.Ink2, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp))
                        Text(if (resp.size == 1) resp.first().nome else resp.joinToString(", ") { it.primeiroNome }, fontSize = 15.sp, color = E.Ink, maxLines = 1)
                    }
                    FlowRow(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        EsusChip(Repo.visitadoHa(i))
                        val n = Repo.condicoesAAcompanhar(i.uuid)
                        if (n > 0) EsusChip("$n " + (if (n == 1) "condição" else "condições") + " a acompanhar")
                    }
                }
            }
        }
    }
}

// ---------------- informacoes do domicilio ----------------
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun HouseholdScreen(uuid: String, onVisit: (cns: String) -> Unit, onEditCitizen: (cns: String) -> Unit, onAddCitizen: (familia: String) -> Unit, onToast: (String) -> Unit) {
    val i = Repo.imovel(uuid) ?: return
    val people = Repo.cidadaosDo(uuid)
    var moradia by remember { mutableStateOf(false) }
    val families = people.groupBy { it.familiaNumero }.toSortedMap()
    LazyColumn(Modifier.fillMaxSize().background(E.Bg), contentPadding = PaddingValues(8.dp, 8.dp, 8.dp, 32.dp)) {
        item {
            EsusCard {
                Row(Modifier.padding(14.dp), verticalAlignment = Alignment.Top) {
                    Box(Modifier.size(64.dp).clip(CircleShape).background(Color(0xFFEEEEEE)), contentAlignment = Alignment.Center) { Icon(Icons.Filled.Home, null, tint = E.GreenDark, modifier = Modifier.size(30.dp)) }
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Kicker(i.tipoLogradouro)
                        Text("${i.logradouro}, ${i.numero}", fontSize = 22.sp, fontWeight = FontWeight.Medium, color = E.Ink)
                        Text("Microárea ${i.microarea}, ${i.bairro} - ${Repo.municipio}/${Repo.uf}", fontSize = 14.sp, color = E.Ink2)
                    }
                    IconButton(onClick = { onToast("Menu do domicílio não disponível no simulador") }) { Icon(Icons.Filled.MoreVert, null, tint = E.Ink2) }
                }
                FlowRow(Modifier.padding(horizontal = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    EsusChip(Repo.visitadoHa(i))
                    val n = Repo.condicoesAAcompanhar(i.uuid); if (n > 0) EsusChip("$n " + (if (n == 1) "condição" else "condições") + " a acompanhar")
                }
                Column(Modifier.padding(14.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Filled.Place, null, tint = E.GreenDark, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Body(i.complemento.ifBlank { "Complemento não informado" }, if (i.complemento.isBlank()) E.Ink2 else E.Ink) }
                    Row(Modifier.padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Filled.LocationOn, null, tint = E.Ink2, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Body(i.pontoReferencia.ifBlank { "Ponto de referência não informado" }, if (i.pontoReferencia.isBlank()) E.Ink2 else E.Ink) }
                    Row(Modifier.padding(top = 8.dp), verticalAlignment = Alignment.Top) {
                        Icon(Icons.Filled.Phone, null, tint = E.Ink2, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(8.dp))
                        Column { Kicker("Residencial"); Body(i.telefone.ifBlank { "Não informado" }) }
                        Spacer(Modifier.width(24.dp))
                        Column { Kicker("Contato"); Body(i.telefoneContato.ifBlank { "Não informado" }, if (i.telefoneContato.isBlank()) E.Ink2 else E.Ink) }
                    }
                    Row(Modifier.fillMaxWidth().clickable { moradia = !moradia }.padding(top = 14.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                        Icon(if (moradia) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore, null, tint = E.Ink2, modifier = Modifier.size(20.dp))
                        Text("VER CONDIÇÕES DE MORADIA", fontSize = 14.sp, letterSpacing = 1.5.sp, color = E.Ink, fontWeight = FontWeight.Medium)
                    }
                    if (moradia) Column(Modifier.padding(top = 8.dp)) {
                        Body("Situação de moradia: ${i.situacaoMoradia}", size = 14); Body("Abastecimento de água: ${i.agua}", size = 14); Body("Esgotamento sanitário: ${i.esgoto}", size = 14); Body("CEP ${i.cep}", E.Ink2, 14)
                    }
                }
            }
        }
        families.forEach { (fam, members) ->
            val resp = members.firstOrNull { it.responsavel } ?: members.first()
            val ordered = members.sortedByDescending { it.responsavel }
            item(key = "f-$fam") {
                Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Família de ${resp.primeiroNome}", fontSize = 22.sp, fontWeight = FontWeight.Medium, color = E.Ink)
                        Text("Nº $fam", fontSize = 15.sp, color = E.Ink2)
                    }
                    EsusOutlinedButton("Visitar família", onClick = { onVisit(resp.cns) })
                    IconButton(onClick = { onToast("Menu da família não disponível no simulador") }) { Icon(Icons.Filled.MoreVert, null, tint = E.Ink2) }
                }
            }
            items(ordered, key = { "c-" + it.cns }) { c ->
                EsusCard(Modifier.padding(vertical = 4.dp)) {
                    Row(Modifier.height(androidx.compose.foundation.layout.IntrinsicSize.Min)) {
                        Box(Modifier.width(4.dp).fillMaxHeight().background(if (c.responsavel) E.Green else Color.Transparent))
                        Column(Modifier.weight(1f).padding(14.dp)) {
                            Row(verticalAlignment = Alignment.Top) {
                                Column(Modifier.weight(1f).clickable { onEditCitizen(c.cns) }) {
                                    if (c.responsavel) Kicker("Responsável")
                                    Text(c.nome, fontSize = 18.sp, color = E.Ink)
                                    Text("${c.sexoLabel} | ${c.idade}", fontSize = 15.sp, color = E.Ink2)
                                }
                                EsusOutlinedButton("Visitar", onClick = { onVisit(c.cns) })
                                IconButton(onClick = { onEditCitizen(c.cns) }) { Icon(Icons.Filled.MoreVert, null, tint = E.Ink2) }
                            }
                            if (c.chips.isNotEmpty()) FlowRow(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { c.chips.forEach { EsusChip(it) } }
                        }
                    }
                }
            }
            item(key = "add-$fam") {
                EsusCard(Modifier.padding(vertical = 6.dp), onClick = { onAddCitizen(fam) }) {
                    Row(Modifier.fillMaxWidth().padding(vertical = 14.dp), horizontalArrangement = Arrangement.Center) { Text("+  ADICIONAR CIDADÃO", fontSize = 15.sp, letterSpacing = 1.5.sp, color = E.Ink, fontWeight = FontWeight.Medium) }
                }
            }
        }
        item {
            Row(Modifier.fillMaxWidth().clickable { onToast("Adicionar família não disponível no simulador") }.padding(vertical = 24.dp), horizontalArrangement = Arrangement.Center) {
                Text("+  ADICIONAR FAMÍLIA", fontSize = 15.sp, letterSpacing = 1.5.sp, color = E.Ink, fontWeight = FontWeight.Medium)
            }
        }
        val visitas = Repo.visitasDo(uuid).sortedByDescending { it.dataHora }
        if (visitas.isNotEmpty()) {
            item { Text("Visitas registradas neste simulador", fontSize = 14.sp, color = E.Ink2, modifier = Modifier.padding(horizontal = 8.dp, vertical = 8.dp)) }
            items(visitas, key = { "v-" + it.uuid }) { v ->
                EsusCard(Modifier.padding(vertical = 3.dp)) {
                    Column(Modifier.padding(12.dp)) {
                        Text("${v.dataHora.replace("T", " ").take(16)} · ${Repo.cidadao(v.cns)?.nome ?: v.cns}", fontSize = 15.sp, color = E.Ink)
                        Text(v.motivos.joinToString(", ").ifBlank { "sem motivo" } + " · " + v.desfecho + " · origem: " + v.origem, fontSize = 13.sp, color = E.Ink2)
                    }
                }
            }
        }
    }
}

// ---------------- cidadaos (lista) ----------------
@Composable
fun CitizensScreen(onHouse: (String) -> Unit) {
    var q by remember { mutableStateOf("") }
    val list = Repo.cidadaos.filter { q.isBlank() || it.nome.contains(q, true) || it.cns.contains(q) }.sortedBy { it.nome }
    Column(Modifier.fillMaxSize().background(E.Bg)) {
        BodyTitle("Cidadãos")
        OutlinedTextField(value = q, onValueChange = { q = it }, label = { Text("Buscar por nome ou CNS") }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = E.Green, focusedLabelColor = E.GreenDark))
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(8.dp, 8.dp, 8.dp, 24.dp)) {
            items(list, key = { it.cns }) { c ->
                val i = Repo.imovel(c.imovelUuid)
                EsusCard(Modifier.padding(vertical = 3.dp), onClick = { onHouse(c.imovelUuid) }) {
                    Column(Modifier.padding(12.dp)) {
                        Text(c.nome, fontSize = 17.sp, color = E.Ink)
                        Text("${c.sexoLabel} | ${c.idade} · CNS ${c.cns}", fontSize = 13.sp, color = E.Ink2)
                        if (i != null) Text("${i.logradouroCompleto}, ${i.numero} · ${i.bairro}", fontSize = 13.sp, color = E.Ink2)
                    }
                }
            }
        }
    }
}

// ---------------- relatorios do territorio ----------------
@Composable
fun ReportsScreen() {
    val visitas = Repo.visitas.sortedByDescending { it.dataHora }
    LazyColumn(Modifier.fillMaxSize().background(E.Bg), contentPadding = PaddingValues(8.dp, 0.dp, 8.dp, 24.dp)) {
        item { BodyTitle("Relatórios do território") }
        item {
            EsusCard {
                Column(Modifier.padding(14.dp)) {
                    Body("Imóveis: ${Repo.imoveis.size}"); Body("Famílias: ${Repo.imoveis.sumOf { it.familias.size }}"); Body("Cidadãos: ${Repo.cidadaos.size}")
                    Body("Visitas registradas neste aparelho: ${visitas.size}")
                    Body("Cidadãos com hipertensão: ${Repo.cidadaos.count { c -> c.condicoes.any { it.contains("ipertens") } }}", size = 14)
                    Body("Cidadãos com diabetes: ${Repo.cidadaos.count { c -> c.condicoes.any { it.contains("iabet") } }}", size = 14)
                }
            }
        }
        item { Text("Visitas registradas", fontSize = 14.sp, color = E.Ink2, modifier = Modifier.padding(8.dp)) }
        if (visitas.isEmpty()) item { Body("Nenhuma visita registrada ainda.", E.Ink2, 14) }
        items(visitas, key = { it.uuid }) { v ->
            val c = Repo.cidadao(v.cns); val i = Repo.imovel(v.imovelUuid)
            EsusCard(Modifier.padding(vertical = 3.dp)) {
                Column(Modifier.padding(12.dp)) {
                    Text("${v.dataHora.replace("T", " ").take(16)} · ${c?.nome ?: v.cns}", fontSize = 16.sp, color = E.Ink)
                    if (i != null) Text("${i.logradouroCompleto}, ${i.numero} · ${i.bairro}", fontSize = 13.sp, color = E.Ink2)
                    Text("Motivos: " + v.motivos.joinToString(", ").ifBlank { "nenhum" }, fontSize = 13.sp, color = E.Ink2)
                    Text("Desfecho: ${v.desfecho} · turno ${v.turno} · origem ${v.origem}", fontSize = 13.sp, color = E.Ink2)
                }
            }
        }
    }
}

// ---------------- mapa, sincronizacao, inconsistencias, ajuda, sobre ----------------
@Composable
fun MapScreen() {
    val pts = Repo.imoveis.filter { it.lat != null && it.lon != null }
    Column(Modifier.fillMaxSize().background(E.Bg)) {
        BodyTitle("Mapa")
        Body("O simulador não desenha o mapa. ${pts.size} imóveis têm coordenadas no cadastro.", E.Ink2, 14)
        Spacer(Modifier.height(12.dp))
        Canvas(Modifier.fillMaxWidth().height(320.dp).padding(16.dp).background(Color(0xFFE8F5E9))) {
            if (pts.isEmpty()) return@Canvas
            val minLat = pts.minOf { it.lat!! }; val maxLat = pts.maxOf { it.lat!! }; val minLon = pts.minOf { it.lon!! }; val maxLon = pts.maxOf { it.lon!! }
            pts.forEach { p ->
                val x = ((p.lon!! - minLon) / (maxLon - minLon + 1e-9)).toFloat() * size.width * 0.9f + size.width * 0.05f
                val y = (1 - (p.lat!! - minLat) / (maxLat - minLat + 1e-9)).toFloat() * size.height * 0.9f + size.height * 0.05f
                drawCircle(E.GreenDark, radius = 8f, center = Offset(x, y))
            }
        }
    }
}

@Composable
fun SyncScreen() {
    var status by remember { mutableStateOf(if (Repo.ultimaSincronizacao.isBlank()) "Nunca sincronizado" else "Última sincronização: ${Repo.ultimaSincronizacao}") }
    Column(Modifier.fillMaxSize().background(E.Bg).padding(16.dp)) {
        BodyTitle("Sincronização")
        Body("No aplicativo oficial, a sincronização envia cadastros e visitas ao PEC da unidade e recebe as atualizações. Aqui ela apenas registra o momento e escreve o resumo no logcat (tag ESUSMOCK).", E.Ink2, 14)
        Spacer(Modifier.height(16.dp))
        Body(status)
        Spacer(Modifier.height(16.dp))
        EsusButton("Sincronizar", Modifier.fillMaxWidth()) { status = "Última sincronização: " + Repo.sincronizar() + " · 0 inconsistências" }
    }
}

@Composable
fun SimpleScreen(title: String, text: String) {
    Column(Modifier.fillMaxSize().background(E.Bg).padding(16.dp)) { BodyTitle(title); Body(text, E.Ink2, 15) }
}
