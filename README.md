# 🎓 NeYapAI: Yapay Zeka Destekli İnteraktif Öğrenme Platformu

## 🛠️ Kullanılan Teknolojiler

- **🤖 Gemini**: Öğrencilere kişiselleştirilmiş ve akıllı yanıtlar sağlayarak öğrenme deneyimini zenginleştirir.
- **⚡ FastAPI**: Yüksek performanslı ve esnek bir web framework'ü olarak, hızlı API geliştirme imkanı sunar.
- **🗄️ MongoDB**: Ölçeklenebilir ve esnek NoSQL veritabanı yapısı sayesinde kullanıcı ve kurs verilerini etkin bir şekilde yönetir.
- **🔗 Langchain**: Gelişmiş dil modelleri ile doğal dil işleme ve yapay zeka tabanlı etkileşimler sağlar.
- **🌐 Streamlit**: Kullanıcı dostu ve etkileşimli web arayüzleri oluşturarak, eğitim materyallerinin kolay erişimini mümkün kılar.

## 🌟 Ürünün Faydaları

- **👤 Kişiselleştirilmiş Öğrenme Deneyimi**: Yapay zeka destekli asistanlar, her öğrencinin bireysel ihtiyaçlarına göre uyarlanmış içerikler sunar.
- **🔄 Etkileşimli ve Dinamik İçerik**: Adım adım ilerleyen kurs yapısı sayesinde, öğrenciler konuları derinlemesine anlayarak öğrenirler.
- **⚡ Gerçek Zamanlı Geri Bildirim**: Anında değerlendirmeler ve açıklamalar ile öğrenciler, öğrenme süreçlerinde sürekli destek alır.
- **🌐 Kolay Erişim ve Kullanım**: Web tabanlı arayüz sayesinde, öğrenciler her yerden ve her cihazdan kurslara erişebilirler.
- **📊 İlerleme Takibi**: Kullanıcıların kurs ilerlemeleri detaylı olarak izlenir ve görsel ilerleme çubukları ile takip edilebilir.

## ✨ Özellikler

### 📚 Çoklu Kurs Desteği
- 🎯 Farklı konularda genişletilebilir bir kurs yelpazesi
- 📝 YAML formatında kolay kurs oluşturma
- 🔄 Modüler ve genişletilebilir kurs yapısı

### 🤖 Gelişmiş Chatbot
- 🧠 Gemini tabanlı doğal dil işleme
- 💡 Bağlama duyarlı yanıtlar
- ⚡ Öğrenci sorularına anında geri bildirim

### 📊 Gerçek Zamanlı Veri Yönetimi
- 🔒 MongoDB ile güvenli veri saklama
- 📈 Kullanıcı ilerleme takibi
- 🔄 Kurs durumu senkronizasyonu

### 🎯 Özelleştirilebilir Kurs Yapısı
- 📑 Bölümler ve alt adımlar
- 🔄 İlerlemeli öğrenme sistemi
- ⚡ Esnek içerik yapılandırması

### 🖼️ Görsel ve Medya Entegrasyonu
- 🎨 Resim desteği


## ⚙️ Kurulum

1. Gerekli ortam değişkenlerini ayarlayın:
```env
MONGODB_URI="mongodb+srv://kullaniciadi:<SIFRE>@cluster0.example.mongodb.net/"
DATABASE_NAME=dev
GEMINI_API_KEY=<GEMINI-API-ANAHTARINIZ>
LANGCHAIN_TRACING_V2="true"
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY=<LANGSMITH-API-ANAHTARINIZ>
LANGCHAIN_PROJECT="neyapai-test"
```

2. Bağımlılıkları yükleyin:
```bash
pipenv shell
pipenv install
```

3. Uygulamayı başlatın:
```bash
# Backend
pipenv run uvicorn server.main:app --reload 

# Frontend
streamlit run ui/main.py
```