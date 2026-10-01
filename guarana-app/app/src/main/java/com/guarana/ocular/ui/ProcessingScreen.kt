package com.guarana.ocular.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun ProcessingScreen() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            GuaranaLogo(84.dp)
            Spacer(Modifier.height(20.dp))
            CircularProgressIndicator(color = G.Seed, trackColor = G.Sand)
            Spacer(Modifier.height(14.dp))
            Text("Analisando a foto…", style = MaterialTheme.typography.headlineSmall)
        }
    }
}
