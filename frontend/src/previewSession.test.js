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

  test("sends the token as bearer header and as query parameter", () => {
    session.savePreviewSessionToken("test-session");
    const headers = { set: jest.fn() };
    const config = session.withPreviewAuth({ url: "/api/tasks", headers }, session.getPreviewSessionToken());
    expect(headers.set).toHaveBeenCalledWith("Authorization", "Bearer test-session");
    expect(config.params).toEqual({ access_token: "test-session" });
  });

  test("plain config without axios headers still receives the query parameter", () => {
    session.savePreviewSessionToken("test-session");
    const config = session.withPreviewAuth({ params: { staff_id: "staff-2" } }, "test-session");
    expect(config.headers.Authorization).toBe("Bearer test-session");
    expect(config.params).toEqual({ staff_id: "staff-2", access_token: "test-session" });
  });

  test("an existing access_token parameter is never overwritten", () => {
    const config = session.withPreviewAuth({ params: { access_token: "explicit" } }, "test-session");
    expect(config.params.access_token).toBe("explicit");
  });

  test("requests without a token stay anonymous", () => {
    expect(session.withPreviewAuth({ url: "/api/tasks", headers: {} }, "")).toEqual({ url: "/api/tasks", headers: {} });
  });

  test("state reports the token and whether iframe storage is blocked", () => {
    expect(session.previewSessionState()).toEqual({ enabled: true, hasToken: false, storageBlocked: false });
    jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    session.savePreviewSessionToken("test-session");
    jest.restoreAllMocks();
    expect(session.previewSessionState()).toEqual({ enabled: true, hasToken: true, storageBlocked: true });
    session.clearPreviewSessionToken();
    expect(session.previewSessionState().hasToken).toBe(false);
  });
});
