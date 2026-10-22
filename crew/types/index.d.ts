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
}

declare module 'claude-code' {
  interface PluginState {
    crew: { isOn: boolean; mates: CrewMate[]; hired: number }
  }
}
