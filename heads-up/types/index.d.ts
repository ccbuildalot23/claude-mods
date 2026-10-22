export type HeadsUp = { isOn: boolean; note: string }

declare module 'claude-code' {
  interface PluginState {
    'heads-up': { state: HeadsUp }
  }
}
