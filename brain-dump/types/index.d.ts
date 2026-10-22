export type DumpKind = 'dump' | 'private' | 'line'

export type BrainDump = {
  isOn: boolean
  kind: DumpKind
  original: string
  tidy: string
  isWorking: boolean
  bypass: string
  passNext: boolean
  notice: string
}

export type SavedDump = { path: string; name: string; preview: string; mtimeMs: number }

declare module 'claude-code' {
  interface PluginState {
    'brain-dump': { dump: BrainDump; saved: SavedDump[] }
  }
}
