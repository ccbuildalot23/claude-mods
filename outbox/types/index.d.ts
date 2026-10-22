export type Held = { id: string; tool: string; digest: string; summary: string; at: string }

declare module 'claude-code' {
  interface PluginState {
    outbox: { held: Held[]; released: string[] }
  }
}
