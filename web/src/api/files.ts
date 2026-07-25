import { http } from './http'
import type {
  FileDetail,
  FileInfo,
  FilePreviewToken,
  FileSearchResponse,
  FileTag,
  FileUpdatePayload,
  MarkdownFileContent,
  TextFileContent,
  UploadFilePayload
} from '@/types/files'

export const filesApi = {
  listFiles(pathId = 'root', showHidden?: boolean) {
    return http.get<FileInfo[]>('/files', {
      query: {
        path_id: pathId,
        show_hidden: showHidden
      }
    })
  },
  searchFiles(query: string, showHidden?: boolean, limit = 50) {
    return http.get<FileSearchResponse>('/files/search', {
      query: {
        q: query,
        show_hidden: showHidden,
        limit
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
  updateFile(fileId: string, payload: FileUpdatePayload, showHidden?: boolean) {
    return http.patch<FileDetail>(
      `/files/${encodeURIComponent(fileId)}`,
      payload,
      {
        query: {
          show_hidden: showHidden
        }
      }
    )
  },
  updateFileRemark(fileId: string, remark: string | null, showHidden?: boolean) {
    return filesApi.updateFile(fileId, { remark }, showHidden)
  },
  updateFileTags(fileId: string, tagNames: string[], showHidden?: boolean) {
    return http.put<FileDetail>(
      `/files/${encodeURIComponent(fileId)}/tags`,
      {
        tag_names: tagNames
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
  },
  getTextFile(fileId: string, showHidden?: boolean) {
    return http.get<TextFileContent>(`/files/${encodeURIComponent(fileId)}/text`, {
      query: {
        show_hidden: showHidden
      }
    })
  },
  getPreviewBlob(fileId: string, showHidden?: boolean) {
    return http.blob(`/files/${encodeURIComponent(fileId)}/preview`, {
      query: {
        show_hidden: showHidden
      }
    })
  },
  issuePreviewToken(fileId: string, showHidden?: boolean) {
    return http.post<FilePreviewToken>(`/files/${encodeURIComponent(fileId)}/preview-token`, undefined, {
      query: {
        show_hidden: showHidden
      }
    })
  }
}

export const tagsApi = {
  listTags() {
    return http.get<FileTag[]>('/tags')
  },
  createTag(tagName: string, tagColor?: string | null) {
    return http.post<FileTag>('/tags', {
      tag_name: tagName,
      tag_color: tagColor
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
