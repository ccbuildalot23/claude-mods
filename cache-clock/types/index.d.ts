export type CacheClock = { lastTurnAt: number; contextTokens: number; keepWarmUntil: number; pings: number }

declare module 'claude-code' {
  interface PluginState {
    'cache-clock': { isOn: boolean; clock: CacheClock }
  }
}
