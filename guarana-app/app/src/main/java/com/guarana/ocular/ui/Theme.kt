@file:OptIn(androidx.compose.ui.text.ExperimentalTextApi::class)

package com.guarana.ocular.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.guarana.ocular.R

/**
 * Estrutura e ritmo do Granola (papel claro, filetes translucidos, pilulas, um acento so), paleta do guarana.
 * Neutros quentes derivados da semente; o vermelho da fruta faz o papel do verde-lima do Granola: aparece pouco.
 */
object G {
    val Red = Color(0xFFD9706A)          // botao principal e acento
    val RedDark = Color(0xFFB3403A)
    val Pink = Color(0xFFF3B9B3)
    val PinkSoft = Color(0xFFFBE4E1)
    val Cream = Color(0xFFFBF7F2)        // fundo
    val Paper2 = Color(0xFFFFFFFF)       // cartoes brancos
    val Sand = Color(0xFFF1E9E1)         // superficies secundarias, trilhos
    val Line = Color(0xFFD9CFC6)         // borda visivel
    val Hairline = Color(0x332B2320)     // filete entre linhas
    val Seed = Color(0xFF2B2320)         // texto primario, botao principal
    val Ink2 = Color(0xFF6E625C)         // texto secundario
    val Ink3 = Color(0xFF9A8F88)         // texto terciario
    val Leaf = Color(0xFF9CC3A0)
    val LeafDark = Color(0xFF4F7D4E)
    val LeafSoft = Color(0xFFE3F0E2)
    val Amber = Color(0xFFF2C98A)
    val AmberDark = Color(0xFF8C5F0E)
    val AmberSoft = Color(0xFFFBEFD9)
    val Outline = Line
}

private val scheme = lightColorScheme(
    primary = G.Red, onPrimary = Color.White,
    primaryContainer = G.PinkSoft, onPrimaryContainer = G.RedDark,
    secondary = G.Red, onSecondary = Color.White,
    secondaryContainer = G.PinkSoft, onSecondaryContainer = G.RedDark,
    tertiary = G.LeafDark, tertiaryContainer = G.LeafSoft, onTertiaryContainer = G.LeafDark,
    background = G.Cream, onBackground = G.Seed,
    surface = Color.White, onSurface = G.Seed,
    surfaceVariant = G.Paper2, onSurfaceVariant = G.Ink2,
    outline = G.Line, outlineVariant = G.Hairline,
    error = G.RedDark, onError = Color.White,
)

val GuaranaShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(16.dp),
    extraLarge = RoundedCornerShape(50),
)

private fun w(weight: Int) = FontVariation.Settings(FontVariation.weight(weight))

/** Corpo: Inter (equivalente livre da Melange Grotesk do Granola). */
val Sans = FontFamily(
    Font(R.font.inter, FontWeight.Normal, variationSettings = w(400)),
    Font(R.font.inter, FontWeight.Medium, variationSettings = w(500)),
    Font(R.font.inter, FontWeight.SemiBold, variationSettings = w(600)),
    Font(R.font.inter, FontWeight.Bold, variationSettings = w(700)),
)

/** Titulos e numeros: Inter Tight, entreletra fechada como no painel de referencia. */
val Display = FontFamily(
    Font(R.font.intertight, FontWeight.Medium, variationSettings = w(500)),
    Font(R.font.intertight, FontWeight.SemiBold, variationSettings = w(600)),
    Font(R.font.intertight, FontWeight.Bold, variationSettings = w(700)),
)

private val type = Typography(
    displayLarge = TextStyle(fontFamily = Display, fontWeight = FontWeight.SemiBold, fontSize = 40.sp, lineHeight = 44.sp, letterSpacing = (-1).sp),
    headlineLarge = TextStyle(fontFamily = Display, fontWeight = FontWeight.SemiBold, fontSize = 30.sp, lineHeight = 36.sp, letterSpacing = (-0.6).sp),
    headlineMedium = TextStyle(fontFamily = Display, fontWeight = FontWeight.SemiBold, fontSize = 24.sp, lineHeight = 30.sp, letterSpacing = (-0.4).sp),
    headlineSmall = TextStyle(fontFamily = Display, fontWeight = FontWeight.Medium, fontSize = 20.sp, lineHeight = 26.sp, letterSpacing = (-0.3).sp),
    titleLarge = TextStyle(fontFamily = Display, fontWeight = FontWeight.Medium, fontSize = 20.sp, lineHeight = 26.sp, letterSpacing = (-0.3).sp),
    titleMedium = TextStyle(fontFamily = Sans, fontWeight = FontWeight.Medium, fontSize = 16.sp, lineHeight = 22.sp),
    titleSmall = TextStyle(fontFamily = Sans, fontWeight = FontWeight.Medium, fontSize = 14.sp, lineHeight = 20.sp),
    bodyLarge = TextStyle(fontFamily = Sans, fontWeight = FontWeight.Normal, fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontFamily = Sans, fontWeight = FontWeight.Normal, fontSize = 14.sp, lineHeight = 21.sp),
    bodySmall = TextStyle(fontFamily = Sans, fontWeight = FontWeight.Normal, fontSize = 12.sp, lineHeight = 17.sp),
    labelLarge = TextStyle(fontFamily = Sans, fontWeight = FontWeight.Medium, fontSize = 14.sp, lineHeight = 20.sp),
    labelMedium = TextStyle(fontFamily = Sans, fontWeight = FontWeight.Medium, fontSize = 12.sp, lineHeight = 16.sp),
    labelSmall = TextStyle(fontFamily = Sans, fontWeight = FontWeight.Medium, fontSize = 11.sp, lineHeight = 14.sp, letterSpacing = 0.2.sp),
)

@Composable
fun GuaranaTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = scheme, shapes = GuaranaShapes, typography = type, content = content)
}
