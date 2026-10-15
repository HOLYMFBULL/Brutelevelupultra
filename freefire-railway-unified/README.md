# Free Fire Matchmaking Studio (Railway Deployment)

Unified project folder containing:
- Flask Web Dashboard + Background Matchmaking Worker (`main.py`)
- Free Fire Protocol Engine (`engine.py`)
- Opcode mappings (`message_ids.py`)
- Protobuf message schemas (`protos/*.proto`)
- Configs (`accounts.json`, `devices.json`, `users.json`, `token_cache.json`)
- Railway deployment config (`Procfile`, `railway.json`, `requirements.txt`)

## Quick Railway Deployment:
```bash
railway login
railway init
railway up
```
