/** 纯前端数据层的公共类型：与全栈版后端返回的结构保持一致，换回后端时页面不用改。 */

export type EntryRow = {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  [field: string]: string | number | boolean
}

export type ModuleMeta = {
  key: string
  name: string
  entity: string
  desc: string
  fields: string[]
  statuses: string[]
  actions: string[]
  actionTargets: Record<string, string>
  metrics: string[]
}

export type PageResult = {
  items: EntryRow[]
  total: number
  page: number
  size: number
}

export type ActionResult = {
  ok: boolean
  message: string
}

export type OverviewResult = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

/* ---------- 抽取锚点绑定预演 ---------- */

export type RehearsalAnchor = {
  锚点编号: string
  选择器类型: string
  CSS表达式: string
  XPath表达式: string
  文本匹配: string
  元素顺序: string
  status: string
}

export type RehearsalEvaluation = {
  锚点编号: string
  选择器类型: string
  选择器: string
  命中: boolean
  命中数: number
  值: string | null
  节点路径: string
  片段: string
  状态: string
  错误: string
}

export type RehearsalExclusion = {
  锚点编号: string
  值: string | null
  节点路径: string
  原因: string
}

export type RehearsalSample = {
  字段: string
  值: string | null
  来源锚点: string | null
  计入样本: boolean
}

export type RehearsalVersion = {
  页面版本: string
  快照编号: string
  登记时间: string
  evaluations: RehearsalEvaluation[]
  sample: RehearsalSample
  excluded: RehearsalExclusion[]
}

export type RehearsalManifestMatch = {
  锚点编号: string
  选择器: string
  选择器类型: string
  页面版本: string
  节点路径: string
  片段: string
  值: string
  状态: string
  记录时间: string
}

export type RehearsalConfirmed = {
  锚点编号: string
  选择器: string
  页面版本: string
  节点路径: string
  值: string
  确认时间: string
}

export type RehearsalManifest = {
  模板编号: string
  抽取字段: string
  关联脚本: string
  matches: RehearsalManifestMatch[]
  confirmed: RehearsalConfirmed | null
  updated_at: string
}

export type RehearsalView = {
  模板: { 模板编号: string; 抽取字段: string; 关联脚本: string; status: string }
  anchors: RehearsalAnchor[]
  pages: { 页面版本: string; 快照编号: string; 登记时间: string; dom预览: string }[]
  runs: { 页面版本: string; 时间: string; 锚点数: number; 命中数: number; 冲突: boolean }[]
  manifest: RehearsalManifest
  versions: RehearsalVersion[]
  stats: {
    版本数: number
    样本行数: number
    计入样本数: number
    未计入样本数: number
    冲突排除数: number
    已确认来源: boolean
  }
}
