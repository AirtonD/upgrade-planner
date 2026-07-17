# Plano de Upgrade — requirements.txt (PyPI)
> 8 dependências diretas · 5 vulnerável(is) · 4 com upgrade sugerido · 0 bloqueada(s)

## Onda 1 — Urgente

### boto3 1.29.0 → 1.43.50   [minor]
Move junto:  boto3==1.29.0 exige botocore<1.33.0,>=1.32.0; botocore==1.29.0 exige urllib3<1.27,>=1.25.4; requests==2.28.1 exige urllib3<1.27,>=1.21.1  [PyPI]
Risco:       não avaliado — GROQ_API_KEY ausente  [LLM]
### botocore 1.29.0 → 1.43.50   [minor]
Move junto:  boto3==1.29.0 exige botocore<1.33.0,>=1.32.0; botocore==1.29.0 exige urllib3<1.27,>=1.25.4; requests==2.28.1 exige urllib3<1.27,>=1.21.1  [PyPI]
Risco:       não avaliado — GROQ_API_KEY ausente  [LLM]
### requests 2.28.1 → 2.34.2   [minor]
Por quê:     GHSA-9hjg-9r4m-mvj7, GHSA-9wx4-h78v-vm56 — Requests vulnerable to .netrc credentials leak via malicious URLs  [OSV]
Move junto:  boto3==1.29.0 exige botocore<1.33.0,>=1.32.0; botocore==1.29.0 exige urllib3<1.27,>=1.25.4; requests==2.28.1 exige urllib3<1.27,>=1.21.1  [PyPI]
Risco:       não avaliado — GROQ_API_KEY ausente  [LLM]
### urllib3 1.26.20 → 2.7.0   [major]
Por quê:     GHSA-2xpw-w6gg-jr37, GHSA-38jv-5279-wg99 — urllib3 streaming API improperly handles highly compressed data  [OSV]
Move junto:  boto3==1.29.0 exige botocore<1.33.0,>=1.32.0; botocore==1.29.0 exige urllib3<1.27,>=1.25.4; requests==2.28.1 exige urllib3<1.27,>=1.21.1  [PyPI]
Risco:       não avaliado — GROQ_API_KEY ausente  [LLM]

### fastapi 0.85.0 → 0.139.2   [minor]
Por quê:     PYSEC-2024-38 — FastAPI is a web framework for building APIs with Python 3.8+ based on standard Python type hints. When using form data, `python-multipart` uses a Regular Expression to parse the HTTP `Content-Type` h  [OSV]
Move junto:  fastapi==0.85.0 exige pydantic!=1.7,!=1.7.1,!=1.7.2,!=1.7.3,!=1.8,!=1.8.1,<2.0.0,>=1.6.2  [PyPI]
Risco:       não avaliado — GROQ_API_KEY ausente  [LLM]
### pydantic 1.10.2 → 2.13.4   [major]
Por quê:     GHSA-mr82-8j83-vxmv, PYSEC-2026-1812 — Pydantic regular expression denial of service  [OSV]
Move junto:  fastapi==0.85.0 exige pydantic!=1.7,!=1.7.1,!=1.7.2,!=1.7.3,!=1.8,!=1.8.1,<2.0.0,>=1.6.2  [PyPI]
Risco:       não avaliado — GROQ_API_KEY ausente  [LLM]

### python-dotenv 0.21.1 → 1.2.2   [major]
Por quê:     GHSA-mf9w-mj56-hr94, PYSEC-2026-2270 — python-dotenv: Symlink following in set_key allows arbitrary file overwrite via cross-device rename fallback  [OSV]
Risco:       não avaliado — GROQ_API_KEY ausente  [LLM]

## Onda 2 — Seguro (sem CVE, salto pequeno)

### uvicorn 0.19.0 → 0.51.0   [minor]
Risco:       não avaliado — GROQ_API_KEY ausente  [LLM]
