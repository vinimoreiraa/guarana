import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Simulador do e-SUS Territorio: reproduz as telas do app oficial do ACS com dados ficticios, para testar
// a integracao do Guarana (injecao de visita e de condicao extra) sem depender de um PEC de municipio.
android {
    namespace = "com.guarana.esusmock"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.guarana.esusmock"
        minSdk = 26
        targetSdk = 35
        versionCode = (System.currentTimeMillis() / 60000L).toInt()
        versionName = "0.1." + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd.HHmm"))
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    val bom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(bom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
}
