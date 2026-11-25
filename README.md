# 배움결 Backend

FastAPI, LangGraph, OpenAI Agents SDK 및 Firestore 저장소로 구성된 백엔드입니다.

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

OpenAI와 Firestore 인증 정보는 환경 변수로 주입하며 저장소에 커밋하지 않습니다.

