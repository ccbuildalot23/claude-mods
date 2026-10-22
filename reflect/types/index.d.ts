export type ReflectState = { isOn: boolean; candidate: string; savedCount: number }

declare module 'claude-code' {
  interface PluginState {
    reflect: { state: ReflectState }
  }
}
