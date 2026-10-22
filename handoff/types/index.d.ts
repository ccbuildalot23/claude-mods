export type HandoffState = { isOn: boolean; contextTokens: number; lastTurnAt: number; isDismissed: boolean; lastText: string; lastPath: string }

declare module 'claude-code' {
  interface PluginState {
    handoff: { state: HandoffState }
  }
}
