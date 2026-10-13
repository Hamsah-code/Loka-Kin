describe("per-tab preview session", () => {
  let session;
  beforeEach(() => {
    jest.resetModules();
    sessionStorage.clear();
    process.env.REACT_APP_PREVIEW_TOKEN_FALLBACK = "true";
    session = require("./previewSession");
  });
  afterEach(() => {
    jest.restoreAllMocks();
    delete process.env.REACT_APP_PREVIEW_TOKEN_FALLBACK;
  });

  test("saves, restores after reload and clears a tab's token", () => {
    session.savePreviewSessionToken("test-session");
    expect(session.getPreviewSessionToken()).toBe("test-session");
    jest.resetModules();
    session = require("./previewSession");
    expect(session.getPreviewSessionToken()).toBe("test-session");
    session.clearPreviewSessionToken();
    expect(session.getPreviewSessionToken()).toBe("");
  });

  test("works in memory when iframe storage is blocked", () => {
    jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    jest.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("blocked"); });
    session.savePreviewSessionToken("test-session");
    expect(session.getPreviewSessionToken()).toBe("test-session");
    session.clearPreviewSessionToken();
    expect(session.getPreviewSessionToken()).toBe("");
  });

  test("new in-memory token wins if replacing a stored token is blocked", () => {
    session.savePreviewSessionToken("old-session");
    jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    session.savePreviewSessionToken("new-session");
    expect(session.getPreviewSessionToken()).toBe("new-session");
  });

  test("fallback is disabled in ordinary production builds", () => {
    delete process.env.REACT_APP_PREVIEW_TOKEN_FALLBACK;
    jest.resetModules();
    session = require("./previewSession");
    session.savePreviewSessionToken("test-session");
    expect(session.previewTokenFallbackEnabled).toBe(false);
    expect(session.getPreviewSessionToken()).toBe("");
    expect(sessionStorage.length).toBe(0);
  });
});
