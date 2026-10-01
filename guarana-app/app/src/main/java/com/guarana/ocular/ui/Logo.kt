package com.guarana.ocular.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.unit.Dp

/**
 * Logo minimalista: a fruta de guaraná aberta reduzida a três círculos concêntricos (cápsula vermelha, arilo claro,
 * semente escura) e uma única folha. Sem gradiente, sem brilho, sem caule. Continua parecendo um olho, de propósito.
 * Proporções do logotipo da Apple: corpo grande centrado, folha pequena inclinada em cima. Mesma geometria do ícone
 * (res/drawable/ic_launcher_foreground.xml): viewport 108, corpo em (54,61) raios 22 / 12 / 7, folha de (56,38) a (69,24).
 */
@Composable
fun GuaranaLogo(size: Dp, modifier: Modifier = Modifier) {
    Canvas(modifier.size(size)) {
        // mesma geometria do icone, sem a margem da zona segura: a caixa da logo (44 x 59 no viewport 108) preenche a altura do Canvas
        val u = this.size.height / 61f
        fun x(v: Float) = (v - 54f) * u + this.size.width / 2f
        fun y(v: Float) = (v - 23f) * u
        val leaf = Path().apply {
            moveTo(x(56f), y(38f)); quadraticTo(x(58f), y(25f), x(69f), y(24f)); quadraticTo(x(68f), y(36f), x(56f), y(38f)); close()
        }
        drawPath(leaf, G.Leaf)
        val c = Offset(x(54f), y(61f))
        drawCircle(G.Red, radius = 22f * u, center = c)
        drawCircle(Color(0xFFFFF9F3), radius = 12f * u, center = c)
        drawCircle(G.Seed, radius = 7f * u, center = c)
    }
}
