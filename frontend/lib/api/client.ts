import createClient from "openapi-fetch";

import type { paths } from "./schema";

// Server components run inside the container network; the browser uses localhost.
const baseUrl =
  typeof window === "undefined"
    ? (process.env.API_URL ?? "http://localhost:8000")
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");

export const api = createClient<paths>({ baseUrl, cache: "no-store" });
