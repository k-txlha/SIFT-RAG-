const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
  });

  const data = response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(data?.detail ?? `Request failed (${response.status})`);
  }

  return data;
}

export { API_BASE };
