export type BridgeFresh = { id: string; from: string; topic: string; needsChris: string; file: string }

declare module 'claude-code' {
  interface PluginState {
    'bridge-inbox': { sync: { isAuto: boolean; fresh: BridgeFresh[]; airtable: string; lastRun: string } }
  }
}
