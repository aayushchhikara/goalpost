import { Suspense } from "react";
import { connection } from "next/server";

import { api } from "@/lib/api/client";

async function BackendStatus() {
  await connection();
  const data = await api
    .GET("/health")
    .then((r) => r.data)
    .catch(() => undefined);

  return (
    <p className="mt-4 text-sm text-muted-foreground">
      {data ? `Backend: ${data.status} (v${data.version})` : "Backend unreachable"}
    </p>
  );
}

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-3xl font-semibold">Goalpost</h1>
      <Suspense fallback={<p className="mt-4 text-sm">Checking backend…</p>}>
        <BackendStatus />
      </Suspense>
    </main>
  );
}
