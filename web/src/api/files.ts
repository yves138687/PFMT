import { http } from './http'
import type { FileInfo, MarkdownFileContent, UploadFilePayload } from '@/types/files'

export const filesApi = {
  listFiles(pathId = 'root', showHidden?: boolean) {
    return http.get<FileInfo[]>('/files', {
      query: {
        path_id: pathId,
        show_hidden: showHidden
      }
    })
  },
  uploadFile(payload: UploadFilePayload) {
    const formData = new FormData()
    formData.append('file', payload.file)
    formData.append('path_id', payload.pathId)
    formData.append('encryption_enabled', String(payload.encryptionEnabled))

    if (payload.relativePath) {
      formData.append('relative_path', payload.relativePath)
    }

    return http.post<FileInfo>('/files/upload', formData)
  },
  getMarkdownFile(fileId: string) {
    return http.get<MarkdownFileContent>(`/files/${encodeURIComponent(fileId)}/markdown`)
  }
}

export async function uploadFileApi(pathId: string, file: File) {
  return filesApi.uploadFile({
    file,
    pathId,
    encryptionEnabled: true
  })
}

export function readMarkdownApi(fileId: string) {
  return filesApi.getMarkdownFile(fileId)
}
