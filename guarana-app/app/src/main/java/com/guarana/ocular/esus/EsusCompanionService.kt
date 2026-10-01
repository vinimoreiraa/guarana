package com.guarana.ocular.esus

import android.accessibilityservice.AccessibilityService
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.drawable.GradientDrawable
import android.provider.Settings
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.widget.Toast
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import android.view.accessibility.AccessibilityWindowInfo
import android.widget.ImageView
import android.widget.LinearLayout
import com.guarana.ocular.MainActivity
import com.guarana.ocular.R
import kotlin.math.abs

/**
 * Companheiro do e-SUS: servico de acessibilidade que percebe quando o e-SUS Territorio (oficial ou simulador)
 * esta em primeiro plano e desenha uma pilula flutuante "Analisar olho" por cima dele. Tocar abre a captura do
 * Guarana; o resultado tem "Voltar ao e-SUS". A pilula some quando o e-SUS sai da frente.
 *
 * Privacidade: para mostrar ou esconder a pilula, o servico consulta apenas o nome do pacote da janela ativa.
 * Nenhum texto da tela do e-SUS e lido. (A injecao de dados no formulario de visita, quando existir, e uma
 * acao explicita do agente e escreve nos campos; tambem nao extrai dados.)
 *
 * Ativacao: Ajustes do Android > Acessibilidade > "Guarana · companheiro do e-SUS". Por adb:
 *   adb shell settings put secure enabled_accessibility_services com.guarana.ocular/com.guarana.ocular.esus.EsusCompanionService
 *   adb shell settings put secure accessibility_enabled 1
 */
class EsusCompanionService : AccessibilityService() {
    companion object {
        /** app oficial do ACS e o nosso simulador */
        val ESUS_PACKAGES = setOf("br.gov.saude.acs", "com.guarana.esusmock")
        @Volatile var running = false

        fun isEnabled(ctx: Context): Boolean {
            val full = "${ctx.packageName}/${EsusCompanionService::class.java.name}"
            val short = "${ctx.packageName}/.esus.EsusCompanionService"
            val list = Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: return false
            return list.split(':').any { it.equals(full, true) || it.equals(short, true) }
        }
    }

    private var pill: View? = null
    private var lastEsus: String = ESUS_PACKAGES.first()
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var fillJob: Job? = null
    private val wm: WindowManager get() = getSystemService(WINDOW_SERVICE) as WindowManager

    override fun onServiceConnected() { super.onServiceConnected(); running = true; refresh(null) }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val t = event?.eventType ?: return
        if (t == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED || t == AccessibilityEvent.TYPE_WINDOWS_CHANGED) refresh(event.packageName?.toString())
    }

    override fun onInterrupt() {}
    override fun onUnbind(intent: Intent?): Boolean { running = false; hide(); return super.onUnbind(intent) }
    override fun onDestroy() { running = false; hide(); scope.cancel(); super.onDestroy() }

    /** Pacote da janela de aplicativo ativa, ou nulo se nao houver. Teclado, sistema e a nossa propria pilula nao contam. */
    private fun activeAppPackage(): String? {
        val ws = runCatching { windows }.getOrNull().orEmpty()
        val app = ws.filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
        val active = app.firstOrNull { it.isActive } ?: app.firstOrNull { it.isFocused }
        return active?.root?.packageName?.toString()
    }

    private fun refresh(eventPkg: String?) {
        val active = activeAppPackage()
        if (CompanionBridge.pendingFill != null) Log.i("Guarana", "esus: refresh ativo=$active evento=$eventPkg")
        if (active != null) { if (active in ESUS_PACKAGES) { lastEsus = active; show(); maybeFill() } else hide(); return }
        // sem janela de app ativa (teclado aberto, transicao, nossa propria pilula): so o e-SUS aparecendo muda o estado
        val ime = runCatching { windows }.getOrNull().orEmpty().any { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD }
        when {
            eventPkg in ESUS_PACKAGES -> { lastEsus = eventPkg!!; show() }
            eventPkg == packageName || eventPkg == null || ime -> {}
            else -> hide()
        }
    }

    // ---------------- preenchimento da Ficha de Visita ----------------
    // Acao explicita do agente ("Registrar visita no e-SUS" no resultado). O servico le apenas os rotulos dos campos
    // e o nome da pessoa para achar onde marcar; nao extrai dados. FINALIZAR fica com o agente.

    private fun maybeFill() {
        val f = CompanionBridge.pendingFill ?: return
        if (fillJob?.isActive == true) return
        fillJob = scope.launch {
            try { runFill(f) } catch (e: Throwable) { Log.e("Guarana", "esus: preenchimento falhou", e); CompanionBridge.pendingFill = null }
        }
    }

    private fun toast(t: String) = Toast.makeText(this, t, Toast.LENGTH_LONG).show()
    /** Raiz da janela do e-SUS: a janela ativa quando e dele; senao procura entre as janelas de app (a pilula e o sistema podem estar ativos). */
    private fun root(): AccessibilityNodeInfo? {
        runCatching { rootInActiveWindow }.getOrNull()?.takeIf { it.packageName?.toString() in ESUS_PACKAGES }?.let { return it }
        return runCatching { windows }.getOrNull().orEmpty()
            .filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
            .firstNotNullOfOrNull { w -> w.root?.takeIf { it.packageName?.toString() in ESUS_PACKAGES } }
    }

    private suspend fun runFill(f: EsusFill) {
        Log.i("Guarana", "esus: preenchendo ${f.patientName} itens=${f.itens} desfecho=${f.desfecho}")
        toast("Guaraná: preenchendo a visita no e-SUS…")
        // 1. chegar ao formulario da visita: se estiver na ficha do domicilio, toca VISITAR da pessoa
        var opened = false
        var tries = 0
        while (tries < 40) {
            val r = root()
            if (r != null) {
                if (isVisitForm(r)) break
                if (!opened && tryOpenVisit(r, f.patientName)) { opened = true; delay(1200); tries++; continue }
            }
            delay(500); tries++
        }
        val onForm = root()?.let { isVisitForm(it) } == true
        Log.i("Guarana", "esus: formulario=$onForm tentativas=$tries")
        if (!onForm) {
            CompanionBridge.pendingFill = null
            toast("Guaraná: abra a visita de ${f.patientName.ifBlank { "da pessoa" }} no e-SUS e toque de novo em Registrar.")
            return
        }
        // 2. volta ao topo do formulario e marca os itens
        Log.i("Guarana", "esus: no formulario, subindo")
        scrollToTop()
        Log.i("Guarana", "esus: no topo")
        val marcados = mutableListOf<String>(); val faltou = mutableListOf<String>()
        for (item in f.itens) { if (ensureChecked(item)) marcados += item else faltou += item }
        // 3. desfecho
        ensureSelected(f.desfecho)
        delay(600); scrollToTop()   // volta ao topo: o agente ve o motivo marcado antes de FINALIZAR
        CompanionBridge.pendingFill = null
        Log.i("Guarana", "esus: marcados=$marcados faltou=$faltou")
        toast("Guaraná: marcado ${marcados.joinToString(", ")}" + (if (faltou.isNotEmpty()) " (não achei: ${faltou.joinToString(", ")})" else "") + ". Confira e toque em FINALIZAR.")
    }

    /** Busca por texto percorrendo a arvore (findAccessibilityNodeInfosByText nao enxerga todas as telas, ex. Compose). */
    private fun byText(r: AccessibilityNodeInfo, text: String): List<AccessibilityNodeInfo> {
        val out = mutableListOf<AccessibilityNodeInfo>()
        fun walk(n: AccessibilityNodeInfo?) {
            if (n == null) return
            val t = n.text?.toString().orEmpty(); val d = n.contentDescription?.toString().orEmpty()
            if (t.contains(text, true) || d.contains(text, true)) out += n
            for (i in 0 until n.childCount) walk(n.getChild(i))
        }
        walk(r); return out
    }

    private fun isVisitForm(r: AccessibilityNodeInfo) = byText(r, "Busca ativa").isNotEmpty()

    private fun exact(r: AccessibilityNodeInfo, text: String): List<AccessibilityNodeInfo> =
        byText(r, text).filter { n ->
            n.text?.toString()?.trim().equals(text, true) || n.contentDescription?.toString()?.trim().equals(text, true)
        }

    private fun clickableAncestor(n: AccessibilityNodeInfo): AccessibilityNodeInfo? { var c: AccessibilityNodeInfo? = n; while (c != null && !c.isClickable) c = c.parent; return c }
    private fun findCheckable(n: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (n.isCheckable) return n
        for (i in 0 until n.childCount) { n.getChild(i)?.let { c -> findCheckable(c)?.let { return it } } }
        return null
    }
    /** Caixa de marcar ligada a um rotulo: o proprio no, um irmao, ou algo dentro do ancestral clicavel. */
    private fun checkableFor(n: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (n.isCheckable) return n
        n.parent?.let { p -> for (i in 0 until p.childCount) { p.getChild(i)?.let { c -> if (c.isCheckable) return c } } }
        return clickableAncestor(n)?.let { findCheckable(it) }
    }
    private fun findScrollable(n: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (n.isScrollable) return n
        for (i in 0 until n.childCount) { n.getChild(i)?.let { c -> findScrollable(c)?.let { return it } } }
        return null
    }
    private fun scroll(forward: Boolean): Boolean {
        val s = root()?.let { findScrollable(it) } ?: return false
        return s.performAction(if (forward) AccessibilityNodeInfo.ACTION_SCROLL_FORWARD else AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD)
    }
    private suspend fun scrollToTop() { repeat(12) { if (!scroll(false)) return; delay(250) } }
    private fun centerY(n: AccessibilityNodeInfo): Int { val b = Rect(); n.getBoundsInScreen(b); return b.centerY() }

    /** Na ficha do domicilio: acha o nome da pessoa e o VISITAR da mesma linha (nao o VISITAR FAMILIA). */
    private suspend fun tryOpenVisit(r0: AccessibilityNodeInfo, name: String): Boolean {
        if (name.isBlank()) return false
        var r: AccessibilityNodeInfo? = r0
        repeat(8) {
            val rr = r ?: return false
            val nameNode = exact(rr, name).firstOrNull() ?: byText(rr, name).firstOrNull { it.text?.toString()?.contains(name, true) == true }
            if (nameNode != null) {
                val y = centerY(nameNode)
                val btn = exact(rr, "VISITAR").minByOrNull { kotlin.math.abs(centerY(it) - y) } ?: return false
                if (kotlin.math.abs(centerY(btn) - y) > dp(120f)) return false
                (clickableAncestor(btn) ?: btn).performAction(AccessibilityNodeInfo.ACTION_CLICK)
                return true
            }
            if (exact(rr, "VISITAR").isEmpty() || !scroll(true)) return false
            delay(400); r = root()
        }
        return false
    }

    private suspend fun ensureChecked(label: String): Boolean {
        repeat(12) {
            val r = root() ?: return false
            val n = exact(r, label).firstOrNull()
            if (n != null) {
                val chk = checkableFor(n)
                if (chk?.isChecked == true) return true
                val target = chk ?: clickableAncestor(n) ?: return false
                target.performAction(AccessibilityNodeInfo.ACTION_CLICK); delay(350)
                return true
            }
            if (!scroll(true)) return false
            delay(450)
        }
        return false
    }

    /** Desfecho: se o valor ja aparece na tela, nada a fazer; senao abre o campo "Desfecho" e escolhe a opcao. */
    private suspend fun ensureSelected(value: String) {
        repeat(12) {
            val r = root() ?: return
            val v = exact(r, value).firstOrNull()
            if (v != null) {
                val chk = checkableFor(v)
                if (chk != null && !chk.isChecked) { chk.performAction(AccessibilityNodeInfo.ACTION_CLICK); delay(300) }
                return
            }
            val field = exact(r, "Desfecho").firstOrNull()
            if (field != null) {
                (clickableAncestor(field) ?: field).performAction(AccessibilityNodeInfo.ACTION_CLICK); delay(500)
                root()?.let { rr -> exact(rr, value).firstOrNull()?.let { o -> (clickableAncestor(o) ?: o).performAction(AccessibilityNodeInfo.ACTION_CLICK); delay(300); return } }
                return
            }
            if (!scroll(true)) return
            delay(450)
        }
    }

    private fun dp(v: Float) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, resources.displayMetrics).toInt()

    /**
     * Pilula vertical como a do Granola: capsula translucida encostada na borda direita com a fruta em cima
     * (pegador; toque abre o Guarana) e um botao redondo com um olho embaixo (abre direto a analise).
     */
    private fun show() {
        if (pill != null) return
        val w = dp(40f)
        val capsule = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(0, dp(6f), 0, dp(6f))
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE; cornerRadius = w / 2f
                setColor(0xF0FBF7F2.toInt()); setStroke(dp(1f), 0x55D9CFC6.toInt())
            }
            elevation = dp(3f).toFloat(); alpha = 0.94f
            clipChildren = false; clipToPadding = false
            contentDescription = "Guaraná"
        }
        // logo desenhada direto no tamanho final (vetor justo, sem escala de view) para ficar nitida
        val fruit = ImageView(this).apply { setImageResource(R.drawable.ic_logo_tight); contentDescription = "Abrir o Guaraná" }
        val divider = View(this).apply { setBackgroundColor(0x40D9CFC6.toInt()) }
        // botao escuro com o olho branco: a acao, claramente diferente da fruta
        val play = ImageView(this).apply {
            setImageResource(R.drawable.ic_eye)
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(0xFF2B2320.toInt()) }
            setPadding(dp(5f), dp(5f), dp(5f), dp(5f))
            contentDescription = "Analisar olho"
        }
        capsule.addView(fruit, LinearLayout.LayoutParams(dp(23f), dp(31f)).apply { topMargin = dp(2f) })
        capsule.addView(divider, LinearLayout.LayoutParams(dp(18f), dp(1f)).apply { topMargin = dp(7f); bottomMargin = dp(7f) })
        capsule.addView(play, LinearLayout.LayoutParams(dp(28f), dp(28f)))
        val lp = WindowManager.LayoutParams(
            w, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT,
        ).apply { gravity = Gravity.TOP or Gravity.END; x = dp(4f); y = (resources.displayMetrics.heightPixels * 0.34f).toInt() }
        // a capsula inteira arrasta; no toque curto, o olho abre a analise e a fruta abre o Guarana
        var downY = 0f; var startY = 0; var moved = false
        val touch = View.OnTouchListener { v, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> { downY = e.rawY; startY = lp.y; moved = false; capsule.alpha = 1f; true }
                MotionEvent.ACTION_MOVE -> {
                    val d = (e.rawY - downY).toInt(); if (abs(d) > dp(6f)) moved = true
                    lp.y = (startY + d).coerceIn(0, resources.displayMetrics.heightPixels - dp(90f)); runCatching { wm.updateViewLayout(capsule, lp) }; true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    capsule.alpha = 0.94f
                    if (e.actionMasked == MotionEvent.ACTION_UP && !moved) { v.performClick(); openGuarana(capture = v === play) }
                    true
                }
                else -> false
            }
        }
        fruit.setOnTouchListener(touch); play.setOnTouchListener(touch); capsule.setOnTouchListener(touch)
        runCatching { wm.addView(capsule, lp); pill = capsule }.onFailure { Log.w("Guarana", "pílula do e-SUS: $it") }
    }

    private val CNS_RE = Regex("""CNS (\d{15})""")

    private fun hide() { pill?.let { runCatching { wm.removeView(it) } }; pill = null }

    private fun openGuarana(capture: Boolean) {
        val pessoa = pessoaNaTela()
        startActivity(Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            putExtra(MainActivity.EXTRA_FROM_ESUS, lastEsus)
            putExtra(MainActivity.EXTRA_CAPTURE, capture)
            pessoa?.let { putExtra(MainActivity.EXTRA_PESSOA, it) }
        })
    }

    /**
     * Quem esta aberto no e-SUS agora: a linha "Masculino | 76 anos e 11 meses | CNS 947..." e o nome logo acima dela
     * (cabecalho da visita e da ficha do cidadao). Devolve "nome|cns|sexo|idade" ou null fora dessas telas.
     */
    private fun pessoaNaTela(): String? {
        val r = root() ?: return null
        val textos = mutableListOf<String>()
        fun walk(n: AccessibilityNodeInfo?) {
            if (n == null) return
            n.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }?.let { textos += it }
            for (i in 0 until n.childCount) walk(n.getChild(i))
        }
        walk(r)
        val i = textos.indexOfFirst { CNS_RE.containsMatchIn(it) }
        if (i <= 0) return null
        val linha = textos[i]
        val cns = CNS_RE.find(linha)!!.groupValues[1]
        val sexo = when { linha.startsWith("Fem") -> "F"; linha.startsWith("Masc") -> "M"; else -> "" }
        val idade = Regex("""(\d+) anos?""").find(linha)?.groupValues?.get(1) ?: ""
        return "${textos[i - 1]}|$cns|$sexo|$idade"
    }
}
