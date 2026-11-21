export const SESSION_EXPIRED_EVENT = "session-expired";

export async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    credentials: "same-origin",
  });

  if (response.status === 401 && !options.signal?.aborted) {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }

  return response;
}