const SESSION_KEY = "loka-kin-preview-session";
export const previewTokenFallbackEnabled = process.env.REACT_APP_PREVIEW_TOKEN_FALLBACK === "true";

let memoryToken = "";

export function savePreviewSessionToken(token) {
  if (!previewTokenFallbackEnabled || !token) return;
  memoryToken = String(token);
  try {
    window.sessionStorage.setItem(SESSION_KEY, memoryToken);
  } catch {
    // Keep an in-memory token for browsers that restrict iframe storage.
  }
}

export function getPreviewSessionToken() {
  if (!previewTokenFallbackEnabled) return "";
  if (memoryToken) return memoryToken;
  try {
    return window.sessionStorage.getItem(SESSION_KEY) || "";
  } catch {
    return memoryToken;
  }
}

export function clearPreviewSessionToken() {
  memoryToken = "";
  try {
    window.sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // Nothing else to clear when iframe storage is unavailable.
  }
}
