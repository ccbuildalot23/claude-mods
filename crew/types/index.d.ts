export type CrewTodo = { label: string; status: 'pending' | 'in_progress' | 'completed' }
export type CrewMate = {
  id: string
  name: string
  glyph: string
  color: string
  task: string
  type: string
  doing: string
  steps: number
  todos: CrewTodo[]
  status: 'working' | 'done' | 'failed'
  startedAt: number
  endedAt: number
  // Taken over from helper-desk (Oct 24): what the agent used, at API-equivalent list prices.
  tokens?: number
  dollars?: number
}

declare module 'claude-code' {
  interface PluginState {
    crew: { isOn: boolean; mates: CrewMate[]; hired: number }
  }
}
