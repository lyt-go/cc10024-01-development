<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "行为脚本", "created": 0, "pending": 0, "abnormal": 0}, {"name": "元素定位", "created": 0, "pending": 0, "abnormal": 0}, {"name": "数据抽取", "created": 0, "pending": 0, "abnormal": 0}, {"name": "清洗管道", "created": 0, "pending": 0, "abnormal": 0}, {"name": "转换规则", "created": 0, "pending": 0, "abnormal": 0}, {"name": "质量防护", "created": 0, "pending": 0, "abnormal": 0}, {"name": "脚本调度", "created": 0, "pending": 0, "abnormal": 0}, {"name": "登录凭证", "created": 0, "pending": 0, "abnormal": 0}, {"name": "页面快照", "created": 0, "pending": 0, "abnormal": 0}, {"name": "错误恢复", "created": 0, "pending": 0, "abnormal": 0}, {"name": "页面去重", "created": 0, "pending": 0, "abnormal": 0}, {"name": "字段归一化", "created": 0, "pending": 0, "abnormal": 0}, {"name": "批次队列", "created": 0, "pending": 0, "abnormal": 0}, {"name": "画布配置", "created": 0, "pending": 0, "abnormal": 0}, {"name": "导出通道", "created": 0, "pending": 0, "abnormal": 0}, {"name": "运行历史", "created": 0, "pending": 0, "abnormal": 0}, {"name": "Schema校验", "created": 0, "pending": 0, "abnormal": 0}, {"name": "内容缓存", "created": 0, "pending": 0, "abnormal": 0}]
  }
})
</script>
