<template>
  <section class="page" data-module="demolition">
    <header class="page-head">
      <div>
        <h2>拆站管理管理</h2>
        <p class="page-desc">维护拆站任务，围绕任务编号、拆除站点、拆除原因、拆除范围做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记拆站任务</button>
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

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-if="row.status === '拆除中'"
              class="link"
              type="button"
              @click="openRecycling(row)"
            >
              物资回收
            </button>
            <button
              v-for="action in availableActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无拆站管理数据，可先登记拆站任务</td>
        </tr>
      </tbody>
    </table>

    <section class="ledger-section">
      <header class="ledger-head">
        <h3>物资去向清单</h3>
        <span>共 {{ ledgerTotal }} 条，合计回收款 ¥{{ ledgerAmount.toFixed(2) }}</span>
      </header>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in ledgerColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in ledgerRows" :key="String(row.id)">
            <td v-for="column in ledgerColumns" :key="column">{{ row[column] ?? '—' }}</td>
          </tr>
          <tr v-if="!ledgerRows.length">
            <td :colspan="ledgerColumns.length" class="empty-state">暂无回收登记记录</td>
          </tr>
        </tbody>
      </table>
    </section>

    <footer class="page-foot">
      <span>共 {{ total }} 条拆站管理记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="panelEntry" class="recycling-mask" @click.self="closePanel">
      <div class="recycling-panel">
        <header class="panel-head">
          <h3>物资回收登记 — {{ panelEntry['任务编号'] }}（{{ panelEntry['拆除站点'] }}）</h3>
          <button class="btn ghost" type="button" @click="closePanel">关闭</button>
        </header>
        <p class="panel-tip">
          已登记的行已锁定；从第一个未登记的类别接着填，可一次勾选多行批量登记，回收款按类别单价结算。
        </p>
        <table class="data-table panel-table">
          <thead>
            <tr>
              <th></th>
              <th>物资类别</th>
              <th>登记数量</th>
              <th>单价(元)</th>
              <th>回收数量</th>
              <th>去向</th>
              <th>差异说明</th>
              <th>回收款(元)</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in panelRows" :key="row.物资类别" :class="{ settled: row.已登记 }">
              <td>
                <input v-model="row.checked" type="checkbox" :disabled="row.已登记" />
              </td>
              <td>{{ row.物资类别 }}</td>
              <td>{{ row.登记数量 }} {{ row.单位 }}</td>
              <td>{{ row.单价 }}</td>
              <td>
                <span v-if="row.已登记">{{ row.回收数量 }}</span>
                <input v-else v-model="row.回收数量" type="number" min="0" class="cell-input" />
              </td>
              <td>
                <span v-if="row.已登记">{{ row.去向 }}</span>
                <input v-else v-model="row.去向" class="cell-input" placeholder="必填" />
              </td>
              <td>
                <span v-if="row.已登记">{{ row.差异说明 || '—' }}</span>
                <input
                  v-else
                  v-model="row.差异说明"
                  class="cell-input"
                  :class="{ required: needNote(row) }"
                  placeholder="少于登记数量时必填"
                />
              </td>
              <td>{{ row.已登记 ? row.回收款 : previewAmount(row) }}</td>
              <td>{{ row.已登记 ? '已登记' : '待登记' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="rejectedRows.length" class="rejected-box">
          <p>以下行被退回，请修正后重新提交：</p>
          <ul>
            <li v-for="item in rejectedRows" :key="item.row">第 {{ item.row }} 行：{{ item.reason }}</li>
          </ul>
        </div>
        <footer class="panel-foot">
          <span>本次勾选合计回收款：¥{{ checkedAmount.toFixed(2) }}</span>
          <span v-if="panelMessage" class="panel-message">{{ panelMessage }}</span>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitRecycling">
            批量登记回收
          </button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>

interface MaterialRow {
  物资类别: string
  单位: string
  登记数量: number
  单价: number
  回收数量: number | string | null
  去向: string
  差异说明: string
  回收款: number | null
  已登记: boolean
  checked: boolean
}

interface RejectedRow {
  row: number
  reason: string
}

const ENDPOINT = '/api/demolition'
const columns = ["任务编号", "拆除站点", "拆除原因", "拆除范围", "施工队伍", "计划工期", "物资回收", "任务状态"]
const ledgerColumns = ["任务编号", "拆除站点", "物资类别", "回收数量", "单价", "回收款", "去向", "差异说明", "登记时间"]
const STATUS_ACTIONS: Record<string, string[]> = {
  待审批: ["提交审批"],
  已批复: ["开始拆除"],
  拆除中: ["回收完成"],
  已拆除: [],
}
const stats = [{"label": "待审批拆站", "value": 0}, {"label": "拆除中站点", "value": 0}, {"label": "已拆除站点", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const ledgerRows = ref<Row[]>([])
const ledgerTotal = ref(0)
const ledgerAmount = computed(() =>
  ledgerRows.value.reduce((sum, row) => sum + Number(row['回收款'] ?? 0), 0),
)

const panelEntry = ref<Row | null>(null)
const panelRows = ref<MaterialRow[]>([])
const rejectedRows = ref<RejectedRow[]>([])
const panelMessage = ref('')
const submitting = ref(false)

const checkedAmount = computed(() =>
  panelRows.value
    .filter((row) => row.checked && !row.已登记)
    .reduce((sum, row) => sum + (Number(row.回收数量) || 0) * row.单价, 0),
)

function availableActions(row: Row): string[] {
  return STATUS_ACTIONS[String(row.status)] ?? []
}

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

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '拆站管理动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '拆站管理操作失败'
  }
}

async function openRecycling(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('拆站任务明细读取失败')
    }
    const entry = await response.json()
    panelEntry.value = entry
    const materials: any[] = entry['物资清单'] ?? []
    // 中断续填：默认勾选第一个还没登记的类别，已登记的行锁定
    const firstOpen = materials.findIndex((item) => !item['已登记'])
    panelRows.value = materials.map((item, index) => ({
      ...item,
      checked: index === firstOpen,
    }))
    rejectedRows.value = []
    panelMessage.value = ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '拆站任务明细读取失败'
  }
}

function closePanel() {
  panelEntry.value = null
  panelRows.value = []
  rejectedRows.value = []
  panelMessage.value = ''
}

function needNote(row: MaterialRow): boolean {
  const quantity = Number(row.回收数量)
  return !Number.isNaN(quantity) && row.回收数量 !== null && row.回收数量 !== '' && quantity < row.登记数量
}

function previewAmount(row: MaterialRow): string {
  const quantity = Number(row.回收数量)
  if (row.回收数量 === null || row.回收数量 === '' || Number.isNaN(quantity)) {
    return '—'
  }
  return (quantity * row.单价).toFixed(2)
}

async function submitRecycling() {
  const entry = panelEntry.value
  if (!entry || submitting.value) {
    return
  }
  const targets = panelRows.value.filter((row) => row.checked && !row.已登记)
  if (!targets.length) {
    panelMessage.value = '请先勾选要登记的物资行'
    return
  }
  const items = targets.map((row) => ({
    物资类别: row.物资类别,
    回收数量: row.回收数量 === '' || row.回收数量 === null ? null : Number(row.回收数量),
    去向: row.去向,
    差异说明: row.差异说明,
  }))
  submitting.value = true
  try {
    const response = await request(`${ENDPOINT}/${entry.id}/recycling`, {
      method: 'POST',
      body: JSON.stringify({ values: { items } }),
    })
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.detail || '物资回收登记失败')
    }
    panelMessage.value = payload.message ?? ''
    const settled: any[] = payload.settled ?? []
    // 落记录的行就地锁定；被退回的行保持勾选与已填内容，方便修正后重提
    for (const record of settled) {
      const row = panelRows.value.find((item) => item.物资类别 === record['物资类别'])
      if (row) {
        row.已登记 = true
        row.checked = false
        row.回收数量 = record['回收数量']
        row.去向 = record['去向']
        row.差异说明 = record['差异说明']
        row.回收款 = record['回收款']
      }
    }
    rejectedRows.value = payload.rejected ?? []
    if (panelEntry.value && payload.entry) {
      panelEntry.value = payload.entry
    }
    await Promise.all([reload(), reloadLedger()])
  } catch (error) {
    panelMessage.value = error instanceof Error ? error.message : '物资回收登记失败'
  } finally {
    submitting.value = false
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

async function reloadLedger() {
  try {
    const response = await request(`${ENDPOINT}/recycling?size=200`)
    if (!response.ok) {
      throw new Error('物资去向清单读取失败')
    }
    const payload = await response.json()
    ledgerRows.value = payload.items ?? []
    ledgerTotal.value = payload.total ?? ledgerRows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '物资去向清单读取失败'
  }
}

onMounted(() => {
  void reload()
  void reloadLedger()
})
</script>

<style scoped>
.ledger-section {
  margin-top: 16px;
}
.ledger-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}
.ledger-head h3 {
  margin: 0;
  font-size: 14px;
}
.ledger-head span {
  color: var(--muted);
  font-size: 12px;
}
.recycling-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.recycling-panel {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 920px;
  max-width: 94vw;
  max-height: 86vh;
  overflow: auto;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-head h3 {
  margin: 0;
  font-size: 15px;
}
.panel-tip {
  color: var(--muted);
  font-size: 12px;
  margin: 8px 0 12px;
}
.panel-table .cell-input {
  width: 110px;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
}
.panel-table .cell-input.required {
  border-color: #b42318;
}
.panel-table tr.settled td {
  background: #f8fafc;
  color: var(--muted);
}
.rejected-box {
  margin-top: 10px;
  padding: 8px 12px;
  border: 1px solid #f3c2c2;
  border-radius: 6px;
  background: #fef3f3;
  color: #b42318;
  font-size: 12px;
}
.rejected-box p {
  margin: 0 0 4px;
}
.rejected-box ul {
  margin: 0;
  padding-left: 18px;
}
.panel-foot {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}
.panel-foot span {
  font-size: 13px;
}
.panel-message {
  color: var(--muted);
}
</style>
