import { http } from './http'
import type { FileDetail } from '@/types/files'
import type { AiTask, AiTaskCreatePayload, AiTaskListResponse } from '@/types/ai'

export const aiApi = {
  createTask(payload: AiTaskCreatePayload) {
    return http.post<AiTask>('/ai/tasks', payload)
  },
  listTasks(fileId: string, limit = 20) {
    return http.get<AiTaskListResponse>('/ai/tasks', {
      query: {
        file_id: fileId,
        limit
      }
    })
  },
  writeSummary(taskId: string) {
    return http.post<FileDetail>(`/ai/tasks/${encodeURIComponent(taskId)}/write-summary`)
  }
}
