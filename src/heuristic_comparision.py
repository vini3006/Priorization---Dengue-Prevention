import pandas as pd
import pulp
import matplotlib.pyplot as plt
import numpy as np

# --- Caminhos ---
PATH_SAW      = "../data/saw_per_RA.csv"        # tem todos os critérios brutos + normalizados
OUTPUT_DIR    = "../data/outputs"

CUSTO_POR_KM2 = 80_000        # R$/km² — nebulização UBV urbana
ORCAMENTOS    = [50_000_000, 75_000_000, 100_000_000]

# --- Carrega dados (já com SAW e critérios calculados) ---
df = pd.read_csv(PATH_SAW, encoding="utf-8-sig", index_col="Rank")
df["custo"] = (df["area_km2"] * CUSTO_POR_KM2).round(2)

# --- Buffer do relatório em Markdown ---
relatorio = []
relatorio.append("# Comparação MILP vs. Heurísticas — Priorização de Dengue (RJ)\n")
relatorio.append(f"**RAs carregadas:** {len(df)}  ")
relatorio.append(f"**Custo total para cobrir todas as RAs (B_full):** R$ {df['custo'].sum():,.0f}\n")

print(f"RAs carregadas: {len(df)}")
print(f"Custo total para cobrir todas as RAs: R$ {df['custo'].sum():,.0f}\n")


# ==========================================================
# 1) MILP — solução ótima
# ==========================================================
def resolver_milp(df, B):

    I = df["Nome_RA"].tolist()
    S = dict(zip(df["Nome_RA"], df["SAW"]))
    C = dict(zip(df["Nome_RA"], df["custo"]))

    prob = pulp.LpProblem(f"Dengue_MILP_B{B//1_000_000}M", pulp.LpMaximize)   # Problema de otimização
    X = {nome: pulp.LpVariable(f"x_{nome}", cat="Binary") for nome in I}      # Variável de decisão binária
    prob += pulp.lpSum(S[nome] * X[nome] for nome in I)                       # Função objetivo: maximizar SAW total
    prob += pulp.lpSum(C[nome] * X[nome] for nome in I) <= B                  # Restrição de orçamento: custo total <= B
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # Verifica se o solver realmente achou solução ótima antes de seguir

    if pulp.LpStatus[prob.status] != "Optimal":
        print(f"  [AVISO] MILP não encontrou solução ótima para B=R${B/1e6:.0f}M "
              f"(status: {pulp.LpStatus[prob.status]})")
        return None

    selecionadas = [
        nome for nome in I
        if X[nome].value() is not None and X[nome].value() > 0.5
    ]
    df_sel = df[df["Nome_RA"].isin(selecionadas)]

    return {
        "metodo":             "MILP",
        "selecionadas":       sorted(selecionadas),
        "n":                  len(selecionadas),
        "custo_total":        round(sum(C[nome] for nome in selecionadas), 2),
        "saw_total":          round(sum(S[nome] for nome in selecionadas), 4),
        "casos_beneficiados": df_sel["casos_absolutos"].sum(),
        "pop_beneficiada":    df_sel["Populacao_2022"].sum(),
    }


# ==========================================================
# 2) Heurísticas gulosas de critério único (H1–H4)
#    Ordena pelo critério isolado (desc) e seleciona até estourar o orçamento
# ==========================================================
HEURISTICAS = {
    "H1_CasosAbsolutos": "casos_absolutos",
    "H2_CasosRelativos": "casos_relativos",
    "H3_Populacao":      "Populacao_2022",
    "H4_Vulnerabilidade": "norm_ips",   # já é 1 - minmax(IPS), então "maior = mais vulnerável"
}

def resolver_heuristica(df, criterio, B):
    """
    Heurística gulosa: ordena por `criterio` descendente e vai testando
    cada RA na ordem. Não há break -- RAs mais baratas mais abaixo na lista
    ainda são testadas, mesmo que uma mais cara acima tenha sido pulada.
    """
    ordenado = df.sort_values(criterio, ascending=False)
 
    nomes_selecionados, custo_acum = [], 0.0
    for i in ordenado.index:
        custo_i = ordenado.loc[i, "custo"]
        if custo_acum + custo_i <= B:
            nomes_selecionados.append(ordenado.loc[i, "Nome_RA"])
            custo_acum += custo_i
 
    df_sel = df[df["Nome_RA"].isin(nomes_selecionados)]
 
    return {
        "selecionadas":       nomes_selecionados,
        "n":                  len(nomes_selecionados),
        "custo_total":        round(custo_acum, 2),
        "saw_total":          round(df_sel["SAW"].sum(), 4),
        "casos_beneficiados": df_sel["casos_absolutos"].sum(),
        "pop_beneficiada":    df_sel["Populacao_2022"].sum(),
    }

# ==========================================================
# 2.5) Métricas de comparação: Jaccard e ganho percentual
# ==========================================================

def jaccard(set_a, set_b):
    """Similaridade de Jaccard entre dois conjuntos de RAs."""
    a, b = set(set_a), set(set_b)
    uniao = a | b
    if not uniao:
        return np.nan
    return len(a & b) / len(uniao)
 
 
def pct_gain(valor_milp, valor_base):
    """Ganho percentual do MILP sobre a heurística."""
    if pd.isna(valor_base) or valor_base == 0:
        return np.nan
    return (valor_milp - valor_base) / valor_base * 100

# ==========================================================
# 3) Rodar tudo para os 3 cenários de orçamento
# ==========================================================
resultados = {} 

for B in ORCAMENTOS:
    resultados[B] = {}

    milp_res = resolver_milp(df, B)

    # Checa se o MILP encontrou solução viável antes de seguir

    if milp_res is None:
        print(f"Orçamento R$ {B/1e6:.0f}M: MILP inviável, cenário pulado.")
        relatorio.append(f"\n## Orçamento: R$ {B/1e6:.0f}M\n")
        relatorio.append("_MILP não encontrou solução ótima — cenário pulado._\n")
        continue

    
    resultados[B]["MILP"] = milp_res

    for nome_h, criterio in HEURISTICAS.items():
        resultados[B][nome_h] = resolver_heuristica(df, criterio, B)

    # --- Jaccard e ganho % de cada heurística em relação ao MILP ---
    for nome_h in HEURISTICAS:
        res_h = resultados[B][nome_h]
        resultados[B][nome_h]["jaccard_vs_milp"] = jaccard(
            milp_res["selecionadas"], res_h["selecionadas"]
        )
        resultados[B][nome_h]["ganho_pct_milp"] = pct_gain(
            milp_res["saw_total"], res_h["saw_total"]
        )

        # Ganho % também sobre o impacto real (casos de dengue cobertos), não só sobre o SAW abstrato
        resultados[B][nome_h]["ganho_pct_casos_milp"] = pct_gain(
            milp_res["casos_beneficiados"], res_h["casos_beneficiados"]
        )

  
    resultados[B]["MILP"]["jaccard_vs_milp"] = 1.0   # MILP vs. ele mesmo
    resultados[B]["MILP"]["ganho_pct_milp"] = 0.0
    resultados[B]["MILP"]["ganho_pct_casos_milp"] = 0.0

    print(f"Orçamento R$ {B/1e6:.0f}M processado.")

    # --- Monta a tabela em Markdown para este orçamento ---
    relatorio.append(f"\n## Orçamento: R$ {B/1e6:.0f}M\n")
    relatorio.append(
        "| Método | RAs | SAW total | Custo usado (R$M) | Jaccard vs. MILP | "
        "Ganho % MILP (SAW) | Ganho % MILP (casos) |"
    )
    relatorio.append(
        "|---|---:|---:|---:|---:|---:|---:|"
    )
    for metodo, res in resultados[B].items():
        nome_exibicao = "**MILP**" if metodo == "MILP" else metodo
        relatorio.append(
            f"| {nome_exibicao} | {res['n']} | {res['saw_total']:.4f} | "
            f"{res['custo_total']/1e6:.2f} | {res['jaccard_vs_milp']:.2f} | "
            f"{res['ganho_pct_milp']:+.1f}% | {res['ganho_pct_casos_milp']:+.1f}% |"
        )

# ==========================================================
# 4) Gráfico comparativo
# ==========================================================
metodos_ordem = ["MILP"] + list(HEURISTICAS.keys())
cores = ["#1565C0", "#E53935", "#FB8C00", "#43A047", "#8E24AA"]

fig, axes = plt.subplots(1, 3, figsize=(18, 6))
fig.suptitle(
    "MILP vs. Heurísticas de Critério Único — SAW Total por Cenário de Orçamento\n"
    "Priorização de RAs para controle de dengue (RJ)",
    fontsize=13, fontweight="bold", y=1.03
)

for ax, B in zip(axes, ORCAMENTOS):
    if B not in resultados or not resultados[B]:
        ax.set_title(f"Orçamento: R$ {B/1e6:.0f}M\n(MILP inviável)", fontsize=10)
        ax.axis("off")
        continue
    
    valores = [resultados[B][m]["saw_total"] for m in metodos_ordem]
    bars = ax.bar(metodos_ordem, valores, color=cores, edgecolor="white")
    ax.set_title(f"Orçamento: R$ {B/1e6:.0f}M", fontsize=11, fontweight="bold")
    ax.set_ylabel("SAW total (Σ)", fontsize=9)
    ax.set_xticklabels(metodos_ordem, rotation=30, ha="right", fontsize=8)
    ax.set_ylim(0, max(valores) * 1.25)
    ax.spines[["top", "right"]].set_visible(False)
    for bar, v in zip(bars, valores):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.02,
                f"{v:.3f}", ha="center", fontsize=9, fontweight="bold")

plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/milp_vs_heuristicas_dengue.png", dpi=150, bbox_inches="tight")
plt.close()

print(f"\nGráfico salvo em: {OUTPUT_DIR}/milp_vs_heuristicas_dengue.png")

# ==========================================================
# 5) Exporta tabela resumo
# ==========================================================
linhas = []
for B in ORCAMENTOS:
    if B not in resultados or not resultados[B]:
        continue 
    for metodo in metodos_ordem:
        res = resultados[B][metodo]
        linhas.append({
            "Orcamento_RS": B,
            "Metodo": metodo,
            "N_RAs": res["n"],
            "SAW_total": res["saw_total"],
            "Custo_usado_RS": round(res["custo_total"], 2),
            "Uso_orcamento_pct": round(100 * res["custo_total"] / B, 1),
            "Jaccard_vs_MILP": round(res["jaccard_vs_milp"], 3),
            "Ganho_pct_MILP": round(res["ganho_pct_milp"], 2),
            "Ganho_pct_Casos_MILP": round(res["ganho_pct_casos_milp"], 2),
        })

tabela = pd.DataFrame(linhas)
tabela.to_csv(f"{OUTPUT_DIR}/tabela_milp_vs_heuristicas.csv", index=False, encoding="utf-8-sig")
print(f"Tabela salva em: {OUTPUT_DIR}/tabela_milp_vs_heuristicas.csv")

# ==========================================================
# 6) Salva o relatório visual em Markdown
# ==========================================================
relatorio.append("\n## Arquivos gerados\n")
relatorio.append(f"- Gráfico: `milp_vs_heuristicas_dengue.png`")
relatorio.append(f"- Tabela completa (CSV): `tabela_milp_vs_heuristicas.csv`\n")
relatorio.append("![Gráfico comparativo](milp_vs_heuristicas_dengue.png)\n")
 
caminho_relatorio = f"{OUTPUT_DIR}/relatorio_milp_vs_heuristicas.md"
with open(caminho_relatorio, "w", encoding="utf-8") as f:
    f.write("\n".join(relatorio))
 
print(f"Relatório salvo em: {caminho_relatorio}")