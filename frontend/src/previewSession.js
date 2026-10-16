const SESSION_KEY = "loka-kin-preview-session";
export const PREVIEW_TOKEN_PARAM = "access_token";
export const previewTokenFallbackEnabled = process.env.REACT_APP_PREVIEW_TOKEN_FALLBACK === "true";

/**
 * Pratinjau di dalam iframe dapat memblokir cookie pihak ketiga, dan gateway di
 * depannya dapat membuang header Authorization. Keduanya gagal tanpa pesan, jadi
 * arahkan pengguna ke jalur yang pasti berhasil.
 */
export const PREVIEW_SESSION_HINT = "Buka pratinjau di tab baru (tombol di bawah) atau izinkan cookie untuk situs ini, lalu masuk ulang.";

let memoryToken = "";
let storageBlocked = false;

function readStoredToken() {
  try {
    return window.sessionStorage.getItem(SESSION_KEY) || "";
  } catch {
    storageBlocked = true;
    return "";
  }
}

export function savePreviewSessionToken(token) {
  if (!previewTokenFallbackEnabled || !token) return;
  memoryToken = String(token);
  try {
    window.sessionStorage.setItem(SESSION_KEY, memoryToken);
    storageBlocked = false;
  } catch {
    // Keep an in-memory token for browsers that restrict iframe storage.
    storageBlocked = true;
  }
}

export function getPreviewSessionToken() {
  if (!previewTokenFallbackEnabled) return "";
  if (memoryToken) return memoryToken;
  memoryToken = readStoredToken();
  return memoryToken;
}

export function clearPreviewSessionToken() {
  memoryToken = "";
  try {
    window.sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // Nothing else to clear when iframe storage is unavailable.
  }
}

/** Diagnosis singkat untuk pesan kesalahan: apa yang masih bisa dipakai tab ini? */
export function previewSessionState() {
  if (!previewTokenFallbackEnabled) return { enabled: false, hasToken: false, storageBlocked: false };
  return { enabled: true, hasToken: Boolean(getPreviewSessionToken()), storageBlocked };
}

/**
 * Tempelkan sesi tab ini pada permintaan API.
 *
 * Header `Authorization` adalah jalur utama, tetapi gateway di depan pratinjau bisa
 * membuangnya dan cookie pihak ketiga sering diblokir di dalam iframe. Karena itu
 * token ikut dikirim sebagai parameter query; API hanya menerimanya bila
 * AUTH_PREVIEW_TOKEN_FALLBACK aktif di server.
 */
export function withPreviewAuth(config, token) {
  if (!token) return config;
  config.headers = config.headers || {};
  if (typeof config.headers.set === "function") config.headers.set("Authorization", `Bearer ${token}`);
  else config.headers.Authorization = `Bearer ${token}`;
  if (config.params?.[PREVIEW_TOKEN_PARAM] === undefined) {
    config.params = { ...(config.params || {}), [PREVIEW_TOKEN_PARAM]: token };
  }
  return config;
}
