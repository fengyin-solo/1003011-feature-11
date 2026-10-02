<template>
  <section class="page" data-module="demolition">
    <header class="page-head">
      <div>
        <h2>拆站管理管理</h2>
        <p class="page-desc">维护拆站任务，围绕任务编号、拆除站点、拆除原因、拆除范围做登记、筛选与状态流转；拆除完成后按物资类别登记回收数量与去向。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记拆站任务</button>
        <button class="btn" type="button" @click="openBatch()">批量回收登记</button>
        <button class="btn" type="button" @click="exportRows">导出拆站管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="panelOpen" class="panel">
      <div class="panel-head">
        <h3 class="panel-title">批量回收登记（{{ panelTasks.map((t) => t.任务编号).join('、') }}）</h3>
        <button class="btn ghost" type="button" @click="closePanel">收起面板</button>
      </div>
      <p v-for="task in panelTasks" :key="task.task_id" class="panel-hint">
        <template v-if="task.登记完成">{{ task.任务编号 }}：物资回收已登记完</template>
        <template v-else>{{ task.任务编号 }}：还差 {{ task.未登记类别.join('、') }}，从「{{ task.接着填 }}」接着填</template>
      </p>
      <table v-if="panelRows.length" class="data-table">
        <thead>
          <tr>
            <th>行号</th>
            <th>任务编号</th>
            <th>物资类别</th>
            <th>单位</th>
            <th>单价（元）</th>
            <th>登记数量</th>
            <th>回收数量</th>
            <th>差异说明</th>
            <th>物资去向</th>
            <th>预估回收款（元）</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in panelRows" :key="row.行号">
            <td>{{ row.行号 }}</td>
            <td>{{ row.任务编号 }}</td>
            <td>{{ row.物资类别 }}</td>
            <td>{{ row.单位 }}</td>
            <td>{{ row.单价 }}</td>
            <td><input v-model="row.登记数量" class="input-cell" placeholder="应回收" /></td>
            <td><input v-model="row.回收数量" class="input-cell" placeholder="实收" /></td>
            <td><input v-model="row.差异说明" class="input-cell wide" placeholder="实收少于应回收时必填" /></td>
            <td><input v-model="row.物资去向" class="input-cell wide" placeholder="回收商 / 利旧库 / 报废处置" /></td>
            <td>{{ estimated(row) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="panel-hint">所选任务的物资回收都已登记完，没有待填的行。</p>
      <div v-if="panelRows.length" class="panel-actions">
        <button class="btn primary" type="button" @click="submitBatch">提交回收登记</button>
        <span class="panel-hint">缺物资去向的行会被单独退回并标明行号，其余照常落记录。</span>
      </div>
      <p v-if="panelMessage" class="panel-result">{{ panelMessage }}</p>
      <ul v-if="rejectedRows.length" class="panel-rejects">
        <li v-for="item in rejectedRows" :key="item.行号">第 {{ item.行号 }} 行{{ item.原因 }}</li>
      </ul>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>勾选</th>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td><input v-model="selectedIds" type="checkbox" :value="Number(row.id)" /></td>
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="openBatch(row)">回收登记</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无拆站管理数据，可先登记拆站任务</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条拆站管理记录<template v-if="selectedIds.length">，已勾选 {{ selectedIds.length }} 条</template></span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type PanelRow = {
  行号: number
  task_id: number
  任务编号: string
  物资类别: string
  单位: string
  单价: number
  登记数量: string
  回收数量: string
  差异说明: string
  物资去向: string
}
type PanelTask = {
  task_id: number
  任务编号: string
  接着填: string | null
  未登记类别: string[]
  登记完成: boolean
}

const ENDPOINT = '/api/demolition'
const columns = ["任务编号", "拆除站点", "拆除原因", "拆除范围", "施工队伍", "计划工期", "物资回收", "任务状态"]
const actions = ["提交审批", "开始拆除", "回收完成"]
const statuses = ["待审批", "已批复", "拆除中", "已拆除"]
const stats = [{"label": "待审批拆站", "value": 0}, {"label": "拆除中站点", "value": 0}, {"label": "已拆除站点", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const selectedIds = ref<number[]>([])
const panelOpen = ref(false)
const panelRows = ref<PanelRow[]>([])
const panelTasks = ref<PanelTask[]>([])
const panelMessage = ref('')
const rejectedRows = ref<{ 行号: number; 原因: string }[]>([])

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '拆站任务登记入口尚未接入审批流'
}

function estimated(row: PanelRow): string {
  const qty = Number(row.回收数量)
  if (row.回收数量 === '' || !Number.isFinite(qty) || qty < 0) {
    return '—'
  }
  return (qty * Number(row.单价)).toFixed(2)
}

async function openBatch(row?: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  const ids = row ? [Number(row.id)] : selectedIds.value
  if (!ids.length) {
    errorMessage.value = '请先勾选同一批拆站任务，再登记物资回收'
    return
  }
  try {
    const response = await request(`${ENDPOINT}/recycling/preview`, {
      method: 'POST',
      body: JSON.stringify({ task_ids: ids, rows: [] }),
    })
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.detail ?? '待登记物资读取失败')
    }
    panelTasks.value = payload.tasks ?? []
    panelRows.value = (payload.rows ?? []).map((item: Record<string, unknown>) => ({
      ...item,
      登记数量: '',
      回收数量: '',
      差异说明: '',
      物资去向: '',
    })) as PanelRow[]
    panelMessage.value = ''
    rejectedRows.value = []
    panelOpen.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '待登记物资读取失败'
  }
}

function closePanel() {
  panelOpen.value = false
  panelRows.value = []
  panelTasks.value = []
  panelMessage.value = ''
  rejectedRows.value = []
}

async function submitBatch() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/recycling/batch`, {
      method: 'POST',
      body: JSON.stringify({
        task_ids: panelTasks.value.map((task) => task.task_id),
        rows: panelRows.value,
      }),
    })
    const payload = await response.json()
    panelMessage.value = payload.message ?? ''
    rejectedRows.value = payload.entry?.退回 ?? []
    if (payload.ok) {
      noticeMessage.value = payload.message ?? '回收登记已落记录'
      closePanel()
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '回收登记提交失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message || '拆站管理动作未生效，请稍后重试'
      return
    }
    noticeMessage.value = payload.message ?? `拆站任务已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '拆站管理操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('拆站任务列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '拆站管理列表读取失败'
  }
}

onMounted(reload)
</script>
