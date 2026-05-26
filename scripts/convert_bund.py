import pandas as pd
import os

file_name = '2026.5.20BUNDTREUR-M1-No Session.csv'
print(f"Reading {file_name}...")
df = pd.read_csv(file_name)

print("Parsing dates...")
df['timestamp'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Time'])
df['price'] = df['Close']
df['volume'] = df['Volume']

df = df[['timestamp', 'price', 'volume']]

df.set_index('timestamp', inplace=True)
df.sort_index(inplace=True)

print("Splitting into weeks...")
# Group by week (starting on Monday)
week_groups = df.groupby(pd.Grouper(freq='W-MON', closed='left', label='left'))

week_num = 1
for name, group in week_groups:
    if len(group) == 0:
        continue
    filename = f'PULITO_bund_trasformato_week_{week_num}.txt'
    group.to_csv(filename, sep='\t', header=False)
    print(f"Saved {filename} with {len(group)} rows.")
    week_num += 1

print("Done.")
