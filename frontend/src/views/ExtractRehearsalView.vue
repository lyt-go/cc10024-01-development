<template>
  <section class="page" data-module="extract_rehearsal">
    <header class="page-head">
      <div>
        <h2>抽取锚点绑定预演</h2>
        <p class="page-desc">
          在页面快照上核对抽取字段的锚点来源：DOM 片段与字段的实际匹配写入字段定位清单，
          提交预演后每个字段只确立一个可执行来源；未确认的绑定只保留候选值，样本不计入抽取成功。
        </p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/data_extract" data-testid="back-to-extract">返回数据抽取</RouterLink>
      </div>
    </header>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>抽取模板</span>
        <select v-model="templateCode" data-testid="template-select" @change="reload">
          <option v-for="item in templates" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" data-testid="reload" type="submit">刷新视图</button>
    </form>

    <div v-if="view" class="stat-row">
      <article class="stat-card">
        <span class="stat-label">页面版本数</span>
        <strong class="stat-value">{{ view.stats.版本数 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">样本行数</span>
        <strong class="stat-value">{{ view.stats.样本行数 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">计入样本（抽取成功）</span>
        <strong class="stat-value">{{ view.stats.计入样本数 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">冲突排除</span>
        <strong class="stat-value">{{ view.stats.冲突排除数 }}</strong>
      </article>
    </div>

    <template v-if="view">
      <!-- 字段定位清单 -->
      <section class="panel" data-testid="manifest-panel">
        <h3>字段定位清单 · {{ view.模板.抽取字段 }}</h3>
        <p v-if="view.manifest.confirmed" class="confirmed-banner" data-testid="confirmed-banner">
          可执行来源：{{ view.manifest.confirmed.锚点编号 }}
          <code>{{ view.manifest.confirmed.选择器 }}</code>
          ｜采纳值 <strong>{{ view.manifest.confirmed.值 }}</strong>
          ｜来源版本 {{ view.manifest.confirmed.页面版本 }}
          ｜节点 {{ view.manifest.confirmed.节点路径 }}
          ｜确认于 {{ view.manifest.confirmed.确认时间 }}
        </p>
        <p v-else class="pending-banner" data-testid="pending-banner">
          尚未确认绑定：候选值与来源已保留，样本不能按抽取成功计数。
        </p>
        <table class="data-table">
          <thead>
            <tr>
              <th>页面版本</th><th>锚点编号</th><th>选择器</th><th>值</th>
              <th>节点路径</th><th>DOM 片段</th><th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(m, i) in view.manifest.matches" :key="i" :data-status="m.状态">
              <td>{{ m.页面版本 }}</td>
              <td>{{ m.锚点编号 }}</td>
              <td><code>{{ m.选择器 }}</code></td>
              <td>{{ m.值 }}</td>
              <td class="mono">{{ m.节点路径 }}</td>
              <td class="mono frag">{{ m.片段 }}</td>
              <td><span class="badge" :class="statusClass(m.状态)">{{ m.状态 }}</span></td>
            </tr>
            <tr v-if="!view.manifest.matches.length">
              <td colspan="7" class="empty-state">尚无匹配记录，请先运行预演</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 预演运行 -->
      <section class="panel" data-testid="run-panel">
        <h3>预演运行</h3>
        <div class="run-bar">
          <label class="filter-item">
            <span>页面版本</span>
            <select v-model="runVersion" data-testid="run-version">
              <option v-for="p in view.pages" :key="p.页面版本" :value="p.页面版本">
                {{ p.页面版本 }}（{{ p.快照编号 }}）
              </option>
            </select>
          </label>
          <button class="btn primary" type="button" data-testid="run-rehearsal" :disabled="!runVersion" @click="doRun">
            运行预演
          </button>
          <span class="hint">运行后 DOM 片段与字段的实际匹配写入字段定位清单</span>
        </div>
        <table v-if="currentVersion" class="data-table">
          <thead>
            <tr>
              <th>锚点编号</th><th>选择器</th><th>命中</th><th>值</th>
              <th>节点路径</th><th>DOM 片段</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="eva in currentVersion.evaluations" :key="eva.锚点编号" :data-testid="`eval-${eva.锚点编号}`">
              <td>{{ eva.锚点编号 }}</td>
              <td><code>{{ eva.选择器 }}</code></td>
              <td>{{ eva.命中 ? `命中（共${eva.命中数}个）` : (eva.错误 || '未命中') }}</td>
              <td>{{ eva.值 ?? '—' }}</td>
              <td class="mono">{{ eva.节点路径 || '—' }}</td>
              <td class="mono frag">{{ eva.片段 || '—' }}</td>
              <td><span class="badge" :class="statusClass(eva.状态)">{{ eva.状态 }}</span></td>
              <td>
                <button
                  v-if="eva.命中 && eva.状态 !== '已采纳'"
                  class="link"
                  type="button"
                  :data-testid="`confirm-${eva.锚点编号}`"
                  @click="doConfirm(eva.锚点编号)"
                >
                  采纳此来源
                </button>
                <span v-else-if="eva.状态 === '已采纳'">已确立</span>
                <span v-else>—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 每版实际获得的值 -->
      <section class="panel" data-testid="version-values-panel">
        <h3>每版实际获得的值</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>页面版本</th><th>实际获得值</th><th>来源锚点</th><th>计入样本</th><th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in view.versions" :key="v.页面版本" :data-testid="`sample-${v.页面版本}`">
              <td>{{ v.页面版本 }}</td>
              <td>{{ v.sample.值 ?? '未获得' }}</td>
              <td>{{ v.sample.来源锚点 ?? '—' }}</td>
              <td>
                <span class="badge" :class="v.sample.计入样本 ? 'ok' : 'muted'">
                  {{ v.sample.计入样本 ? '计入' : '不计入' }}
                </span>
              </td>
              <td>{{ sampleNote(v) }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 冲突排除 -->
      <section class="panel" data-testid="excluded-panel">
        <h3>因冲突未进入样本的匹配</h3>
        <table class="data-table">
          <thead>
            <tr><th>页面版本</th><th>锚点编号</th><th>候选值</th><th>节点路径</th><th>原因</th></tr>
          </thead>
          <tbody>
            <template v-for="v in view.versions" :key="v.页面版本">
              <tr v-for="(e, i) in v.excluded" :key="`${v.页面版本}-${i}`">
                <td>{{ v.页面版本 }}</td>
                <td>{{ e.锚点编号 }}</td>
                <td>{{ e.值 ?? '—' }}</td>
                <td class="mono">{{ e.节点路径 }}</td>
                <td><span class="badge warn">{{ e.原因 }}</span></td>
              </tr>
            </template>
            <tr v-if="!view.stats.冲突排除数">
              <td colspan="5" class="empty-state">没有被冲突排除的匹配</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 录入页面版本 -->
      <section class="panel" data-testid="register-panel">
        <h3>录入页面版本</h3>
        <form class="register-form" @submit.prevent="doRegister">
          <label class="filter-item">
            <span>页面版本</span>
            <input v-model="newVersion" data-testid="new-version" placeholder="如 product-v2" required />
          </label>
          <label class="filter-item dom-input">
            <span>页面 DOM</span>
            <textarea v-model="newDom" data-testid="new-dom" rows="5" placeholder="粘贴页面 DOM 快照全文" required></textarea>
          </label>
          <div class="page-actions">
            <button class="btn ghost" type="button" data-testid="fill-sample" @click="fillSample">
              填入示例第二版
            </button>
            <button class="btn primary" type="submit" data-testid="register-page" :disabled="registering">
              {{ registering ? '录入中…' : '录入并预演' }}
            </button>
          </div>
        </form>
      </section>
    </template>

    <footer class="page-foot">
      <span v-if="message" class="ok-text">{{ message }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  confirmRehearsal,
  listEntries,
  loadRehearsal,
  loadRehearsalSampleDom,
  registerRehearsalPage,
  runRehearsal,
} from '@/api/backend-service'
import type { RehearsalVersion, RehearsalView } from '@/data/types'

const templates = ref<string[]>([])
const templateCode = ref('')
const view = ref<RehearsalView | null>(null)
const runVersion = ref('')
const newVersion = ref('')
const newDom = ref('')
const registering = ref(false)
const message = ref('')
const errorMessage = ref('')

const currentVersion = computed<RehearsalVersion | null>(() => {
  if (!view.value) return null
  return view.value.versions.find((v) => v.页面版本 === runVersion.value) ?? null
})

function statusClass(status: string): string {
  if (status === '已采纳') return 'ok'
  if (status === '冲突未采纳') return 'warn'
  if (status === '候选') return 'info'
  return 'muted'
}

function sampleNote(v: RehearsalVersion): string {
  if (v.sample.计入样本) return '已确认来源命中，计入抽取成功'
  if (!v.sample.来源锚点) return '绑定未确认，候选值不计入样本'
  return '已确认来源在此版本未命中，不计入样本'
}

async function reload() {
  errorMessage.value = ''
  try {
    view.value = await loadRehearsal(templateCode.value)
    if (!view.value.versions.some((v) => v.页面版本 === runVersion.value)) {
      runVersion.value = view.value.versions.at(-1)?.页面版本 ?? ''
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '预演视图读取失败'
  }
}

async function doRun() {
  message.value = ''
  errorMessage.value = ''
  try {
    const result = await runRehearsal(templateCode.value, runVersion.value)
    if (!result.ok) throw new Error(result.message)
    message.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '预演运行失败'
  }
}

async function doConfirm(anchor: string) {
  message.value = ''
  errorMessage.value = ''
  try {
    const result = await confirmRehearsal(templateCode.value, runVersion.value, anchor)
    if (!result.ok) throw new Error(result.message)
    message.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '确认来源失败'
  }
}

async function fillSample() {
  errorMessage.value = ''
  try {
    const sample = await loadRehearsalSampleDom()
    newVersion.value = sample.页面版本
    newDom.value = sample.dom
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '示例页面读取失败'
  }
}

async function doRegister() {
  registering.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    const result = await registerRehearsalPage(templateCode.value, newVersion.value, newDom.value)
    if (!result.ok) throw new Error(result.message)
    // 录入后立即在新版本上跑预演，让匹配写入字段定位清单
    const run = await runRehearsal(templateCode.value, newVersion.value)
    if (!run.ok) throw new Error(run.message)
    message.value = `${result.message}；${run.message}`
    runVersion.value = newVersion.value
    newVersion.value = ''
    newDom.value = ''
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '页面版本录入失败'
  } finally {
    registering.value = false
  }
}

onMounted(async () => {
  errorMessage.value = ''
  try {
    const page = await listEntries('data_extract')
    templates.value = page.items.map((row) => String(row['模板编号']))
    templateCode.value = templates.value.includes('DATA-0004')
      ? 'DATA-0004'
      : (templates.value[0] ?? '')
    if (templateCode.value) await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模板列表读取失败'
  }
})
</script>

<style scoped>
.panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 14px;
}
.panel h3 {
  margin: 0 0 10px;
  font-size: 14px;
}
.mono {
  font-family: ui-monospace, monospace;
  font-size: 12px;
}
.frag {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
code {
  background: #f0f2f5;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 12px;
}
.badge {
  display: inline-block;
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 12px;
  background: #e2e8f0;
  color: #475569;
}
.badge.ok { background: #dcfce7; color: #15803d; }
.badge.warn { background: #fee2e2; color: #b42318; }
.badge.info { background: #dbeafe; color: #1d4ed8; }
.badge.muted { background: #e2e8f0; color: #64748b; }
.confirmed-banner {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
}
.pending-banner {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
}
.run-bar {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  margin-bottom: 10px;
}
.hint {
  color: var(--muted);
  font-size: 12px;
}
.register-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dom-input textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  font-family: ui-monospace, monospace;
  font-size: 12px;
}
.ok-text {
  color: #15803d;
}
select {
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
</style>
