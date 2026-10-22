export type NeedsYouOn = boolean

declare module 'claude-code' {
  interface PluginState {
    'needs-you': { isOn: NeedsYouOn }
  }
}
