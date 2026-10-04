import { expect, test } from '@playwright/test'
import path from 'node:path'

const projectRoot = path.resolve(process.cwd(), '..')

async function login(page) {
  await page.goto('/login')
  await page.getByPlaceholder('请输入用户名').fill('admin')
  await page.getByPlaceholder('请输入密码').fill('admin123')
  await page.getByRole('button', { name: '进入分析系统' }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole('heading', { name: '城市客流综合态势' })).toBeVisible()
}

test.describe.serial('城市客流系统完整业务链路', () => {
  test('登录、菜单与本地地图', async ({ page }) => {
    await login(page)
    await expect(page.getByText('当前系统使用内置模拟城市交通数据集进行功能验证')).toBeVisible()
    await expect(page.locator('canvas')).toHaveCount(4, { timeout: 20_000 })
    await page.getByText('区域热力', { exact: true }).click()
    await page.getByText('OD 流向', { exact: true }).click()
    await expect(page.getByText('VIRTUAL DEMO CITY · LOCAL GEOJSON')).toBeVisible()
  })

  test('上传 Demo 并执行 Spark 清洗', async ({ page }) => {
    await login(page)
    await page.getByRole('link', { name: '数据管理' }).click()
    await expect(page.getByRole('heading', { name: '数据管理' })).toBeVisible()
    const datasetRows = page.locator('.el-table').first().locator('tbody tr')
    await expect(datasetRows.first()).toBeVisible()
    const previousCount = await datasetRows.count()
    await page.locator('input[type="file"]').setInputFiles(path.join(projectRoot, 'data', 'demo', 'passenger_flow_demo.csv'))
    await expect(page.getByText('数据集上传成功')).toBeVisible({ timeout: 20_000 })
    await expect(datasetRows).toHaveCount(previousCount + 1)
    const firstRow = datasetRows.first()
    await firstRow.getByText('Spark 清洗', { exact: true }).click()
    await expect(page.getByText('Spark 清洗任务已提交')).toBeVisible()
    const newestTask = page.locator('.el-table').nth(1).locator('tbody tr').first()
    await expect(newestTask).toContainText('已完成', { timeout: 90_000 })
  })

  test('运行 Spark 离线分析', async ({ page }) => {
    await login(page)
    await page.getByRole('link', { name: 'Spark 分析' }).click()
    await page.getByRole('button', { name: '运行全量分析' }).click()
    await expect(page.getByText(/分析任务 #\d+ 已启动/)).toBeVisible()
    await expect(page.getByText('Spark 正在分析')).toBeHidden({ timeout: 90_000 })
    await expect(page.locator('canvas').first()).toBeVisible()
  })

  test('Structured Streaming 启停与窗口更新', async ({ page }) => {
    await login(page)
    await page.getByRole('link', { name: '实时客流' }).click()
    await page.getByRole('button', { name: '启动实时模拟' }).click()
    await expect(page.getByText('运行中', { exact: true })).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('.stat-card').nth(1)).not.toContainText('0人次', { timeout: 35_000 })
    await page.getByRole('button', { name: '暂停', exact: true }).click()
    await expect(page.getByText('已暂停', { exact: true })).toBeVisible({ timeout: 25_000 })
    await page.getByRole('button', { name: '继续', exact: true }).click()
    await expect(page.getByText('运行中', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '停止', exact: true }).click()
    await page.getByRole('button', { name: '重置', exact: true }).click()
    await expect(page.getByText('未启动', { exact: true })).toBeVisible()
  })

  test('训练 ARIMA 并生成预测预警', async ({ page }) => {
    await login(page)
    await page.getByRole('link', { name: '客流预测' }).click()
    await page.getByRole('button', { name: '训练新模型' }).click()
    await page.getByText('ARIMA', { exact: true }).last().click()
    await page.getByRole('button', { name: '开始训练' }).click()
    await expect(page.getByText(/模型任务 #\d+ 已提交/)).toBeVisible()
    await expect(page.getByText('ARIMA 训练完成')).toBeVisible({ timeout: 90_000 })
    await page.getByRole('link', { name: '预警与决策' }).click()
    await page.getByRole('button', { name: '根据最新预测生成预警' }).click()
    await expect(page.getByText(/已根据预测结果生成 \d+ 条预警/)).toBeVisible()
  })

  test('日志查询与用户管理', async ({ page }) => {
    await login(page)
    await page.getByRole('link', { name: '操作日志' }).click()
    await expect(page.getByRole('heading', { name: '操作日志' })).toBeVisible()
    await expect(page.locator('.el-table__body tbody tr').first()).toBeVisible()
    await page.getByRole('link', { name: '用户管理' }).click()
    const oldRow = page.locator('.el-table__body tbody tr').filter({ hasText: 'e2e_user' })
    if (await oldRow.count()) {
      await oldRow.getByText('删除', { exact: true }).click()
      await page.getByRole('button', { name: '确定' }).click()
      await expect(oldRow).toHaveCount(0)
    }
    await page.getByRole('button', { name: '新增用户' }).click()
    const dialog = page.getByRole('dialog')
    await dialog.locator('input').nth(0).fill('e2e_user')
    await dialog.locator('input').nth(1).fill('自动测试用户')
    await dialog.locator('input').nth(2).fill('e2e123456')
    await dialog.getByRole('button', { name: '保存' }).click()
    await expect(page.getByText('用户信息已保存')).toBeVisible()
    const row = page.locator('.el-table__body tbody tr').filter({ hasText: 'e2e_user' })
    await expect(row).toBeVisible()
    await row.getByText('删除', { exact: true }).click()
    await page.getByRole('button', { name: '确定' }).click()
    await expect(page.getByText('用户已删除')).toBeVisible()
  })
})
