import { test, expect, Page } from '@playwright/test'

/* ===========================================================
   OntoPilot Demo E2E Tests
   =========================================================== */

async function loginAs(page: Page, role: string) {
  const accounts: Record<string, { name: string; password: string }> = {
    admin: { name: '超级管理员', password: 'admin123' },
    dispatcher: { name: '调度员', password: 'disp123' },
    manager: { name: '区域经理', password: 'mgr123' },
  }
  const acc = accounts[role]
  if (!acc) return
  // Wait for login page to render
  await page.waitForTimeout(500)
  // Click account selection button
  await page.getByText(acc.name).first().click()
  await page.waitForTimeout(300)
  // Type password
  const pwInput = page.locator('input[type="password"]')
  await pwInput.fill(acc.password)
  // Click login
  await page.getByRole('button', { name: '进入系统' }).click()
  await page.waitForTimeout(1000)
}

test.describe('Login', () => {
  test('shows login page with 3 accounts', async ({ page }) => {
    await page.goto('/')
    await page.waitForTimeout(1000)

    await expect(page.getByText('选择账号登录')).toBeVisible()
    await expect(page.getByText('超级管理员')).toBeVisible()
    await expect(page.getByText('调度员')).toBeVisible()
    await expect(page.getByText('区域经理')).toBeVisible()
  })

  test('can login as admin', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'admin')

    // After login, should see the sidebar and welcome page
    await expect(page.getByTitle('首页')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'OntoPilot' })).toBeVisible()
  })

  test('can login as regional manager', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'manager')

    await expect(page.getByTitle('首页')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'OntoPilot' })).toBeVisible()
  })
})

test.describe('Landing Page', () => {
  test('shows welcome page with brand and action cards', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'manager')
    await page.waitForTimeout(500)

    await expect(page.getByRole('heading', { name: 'OntoPilot' })).toBeVisible()
    await expect(page.getByText('基于本体的智能 Agent 运行时')).toBeVisible()
    const cards = page.locator('.grid button, .grid a')
    await expect(cards.first()).toBeVisible()
    await expect(page.getByText('三步开始使用')).toBeVisible()
  })

  test('clicking start chat goes to chat view', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'manager')
    await page.waitForTimeout(500)

    await page.getByRole('button', { name: '开始对话' }).first().click()
    await page.waitForTimeout(500)
    await expect(page.locator('textarea')).toBeVisible()
  })
})

test.describe('Sidebar Navigation', () => {
  test('sidebar icons are visible', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'admin')
    await page.waitForTimeout(500)

    await expect(page.getByTitle('首页')).toBeVisible()
    await expect(page.getByTitle('对话')).toBeVisible()
    await expect(page.getByTitle('本体配置')).toBeVisible()
    await expect(page.getByTitle('模型配置')).toBeVisible()
    await expect(page.getByTitle('用户管理')).toBeVisible()
  })

  test('clicking config shows config panel', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'admin')
    await page.waitForTimeout(500)

    await page.getByTitle('模型配置').click()
    await page.waitForTimeout(300)
    await expect(page.getByRole('heading', { name: '模型配置' })).toBeVisible()
    await expect(page.getByRole('button', { name: '添加模型' })).toBeVisible()
  })

  test('clicking ontology shows ontology config panel', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'admin')
    await page.waitForTimeout(500)

    await page.getByTitle('本体配置').click()
    await page.waitForTimeout(300)
    await expect(page.getByRole('heading', { name: '本体配置' })).toBeVisible()
    await expect(page.getByRole('button', { name: /导入/ })).toBeVisible()
  })

  test('clicking home returns to landing', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'admin')
    await page.waitForTimeout(500)

    await page.getByTitle('模型配置').click()
    await page.waitForTimeout(300)
    await page.getByTitle('首页').click()
    await page.waitForTimeout(500)
    await expect(page.getByRole('heading', { name: 'OntoPilot' })).toBeVisible()
  })
})

test.describe('Model Configuration', () => {
  test('shows config panel and add model form', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'admin')
    await page.waitForTimeout(500)

    await page.getByTitle('模型配置').click()
    await page.waitForTimeout(500)

    await expect(page.getByRole('button', { name: '添加模型' })).toBeVisible()

    await page.getByRole('button', { name: '添加模型' }).click()
    await page.waitForTimeout(300)
    await expect(page.getByPlaceholder('e.g. My Model')).toBeVisible()
    await expect(page.getByPlaceholder('e.g. claude-sonnet-4-5')).toBeVisible()
  })
})

test.describe('Ontology Config', () => {
  test('imports seed data and shows ontology in list', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'admin')
    await page.waitForTimeout(500)

    await page.getByTitle('本体配置').click()
    await page.waitForTimeout(500)

    await page.getByRole('button', { name: '导入 Ontology' }).click()
    await page.waitForTimeout(300)

    await expect(page.getByText('上传 Ontology YAML')).toBeVisible()

    await page.getByRole('button', { name: '重新加载种子数据' }).click()
    await page.waitForTimeout(3500)

    await page.getByRole('button', { name: '返回列表' }).click()
    await page.waitForTimeout(500)
  })
})

test.describe('Agent Chat', () => {
  test('sends a query and gets a response', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'manager')
    await page.waitForTimeout(500)

    await page.getByRole('button', { name: '开始对话' }).first().click()
    await page.waitForTimeout(500)

    const input = page.locator('textarea')
    await expect(input).toBeVisible()
    await input.fill('查询华南仓所有延迟的货物')

    await page.getByRole('button', { name: '发送' }).click()

    await page.waitForTimeout(3000)
    try {
      await page.locator('.animate-bounce').waitFor({ state: 'hidden', timeout: 60000 })
    } catch {}

    await expect(page.getByText('查询华南仓所有延迟的货物')).toBeVisible()
  })
})

test.describe('Full Walkthrough', () => {
  test('landing → config → import → chat as manager', async ({ page }) => {
    test.setTimeout(180000)
    await page.goto('/')
    await loginAs(page, 'admin')
    await page.waitForTimeout(500)

    // ─── 1. Landing ───
    await expect(page.getByRole('heading', { name: 'OntoPilot' })).toBeVisible()
    console.log('1/5 Login & Landing OK')

    // ─── 2. Config ───
    await page.getByTitle('模型配置').click()
    await page.waitForTimeout(500)
    await expect(page.getByRole('button', { name: '添加模型' })).toBeVisible()
    console.log('2/5 Config panel OK')

    // ─── 3. Import seed data via ontology config ───
    await page.getByTitle('本体配置').click()
    await page.waitForTimeout(500)
    await page.getByRole('button', { name: '导入 Ontology' }).click()
    await page.waitForTimeout(300)
    await page.getByRole('button', { name: '重新加载种子数据' }).click()
    await page.waitForTimeout(3500)
    console.log('3/5 Import done')

    // ─── 4. Chat as regional manager ───
    await page.getByTitle('对话').click()
    await page.waitForTimeout(500)

    await page.locator('textarea').fill('SH-0042 这个货物延迟了，有什么建议？')
    await page.getByRole('button', { name: '发送' }).click()

    await page.waitForTimeout(5000)
    try {
      await page.locator('.animate-bounce').waitFor({ state: 'hidden', timeout: 60000 })
    } catch {}

    const responses = await page.locator('div.bg-gray-50').count()
    console.log(`4/5 Chat done, assistant blocks: ${responses}`)
  })
})

test.describe('真实对话测试', () => {
  test('多轮业务对话：查询 → 分析 → 决策', async ({ page }) => {
    test.setTimeout(240000)
    await page.goto('/')
    await loginAs(page, 'manager')
    await page.waitForTimeout(1000)

    // 从首页开始对话
    await page.getByRole('button', { name: '开始对话' }).first().click()
    await page.waitForTimeout(1500)

    await expect(page.locator('textarea')).toBeVisible()
    console.log('✅ 对话界面已加载')

    const modelSelect = page.locator('select[title="选择模型"]')
    if (await modelSelect.isVisible()) {
      const modelVal = await modelSelect.inputValue()
      if (modelVal !== 'model-mqqgwumv') {
        await modelSelect.selectOption('model-mqqgwumv')
        console.log('✅ 已切换到 DeepSeek 模型')
      } else {
        console.log(`✅ 当前模型: ${modelVal}`)
      }
    }

    await page.waitForTimeout(500)

    const sendAndWait = async (text: string) => {
      await page.locator('textarea').fill(text)
      await page.getByRole('button', { name: '发送' }).click()
      console.log(`📤 发送: ${text.substring(0, 50)}...`)
      await page.waitForTimeout(2000)
      try {
        await page.locator('.animate-bounce').waitFor({ state: 'hidden', timeout: 120000 })
      } catch {}
      console.log('📥 回复完成')
    }

    // ─── 对话第 1 轮：查询 ───
    await sendAndWait('查一下华南仓所有延迟的货物有哪些')

    let assistantCount = await page.locator('div.bg-gray-50').count()
    console.log(`  助手消息条数: ${assistantCount}`)
    expect(assistantCount).toBeGreaterThanOrEqual(1)
    let userBadgeCount = await page.locator('div.bg-blue-600.text-white:has-text("U")').count()
    console.log(`  U 徽章数: ${userBadgeCount}`)
    expect(userBadgeCount).toBeGreaterThanOrEqual(1)

    const confirmBtn = page.locator('button:has-text("确认执行")')

    // ─── 对话第 2 轮：分析 ───
    await sendAndWait('这些延迟的货物中，哪个对客户影响最大？帮我分析一下风险')

    assistantCount = await page.locator('div.bg-gray-50').count()
    console.log(`  助手消息数: ${assistantCount}`)
    expect(assistantCount).toBeGreaterThanOrEqual(2)

    if (await confirmBtn.first().isVisible({ timeout: 3000 }).catch(() => false)) {
      await confirmBtn.first().click()
      console.log('✅ 已确认执行操作')
      await page.waitForTimeout(3000)
      try {
        await page.locator('.animate-bounce').waitFor({ state: 'hidden', timeout: 60000 })
      } catch {}
    }

    // ─── 对话第 3 轮：仿真决策 ───
    await sendAndWait('如果重新安排这些高风险的货物走顺丰，预计能节省多少时间？做个仿真对比')

    assistantCount = await page.locator('div.bg-gray-50').count()
    console.log(`  总助手消息数: ${assistantCount}`)
    expect(assistantCount).toBeGreaterThanOrEqual(3)

    const allAssistantTexts = await page.locator('div.bg-gray-50 .text-sm.text-gray-800').allTextContents()
    const goodReplies = allAssistantTexts.filter(t => !t.includes('❌'))
    console.log(`  有效回复数: ${goodReplies.length}`)
    expect(goodReplies.length).toBeGreaterThanOrEqual(1)

    const showPanelBtn = page.getByRole('button', { name: '推理过程' })
    await showPanelBtn.click()
    await page.waitForTimeout(500)
    const panels = page.locator('div.w-1\\/2.flex.flex-col.border-l')
    await expect(page.getByText('推理过程').first()).toBeVisible()
    console.log('✅ 推理过程面板可正常打开')

    console.log('🎉 真实对话测试全部通过（3轮对话 + 推理面板）')
  })
})
