package com.guarana.ocular.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Color as AColor
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.guarana.ocular.core.Household
import com.guarana.ocular.core.Patient
import com.guarana.ocular.core.TerritoryStore
import com.guarana.ocular.core.Visit
import com.guarana.ocular.core.VisitState
import org.maplibre.android.MapLibre
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.location.LocationComponentActivationOptions
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.offline.OfflineManager
import org.maplibre.android.offline.OfflineRegion
import org.maplibre.android.offline.OfflineRegionError
import org.maplibre.android.offline.OfflineRegionStatus
import org.maplibre.android.offline.OfflineTilePyramidRegionDefinition
import org.maplibre.android.style.expressions.Expression
import org.maplibre.android.style.layers.CircleLayer
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.Property
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.layers.SymbolLayer
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.Point

/** Estilo aberto sem chave (OpenFreeMap, dados do OpenStreetMap). "Baixar mapa desta área" guarda os tiles para uso sem internet. */
const val MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"
private const val SRC = "domicilios"
private const val SRC_ROTA = "rota"
private const val LAYER = "domicilios-pontos"

/** Controles do mapa expostos para quem o embute (painel ou tela cheia). */
class MapHandle {
    internal var map: MapLibreMap? = null
    var onStatus: (String) -> Unit = {}
    fun downloadVisibleArea(ctx: Context, name: String) {
        val m = map ?: return
        val def = OfflineTilePyramidRegionDefinition(MAP_STYLE_URL, m.projection.visibleRegion.latLngBounds, 10.0, 16.0, ctx.resources.displayMetrics.density)
        onStatus("Preparando download…")
        OfflineManager.getInstance(ctx).createOfflineRegion(def, "{\"nome\":\"$name\"}".toByteArray(), object : OfflineManager.CreateOfflineRegionCallback {
            override fun onCreate(offlineRegion: OfflineRegion) {
                offlineRegion.setObserver(object : OfflineRegion.OfflineRegionObserver {
                    override fun onStatusChanged(s: OfflineRegionStatus) {
                        val pct = if (s.requiredResourceCount > 0) (100.0 * s.completedResourceCount / s.requiredResourceCount).toInt() else 0
                        onStatus(if (s.isComplete) "Mapa desta área salvo para uso sem internet (${s.completedResourceSize / 1_000_000} MB)" else "Baixando mapa… $pct%")
                    }
                    override fun onError(error: OfflineRegionError) { onStatus("Erro no download: ${error.message}") }
                    override fun mapboxTileCountLimitExceeded(limit: Long) { onStatus("Área grande demais; aproxime o mapa") }
                })
                offlineRegion.setDownloadState(OfflineRegion.STATE_ACTIVE)
            }
            override fun onError(error: String) { onStatus("Erro: $error") }
        })
    }
}

/**
 * Mapa dos domicilios de um dia: pinos coloridos por estado da visita, nome da pessoa, trajeto sugerido (vizinho mais proximo)
 * e posicao atual. Reutilizado pelo painel inicial e pela tela de mapa.
 */
@Composable
fun HouseholdMap(
    modifier: Modifier,
    date: String,
    visits: List<Visit>,
    households: Map<String, Household>,
    patients: Map<String, Patient>,
    handle: MapHandle,
    showRoute: Boolean = true,
    onSelect: (Visit?) -> Unit = {},
    overlay: @Composable BoxScope.() -> Unit = {},
) {
    val ctx = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val viewRef = remember { arrayOfNulls<MapView>(1) }
    val day = visits.filter { it.date == date }
    val ordered = remember(day, households) { TerritoryStore.route(day.filter { it.state == VisitState.planejada }, households, null, null) }
    val features = remember(day, households) {
        FeatureCollection.fromFeatures(day.mapNotNull { v ->
            val h = households[v.householdId] ?: return@mapNotNull null
            if (h.lat == null || h.lon == null) return@mapNotNull null
            Feature.fromGeometry(Point.fromLngLat(h.lon, h.lat)).apply {
                addStringProperty("uuid", v.uuid)
                addStringProperty("cor", when (v.state) { VisitState.planejada -> "#D9706A"; VisitState.feita -> "#4F7D4E"; VisitState.adiada -> "#8C5F0E"; else -> "#9A8F88" })
                addStringProperty("rotulo", (patients[v.patientId]?.name ?: "").split(" ").firstOrNull() ?: "")
            }
        })
    }
    val route = remember(ordered, households) {
        val pts = ordered.mapNotNull { v -> households[v.householdId]?.let { h -> if (h.lat != null && h.lon != null) Point.fromLngLat(h.lon, h.lat) else null } }
        if (pts.size >= 2) FeatureCollection.fromFeature(Feature.fromGeometry(LineString.fromLngLats(pts))) else FeatureCollection.fromFeatures(emptyList())
    }
    val locPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { r ->
        if (r.values.any { it }) handle.map?.let { m -> m.style?.let { enableLocation(ctx, m, it) } }
    }

    fun onStyle(map: MapLibreMap, style: Style) {
        Log.i("Guarana", "mapa: ${features.features()?.size ?: 0} pontos de ${day.size} visitas")
        if (showRoute) {
            style.addSource(GeoJsonSource(SRC_ROTA, route))
            style.addLayer(LineLayer("$SRC_ROTA-linha", SRC_ROTA).withProperties(
                PropertyFactory.lineColor(AColor.parseColor("#D9706A")), PropertyFactory.lineWidth(3f), PropertyFactory.lineOpacity(0.9f),
                PropertyFactory.lineDasharray(arrayOf(2f, 1.5f)), PropertyFactory.lineCap(Property.LINE_CAP_ROUND), PropertyFactory.lineJoin(Property.LINE_JOIN_ROUND),
            ))
        }
        style.addSource(GeoJsonSource(SRC, features))
        style.addLayer(CircleLayer(LAYER, SRC).withProperties(
            PropertyFactory.circleRadius(9f), PropertyFactory.circleColor(Expression.toColor(Expression.get("cor"))),
            PropertyFactory.circleStrokeColor(AColor.WHITE), PropertyFactory.circleStrokeWidth(2f),
        ))
        style.addLayer(SymbolLayer("$LAYER-rotulo", SRC).withProperties(
            PropertyFactory.textField(Expression.get("rotulo")), PropertyFactory.textFont(arrayOf("Noto Sans Regular")), PropertyFactory.textSize(11f),
            PropertyFactory.textOffset(arrayOf(0f, 1.4f)), PropertyFactory.textColor(AColor.parseColor("#2B2320")),
            PropertyFactory.textHaloColor(AColor.WHITE), PropertyFactory.textHaloWidth(1.2f),
        ))
        val pts = features.features()?.mapNotNull { (it.geometry() as? Point)?.let { p -> LatLng(p.latitude(), p.longitude()) } }.orEmpty()
        if (pts.size >= 2) map.moveCamera(CameraUpdateFactory.newLatLngBounds(LatLngBounds.Builder().includes(pts).build(), 110))
        else if (pts.size == 1) map.moveCamera(CameraUpdateFactory.newLatLngZoom(pts.first(), 15.0))
        map.addOnMapClickListener { p ->
            val hit = map.queryRenderedFeatures(map.projection.toScreenLocation(p), LAYER).firstOrNull()
            onSelect(hit?.getStringProperty("uuid")?.let { id -> day.firstOrNull { it.uuid == id } })
            hit != null
        }
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) enableLocation(ctx, map, style)
        else locPermission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
    }

    Box(modifier) {
        AndroidView(
            factory = { c ->
                MapLibre.getInstance(c)
                MapView(c).apply {
                    viewRef[0] = this
                    onCreate(null); onStart(); onResume()
                    getMapAsync { map ->
                        handle.map = map
                        map.uiSettings.isAttributionEnabled = true
                        map.uiSettings.isLogoEnabled = false
                        map.setStyle(Style.Builder().fromUri(MAP_STYLE_URL)) { style -> runCatching { onStyle(map, style) }.onFailure { Log.e("Guarana", "mapa", it) } }
                    }
                }
            },
            modifier = Modifier.fillMaxSize(),
        )
        DisposableEffect(lifecycleOwner) {
            val obs = LifecycleEventObserver { _, e ->
                val mv = viewRef[0] ?: return@LifecycleEventObserver
                when (e) {
                    Lifecycle.Event.ON_START -> mv.onStart(); Lifecycle.Event.ON_RESUME -> mv.onResume()
                    Lifecycle.Event.ON_PAUSE -> mv.onPause(); Lifecycle.Event.ON_STOP -> mv.onStop()
                    Lifecycle.Event.ON_DESTROY -> mv.onDestroy(); else -> {}
                }
            }
            lifecycleOwner.lifecycle.addObserver(obs)
            onDispose {
                lifecycleOwner.lifecycle.removeObserver(obs)
                viewRef[0]?.let { runCatching { it.onPause(); it.onStop(); it.onDestroy() } }
                viewRef[0] = null; handle.map = null
            }
        }
        overlay()
    }
}

private fun enableLocation(ctx: Context, map: MapLibreMap, style: Style) {
    runCatching {
        val lc = map.locationComponent
        lc.activateLocationComponent(LocationComponentActivationOptions.builder(ctx, style).build())
        @Suppress("MissingPermission")
        lc.isLocationComponentEnabled = true
    }.onFailure { Log.w("Guarana", "localização: $it") }
}
