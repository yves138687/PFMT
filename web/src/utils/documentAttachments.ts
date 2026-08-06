/**
 * 文档附件目录工具。
 *
 * 文档图片/附件统一上传到文档所在目录下的「附件」子目录；
 * 同目录下不同文档的附件共用该目录，首次使用时自动创建。
 */

import { pathsApi } from '@/api/paths'
import type { FilePathNode } from '@/types/files'

export const ATTACHMENT_FOLDER_NAME = '附件'

function findNode(nodes: FilePathNode[], pathId: string): FilePathNode | null {
  for (const node of nodes) {
    if (node.path_id === pathId) {
      return node
    }
    const child = findNode(node.children ?? [], pathId)
    if (child) {
      return child
    }
  }
  return null
}

/** 在父目录下查找「附件」子目录；不存在则自动创建，并继承父目录隐藏状态。 */
export async function ensureAttachmentFolder(parentPathId: string, showHidden: boolean): Promise<string> {
  const tree = await pathsApi.getPathTree(showHidden)
  const parent = findNode(tree, parentPathId) ?? { path_id: parentPathId, is_hidden: false } as FilePathNode
  const existing = (parent.children ?? []).find((child) => child.path_name === ATTACHMENT_FOLDER_NAME)
  if (existing) {
    return existing.path_id
  }
  try {
    const created = await pathsApi.createPath({
      path_name: ATTACHMENT_FOLDER_NAME,
      parent_path_id: parentPathId,
      description: '文档附件',
      is_hidden: parent.is_hidden
    })
    return created.path_id
  } catch {
    // 并发创建冲突等场景：重查一次，若已存在则复用。
    const refreshed = await pathsApi.getPathTree(showHidden)
    const refreshedParent = findNode(refreshed, parentPathId)
    const createdNow = (refreshedParent?.children ?? []).find((child) => child.path_name === ATTACHMENT_FOLDER_NAME)
    if (createdNow) {
      return createdNow.path_id
    }
    throw new Error('创建附件目录失败')
  }
}
