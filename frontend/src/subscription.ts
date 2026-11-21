import type { Hass, HassConnection, HomeworkPayload, Unsubscribe, WsError } from "./types";

export const SUBSCRIBE = "magister/homework/subscribe";
/** Retry of a failed subscribe: 30 s, doubling, at most 10 minutes. */
const RETRY_START_MS = 30_000;
const RETRY_MAX_MS = 600_000;

export type LoadError = "not_found" | "unauthorized" | "load_failed";

/** What a card gives the subscription: where to look, and where to put what arrives. */
export interface SubscriptionHost {
  isConnected(): boolean;
  hass(): Hass | undefined;
  entity(): string | undefined;
  /** A pushed payload (the subscription has already cleared its own error and back-off). */
  onPayload(payload: HomeworkPayload): void;
  onLoadError(error: LoadError): void;
  /** The connection went away (true) or the host should consider itself online (false). */
  onOffline(offline: boolean): void;
  /** True while the last subscribe failed (a reconnect then retries at once). */
  hasLoadError(): boolean;
}

/** Unsubscribe without letting a rejected promise escape. */
export function safeUnsubscribe(unsubscribe: Unsubscribe): void {
  try {
    void Promise.resolve(unsubscribe()).catch(() => undefined);
  } catch {
    // already closed
  }
}

/**
 * The subscription to the homework WebSocket of one entity, shared by the homework card and the
 * timer card: one subscribe call, resubscribe by the connection, a back-off after a failure, and
 * the offline flag.
 */
export class HomeworkSubscription {
  private _connection: HassConnection | undefined;
  private _subscribedEntity = "";
  private _unsubscribe: Unsubscribe | undefined;
  private _generation = 0;
  private _retryTimer: ReturnType<typeof setTimeout> | undefined;
  private _retryDelay = RETRY_START_MS;

  constructor(private readonly host: SubscriptionHost) {}

  private readonly _onDisconnected = (): void => {
    this.host.onOffline(true);
  };

  private readonly _onReady = (): void => {
    this.host.onOffline(false);
    // A reconnect: try again at once after a failed subscribe (a working one is
    // resubscribed by the connection itself).
    if (this.host.hasLoadError()) this.retry();
  };

  /** Back to the first back-off (another entity, or a payload arrived). */
  resetBackoff(): void {
    this._retryDelay = RETRY_START_MS;
  }

  ensure(): void {
    const hass = this.host.hass();
    const entity = this.host.entity();
    if (!this.host.isConnected() || !hass?.connection || !entity) return;
    // Also after a failed subscribe: that is retried on reconnect or after a back-off,
    // not on every hass update.
    if (this._subscribedEntity === entity && this._connection === hass.connection) return;
    this.reset();
    this._attach(hass.connection);
    this._subscribedEntity = entity;
    const generation = ++this._generation;
    hass.connection
      .subscribeMessage<HomeworkPayload>(
        (payload) => {
          if (generation !== this._generation) return;
          this._retryDelay = RETRY_START_MS;
          this.host.onPayload(payload);
        },
        { type: SUBSCRIBE, entity_id: entity },
        { resubscribe: true },
      )
      .then(
        (unsubscribe) => {
          if (generation === this._generation) {
            this._unsubscribe = unsubscribe;
          } else {
            safeUnsubscribe(unsubscribe);
          }
        },
        (error: unknown) => {
          if (generation !== this._generation) return;
          const code = (error as WsError | undefined)?.code;
          this.host.onLoadError(
            code === "not_found" || code === "invalid_format"
              ? "not_found"
              : code === "unauthorized"
                ? "unauthorized"
                : "load_failed",
          );
          this._scheduleRetry();
        },
      );
  }

  private _scheduleRetry(): void {
    if (this._retryTimer) clearTimeout(this._retryTimer);
    this._retryTimer = setTimeout(() => {
      this._retryTimer = undefined;
      this.retry();
    }, this._retryDelay);
    this._retryDelay = Math.min(this._retryDelay * 2, RETRY_MAX_MS);
  }

  retry(): void {
    this.reset();
    this.ensure();
  }

  private _attach(connection: HassConnection): void {
    connection.addEventListener?.("disconnected", this._onDisconnected);
    connection.addEventListener?.("ready", this._onReady);
    this._connection = connection;
    if (connection.connected === false) this.host.onOffline(true);
  }

  /** Unsubscribe (also while the subscribe call is still pending) and forget the connection. */
  reset(): void {
    this._generation++;
    if (this._unsubscribe) safeUnsubscribe(this._unsubscribe);
    this._unsubscribe = undefined;
    if (this._retryTimer) clearTimeout(this._retryTimer);
    this._retryTimer = undefined;
    this._connection?.removeEventListener?.("disconnected", this._onDisconnected);
    this._connection?.removeEventListener?.("ready", this._onReady);
    this._connection = undefined;
    this._subscribedEntity = "";
  }
}
