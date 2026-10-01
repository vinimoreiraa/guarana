package com.guarana.esusmock

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Block
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Paleta do e-SUS Territorio: verde Material classico, fundo cinza claro, cartoes brancos com sombra, texto Roboto. */
object E {
    val Green = Color(0xFF4CAF50)
    val GreenDark = Color(0xFF388E3C)
    val GreenBar = Color(0xFF43A047)
    val Bg = Color(0xFFF5F5F5)
    val Card = Color.White
    val Ink = Color(0xDE000000)
    val Ink2 = Color(0x8A000000)
    val Ink3 = Color(0x61000000)
    val DarkHeader = Color(0xFF424242)
    val ChipBg = Color(0xFFEEEEEE)
    val Line = Color(0x1F000000)
}

/** Barra verde de 56 dp com icone de menu ou voltar, titulo branco e acoes. */
@Composable
fun EsusTopBar(title: String, back: Boolean, onNav: () -> Unit, actions: @Composable RowScope.() -> Unit = {}) {
    Surface(color = E.GreenBar, shadowElevation = 4.dp) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().height(56.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onNav) { Icon(if (back) Icons.AutoMirrored.Filled.ArrowBack else Icons.Filled.Menu, if (back) "Voltar" else "Menu", tint = Color.White) }
            Text(title, color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f).padding(start = 8.dp), maxLines = 1)
            actions()
        }
    }
}

/** Cartao branco de cantos quase retos com sombra leve, como o Material antigo. */
@Composable
fun EsusCard(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    val m = if (onClick != null) modifier.clickable(onClick = onClick) else modifier
    Surface(m.fillMaxWidth(), shape = RoundedCornerShape(2.dp), color = E.Card, shadowElevation = 2.dp) { Column(content = content) }
}

/** Botao verde retangular com texto em caixa alta. */
@Composable
fun EsusButton(text: String, modifier: Modifier = Modifier, enabled: Boolean = true, onClick: () -> Unit) {
    Button(
        onClick = onClick, enabled = enabled, modifier = modifier.height(44.dp), shape = RoundedCornerShape(2.dp),
        colors = ButtonDefaults.buttonColors(containerColor = E.Green, contentColor = Color.White, disabledContainerColor = Color(0xFFBDBDBD)),
        elevation = ButtonDefaults.buttonElevation(defaultElevation = 2.dp),
    ) { Text(text.uppercase(), fontWeight = FontWeight.Bold, letterSpacing = 1.sp) }
}

/** Botao de texto em caixa alta (LIMPAR, NAO, SIM, PROXIMA ETAPA...). */
@Composable
fun EsusTextButton(text: String, modifier: Modifier = Modifier, color: Color = E.Ink2, enabled: Boolean = true, onClick: () -> Unit) {
    TextButton(onClick = onClick, enabled = enabled, modifier = modifier, shape = RoundedCornerShape(2.dp)) {
        Text(text.uppercase(), color = if (enabled) color else E.Ink3, fontWeight = FontWeight.Medium, letterSpacing = 1.5.sp, fontSize = 14.sp)
    }
}

/** Botao contornado (VISITAR, VISITAR FAMILIA, + ADICIONAR CIDADAO). */
@Composable
fun EsusOutlinedButton(text: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Surface(modifier.clickable(onClick = onClick), shape = RoundedCornerShape(2.dp), color = Color.Transparent, border = BorderStroke(1.dp, E.Line)) {
        Text(text.uppercase(), color = E.Ink, fontWeight = FontWeight.Medium, letterSpacing = 1.5.sp, fontSize = 14.sp, modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp))
    }
}

@Composable
fun EsusChip(text: String) {
    Text(text, color = E.Ink, fontSize = 14.sp, modifier = Modifier.background(E.ChipBg, RoundedCornerShape(3.dp)).padding(horizontal = 8.dp, vertical = 4.dp))
}

@Composable
fun Divider() = HorizontalDivider(color = E.Line, thickness = 1.dp)

/** Campo com rotulo flutuante e "Obrigatorio" embaixo, como o cadastro do cidadao. */
@Composable
fun EsusField(label: String, value: String, onChange: (String) -> Unit, modifier: Modifier = Modifier, required: Boolean = false, enabled: Boolean = true, singleLine: Boolean = true) {
    Column(modifier) {
        OutlinedTextField(
            value = value, onValueChange = onChange, label = { Text(label) }, singleLine = singleLine, enabled = enabled, modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(4.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = E.Green, focusedLabelColor = E.GreenDark),
        )
        if (required) Text("Obrigatório", color = E.Ink2, fontSize = 12.sp, modifier = Modifier.padding(start = 4.dp, top = 2.dp))
    }
}

/** Campo de selecao com seta, como os "Grau de instrucao", "Situacao no mercado de trabalho". */
@Composable
fun EsusDropdown(label: String, value: String, options: List<String>, onChange: (String) -> Unit, modifier: Modifier = Modifier, required: Boolean = false) {
    var open by remember { mutableStateOf(false) }
    Column(modifier) {
        Box {
            OutlinedTextField(
                value = value, onValueChange = {}, readOnly = true, label = { Text(label) }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                trailingIcon = { Icon(Icons.Filled.ArrowDropDown, null, tint = E.Ink2) }, shape = RoundedCornerShape(4.dp),
                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = E.Green, focusedLabelColor = E.GreenDark),
            )
            Box(Modifier.matchParentSize().clickable { open = true })
            DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                options.forEach { o -> DropdownMenuItem(text = { Text(o) }, onClick = { onChange(o); open = false }) }
            }
        }
        if (required) Text("Obrigatório", color = E.Ink2, fontSize = 12.sp, modifier = Modifier.padding(start = 4.dp, top = 2.dp))
    }
}

/**
 * Cartao Sim/Nao do cadastro individual: cabecalho cinza escuro com "⊘ Nao tem diabetes" quando Nao, verde com
 * "✓ Tem diabetes" quando Sim, branco com a pergunta quando vazio; embaixo LIMPAR a esquerda e NAO SIM a direita.
 */
@Composable
fun YesNoCard(pergunta: String, sim: String, nao: String, value: Boolean?, onChange: (Boolean?) -> Unit, extra: (@Composable ColumnScope.() -> Unit)? = null) {
    EsusCard {
        val (bg, fg, icon, texto) = when (value) {
            true -> listOf(E.GreenBar, Color.White, Icons.Filled.Check, sim)
            false -> listOf(E.DarkHeader, Color.White, Icons.Filled.Block, nao)
            null -> listOf(E.Card, E.Ink, null, pergunta)
        }
        Row(Modifier.fillMaxWidth().background(bg as Color).padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            if (icon != null) { Icon(icon as ImageVector, null, tint = fg as Color, modifier = Modifier.size(20.dp)); Spacer(Modifier.width(8.dp)) }
            Text(texto as String, color = fg as Color, fontWeight = FontWeight.Bold, fontSize = 15.sp)
        }
        Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            EsusTextButton("Limpar", enabled = value != null, onClick = { onChange(null) })
            Spacer(Modifier.weight(1f))
            EsusTextButton("Não", color = if (value == false) E.Ink else E.Ink2, onClick = { onChange(false) })
            EsusTextButton("Sim", color = if (value == true) E.GreenDark else E.Ink2, onClick = { onChange(true) })
        }
        if (value == true && extra != null) Column(Modifier.padding(horizontal = 14.dp).padding(bottom = 12.dp), content = extra)
    }
}

/** Rodape das etapas do cadastro: ETAPA ANTERIOR a esquerda, PROXIMA ETAPA ou FINALIZAR a direita. */
@Composable
fun StepFooter(first: Boolean, last: Boolean, onPrev: () -> Unit, onNext: () -> Unit) {
    Surface(color = E.Card, shadowElevation = 8.dp) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            EsusTextButton("Etapa anterior", enabled = !first, color = E.Ink, onClick = onPrev)
            EsusTextButton(if (last) "Finalizar" else "Próxima etapa", color = E.Ink, onClick = onNext)
        }
    }
}

/** Titulo de secao grande dentro do corpo ("Lista de logradouros", "Identificacao") com "Etapa N de 7" opcional. */
@Composable
fun BodyTitle(text: String, right: String? = null) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text, fontSize = 22.sp, fontWeight = FontWeight.Medium, color = E.Ink, modifier = Modifier.weight(1f))
        if (right != null) Text(right, fontSize = 12.sp, color = E.Ink2)
    }
}

@Composable
fun Kicker(text: String) = Text(text.uppercase(), fontSize = 12.sp, color = E.Ink2, letterSpacing = 1.sp)

@Composable
fun Body(text: String, color: Color = E.Ink, size: Int = 16) = Text(text, fontSize = size.sp, color = color)
