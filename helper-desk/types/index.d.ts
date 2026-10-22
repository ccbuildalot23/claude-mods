export type HelperTodo = { id: string; label: string; status: 'pending' | 'in_progress' | 'completed' }
export type Helper = { id: string; label: string; type: string; isDone: boolean; tokens: number; dollars: number; startedAt: number; endedAt: number }

declare module 'claude-code' {
  interface PluginState {
    'helper-desk': { isOn: boolean; todos: HelperTodo[]; helpers: Helper[] }
  }
}
