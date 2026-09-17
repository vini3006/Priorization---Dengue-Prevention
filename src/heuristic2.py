import time
import pandas as pd
import pulp
import matplotlib.pyplot as plt
import numpy as np
from config import CUSTO_POR_KM2

PATH_SAW   = "../data/saw_per_RA.csv"
OUTPUT_DIR = "../data/outputs"

ORCAMENTOS = [20_000_000, 40_000_000, 60_000_000, 80_000_000, 100_000_000]

# --- Carrega dados (já com SAW e critérios brutos calculados) ---
df = pd.read_csv(PATH_SAW, encoding="utf-8-sig", index_col="Rank")
df["custo"] = (df["area_km2"] * CUSTO_POR_KM2).round(2)

print(f"RAs carregadas: {len(df)}")
print(f"Custo total para cobrir todas as RAs: R$ {df['custo'].sum():,.0f}\n")

# ==========================================================
# Funções objetivo (FO): os 4 critérios isolados + a FO agregada
# (SAW, que já combina os 4 com peso 0.25 cada)
# ==========================================================
FUNCOES_OBJETIVO = {
    "C1_CasosAbsolutos":  "casos_absolutos",
    "C2_CasosRelativos":  "casos_relativos",
    "C3_Populacao":       "Populacao_2022",
    "C4_Vulnerabilidade": "norm_ips",
    "FO_Agregada_SAW":    "SAW",
}


# ==========================================================
# 1) MILP — maximiza a soma de `valor_col` sob restrição de orçamento
#    `valor_col` pode ser qualquer critério isolado (C1-C4) ou a FO
#    agregada (SAW). Isso permite comparar MILP e heurística usando
#    exatamente a mesma função objetivo -- comparação justa.
# ==========================================================
def resolver_milp(df, B, valor_col):
    I = df["Nome_RA"].tolist()
    V = dict(zip(df["Nome_RA"], df[valor_col]))
    C = dict(zip(df["Nome_RA"], df["custo"]))

    prob = pulp.LpProblem(f"Dengue_MILP_{valor_col}", pulp.LpMaximize)
    X = {nome: pulp.LpVariable(f"x_{nome}", cat="Binary") for nome in I}
    prob += pulp.lpSum(V[nome] * X[nome] for nome in I)
    prob += pulp.lpSum(C[nome] * X[nome] for nome in I) <= B
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    if pulp.LpStatus[prob.status] != "Optimal":
        print(f"  [AVISO] MILP inviável para B=R${B/1e6:.0f}M, FO={valor_col}")
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
        "valor_fo_total":     round(sum(V[nome] for nome in selecionadas), 4),
        "casos_beneficiados": df_sel["casos_absolutos"].sum(),
        "pop_beneficiada":    df_sel["Populacao_2022"].sum(),
    }


# ==========================================================
# 2) Heurística gulosa — ordena por `valor_col` (a mesma FO do MILP
#    naquele cenário) e inclui cada RA que ainda cabe no orçamento.
# ==========================================================
def resolver_heuristica(df, valor_col, B):
    ordenado = df.sort_values(valor_col, ascending=False)

    nomes_sel, custo_acum, valor_acum = [], 0.0, 0.0
    for i in ordenado.index:
        custo_i = ordenado.loc[i, "custo"]
        if custo_acum + custo_i <= B:
            nomes_sel.append(ordenado.loc[i, "Nome_RA"])
            custo_acum += custo_i
            valor_acum += ordenado.loc[i, valor_col]

    df_sel = df[df["Nome_RA"].isin(nomes_sel)]

    return {
        "metodo":             "Heuristica_Gulosa",
        "selecionadas":       sorted(nomes_sel),
        "n":                  len(nomes_sel),
        "custo_total":        round(custo_acum, 2),
        "valor_fo_total":     round(valor_acum, 4),
        "casos_beneficiados": df_sel["casos_absolutos"].sum(),
        "pop_beneficiada":    df_sel["Populacao_2022"].sum(),
    }


# ==========================================================
# 3) Métricas de comparação
# ==========================================================
def jaccard(set_a, set_b):
    a, b = set(set_a), set(set_b)
    uniao = a | b
    if not uniao:
        return np.nan
    return len(a & b) / len(uniao)


def pct_gain(valor_milp, valor_base):
    if pd.isna(valor_base) or valor_base == 0:
        return np.nan
    return (valor_milp - valor_base) / valor_base * 100


# ==========================================================
# 4) Roda MILP e Heurística para cada (orçamento x função objetivo),
#    medindo tempo computacional de cada execução
# ==========================================================

# Rótulo de "Estudo de Caso" (EC1-EC5) para cada FO, aplicado às linhas do MILP
ESTUDOS_DE_CASO = {nome_fo: f"EC{i+1}" for i, nome_fo in enumerate(FUNCOES_OBJETIVO)}
 
linhas = []
linhas_ras = []  # registra, para cada cenário, quais RAs foram selecionadas

for B in ORCAMENTOS:
    for nome_fo, col in FUNCOES_OBJETIVO.items():

        t0 = time.perf_counter()
        milp_res = resolver_milp(df, B, col)
        tempo_milp = time.perf_counter() - t0

        t0 = time.perf_counter()
        heur_res = resolver_heuristica(df, col, B)
        tempo_heur = time.perf_counter() - t0

        if milp_res is None:
            continue

        jac    = jaccard(milp_res["selecionadas"], heur_res["selecionadas"])
        ganho  = pct_gain(milp_res["valor_fo_total"], heur_res["valor_fo_total"])
        ganho_casos = pct_gain(milp_res["casos_beneficiados"], heur_res["casos_beneficiados"])

        for res, tempo, eh_milp in [(milp_res, tempo_milp, True), (heur_res, tempo_heur, False)]:

            estudo_de_caso = ESTUDOS_DE_CASO[nome_fo] if eh_milp else ""
            linhas.append({
                "Orcamento_RS":          B,
                "Estudo_de_Caso":        estudo_de_caso,
                "FO":                    nome_fo,
                "Metodo":                res["metodo"],
                "N_RAs":                 res["n"],
                "Valor_FO_total":        res["valor_fo_total"],
                "Custo_usado_RS":        res["custo_total"],
                "Uso_orcamento_pct":     round(100 * res["custo_total"] / B, 1),
                "Casos_beneficiados":    res["casos_beneficiados"],
                "Pop_beneficiada":       res["pop_beneficiada"],
                "Tempo_computacional_s": round(tempo, 6),
                "Jaccard_vs_MILP":       1.0 if eh_milp else round(jac, 3),
                "Ganho_pct_MILP_FO":     0.0 if eh_milp else round(ganho, 2),
                "Ganho_pct_MILP_Casos":  0.0 if eh_milp else round(ganho_casos, 2),
            })

             # --- registra quais RAs foram atendidas nesse cenário ---
            for nome_ra in res["selecionadas"]:
                linhas_ras.append({
                    "Orcamento_RS":   B,
                    "Estudo_de_Caso": estudo_de_caso,
                    "FO":             nome_fo,
                    "Metodo":         res["metodo"],
                    "Nome_RA":        nome_ra,
                })

    print(f"Orçamento R$ {B/1e6:.0f}M processado ({len(FUNCOES_OBJETIVO)} funções objetivo).")

tabela = pd.DataFrame(linhas)
tabela_ras = pd.DataFrame(linhas_ras)

# ==========================================================
# 5) Exporta tabela completa
# ==========================================================
caminho_csv = f"{OUTPUT_DIR}/tabela_milp_vs_heuristica_por_fo.csv"
tabela.to_csv(caminho_csv, index=False, encoding="utf-8-sig")

# 5.1) Tabela simplificada solicitada pela professora:
#      Método, Critério (FO), Valor da FO, Nº de RAs, Tempo computacional
# ==========================================================
tabela_simplificada = tabela[[
    "Orcamento_RS", "Estudo_de_Caso", "Metodo", "FO",
    "Valor_FO_total", "N_RAs", "Tempo_computacional_s"
]].rename(columns={
    "FO": "Criterio",
    "Valor_FO_total": "FO_valor",
})

caminho_simplificada = f"{OUTPUT_DIR}/tabela_metodo_criterio_tempo.csv"
tabela_simplificada.to_csv(caminho_simplificada, index=False, encoding="utf-8-sig")

# ==========================================================
# 5.2) Tabela de RAs atendidas em cada cenário
#      (Orçamento x Estudo de Caso/Critério x Método -> quais RAs)
#      -- mantida só a versão em matriz (Excel); o formato longo é
#      usado apenas como estrutura intermediária, sem ser exportado.
# ==========================================================
caminho_ras_matriz = f"{OUTPUT_DIR}/ras_atendidas_matriz.xlsx"
with pd.ExcelWriter(caminho_ras_matriz) as writer:
    for B in ORCAMENTOS:
        sub = tabela_ras[tabela_ras["Orcamento_RS"] == B].copy()
        if sub.empty:
            continue
        sub["Cenario"] = sub["Metodo"].where(sub["Metodo"] != "MILP", sub["Estudo_de_Caso"]) \
            + " (" + sub["FO"] + ")"
        matriz = (
            sub.pivot_table(index="Nome_RA", columns="Cenario", values="Orcamento_RS",
                             aggfunc=lambda x: 1, fill_value=0)
        )
        matriz.to_excel(writer, sheet_name=f"{int(B/1e6)}M")

# ==========================================================
# 6) Resumo de tempo computacional
#    (a) tempo médio por FO e método -- MILP-SAW, MILP por critério
#        isolado (C1-C4), e cada heurística isolada
#    (b) tempo TOTAL da heurística gulosa rodando os 4 critérios
#        (C1+C2+C3+C4) juntos, por orçamento
# ==========================================================
resumo_tempo = (
    tabela.groupby(["FO", "Metodo"])["Tempo_computacional_s"]
    .mean()
    .unstack()
    .round(6)
)
print("\nTempo computacional médio (segundos) por FO e método:")
print(resumo_tempo.to_string())

caminho_tempo = f"{OUTPUT_DIR}/tempo_computacional_resumo.csv"
resumo_tempo.to_csv(caminho_tempo, encoding="utf-8-sig")

# --- (b) Tempo total das 4 heurísticas isoladas (C1-C4), por orçamento ---
CRITERIOS_ISOLADOS = ["C1_CasosAbsolutos", "C2_CasosRelativos",
                      "C3_Populacao", "C4_Vulnerabilidade"]

tempo_total_heuristicas = (
    tabela[
        (tabela["Metodo"] == "Heuristica_Gulosa") &
        (tabela["FO"].isin(CRITERIOS_ISOLADOS))
    ]
    .groupby("Orcamento_RS")["Tempo_computacional_s"]
    .sum()
    .round(6)
    .rename("Tempo_total_4_heuristicas_s")
)
print("\nTempo TOTAL das 4 heurísticas isoladas (C1+C2+C3+C4), por orçamento:")
print(tempo_total_heuristicas.to_string())

caminho_tempo_total = f"{OUTPUT_DIR}/tempo_total_heuristicas.csv"
tempo_total_heuristicas.to_csv(caminho_tempo_total, encoding="utf-8-sig")

# ==========================================================
# 7) Gráfico: ganho % do MILP sobre a heurística, por FO e orçamento
# ==========================================================
tabela_heur = tabela[tabela["Metodo"] == "Heuristica_Gulosa"]

fig, axes = plt.subplots(1, len(ORCAMENTOS), figsize=(6 * len(ORCAMENTOS), 6), sharey=True)
fig.suptitle(
    "Ganho % do MILP sobre a Heurística Gulosa, por Função Objetivo\n"
    "Priorização de RAs para controle de dengue (RJ)",
    fontsize=13, fontweight="bold"
)

for ax, B in zip(axes, ORCAMENTOS):
    sub = tabela_heur[tabela_heur["Orcamento_RS"] == B]
    bars = ax.bar(sub["FO"], sub["Ganho_pct_MILP_FO"], color="#1565C0", edgecolor="white")
    ax.set_title(f"Orçamento: R$ {B/1e6:.0f}M", fontsize=11, fontweight="bold")
    ax.set_xticklabels(sub["FO"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Ganho % MILP (na própria FO)", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.axhline(0, color="black", linewidth=0.8)
    for bar, v in zip(bars, sub["Ganho_pct_MILP_FO"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                 f"{v:.1f}%", ha="center",
                 va="bottom" if v >= 0 else "top", fontsize=8, fontweight="bold")

plt.tight_layout()
caminho_png = f"{OUTPUT_DIR}/ganho_milp_por_fo.png"
plt.savefig(caminho_png, dpi=150, bbox_inches="tight")
plt.close()

# ==========================================================
# 8) Relatório em Markdown (visual, organizado por orçamento)
# ==========================================================
nomes_fo_exibicao = {
    "C1_CasosAbsolutos":  "C1 — Casos Absolutos",
    "C2_CasosRelativos":  "C2 — Casos Relativos (Incidência)",
    "C3_Populacao":       "C3 — População",
    "C4_Vulnerabilidade": "C4 — Vulnerabilidade (IPS)",
    "FO_Agregada_SAW":    "FO Agregada — SAW (pesos 0,25 cada)",
}
 
relatorio = []
relatorio.append("# Relatório: MILP vs. Heurística Gulosa, por Função Objetivo\n")
relatorio.append(
    "Comparação justa: MILP e heurística otimizam/ordenam pela **mesma** "
    "função objetivo em cada teste.\n"
)
 
# --- 8.1: uma tabela por orçamento, com as 5 FOs e os 2 métodos ---
for B in ORCAMENTOS:
    sub = tabela[tabela["Orcamento_RS"] == B]
    if sub.empty:
        continue
    relatorio.append(f"\n## Orçamento: R$ {B/1e6:.0f}M\n")
    relatorio.append(
        "| EC | FO | Método | RAs | Valor FO | Custo usado (R$M) | Uso (%) | "
        "Casos cobertos | Tempo (s) | Jaccard | Ganho % FO | Ganho % Casos |"
    )
    relatorio.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for nome_fo in FUNCOES_OBJETIVO:
        for metodo, rotulo in [("MILP", "**MILP**"), ("Heuristica_Gulosa", "Heurística")]:
            linha = sub[(sub["FO"] == nome_fo) & (sub["Metodo"] == metodo)]
            if linha.empty:
                continue
            r = linha.iloc[0]
            ec = r["Estudo_de_Caso"] if r["Estudo_de_Caso"] else "—"
            relatorio.append(
                f"| {ec} | {nomes_fo_exibicao[nome_fo]} | {rotulo} | {r['N_RAs']} | "
                f"{r['Valor_FO_total']:.4f} | {r['Custo_usado_RS']/1e6:.2f} | "
                f"{r['Uso_orcamento_pct']:.1f} | {int(r['Casos_beneficiados'])} | "
                f"{r['Tempo_computacional_s']:.4f} | {r['Jaccard_vs_MILP']:.2f} | "
                f"{r['Ganho_pct_MILP_FO']:+.1f}% | {r['Ganho_pct_MILP_Casos']:+.1f}% |"
            )
 
# --- 8.2: resumo de tempo médio por FO, com razão MILP/Heurística ---
relatorio.append("\n## Tabela simplificada: método, critério, FO valor, N_RAs, tempo\n")
relatorio.append("| Orçamento | EC | Método | Critério | FO valor | N_RAs | Tempo (s) |")
relatorio.append("|---|---|---|---|---:|---:|---:|")
for _, r in tabela_simplificada.iterrows():
    ec = r["Estudo_de_Caso"] if r["Estudo_de_Caso"] else "—"
    rotulo_metodo = "**MILP**" if r["Metodo"] == "MILP" else "Heurística"
    relatorio.append(
        f"| R$ {r['Orcamento_RS']/1e6:.0f}M | {ec} | {rotulo_metodo} | "
        f"{nomes_fo_exibicao[r['Criterio']]} | {r['FO_valor']:.4f} | "
        f"{r['N_RAs']} | {r['Tempo_computacional_s']:.4f} |"
    )
 
relatorio.append("\n## Resumo: tempo computacional médio (segundos)\n")
relatorio.append("| EC | FO | MILP (s) | Heurística (s) | MILP é quantas vezes mais lento? |")
relatorio.append("|---|---|---:|---:|---:|")
for nome_fo in FUNCOES_OBJETIVO:
    if nome_fo not in resumo_tempo.index:
        continue
    milp_t = resumo_tempo.loc[nome_fo, "MILP"]
    heur_t = resumo_tempo.loc[nome_fo, "Heuristica_Gulosa"]
    razao = milp_t / heur_t if heur_t > 0 else float("nan")
    relatorio.append(
        f"| {ESTUDOS_DE_CASO[nome_fo]} | {nomes_fo_exibicao[nome_fo]} | "
        f"{milp_t:.4f} | {heur_t:.4f} | {razao:.0f}x |"
    )
 
# --- 8.3: tempo total das 4 heurísticas isoladas, por orçamento ---
relatorio.append("\n## Tempo total das 4 heurísticas (C1+C2+C3+C4), por orçamento\n")
relatorio.append("| Orçamento | Tempo total (s) |")
relatorio.append("|---|---:|")
for B, t in tempo_total_heuristicas.items():
    relatorio.append(f"| R$ {B/1e6:.0f}M | {t:.4f} |")
 
# --- 8.4: RAs atendidas por cenário (uma tabela por orçamento) ---
relatorio.append(
    "\n## RAs atendidas por cenário\n"
    "\nCada célula mostra as RAs selecionadas (nomes) para aquele "
    "Estudo de Caso / heurística, no respectivo orçamento.\n"
)
for B in ORCAMENTOS:
    sub = tabela_ras[tabela_ras["Orcamento_RS"] == B]
    if sub.empty:
        continue
    relatorio.append(f"\n### Orçamento: R$ {B/1e6:.0f}M\n")
    relatorio.append("| EC/Método | FO | RAs atendidas |")
    relatorio.append("|---|---|---|")
    for nome_fo in FUNCOES_OBJETIVO:
        for metodo, rotulo in [("MILP", None), ("Heuristica_Gulosa", "Heurística")]:
            grupo = sub[(sub["FO"] == nome_fo) & (sub["Metodo"] == metodo)]
            if grupo.empty:
                continue
            ec_ou_metodo = ESTUDOS_DE_CASO[nome_fo] if metodo == "MILP" else rotulo
            ras_lista = ", ".join(sorted(grupo["Nome_RA"]))
            relatorio.append(f"| {ec_ou_metodo} | {nomes_fo_exibicao[nome_fo]} | {ras_lista} |")
 
# --- 8.5: arquivos gerados ---
relatorio.append("\n## Arquivos gerados\n")
relatorio.append(f"- Tabela completa (CSV): `tabela_milp_vs_heuristica_por_fo.csv`")
relatorio.append(f"- Tabela simplificada (método/critério/FO/RAs/tempo): `tabela_metodo_criterio_tempo.csv`")
relatorio.append(f"- RAs atendidas (matriz, Excel): `ras_atendidas_matriz.xlsx`")
relatorio.append(f"- Resumo de tempo (CSV): `tempo_computacional_resumo.csv`")
relatorio.append(f"- Gráfico: `ganho_milp_por_fo.png`\n")
relatorio.append("![Gráfico de ganho do MILP por FO](ganho_milp_por_fo.png)\n")
 
caminho_relatorio = f"{OUTPUT_DIR}/relatorio_milp_por_fo.md"
with open(caminho_relatorio, "w", encoding="utf-8") as f:
    f.write("\n".join(relatorio))