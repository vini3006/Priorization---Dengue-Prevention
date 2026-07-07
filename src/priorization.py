import pandas as pd

# --- Caminhos dos arquivos ---
PATH_DENGUE = "../data/2024_dengue_cases_per_RA.csv"
PATH_POP    = "../data/2022_population_per_RA.csv"
PATH_IPS    = "../data/2024_ips_per_RA.csv"
PATH_AREA   = "../data/total_area_per_RA.csv"
OUTPUT      = "../data/saw_per_RA.csv"
OUTPUT_RANK = "../data/ranking_saw.csv"

# --- Conversão romano -> inteiro para join com codra ---
def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total, prev = 0, 0
    for ch in reversed(s):
        v = vals[ch]
        total += v if v >= prev else -v
        prev = v
    return total

# --- Carrega os dados ---
dengue = pd.read_csv(PATH_DENGUE,  encoding="utf-8-sig")
pop    = pd.read_csv(PATH_POP,     encoding="utf-8-sig")
ips    = pd.read_csv(PATH_IPS,     encoding="utf-8-sig")
area   = pd.read_csv(PATH_AREA,    encoding="utf-8-sig")[["codra", "st_areashape"]] \
           .rename(columns={"st_areashape": "area_km2"})
area["area_km2"] = (area["area_km2"] / 1e6).round(4)

# --- Join pelos três datasets ---
df = dengue[["ID_RA", "Nome_RA", "Total"]].merge(
         pop[["ID_RA", "Populacao_2022"]], on="ID_RA") \
     .merge(ips[["ID_RA", "IPS_2024"]], on="ID_RA")

# Adiciona codra como inteiro para join com área
df["codra"] = df["ID_RA"].apply(roman_to_int)
df = df.merge(area, on="codra")

# Paquetá (XXI) cai fora aqui pois não tem IPS — ficamos com 32 RAs
print(f"RAs após join: {len(df)}")

# --- Critérios brutos ---
df["casos_absolutos"] = df["Total"]
df["casos_relativos"] = df["Total"] / df["Populacao_2022"]

# --- Normalização min-max ---
def minmax(series):
    return (series - series.min()) / (series.max() - series.min())

df["norm_populacao"]       = minmax(df["Populacao_2022"])
df["norm_casos_absolutos"] = minmax(df["casos_absolutos"])
df["norm_casos_relativos"] = minmax(df["casos_relativos"])
df["norm_ips"]             = 1 - minmax(df["IPS_2024"])   # invertido: IPS alto = menos vulnerável

# --- SAW com pesos iguais (0.25 cada) ---
W = 0.25
df["SAW"] = (W * df["norm_populacao"]
           + W * df["norm_casos_absolutos"]
           + W * df["norm_casos_relativos"]
           + W * df["norm_ips"]).round(4)

# --- Ordenar por SAW decrescente ---
df = df.sort_values("SAW", ascending=False).reset_index(drop=True)
df.index += 1  # ranking começa em 1

# --- CSV completo ---
out_cols = [
    "ID_RA", "Nome_RA", "area_km2",
    "Populacao_2022", "casos_absolutos", "casos_relativos", "IPS_2024",
    "norm_populacao", "norm_casos_absolutos", "norm_casos_relativos", "norm_ips",
    "SAW"
]
df[out_cols].to_csv(OUTPUT, index_label="Rank", encoding="utf-8-sig")

# --- Ranking enxuto para o MILP ---
df[["ID_RA", "Nome_RA", "area_km2", "SAW"]].to_csv(
    OUTPUT_RANK, index_label="Rank", encoding="utf-8-sig")

print(f"\nRanking completo (32 RAs):")
print(df[["ID_RA", "Nome_RA", "area_km2", "SAW"]].to_string())