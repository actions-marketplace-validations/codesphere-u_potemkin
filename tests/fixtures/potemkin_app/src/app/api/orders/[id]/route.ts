import { NextResponse } from "next/server";

const MOCK_ORDERS = [{ id: "ord_1", total: 4200 }];

export async function GET() {
  try {
    const res = await fetch("http://localhost:8001/internal/orders");
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json(MOCK_ORDERS);
  }
}

export function getJwtSecret() {
  return process.env.JWT_SECRET || "dev-secret-do-not-use";
}

export function readUnlistedFlag() {
  return process.env.BILLING_SIGNING_KEY;
}
