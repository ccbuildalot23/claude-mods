export type SkinName = 'labeau' | 'noir' | 'tokyo' | 'off'

declare module 'claude-code' {
  interface PluginState {
    skins: { skin: SkinName }
  }
}
