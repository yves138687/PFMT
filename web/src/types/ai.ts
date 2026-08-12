export type AiTaskType = 'summary' | 'qa' | 'polish' | 'translate' | 'continue'
export type AiTaskStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled'

export interface AiTaskCreatePayload {
  file_id: string
  task_type: AiTaskType
  prompt?: string | null
  selected_text?: string | null
  provider_id?: string | null
}

export interface AiReadScope {
  current_document?: string
  document_format?: string
  selected_range?: string | null
  includes_hidden_content?: boolean
  context_truncated?: boolean
}

export interface AiTask {
  task_id: string
  task_type: AiTaskType | string
  task_status: AiTaskStatus
  answer?: string | null
  read_scope: string
  model_provider?: string | null
  model_name?: string | null
  error_message?: string | null
  created_at: string
  completed_at?: string | null
}

export interface AiTaskListResponse {
  items: AiTask[]
  total: number
}
