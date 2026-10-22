export type HiddenNames = string[]

declare module 'claude-code' {
  interface PluginState {
    'screen-share': { isOn: boolean; names: HiddenNames }
  }
}
