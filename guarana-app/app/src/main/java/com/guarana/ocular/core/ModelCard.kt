package com.guarana.ocular.core

import android.content.Context
import org.json.JSONObject

/** Le assets/model_card.json: tamanho de entrada, normalizacao, rotulos e limiares vem DAQUI, nunca de constantes. */
class ModelCard(
    val name: String,
    val file: String,
    val inputSize: Int,
    val mean: FloatArray,
    val std: FloatArray,
    val labels: List<String>,
    val thresholds: Map<String, Float>,
    /** limiar de "candidato" (mais frouxo) por sinal; se o cartao nao trouxer, o app usa metade do limiar de presente */
    val candidateThresholds: Map<String, Float> = emptyMap(),
    val unreliable: Set<String>,
    /** "multirrotulo" (v2.x, sigmoide por sinal) ou "multiclasse" (v2.3+, softmax com classe normal e decisao conservadora) */
    val task: String = "multirrotulo",
    /** corte de P(doente) = 1 - P(normal) para "precisa de avaliacao" (so multiclasse) */
    val corteDoente: Float = 0.5f,
) {
    val multiclasse: Boolean get() = task == "multiclasse"
    companion object {
        fun load(context: Context): ModelCard {
            val o = JSONObject(context.assets.open("model_card.json").bufferedReader().use { it.readText() })
            val input = o.getJSONObject("input")
            if (o.optString("task") == "multiclasse") {
                val cl = o.getJSONArray("classes"); val m = input.getJSONArray("mean"); val sd = input.getJSONArray("std"); val thr0 = o.optJSONObject("thresholds")
                return ModelCard(
                    name = o.optString("name", "modelo"), file = o.getJSONObject("files").getString("recommended"), inputSize = input.getInt("size"),
                    mean = FloatArray(3) { m.getDouble(it).toFloat() }, std = FloatArray(3) { sd.getDouble(it).toFloat() },
                    labels = List(cl.length()) { cl.getString(it) }, thresholds = thr0?.keys()?.asSequence()?.associateWith { thr0.getDouble(it).toFloat() } ?: emptyMap(),
                    unreliable = emptySet(), task = "multiclasse", corteDoente = o.optDouble("corte_doente", 0.5).toFloat(),
                )
            }
            val shape = input.getJSONArray("shape")
            val meanArr = input.getJSONArray("mean")
            val stdArr = input.getJSONArray("std")
            val labelsArr = o.getJSONObject("output").getJSONArray("labels")
            val thr = o.getJSONObject("thresholds")
            val thrC = o.optJSONObject("thresholds_candidato")
            val files = o.optJSONObject("files")
            val unrel = o.optJSONArray("unreliable_labels")
            return ModelCard(
                name = o.optString("name", "modelo"),
                file = files?.optString("recommended", "ocular_v1.onnx") ?: "ocular_v1.onnx",
                inputSize = shape.getInt(shape.length() - 1),
                mean = FloatArray(3) { meanArr.getDouble(it).toFloat() },
                std = FloatArray(3) { stdArr.getDouble(it).toFloat() },
                labels = List(labelsArr.length()) { labelsArr.getString(it) },
                thresholds = thr.keys().asSequence().associateWith { thr.getDouble(it).toFloat() },
                candidateThresholds = thrC?.keys()?.asSequence()?.associateWith { thrC.getDouble(it).toFloat() } ?: emptyMap(),
                unreliable = if (unrel == null) emptySet() else List(unrel.length()) { unrel.getString(it) }.toSet(),
            )
        }
    }
}
