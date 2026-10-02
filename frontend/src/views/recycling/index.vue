<template>
  <section class="page" data-module="recycling">
    <header class="page-head">
      <div>
        <h2>物资去向清单</h2>
        <p class="page-desc">拆站物资每落一条回收登记，清单跟着多出一条；回收款按物资类别单价结算。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出物资去向清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>任务编号</span>
        <input v-model="filters.keyword" placeholder="按任务编号检索" />
      </label>
      <label class="filter-item">
        <span>物资类别</span>
        <select v-model="filters.category">
          <option value="">全部类别</option>
          <option v-for="item in catalog" :key="item.物资类别" :value="item.物资类别">
            {{ item.物资类别 }}（{{ item.单价 }}元/{{ item.单位 }}）
          </option>
        </select>
      </label>
      <label class="filter-item">
        <span>物资去向</span>
        <input v-model="filters.destination" placeholder="按物资去向检索" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length" class="empty-state">暂无物资回收记录，可先在拆站管理里批量登记</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条物资回收记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | null>
type CatalogItem = { 物资类别: string; 单位: string; 单价: number }

const ENDPOINT = '/api/recycling'
const columns = ["记录编号", "任务编号", "拆除站点", "物资类别", "单位", "登记数量", "回收数量", "差异说明", "单价", "回收款", "物资去向", "登记时间"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const catalog = ref<CatalogItem[]>([])
const filters = ref<Record<string, string>>({ keyword: '', category: '', destination: '' })
const stats = ref([
  { label: '回收记录', value: 0 },
  { label: '回收款合计（元）', value: 0 },
  { label: '差异笔数', value: 0 },
])

function resetFilters() {
  filters.value = { keyword: '', category: '', destination: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(
    Object.entries(filters.value).filter(([, value]) => value),
  ).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('物资去向清单读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '物资去向清单读取失败'
  }
}

onMounted(async () => {
  await reload()
  try {
    const summary = await fetchJson<{ 记录数: number; 回收款合计: number; 差异笔数: number }>(`${ENDPOINT}/summary`)
    stats.value = [
      { label: '回收记录', value: summary.记录数 },
      { label: '回收款合计（元）', value: summary.回收款合计 },
      { label: '差异笔数', value: summary.差异笔数 },
    ]
    const data = await fetchJson<{ items: CatalogItem[] }>(`${ENDPOINT}/catalog`)
    catalog.value = data.items
  } catch {
    errorMessage.value = '回收汇总读取失败，统计卡与类别选项暂未更新'
  }
})
</script>
