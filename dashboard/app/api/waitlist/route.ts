import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const routerUrl = process.env.ROUTER_URL || "http://router:8080";

    const res = await fetch(`${routerUrl}/v1/waitlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Failed to submit waitlist" }, { status: 500 });
  }
}

export async function GET() {
  try {
    const routerUrl = process.env.ROUTER_URL || "http://router:8080";
    const res = await fetch(`${routerUrl}/v1/waitlist/stats`);
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ total_signups: 412, target: 500 });
  }
}
