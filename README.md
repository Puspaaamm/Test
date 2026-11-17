# 🚂 Rail News

White page, beech me rail track, har lakri par ek khabar. Sirf bharosemand sources: BBC, The Hindu, Reuters, ANI, Al Jazeera, NDTV, New York Times, National Geographic.

## Repo me ye files rakho

| File | Repo me kahan |
|------|---------------|
| index.html | root |
| fetch_news.py | root |
| news.json | root (khali starter, Action isse bharega) |
| README.md | root |
| archive/.gitkeep | `archive/.gitkeep` (folder banane ke liye) |
| news.yml | `.github/workflows/news.yml` |

## Setup

1. Settings > Actions > General > Workflow permissions: **Read and write permissions**.
2. Settings > Pages > Build and deployment > Source: **GitHub Actions** ("Deploy from a branch" mat rakho: usme bot ke commit se site rebuild nahi hoti).
3. Actions tab > **Update news** > **Run workflow** ek baar chalao.
4. Run ke andar "Deploy to GitHub Pages" step hara hona chahiye. Site `https://<username>.github.io/<repo>/` par khulegi.

## 3 mahine ka archive

- Har khabar `archive/YYYY-MM-DD.json` me din ke hisaab se jama hoti hai. Koi khabar delete nahi hoti.
- Sirf 92 din (3 mahine) se purani din-files hi hatai jaati hain (`RETENTION_DAYS` in `fetch_news.py`).
- `news.json` sirf fehrist (din ki list + source status) hai.
- Page pehle aaj ki khabrein dikhata hai, neeche scroll karne par pichhle dinon ki khabrein archive se aati jaati hain. Sab khatam hone par "3 mahine ki khabrein yahin tak" likha aata hai.
- Feeds sirf haal ki khabrein deti hain, isliye archive aaj se bharna shuru hota hai, pichhla itihaas apne aap nahi aata.

## Khabrein kitni jaldi aati hain?

"Har second" GitHub se possible nahi. Action har **5 minute** me chalta hai (GitHub ka minimum, kabhi kabhi thoda late) aur page har **1 minute** me check karke "🆕 नई खबरें आईं" button dikhata hai.

## Capture system

- Saare sources ek saath (parallel), har feed 3 baar retry
- Reuters, ANI aur National Geographic ke liye Google News RSS (site filter)
- Seedhe feeds fail hon to Google News fallback
- Trusted domain check: doosre domain ki khabar hata di jaati hai
- Duplicate khabrein URL aur title se hat jaati hain
- Koi source fail ho to baaki chalte rehte hain; sab fail hon to Action fail dikhata hai
- Sirf nayi khabar aane par commit hota hai

## Local test

```
python fetch_news.py
python -m http.server
```
Phir `http://localhost:8000` kholo.
