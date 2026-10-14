import requests
import json
import time

url = 'http://localhost:8000/api/v1/investigations'
claim = 'delhi jantar mantar no longer protest site'
payload = {'claim': claim}

print(f'Submitting claim: {claim}')
r = requests.post(url, json=payload, timeout=300)
print(f'Status: {r.status_code}')
result = r.json()
print(f'Claim ID: {result.get("claim_id")}')

if result.get('claim_id'):
    claim_id = result['claim_id']
    for i in range(30):
        time.sleep(10)
        r2 = requests.get(f'http://localhost:8000/api/v1/investigations/{claim_id}', timeout=30)
        if r2.status_code == 200:
            data = r2.json()
            status = data.get('status')
            print(f'Status: {status}')
            if status == 'completed':
                print('Investigation completed!')
                ov = data.get('overall_verdict', {})
                print(f'Overall verdict: {ov.get("overall_verdict")}')
                print(f'Overall confidence: {ov.get("overall_confidence")}')
                for v in data.get('verification', []):
                    print(f'  Subclaim: {v.get("subclaim_text")}')
                    print(f'  Verdict: {v.get("verdict")}, Confidence: {v.get("confidence")}')
                break
            elif status == 'failed':
                print(f'Failed: {data.get("errors")}')
                break
        else:
            print(f'Error: {r2.status_code}')
            break