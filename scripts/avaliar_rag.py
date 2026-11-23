"""
Script de avaliação sistemática e benchmark comparativo do RAG (Etapa 3).
Avalia Context Hit Rate, Aderência ao Gabarito, Recusa Correta e Latência de Inferência (qwen3.5:4b vs llama3.1:8b).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from rag.chain import criar_chain_rag
from rag.ingest import carregar_ou_criar_indice
from rag.ollama_client import obter_embeddings, obter_llm, obter_url_ollama, verificar_conexao_ollama

CAMINHO_DATASET = RAIZ / "data" / "golden_dataset.json"
CAMINHO_OUTPUT = RAIZ / "data" / "benchmarks" / "resultado_benchmark.json"


def avaliar_recuperacao(item: dict, docs_recuperados: list) -> dict:
    """Calcula métricas de recuperação (Hit Rate / Recall@k e precisão)."""
    pag_esperada = item.get("pagina_esperada")
    if pag_esperada is None:
        return {"hit": True, "posicao": None, "paginas_recuperadas": []}

    paginas = [d.metadata.get("page", 0) + 1 for d in docs_recuperados]
    hit = pag_esperada in paginas
    posicao = paginas.index(pag_esperada) + 1 if hit else None

    return {
        "hit": hit,
        "posicao": posicao,
        "paginas_recuperadas": paginas,
    }


def avaliar_geracao(item: dict, resposta: str) -> dict:
    """Verifica fidelidade léxica e taxa de recusa controlada."""
    resposta_lower = resposta.lower()
    espera_recusa = item.get("espera_recusa", False)
    palavras_chave = item.get("palavras_chave_gabarito", [])

    if espera_recusa:
        termos_recusa = [
            "não encontrei",
            "não encontrou",
            "não consta",
            "não foi encontrada",
            "não há menção",
            "não há informação",
        ]
        recusa_correta = any(t in resposta_lower for t in termos_recusa)
        aderencia = 1.0 if recusa_correta else 0.0
    else:
        acertos = sum(1 for p in palavras_chave if p.lower() in resposta_lower)
        aderencia = acertos / len(palavras_chave) if palavras_chave else 1.0
        recusa_correta = None

    return {
        "aderencia": round(aderencia, 2),
        "recusa_correta": recusa_correta,
    }


def executar_benchmark():
    print("=================================================================")
    print("INICIANDO BENCHMARK SISTEMÁTICO DE RAG — ETAPA 3")
    print("=================================================================")

    url_ollama = obter_url_ollama()
    if not verificar_conexao_ollama(url_ollama):
        print(f"ERRO: Ollama indisponível em {url_ollama}")
        sys.exit(1)

    with open(CAMINHO_DATASET, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"Dataset carregado: {len(dataset)} perguntas de referência.")
    embeddings = obter_embeddings(base_url=url_ollama)
    banco_vetores = carregar_ou_criar_indice(embeddings=embeddings)
    print(f"Banco vetorial pronto ({banco_vetores.index.ntotal} chunks).")

    modelos_para_testar = ["qwen3.5:4b", "llama3.1:8b"]
    resultados_finais = {}

    # Carrega dados parciais se já existirem
    if CAMINHO_OUTPUT.exists():
        try:
            with open(CAMINHO_OUTPUT, "r", encoding="utf-8") as f:
                resultados_finais = json.load(f)
        except Exception:
            resultados_finais = {}

    for modelo in modelos_para_testar:
        print(f"\n>>> Avaliando Modelo: {modelo} (CPU Intel i7, num_ctx=2048)...")
        llm = obter_llm(model=modelo, temperature=0.0, base_url=url_ollama, num_ctx=2048)
        chain = criar_chain_rag(banco_vetores=banco_vetores, llm=llm, k_documentos=3)

        metricas_modelo = []
        tempos_geracao = []
        tempos_recuperacao = []
        total_tokens_gerados = 0

        for idx, item in enumerate(dataset, start=1):
            pergunta = item["pergunta"]
            print(f"  [{idx}/{len(dataset)}] {item['id']}: '{pergunta[:40]}...'")

            # 1. Mede recuperação
            t_rec_inicio = time.time()
            docs = banco_vetores.similarity_search(pergunta, k=3)
            t_rec = time.time() - t_rec_inicio
            tempos_recuperacao.append(t_rec)

            rec_eval = avaliar_recuperacao(item, docs)

            # 2. Mede geração com tratamento de timeout/exceção
            t_gen_inicio = time.time()
            try:
                resposta = chain.invoke(pergunta)
                t_gen = time.time() - t_gen_inicio
                tempos_geracao.append(t_gen)

                tokens_est = len(resposta.split()) * 1.3
                total_tokens_gerados += tokens_est
                gen_eval = avaliar_geracao(item, resposta)
                preview = resposta[:160].replace("\n", " ")
            except Exception as exc:
                t_gen = time.time() - t_gen_inicio
                gen_eval = {"aderencia": 0.0, "recusa_correta": False, "erro": str(exc)}
                preview = f"FALHA: {exc}"
                print(f"    -> Erro na pergunta {item['id']}: {exc}")

            metricas_modelo.append({
                "id": item["id"],
                "tempo_recuperacao_s": round(t_rec, 4),
                "tempo_geracao_s": round(t_gen, 2),
                "tokens_estimados": int(tokens_est) if 'tokens_est' in locals() else 0,
                "recuperacao": rec_eval,
                "geracao": gen_eval,
                "resposta_preview": preview,
            })

        # Agregação das métricas
        perguntas_positivas = [m for m in metricas_modelo if not dataset[metricas_modelo.index(m)]["espera_recusa"]]
        perguntas_negativas = [m for m in metricas_modelo if dataset[metricas_modelo.index(m)]["espera_recusa"]]

        hit_rate = sum(1 for m in perguntas_positivas if m["recuperacao"]["hit"]) / len(perguntas_positivas)
        aderencia_media = sum(m["geracao"]["aderencia"] for m in perguntas_positivas) / len(perguntas_positivas)
        recusa_correta = sum(1 for m in perguntas_negativas if m["geracao"].get("recusa_correta")) / len(perguntas_negativas)
        tempo_medio_gen = sum(tempos_geracao) / len(tempos_geracao) if tempos_geracao else 0.0
        tempo_total = sum(tempos_geracao)
        tokens_por_segundo = total_tokens_gerados / tempo_total if tempo_total > 0 else 0

        resultados_finais[modelo] = {
            "resumo": {
                "total_perguntas": len(dataset),
                "perguntas_positivas": len(perguntas_positivas),
                "perguntas_negativas": len(perguntas_negativas),
                "context_hit_rate_at_3": round(hit_rate * 100, 1),
                "aderencia_gabarito_pct": round(aderencia_media * 100, 1),
                "taxa_recusa_negativa_pct": round(recusa_correta * 100, 1),
                "tempo_medio_geracao_s": round(tempo_medio_gen, 2),
                "throughput_tokens_seg": round(tokens_por_segundo, 1),
            },
            "detalhes": metricas_modelo,
        }

        # Salva incrementalmente
        CAMINHO_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(CAMINHO_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(resultados_finais, f, indent=2, ensure_ascii=False)
        print(f"  -> Resultados para {modelo} salvos com sucesso.")

    print("\n=================================================================")
    print("RELATÓRIO COMPARATIVO CONSOLIDADO (ETAPA 3)")
    print("=================================================================")
    m1 = "qwen3.5:4b"
    m2 = "llama3.1:8b"
    print(f"{'Métrica':<35} | {m1:<15} | {m2:<15}")
    print("-" * 70)
    for rotulo, chave, unidade in [
        ("Context Hit Rate @ 3", "context_hit_rate_at_3", "%"),
        ("Aderência ao Gabarito", "aderencia_gabarito_pct", "%"),
        ("Taxa de Recusa Correta", "taxa_recusa_negativa_pct", "%"),
        ("Tempo Médio de Geração", "tempo_medio_geracao_s", "s"),
        ("Taxa de Geração (Tokens/s)", "throughput_tokens_seg", " tok/s"),
    ]:
        v1 = f"{resultados_finais[m1]['resumo'][chave]}{unidade}" if m1 in resultados_finais else "N/A"
        v2 = f"{resultados_finais[m2]['resumo'][chave]}{unidade}" if m2 in resultados_finais else "N/A"
        print(f"{rotulo:<35} | {v1:<15} | {v2:<15}")
    print("=================================================================")
    print(f"Resultados completos salvos em: {CAMINHO_OUTPUT}")


if __name__ == "__main__":
    executar_benchmark()
