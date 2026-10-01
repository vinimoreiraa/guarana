package com.guarana.esusmock

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.Assessment
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.ExitToApp
import androidx.compose.material.icons.outlined.Group
import androidx.compose.material.icons.outlined.HelpOutline
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.MergeType
import androidx.compose.material.icons.outlined.Place
import androidx.compose.material.icons.outlined.Sync
import androidx.compose.material.icons.outlined.SyncProblem
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Repo.init(this)
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(primary = E.Green, secondary = E.GreenDark, background = E.Bg, surface = Color.White)) { EsusApp() }
        }
    }
}

sealed interface Tela {
    data object Login : Tela
    data object Logradouros : Tela
    data class Imoveis(val bairro: String, val chaveRua: String) : Tela
    data class Domicilio(val uuid: String) : Tela
    data class Cidadao(val cns: String?, val imovelUuid: String, val familia: String) : Tela
    data class Visita(val imovelUuid: String, val cns: String) : Tela
    data object Cidadaos : Tela
    data object Relatorios : Tela
    data object Mapa : Tela
    data object Sincronizar : Tela
    data class Simples(val titulo: String, val texto: String) : Tela
}

@Composable
fun EsusApp() {
    val ctx = LocalContext.current
    var tela by remember { mutableStateOf<Tela>(Tela.Login) }
    val pilha = remember { mutableListOf<Tela>() }
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    var tick by remember { mutableStateOf(0) }   // forca recomposicao apos gravar no Repo
    fun toast(t: String) = Toast.makeText(ctx, t, Toast.LENGTH_SHORT).show()
    fun ir(t: Tela) { pilha += tela; tela = t }
    fun voltar() { tela = pilha.removeLastOrNull() ?: Tela.Logradouros; tick++ }
    fun raiz(t: Tela) { pilha.clear(); tela = t; scope.launch { drawer.close() } }

    if (tela == Tela.Login) { LoginScreen { pilha.clear(); tela = Tela.Logradouros }; return }
    BackHandler { if (drawer.isOpen) scope.launch { drawer.close() } else if (pilha.isEmpty()) toast("Use Sair no menu") else voltar() }

    val topLevel = tela is Tela.Logradouros || tela is Tela.Cidadaos || tela is Tela.Relatorios || tela is Tela.Mapa || tela is Tela.Sincronizar || tela is Tela.Simples
    val titulo = when (val t = tela) {
        is Tela.Logradouros -> "Lista de logradouros"; is Tela.Imoveis -> "Lista de imóveis"; is Tela.Domicilio -> "Informações do domicílio"
        is Tela.Cidadao -> "Cidadão"; is Tela.Visita -> "Visita domiciliar"; is Tela.Cidadaos -> "Cidadãos"; is Tela.Relatorios -> "Relatórios do território"
        is Tela.Mapa -> "Mapa"; is Tela.Sincronizar -> "Sincronização"; is Tela.Simples -> t.titulo; else -> ""
    }

    ModalNavigationDrawer(
        drawerState = drawer, gesturesEnabled = topLevel,
        drawerContent = { Drawer(onPick = { raiz(it) }, onSair = { pilha.clear(); tela = Tela.Login; scope.launch { drawer.close() } }) },
    ) {
        Column(Modifier.fillMaxSize().background(E.Bg)) {
            EsusTopBar(titulo, back = !topLevel, onNav = { if (topLevel) scope.launch { drawer.open() } else voltar() }) {
                if (tela is Tela.Logradouros || tela is Tela.Imoveis) {
                    Text("FILTROS", color = Color.White, fontSize = 13.sp, letterSpacing = 1.sp, modifier = Modifier.clickable { toast("Filtros não disponíveis no simulador") }.padding(8.dp))
                    IconButton(onClick = { raiz(Tela.Cidadaos) }) { Icon(Icons.Filled.Search, "Buscar", tint = Color.White) }
                }
                if (tela is Tela.Domicilio) IconButton(onClick = { toast("Ajuda: toque em VISITAR para registrar a visita") }) { Icon(Icons.Outlined.HelpOutline, null, tint = Color.White) }
            }
            key(tick) {
                when (val t = tela) {
                    is Tela.Logradouros -> StreetsScreen { b, r -> ir(Tela.Imoveis(b, r)) }
                    is Tela.Imoveis -> PropertiesScreen(t.bairro, t.chaveRua) { ir(Tela.Domicilio(it)) }
                    is Tela.Domicilio -> HouseholdScreen(
                        t.uuid, onVisit = { ir(Tela.Visita(t.uuid, it)) },
                        onEditCitizen = { cns -> ir(Tela.Cidadao(cns, t.uuid, Repo.cidadao(cns)?.familiaNumero ?: "")) },
                        onAddCitizen = { fam -> ir(Tela.Cidadao(null, t.uuid, fam)) }, onToast = ::toast,
                    )
                    is Tela.Cidadao -> CitizenWizard(t.cns, t.imovelUuid, t.familia, onDone = { toast("Cadastro salvo"); voltar() }, onCancel = ::voltar)
                    is Tela.Visita -> VisitForm(t.imovelUuid, t.cns, onDone = { toast("Visita registrada"); voltar() }, onCancel = ::voltar)
                    is Tela.Cidadaos -> CitizensScreen { ir(Tela.Domicilio(it)) }
                    is Tela.Relatorios -> ReportsScreen()
                    is Tela.Mapa -> MapScreen()
                    is Tela.Sincronizar -> SyncScreen()
                    is Tela.Simples -> SimpleScreen(t.titulo, t.texto)
                    else -> {}
                }
            }
        }
    }
}

@Composable
private fun Drawer(onPick: (Tela) -> Unit, onSair: () -> Unit) {
    ModalDrawerSheet(drawerContainerColor = Color.White, drawerShape = androidx.compose.ui.graphics.RectangleShape) {
        Column(Modifier.verticalScroll(rememberScrollState()).statusBarsPadding().padding(bottom = 24.dp)) {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 20.dp)) {
                Text(Repo.agente.nome, fontSize = 20.sp, color = E.Ink)
                Text(Repo.agente.papel, fontSize = 13.sp, color = E.Ink2)
                Spacer(Modifier.height(10.dp))
                Row { Text("EQUIPE ", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = E.Ink); Text(Repo.equipe.uppercase(), fontSize = 12.sp, color = E.Ink) }
                Text(Repo.unidade, fontSize = 13.sp, color = E.Ink2)
            }
            Section("Sincronização")
            Item(Icons.Outlined.Sync, "Sincronizar") { onPick(Tela.Sincronizar) }
            Item(Icons.Outlined.SyncProblem, "Inconsistências da sincronização") { onPick(Tela.Simples("Inconsistências da sincronização", "Nenhuma inconsistência. No aplicativo oficial, aparecem aqui as fichas rejeitadas pelo PEC com o motivo.")) }
            Divider()
            Section("Território")
            Item(Icons.Outlined.Place, "Mapa") { onPick(Tela.Mapa) }
            Item(Icons.Outlined.Group, "Cidadãos") { onPick(Tela.Cidadaos) }
            Item(Icons.Outlined.Assessment, "Relatórios do território") { onPick(Tela.Relatorios) }
            Item(Icons.Outlined.MergeType, "Unificar logradouros") { onPick(Tela.Simples("Unificar logradouros", "Não disponível no simulador.")) }
            Item(Icons.Outlined.Edit, "Editar logradouro") { onPick(Tela.Simples("Editar logradouro", "Não disponível no simulador.")) }
            Divider()
            Item(Icons.Outlined.HelpOutline, "Obter ajuda") { onPick(Tela.Simples("Obter ajuda", "Simulador do e-SUS Território para testes de integração do Guaraná. Fluxo: Lista de logradouros → imóvel → VISITAR → FINALIZAR. O que for gravado sai no logcat com a tag ESUSMOCK.")) }
            Item(Icons.Outlined.Info, "Sobre") { onPick(Tela.Simples("Sobre", "e-SUS Território (simulador) · não é o aplicativo oficial do Ministério da Saúde. Dados fictícios de ${Repo.unidade}. Feito para o projeto Guaraná.")) }
            Item(Icons.Outlined.ExitToApp, "Sair", onSair)
        }
    }
}

@Composable
private fun Section(text: String) = Text(text, fontSize = 15.sp, color = E.Ink, modifier = Modifier.padding(start = 16.dp, top = 16.dp, bottom = 6.dp))

@Composable
private fun Item(icon: ImageVector, text: String, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = E.Ink2, modifier = Modifier.size(22.dp)); Spacer(Modifier.width(24.dp))
        Text(text, fontSize = 16.sp, color = E.Ink)
    }
}
