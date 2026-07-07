import csv

def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total, prev = 0, 0
    for ch in reversed(s):
        v = vals[ch]
        total += v if v >= prev else -v
        prev = v
    return total

input_path = "../data/484_2022.csv"
output_path = "2022_population_per_RA.csv"

rows = []
with open(input_path, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        ra_full = row["ra"].strip()  # ex: "XXII Anchieta"
        id_ra, nome_ra = ra_full.split(" ", 1)
        pop = row["Populacao Residente/2022"].strip()
        rows.append([id_ra, nome_ra, pop])

# Correção: Ramos está com ID "XX" no arquivo original, mas o codra (10)
# indica que o correto é "X" (XX já pertence à Ilha do Governador)
for row in rows:
    if row[1] == "Ramos" and row[0] == "XX":
        row[0] = "X"

rows.sort(key=lambda r: roman_to_int(r[0]))

with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["ID_RA", "Nome_RA", "Populacao_2022"])
    writer.writerows(rows)

print(f"CSV gerado com {len(rows)} RAs em {output_path}")