package com.guarana.esusmock

import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.Period
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

/** Modelos do simulador. Os nomes seguem o vocabulario do e-SUS Territorio: imovel, familia, cidadao, visita. */
data class Familia(val numero: String, val responsavelCns: String)

data class Imovel(
    val uuid: String, val tipoLogradouro: String, val logradouro: String, val numero: String, val complemento: String,
    val bairro: String, val cep: String, val microarea: String, val telefone: String, val telefoneContato: String,
    val pontoReferencia: String, val ultimaVisitaCadastro: String, val familias: List<Familia>,
    val situacaoMoradia: String, val agua: String, val esgoto: String, val lat: Double?, val lon: Double?,
) {
    val logradouroCompleto: String get() = "$tipoLogradouro $logradouro".trim()
    /** chave de agrupamento por rua dentro do bairro */
    val chaveRua: String get() = "$bairro|$logradouroCompleto"
}

data class Cidadao(
    val cns: String, val cpf: String, val nome: String, val sexo: String, val dataNascimento: String, val racaCor: String,
    val imovelUuid: String, val familiaNumero: String, val responsavel: Boolean,
    val condicoes: List<String>, val condicoesExtra: List<String>, val telefone: String,
    val nomeMae: String = "", val nomePai: String = "", val email: String = "", val nis: String = "",
    val nacionalidade: String = "Brasileira", val ufNascimento: String = "SP", val municipioNascimento: String = "São José dos Campos",
    val frequentaEscola: Boolean? = null, val grauInstrucao: String = "", val situacaoTrabalho: String = "", val ocupacao: String = "",
    val respostas: Map<String, Boolean?> = emptyMap(),   // perguntas sim/nao do cadastro individual (id -> resposta)
) {
    val sexoLabel: String get() = when (sexo) { "F" -> "Feminino"; "M" -> "Masculino"; else -> "Não informado" }
    val primeiroNome: String get() = nome.split(" ").first()
    val idade: String get() = runCatching {
        val p = Period.between(LocalDate.parse(dataNascimento), LocalDate.now())
        when {
            p.years == 0 && p.months == 0 -> "${p.days} dias"
            p.years == 0 -> "${p.months} meses"
            p.months == 0 -> "${p.years} anos"
            else -> "${p.years} anos e ${p.months} " + if (p.months == 1) "mês" else "meses"
        }
    }.getOrDefault("")
    val chips: List<String> get() = condicoes + condicoesExtra

    fun toJson(): JSONObject = JSONObject().put("cns", cns).put("cpf", cpf).put("nome", nome).put("sexo", sexo).put("data_nascimento", dataNascimento)
        .put("raca_cor", racaCor).put("domicilio_uuid", imovelUuid).put("familia_numero", familiaNumero).put("responsavel_familiar", responsavel)
        .put("condicoes", JSONArray(condicoes)).put("condicoes_extra", JSONArray(condicoesExtra)).put("telefone", telefone)
        .put("nome_mae", nomeMae).put("nome_pai", nomePai).put("email", email).put("nis", nis)
        .put("nacionalidade", nacionalidade).put("uf_nascimento", ufNascimento).put("municipio_nascimento", municipioNascimento)
        .put("frequenta_escola", frequentaEscola ?: JSONObject.NULL).put("grau_instrucao", grauInstrucao).put("situacao_trabalho", situacaoTrabalho).put("ocupacao", ocupacao)
        .put("respostas", JSONObject().also { o -> respostas.forEach { (k, v) -> o.put(k, v ?: JSONObject.NULL) } })

    companion object {
        fun fromJson(o: JSONObject): Cidadao {
            fun list(k: String) = o.optJSONArray(k)?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList()
            val r = o.optJSONObject("respostas") ?: JSONObject()
            return Cidadao(
                cns = o.optString("cns"), cpf = o.optString("cpf"), nome = o.optString("nome"), sexo = o.optString("sexo"),
                dataNascimento = o.optString("data_nascimento"), racaCor = o.optString("raca_cor"), imovelUuid = o.optString("domicilio_uuid"),
                familiaNumero = o.optString("familia_numero"), responsavel = o.optBoolean("responsavel_familiar", false),
                condicoes = list("condicoes"), condicoesExtra = list("condicoes_extra"), telefone = o.optString("telefone"),
                nomeMae = o.optString("nome_mae"), nomePai = o.optString("nome_pai"), email = o.optString("email"), nis = o.optString("nis"),
                nacionalidade = o.optString("nacionalidade", "Brasileira"), ufNascimento = o.optString("uf_nascimento", "SP"),
                municipioNascimento = o.optString("municipio_nascimento", "São José dos Campos"),
                frequentaEscola = if (o.isNull("frequenta_escola")) null else o.optBoolean("frequenta_escola"),
                grauInstrucao = o.optString("grau_instrucao"), situacaoTrabalho = o.optString("situacao_trabalho"), ocupacao = o.optString("ocupacao"),
                respostas = r.keys().asSequence().associateWith { k -> if (r.isNull(k)) null else r.optBoolean(k) },
            )
        }
    }
}

/** Ficha de Visita Domiciliar e Territorial registrada no simulador. */
data class Visita(
    val uuid: String, val imovelUuid: String, val cns: String, val dataHora: String, val turno: String, val tipoImovel: String,
    val compartilhada: Boolean, val motivos: List<String>, val peso: String, val altura: String, val desfecho: String, val origem: String,
) {
    val data: String get() = dataHora.take(10)
    fun toJson(): JSONObject = JSONObject().put("uuid", uuid).put("imovel_uuid", imovelUuid).put("cns", cns).put("data_hora", dataHora).put("turno", turno)
        .put("tipo_imovel", tipoImovel).put("compartilhada", compartilhada).put("motivos", JSONArray(motivos)).put("peso", peso).put("altura", altura)
        .put("desfecho", desfecho).put("origem", origem)
    companion object {
        fun fromJson(o: JSONObject) = Visita(
            uuid = o.optString("uuid"), imovelUuid = o.optString("imovel_uuid"), cns = o.optString("cns"), dataHora = o.optString("data_hora"),
            turno = o.optString("turno"), tipoImovel = o.optString("tipo_imovel"), compartilhada = o.optBoolean("compartilhada"),
            motivos = o.optJSONArray("motivos")?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList(),
            peso = o.optString("peso"), altura = o.optString("altura"), desfecho = o.optString("desfecho"), origem = o.optString("origem", "simulador"),
        )
    }
}

data class Profissional(val cns: String, val cpf: String, val nome: String, val papel: String, val ine: String)

/**
 * Dados do simulador: o territorio ficticio vem do mesmo JSON que o Guarana importa (assets), e o que o agente
 * registra aqui (visitas, cadastros editados) fica em arquivos do app. Tudo o que e gravado tambem vai para o logcat
 * com a tag ESUSMOCK, para conferir uma injecao vinda de fora com `adb logcat -s ESUSMOCK`.
 */
object Repo {
    const val TAG = "ESUSMOCK"
    lateinit var dir: File
    var unidade: String = ""; var municipio: String = ""; var uf: String = ""
    var equipe: String = ""
    lateinit var agente: Profissional
    var imoveis: List<Imovel> = emptyList()
    var cidadaos: MutableList<Cidadao> = mutableListOf()
    var visitas: MutableList<Visita> = mutableListOf()
    var ultimaSincronizacao: String = ""

    fun init(context: Context) {
        if (imoveis.isNotEmpty()) return
        dir = File(context.filesDir, "esus_mock").apply { mkdirs() }
        val json = JSONObject(context.assets.open("mock_territorio.json").bufferedReader().use { it.readText() })
        val u = json.optJSONObject("unidade") ?: JSONObject()
        unidade = u.optString("nome"); municipio = u.optString("municipio"); uf = u.optString("uf")
        val profs = json.optJSONArray("profissionais") ?: JSONArray()
        val acs = (0 until profs.length()).map { profs.getJSONObject(it) }.firstOrNull { it.optString("papel") == "ACS" } ?: profs.getJSONObject(0)
        agente = Profissional(acs.optString("cns"), acs.optString("cpf"), acs.optString("nome"), "Agente Comunitário de Saúde", acs.optString("ine"))
        val eqs = json.optJSONArray("equipes") ?: JSONArray()
        equipe = (0 until eqs.length()).map { eqs.getJSONObject(it) }.firstOrNull { it.optString("ine") == agente.ine }?.optString("nome") ?: ""
        val hs = json.optJSONArray("domicilios") ?: JSONArray()
        imoveis = (0 until hs.length()).map { i ->
            val h = hs.getJSONObject(i)
            val fams = h.optJSONArray("familias")?.let { a -> List(a.length()) { Familia(a.getJSONObject(it).optString("numero"), a.getJSONObject(it).optString("responsavel_cns")) } } ?: emptyList()
            Imovel(
                uuid = h.getString("uuid"), tipoLogradouro = h.optString("tipo_logradouro", "Rua"), logradouro = h.optString("logradouro"), numero = h.optString("numero"),
                complemento = h.optString("complemento"), bairro = h.optString("bairro"), cep = h.optString("cep"), microarea = h.optString("microarea"),
                telefone = h.optString("telefone"), telefoneContato = h.optString("telefone_contato"), pontoReferencia = h.optString("ponto_referencia"),
                ultimaVisitaCadastro = h.optString("ultima_visita"), familias = fams, situacaoMoradia = h.optString("situacao_moradia"),
                agua = h.optString("agua"), esgoto = h.optString("esgoto"),
                lat = if (h.isNull("latitude")) null else h.optDouble("latitude"), lon = if (h.isNull("longitude")) null else h.optDouble("longitude"),
            )
        }.sortedWith(compareBy({ it.bairro }, { it.logradouroCompleto }, { it.numero.toIntOrNull() ?: 0 }))
        val fC = File(dir, "cidadaos.json")
        cidadaos = if (fC.exists()) readList(fC).map { Cidadao.fromJson(it) }.toMutableList()
        else (json.optJSONArray("pessoas") ?: JSONArray()).let { a -> List(a.length()) { Cidadao.fromJson(a.getJSONObject(it)) } }.toMutableList()
        visitas = readList(File(dir, "visitas.json")).map { Visita.fromJson(it) }.toMutableList()
        ultimaSincronizacao = File(dir, "sync.txt").takeIf { it.exists() }?.readText().orEmpty()
    }

    private fun readList(f: File): List<JSONObject> = if (!f.exists()) emptyList() else runCatching { val a = JSONArray(f.readText()); List(a.length()) { a.getJSONObject(it) } }.getOrDefault(emptyList())

    fun imovel(uuid: String): Imovel? = imoveis.firstOrNull { it.uuid == uuid }
    fun cidadaosDo(imovelUuid: String): List<Cidadao> = cidadaos.filter { it.imovelUuid == imovelUuid }
    fun cidadao(cns: String): Cidadao? = cidadaos.firstOrNull { it.cns == cns }
    fun visitasDo(imovelUuid: String): List<Visita> = visitas.filter { it.imovelUuid == imovelUuid }

    /** Data da ultima visita realizada: a do cadastro ou a mais recente registrada no simulador. */
    fun ultimaVisita(i: Imovel): String? {
        val reg = visitasDo(i.uuid).filter { it.desfecho == "Visita realizada" }.maxOfOrNull { it.data }
        return listOfNotNull(i.ultimaVisitaCadastro.takeIf { it.isNotBlank() }, reg).maxOrNull()
    }
    fun diasDesdeVisita(i: Imovel): Long? = ultimaVisita(i)?.let { runCatching { ChronoUnit.DAYS.between(LocalDate.parse(it), LocalDate.now()) }.getOrNull() }
    fun visitadoHa(i: Imovel): String = when (val d = diasDesdeVisita(i)) { null -> "Nunca visitado"; 0L -> "Visitado hoje"; 1L -> "Visitado ontem"; else -> "Visitado há $d dias" }
    fun condicoesAAcompanhar(imovelUuid: String): Int = cidadaosDo(imovelUuid).sumOf { it.chips.size }

    fun salvarCidadao(c: Cidadao) {
        val i = cidadaos.indexOfFirst { it.cns == c.cns }
        if (i >= 0) cidadaos[i] = c else cidadaos += c
        File(dir, "cidadaos.json").writeText(JSONArray(cidadaos.map { it.toJson() }).toString())
        Log.i(TAG, "cadastro individual salvo: ${c.toJson()}")
    }

    fun registrarVisita(v: Visita) {
        visitas += v
        File(dir, "visitas.json").writeText(JSONArray(visitas.map { it.toJson() }).toString())
        Log.i(TAG, "visita registrada: ${v.toJson()}")
    }

    fun sincronizar(): String {
        ultimaSincronizacao = LocalDateTime.now().format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm"))
        File(dir, "sync.txt").writeText(ultimaSincronizacao)
        Log.i(TAG, "sincronizacao: ${visitas.size} visitas, ${cidadaos.size} cidadaos")
        return ultimaSincronizacao
    }

    fun novoCns(): String {
        // CNS provisorio (inicia em 9) com digito verificador valido, so para o simulador
        while (true) {
            val d = IntArray(15) { if (it == 0) 9 else (0..9).random() }
            if (d.withIndex().sumOf { (i, v) -> v * (15 - i) } % 11 == 0) return d.joinToString("")
        }
    }

    fun cpfFormatado(cpf: String): String = if (cpf.length == 11) "${cpf.substring(0, 3)}.${cpf.substring(3, 6)}.${cpf.substring(6, 9)}-${cpf.substring(9)}" else cpf
}
