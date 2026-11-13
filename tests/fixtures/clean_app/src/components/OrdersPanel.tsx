import React, { useState } from "react";

interface Order {
  id: string;
  item: string;
}

export function OrdersPanel({ onNavigateHelp }: { onNavigateHelp: () => void }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState<string | null>(null);
  const publishableKey = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY ?? "";

  async function loadOrders() {
    setError(null);
    try {
      const response = await fetch("/api/orders", { method: "GET" });
      if (!response.ok) {
        throw new Error(`Load failed: ${response.status}`);
      }
      const data = (await response.json()) as { orders: Order[] };
      setOrders(data.orders);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load orders");
    }
  }

  async function createOrder(item: string) {
    setError(null);
    const response = await fetch("/api/orders", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Stripe-Key": publishableKey,
      },
      body: JSON.stringify({ item }),
    });
    if (!response.ok) {
      throw new Error(`Create failed: ${response.status}`);
    }
    await loadOrders();
  }

  async function cancelOrder(orderId: string) {
    setError(null);
    const response = await fetch(`/api/orders/${orderId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error(`Cancel failed: ${response.status}`);
    }
    setOrders((prev) => prev.filter((order) => order.id !== orderId));
  }

  return (
    <section id="features">
      <nav>
        <a href="#features">Features</a>
        <a
          href="#"
          onClick={(event) => {
            event.preventDefault();
            onNavigateHelp();
          }}
        >
          Help
        </a>
      </nav>
      <button type="button" onClick={() => void loadOrders()}>
        Refresh Orders
      </button>
      <button type="button" onClick={() => void createOrder("starter-plan")}>
        Create Order
      </button>
      {orders.map((order) => (
        <div key={order.id}>
          <span>{order.item}</span>
          <button type="button" onClick={() => void cancelOrder(order.id)}>
            Cancel
          </button>
        </div>
      ))}
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}
