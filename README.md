# Finance Dashboard (Vite + Netlify Functions)

## 개발 실행
```bash
npm install
npm run dev
```

## 배포(넷틀리파이)
1) 이 폴더를 GitHub에 푸시
2) Netlify → New site from Git → GitHub 저장소 연결
3) Build command: `npm run build`, Publish dir: `dist`, Functions dir: `netlify/functions`
4) Site settings → Build & deploy → Environment → Environment variables → Add **INDEX_CSV** (INDEX 탭의 CSV URL)
5) Deploys → Trigger deploy (재배포)

## 함수 확인
- `/.netlify/functions/sheets-hub`
- `/.netlify/functions/sheets-hub?type=equity`
- `/.netlify/functions/sheets-hub?keys=005930,VIX`
