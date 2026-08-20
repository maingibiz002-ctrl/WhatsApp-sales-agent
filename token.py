import os
import requests

TOKEN = "EAAXzfi8zpiUBSPl9zWEtohpGYCb2861nbPQp5QPaES1JjnoZBCfWLAGMb4bkglrfA1OvTeCBVjZAElIoaE3lpHoZAtRG8VDsx1VHTn3DBTFgd8ES2fBmS3ZBF416GqmJ3BaEwrrWBi0ZAFJ739SX2KGd9MZCkm66ErMi6RK8qWMdnsuSIcvZBAs3GumHnFxSwZDZD"
PHONE_NUMBER_ID = "1337531246105137"

url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}"
headers = {"Authorization": f"Bearer {TOKEN}"}

response = requests.get(url, headers=headers)
print("Status Code:", response.status_code)
print("Response:", response.json())