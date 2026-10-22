export type SwitchboardSeen = { name: string; provenance: string }[]

declare module 'claude-code' {
  interface PluginState {
    switchboard: { off: string[]; seen: SwitchboardSeen; blocked: string[] }
  }
}
