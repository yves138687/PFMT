import { http } from './http'
import type {
  DocumentContent,
  DocumentCreatePayload,
  DocumentConvertPayload,
  DocumentMergePayload,
  DocumentSavePayload,
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
  listFiles(pathId = 'root', _showHidden?: boolean) {
    return http.get<FileInfo[]>('/files', {
      query: {
        path_id: pathId
      }
    })
  },
  searchFiles(query: string, _showHidden?: boolean, limit = 50) {
    return http.get<FileSearchResponse>('/files/search', {
      query: {
        q: query,
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
  getFileDetail(fileId: string, _showHidden?: boolean) {
    return http.get<FileDetail>(`/files/${encodeURIComponent(fileId)}`)
  },
  updateFile(fileId: string, payload: FileUpdatePayload, _showHidden?: boolean) {
    return http.patch<FileDetail>(`/files/${encodeURIComponent(fileId)}`, payload)
  },
  updateFileRemark(fileId: string, remark: string | null, showHidden?: boolean) {
    return filesApi.updateFile(fileId, { remark }, showHidden)
  },
  updateFileTags(fileId: string, tagNames: string[], _showHidden?: boolean) {
    return http.put<FileDetail>(
      `/files/${encodeURIComponent(fileId)}/tags`,
      {
        tag_names: tagNames
      }
    )
  },
  moveFile(fileId: string, pathId: string, _showHidden?: boolean) {
    return http.patch<FileDetail>(
      `/files/${encodeURIComponent(fileId)}/move`,
      {
        path_id: pathId
      }
    )
  },
  deleteFile(fileId: string, _showHidden?: boolean) {
    return http.delete<void>(`/files/${encodeURIComponent(fileId)}`)
  },
  exportFile(fileId: string, _showHidden?: boolean) {
    return http.blobResponse(`/files/${encodeURIComponent(fileId)}/export`, {
      method: 'GET'
    })
  },
  exportFiles(fileIds: string[], _showHidden?: boolean) {
    return http.blobResponse('/files/export', {
      method: 'POST',
      body: {
        file_ids: fileIds
      }
    })
  },
  getMarkdownFile(fileId: string, _showHidden?: boolean) {
    return http.get<MarkdownFileContent>(`/files/${encodeURIComponent(fileId)}/markdown`)
  },
  getTextFile(fileId: string, _showHidden?: boolean) {
    return http.get<TextFileContent>(`/files/${encodeURIComponent(fileId)}/text`)
  },
  getPreviewBlob(fileId: string, _showHidden?: boolean) {
    return http.blob(`/files/${encodeURIComponent(fileId)}/preview`)
  },
  issuePreviewToken(fileId: string, _showHidden?: boolean) {
    return http.post<FilePreviewToken>(`/files/${encodeURIComponent(fileId)}/preview-token`)
  },
  getDocument(fileId: string, _showHidden?: boolean) {
    return http.get<DocumentContent>(`/files/${encodeURIComponent(fileId)}/document`)
  },
  createDocument(payload: DocumentCreatePayload) {
    return http.post<FileDetail>('/files/document', payload)
  },
  saveDocument(fileId: string, payload: DocumentSavePayload, _showHidden?: boolean) {
    return http.put<DocumentContent>(`/files/${encodeURIComponent(fileId)}/document`, payload)
  },
  convertDocument(fileId: string, payload: DocumentConvertPayload, _showHidden?: boolean) {
    return http.post<FileDetail>(`/files/${encodeURIComponent(fileId)}/convert`, payload)
  },
  mergeDocuments(payload: DocumentMergePayload, _showHidden?: boolean) {
    return http.post<FileDetail>('/files/merge', payload)
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
