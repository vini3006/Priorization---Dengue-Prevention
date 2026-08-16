import pandas as pd
import pulp
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from config import CUSTO_POR_KM2

PATH_RANKING = "../data/ranking_saw.csv"
OUTPUT_DIR   = "../data/outputs"

ORCAMENTOS    = [50_000_000, 75_000_000, 100_000_000]

df = pd.read_csv(PATH_RANKING, encoding="utf-8-sig", index_col="Rank")
df["custo"] = (df["area_km2"] * CUSTO_POR_KM2).round(2)

custo_total_cidade = df["custo"].sum()
print(f"Custo para cobrir TODAS as RAs: R$ {custo_total_cidade:,.0f}\n")

print(f"{'RA':<30} {'Área (km²)':>10} {'Custo (R$M)':>12} {'SAW':>6}")
print("-" * 62)
for _, row in df.iterrows():
    print(f"{row['Nome_RA']:<30} {row['area_km2']:>10.2f} "
          f"{row['custo']/1e6:>11.2f}M {row['SAW']:>6.4f}")

resultados = {}

for B in ORCAMENTOS:
    prob = pulp.LpProblem(f"Dengue_B{B//1_000_000}M", pulp.LpMaximize)
    X = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in df.index}
    prob += pulp.lpSum(df.loc[i, "SAW"] * X[i] for i in df.index)
    prob += pulp.lpSum(df.loc[i, "custo"] * X[i] for i in df.index) <= B
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    selecionadas = [i for i in df.index if pulp.value(X[i]) == 1]
    total_custo  = sum(df.loc[i, "custo"] for i in selecionadas)
    total_saw    = sum(df.loc[i, "SAW"]   for i in selecionadas)
    total_area   = sum(df.loc[i, "area_km2"] for i in selecionadas)

    resultados[B] = {
        "status":       pulp.LpStatus[prob.status],
        "selecionadas": selecionadas,
        "n":            len(selecionadas),
        "custo_total":  total_custo,
        "saw_total":    round(total_saw, 4),
        "area_total":   round(total_area, 2),
    }

    print(f"\n{'='*62}")
    print(f"  Orçamento: R$ {B/1e6:.0f}M  |  Status: {pulp.LpStatus[prob.status]}")
    print(f"  RAs selecionadas ({len(selecionadas)}/{len(df)}):")
    for i in selecionadas:
        print(f"    [{df.loc[i,'ID_RA']:>6}] {df.loc[i,'Nome_RA']:<25} "
              f"SAW={df.loc[i,'SAW']:.4f}  "
              f"Custo=R${df.loc[i,'custo']/1e6:>5.2f}M")
    print(f"  Custo total:   R$ {total_custo/1e6:.2f}M  (uso: {100*total_custo/B:.1f}%)")
    print(f"  SAW acumulado: {total_saw:.4f}")
    print(f"  Área coberta:  {total_area:.2f} km²")

# --- Gráfico 1: cobertura por orçamento ---
fig, axes = plt.subplots(1, 3, figsize=(18, 7))
fig.suptitle("Otimização MILP — Dedetização por Carros Nebulizadores (UBV)\n"
             "Rio de Janeiro 2024  |  Custo: R$ 80.000/km²",
             fontsize=13, fontweight="bold", y=1.01)

COR_SEL = "#1565C0"
COR_NAO = "#CFD8DC"

for ax, B in zip(axes, ORCAMENTOS):
    res = resultados[B]
    sel = set(res["selecionadas"])

    nomes = df["Nome_RA"].values
    saws  = df["SAW"].values
    cores = [COR_SEL if i in sel else COR_NAO for i in df.index]

    bars = ax.barh(range(len(df)), saws, color=cores, edgecolor="white", linewidth=0.4)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(nomes, fontsize=7.5)
    ax.invert_yaxis()
    ax.set_xlabel("SAW", fontsize=9)
    ax.set_title(
        f"Orçamento: R$ {B/1e6:.0f}M\n"
        f"{res['n']} RAs cobertas  |  SAW Σ = {res['saw_total']:.2f}\n"
        f"Uso: {100*res['custo_total']/B:.1f}%  |  {res['area_total']:.0f} km²",
        fontsize=8.5)
    ax.set_xlim(0, df["SAW"].max() * 1.22)

    for bar, i in zip(bars, df.index):
        if i in sel:
            ax.text(bar.get_width() + 0.005,
                    bar.get_y() + bar.get_height() / 2,
                    f"R${df.loc[i,'custo']/1e6:.1f}M",
                    va="center", fontsize=6, color="#0D47A1")

patch_sel = mpatches.Patch(color=COR_SEL, label="Selecionada")
patch_nao = mpatches.Patch(color=COR_NAO, label="Não selecionada")
fig.legend(handles=[patch_sel, patch_nao], loc="lower center",
           ncol=2, bbox_to_anchor=(0.5, -0.03), fontsize=10)

plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/milp_cobertura_por_orcamento.png", dpi=150, bbox_inches="tight")
plt.close()

# --- Gráfico 2: comparativo de cenários ---
labels   = [f"R$ {B//1_000_000}M" for B in ORCAMENTOS]
n_ras    = [resultados[B]["n"]          for B in ORCAMENTOS]
saw_acc  = [resultados[B]["saw_total"]  for B in ORCAMENTOS]
area_acc = [resultados[B]["area_total"] for B in ORCAMENTOS]
uso_pct  = [100 * resultados[B]["custo_total"] / B for B in ORCAMENTOS]

x = np.arange(len(labels))
fig, axes = plt.subplots(1, 3, figsize=(14, 5))
fig.suptitle("Comparativo de Cenários de Orçamento — MILP Dengue RJ 2024",
             fontsize=12, fontweight="bold")

configs = [
    (n_ras,    ["#90CAF9","#1E88E5","#0D47A1"], "Nº de RAs",  "RAs Cobertas",          "{:.0f}"),
    (saw_acc,  ["#A5D6A7","#43A047","#1B5E20"], "SAW Σ",      "SAW Acumulado",          "{:.2f}"),
    (area_acc, ["#FFCC80","#FB8C00","#BF360C"], "Área (km²)", "Área Total Coberta (km²)","{:.0f}"),
]

for ax, (vals, cores, ylabel, title, fmt) in zip(axes, configs):
    bars = ax.bar(x, vals, color=cores, width=0.5, edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_ylim(0, max(vals) * 1.22)
    ax.spines[["top","right"]].set_visible(False)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() * 1.03,
                fmt.format(v), ha="center", fontweight="bold", fontsize=11)

plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/milp_comparativo_cenarios.png", dpi=150, bbox_inches="tight")
plt.close()

print("\nGráficos salvos:")
print(f"  {OUTPUT_DIR}/milp_cobertura_por_orcamento.png")
print(f"  {OUTPUT_DIR}/milp_comparativo_cenarios.png")