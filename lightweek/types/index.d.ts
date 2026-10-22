export type LightweekUntil = number

declare module 'claude-code' {
  interface PluginState {
    lightweek: { until: LightweekUntil }
  }
}
