import { useState } from "react";

const mockUsers = [
  { id: "1", email: "test@example.com", role: "admin" },
];

export function BillingPanel() {
  const [saved, setSaved] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTimeout(() => {
      setSaved(true);
    }, 600);
  };

  async function deleteOrder(id: string) {
    return fetch(`/api/orders/${id}`, { method: "DELETE" });
  }

  return (
    <div>
      <button onClick={() => alert("Exporting PDF invoice...")}>Export PDF</button>
      <a href="#">Documentation</a>
      <p>{mockUsers.length}</p>
      <p>{process.env.NEXT_PUBLIC_ADMIN_SECRET}</p>
      <button onClick={() => deleteOrder("ord_1")}>Delete</button>
      <form onSubmit={handleSubmit}>
        <button type="submit">{saved ? "Saved" : "Save"}</button>
      </form>
    </div>
  );
}
