import { http } from './http'
import type { FileDetail, FileInfo, MarkdownFileContent, UploadFilePayload } from '@/types/files'

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
  getFileDetail(fileId: string, showHidden?: boolean) {
    return http.get<FileDetail>(`/files/${encodeURIComponent(fileId)}`, {
      query: {
        show_hidden: showHidden
      }
    })
  },
  updateFileRemark(fileId: string, remark: string | null, showHidden?: boolean) {
    return http.patch<FileDetail>(
      `/files/${encodeURIComponent(fileId)}`,
      {
        remark
      },
      {
        query: {
          show_hidden: showHidden
        }
      }
    )
  },
  moveFile(fileId: string, pathId: string, showHidden?: boolean) {
    return http.patch<FileDetail>(
      `/files/${encodeURIComponent(fileId)}/move`,
      {
        path_id: pathId
      },
      {
        query: {
          show_hidden: showHidden
        }
      }
    )
  },
  deleteFile(fileId: string, showHidden?: boolean) {
    return http.delete<void>(`/files/${encodeURIComponent(fileId)}`, {
      query: {
        show_hidden: showHidden
      }
    })
  },
  getMarkdownFile(fileId: string, showHidden?: boolean) {
    return http.get<MarkdownFileContent>(`/files/${encodeURIComponent(fileId)}/markdown`, {
      query: {
        show_hidden: showHidden
      }
    })
  }
}

export async function uploadFileApi(pathId: string, file: File) {
  return filesApi.uploadFile({
    file,
    pathId,
    encryptionEnabled: true
  })
}

export function readMarkdownApi(fileId: string, showHidden?: boolean) {
  return filesApi.getMarkdownFile(fileId, showHidden)
}
