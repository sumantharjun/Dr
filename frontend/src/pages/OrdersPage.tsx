import { useEffect, useState, useRef } from "react";
import { ShoppingBag, Plus, Minus, ShoppingCart, Package, XCircle, CheckCircle2, Truck, Clock, Search } from "lucide-react";
import api from "../services/api";
import { Order, Product } from "../types";
import { CardSkeleton } from "../components/Skeleton";
import { format, formatDistanceToNow } from "date-fns";

const STATUS_STEPS: Order["status"][] = ["pending", "confirmed", "shipped", "delivered"];

export default function OrdersPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [cart, setCart] = useState<Record<number, number>>({});
  const [tab, setTab] = useState<"shop" | "orders">("shop");
  const [placing, setPlacing] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    Promise.all([
      api.get("/orders/products").then((r) => setProducts(r.data)),
      api.get("/orders/").then((r) => setOrders(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  // Auto-refresh orders every 30 s when on the orders tab and there are active orders
  useEffect(() => {
    if (tab !== "orders") {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    const hasActive = orders.some((o) =>
      ["pending", "confirmed", "shipped"].includes(o.status)
    );
    if (!hasActive) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(async () => {
      const { data } = await api.get("/orders/");
      setOrders(data);
    }, 30_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [tab, orders]);

  const categories = ["all", ...Array.from(new Set(products.map((p) => p.category)))];
  const q = search.trim().toLowerCase();
  const filtered = products
    .filter((p) => categoryFilter === "all" || p.category === categoryFilter)
    .filter(
      (p) =>
        !q ||
        p.name.toLowerCase().includes(q) ||
        (p.description ?? "").toLowerCase().includes(q)
    );

  function updateCart(id: number, delta: number) {
    setCart((prev) => {
      const next = { ...prev, [id]: (prev[id] || 0) + delta };
      if (next[id] <= 0) delete next[id];
      return next;
    });
  }

  const cartTotal = Object.entries(cart).reduce((sum, [id, qty]) => {
    const p = products.find((p) => p.id === Number(id));
    return sum + (p?.price || 0) * qty;
  }, 0);

  const cartCount = Object.values(cart).reduce((s, v) => s + v, 0);

  async function handlePlaceOrder() {
    if (cartCount === 0) return;
    setPlacing(true);
    try {
      await api.post("/orders/", {
        items: Object.entries(cart).map(([id, qty]) => ({
          product_id: Number(id),
          quantity: qty,
        })),
      });
      setCart({});
      setSuccessMsg("Order placed! Track progress in My Orders.");
      const { data } = await api.get("/orders/");
      setOrders(data);
      setTab("orders");
      setTimeout(() => setSuccessMsg(""), 5000);
    } finally {
      setPlacing(false);
    }
  }

  async function handleCancel(orderId: number) {
    if (!confirm("Are you sure you want to cancel this order? Stock will be restored.")) return;
    setCancellingId(orderId);
    try {
      const { data } = await api.patch(`/orders/${orderId}/cancel`);
      setOrders((prev) => prev.map((o) => (o.id === orderId ? data : o)));
    } catch (err: any) {
      alert(err.response?.data?.detail || "Failed to cancel order");
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Orders</h1>
          <p className="text-gray-500 text-sm mt-1">Shop for cleaning supplies and accessories</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setTab("shop")}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
              tab === "shop" ? "bg-primary-600 text-white" : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
            }`}
          >
            Shop
          </button>
          <button
            onClick={() => setTab("orders")}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
              tab === "orders" ? "bg-primary-600 text-white" : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
            }`}
          >
            My Orders {orders.filter((o) => ["pending", "confirmed", "shipped"].includes(o.status)).length > 0 && (
              <span className="ml-1 bg-primary-200 text-primary-800 text-xs px-1.5 py-0.5 rounded-full">
                {orders.filter((o) => ["pending", "confirmed", "shipped"].includes(o.status)).length}
              </span>
            )}
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-4 text-green-700 text-sm font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          {successMsg}
        </div>
      )}

      {/* ── SHOP TAB ── */}
      {tab === "shop" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <div className="relative mb-4">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search products…"
                className="w-full border border-gray-300 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div className="flex gap-2 mb-4 flex-wrap">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(cat)}
                  className={`px-3 py-1 text-xs rounded-full font-medium capitalize transition-colors ${
                    categoryFilter === cat
                      ? "bg-primary-600 text-white"
                      : "bg-white border border-gray-300 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {loading && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <CardSkeleton key={i} />
                ))}
              </div>
            )}
            {!loading && filtered.length === 0 && (
              <div className="text-center text-sm text-gray-400 py-12 border border-dashed border-gray-200 rounded-xl">
                No products match{search.trim() ? ` “${search.trim()}”` : " this filter"}.
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {!loading && filtered.map((p) => (
                <div key={p.id} className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="w-full h-32 bg-gray-50 rounded-lg mb-3 overflow-hidden flex items-center justify-center">
                    {p.image_url ? (
                      <img
                        src={p.image_url}
                        alt={p.name}
                        loading="lazy"
                        className="w-full h-full object-contain"
                        onError={(e) => {
                          // Fallback to the generic icon if the image fails to load.
                          e.currentTarget.style.display = "none";
                          e.currentTarget.insertAdjacentHTML(
                            "afterend",
                            '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" stroke-width="2"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>'
                          );
                        }}
                      />
                    ) : (
                      <Package className="w-10 h-10 text-gray-300" />
                    )}
                  </div>
                  <p className="font-semibold text-gray-900 text-sm mb-1">{p.name}</p>
                  {p.description && (
                    <p className="text-xs text-gray-500 mb-2 line-clamp-2">{p.description}</p>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-primary-700">₹{p.price.toFixed(2)}</span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => updateCart(p.id, -1)}
                        disabled={!cart[p.id]}
                        className="w-7 h-7 rounded-full border border-gray-300 flex items-center justify-center text-gray-600 hover:bg-gray-100 disabled:opacity-30"
                      >
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="w-5 text-center text-sm font-medium">{cart[p.id] || 0}</span>
                      <button
                        onClick={() => updateCart(p.id, 1)}
                        className="w-7 h-7 rounded-full bg-primary-600 text-white flex items-center justify-center hover:bg-primary-700"
                      >
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Cart */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 h-fit sticky top-6">
            <div className="flex items-center gap-2 mb-4">
              <ShoppingCart className="w-5 h-5 text-primary-600" />
              <h2 className="font-semibold text-gray-900">Cart ({cartCount})</h2>
            </div>
            {cartCount === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">Your cart is empty</p>
            ) : (
              <>
                <ul className="space-y-3 mb-4">
                  {Object.entries(cart).map(([id, qty]) => {
                    const p = products.find((p) => p.id === Number(id));
                    if (!p) return null;
                    return (
                      <li key={id} className="flex justify-between text-sm">
                        <span className="text-gray-700 flex-1 pr-2 truncate">{p.name}</span>
                        <span className="text-gray-500 flex-shrink-0">
                          ×{qty} · ₹{(p.price * qty).toFixed(2)}
                        </span>
                      </li>
                    );
                  })}
                </ul>
                <div className="border-t border-gray-100 pt-3 mb-4 flex justify-between font-semibold text-gray-900">
                  <span>Total</span>
                  <span>₹{cartTotal.toFixed(2)}</span>
                </div>
                <button
                  onClick={handlePlaceOrder}
                  disabled={placing}
                  className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
                >
                  {placing ? "Placing order..." : "Place Order"}
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── MY ORDERS TAB ── */}
      {tab === "orders" && (
        <div>
          {orders.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
              <ShoppingBag className="w-12 h-12 mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500">No orders yet</p>
            </div>
          ) : (
            <div className="space-y-4">
              {orders.map((order) => (
                <div key={order.id} className="bg-white rounded-xl border border-gray-200 p-5">
                  {/* Order header */}
                  <div className="flex items-start justify-between mb-4 gap-3">
                    <div>
                      <p className="font-semibold text-gray-900">Order #{order.id}</p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        Placed {formatDistanceToNow(new Date(order.created_at), { addSuffix: true })} ·{" "}
                        {format(new Date(order.created_at), "dd MMM yyyy, HH:mm")}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${orderStatusBadge(order.status)}`}>
                        {order.status}
                      </span>
                      <span className="font-bold text-primary-700">₹{order.total_price.toFixed(2)}</span>
                    </div>
                  </div>

                  {/* Status progress bar (hide for cancelled) */}
                  {order.status !== "cancelled" && (
                    <OrderProgressBar status={order.status} />
                  )}

                  {/* Items */}
                  <ul className="space-y-1 mt-4">
                    {order.items.map((item) => (
                      <li key={item.id} className="text-sm text-gray-600 flex justify-between">
                        <span>{item.product.name} ×{item.quantity}</span>
                        <span>₹{(item.unit_price * item.quantity).toFixed(2)}</span>
                      </li>
                    ))}
                  </ul>

                  {/* Cancel button */}
                  {(order.status === "pending" || order.status === "confirmed") && (
                    <div className="mt-4 pt-3 border-t border-gray-100">
                      <button
                        onClick={() => handleCancel(order.id)}
                        disabled={cancellingId === order.id}
                        className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-700 font-medium disabled:opacity-50 transition-colors"
                      >
                        <XCircle className="w-4 h-4" />
                        {cancellingId === order.id ? "Cancelling..." : "Cancel Order"}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OrderProgressBar({ status }: { status: Order["status"] }) {
  const steps = [
    { key: "pending",   label: "Placed",    icon: Clock },
    { key: "confirmed", label: "Confirmed", icon: CheckCircle2 },
    { key: "shipped",   label: "Shipped",   icon: Truck },
    { key: "delivered", label: "Delivered", icon: Package },
  ] as const;

  const currentIdx = STATUS_STEPS.indexOf(status);

  return (
    <div className="flex items-center gap-0">
      {steps.map((step, idx) => {
        const done = idx <= currentIdx;
        const active = idx === currentIdx;
        const Icon = step.icon;
        return (
          <div key={step.key} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center transition-colors ${
                  done
                    ? active
                      ? "bg-primary-600 text-white ring-2 ring-primary-200"
                      : "bg-primary-100 text-primary-600"
                    : "bg-gray-100 text-gray-400"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
              </div>
              <span className={`text-xs font-medium ${done ? "text-primary-700" : "text-gray-400"}`}>
                {step.label}
              </span>
            </div>
            {idx < steps.length - 1 && (
              <div
                className={`flex-1 h-0.5 mx-1 mb-4 transition-colors ${
                  idx < currentIdx ? "bg-primary-400" : "bg-gray-200"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function orderStatusBadge(status: string) {
  return (
    {
      pending:   "bg-yellow-100 text-yellow-700",
      confirmed: "bg-blue-100 text-blue-700",
      shipped:   "bg-purple-100 text-purple-700",
      delivered: "bg-green-100 text-green-700",
      cancelled: "bg-red-100 text-red-700",
    }[status] || "bg-gray-100 text-gray-600"
  );
}
