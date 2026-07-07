import pandas as pd, csv, re

input_path = "../data/3726.xlsx"
output_path = "2024_ips_por_RA.csv"

df = pd.read_excel(input_path,
                   sheet_name='Dimensões e Componentes 2024',
                   header=None)

# Dados começam na linha 7; col 0 = nome da RA, col 1 = IPS geral
rows = []
for i in range(7, len(df)):
    ra = str(df.iloc[i, 0]).strip()
    ips = df.iloc[i, 1]
    if not ra or ra == 'nan' or ra == 'RIO DE JANEIRO':
        continue
    m = re.match(r'^((?:X{0,3})(?:IX|IV|V?I{0,3}){1,2})\s+(.+)$', ra)
    if not m:
        break
    id_ra = m.group(1)
    nome_ra = m.group(2).title()
    rows.append((id_ra, nome_ra, round(float(ips), 2)))

with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['ID_RA', 'Nome_RA', 'IPS_2024'])
    writer.writerows(rows)

print(f"CSV gerado com {len(rows)} RAs em {output_path}")
print("Obs: XXI Paquetá não consta no dataset de IPS.")