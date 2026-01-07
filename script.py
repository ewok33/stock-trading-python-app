import requests
import csv
import os
from dotenv import load_dotenv
load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

url = f'https://api.massive.com/v3/reference/tickers?market=stocks&active=true&order=asc&limit=100&sort=ticker&apiKey={POLYGON_API_KEY}'

response = requests.get(url)
tickers = []

# Formatting api data into json
data = response.json()
for ticker in data['results']:
    tickers.append(ticker)

while 'next_url' in data:
    print('requesting next page', data['next_url'])
    respone = requests.get(data['next_url']) + f'&apiKey={POLYGON_API_KEY}'
    data = response.json
    for ticker in data['results']:
        tickers.append(ticker)

example_ticker = {'ticker': 'ACHC', 
    'name': 'Acadia Healthcare Company, Inc.', 
    'market': 'stocks', 
    'locale': 'us', 
    'primary_exchange': 'XNAS', 
    'type': 'CS', 
    'active': True, 
    'currency_name': 'usd', 
    'cik': '0001520697', 
    'composite_figi': 'BBG000FPNN38', 
    'share_class_figi': 'BBG001SNNWL7', 
    'last_updated_utc': '2026-01-05T07:05:44.936863133Z'}


# Writing tickers to csv with example_ticker schema
fieldnames = list(example_ticker.keys())
output_csv = 'ticker.csv'
with open(output_csv, mode = 'w', newline = '', encoding = 'utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for t in tickers():
        row = {key: t.get(key, '') for key in fieldnames}
        writer.writerow(row)
print(f'Wrote {len(tickers)} rows to {output_csv}')



