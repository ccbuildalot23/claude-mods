export type Blocked = { id: string; where: string; problem: string; digest: string }

declare module 'claude-code' {
  interface PluginState {
    'privacy-preflight': { blocked: Blocked[]; allowed: string[] }
  }
}
