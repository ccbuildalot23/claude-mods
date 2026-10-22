export type InventoryFile = { path: string; state: 'read' | 'editing' | 'changed' }
export type Inventory = { isOn: boolean; goal: string; connectors: Record<string, number>; skills: string[]; links: string[]; files: InventoryFile[]; commands: number }

declare module 'claude-code' {
  interface PluginState {
    'chat-inventory': { inv: Inventory }
  }
}
