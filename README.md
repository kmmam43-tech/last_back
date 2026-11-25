# 배움결 Backend

FastAPI, LangGraph, OpenAI Agents SDK 및 Firestore 저장소로 구성된 백엔드입니다.

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

`App/Api/.env.example`을 `.env`로 복사해 OpenAI, Firestore 및 CORS 값을 설정합니다. 인증 정보는 저장소에 커밋하지 않습니다.

