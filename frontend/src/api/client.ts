type ApiError = {
  error?: {
    code?: string;
    message?: string;
  };
};

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const method = options.method ?? "GET";
  const isBodyRequest = method !== "GET" && method !== "HEAD";

  const headers: HeadersInit = {
    ...(isBodyRequest ? { "Content-Type": "application/json" } : {}),
    ...(options.headers ?? {})
  };

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    let errorMessage = `Request failed (${response.status})`;
    try {
      const data = (await response.json()) as ApiError;
      if (data?.error?.message) {
        errorMessage = data.error.message;
      }
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(errorMessage);
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new Error("Invalid JSON response");
  }
}
