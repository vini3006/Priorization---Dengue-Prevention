import csv

def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total, prev = 0, 0
    for ch in reversed(s):
        v = vals[ch]
        total += v if v >= prev else -v
        prev = v
    return total

# Dados das Regiões Administrativas (RA) extraídos do PDF
# Formato: (ID_RA, Nome_RA, Jan, Fev, Mar, Abr, Mai, Jun, Jul, Ago, Set, Out, Nov, Dez, Total)
data = [
    ("I", "Portuária", 88, 353, 317, 106, 31, 21, 8, 9, 1, 3, 4, 1, 942),
    ("II", "Centro", 36, 248, 159, 69, 49, 21, 6, 3, 1, 3, 0, 2, 597),
    ("III", "Rio Comprido", 116, 785, 696, 241, 94, 38, 12, 13, 4, 10, 11, 5, 2025),
    ("VII", "São Cristóvão", 134, 925, 775, 195, 106, 49, 16, 14, 12, 14, 17, 13, 2270),
    ("XXI", "Paquetá", 21, 112, 98, 34, 12, 4, 1, 1, 2, 1, 0, 1, 287),
    ("XXIII", "Santa Teresa", 71, 366, 350, 121, 68, 28, 11, 7, 5, 2, 3, 6, 1038),
    ("IV", "Botafogo", 202, 1018, 748, 410, 255, 132, 49, 35, 10, 18, 7, 18, 2902),
    ("V", "Copacabana", 114, 547, 514, 175, 132, 41, 18, 5, 4, 7, 8, 6, 1571),
    ("VI", "Lagoa", 159, 740, 617, 280, 162, 75, 20, 12, 13, 5, 3, 7, 2093),
    ("XXVII", "Rocinha", 112, 536, 274, 136, 91, 16, 12, 3, 1, 0, 7, 6, 1194),
    ("VIII", "Tijuca", 222, 1219, 779, 357, 154, 81, 26, 13, 7, 7, 12, 10, 2887),
    ("IX", "Vila Isabel", 245, 839, 597, 211, 129, 64, 25, 13, 18, 8, 8, 10, 2167),
    ("X", "Ramos", 124, 845, 856, 256, 188, 94, 47, 21, 19, 16, 18, 16, 2500),
    ("XI", "Penha", 211, 1445, 1293, 387, 165, 86, 24, 20, 22, 28, 24, 16, 3721),
    ("XXXI", "Vigário Geral", 23, 175, 191, 77, 13, 10, 5, 1, 1, 1, 3, 3, 503),
    ("XX", "Ilha Do Governador", 89, 1477, 1694, 289, 105, 62, 22, 24, 21, 8, 10, 8, 3809),
    ("XXIX", "Complexo do Alemão", 41, 1401, 824, 30, 19, 5, 8, 2, 1, 0, 0, 1, 2332),
    ("XXX", "Maré", 44, 290, 251, 122, 46, 36, 11, 6, 6, 7, 5, 2, 826),
    ("XII", "Inhaúma", 228, 1261, 1039, 328, 189, 109, 40, 40, 14, 27, 15, 16, 3306),
    ("XIII", "Méier", 427, 1672, 1467, 458, 263, 125, 60, 41, 42, 41, 41, 38, 4675),
    ("XXVIII", "Jacarezinho", 4, 33, 35, 10, 4, 0, 0, 0, 0, 0, 2, 2, 90),
    ("XIV", "Irajá", 185, 877, 646, 219, 120, 75, 34, 31, 23, 23, 26, 30, 2289),
    ("XV", "Madureira", 298, 1939, 1464, 379, 156, 108, 55, 31, 27, 25, 31, 37, 4550),
    ("XXII", "Anchieta", 210, 645, 523, 134, 51, 32, 16, 10, 15, 7, 10, 19, 1672),
    ("XXV", "Pavuna", 172, 726, 638, 147, 62, 35, 18, 10, 8, 9, 10, 10, 1845),
    ("XVI", "Jacarepaguá", 627, 2947, 2358, 868, 613, 303, 105, 53, 55, 59, 73, 27, 8088),
    ("XXXIV", "Cidade De Deus", 24, 124, 105, 20, 18, 9, 8, 2, 3, 3, 1, 0, 317),
    ("XXIV", "Barra Da Tijuca", 455, 1572, 1263, 761, 368, 167, 88, 34, 43, 43, 32, 16, 4842),
    ("XXXIII", "Realengo", 208, 1166, 877, 278, 138, 77, 39, 30, 15, 21, 22, 22, 2893),
    ("XVII", "Bangu", 385, 2078, 1617, 587, 354, 149, 95, 52, 67, 46, 55, 41, 5526),
    ("XVIII", "Campo Grande", 1436, 5461, 3632, 918, 403, 193, 136, 99, 74, 62, 109, 91, 12614),
    ("XXVI", "Guaratiba", 455, 1360, 950, 427, 220, 104, 72, 31, 26, 25, 32, 26, 3728),
    ("XIX", "Santa Cruz", 1026, 3882, 2567, 849, 222, 62, 42, 27, 26, 36, 37, 32, 8808),
]

data.sort(key=lambda r: roman_to_int(r[0]))

header = ["ID_RA", "Nome_RA", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
          "Jul", "Ago", "Set", "Out", "Nov", "Dez", "Total"]

output_path = "2024_dengue_cases_per_RA.csv"
with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(data)

print(f"CSV gerado com {len(data)} RAs em {output_path}")