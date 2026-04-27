# Geliştirme Günlüğü

Bu doküman, Fraud Sentinel projesini bu repo içinde sıfırdan nasıl kurduğumuzu, hangi kararları neden aldığımızı, hangi dosyaları eklediğimizi, hangi sorunlarla karşılaşıp nasıl çözdüğümüzü adım adım anlatır.

Yazım tarihi: 27 Nisan 2026

## 1. Başlangıç Durumu

Projeye başladığımızda çalışma dizini fiilen boştu. Hazır bir backend, frontend, docker yapısı veya script yoktu. Bu yüzden geliştirme süreci bir mevcut sistemi düzeltmekten çok, gereksinimlere uygun komple bir çözüm kurma işi olarak ilerledi.

İlk iş olarak şu sorulara cevap verdik:

1. Hangi backend dili ve framework daha hızlı ve temiz bir çözüm sağlar?
2. İsterlerde geçen kuyruk, cache, veritabanı ve MCP gereksinimleri nasıl birbirine bağlanır?
3. Docker ayağa kalkmasa bile projeyi yerelde gösterilebilir halde nasıl tutarız?

## 2. Mimari Kararı

Teknoloji seçimi şu şekilde yapıldı:

1. Backend için `Python + FastAPI` seçildi.
2. Mimari olarak `3 servisli microservice yapı` seçildi.
3. Kuyruk için `RabbitMQ` planlandı.
4. Kalıcı veri için `PostgreSQL` planlandı.
5. Kullanıcı bazlı hızlı state kontrolü için `Redis` planlandı.
6. Frontend için `React + Vite + Recharts` seçildi.
7. MCP için `Python MCP SDK` kullanıldı.

Bu seçimlerin ana nedeni, gereksinimleri kısa sürede temiz biçimde karşılayabilmekti. FastAPI hem REST hem SSE tarafında rahatlık sağladı. React ise dashboard işini hızlı ilerletti. MCP tarafında Python SDK ile doğrudan tool yayınlamak mantıklı oldu.

## 3. Repo İskeletinin Kurulması

Boş klasörde temel proje dizinleri oluşturuldu:

- `backend/`
- `backend/common/`
- `backend/api/`
- `backend/worker/`
- `backend/mcp_server/`
- `frontend/`
- `frontend/src/`
- `scripts/`

Bu yapı ile ortak kodları `backend/common` içinde tutup servislerin kendi giriş noktalarını ayrı klasörlerde topladık.

## 4. Ortak Backend Katmanının Yazılması

Önce tüm servislerin ortak kullanacağı çekirdek yapı yazıldı.

Eklenen temel dosyalar:

- `backend/common/config.py`
- `backend/common/database.py`
- `backend/common/models.py`
- `backend/common/schemas.py`
- `backend/common/location.py`
- `backend/common/fraud.py`
- `backend/common/broker.py`
- `backend/common/repository.py`

Bu dosyaların rolü:

### `config.py`

Uygulamanın tüm ayarları tek yerde toplandı:

- veritabanı bağlantısı
- Redis adresi
- RabbitMQ adresi
- CORS ayarları
- fraud eşik değerleri
- port bilgileri
- demo mod bayrağı

### `database.py`

SQLAlchemy tabanı kuruldu. Burada:

- ortak `Base` tanımı
- `engine`
- `SessionLocal`
- `init_database()`
- dependency olarak kullanılacak `get_db()`

oluşturuldu.

Sonradan ayrıca SQLite demo modunu desteklemek için `check_same_thread=False` eklenerek engine tarafı iyileştirildi.

### `models.py`

Kalıcı transaction modeli yazıldı. Transaction kaydı şu alanları içerir:

- `id`
- `user_id`
- `amount`
- `location`
- `occurred_at`
- `status`
- `reasons`
- `velocity_violation`
- `amount_violation`
- `location_violation`
- `created_at`

Bu model fraud tespitinin nedenlerini hem raporlama hem de UI tarafında gösterebilmek için ayrıntılı tutuldu.

### `schemas.py`

Pydantic şemaları oluşturuldu:

- API input şeması
- API output şemaları
- user status cevabı
- fraud list cevabı
- fraud trend noktaları
- SSE event modeli

Ayrıca tarihlerin UTC normalize edilmesi için yardımcı fonksiyonlar eklendi.

### `location.py`

Lokasyon tabanlı fraud kontrolü için:

- tanımlı şehir koordinatları
- lokasyon normalizasyonu
- haversine mesafe hesabı
- imkansız yolculuk kontrolü

yazıldı.

Bu sayede İstanbul ve Antalya gibi şehirler arasında çok kısa sürede yapılan ardışık işlemler işaretlenebilir hale geldi.

### `fraud.py`

Fraud mantığının asıl çekirdeği burada kuruldu.

İki farklı kullanım yolu hazırlandı:

1. Gerçek mimaride Redis kullanan değerlendirme akışı
2. Demo modunda veritabanı geçmişiyle çalışan yedek değerlendirme akışı

Kontroller:

- velocity kontrolü
- amount kontrolü
- location kontrolü

Kural:

Bir işlemde en az 2 ihlal varsa `suspicious` olarak işaretleniyor.

### `broker.py`

RabbitMQ için ortak publish ve queue declare yardımcıları eklendi.

Sonradan demo modunda RabbitMQ kurulmadan da sistem açılabilsin diye `pika` importu opsiyonel hale getirildi.

### `repository.py`

Sorgu ve özet toplama katmanı yazıldı:

- son işlemler listesi
- fraud işlemler listesi
- kullanıcı geçmişi
- kullanıcı risk özeti
- fraud trend verisi

Bu katman API ve MCP servislerinde veri erişimini sade tuttu.

## 5. API Servisinin Geliştirilmesi

API tarafı için şu ana dosyalar yazıldı:

- `backend/api/main.py`
- `backend/api/events.py`

### API servisinin görevi

1. Ham transaction verisini almak
2. İşlenmiş transaction verisini sunmak
3. Kullanıcı bazlı sorgulara cevap vermek
4. Fraud verilerini listelemek
5. SSE ile canlı bildirim yaymak

### Açılan endpointler

- `GET /health`
- `GET /`
- `POST /transactions`
- `GET /transactions/recent`
- `GET /users/{user_id}/status`
- `GET /frauds`
- `GET /metrics/fraud-trend`
- `GET /meta/locations`
- `GET /stream/events`

### `events.py`

İşlenmiş transaction eventlerini dinleyip frontend tarafına SSE olarak vermek için event manager yazıldı.

Burada:

- aktif subscriber yönetimi
- event history buffer
- queue consumer thread
- SSE broadcast akışı

kuruldu.

### `main.py`

API servisinin ana akışı burada tanımlandı.

Özellikle iki önemli nokta var:

1. Normal modda `POST /transactions` ham veriyi RabbitMQ kuyruğuna yollar.
2. Demo modda aynı endpoint transaction’ı doğrudan işleyip kaydeder ve anında SSE yayını yapar.

Bu ikinci davranış, Docker veya dış servisler ayağa kalkmadığında bile platformu gösterebilmek için sonradan eklendi.

## 6. Worker Servisinin Geliştirilmesi

Worker için ana dosya:

- `backend/worker/main.py`

Worker’ın görevi:

1. `raw-transactions` kuyruğunu dinlemek
2. Redis üzerinden kullanıcı bazlı geçmişi kontrol etmek
3. Fraud değerlendirmesini yapmak
4. Sonucu PostgreSQL’e yazmak
5. `processed-transactions` kuyruğuna event üretmek

Bu servis fraud logic’in asıl üretim akışını temsil ediyor.

Demo modda worker çalıştırmak zorunlu değil çünkü API aynı işi senkron biçimde taklit edebiliyor. Ancak gerçek mimari kurgusu dosya bazında tam yazılmış durumda.

## 7. MCP Servisinin Geliştirilmesi

MCP için ana dosya:

- `backend/mcp_server/main.py`

Burada MCP tool’ları tanımlandı:

- `get_recent_frauds(limit=10, minutes=60)`
- `check_user_status(user_id, limit=20)`

Amaç, AI ajanlarının fraud verisini doğrudan kullanabilmesi.

Servis streamable HTTP mantığıyla kurgulandı ve `/mcp` altına mount edildi.

Ayrıca `GET /health` eklendi ki servis ayağa kalktı mı kolay kontrol edilebilsin.

## 8. Frontend Dashboard’un Yazılması

Frontend tarafında şu temel dosyalar oluşturuldu:

- `frontend/package.json`
- `frontend/index.html`
- `frontend/vite.config.js`
- `frontend/src/main.jsx`
- `frontend/src/App.jsx`
- `frontend/src/styles.css`
- `frontend/Dockerfile`
- `frontend/nginx.conf`

### Dashboard’da yapılan bölümler

1. Üstte genel özet kartları
2. Fraud trend grafiği
3. Anlık alarm paneli
4. Canlı işlem akışı
5. Kullanıcı bazlı detay ekranı

### `App.jsx`

Burada frontend’in tüm veri akışı kuruldu:

- başlangıçta API’den son işlemler çekiliyor
- fraud trend verisi çekiliyor
- son şüpheli işlemler çekiliyor
- kullanıcı detayı yükleniyor
- `EventSource` ile SSE akışına bağlanılıyor
- yeni event gelince ekran dinamik güncelleniyor

### `styles.css`

İsterlerdeki responsive tasarım şartını karşılamak için özel bir görünüm yazıldı.

Seçilen görsel yaklaşım:

- koyu ama tek renk olmayan katmanlı arka plan
- vurgulu alarm renkleri
- kart tabanlı kontrol paneli görünümü
- mobil uyumlu grid yapısı

## 9. Scriptlerin Yazılması

Manuel ve otomatik test scriptleri istendiği için şu dosyalar eklendi:

- `scripts/manual_input.py`
- `scripts/auto_test.py`
- `manual-input.sh`
- `auto-test.sh`
- `manual-input.ps1`
- `auto-test.ps1`

### Manuel input scripti

Bu script kullanıcıdan şu bilgileri alıyor:

- `user_id`
- `amount`
- `location`

ve bunu REST API’ye gönderiyor.

### Otomatik test scripti

Bu script:

- rastgele kullanıcı üretir
- farklı şehirlerden işlem yollar
- belirli olasılıkla anomaly senaryosu üretir
- istekleri rate bazlı gönderir

Kullandığı parametreler:

- `--duration`
- `--rate`
- `--anomaly-chance`
- `--users`
- `--api-base-url`

## 10. Docker ve Dağıtım Dosyalarının Eklenmesi

Dağıtım için şu dosyalar eklendi:

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `.gitignore`

### `docker-compose.yml`

Şu servisler tanımlandı:

- `postgres`
- `redis`
- `rabbitmq`
- `api`
- `worker`
- `mcp`
- `frontend`

Yani isterde geçen tek komutla ayağa kalkabilen çok servisli yapı hazırlandı.

## 11. README’nin Yazılması

Ana kullanım dökümü `README.md` içine yazıldı.

README içinde şunlar bulunuyor:

- proje amacı
- mimari açıklama
- teknoloji seçimleri
- anomaly mantığı
- kurulum
- kullanım örnekleri
- API açıklamaları
- MCP açıklamaları
- script parametreleri
- troubleshooting

Yani teslimatta beklenen ana dokümantasyon iskeleti hazırlandı.

## 12. İlk Doğrulama Adımları

Kod yazıldıktan sonra birkaç temel doğrulama yapıldı:

1. `python -m compileall backend scripts`
2. `docker compose config`
3. `npm install`
4. `npm run build`

Sonuç:

- Python dosyaları derleme kontrolünden geçti
- compose dosyası parse edildi
- frontend dependency kurulumu tamamlandı
- frontend production build başarılı oldu

Bu aşamada frontend bundle boyutuyla ilgili sadece bir uyarı çıktı, ama build başarısız olmadı.

## 13. Docker Tarafında Karşılaşılan Sorun

Projeyi tam stack olarak `docker compose up --build` ile çalıştırmaya çalıştığımızda iki ayrı problemle karşılaştık.

### Problem 1

Başlangıçta Docker daemon kapalıydı.

Yapılan çözüm:

- Docker Desktop başlatıldı
- daemon hazır olana kadar beklendi

### Problem 2

Daemon açıldıktan sonra image pull aşamasında `TLS handshake timeout` hatası alındı.

Bu hata özellikle public registry’den image çekerken çıktı. Sorun proje kodundan çok ağ veya Docker registry erişimi tarafındaydı.

Bu yüzden tam compose stack’i burada zorlayarak zaman kaybetmek yerine, kullanıcıya hızlıca çalışan bir sürüm gösterecek yerel demo stratejisine geçildi.

## 14. Demo Mode Kararı ve Uygulanması

Projeyi incelenebilir hale getirmek için `demo mode` eklendi.

Amaç:

1. RabbitMQ olmadan işlem akışını göstermek
2. Redis olmadan fraud mantığını göstermek
3. PostgreSQL yerine SQLite ile hızlıca ayağa kalkmak
4. Frontend’i canlı veriyle besleyebilmek

Bu karar üzerine şu değişiklikler yapıldı:

- `config.py` içine `demo_mode` eklendi
- `database.py` SQLite destekleyecek şekilde güncellendi
- `broker.py` opsiyonel hale getirildi
- `fraud.py` içine veritabanı geçmişiyle çalışan yedek fraud değerlendirme fonksiyonu eklendi
- `events.py` demo modda queue consumer başlatmayacak hale getirildi
- `api/main.py` demo modda transaction’ı inline işleyip kaydedecek şekilde genişletildi

Bu sayede proje dış bağımlılıklar olmadan da incelenebilir hale geldi.

## 15. Demo Mode İçinde Bulunan Hata ve Çözümü

Demo mod ilk çalıştığında kontrollü fraud senaryosu beklediğimiz gibi `suspicious` çıkmadı.

Yapılan incelemede görüldü ki:

- SQLite tarafında tarih/zaman alanları UTC beklendiği gibi normalize edilmiyordu
- velocity ve location kontrolü yanlış zaman bazında hesaplanıyordu

Çözüm olarak:

- demo mod fraud değerlendirmesinde transaction tarihleri `ensure_utc()` ile normalize edildi
- son transaction zamanı karşılaştırmaları düzeltildi

Bu düzeltmeden sonra aynı senaryo tekrar çalıştırıldı ve fraud kaydı doğru şekilde `suspicious` üretildi.

## 16. Servislerin Yerelde Ayağa Kaldırılması

Tam Docker stack açılamadığı için proje şu şekilde yerelde ayağa kaldırıldı:

1. API, `DEMO_MODE=true` ve `DATABASE_URL=sqlite:///./fraud_sentinel.db` ile başlatıldı
2. Frontend, `VITE_API_BASE_URL=http://localhost:8000` ile başlatıldı
3. API sağlık kontrolü doğrulandı
4. Frontend erişimi doğrulandı

Çalışan adresler:

- `http://localhost:8000`
- `http://localhost:3000`

## 17. Veri Besleme ve Gösterim Amaçlı Seed İşlemleri

Dashboard boş görünmesin diye çeşitli veri besleme adımları uygulandı.

### Otomatik veri akışı

`auto_test.py` ile belirli süre çalışan sentetik trafik gönderildi.

### Kontrollü fraud senaryosu

Özellikle şu kullanıcılar için manuel fraud senaryosu basıldı:

- `user-fraud`
- `user-fraud-2`
- `user-fraud-3`
- `user-fraud-4`

Senaryo mantığı:

1. Aynı kullanıcıya kısa sürede 5 normal işlem
2. Ardından çok yüksek tutarlı bir işlem
3. Aynı anda uzak lokasyon değişimi

Bu şekilde tek işlemde 3 kural birden kırıldı:

- velocity
- amount
- location

Sonuç olarak alarm paneli ve kullanıcı detay ekranında görünür fraud kayıtları oluştu.

## 18. Son Kontroller

Son durumda şunlar doğrulandı:

1. `GET /health` başarılı
2. frontend `200` dönüyor
3. `GET /transactions/recent` veri dönüyor
4. `GET /frauds` şüpheli kayıt dönüyor
5. `GET /users/{user_id}/status` kullanıcı özeti dönüyor
6. `GET /metrics/fraud-trend` grafik verisi dönüyor

Özellikle `user-fraud-*` kullanıcılarında fraud kayıtlarının oluştuğu API üzerinden teyit edildi.

## 19. Şu Anda Projede Tam Olarak Ne Var

Şu anda repoda şu ana yetenekler mevcut:

1. Çok servisli bir backend mimarisi
2. REST API
3. Worker tüketim mantığı
4. MCP tool yayını
5. Redis tabanlı fraud değerlendirme mantığı
6. SQLite destekli demo fraud değerlendirme modu
7. Canlı SSE akışı
8. React dashboard
9. Trend grafiği
10. Alarm paneli
11. Kullanıcı detay ekranı
12. Manuel veri girişi scripti
13. Otomatik yük/anomaly scripti
14. Docker ve compose tanımları
15. README dokümantasyonu

## 20. Bilinçli Olarak Açık Bırakılan veya Ortama Bağlı Kalan Noktalar

Kod bazında mimari hazır olsa da şu noktalar ortam bağımlı kaldı:

1. Bu makinede Docker registry timeout verdiği için gerçek container akışı burada tam test edilemedi.
2. MCP servisi kod olarak hazır, ancak demo modda asıl inceleme frontend + API üzerinden yapıldı.
3. Redis ve RabbitMQ içeren gerçek akışın son smoke testi ancak Docker image pull sorunu çözüldüğünde tamamlanabilir.

Bu maddeler projenin eksik yazıldığı anlamına gelmiyor; daha çok mevcut ortamın dış servis çekme probleminden kaynaklanıyor.

## 21. İnceleme İçin Önerilen Yol

Projeyi inceleyecek kişi için en pratik rota şu:

1. `README.md` ile genel resmi oku
2. `backend/api/main.py` ile API akışını incele
3. `backend/worker/main.py` ile asenkron fraud işleme mantığını incele
4. `backend/mcp_server/main.py` ile MCP tool tanımlarına bak
5. `backend/common/fraud.py` ile anomaly karar mekanizmasını incele
6. `frontend/src/App.jsx` ile dashboard davranışını incele
7. `scripts/auto_test.py` ile test besleme yaklaşımını incele

## 22. Kısa Özet

Bu repo içinde yaptığımız şey, boş bir klasörden başlayıp şu gereksinimleri karşılayan çalışan bir ürün iskeleti çıkarmak oldu:

- fraud tespiti yapan backend
- canlı veri gösteren frontend
- AI ajanlarına açılan MCP araçları
- script ile veri besleme
- docker ile dağıtım kurgusu
- demo mod ile yerelde gösterilebilir sürüm

En kritik ek değerlerden biri, Docker ağı sorunlu olsa bile projeyi görülebilir ve test edilebilir halde tutmak için demo mod geliştirilmiş olmasıdır.

## 23. İlgili Dosyalar

Hızlı referans için önemli dosyalar:

- `README.md`
- `docker-compose.yml`
- `backend/api/main.py`
- `backend/api/events.py`
- `backend/worker/main.py`
- `backend/mcp_server/main.py`
- `backend/common/fraud.py`
- `backend/common/repository.py`
- `frontend/src/App.jsx`
- `frontend/src/styles.css`
- `scripts/manual_input.py`
- `scripts/auto_test.py`

