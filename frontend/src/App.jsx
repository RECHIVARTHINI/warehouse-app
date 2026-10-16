import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

function money(cents) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

export default function App() {
  const [products, setProducts] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [busyProduct, setBusyProduct] = useState(null);
  const [restockAmounts, setRestockAmounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadData = useCallback(async () => {
    setError("");
    try {
      const [productResponse, alertResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/products`),
        fetch(`${API_BASE_URL}/warehouse/alerts`),
      ]);
      if (!productResponse.ok || !alertResponse.ok) {
        throw new Error("The API returned an error. Check the backend and database.");
      }
      setProducts(await productResponse.json());
      setAlerts(await alertResponse.json());
    } catch (err) {
      setError(`${err.message} API URL: ${API_BASE_URL}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function buy(product) {
    setBusyProduct(product.id);
    setNotice("");
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/store/buy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: product.id }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Purchase failed");
      setNotice(result.message);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyProduct(null);
    }
  }

  async function restock(productId) {
    const quantity = Number(restockAmounts[productId] || 10);
    if (!Number.isInteger(quantity) || quantity <= 0) {
      setError("Enter a whole-number restock quantity greater than zero.");
      return;
    }
    setError("");
    setNotice("");
    try {
      const response = await fetch(`${API_BASE_URL}/warehouse/restock`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId, quantity }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Restock failed");
      setNotice(result.message);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="page">
      <header className="topbar">
        <div className="brand-mark">S</div>
        <div>
          <p className="eyebrow">INVENTORY MANAGEMENT DEMO</p>
          <h1>StockDesk</h1>
        </div>
        <span className="api-pill"><span className="dot" /> API connected by URL</span>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">STORE + WAREHOUSE</p>
          <h2>Inventory, kept simple.</h2>
          <p className="hero-copy">Buy a product in the store. When stock drops below its threshold, a warehouse alert is created automatically.</p>
        </div>
        <div className="hero-stat">
          <span>Products listed</span>
          <strong>{products.length}</strong>
          <small>Live data from PostgreSQL</small>
        </div>
      </section>

      {error && <div className="banner error">{error}</div>}
      {notice && <div className="banner success">{notice}</div>}

      <section className="section-heading">
        <div>
          <p className="eyebrow">USE CASE 01</p>
          <h2>Store products</h2>
        </div>
        <button className="secondary-button" onClick={loadData}>Refresh data</button>
      </section>

      {loading ? <p className="empty">Loading products…</p> : (
        <section className="product-grid">
          {products.map((product) => (
            <article className="product-card" key={product.id}>
              <div className={`product-icon icon-${product.id % 3}`}>
                {product.name.toLowerCase().includes("mouse") ? "⌁" : product.name.toLowerCase().includes("cable") ? "↗" : "⌨"}
              </div>
              <div className="product-title-row">
                <h3>{product.name}</h3>
                <span className={product.stock < product.threshold ? "stock low" : "stock"}>
                  {product.stock} in stock
                </span>
              </div>
              <p className="description">{product.description}</p>
              <p className="threshold">Alert threshold: {product.threshold} units</p>
              <div className="product-footer">
                <strong className="price">{money(product.price_cents)}</strong>
                <button disabled={product.stock <= 0 || busyProduct === product.id} onClick={() => buy(product)}>
                  {busyProduct === product.id ? "Buying…" : product.stock <= 0 ? "Out of stock" : "Buy"}
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      <section className="section-heading warehouse-heading">
        <div>
          <p className="eyebrow">USE CASE 02 + 03</p>
          <h2>Warehouse alerts</h2>
          <p className="section-subtitle">Low-stock alerts are stored in PostgreSQL. Restocking updates the inventory and resolves its open alert.</p>
        </div>
        <span className="alert-count">{alerts.length} open {alerts.length === 1 ? "alert" : "alerts"}</span>
      </section>

      <section className="warehouse-panel">
        {alerts.length === 0 ? (
          <div className="empty-state">
            <div className="check-circle">✓</div>
            <h3>All clear for now</h3>
            <p>No open low-stock alerts. Buy products until stock falls below a threshold to test the workflow.</p>
          </div>
        ) : (
          <div className="alert-list">
            {alerts.map((alert) => (
              <article className="alert-row" key={alert.id}>
                <div className="alert-symbol">!</div>
                <div className="alert-info">
                  <h3>{alert.product_name}</h3>
                  <p>{alert.message}</p>
                  <small>Current stock: {alert.stock} · Threshold: {alert.threshold}</small>
                </div>
                <div className="restock-controls">
                  <label htmlFor={`qty-${alert.id}`}>Add units</label>
                  <input
                    id={`qty-${alert.id}`}
                    type="number"
                    min="1"
                    value={restockAmounts[alert.product_id] ?? 10}
                    onChange={(event) => setRestockAmounts({ ...restockAmounts, [alert.product_id]: event.target.value })}
                  />
                  <button onClick={() => restock(alert.product_id)}>Restock</button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <footer>
        <span>StockDesk · AWS learning project</span>
        <span>React · FastAPI · PostgreSQL</span>
      </footer>
    </main>
  );
}
