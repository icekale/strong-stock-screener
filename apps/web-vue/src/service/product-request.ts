export class ApiRequestError extends Error {
  readonly status: number;
  readonly body: string;

  constructor(status: number, body: string) {
    super(`API request failed: ${status} ${body}`.trim());
    this.name = 'ApiRequestError';
    this.status = status;
    this.body = body;
  }
}

function resolveApiUrl(path: string): string {
  const baseUrl = String(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  return `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
}

export async function apiRequest<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(resolveApiUrl(path), init);

  if (!response.ok) {
    throw new ApiRequestError(response.status, await response.text());
  }

  return response.json() as Promise<T>;
}

export function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(resolveApiUrl(path), init);
}

export function apiUrl(path: string): string {
  return resolveApiUrl(path);
}
