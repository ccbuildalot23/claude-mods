export type Peek = { url: string; file: string; shotAt: number; error: string }

declare module 'claude-code' {
  interface PluginState {
    'browser-peek': { peek: Peek }
  }
}
