# XORA TEAM — Command Center

Free Fire Level Up Bot dengan Web Dashboard real-time.

## Fitur

- Auto Battle Royale & Lone Wolf (level 3+)
- Squad auto-fill (create, invite, accept)
- Anti-AFK otomatis
- Web Dashboard real-time
- Multi-account support
- Auto refresh EXP

## Deploy ke Railway

### Quick Deploy

1. Fork/clone repo ini
2. Buka [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Pilih repo ini
4. Railway auto-detect Python + Procfile
5. Tunggu build selesai (~2 menit)
6. Generate Domain di Settings → Networking
7. Buka URL `.up.railway.app`

### Environment Variables (Railway)

| Variable | Value | Wajib |
|---|---|---|
| `PYTHONUNBUFFERED` | `1` | Ya |
| `PYTHONDONTWRITEBYTECODE` | `1` | Opsional |

Railway otomatis inject `PORT` — **jangan** di-override.

### Persistent Storage (opsional)

Buat Volume di Railway → mount ke `/data`:

1. Tab **Data** → **New Volume**
2. Mount path: `/data`
3. Railway auto-set `RAILWAY_VOLUME_MOUNT_PATH=/data`

Tanpa volume, `token_cache.json` & `accounts.json` hilang tiap restart.

## Struktur
