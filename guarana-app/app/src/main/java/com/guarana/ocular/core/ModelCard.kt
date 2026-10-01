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
) {
    companion object {
        fun load(context: Context): ModelCard {
            val o = JSONObject(context.assets.open("model_card.json").bufferedReader().use { it.readText() })
            val input = o.getJSONObject("input")
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
