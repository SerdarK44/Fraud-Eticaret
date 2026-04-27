import { startTransition, useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function formatMoney(value) {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(value) {
  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusLabel(status) {
  return status === "suspicious" ? "Şüpheli" : "Onaylandı";
}

function EventBadge({ status }) {
  return (
    <span className={`status-badge ${status}`}>
      {statusLabel(status)}
    </span>
  );
}

function App() {
  const [transactions, setTransactions] = useState([]);
  const [trend, setTrend] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedUser, setSelectedUser] = useState("user-001");
  const [searchValue, setSearchValue] = useState("user-001");
  const [userStatus, setUserStatus] = useState(null);
  const [connectionState, setConnectionState] = useState("connecting");
  const [loadingUser, setLoadingUser] = useState(false);
  const [error, setError] = useState("");

  const loadDashboard = async () => {
    const [recentTransactions, fraudTrend, frauds] = await Promise.all([
      fetchJson("/transactions/recent?limit=20"),
      fetchJson("/metrics/fraud-trend?hours=24&bucket_minutes=15"),
      fetchJson("/frauds?limit=12"),
    ]);
    setTransactions(recentTransactions);
    setTrend(fraudTrend);
    setAlerts(frauds.transactions);
  };

  const loadUser = async (userId) => {
    if (!userId) {
      return;
    }
    setLoadingUser(true);
    try {
      const response = await fetchJson(`/users/${encodeURIComponent(userId)}/status?limit=15`);
      setUserStatus(response);
      setSelectedUser(userId);
    } finally {
      setLoadingUser(false);
    }
  };

  useEffect(() => {
    loadDashboard()
      .then(() => loadUser(selectedUser))
      .catch((loadError) => setError(loadError.message));
  }, []);

  useEffect(() => {
    const source = new EventSource(`${API_BASE}/stream/events`);

    const handleStreamEvent = (incoming) => {
      const event = JSON.parse(incoming.data);
      const nextTransaction = event.transaction;

      setTransactions((current) => [nextTransaction, ...current].slice(0, 20));
      if (event.event_type === "fraud_alert") {
        setAlerts((current) => [nextTransaction, ...current].slice(0, 12));
      }

      startTransition(() => {
        loadDashboard().catch(() => null);
        if (selectedUser === nextTransaction.user_id) {
          loadUser(selectedUser).catch(() => null);
        }
      });
    };

    source.onopen = () => setConnectionState("live");
    source.onerror = () => setConnectionState("reconnecting");
    source.addEventListener("transaction_processed", handleStreamEvent);
    source.addEventListener("fraud_alert", handleStreamEvent);

    return () => {
      source.close();
      setConnectionState("offline");
    };
  }, [selectedUser]);

  const totalTransactions = trend.reduce((sum, point) => sum + point.total_transactions, 0);
  const suspiciousTransactions = trend.reduce(
    (sum, point) => sum + point.suspicious_transactions,
    0,
  );
  const fraudRate = totalTransactions
    ? ((suspiciousTransactions / totalTransactions) * 100).toFixed(1)
    : "0.0";

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="hero">
        <div>
          <p className="eyebrow">Gerçek zamanlı işlem savunma katmanı</p>
          <h1>Fraud Sentinel Control Room</h1>
          <p className="hero-copy">
            E-ticaret işlemlerini akış halinde izler, kullanıcı bazlı anomalileri
            işaretler ve operasyon ekiplerini anında bilgilendirir.
          </p>
        </div>
        <div className="connection-card">
          <span className={`connection-dot ${connectionState}`} />
          <div>
            <strong>Canlı bağlantı</strong>
            <p>{connectionState}</p>
          </div>
        </div>
      </header>

      <section className="summary-grid">
        <article className="summary-card">
          <span>24 Saatlik İşlem</span>
          <strong>{totalTransactions}</strong>
        </article>
        <article className="summary-card">
          <span>Şüpheli İşlem</span>
          <strong>{suspiciousTransactions}</strong>
        </article>
        <article className="summary-card accent">
          <span>Fraud Oranı</span>
          <strong>%{fraudRate}</strong>
        </article>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <main className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="panel-head">
            <div>
              <p className="panel-kicker">Trend Analizi</p>
              <h2>Fraud oranının zamana göre seyri</h2>
            </div>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="fraudGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff6b57" stopOpacity={0.7} />
                    <stop offset="95%" stopColor="#ff6b57" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" />
                <XAxis
                  dataKey="bucket"
                  tickFormatter={(value) =>
                    new Intl.DateTimeFormat("tr-TR", {
                      hour: "2-digit",
                      minute: "2-digit",
                    }).format(new Date(value))
                  }
                  stroke="#8da3b9"
                />
                <YAxis stroke="#8da3b9" />
                <Tooltip
                  formatter={(value, name) => [
                    name === "fraud_rate" ? `%${value}` : value,
                    name === "fraud_rate" ? "Fraud Oranı" : "Şüpheli İşlem",
                  ]}
                  labelFormatter={(value) => formatDate(value)}
                />
                <Area
                  type="monotone"
                  dataKey="fraud_rate"
                  stroke="#ff6b57"
                  strokeWidth={3}
                  fill="url(#fraudGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="panel-kicker">Anlık Alarm</p>
              <h2>Son şüpheli işlemler</h2>
            </div>
          </div>
          <div className="alert-list">
            {alerts.length === 0 ? (
              <p className="empty-state">Henüz şüpheli işlem algılanmadı.</p>
            ) : (
              alerts.map((item) => (
                <article className="alert-item" key={item.id}>
                  <div>
                    <strong>{item.user_id}</strong>
                    <p>{formatMoney(item.amount)} · {item.location}</p>
                  </div>
                  <span>{formatDate(item.occurred_at)}</span>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="panel-kicker">Canlı Akış</p>
              <h2>İşlem sırası</h2>
            </div>
          </div>
          <div className="feed-list">
            {transactions.map((item) => (
              <article className={`feed-item ${item.status}`} key={item.id}>
                <div className="feed-item-top">
                  <strong>{item.user_id}</strong>
                  <EventBadge status={item.status} />
                </div>
                <p>{formatMoney(item.amount)} · {item.location}</p>
                <span>{formatDate(item.occurred_at)}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="panel panel-wide">
          <div className="panel-head panel-head-split">
            <div>
              <p className="panel-kicker">Kullanıcı İncelemesi</p>
              <h2>Davranış profili ve işlem geçmişi</h2>
            </div>
            <form
              className="user-search"
              onSubmit={(event) => {
                event.preventDefault();
                loadUser(searchValue).catch((loadError) => setError(loadError.message));
              }}
            >
              <input
                value={searchValue}
                onChange={(event) => setSearchValue(event.target.value)}
                placeholder="user-001"
              />
              <button type="submit">Analiz Et</button>
            </form>
          </div>

          {userStatus ? (
            <>
              <div className="user-summary">
                <article>
                  <span>Risk Seviyesi</span>
                  <strong className={`risk-${userStatus.risk_level}`}>
                    {userStatus.risk_level}
                  </strong>
                </article>
                <article>
                  <span>24s Şüpheli</span>
                  <strong>{userStatus.suspicious_transactions_last_24h}</strong>
                </article>
                <article>
                  <span>24s Ortalama Tutar</span>
                  <strong>{formatMoney(userStatus.average_amount_last_24h)}</strong>
                </article>
                <article>
                  <span>Son Lokasyon</span>
                  <strong>{userStatus.latest_location ?? "-"}</strong>
                </article>
              </div>

              <div className="user-history">
                {loadingUser ? (
                  <p className="empty-state">Kullanıcı verisi yükleniyor...</p>
                ) : userStatus.transactions.length === 0 ? (
                  <p className="empty-state">Bu kullanıcı için işlem geçmişi bulunamadı.</p>
                ) : (
                  userStatus.transactions.map((item) => (
                    <article className="history-row" key={item.id}>
                      <div>
                        <strong>{formatMoney(item.amount)}</strong>
                        <p>{item.location}</p>
                      </div>
                      <div>
                        <EventBadge status={item.status} />
                        <p>{item.reasons.join(" | ") || "Normal davranış"}</p>
                      </div>
                      <span>{formatDate(item.occurred_at)}</span>
                    </article>
                  ))
                )}
              </div>
            </>
          ) : (
            <p className="empty-state">Kullanıcı seçerek detayları görüntüleyin.</p>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
