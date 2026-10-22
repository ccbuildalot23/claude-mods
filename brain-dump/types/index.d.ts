export type BrainDump = { isOn: boolean; original: string; tidy: string; isWorking: boolean; bypass: string }

declare module 'claude-code' {
  interface PluginState {
    'brain-dump': { dump: BrainDump }
  }
}
