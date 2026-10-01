package com.guarana.ocular.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.guarana.ocular.core.SignState

data class TriageStyle(val title: String, val text: String, val bg: Color, val fg: Color)

fun triageStyle(triage: String, child: Boolean): TriageStyle = when (triage) {
    "encaminhar_urgente" -> TriageStyle("Encaminhar com urgência",
        if (child) "Pupila esbranquiçada em criança pede avaliação oftalmológica imediata." else "Sinal que pede avaliação imediata.",
        G.Red, Color.White)
    "encaminhar" -> TriageStyle("Encaminhar", "Sinal compatível com condição que pede avaliação por profissional de saúde.", G.PinkSoft, G.RedDark)
    "observar" -> TriageStyle("Observar", "Sinal fraco ou que costuma ser benigno. Repita a foto em alguns dias ou se piorar.", G.AmberSoft, G.AmberDark)
    else -> TriageStyle("Sem sinais detectados", "Nenhum sinal acima do limiar nesta foto. Não exclui doença.", G.LeafSoft, G.LeafDark)
}

fun triageShort(triage: String): String = when (triage) {
    "encaminhar_urgente" -> "Urgente"
    "encaminhar" -> "Encaminhar"
    "observar" -> "Observar"
    else -> "Sem sinais"
}

/** Filete translucido entre linhas, como o Granola. */
@Composable
fun Hairline(modifier: Modifier = Modifier) = HorizontalDivider(modifier, thickness = 1.dp, color = G.Hairline)

/** Rotulo pequeno de secao ("Recentes", "Hoje"). */
@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(text, style = MaterialTheme.typography.labelMedium, color = G.Ink3, modifier = modifier.padding(top = 22.dp, bottom = 8.dp))
}

/** Cartao branco sobre o creme, cantos 12, sem sombra. */
@Composable
fun SoftCard(modifier: Modifier = Modifier, color: Color = G.Paper2, content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier = modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium, color = color, tonalElevation = 0.dp, shadowElevation = 0.dp) {
        Column(Modifier.padding(16.dp), content = content)
    }
}

/** Botao principal: pilula no vermelho da fruta. */
@Composable
fun PrimaryPill(text: String, modifier: Modifier = Modifier, enabled: Boolean = true, onClick: () -> Unit, icon: (@Composable RowScope.() -> Unit)? = null) {
    Button(
        onClick = onClick, enabled = enabled, modifier = modifier.height(52.dp), shape = RoundedCornerShape(50),
        colors = ButtonDefaults.buttonColors(containerColor = G.Red, contentColor = Color.White, disabledContainerColor = G.Sand, disabledContentColor = G.Ink3),
        elevation = null,
    ) {
        if (icon != null) { icon(); Spacer(Modifier.width(10.dp)) }
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

/** Botao secundario: pilula com filete, fundo do papel. */
@Composable
fun SecondaryPill(text: String, modifier: Modifier = Modifier, onClick: () -> Unit, icon: (@Composable RowScope.() -> Unit)? = null) {
    OutlinedButton(
        onClick = onClick, modifier = modifier.height(48.dp), shape = RoundedCornerShape(50),
        border = BorderStroke(1.dp, G.Line),
        colors = ButtonDefaults.outlinedButtonColors(contentColor = G.RedDark, containerColor = Color.Transparent),
    ) {
        if (icon != null) { icon(); Spacer(Modifier.width(10.dp)) }
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
fun Pill(text: String, bg: Color, fg: Color) {
    Text(
        text, style = MaterialTheme.typography.labelSmall, color = fg,
        modifier = Modifier.clip(RoundedCornerShape(50)).background(bg).padding(horizontal = 9.dp, vertical = 4.dp),
    )
}

@Composable
fun StateChip(state: SignState) = when (state) {
    SignState.present -> Pill("Presente", G.PinkSoft, G.RedDark)
    SignState.candidate -> Pill("Sinal fraco", G.AmberSoft, G.AmberDark)
    SignState.absent -> Pill("Ausente", G.Sand, G.Ink2)
}

@Composable
fun TriageChip(triage: String) {
    val s = triageStyle(triage, false)
    Pill(triageShort(triage), s.bg, s.fg)
}

/** [text] substitui a frase padrao (ex.: quando a ficha do cidadao elevou a triagem alem do que a foto mostra). */
@Composable
fun TriageBanner(triage: String, child: Boolean, text: String? = null) {
    val s = triageStyle(triage, child)
    SoftCard(color = s.bg) {
        Text(s.title, style = MaterialTheme.typography.headlineMedium, color = s.fg)
        Spacer(Modifier.height(4.dp))
        Text(text ?: s.text, style = MaterialTheme.typography.bodyMedium, color = s.fg)
    }
}

@Composable
fun WarningCard(title: String, text: String) {
    SoftCard(color = G.AmberSoft) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Outlined.Info, null, tint = G.AmberDark)
            Spacer(Modifier.width(10.dp))
            Column {
                Text(title, style = MaterialTheme.typography.titleSmall, color = G.AmberDark)
                Text(text, style = MaterialTheme.typography.bodySmall, color = G.AmberDark)
            }
        }
    }
}
