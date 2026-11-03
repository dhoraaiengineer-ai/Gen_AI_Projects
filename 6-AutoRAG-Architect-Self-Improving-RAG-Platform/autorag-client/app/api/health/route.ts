import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json(
    {
      status: "healthy",
      service: "autorag-client",
      timestamp: new Date().toISOString(),
    },
    { status: 200 }
  );
}