import { WSManager, initWs, type Channel } from "./ws";

// --- Mock WebSocket ---
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }

  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
  });

  // Test helpers
  static instances: MockWebSocket[] = [];
  static reset() {
    MockWebSocket.instances = [];
  }
  static latest(): MockWebSocket {
    return MockWebSocket.instances[MockWebSocket.instances.length - 1];
  }

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  simulateMessage(data: string) {
    this.onmessage?.({ data } as MessageEvent);
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({} as CloseEvent);
  }
}

// Install mock
(globalThis as any).WebSocket = MockWebSocket;

beforeEach(() => {
  vi.useFakeTimers();
  MockWebSocket.reset();
  initWs((ch: Channel) => `ws://test/${ch}`);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("WSManager", () => {
  it("throws if initWs was not called", () => {
    // Temporarily reset the url builder
    initWs(null as any);
    const mgr = new WSManager("portfolio");
    // initWs(null) means _wsUrlBuilder is null-ish — but it's set to null
    // The code checks `if (!_wsUrlBuilder)` which catches null
    expect(() => mgr.connect()).toThrow("WS not initialized");
    // Restore
    initWs((ch: Channel) => `ws://test/${ch}`);
  });

  it("connect creates a WebSocket with the correct URL", () => {
    const mgr = new WSManager("alerts");
    mgr.connect();
    expect(MockWebSocket.latest().url).toBe("ws://test/alerts");
    mgr.disconnect();
  });

  it("subscribe adds a listener and returns unsubscribe fn", () => {
    const mgr = new WSManager("portfolio");
    const handler = vi.fn();
    const unsub = mgr.subscribe(handler);

    mgr.connect();
    const ws = MockWebSocket.latest();
    ws.simulateOpen();
    ws.simulateMessage(JSON.stringify({ value: 42 }));

    expect(handler).toHaveBeenCalledWith({ value: 42 });

    // Unsubscribe
    unsub();
    ws.simulateMessage(JSON.stringify({ value: 99 }));
    expect(handler).toHaveBeenCalledTimes(1);

    mgr.disconnect();
  });

  it("dispatches messages to multiple subscribers", () => {
    const mgr = new WSManager("orders");
    const h1 = vi.fn();
    const h2 = vi.fn();
    mgr.subscribe(h1);
    mgr.subscribe(h2);

    mgr.connect();
    const ws = MockWebSocket.latest();
    ws.simulateOpen();
    ws.simulateMessage(JSON.stringify({ id: 1 }));

    expect(h1).toHaveBeenCalledWith({ id: 1 });
    expect(h2).toHaveBeenCalledWith({ id: 1 });
    mgr.disconnect();
  });

  it("ignores pong messages", () => {
    const mgr = new WSManager("market");
    const handler = vi.fn();
    mgr.subscribe(handler);

    mgr.connect();
    const ws = MockWebSocket.latest();
    ws.simulateOpen();
    ws.simulateMessage("pong");

    expect(handler).not.toHaveBeenCalled();
    mgr.disconnect();
  });

  it("ignores non-JSON messages", () => {
    const mgr = new WSManager("market");
    const handler = vi.fn();
    mgr.subscribe(handler);

    mgr.connect();
    const ws = MockWebSocket.latest();
    ws.simulateOpen();
    ws.simulateMessage("not json {{{");

    expect(handler).not.toHaveBeenCalled();
    mgr.disconnect();
  });

  it("disconnect closes the WebSocket and prevents reconnect", () => {
    const mgr = new WSManager("portfolio");
    mgr.connect();
    const ws = MockWebSocket.latest();
    ws.simulateOpen();

    mgr.disconnect();
    expect(ws.close).toHaveBeenCalled();

    // Simulate close after disconnect — should NOT reconnect
    const countBefore = MockWebSocket.instances.length;
    vi.advanceTimersByTime(60_000);
    expect(MockWebSocket.instances.length).toBe(countBefore);
  });

  it("auto-reconnects after close with exponential backoff", () => {
    const mgr = new WSManager("portfolio");
    mgr.connect();
    const ws1 = MockWebSocket.latest();
    ws1.simulateOpen();

    // Simulate unexpected close
    ws1.simulateClose();

    // First reconnect after BASE_DELAY (3000ms * 2^0 = 3000ms)
    expect(MockWebSocket.instances.length).toBe(1);
    vi.advanceTimersByTime(3000);
    expect(MockWebSocket.instances.length).toBe(2);

    // Second close — reconnect after 6000ms (3000 * 2^1)
    const ws2 = MockWebSocket.latest();
    ws2.simulateClose();
    vi.advanceTimersByTime(5999);
    expect(MockWebSocket.instances.length).toBe(2);
    vi.advanceTimersByTime(1);
    expect(MockWebSocket.instances.length).toBe(3);

    mgr.disconnect();
  });

  it("resets retry count on successful open", () => {
    const mgr = new WSManager("portfolio");
    mgr.connect();

    // Close and reconnect to increment retries
    MockWebSocket.latest().simulateClose();
    vi.advanceTimersByTime(3000); // reconnect #1
    const ws2 = MockWebSocket.latest();
    ws2.simulateOpen(); // successful open resets retries

    // Close again — delay should be 3000 (base), not 6000
    ws2.simulateClose();
    const countBefore = MockWebSocket.instances.length;
    vi.advanceTimersByTime(3000);
    expect(MockWebSocket.instances.length).toBe(countBefore + 1);

    mgr.disconnect();
  });
});
