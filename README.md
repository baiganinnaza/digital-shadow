# Digital Shadow — OSINT/DarkNet Monitoring Platform (MVP)

> АФМ AI Hackathon 2026 · Направление 1 · Команда Digital Shadow

## Быстрый старт

```bash
# 1. Скопировать переменные окружения
cp .env.example .env

# 2. Сгенерировать синтетические данные
cd digital-shadow
python ml/gen_synthetic.py

# 3. Обучить классификатор
python ml/train_classifier.py

# 4. Поднять все сервисы
docker compose up --build -d

# 5. Загрузить seed-данные через полный конвейер
python scripts/seed.py

# 6. Открыть интерфейс аналитика
open http://localhost:5173
```

## Сервисы

| Сервис | URL | Описание |
|---|---|---|
| Frontend | http://localhost:5173 | Дашборд аналитика |
| API | http://localhost:8000 | FastAPI backend |
| API docs | http://localhost:8000/docs | Swagger UI |
| Neo4j Browser | http://localhost:7474 | Граф (neo4j/shadowpass) |

## Структура конвейера

```
seed_posts.jsonl
  → SeedCollector
  → RQ Queue
  → Worker:
      extract.py   (регулярки: BTC/ETH/TRON/@ники/телефоны)
      classifier   (TF-IDF + LogisticRegression, собственная модель)
      resolve.py   (entity resolution → объекты)
      graph.py     (Neo4j: PAYS_TO / LINKED / SAME_AS рёбра)
      rules.py     (риск-скоринг с объяснением reasons[])
  → PostgreSQL
  → FastAPI
  → React + Cytoscape.js
```

## ML-модель

Собственный классификатор (не внешний API):
- **Архитектура:** TF-IDF (char 2-4 gram) + Logistic Regression
- **Задача:** категория (vapes/alcohol/drugs/leak/none) + illegal_sale (binary)
- **Обучение:** синтетический датасет `data/labeled.jsonl`
- **Метрики:** запустить `python ml/eval.py`

## Демо-кластер в seed-данных

В `data/seed_posts.jsonl` заложен кластер:
```
@demo_channel_01 → @demo_user_01, @demo_user_02
           ↓ оба платят на один кошелёк
    bc1qcluster0000000000000000000000000000demo
           ↓ этот кошелёк в blacklist
    → риск-сигнал высокий, граф показывает кластер
```

Cypher-запрос для демо:
```cypher
MATCH p = (o:Object {key:"@demo_user_01"})-[:PAYS_TO|LINKED|SAME_AS*1..3]-(x:Object)
RETURN p
```

## Этические инварианты

- Все данные в seed — синтетические, контакты фейковые
- Нет реального скрапинга даркнет-источников
- Система выдаёт **сигналы**, не вердикты
- Аналитик подтверждает/отклоняет через UI (human-in-loop)
- Каждый факт имеет провенанс: `source`, `collected_at`, `confidence`
- `USE_LOCAL_LLM=false` — внешние LLM не используются

## API

```
GET  /api/health
GET  /api/signals?sort=risk_desc&limit=50
GET  /api/objects/{id}
GET  /api/graph/{object_id}?depth=2
POST /api/cases
POST /api/feedback
POST /api/signals/{id}/dismiss
```
