# Fraud Sentinel

Fraud Sentinel, e-ticaret platformlarındaki ödeme ve işlem verilerini gerçek zamanlı analiz eden, şüpheli hareketleri işaretleyen, operasyon ekiplerine canlı görünürlük sağlayan ve aynı verileri MCP üzerinden yapay zeka ajanlarına açan bir izleme platformudur.

## Amaç ve Kapsam

- REST API üzerinden gelen ham işlem verilerini kuyruğa alır.
- Worker servisi kullanıcı bazlı state/cache yönetimiyle fraud kontrolü yapar.
- Sonuçları PostgreSQL'e kaydeder, API servisine bildirim olarak yollar.
- React paneli canlı akış, trend grafikleri, uyarılar ve kullanıcı detay ekranı sunar.
- MCP server, `get_recent_frauds` ve `check_user_status` tool'larını dışa açar.

## Mimari

Projede Python tabanlı 3 servisli bir microservice yaklaşımı kullanılır:

- `api`: FastAPI ile REST endpoint'leri ve SSE canlı veri yayını sunar.
- `worker`: RabbitMQ kuyruğundan ham işlemleri tüketir, Redis tabanlı state yönetimiyle fraud analizi yapar.
- `mcp`: MCP Python SDK ile AI ajanlarına fraud araçları açar.
- `frontend`: React + Recharts ile dashboard sunar.
- `postgres`: işlem geçmişi ve sorgulanabilir kayıtlar.
- `redis`: kullanıcı bazlı son işlem ve 24 saatlik hafıza.
- `rabbitmq`: ham işlem kuyruğu ve işlenmiş bildirim akışı.

Akış:

1. İstemci `POST /transactions` ile işlemi API'ye gönderir.
2. API veriyi `raw-transactions` kuyruğuna yazar.
3. Worker veriyi tüketir, velocity/amount/location kurallarını değerlendirir.
4. Sonuç PostgreSQL'e kaydedilir ve `processed-transactions` kuyruğuna bildirim atılır.
5. API bu kuyruğu dinleyerek SSE üzerinden frontend'i günceller.
6. Aynı veriler API endpoint'leri ve MCP tool'ları ile dışa açılır.

## Teknoloji Seçimleri ve Gerekçeler

- `FastAPI`: hızlı REST geliştirme, type-safe schema üretimi ve SSE desteği için.
- `RabbitMQ`: kuyruklama ihtiyacını düşük operasyonel maliyetle karşılamak için.
- `PostgreSQL`: işlem geçmişi, filtreleme ve fraud raporları için güçlü sorgu desteği nedeniyle.
- `Redis`: kullanıcı bazlı anlık fraud state kontrolünü hızlı yapmak için.
- `React + Recharts`: canlı dashboard ve zaman serisi görselleştirmesi için.
- `MCP Python SDK`: resmi SDK ile streamable HTTP üzerinden tool yayını yapmak için.

Cache yönetimi kararı:

- Son 24 saatlik kullanıcı geçmişi Redis sorted set içinde tutulur.
- Son işlem zamanı/lokasyonu Redis hash ile saklanır.
- Böylece velocity, 24s ortalama tutar ve son lokasyon kontrolleri worker tarafında düşük gecikmeyle yapılır.
- Kalıcı raporlama için nihai durum yine PostgreSQL'e yazılır.

## Anomali Tespiti Kuralları

Bir işlem aşağıdaki ihlallerden en az ikisini aynı anda sağlarsa `suspicious` kabul edilir:

- `Velocity`: son 1 dakikada 5'ten fazla işlem.
- `Amount`: işlem tutarı, kullanıcının son 24 saatteki ortalama tutarının 3 katından fazla.
- `Location`: ardışık iki işlem arasındaki sürede fiziksel olarak imkansız lokasyon geçişi.

## Kurulum

### Gereksinimler

- Docker
- Docker Compose

### Tek Komutla Başlatma

```bash
docker compose up --build
```

Servisler:

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- MCP: `http://localhost:9000/mcp`
- RabbitMQ UI: `http://localhost:15672` (`guest/guest`)

## Kullanım Rehberi

### Manuel veri girişi

```bash
./manual-input.sh user-001 1250 Istanbul
```

PowerShell:

```powershell
./manual-input.ps1 user-001 1250 Istanbul
```

### Otomatik test

```bash
./auto-test.sh --duration=45 --rate=8 --anomaly-chance=35
```

PowerShell:

```powershell
./auto-test.ps1 --duration 45 --rate 8 --anomaly-chance 35
```

## API Dokümantasyonu

### `POST /transactions`

İşlemi analize göndermek için kullanılır.

Örnek payload:

```json
{
  "user_id": "user-001",
  "amount": 1250,
  "location": "Istanbul",
  "occurred_at": "2026-04-27T12:34:56Z"
}
```

### `GET /users/{user_id}/status`

Kullanıcının son işlemlerini, risk seviyesini ve 24 saatlik özetini döner.

### `GET /frauds?start=<iso>&end=<iso>&limit=200`

Belirli bir zaman aralığındaki şüpheli işlemleri listeler.

### `GET /transactions/recent?limit=20`

Dashboard başlangıç canlı akışını doldurur.

### `GET /metrics/fraud-trend?hours=24&bucket_minutes=15`

Fraud oranını zaman serisi olarak döner.

### `GET /stream/events`

Server-Sent Events akışı. `transaction_processed` ve `fraud_alert` event tiplerini üretir.

## MCP Dokümantasyonu

MCP endpoint:

```text
http://localhost:9000/mcp
```

Yayınlanan tool'lar:

- `get_recent_frauds(limit=10, minutes=60)`
- `check_user_status(user_id, limit=20)`

### MCP test yöntemi

MCP Inspector ile test edebilirsiniz:

```bash
npx -y @modelcontextprotocol/inspector
```

Inspector içinde `http://localhost:9000/mcp` adresine bağlanıp tool'ları çağırın.

## Frontend Özellikleri

- Onaylanan ve şüpheli işlemler için canlı akış listesi
- Zaman bazlı fraud oranı grafiği
- Anlık uyarı paneli
- Kullanıcı bazlı detay analizi ve işlem geçmişi
- Responsive dashboard düzeni

## Script Parametreleri

### `auto-test.sh`

- `--duration`: çalışacağı süre, saniye
- `--rate`: saniye başına istek sayısı
- `--anomaly-chance`: anomaly üretim yüzdesi
- `--users`: sentetik kullanıcı sayısı
- `--api-base-url`: hedef API adresi

### `manual-input.sh`

- `<user_id>`
- `<amount>`
- `<location>`

İki script de opsiyonel olarak `FRAUD_API_BASE_URL` ortam değişkenini kullanabilir.

## Sorun Giderme

- Frontend açılıyor ama veri yoksa `docker compose logs worker api` ile kuyruk ve SSE akışını kontrol edin.
- RabbitMQ erişilemiyorsa `http://localhost:15672` üzerinden servis durumunu doğrulayın.
- İşlemler kaydedilmiyorsa PostgreSQL healthcheck tamamlanmadan servislerin başlamadığını doğrulayın.
- MCP client bağlanamıyorsa endpoint'in tam olarak `http://localhost:9000/mcp` olduğuna dikkat edin.

## Teslimat Notu

Bu repo private GitHub deposuna taşınıp `KartacaCandidate` kullanıcısına erişim verilerek paylaşılabilir. Alternatif olarak sıkıştırılmış çıktı alınarak indirilebilir bağlantı üretilebilir.
