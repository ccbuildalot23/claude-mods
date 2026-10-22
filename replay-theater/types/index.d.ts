export type ReplayEdit = { path: string; diff: string; turn: number }
export type Replay = { isOn: boolean; edits: ReplayEdit[]; turn: number; at: number; lastTurnEdits: number }

declare module 'claude-code' {
  interface PluginState {
    'replay-theater': { replay: Replay }
  }
}
