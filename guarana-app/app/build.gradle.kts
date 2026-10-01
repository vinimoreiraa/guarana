import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.guarana.ocular"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.guarana.ocular"
        minSdk = 26
        targetSdk = 35
        // versao sempre crescente: qualquer APK novo instala por cima do anterior, mantendo icone, dados e permissoes
        versionCode = (System.currentTimeMillis() / 60000L).toInt()
        versionName = "0.1." + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd.HHmm"))
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64") }   // tablets atuais, tablets de entrada 32 bits (e-SUS Território roda neles) e emulador
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")   // demo: assinado com a chave de debug, instala por sideload
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    val bom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(bom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.exifinterface:exifinterface:1.3.7")
    val camerax = "1.4.1"
    implementation("androidx.camera:camera-core:$camerax")
    implementation("androidx.camera:camera-camera2:$camerax")
    implementation("androidx.camera:camera-lifecycle:$camerax")
    implementation("androidx.camera:camera-view:$camerax")
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.github.mik3y:usb-serial-for-android:3.8.1")
    implementation("net.lingala.zip4j:zip4j:2.11.5")
    implementation("org.maplibre.gl:android-sdk:11.8.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
}
