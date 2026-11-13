import { createHmac } from "node:crypto";

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function getAllowedOrigins(config: { dev: boolean }): string[] {
  if (config.dev) {
    return ["http://localhost:3000"];
  }
  return ["https://app.example.com"];
}

export async function GET(): Promise<Response> {
  const dbUrl = requireEnv("DATABASE_URL");
  const signingKey = requireEnv("JWT_SECRET");
  const digest = createHmac("sha256", signingKey).update(dbUrl).digest("hex").slice(0, 8);
  return Response.json({ orders: [], storeHash: digest });
}

export async function POST(request: Request): Promise<Response> {
  requireEnv("DATABASE_URL");
  const body = (await request.json()) as { item?: string };
  if (!body.item || body.item.trim().length === 0) {
    return Response.json({ error: "item is required" }, { status: 400 });
  }
  return Response.json({ id: "ord_created", item: body.item.trim() }, { status: 201 });
}
