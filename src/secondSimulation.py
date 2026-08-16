import pandas as pd
import pulp
import matplotlib.pyplot as plt
import numpy as np
from config import CUSTO_POR_KM2

PATH_SAW   = "../data/saw_per_RA.csv"
OUTPUT_DIR = "../data/outputs"

N_ORCAMENTOS  = 20

# --- Carrega dados (já com SAW e critérios brutos calculados) ---
df = pd.read_csv(PATH_SAW, encoding="utf-8-sig", index_col="Rank")
df["custo"] = (df["area_km2"] * CUSTO_POR_KM2).round(2)

# --- Intervalo de orçamento: [custo da RA mais barata, custo de cobrir todas] ---
custo_min = df["custo"].min()
custo_max = df["custo"].sum()
orcamentos = np.linspace(custo_min, custo_max, N_ORCAMENTOS)

print(f"Custo mínimo (1 RA mais barata): R$ {custo_min:,.0f}")
print(f"Custo máximo (todas as RAs):     R$ {custo_max:,.0f}")
print(f"{N_ORCAMENTOS} orçamentos gerados entre os dois limites.\n")


def resolver_milp(df, B):
    I = df["Nome_RA"].tolist()
    S = dict(zip(df["Nome_RA"], df["SAW"]))
    C = dict(zip(df["Nome_RA"], df["custo"]))

    prob = pulp.LpProblem("Dengue_Tradeoff", pulp.LpMaximize)
    X = {nome: pulp.LpVariable(f"x_{nome}", cat="Binary") for nome in I}
    prob += pulp.lpSum(S[nome] * X[nome] for nome in I)
    prob += pulp.lpSum(C[nome] * X[nome] for nome in I) <= B
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    if pulp.LpStatus[prob.status] != "Optimal":
        return None

    selecionadas = [
        nome for nome in I
        if X[nome].value() is not None and X[nome].value() > 0.5
    ]
    df_sel = df[df["Nome_RA"].isin(selecionadas)]

    casos = df_sel["casos_absolutos"].sum()
    pop   = df_sel["Populacao_2022"].sum()
    taxa_relativa = casos / pop if pop > 0 else 0.0

    return {
        "orcamento":       B,
        "n_ras":           len(selecionadas),
        "custo_total":     round(sum(C[nome] for nome in selecionadas), 2),
        "casos_cobertos":  casos,
        "pop_atendida":    pop,
        "casos_relativos": taxa_relativa,
    }


# --- Roda o MILP para os 20 orçamentos ---
resultados = []
for B in orcamentos:
    res = resolver_milp(df, B)
    if res is None:
        print(f"  [AVISO] MILP inviável para B=R${B/1e6:.2f}M — pulado.")
        continue
    resultados.append(res)
    print(f"B=R${B/1e6:6.2f}M -> {res['n_ras']:2d} RAs | "
          f"{res['casos_cobertos']:6.0f} casos | "
          f"{res['pop_atendida']:8.0f} hab | "
          f"taxa={res['casos_relativos']:.5f}")

tabela = pd.DataFrame(resultados)
tabela.to_csv(f"{OUTPUT_DIR}/tradeoff_curve.csv", index=False, encoding="utf-8-sig")
print(f"\nTabela salva em: {OUTPUT_DIR}/tradeoff_curve.csv")

# --- Gráficos: benefício x custo ---
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle(
    "Curva de Trade-off: Benefício x Custo — Priorização de Dengue (RJ)",
    fontsize=13, fontweight="bold"
)

x = tabela["orcamento"] / 1e6

paineis = [
    (axes[0, 0], tabela["n_ras"],           "#1565C0", "Nº de RAs cobertas",              "RAs Cobertas x Custo"),
    (axes[0, 1], tabela["casos_cobertos"],  "#E53935", "Casos de dengue cobertos",         "Casos Absolutos x Custo"),
    (axes[1, 0], tabela["pop_atendida"],    "#43A047", "População atendida",               "População Atendida x Custo"),
    (axes[1, 1], tabela["casos_relativos"], "#FB8C00", "Taxa de casos (casos/população)",  "Casos Relativos x Custo"),
]

for ax, y, cor, ylabel, titulo in paineis:
    ax.plot(x, y, marker="o", color=cor, linewidth=1.8, markersize=4)
    ax.set_xlabel("Orçamento (R$M)", fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(titulo, fontsize=10, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/tradeoff_curve.png", dpi=150, bbox_inches="tight")
plt.close()

print(f"Gráfico salvo em: {OUTPUT_DIR}/tradeoff_curve.png")
