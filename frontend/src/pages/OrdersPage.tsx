import { useEffect, useState } from "react";
import { ShoppingBag, Plus, Minus, ShoppingCart, Package } from "lucide-react";
import api from "../services/api";
import { Order, Product } from "../types";
import { format } from "date-fns";

export default function OrdersPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [cart, setCart] = useState<Record<number, number>>({});
  const [tab, setTab] = useState<"shop" | "orders">("shop");
  const [placing, setPlacing] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");

  useEffect(() => {
    api.get("/orders/products").then((r) => setProducts(r.data));
    api.get("/orders/").then((r) => setOrders(r.data));
  }, []);

  const categories = ["all", ...Array.from(new Set(products.map((p) => p.category)))];
  const filtered = categoryFilter === "all" ? products : products.filter((p) => p.category === categoryFilter);

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
      setSuccessMsg("Order placed successfully!");
      const { data } = await api.get("/orders/");
      setOrders(data);
      setTimeout(() => setSuccessMsg(""), 4000);
    } finally {
      setPlacing(false);
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
            My Orders
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-4 text-green-700 text-sm font-medium">
          {successMsg}
        </div>
      )}

      {tab === "shop" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Products */}
          <div className="lg:col-span-2">
            {/* Category filter */}
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

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {filtered.map((p) => (
                <div key={p.id} className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="w-full h-32 bg-gray-100 rounded-lg mb-3 flex items-center justify-center">
                    <Package className="w-10 h-10 text-gray-300" />
                  </div>
                  <p className="font-semibold text-gray-900 text-sm mb-1">{p.name}</p>
                  {p.description && (
                    <p className="text-xs text-gray-500 mb-2 line-clamp-2">{p.description}</p>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-primary-700">${p.price.toFixed(2)}</span>
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
                          ×{qty} · ${(p.price * qty).toFixed(2)}
                        </span>
                      </li>
                    );
                  })}
                </ul>
                <div className="border-t border-gray-100 pt-3 mb-4 flex justify-between font-semibold text-gray-900">
                  <span>Total</span>
                  <span>${cartTotal.toFixed(2)}</span>
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
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="font-semibold text-gray-900">Order #{order.id}</p>
                      <p className="text-xs text-gray-400">
                        {format(new Date(order.created_at), "MMM d, yyyy h:mm a")}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${orderStatusBadge(order.status)}`}>
                        {order.status}
                      </span>
                      <span className="font-bold text-primary-700">${order.total_price.toFixed(2)}</span>
                    </div>
                  </div>
                  <ul className="space-y-1">
                    {order.items.map((item) => (
                      <li key={item.id} className="text-sm text-gray-600 flex justify-between">
                        <span>{item.product.name} ×{item.quantity}</span>
                        <span>${(item.unit_price * item.quantity).toFixed(2)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function orderStatusBadge(status: string) {
  return {
    pending: "bg-yellow-100 text-yellow-700",
    confirmed: "bg-blue-100 text-blue-700",
    shipped: "bg-purple-100 text-purple-700",
    delivered: "bg-green-100 text-green-700",
    cancelled: "bg-red-100 text-red-700",
  }[status] || "bg-gray-100 text-gray-600";
}
